// The chrome around the canvas, Figma's (V2 "Figma · Corner pills" in
// reports/media/studio-layout-proposals-2026-10-20.html, picked by Zach on
// 2026-10-20 night: "For the design let's please follow Figma!"; UI3's as
// help.figma.com draws it): two corner pills over the canvas and, in the
// bottom corner, ? and GitHub.
// - Top left, the document pill: the main menu (the logo with ⌄: Back to
//   files, then File, Edit, Export, View, Preferences and Help and account as
//   submenus), then the title bar of Simple Hosted Files (the registry's
//   hosted-files-title-bar, in the kit): the document's name, which is its
//   cloud file's name (click to rename), a quiet status dot (it opens
//   History), and ⌄: this file only (its status, Rename, Duplicate, Version
//   history, Move to trash; on a phone also Download for CAD).
// - Top right: Download for CAD, then Verify | Print (K, S: in the tooltips,
//   no key badges).
// - Bottom right: ? (the keys, and how the start went) and GitHub.
// WHY one item in one menu (Zach, 2026-10-21: "Please unify these two file
// menus, they are redundant... Copy how figma does it"; simple-hosted-files
// SPEC "v2.9 Menus follow Figma's split"): the logo's menu is the app's (File
// ▸ New, Open, Save, Download, Export, Trash, Autosave; Help and account ▸ the
// person), the name's ⌄ is this file's, and nothing is in both. Signed out,
// File keeps what needs no account and Help and account offers the sign-in.
// WHY no preset in the pill (Zach): "Preset shouldn't be on the file because
// it's applied on a per marker basis!" -- it is the panel's Make tab's, and
// Edit › Presets… sets the one a new marker starts with.
// WHY no core chip (Zach): "for me that's back end details ... maybe just in a
// panel etc. you can show that status thing ... but it shouldn't clutter the
// main viewer" -- what waits says it (panel/Waiting.tsx); ? shows the status.
// WHY no key badges on the corner buttons and GitHub at the bottom (Zach):
// "No need for hot keys on those corner buttons. GitHub maybe better in the
// bottom corner."
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Menu as M } from "@base-ui/react/menu";
import { Popover } from "@base-ui/react/popover";
import { Button, Dialog, Glyph, Kbd, Menu, MenuItem, MenuSeparator, cn, useTheme } from "@bam/ui";
import { Check, ChevronRight, CircleHelp, Moon, RotateCcw, Sun } from "lucide-react";
import { newDocument, renameDocument } from "../hosted/hosted";
import { useHostedFiles, useHostedFilesActions, useHostedFilesUi, useStatus } from "../hosted/react";
import { UsageLine, initials, usePlan } from "../hosted/ui/HostedDialogs";
import { useCoreStatus } from "../coreSource";
import { WaitLine, failedDetail, reload, startingText, useTick } from "../panel/Waiting";
import { useStudio } from "../store";
import { SKINS, useSkin } from "../skins/skins";
import { exportPdf, exportSvg, openDoc, openPrint, openVerify, saveDoc } from "./commands";
import { ZoomItems } from "../zoom/ZoomItems";
import { openHome } from "./home";

export const GITHUB = "https://github.com/zacharyyamaoka/aruco-studio";
/** At or under this width the pills fold into the ⌄ menu (styles.css, the same number). */
const NARROW = "(max-width: 640px)";

