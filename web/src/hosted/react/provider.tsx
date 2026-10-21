// <HostedFilesProvider>: the one thing a host adds besides its chosen layout component.
// It implements the core's UiHost seam (name prompts, the limit dialog, Open, History, the
// sign-in dialog) as React state, and hands every layout the same actions — so the layouts differ in
// where things sit, never in what a click does.
//
//   const hostedFiles = new HostedFiles({ server, app, getContent, setContent, newDocument })
//   <HostedFilesProvider hostedFiles={hostedFiles} appName="My App" appIcon={<MyLogo />}> <HostedFilesSidebar /> … </HostedFilesProvider>

import { createContext, useCallback, useContext, useEffect, useMemo, useSyncExternalStore, type ReactNode } from "react"
import { toast } from "sonner"
import { DISCARD, HostedFilesError, type FileMeta, type HostedFiles, type SignInFlow, type State, withExtension } from "@/lib/hosted-files/core"

// WHY derived from the class instead of importing the interface: the seam is exactly what
// HostedFiles#ui accepts, whatever the core names it.
export type UiHost = NonNullable<HostedFiles["ui"]>
export type NameAnswer = string | null | typeof DISCARD

export type Panel =
  | { kind: "browse"; tab: "files" | "trash"; query: string }
  | { kind: "history"; fileId: string }
  | { kind: "limit"; variant: "files" | "locked"; waiting: boolean }
  | { kind: "name"; title: string; value: string; okLabel: string; discard: boolean; resolve: (answer: NameAnswer) => void }

export interface UiSnapshot {
  panel: Panel | null
  // The open sign-in dialog's flow (SPEC v2.7); `signingIn` is true while it is open.
  signIn: SignInFlow | null
  signingIn: boolean
  revision: number
}

// A small external store (like a query client). One dialog at a time (SPEC §8): opening a panel
// answers a pending name prompt with "cancel" so the core's awaiting save never hangs.
export class HostedFilesUiStore {
  private snap: UiSnapshot = { panel: null, signIn: null, signingIn: false, revision: 0 }
  private listeners = new Set<() => void>()

  subscribe = (fn: () => void) => {
    this.listeners.add(fn)
    return () => {
      this.listeners.delete(fn)
    }
  }
  getSnapshot = () => this.snap

  private patch(next: Partial<UiSnapshot>): void {
    this.snap = { ...this.snap, ...next }
    for (const fn of this.listeners) fn()
  }

  get panel(): Panel | null {
    return this.snap.panel
  }

  open(panel: Panel): void {
    const previous = this.snap.panel
    this.patch({ panel })
    if (previous?.kind === "name" && previous !== panel) previous.resolve(null)
  }

  close(): void {
    const previous = this.snap.panel
    this.patch({ panel: null })
    if (previous?.kind === "name") previous.resolve(null)
  }

  // Replace the open panel's fields without closing it (search text, tab, waiting flag).
  update<K extends Panel["kind"]>(kind: K, fields: Partial<Extract<Panel, { kind: K }>>): void {
    const panel = this.snap.panel
    if (panel?.kind === kind) this.patch({ panel: { ...panel, ...fields } as Panel })
  }

  // Answers an open name prompt and closes it.
  answer(value: NameAnswer): void {
    const panel = this.snap.panel
    if (panel?.kind !== "name") return
    this.patch({ panel: null })
    panel.resolve(value)
  }

  setSignIn(flow: SignInFlow | null): void {
    this.patch({ signIn: flow, signingIn: !!flow })
  }

  // × / Escape: hostedFiles.signIn() rejects with `cancelled`, and the core hides the dialog.
  cancelSigningIn(): void {
    this.snap.signIn?.cancel()
  }

  // Lists refetch when this moves (after a rename, trash, restore, duplicate …).
  bump(): void {
    this.patch({ revision: this.snap.revision + 1 })
  }
}

// One cached snapshot per instance. WHY: `hostedFiles.state` returns a fresh copy on every read,
// and useSyncExternalStore needs a stable value between changes.
interface StateStore {
  get: () => State
  subscribe: (fn: () => void) => () => void
}
const stateStores = new WeakMap<HostedFiles, StateStore>()

function stateStore(hostedFiles: HostedFiles): StateStore {
  let store = stateStores.get(hostedFiles)
  if (store) return store
  let snapshot = hostedFiles.state
  const listeners = new Set<() => void>()
  let unsubscribe: (() => void) | null = null
  store = {
    get: () => snapshot,
    subscribe: (fn) => {
      listeners.add(fn)
      unsubscribe ??= hostedFiles.subscribe((next) => {
        snapshot = next
        for (const listener of listeners) listener()
      })
      return () => {
        listeners.delete(fn)
        if (listeners.size === 0 && unsubscribe) {
          unsubscribe()
          unsubscribe = null
        }
      }
    },
  }
  stateStores.set(hostedFiles, store)
  return store
}

