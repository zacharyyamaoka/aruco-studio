// The Studio's Simple Hosted Files dialogs: the registry's shared dialogs
// (simple-hosted-files web/registry/hosted-files-react/components/hosted-files/
// dialogs.tsx) rebuilt in the Studio's kit, over the copied hooks (../react,
// verbatim). Same steps, copy and data-testids (SPEC v2.5, v2.7); the kit's
// tokens make them follow the skin. The title bar's half is in
// ../../app/TopBar.tsx.
// WHY the kit, not shadcn (Zach, 2026-10-20 night): one UI, skinned by tokens.
import { useEffect, useRef, useState, useSyncExternalStore, type ReactNode } from "react";
import { Button, Dialog, IconButton, cn } from "@bam/ui";
import { ArchiveRestore, Copy, Download, History, Lock, Pencil, RotateCcw, ShieldCheck, Trash2 } from "lucide-react";
import { DISCARD, daysUntil, humanSize, relativeTime, type FileMeta, type SignInFlow, type VersionMeta } from "../core";
import { HostedFilesProvider, matches, useFiles, useHostedFiles, useHostedFilesActions, useHostedFilesUi, useVersions, type Panel } from "../react";
import { dismissToast, useToast } from "../shims/sonner";
import { APP_NAME, hostedFiles, nameNextSave } from "../hosted";
import { useStudio } from "../../store";
import "./hosted.css";

export function HostedProvider({ icon, children }: { icon?: ReactNode; children: ReactNode }) {
  return <HostedFilesProvider hostedFiles={hostedFiles()} appName={APP_NAME} appIcon={icon}>{children}</HostedFilesProvider>;
}

// ---- account + plan ---------------------------------------------------------------------------

export function usePlan() {
  const { state } = useHostedFiles();
  const me = state.me;
  const limit = me?.app?.limit ?? null;
  const files = me?.app?.files ?? 0;
  const editable = limit === null ? files : Math.min(files, limit);
  return {
    me, pro: me?.plan === "pro", limit, files, editable,
    viewOnly: limit === null ? 0 : Math.max(0, files - limit),
    price: me?.billing.priceLabel ?? "$4/month",
    canUpgrade: !!me?.billing.canUpgrade,
    appName: me?.app?.name ?? "this app",
  };
}

/** "12 of 100 free files in Aruco Studio", with a bar; "Pro" on Pro. */
export function UsageLine() {
  const plan = usePlan();
  if (!plan.me) return null;
  if (plan.pro) return <div className="shf-usage" data-testid="shf-usage">Pro · unlimited files in every app</div>;
  return (
    <div className="shf-usage" data-testid="shf-usage">
      <div className="shf-usage-text">
        <span>{plan.editable} of {plan.limit} free files in {plan.appName}</span>
        {plan.viewOnly > 0 && <span className="shf-muted">{plan.viewOnly} view-only</span>}
      </div>
      <div className="shf-bar" role="progressbar" aria-label="Free files used" aria-valuenow={plan.editable} aria-valuemax={plan.limit ?? 0}>
        <i style={{ width: `${plan.limit ? (100 * plan.editable) / plan.limit : 0}%` }} />
      </div>
    </div>
  );
}

export function initials(name: string | null | undefined, email: string | undefined): string {
  return (name?.trim() || email || "?").charAt(0).toUpperCase();
}

function TrustNote({ kind }: { kind: "history" | "trash" | "export" }) {
  const text = {
    history: "Every save is kept as a version. Restoring adds a new version — nothing is overwritten.",
    trash: "Files in the trash can be restored for 30 days, then they're deleted.",
    export: "Your files are yours: download any file, or export all of them, on any plan.",
  }[kind];
  return <p className="shf-trust"><ShieldCheck size={13} /><span>{text}</span></p>;
}

// ---- Open: your files and the trash -----------------------------------------------------------

function fileMeta(file: FileMeta): string {
  if (file.trashedAt) return `Deleted in ${daysUntil(file.purgeAt)} days`;
  return `${relativeTime(file.updatedAt)} · ${humanSize(file.size)}`;
}