function GithubMark() {
  return (
    <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">
      <path fill="currentColor" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}

// The brand mark: the line-art block (#3's style at 0.48 x the
// side) with the "winky face" bitmap on top, no tile; the same paths as
// public/icon.svg.
// WHY: Zach's round-4 pick on 2026-10-20 (reports/media/logo-slab-series-
// 2026-10-18.html). The top bitmap and this stroke weight are checked not to
// decode as any OpenCV dictionary, and the pass is narrow: re-check any
// change to the bitmap, the height or the stroke.
export function BrandCube() {
  return (
    <svg className="brand-cube" viewBox="0 0 64 64" width="20" height="20" aria-hidden="true">
      <path fill="#f1f3f6" stroke="#111418" strokeWidth="2.6" strokeLinejoin="round" d="M2 40.31L32 57.63L32 41.01L2 23.69z" />
      <path fill="#dfe3e8" stroke="#111418" strokeWidth="2.6" strokeLinejoin="round" d="M62 40.31L32 57.63L32 41.01L62 23.69z" />
      <path fill="#ffffff" stroke="#111418" strokeWidth="2.6" strokeLinejoin="round" d="M32 6.37L62 23.69L32 41.01L2 23.69z" />
      <path fill="#111418" d="M32 10.87L54.2 23.69L50.39 25.89L28.19 13.07zM28.41 12.94L32.22 15.14L28.3 17.41L24.49 15.21zM35.7 17.15L39.62 19.41L35.7 21.68L31.78 19.41zM46.8 23.56L50.61 25.76L46.69 28.02L42.88 25.82zM24.71 15.08L32.22 19.41L28.3 21.68L20.79 17.34zM35.7 21.42L39.62 23.69L35.7 25.95L31.78 23.69zM43.1 25.69L46.91 27.89L42.99 30.16L39.18 27.96zM21.01 17.21L24.82 19.41L20.9 21.68L17.09 19.48zM28.3 21.42L35.92 25.82L32 28.09L24.38 23.69zM39.4 27.83L43.21 30.03L39.29 32.29L35.48 30.09zM17.31 19.35L21.12 21.55L17.2 23.81L13.39 21.61zM24.6 23.56L28.52 25.82L24.6 28.09L20.68 25.82zM35.7 29.97L39.51 32.17L35.59 34.43L31.78 32.23zM13.61 21.49L35.81 34.3L32 36.5L9.8 23.69z" />
    </svg>
  );
}

/** True at a phone's width (NARROW), following resizes. */
export function useNarrow(): boolean {
  const query = () => typeof window !== "undefined" && window.matchMedia(NARROW).matches;
  const [narrow, setNarrow] = useState(query);
  useEffect(() => {
    const mq = window.matchMedia(NARROW);
    const on = () => setNarrow(mq.matches);
    mq.addEventListener("change", on);
    on();
    return () => mq.removeEventListener("change", on);
  }, []);
  return narrow;
}

/** Download for CAD (Zach, 2026-10-18: "we want it ready to drop into a cad
 *  program"): the doors to the CAD add-ins. Neither is packaged yet, so both
 *  are shown disabled, "coming soon", and link nowhere. */
function CadMenu() {
  const none = () => {};
  return (
    <Menu icon="download" label="Download for CAD" testid="menu-cad" align="end">
      <MenuItem icon="cube" testid="cad-fusion" disabled onClick={none} hint="coming soon"
        label={<span className="cad-item"><b>Fusion 360</b><span className="cad-note">the add-in is being rebuilt on this core</span></span>} />
      <MenuItem icon="cube" testid="cad-onshape" disabled onClick={none} hint="coming soon"
        label={<span className="cad-item"><b>Onshape</b></span>} />
    </Menu>
  );
}

/** A submenu of the main menu (Figma's File ›, Edit ›, …): it opens on hover
 *  or a click, to the side. On a phone (`inline`) it is a group in the menu
 *  itself: beside a 230 px menu there is no side, and a submenu laid over its
 *  parent would hide the next one. */
function Sub({ label, testid, inline, children }: { label: string; testid: string; inline?: boolean; children: ReactNode }) {
  if (inline) {
    return (
      <M.Group className="mm-group" data-testid={`${testid}-popup`}>
        <M.GroupLabel className="mm-h">{label}</M.GroupLabel>
        {children}
      </M.Group>
    );
  }
  return (
    <M.SubmenuRoot>
      <M.SubmenuTrigger className="kit-menu-item mm-sub" data-testid={testid}>
        <span className="ic" /><span className="kit-menu-label">{label}</span><ChevronRight size={14} className="mm-chev" />
      </M.SubmenuTrigger>
      <M.Portal>
        <M.Positioner side="right" align="start" sideOffset={4} alignOffset={-5} className="kit-menu-positioner">
          <M.Popup className="kit-menu-popup mm-popup" data-kit-popup="menu" data-testid={`${testid}-popup`}>{children}</M.Popup>
        </M.Positioner>
      </M.Portal>
    </M.SubmenuRoot>
  );
}

/** A radio-like row: a check when it is the one. */
function Pick({ on, label, testid, onClick, disabled, title }: { on: boolean; label: ReactNode; testid: string; onClick: () => void; disabled?: boolean; title?: string }) {
  return (
    <M.Item className={cn("kit-menu-item", disabled && "dis")} data-testid={testid} aria-checked={on} role="menuitemradio" disabled={disabled} title={title}
      onClick={onClick}>
      <span className="ic">{on && <Check size={14} />}</span><span className="kit-menu-label">{label}</span>
    </M.Item>
  );
}

/** An on / off row: a check when it is on. `stay`: the menu stays open (it
 *  says its new state where it was clicked, SPEC v2.4's Autosave). */
function Toggle({ on, label, testid, onClick, stay }: { on: boolean; label: ReactNode; testid: string; onClick: () => void; stay?: boolean }) {
  return (
    <M.Item className="kit-menu-item" data-testid={testid} aria-checked={on} role="menuitemcheckbox" closeOnClick={!stay} onClick={onClick}>
      <span className="ic">{on && <Check size={14} />}</span><span className="kit-menu-label">{label}</span>
    </M.Item>
  );
}

/** File ▸ (the registry's HostedFileMenuItems, with the Studio's own: Open
 *  from this computer, Examples): every file action that is not about the
 *  open file. Signed out, what needs an account is not here (as the registry
 *  does); Help and account ▸ has the sign-in. */
function FileItems() {
  const { state } = useHostedFiles();
  const actions = useHostedFilesActions();
  const file = state.file;
  const st = useStudio.getState;
  if (!state.user) {
    return (
      <>
        <MenuItem icon="sketch" label="New" testid="cmd-new" onClick={newDocument} />
        <MenuItem label="Open from this computer…" testid="cmd-open" onClick={() => void openDoc()} />
        <MenuSeparator />
        <MenuItem icon="download" label="Download" hint=".arucostudio-web.json" testid="cmd-save" onClick={saveDoc} />
        <MenuSeparator />
        <MenuItem icon="library" label="Examples…" testid="cmd-examples" onClick={() => st().openModal("examples")} />
      </>
    );
  }
  return (
    <>
      <MenuItem icon="sketch" label="New" testid="cmd-new" onClick={newDocument} />
      <MenuItem label="Open…" hint="your files" testid="shf-action-files" onClick={actions.showFiles} />
      <MenuItem label="Open from this computer…" testid="cmd-open" onClick={() => void openDoc()} />
      <MenuSeparator />
      <MenuItem label="Save" hint="Ctrl+S" testid="shf-action-save" disabled={!!file?.locked} onClick={() => void actions.save()} />
      <MenuItem label="Save as…" testid="shf-action-saveas" onClick={() => void actions.saveAs()} />
      {/* the bytes the server holds; a document not saved online yet is the Studio's own file */}
      <MenuItem icon="download" label="Download" hint=".arucostudio-web.json" testid="shf-action-download" onClick={() => (file ? void actions.downloadCurrent() : saveDoc())} />
      <MenuItem label="Export all files" hint=".zip" testid="shf-action-export" onClick={() => void actions.exportAll()} />
      <MenuSeparator />
      <MenuItem label="Trash…" hint="the files you trashed" testid="shf-action-trash-view" onClick={actions.showTrash} />
      <MenuItem icon="library" label="Examples…" testid="cmd-examples" onClick={() => st().openModal("examples")} />
      <MenuSeparator />
      <Toggle on={state.autosave} label="Autosave" testid="shf-autosave-toggle" stay onClick={() => actions.setAutosave(!state.autosave)} />
    </>
  );
}

/** Help and account ▸ (Figma's; the registry's HostedAccountMenuItems after
 *  the Studio's help): the keys, GitHub, About, then who is signed in, their
 *  plan and usage, Your account, Sign out; signed out, the sign-in. */
function AccountItems({ onHelp }: { onHelp: () => void }) {
  const { state } = useHostedFiles();
  const actions = useHostedFilesActions();
  const { signingIn } = useHostedFilesUi();
  const plan = usePlan();
  const user = state.user;
  return (
    <>
      <MenuItem label="Keyboard shortcuts" hint="?" testid="help-menu" onClick={onHelp} />
      <M.LinkItem className="kit-menu-item" href={GITHUB} target="_blank" rel="noreferrer" data-testid="github-menu">
        <span className="ic mm-gh"><GithubMark /></span><span className="kit-menu-label">GitHub</span><span className="hint">the source</span>
      </M.LinkItem>
      {/* the landing page (Zach, 2026-10-20); a real navigation, not a route */}
      <M.LinkItem className="kit-menu-item" href="/about/" data-testid="brand">
        <span className="ic"><BrandCube /></span><span className="kit-menu-label">About ArUco Studio</span>
      </M.LinkItem>
      <MenuSeparator />
      {user ? (
        <>
          <div className="shf-account" data-testid="shf-account-card">
            <span className="shf-avatar" aria-hidden="true">{initials(user.name, user.email)}</span>
            <span className="shf-who">{user.name && <b>{user.name}</b>}<span className="shf-who-email">{user.email}</span></span>
          </div>
          <UsageLine />
          {plan.canUpgrade && <MenuItem label={`Upgrade — ${plan.price}`} testid="shf-action-upgrade" onClick={() => void actions.upgrade()} />}
          <MenuSeparator />
          <MenuItem label="Your account ↗" testid="shf-action-account" onClick={() => void actions.account()} />
          <MenuItem label="Sign out" testid="shf-action-signout" onClick={() => void actions.signOut()} />
        </>
      ) : (
        <MenuItem label={signingIn ? "Signing in…" : "Sign in to save online"} testid="shf-action-signin" disabled={signingIn} onClick={() => void actions.signIn()} />
      )}
    </>
  );
}

/** The main menu (Figma UI3's: the logo with ⌄, top left): Back to files, then
 *  File, Edit, Export, View, Preferences and Help and account, each a submenu.
 *  WHY no inline File / Edit / Export (Zach, 2026-10-20 night): "Figma doesn't
 *  have the file edit export etc there... it's in a drop down when you press
 *  the icon, and there is also the button there when you click the icon to go
 *  home". */
function MainMenu({ onHelp }: { onHelp: () => void }) {
  const canUndo = useStudio((s) => s.canUndo);
  const canRedo = useStudio((s) => s.canRedo);
  const markers = useStudio((s) => s.doc.features.length);
  const view3d = useStudio((s) => s.view3d);
  const markerInfo = useStudio((s) => s.markerInfo);
  const [theme, setTheme] = useTheme();
  const [skin, setSkin] = useSkin();
  const pinned = skin.theme ? `${skin.name} is ${skin.theme} only` : undefined;
  const inline = useNarrow();
  const st = useStudio.getState;
  return (
    <M.Root modal={false}>
      <M.Trigger className="logo-btn" data-testid="menu-main" title="Main menu" aria-label="Main menu">
        <BrandCube />
        <svg viewBox="0 0 16 16" width="10" height="10" aria-hidden="true" className="chev"><path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.6" /></svg>
      </M.Trigger>
      <M.Portal>
        <M.Positioner side="bottom" align="start" sideOffset={8} className="kit-menu-positioner">
          <M.Popup className="kit-menu-popup mm-popup" data-kit-popup="menu" data-testid="main-menu">
            <MenuItem label="Back to files" testid="cmd-home" onClick={openHome} />
            <MenuSeparator />
            <Sub label="File" testid="menu-file" inline={inline}>
              <FileItems />
            </Sub>
            <Sub label="Edit" testid="menu-edit" inline={inline}>
              <MenuItem label="Undo" hint="Ctrl+Z" testid="cmd-undo" disabled={!canUndo} onClick={() => st().undo()} />
              <MenuItem label="Redo" hint="Ctrl+Shift+Z" testid="cmd-redo" disabled={!canRedo} onClick={() => st().redo()} />
              <MenuSeparator />
              <MenuItem icon="marker" label="ArUco Re-ID…" testid="cmd-reid" disabled={!markers}
                title={markers ? undefined : "No markers yet: make an ArUco Extrude (A) first"} onClick={() => st().openModal("reid")} />
              <MenuItem icon="inkjet" label="Presets…" testid="cmd-presets" title="How a marker is made: the open marker's preset, or the one a new marker starts with"
                onClick={() => st().openModal("presets")} />
            </Sub>
            <Sub label="Export" testid="menu-export" inline={inline}>
              <MenuItem icon="print" label="Print…" hint="S" testid="cmd-print" onClick={openPrint} />
              <MenuItem label="SVG" hint="the marker, true size" testid="cmd-svg" onClick={() => void exportSvg()} />
              <MenuItem label="PDF" hint="the marker's preset's page" testid="cmd-pdf" onClick={() => void exportPdf()} />
            </Sub>
            <Sub label="View" testid="menu-view" inline={inline}>
              <Pick on={!view3d} label={<>2D <span className="hint">the sketch</span></>} testid="cmd-view-2d" onClick={() => st().setView3d(false)} />
              <Pick on={view3d} label={<>3D <span className="hint">the model</span></>} testid="cmd-view-3d" onClick={() => st().setView3d(true)} />
              <MenuSeparator />
              {/* WHY (Zach, 2026-10-21): "give me the option to add a lable under neatht he aruco markers ... You can put it here in the view tab" */}
              <Toggle on={markerInfo} label={<>Marker info <span className="hint">id · dictionary · size</span></>} testid="cmd-marker-info"
                onClick={() => st().setMarkerInfo(!markerInfo)} />
              <MenuSeparator />
              <MenuItem icon="fit" label="Fit" hint="F" testid="cmd-fit" onClick={() => st().fit()} />
              {/* Zoom to selection, Actual size, Zoom 100 %, Calibrate… (the canvas's right-click menu has them too) */}
              <ZoomItems prefix="cmd" fit={false} />
            </Sub>
            <Sub label="Preferences" testid="menu-prefs" inline={inline}>
              <div className="mm-h">{theme === "dark" ? <Moon size={12} /> : <Sun size={12} />}Theme</div>
              {(["light", "dark"] as const).map((t) => (
                <Pick key={t} on={theme === t} label={t === "light" ? "Light" : "Dark"} testid={`theme-${t}`} disabled={!!skin.theme} title={pinned} onClick={() => setTheme(t)} />
              ))}
              <MenuSeparator />
              <div className="mm-h"><Glyph name="skin" />Skin</div>
              {SKINS.map((k) => (
                <Pick key={k.id} on={k.id === skin.id} label={k.name} testid={`skin-${k.id}`} title={k.theme ? `${k.theme} only` : undefined} onClick={() => setSkin(k.id)} />
              ))}
            </Sub>
            <Sub label="Help and account" testid="menu-account" inline={inline}>
              <AccountItems onHelp={onHelp} />
            </Sub>
          </M.Popup>
        </M.Positioner>
      </M.Portal>
    </M.Root>
  );
}

/** A row of the ⌄ menu: a plain button that runs and closes the menu. */
function Item({ icon, label, hint, onClick, testid, disabled, close }: {
  icon?: string; label: ReactNode; hint?: string; onClick: () => void; testid: string; disabled?: boolean; close: () => void;
}) {
  return (
    <button type="button" className="dm-item" data-testid={testid} disabled={disabled} onClick={() => { close(); onClick(); }}>
      {icon ? <Glyph name={icon} /> : <span className="ic" />}<span className="dm-label">{label}</span>{hint && <span className="dm-hint">{hint}</span>}
    </button>
  );
}

/** ⌄'s items (the registry title bar's menu): the save status on top
 *  ("Saved · 1 min ago", Figma shows it under the name), then what is about
 *  THIS file: Rename, Duplicate, Version history, Move to trash. Signed out,
 *  the status and Rename: the rest needs an account. */
function ThisFileItems({ close, onRename }: { close: () => void; onRename: () => void }) {
  const { state } = useHostedFiles();
  const status = useStatus();
  const actions = useHostedFilesActions();
  const file = state.file;
  const label = status.label.startsWith("Saved ") ? `Saved · ${status.label.slice("Saved ".length)}` : status.label;
  return (
    <>
      <div className={cn("dm-head shf-menu-status", `k-${status.kind}`)} data-testid="shf-menu-status" title={status.detail}>{label}</div>
      <Item close={close} label="Rename" testid="shf-action-rename" onClick={onRename} />
      {state.user && (
        <>
          <Item close={close} label="Duplicate" testid="shf-action-duplicate" disabled={!file} onClick={() => { if (file) void actions.duplicate(file); }} />
          <Item close={close} label="Version history" testid="shf-action-history" disabled={!file} onClick={() => actions.showHistory()} />
          <div className="dm-sep" />
          <Item close={close} label="Move to trash" testid="shf-action-trash" disabled={!file} onClick={() => { if (file) void actions.trash(file); }} />
        </>
      )}
    </>
  );
}

/** The name: the control (click, or ⌄ › Rename, to rename in place). One
 *  name: the document's is its cloud file's (hosted/hosted.ts oneName). */
function DocTitle({ editing, setEditing }: { editing: boolean; setEditing: (on: boolean) => void }) {
  const name = useStudio((s) => s.doc.name);
  if (editing) return <NameInput name={name} done={() => setEditing(false)} />;
  return (
    <button type="button" className="doc-name" data-testid="shf-filename" title="Rename" onClick={() => setEditing(true)}>
      <span className="doc-text" data-testid="doc-name">{name}</span>
    </button>
  );
}

function NameInput({ name, done }: { name: string; done: () => void }) {
  const [value, setValue] = useState(name);
  const input = useRef<HTMLInputElement>(null);
  const finished = useRef(false);
  useEffect(() => { input.current?.select(); }, []);
  const finish = (save: boolean) => {
    if (finished.current) return;
    finished.current = true;
    done();
    if (save) renameDocument(value);
  };
  return (
    <input ref={input} autoFocus className="kit-text doc-name-input" data-testid="doc-name-input" aria-label="Document name" maxLength={200}
      value={value} onChange={(e) => setValue(e.target.value)} onBlur={() => finish(true)}
      onKeyDown={(e) => { if (e.key === "Enter") finish(true); else if (e.key === "Escape") finish(false); }} />
  );
}

/** The save status, quiet: a dot (saved, saving, on this device, …) whose
 *  words are its tooltip; it opens History. Nothing while signed out. */
function StatusDot() {
  const { hostedFiles, state } = useHostedFiles();
  const status = useStatus();
  const actions = useHostedFilesActions();
  if (!state.user) return null;
  const stale = !!hostedFiles.staleHead && !!state.message && state.status === "saved";
  return (
    <>
      <button type="button" className={cn("shf-dot", `k-${status.kind}`)} data-testid="shf-status" data-kind={status.kind}
        title={state.file ? `${status.detail} — Version history` : status.detail} disabled={!state.file} onClick={() => actions.showHistory()}>
        <i /><span className="shf-sr">{status.label}</span>
      </button>
      {stale && <Button size="sm" className="shf-reload" testid="shf-reload" icon={<RotateCcw size={11} />} onClick={() => void actions.reload()}>Updated elsewhere — Reload</Button>}
    </>
  );
}

/** ⌄ (Figma's file-name menu): this file only; on a phone also Download for
 *  CAD, which the top-right pill folds away. */
function DocMenu({ onRename }: { onRename: () => void }) {
  const narrow = useNarrow();
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);
  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger className="doc-name doc-chev" data-testid="menu-doc" title="This file: rename, duplicate, history, trash" aria-label="File menu">
        <svg viewBox="0 0 16 16" width="10" height="10" aria-hidden="true" className="chev"><path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.6" /></svg>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Positioner sideOffset={10} align="start" className="kit-menu-positioner">
          <Popover.Popup className="kit-menu-popup dm-popup" data-kit-popup="doc" data-testid="doc-menu">
            <ThisFileItems close={close} onRename={onRename} />
            {narrow && (
              <>
                <div className="dm-sep" />
                <div className="dm-h">Download for CAD</div>
                <Item close={close} icon="cube" label="Fusion 360" hint="coming soon" testid="cad-fusion" disabled onClick={() => {}} />
                <Item close={close} icon="cube" label="Onshape" hint="coming soon" testid="cad-onshape" disabled onClick={() => {}} />
              </>
            )}
          </Popover.Popup>
        </Popover.Positioner>
      </Popover.Portal>
    </Popover.Root>
  );
}