interface HostedFilesContextValue {
  hostedFiles: HostedFiles
  ui: HostedFilesUiStore
  appName: string
  /** The appName prop as given (the sign-in dialog otherwise asks the server for the name). */
  appNameOption: string | undefined
  appIcon: ReactNode | string | undefined
  openAccount: () => Promise<void> | void
}

const HostedFilesContext = createContext<HostedFilesContextValue | null>(null)

export interface HostedFilesProviderProps {
  hostedFiles: HostedFiles
  /** Optional: create it yourself to open panels from your own chrome. */
  ui?: HostedFilesUiStore
  /** Shown in layouts that name the app (Home, Sidebar) and atop the sign-in dialog; defaults to the server's name for the app. */
  appName?: string
  /** The sign-in dialog's mark: an element or an image URL. Default: the Simple Hosted Files logo. */
  appIcon?: ReactNode | string
  /** Default opens the account page, already signed in, in a new tab. */
  onOpenAccount?: (url: string) => void
  children: ReactNode
}

export function HostedFilesProvider({ hostedFiles, ui, appName, appIcon, onOpenAccount, children }: HostedFilesProviderProps) {
  const store = useMemo(() => ui ?? new HostedFilesUiStore(), [ui])
  const state = useSyncExternalStore(stateStore(hostedFiles).subscribe, stateStore(hostedFiles).get)

  useEffect(() => {
    const host: UiHost = {
      promptName: (opts) =>
        new Promise<NameAnswer>((resolve) => {
          store.open({ kind: "name", title: opts.title, value: opts.value, okLabel: opts.okLabel ?? "Save", discard: !!opts.discard, resolve })
        }),
      showLimit: (variant) => store.open({ kind: "limit", variant, waiting: false }),
      closeLimit: () => {
        if (store.panel?.kind === "limit") store.close()
      },
      showOpen: () => store.open({ kind: "browse", tab: "files", query: "" }),
      showHistory: () => {
        const file = hostedFiles.state.file
        if (file) store.open({ kind: "history", fileId: file.id })
      },
      showSignIn: (flow) => {
        store.setSignIn(flow)
        return () => {
          if (store.getSnapshot().signIn === flow) store.setSignIn(null)
        }
      },
    }
    hostedFiles.ui = host
    return () => {
      if (hostedFiles.ui === host) hostedFiles.ui = null
    }
  }, [hostedFiles, store])

  const value = useMemo<HostedFilesContextValue>(
    () => ({
      hostedFiles,
      ui: store,
      appName: appName ?? state.me?.app?.name ?? "this app",
      appNameOption: appName,
      appIcon,
      openAccount: onOpenAccount ? () => onOpenAccount(hostedFiles.accountUrl) : () => hostedFiles.openAccount(),
    }),
    [hostedFiles, store, appName, appIcon, state.me?.app?.name, onOpenAccount],
  )
  return <HostedFilesContext.Provider value={value}>{children}</HostedFilesContext.Provider>
}

export function useHostedFilesContext(): HostedFilesContextValue {
  const value = useContext(HostedFilesContext)
  if (!value) throw new Error("Hosted Files components must sit inside <HostedFilesProvider>")
  return value
}

/** The instance and its live state (re-renders on every state change). */
export function useHostedFiles(): { hostedFiles: HostedFiles; state: State } {
  const { hostedFiles } = useHostedFilesContext()
  const store = stateStore(hostedFiles)
  const state = useSyncExternalStore(store.subscribe, store.get)
  return { hostedFiles, state }
}

export function useHostedFilesUi(): UiSnapshot & { store: HostedFilesUiStore } {
  const { ui } = useHostedFilesContext()
  const snap = useSyncExternalStore(ui.subscribe, ui.getSnapshot)
  return { ...snap, store: ui }
}