function FileRow({ file, current }: { file: FileMeta; current: boolean }) {
  const actions = useHostedFilesActions();
  const trashed = !!file.trashedAt;
  const open = () => { if (!trashed) void actions.open(file.id); };
  // a row action never also opens the row (SPEC §8)
  const act = (fn: () => void) => (e?: { stopPropagation(): void }) => { e?.stopPropagation(); fn(); };
  return (
    <div role={trashed ? "listitem" : "button"} tabIndex={trashed ? -1 : 0} className={cn("shf-row", !trashed && "open", current && "current")}
      data-testid="shf-file-row" data-file-id={file.id} data-locked={file.locked ? "true" : "false"}
      onClick={open} onKeyDown={(e) => { if (e.key === "Enter" && e.target === e.currentTarget) open(); }}>
      <div className="shf-row-main">
        <div className="shf-row-name">
          <span className="shf-name">{file.name}</span>
          {current && <span className="kit-pill t-accent">Open</span>}
          {file.locked && <span className="kit-pill" title="View-only on the free plan"><Lock size={9} /> View-only</span>}
        </div>
        <div className="shf-muted">{fileMeta(file)}</div>
      </div>
      <span className="shf-row-acts" onClick={(e) => e.stopPropagation()}>
        {trashed ? (
          <>
            <Button size="sm" testid="shf-file-restore" icon={<ArchiveRestore size={12} />} onClick={act(() => void actions.restore(file))}>Restore</Button>
            <IconButton icon={<Download size={14} />} title={`Download ${file.name}`} testid="shf-file-download" onClick={act(() => void actions.download(file))} />
          </>
        ) : (
          <>
            <IconButton icon={<Pencil size={14} />} title="Rename…" testid="shf-file-rename" onClick={act(() => void actions.promptRename(file))} />
            <IconButton icon={<Copy size={14} />} title="Duplicate" testid="shf-file-duplicate" onClick={act(() => void actions.duplicate(file))} />
            <IconButton icon={<Download size={14} />} title={`Download ${file.name}`} testid="shf-file-download" onClick={act(() => void actions.download(file))} />
            <IconButton icon={<History size={14} />} title="Version history" testid="shf-file-history" onClick={act(() => actions.showHistory(file))} />
            <IconButton icon={<Trash2 size={14} />} title="Move to trash" testid="shf-file-trash" onClick={act(() => void actions.trash(file))} />
          </>
        )}
      </span>
    </div>
  );
}

function FileList({ query, trashed }: { query: string; trashed: boolean }) {
  const { state } = useHostedFiles();
  const { data, error } = useFiles({ trashed });
  const files = data?.filter((f) => matches(f, query));
  return (
    <div className="shf-list" role="list">
      {error && <p className="shf-empty bad">{error}</p>}
      {!error && !files && <p className="shf-empty">Loading…</p>}
      {!error && files?.length === 0 && <p className="shf-empty">{query ? "No files match that search." : trashed ? "Trash is empty." : "No files yet."}</p>}
      {files?.map((f) => <FileRow key={f.id} file={f} current={f.id === state.file?.id} />)}
    </div>
  );
}

function BrowseDialog() {
  const { panel, store } = useHostedFilesUi();
  const browse = panel?.kind === "browse" ? panel : null;
  return (
    <Dialog open={!!browse} onClose={() => store.close()} title="Your files" testid="shf-files-dialog" width={520}>
      {browse && (
        <div className="shf-pad">
          <div className="shf-browse-head">
            <span className="kit-tab-list shf-tabs" role="tablist">
              {(["files", "trash"] as const).map((tab) => (
                <button key={tab} type="button" role="tab" aria-selected={browse.tab === tab} className={cn("kit-tab tab", browse.tab === tab && "on")}
                  data-testid={`shf-tab-${tab}`} onClick={() => store.update("browse", { tab })}>
                  {tab === "trash" && <Trash2 size={12} />}{tab === "files" ? "Files" : "Trash"}
                </button>
              ))}
            </span>
            <input className="kit-text shf-search" type="search" data-testid="shf-search" aria-label="Search files" placeholder="Search files" autoFocus
              value={browse.query} onChange={(e) => store.update("browse", { query: e.target.value })} />
          </div>
          <FileList query={browse.query} trashed={browse.tab === "trash"} />
          <TrustNote kind={browse.tab === "trash" ? "trash" : "export"} />
        </div>
      )}
    </Dialog>
  );
}

// ---- History ----------------------------------------------------------------------------------