/** The top-left pill: the main menu (the logo with ⌄), the title bar (the
 *  name, the status dot, ⌄). */
export function DocPill({ onHelp }: { onHelp: () => void }) {
  const [editing, setEditing] = useState(false);
  return (
    <div className="pill doc-pill" data-testid="doc-pill">
      <MainMenu onHelp={onHelp} />
      <span className="pill-sep" />
      <span className="doc-title">
        <DocTitle editing={editing} setEditing={setEditing} />
        <StatusDot />
        <DocMenu onRename={() => setEditing(true)} />
      </span>
    </div>
  );
}

/** The top-right pill: Download for CAD, then Verify | Print. */
export function ActionsPill() {
  return (
    <div className="pill actions-pill" data-testid="actions-pill">
      <span className="act-cad"><CadMenu /></span>
      <span className="pill-sep act-cad" />
      <Button icon="verify" className="act-btn" testid="act-verify" title="Verify: a simulated camera reads the marker (K)" onClick={openVerify}>
        <span className="act-text">Verify</span>
      </Button>
      <Button icon="print" variant="primary" className="act-btn" testid="act-print" title="Print the stickers (S)" onClick={openPrint}>
        <span className="act-text">Print</span>
      </Button>
    </div>
  );
}

/** The keys App.tsx binds. */
const KEYS: [string, string][] = [
  ["V", "Select"], ["R", "Rectangle"], ["C", "Circle"], ["D", "Dimension"], ["A", "ArUco Extrude"], ["F", "Fit"], ["3", "2D | 3D"],
  ["Shift+1", "Zoom to fit"], ["Shift+2", "Zoom to selection"], ["Shift+0", "Actual size"],
  ["S", "Print (P too)"], ["K", "Verify"],
  ["Ctrl+Z", "Undo"], ["Ctrl+Shift+Z", "Redo (Ctrl+Y too)"], ["Ctrl+C", "Copy"], ["Ctrl+X", "Cut"], ["Ctrl+V", "Paste at the pointer"],
  ["Ctrl+D", "Duplicate"], ["Right-click", "The menu (a right-drag selects)"],
  ["← ↑ → ↓", "Nudge 1 mm (Shift: 10 mm)"], ["Del", "Delete"], ["Esc", "Back to Select; close the panel"],
];