// Every user-facing action, with the Lit bar's error rules: a plan refusal the core has not shown
// yet opens the limit panel; errors the core already reported stay in the status line.
export function useHostedFilesActions() {
  const { hostedFiles, ui, openAccount } = useHostedFilesContext()

  const run = useCallback(
    async <T,>(action: () => Promise<T> | T, success?: string): Promise<T | undefined> => {
      try {
        const result = await action()
        ui.bump()
        if (success) toast(success)
        return result
      } catch (err) {
        ui.bump()
        if (err instanceof HostedFilesError && (err.code === "file_limit" || err.code === "locked") && !err.reported) {
          ui.open({ kind: "limit", variant: err.code === "locked" ? "locked" : "files", waiting: false })
          return undefined
        }
        if (err instanceof HostedFilesError && (err.reported || err.code === "popup_closed" || err.code === "cancelled")) return undefined
        hostedFiles.report(err)
        toast.error(err instanceof Error ? err.message : String(err))
        return undefined
      }
    },
    [hostedFiles, ui],
  )

  return useMemo(() => {
    const ext = () => hostedFiles.state.me?.app?.extension
    const prompt = async (title: string, value: string, okLabel: string) => {
      const answer = await hostedFiles.ui?.promptName({ title, value, okLabel })
      return typeof answer === "string" && answer.trim() ? answer.trim() : null
    }
    const renameFile = async (file: FileMeta, name: string) => {
      if (file.id === hostedFiles.state.file?.id) await hostedFiles.rename(name)
      else hostedFiles.patchFile(await hostedFiles.files.rename(file.id, name))
    }
    const actions = {
      signIn: () => run(() => hostedFiles.signIn()),
      signOut: () => run(() => hostedFiles.signOut()),
      newFile: () => {
        ui.close()
        return run(() => hostedFiles.newFile())
      },
      open: (id: string) => {
        ui.close()
        return run(() => hostedFiles.open(id))
      },
      save: () => run(() => hostedFiles.save()),
      saveAs: (name?: string) => run(() => hostedFiles.saveAs(name)),
      setAutosave: (on: boolean) => hostedFiles.setAutosave(on),
      showFiles: () => ui.open({ kind: "browse", tab: "files", query: "" }),
      showTrash: () => ui.open({ kind: "browse", tab: "trash", query: "" }),
      showHistory: (file?: FileMeta | null) => {
        const target = file ?? hostedFiles.state.file
        if (target) ui.open({ kind: "history", fileId: target.id })
      },
      // Rename any file; the open one goes through hostedFiles.rename so the session stays exact.
      rename: (file: FileMeta, name: string) =>
        run(async () => {
          const clean = name.trim()
          if (clean && clean !== file.name) await renameFile(file, clean)
        }),
      promptRename: (file: FileMeta) =>
        run(async () => {
          const name = await prompt("Rename", file.name, "Rename")
          if (name && name !== file.name) await renameFile(file, name)
        }),
      duplicate: (file: FileMeta) =>
        run(async () => {
          const copy = await hostedFiles.files.duplicate(file.id, `${file.name} (copy)`)
          await hostedFiles.me()
          toast(`Duplicated as “${copy.name}”`)
          return copy
        }),
      trash: (file: FileMeta) =>
        run(async () => {
          if (file.id === hostedFiles.state.file?.id) await hostedFiles.trashCurrent()
          else hostedFiles.patchFile(await hostedFiles.files.trash(file.id))
          await hostedFiles.me().catch(() => {})
          // WHY an Undo in the toast: delete is "move to trash" (SPEC §0); say so at the moment it happens.
          toast(`Moved “${file.name}” to the trash`, {
            description: "Restorable for 30 days.",
            action: { label: "Undo", onClick: () => void actions.restore(file) },
          })
        }),
      restore: (file: FileMeta) =>
        run(async () => {
          hostedFiles.patchFile(await hostedFiles.files.restore(file.id))
          await hostedFiles.me().catch(() => {})
        }, `Restored “${file.name}”`),
      download: (file: FileMeta, version?: number) =>
        run(() => hostedFiles.files.download(file.id, { version }), `Downloaded ${withExtension(file.name, ext())}`),
      downloadCurrent: () => run(() => hostedFiles.downloadCurrent()),
      downloadLocal: () => run(() => hostedFiles.downloadLocal()),
      restoreVersion: (n: number) => {
        ui.close()
        return run(() => hostedFiles.restoreVersion(n), `Version ${n} is now the current version`)
      },
      reload: () => run(() => hostedFiles.reload()),
      exportAll: () => run(() => hostedFiles.exportAll(), "Exported every file as a .zip"),
      upgrade: () =>
        run(async () => {
          await hostedFiles.upgrade()
          ui.update("limit", { waiting: true })
        }),
      manageBilling: () => run(() => hostedFiles.manageBilling()),
      account: () => run(() => openAccount()),
      close: () => ui.close(),
    }
    return actions
  }, [hostedFiles, ui, run, openAccount])
}

export type HostedFilesActions = ReturnType<typeof useHostedFilesActions>