function VersionRow({ file, version, head }: { file: FileMeta; version: VersionMeta; head: boolean }) {
  const actions = useHostedFilesActions();
  const { state } = useHostedFiles();
  const isOpen = state.file?.id === file.id;
  const locked = isOpen && !!state.file?.locked;
  const kind = version.kind ?? "manual";
  return (
    <div className={cn("shf-row", version.superseded && "superseded")} data-testid="shf-version-row" data-version={version.version} data-kind={kind}>
      <div className="shf-row-main">
        <div className="shf-row-name">
          <span className="shf-name">{relativeTime(version.createdAt)}</span>
          {kind === "auto" && <span className="shf-muted">Autosave</span>}
          {head && <span className="kit-pill t-accent">Current</span>}
        </div>
        <div className="shf-muted" title={new Date(version.createdAt).toLocaleString()}>Version {version.version} · {humanSize(version.size)}</div>
      </div>
      <span className="shf-row-acts">
        <IconButton icon={<Download size={14} />} title={`Download version ${version.version}`} testid="shf-version-download"
          onClick={() => void actions.download(file, version.version)} />
        {!head && isOpen && (
          <Button size="sm" testid="shf-version-restore" disabled={locked} icon={<RotateCcw size={12} />}
            onClick={() => void actions.restoreVersion(version.version)}>Restore</Button>
        )}
      </span>
    </div>
  );
}

function VersionList({ fileId }: { fileId: string }) {
  const { data: files } = useFiles();
  const { state } = useHostedFiles();
  const { data, error } = useVersions(fileId);
  const [showAll, setShowAll] = useState(false);
  const file = (state.file?.id === fileId ? state.file : files?.find((f) => f.id === fileId)) ?? null;
  if (error) return <p className="shf-empty bad">{error}</p>;
  if (!data || !file) return <p className="shf-empty">Loading…</p>;
  // the superseded autosaves of an editing burst sit behind one disclosure (SPEC v2.4)
  const head = data[0]?.version;
  const hidden = data.filter((v) => v.superseded && v.version !== head).length;
  const shown = showAll ? data : data.filter((v) => !v.superseded || v.version === head);
  return (
    <div className="shf-list">
      {shown.map((v) => <VersionRow key={v.version} file={file} version={v} head={v.version === head} />)}
      {hidden > 0 && (
        <button type="button" className="shf-link" data-testid="shf-show-autosaves" aria-expanded={showAll} onClick={() => setShowAll(!showAll)}>
          {showAll ? "Hide extra autosaves" : `Show all autosaves (last 24 h) · ${hidden} more`}
        </button>
      )}
    </div>
  );
}

function HistoryDialog() {
  const { panel, store } = useHostedFilesUi();
  const { state } = useHostedFiles();
  const fileId = panel?.kind === "history" ? panel.fileId : null;
  const open = state.file?.id === fileId ? state.file : null;
  return (
    <Dialog open={!!fileId} onClose={() => store.close()} title={<>Version history{open && <span className="shf-muted shf-title-note">{open.name}</span>}</>}
      testid="shf-history-dialog" width={480}>
      {fileId && (
        <div className="shf-pad">
          {open?.locked && <p className="shf-muted">View-only on the free plan — versions can be downloaded, not restored.</p>}
          {!open && <p className="shf-muted">Open this file to restore a version.</p>}
          <VersionList fileId={fileId} />
          <TrustNote kind="history" />
        </div>
      )}
    </Dialog>
  );
}

// ---- the limit --------------------------------------------------------------------------------

function LimitDialog() {
  const { panel, store } = useHostedFilesUi();
  const { state } = useHostedFiles();
  const plan = usePlan();
  const actions = useHostedFilesActions();
  const limit = panel?.kind === "limit" ? panel : null;
  const name = state.file?.name;
  const copy = limit?.variant === "locked"
    ? { title: `${name ? `“${name}”` : "This file"} is view-only on the free plan.`,
      body: `Free edits your ${plan.limit ?? 3} most recent files in each app. You can still open, download, rename or trash it — nothing is deleted.` }
    : { title: `You've used your ${plan.limit ?? 3} free files in ${plan.appName}.`, body: "Nothing is lost: this document is kept on this device until it's saved." };
  return (
    <Dialog open={!!limit} onClose={() => store.close()} title={copy.title} testid="shf-limit-dialog" width={420}>
      <div className="shf-pad shf-stack">
        <p>{copy.body}</p>
        {plan.canUpgrade && <Button variant="primary" testid="shf-limit-upgrade" onClick={() => void actions.upgrade()}>Upgrade — {plan.price}, unlimited files in every app</Button>}
        <Button testid="shf-limit-download" icon={<Download size={13} />} onClick={() => void actions.downloadLocal()}>Download instead</Button>
        <Button variant="ghost" testid="shf-limit-manage" onClick={() => actions.showFiles()}>Manage files</Button>
        {limit?.waiting && <p className="shf-muted">Waiting for checkout to finish. This closes by itself and saves your document.</p>}
      </div>
    </Dialog>
  );
}

