// One status vocabulary for every layout: each state gets its own icon and words, so "saved",
// "kept on this device" and "both versions kept" never look alike. Colours are shadcn's default
// theme tokens only (no per-host presets): the icon carries the difference.

import { CircleAlert, Cloud, CloudCheck, CloudOff, CloudUpload, GitCompareArrows, LoaderCircle, Lock, type LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"
import { relativeTime, type State } from "@/lib/hosted-files/core"
import { useHostedFiles, useHostedFilesContext, useHostedFilesUi } from "./provider"

export type StatusKind = "signed-out" | "signing-in" | "idle" | "saved" | "dirty" | "saving" | "offline" | "conflict" | "view-only" | "error"

export interface StatusView {
  kind: StatusKind
  label: string // a few words, for chips and rows; starts with "Saved" exactly when saved
  detail: string // one sentence, for tooltips and headers
  tone: "quiet" | "attention" | "danger"
}

const DOT: LucideIcon = (({ className }: { className?: string }) => (
  <span aria-hidden className={cn("inline-flex size-4 items-center justify-center", className)}>
    <span className="size-1.5 rounded-full bg-current" />
  </span>
)) as unknown as LucideIcon

export const STATUS_ICON: Record<StatusKind, LucideIcon> = {
  "signed-out": Cloud,
  "signing-in": LoaderCircle,
  idle: CloudUpload,
  saved: CloudCheck,
  dirty: DOT,
  saving: LoaderCircle,
  offline: CloudOff,
  conflict: GitCompareArrows,
  "view-only": Lock,
  error: CircleAlert,
}

export const TONE_CLASS: Record<StatusView["tone"], string> = {
  quiet: "text-muted-foreground",
  attention: "text-foreground",
  danger: "text-destructive",
}

export function describeStatus(state: State, signingIn = false, appName = "this app"): StatusView {
  const file = state.file
  if (!state.user) {
    if (signingIn) return { kind: "signing-in", label: "Signing in…", detail: "Signing in to save your files online.", tone: "quiet" }
    return { kind: "signed-out", label: "Not saved online", detail: `Sign in to save your files online with ${appName}. Until then they stay in this browser.`, tone: "quiet" }
  }
  switch (state.status) {
    case "saving":
      return { kind: "saving", label: "Saving…", detail: file ? `Saving version ${file.version + 1}…` : "Saving…", tone: "quiet" }
    case "offline":
      return {
        kind: "offline",
        label: "On this device",
        detail: state.message ?? "Not saved online yet — kept on this device. It uploads by itself when you're back online.",
        tone: "attention",
      }
    case "conflict":
      return {
        kind: "conflict",
        label: "Both versions kept",
        detail: state.message ?? "Changed somewhere else — both versions are in History. Yours is on top.",
        tone: "attention",
      }
    case "error":
      return { kind: "error", label: "Not saved", detail: state.message ?? "Not saved.", tone: "danger" }
    case "dirty":
      // WHY the message wins: "Restored your unsaved text" must be readable where the status sits.
      return { kind: "dirty", label: state.message ?? "Unsaved changes", detail: state.message ?? "Changes not saved yet.", tone: "quiet" }
  }
  if (file?.locked) {
    const limit = state.me?.app?.limit ?? null
    return {
      kind: "view-only",
      label: "View-only",
      detail: `View-only: the free plan edits your ${limit === null ? "" : `${limit} `}most recent files in ${state.me?.app?.name ?? appName}. You can still open, download, rename or trash it.`,
      tone: "quiet",
    }
  }
  if (!file) return { kind: "idle", label: state.message ?? "Not saved yet", detail: "This document isn't saved online yet. Save to keep it.", tone: "quiet" }
  const when = relativeTime(state.lastSavedAt ?? file.updatedAt)
  // The "Updated elsewhere — Reload" message is shown beside it by <StaleHeadButton>, never instead of it.
  return { kind: "saved", label: `Saved ${when}`, detail: `Saved online ${when} · version ${file.version}`, tone: "quiet" }
}

export function useStatus(): StatusView {
  const { state } = useHostedFiles()
  const { signingIn } = useHostedFilesUi()
  const { appName } = useHostedFilesContext()
  return describeStatus(state, signingIn, appName)
}

export function StatusGlyph({ status, className }: { status: StatusView; className?: string }) {
  const Icon = STATUS_ICON[status.kind]
  const spin = status.kind === "saving" || status.kind === "signing-in"
  return <Icon aria-hidden className={cn("size-4 shrink-0", TONE_CLASS[status.tone], spin && "animate-spin", className)} />
}