/** How the start went: the seconds while starting, the time it took, or
 *  "Couldn't start" with Reload and the reason behind Details. */
function CoreLine() {
  const s = useCoreStatus();
  useTick(s.state === "loading", 1000);
  if (s.state === "error") {
    return <div className="help-status" data-testid="core-status" data-state="error">
      <WaitLine wait={{ kind: "core-error", short: "Couldn't start", text: "Couldn't start", detail: failedDetail(s.detail), action: { label: "Reload", run: reload } }} testid="core-status-wait" />
    </div>;
  }
  const text = s.state === "ready" ? `Ready in ${((s.ms ?? 0) / 1000).toFixed(1)} s` : startingText();
  return <div className={`help-status st-${s.state}`} data-testid="core-status" data-state={s.state}><i className="dot" />{text}</div>;
}

function HelpBody() {
  return (
    <div className="help-body" data-testid="help-body">
      <div className="help-title">Keyboard shortcuts</div>
      <dl className="help-keys">
        {KEYS.map(([k, what]) => (
          <div key={k} className="help-key" data-key={k}><dt><Kbd keys={k} /></dt><dd>{what}</dd></div>
        ))}
      </dl>
      <CoreLine />
    </div>
  );
}

/** The bottom corner: ? (the keys and the status) and GitHub; on a phone they
 *  are in the ⌄ menu, and `help` opens the same list as a dialog. */
export function HelpCorner({ help, setHelp }: { help: boolean; setHelp: (on: boolean) => void }) {
  const narrow = useNarrow();
  return (
    <>
      <div className="corner" data-testid="corner">
        <Popover.Root open={help && !narrow} onOpenChange={setHelp}>
          <Popover.Trigger className="corner-btn" data-testid="help" title="Keyboard shortcuts" aria-label="Keyboard shortcuts"><CircleHelp size={18} /></Popover.Trigger>
          <Popover.Portal>
            <Popover.Positioner side="top" align="end" sideOffset={8} className="kit-menu-positioner">
              <Popover.Popup className="kit-menu-popup help-popup" data-kit-popup="help" data-testid="help-popover"><HelpBody /></Popover.Popup>
            </Popover.Positioner>
          </Popover.Portal>
        </Popover.Root>
        <a className="corner-btn" href={GITHUB} target="_blank" rel="noreferrer" title="Source on GitHub" aria-label="GitHub" data-testid="github"><GithubMark /></a>
      </div>
      <Dialog open={help && narrow} onClose={() => setHelp(false)} title="Keyboard shortcuts" testid="help-dialog" width={360}><HelpBody /></Dialog>
    </>
  );
}