// ---- name prompt (Save / Save as / Rename / "Save this first?") ------------------------------

function NameForm({ panel }: { panel: Extract<Panel, { kind: "name" }> }) {
  const { store } = useHostedFilesUi();
  // WHY the document's name for an untitled save: the cloud file's name IS
  // the document's name (Zach, 2026-10-20 night); the core only knows "Untitled"
  const [value, setValue] = useState(() => panel.value === hostedFiles().untitledName ? useStudio.getState().doc.name : panel.value);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => { input.current?.focus(); input.current?.select(); }, []);
  return (
    <form className="shf-pad shf-stack" onSubmit={(e) => {
      e.preventDefault();
      const name = value.trim();
      if (!name) return;
      // the open document's Save / Save as (not a rename of a listed file, and
      // not "Save this first?", whose content the core has already taken)
      if (panel.title !== "Rename" && !panel.discard) nameNextSave(name);
      store.answer(name);
    }}>
      {panel.discard && <p className="shf-muted">This document isn't saved online yet.</p>}
      <input ref={input} className="kit-text shf-wide" data-testid="shf-name-input" aria-label="Name" maxLength={200} value={value} onChange={(e) => setValue(e.target.value)} />
      <div className="shf-buttons">
        {panel.discard && <Button variant="ghost" testid="shf-name-discard" onClick={() => store.answer(DISCARD)}>Don't save</Button>}
        <span className="grow" />
        <Button testid="shf-name-cancel" onClick={() => store.close()}>Cancel</Button>
        <Button type="submit" variant="primary" testid="shf-name-ok">{panel.okLabel}</Button>
      </div>
    </form>
  );
}

function NameDialog() {
  const { panel, store } = useHostedFilesUi();
  const name = panel?.kind === "name" ? panel : null;
  return (
    <Dialog open={!!name} onClose={() => store.close()} title={name?.title ?? ""} testid="shf-name-dialog" width={360}>
      {name && <NameForm key={name.title + name.value} panel={name} />}
    </Dialog>
  );
}

// ---- sign-in (SPEC v2.7) ----------------------------------------------------------------------

// Google's "G" mark, unaltered, as its sign-in branding guidelines require.
function GoogleMark() {
  return (
    <svg viewBox="0 0 48 48" width="18" height="18" aria-hidden="true">
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
      <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
      <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
    </svg>
  );
}

function SignInCard({ flow }: { flow: SignInFlow }) {
  const view = useSyncExternalStore(flow.subscribe, flow.getView);
  const [email, setEmail] = useState(view.email);
  const [code, setCode] = useState("");
  const emailInput = useRef<HTMLInputElement>(null);
  const codeInput = useRef<HTMLInputElement>(null);
  const methods = view.methods;
  const focusKey = `${view.step}:${view.loading}`;
  // the caret goes where the next keystroke belongs: the email, then the code
  useEffect(() => {
    const target = focusKey.startsWith("code") ? codeInput.current : emailInput.current;
    const frame = requestAnimationFrame(() => target?.focus());
    return () => cancelAnimationFrame(frame);
  }, [focusKey]);
  const error = view.error && <p role="alert" className="shf-error" data-testid="shf-signin-error">{view.error}</p>;

  let body: ReactNode;
  if (view.step === "google") {
    body = (
      <>
        <div role="status" className="shf-center"><b>Finish in the Google window</b><span className="shf-muted">Can't see it? It may be behind this window.</span></div>
        <Button className="shf-wide" testid="shf-signin-cancel" onClick={() => flow.cancelGoogle()}>Cancel</Button>
      </>
    );
  } else if (view.step === "code") {
    body = (
      <>
        <div className="shf-center"><b>Check your email</b><span className="shf-muted">We sent a 6-digit code to <b className="shf-email">{view.email}</b></span></div>
        <form className="shf-stack" onSubmit={(e) => { e.preventDefault(); void flow.verify(code); }}>
          <label htmlFor="shf-signin-code" className="shf-label">Code</label>
          <input ref={codeInput} id="shf-signin-code" className="kit-text shf-wide shf-code" data-testid="shf-signin-code-input" inputMode="numeric"
            autoComplete="one-time-code" maxLength={6} placeholder="123456" value={code} onChange={(e) => setCode(e.target.value)} />
          {error}
          <Button type="submit" variant="primary" className="shf-wide" testid="shf-signin-code-verify" disabled={view.busy}>Continue</Button>
        </form>
        <div className="shf-center-row">
          <button type="button" className="shf-link" data-testid="shf-signin-code-back" onClick={() => flow.back()}>Use a different email</button>
          <span aria-hidden="true">·</span>
          <button type="button" className="shf-link" data-testid="shf-signin-resend" disabled={view.busy} onClick={() => void flow.resend()}>Send a new code</button>
        </div>
        {view.notice && <p role="status" className="shf-muted shf-center">{view.notice}</p>}
      </>
    );
  } else {
    body = (
      <>
        <p className="shf-center shf-muted">Create a free account to save your files online and open them on any device.</p>
        {methods?.google && (
          <button type="button" className="shf-google" data-testid="shf-signin-google" disabled={view.busy} onClick={() => flow.google()}>
            <span className="shf-google-g"><GoogleMark /></span>Sign in with Google
          </button>
        )}
        {methods?.google && methods.email && <div role="separator" className="shf-or">or</div>}
        {methods?.email && (
          <form className="shf-stack" onSubmit={(e) => { e.preventDefault(); void flow.startEmail(email); }}>
            <label htmlFor="shf-signin-email" className="shf-label">Email address</label>
            <input ref={emailInput} id="shf-signin-email" className="kit-text shf-wide" data-testid="shf-signin-email-input" type="email"
              autoComplete="email" placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} />
            <Button type="submit" className="shf-wide" testid="shf-signin-email-continue" disabled={view.busy}>{view.busy ? "Sending a code…" : "Continue with email"}</Button>
          </form>
        )}
        {methods && !methods.google && !methods.email && <p className="shf-center shf-muted">Sign-in isn't available on this server yet.</p>}
        {view.step === "choose" && error}
        {!methods && !view.loading && <Button className="shf-wide" onClick={() => flow.retry()}>Try again</Button>}
      </>
    );
  }
  return (
    <div className="shf-signin">
      {body}
      <footer className="shf-signin-foot">
        <span>
          <a href={view.termsUrl} target="_blank" rel="noopener" data-testid="shf-signin-terms">Terms of Use</a>
          <span aria-hidden="true"> · </span>
          <a href={view.privacyUrl} target="_blank" rel="noopener" data-testid="shf-signin-privacy">Privacy Policy</a>
        </span>
        <span>Accounts by {view.serviceName}</span>
      </footer>
    </div>
  );
}

function SignInDialog({ icon }: { icon?: ReactNode }) {
  const { signIn, store } = useHostedFilesUi();
  // WHY keep the last flow: the card stays filled while the dialog closes; `n`
  // gives every new sign-in a fresh card (empty fields)
  const [shown, setShown] = useState<{ flow: SignInFlow; n: number } | null>(signIn ? { flow: signIn, n: 0 } : null);
  if (signIn && signIn !== shown?.flow) setShown({ flow: signIn, n: (shown?.n ?? 0) + 1 });
  return (
    <Dialog open={!!signIn} onClose={() => store.cancelSigningIn()} testid="shf-signin-dialog" width={340} className="shf-signin-dialog"
      title={<span className="shf-signin-title">{icon}{APP_NAME}</span>}>
      {shown && <SignInCard key={shown.n} flow={shown.flow} />}
    </Dialog>
  );
}

// ---- toasts (the bindings' toast(), ../shims/sonner.ts) ---------------------------------------

/** The bindings' toasts; it sits in the stage, beside the Studio's own note. */
export function HostedToast() {
  const t = useToast();
  useEffect(() => {
    if (!t) return;
    const timer = setTimeout(() => dismissToast(t.id), t.action ? 8000 : 4000);
    return () => clearTimeout(timer);
  }, [t]);
  if (!t) return null;
  return (
    <div className={cn("toast shf-toast", t.error && "bad")} role="status" data-testid="shf-toast">
      <span>{t.message}{t.description && <span className="shf-toast-note"> {t.description}</span>}</span>
      {t.action && <button type="button" className="shf-toast-act" onClick={() => { dismissToast(t.id); t.action!.onClick(); }}>{t.action.label}</button>}
    </div>
  );
}

/** Every dialog of the title bar. */
export function HostedDialogs({ icon }: { icon?: ReactNode }) {
  return (
    <>
      <BrowseDialog />
      <HistoryDialog />
      <LimitDialog />
      <NameDialog />
      <SignInDialog icon={icon} />
    </>
  );
}
