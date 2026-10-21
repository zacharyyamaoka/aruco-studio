// Home ("Back to files" in the main menu): the registry's hosted-files-home
// (simple-hosted-files web/registry/hosted-files-home, "V4 · Home dashboard":
// Miro / Canva / tldraw.com's "Your files" page) rebuilt in the Studio's kit,
// over the copied hooks (../react, verbatim), as ./HostedDialogs.tsx rebuilt
// its dialogs. Same behaviour: cards with search, a New tile and a Trash view;
// opening a card (or New) goes to the editor. Signed out (the Studio's
// addition): "Sign in to save online", the work on this device and the
// examples as cards.
// WHY the editor stays mounted (hidden) under Home (the registry's reason):
// the document and the editor's own state survive a look at the file list.
// The view itself is app/home.ts's (a history entry: Back returns Home).
import { useEffect, useState } from "react";
import { Button, cn } from "@bam/ui";
import { ArrowLeft, Clock, FileText, LogIn, Plus, Trash2 } from "lucide-react";
import { daysUntil, relativeTime, type FileMeta } from "../core";
import { matches, useFiles, useHostedFiles, useHostedFilesActions } from "../react";
import { UsageLine, initials, usePlan } from "./HostedDialogs";
import { EXAMPLES } from "../../model/examples";
import { ShapesThumb, openExample } from "../../app/ExamplesDialog";
import { BrandCube } from "../../app/TopBar";
import { leaveHome, useHome } from "../../app/home";
import { useStudio } from "../../store";

type Tab = "files" | "trash";

/** A card: a picture, the name, a line under it. */
function Card({ testid, id, pic, name, meta, onOpen, current, children }: {
  testid: string; id?: string; pic: React.ReactNode; name: string; meta: React.ReactNode; onOpen?: () => void; current?: boolean; children?: React.ReactNode;
}) {
  return (
    <div role={onOpen ? "button" : "listitem"} tabIndex={onOpen ? 0 : -1} className={cn("home-card", onOpen && "open")} data-testid={testid} data-id={id}
      onClick={onOpen} onKeyDown={(e) => { if (onOpen && e.key === "Enter" && e.target === e.currentTarget) onOpen(); }}>
      <div className={cn("home-pic", current && "current")}>{pic}</div>
      <div className="home-card-text">
        <span className="home-name" title={name}>{name}</span>
        <span className="home-meta">{meta}</span>
      </div>
      {children}
    </div>
  );
}

/** The document in the editor, drawn (the open cloud file's card, or the local draft's). */
function DocPic() {
  const shapes = useStudio((s) => s.doc.shapes);
  return <ShapesThumb shapes={shapes} />;
}

function FileCard({ file, current }: { file: FileMeta; current: boolean }) {
  const actions = useHostedFilesActions();
  const trashed = !!file.trashedAt;
  const open = trashed ? undefined : () => { void actions.open(file.id).then(leaveHome); };
  return (
    <Card testid="home-file" id={file.id} name={file.name} current={current} onOpen={open}
      pic={current ? <DocPic /> : <FileText size={26} className="home-file-ic" />}
      meta={trashed ? `Deleted in ${daysUntil(file.purgeAt)} days` : <>Edited {relativeTime(file.updatedAt)}{current && <span className="kit-pill t-accent">Open</span>}{file.locked && <span className="kit-pill">View-only</span>}</>}>
      {trashed && (
        <Button size="sm" className="home-restore" testid="home-restore" onClick={() => void actions.restore(file)}>Restore</Button>
      )}
    </Card>
  );
}

function NewTile() {
  const actions = useHostedFilesActions();
  const plan = usePlan();
  if (plan.limit !== null && plan.editable >= plan.limit && !plan.pro) {
    return (
      <div className="home-new limit" data-testid="home-limit">
        <b>{plan.editable} of {plan.limit} free files used</b>
        <span className="home-meta">New files stay on this device until you upgrade or move one to the trash.</span>
        <span className="home-row">
          {plan.canUpgrade && <Button size="sm" variant="primary" onClick={() => void actions.upgrade()}>Upgrade — {plan.price}</Button>}
          <Button size="sm" testid="home-new" onClick={() => { void actions.newFile().then(leaveHome); }}>New on this device</Button>
        </span>
      </div>
    );
  }
  return (
    <button type="button" className="home-new" data-testid="home-new" onClick={() => { void actions.newFile().then(leaveHome); }}>
      <Plus size={22} />New file
    </button>
  );
}

/** Signed in: your files (Recent) and the trash, searchable. */
function Files({ tab, query }: { tab: Tab; query: string }) {
  const { state } = useHostedFiles();
  const { data, error } = useFiles({ trashed: tab === "trash" });
  const files = data?.filter((f) => matches(f, query));
  return (
    <>
      <h1 className="home-h1">{tab === "trash" ? "Trash" : "Recents"}</h1>
      {tab === "trash" && <p className="home-note">Files in the trash can be restored for 30 days, then they're deleted.</p>}
      <div className="home-grid" role="list" data-testid="home-files">
        {tab === "files" && !query && <NewTile />}
        {files?.map((f) => <FileCard key={f.id} file={f} current={f.id === state.file?.id} />)}
      </div>
      {error && <p className="home-empty bad">{error}</p>}
      {!error && !files && <p className="home-empty">Loading…</p>}
      {!error && files?.length === 0 && <p className="home-empty">{query ? "No files match that search." : tab === "trash" ? "Trash is empty." : "No files yet."}</p>}
    </>
  );
}

/** Signed out: sign in, the work on this device, the examples. */
function SignedOut() {
  const actions = useHostedFilesActions();
  const name = useStudio((s) => s.doc.name);
  return (
    <>
      <div className="home-signin" data-testid="home-signin">
        <div>
          <b>Sign in to save online</b>
          <span className="home-meta">Your files in the cloud, on any device. The Studio works the same without it.</span>
        </div>
        <Button variant="primary" icon={<LogIn size={13} />} testid="shf-signin" onClick={() => void actions.signIn()}>Sign in</Button>
      </div>
      <h1 className="home-h1">On this device</h1>
      <div className="home-grid" role="list">
        <Card testid="home-draft" name={name} pic={<DocPic />} meta="Your work here, kept in this browser" onOpen={leaveHome} current />
      </div>
      <h1 className="home-h1">Examples</h1>
      <div className="home-grid" role="list" data-testid="home-examples">
        {EXAMPLES.map((e) => (
          <Card key={e.id} testid="home-example" id={e.id} name={e.name} meta={e.note} pic={<ShapesThumb shapes={e.shapes} />}
            onOpen={() => { void openExample(e.id).then(leaveHome); }} />
        ))}
      </div>
    </>
  );
}

export function HostedHome() {
  const home = useHome();
  const { state } = useHostedFiles();
  const actions = useHostedFilesActions();
  const docName = useStudio((s) => s.doc.name);
  const [tab, setTab] = useState<Tab>("files");
  const [query, setQuery] = useState("");
  const { data: trashed } = useFiles({ trashed: true, enabled: home && !!state.user });
  const user = state.user;
  useEffect(() => {
    if (!home) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && !e.defaultPrevented && !document.querySelector("[data-kit-popup][data-open], [role=dialog]")) leaveHome(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [home]);
  if (!home) return null;
  return (
    <div className="home" data-testid="home" data-signed-in={user ? "1" : "0"}>
      <header className="home-head">
        <span className="home-brand"><BrandCube /><b>ArUco Studio</b></span>
        <Button variant="ghost" icon={<ArrowLeft size={14} />} testid="home-back" title="Back to the editor (Esc)" className="home-back" onClick={leaveHome}>
          <span className="home-back-name">{docName}</span>
        </Button>
        {user && (
          <input className="kit-text home-search" type="search" data-testid="home-search" aria-label="Search files" placeholder="Search files"
            value={query} onChange={(e) => setQuery(e.target.value)} />
        )}
        <span className="home-grow" />
        {user ? (
          <span className="home-account" data-testid="home-account" title={user.email}>
            <span className="shf-avatar" aria-hidden="true">{initials(user.name, user.email)}</span>
            <span className="home-who">{user.name || user.email}</span>
          </span>
        ) : (
          <Button size="sm" icon={<LogIn size={12} />} testid="home-signin-top" onClick={() => void actions.signIn()}>Sign in</Button>
        )}
      </header>
      <div className="home-body">
        {user && (
          <nav className="home-nav" aria-label="Files">
            <button type="button" className={cn("home-tab", tab === "files" && "on")} data-testid="home-tab-files" onClick={() => setTab("files")}><Clock size={14} />Recents</button>
            <button type="button" className={cn("home-tab", tab === "trash" && "on")} data-testid="home-tab-trash" onClick={() => setTab("trash")}>
              <Trash2 size={14} />Trash<span className="home-count">{trashed?.length || ""}</span>
            </button>
            <span className="home-grow" />
            <div className="home-usage"><UsageLine /></div>
          </nav>
        )}
        <main className="home-main">{user ? <Files tab={tab} query={query} /> : <SignedOut />}</main>
      </div>
    </div>
  );
}
