// The chrome around the canvas, Figma's (V2 "Figma · Corner pills" in
// reports/media/studio-layout-proposals-2026-10-20.html, picked by Zach on
// 2026-10-20 night: "For the design let's please follow Figma!"): two corner
// pills over the canvas and, in the bottom corner, ? and GitHub.
// - Top left, the document pill: the logo (the landing page), File, Edit,
//   Export, and the document's name with ⌄ (Theme and Skin; on a phone also
//   File, Edit, Export, Download for CAD, GitHub and the keys).
// - Top right: Download for CAD, then Verify | Print (K, S: in the tooltips,
//   no key badges).
// - Bottom right: ? (the keys, and how the start went) and GitHub.
// WHY no preset in the pill (Zach): "Preset shouldn't be on the file because
// it's applied on a per marker basis!" -- it is the panel's Make tab's, and
// Edit › Presets… sets the one a new marker starts with.
// WHY no core chip (Zach): "for me that's back end details ... maybe just in a
// panel etc. you can show that status thing ... but it shouldn't clutter the
// main viewer" -- what waits says it (panel/Waiting.tsx); ? shows the status.
// WHY no key badges on the corner buttons and GitHub at the bottom (Zach):
// "No need for hot keys on those corner buttons. GitHub maybe better in the
// bottom corner."
import { useEffect, useState, type ReactNode } from "react";
import { Popover } from "@base-ui/react/popover";
import { Button, Dialog, Glyph, Kbd, Menu, MenuItem, MenuSeparator, cn, useTheme } from "@bam/ui";
import { CircleHelp, Moon, Sun } from "lucide-react";
import { useCoreStatus } from "../coreSource";
import { WaitLine, failedDetail, reload, startingText, useTick } from "../panel/Waiting";
import { useStudio } from "../store";
import { SKINS, useSkin } from "../skins/skins";
import { exportPdf, exportSvg, openDoc, openPrint, openVerify, saveDoc } from "./commands";

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
function BrandCube() {
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

function FileMenu() {
  const st = useStudio.getState;
  return (
    <Menu label="File" testid="menu-file">
      <MenuItem icon="sketch" label="New" testid="cmd-new" onClick={() => st().newDoc()} />
      <MenuItem icon="library" label="Examples…" testid="cmd-examples" onClick={() => st().openModal("examples")} />
      <MenuItem label="Open…" testid="cmd-open" onClick={() => void openDoc()} />
      <MenuSeparator />
      <MenuItem label="Save" hint=".arucostudio-web.json" testid="cmd-save" onClick={saveDoc} />
    </Menu>
  );
}

/** Edit: the document's history (store.undo / redo, the keys App.tsx binds),
 *  ArUco Re-ID… (ReIdDialog.tsx) and Presets… (the open marker's preset, or
 *  the one a new marker starts with). */
function EditMenu() {
  const canUndo = useStudio((s) => s.canUndo);
  const canRedo = useStudio((s) => s.canRedo);
  const markers = useStudio((s) => s.doc.features.length);
  const st = useStudio.getState;
  return (
    <Menu label="Edit" testid="menu-edit">
      <MenuItem label="Undo" hint="Ctrl+Z" testid="cmd-undo" disabled={!canUndo} onClick={() => st().undo()} />
      <MenuItem label="Redo" hint="Ctrl+Shift+Z" testid="cmd-redo" disabled={!canRedo} onClick={() => st().redo()} />
      <MenuSeparator />
      <MenuItem icon="marker" label="ArUco Re-ID…" testid="cmd-reid" disabled={!markers}
        title={markers ? undefined : "No markers yet: make an ArUco Extrude (A) first"} onClick={() => st().openModal("reid")} />
      <MenuItem icon="inkjet" label="Presets…" testid="cmd-presets" title="How a marker is made: the open marker's preset, or the one a new marker starts with"
        onClick={() => st().openModal("presets")} />
    </Menu>
  );
}

function ExportMenu() {
  return (
    <Menu label="Export" testid="menu-export">
      <MenuItem icon="print" label="Print…" hint="S" testid="cmd-print" onClick={openPrint} />
      <MenuItem label="SVG" hint="the marker, true size" testid="cmd-svg" onClick={() => void exportSvg()} />
      <MenuItem label="PDF" hint="the marker's preset's page" testid="cmd-pdf" onClick={() => void exportPdf()} />
    </Menu>
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

/** Theme (Light | Dark) and Skin, V2's Preferences: a one-theme skin (Fusion
 *  dark, Onshape light) greys the theme out. */
function Preferences() {
  const [theme, setTheme] = useTheme();
  const [skin, setSkin] = useSkin();
  const pinned = skin.theme ? `${skin.name} is ${skin.theme} only` : undefined;
  return (
    <div className="dm-prefs" data-testid="prefs">
      <div className="dm-row">
        <span className="dm-row-label">{theme === "dark" ? <Moon size={14} /> : <Sun size={14} />}Theme</span>
        <span className="dm-sws" role="group" aria-label="Theme">
          {(["light", "dark"] as const).map((t) => (
            <button key={t} type="button" className={cn("dm-sw", theme === t && "on")} aria-pressed={theme === t} disabled={!!skin.theme}
              data-testid={`theme-${t}`} title={pinned} onClick={() => setTheme(t)}>
              {t === "light" ? <Sun size={13} /> : <Moon size={13} />}{t === "light" ? "Light" : "Dark"}
            </button>
          ))}
        </span>
      </div>
      <div className="dm-row">
        <span className="dm-row-label"><Glyph name="skin" />Skin</span>
        <span className="dm-sws" role="group" aria-label="Skin">
          {SKINS.map((s) => (
            <button key={s.id} type="button" className={cn("dm-sw", s.id === skin.id && "on")} aria-pressed={s.id === skin.id}
              data-testid={`skin-${s.id}`} title={s.theme ? `${s.theme} only` : undefined} onClick={() => setSkin(s.id)}>{s.name}</button>
          ))}
        </span>
      </div>
    </div>
  );
}

/** The document's name with ⌄ (Figma's file-name menu): Theme and Skin; on a
 *  phone also what the pills fold away. */
function DocMenu({ onHelp }: { onHelp: () => void }) {
  const name = useStudio((s) => s.doc.name);
  const canUndo = useStudio((s) => s.canUndo);
  const canRedo = useStudio((s) => s.canRedo);
  const markers = useStudio((s) => s.doc.features.length);
  const narrow = useNarrow();
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);
  const st = useStudio.getState;
  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger className="doc-name" data-testid="menu-doc" title="The document: Theme and Skin">
        <span className="doc-text" data-testid="doc-name">{name}</span>
        <svg viewBox="0 0 16 16" width="10" height="10" aria-hidden="true" className="chev"><path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.6" /></svg>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Positioner sideOffset={10} align="start" className="kit-menu-positioner">
          <Popover.Popup className="kit-menu-popup dm-popup" data-kit-popup="doc" data-testid="doc-menu">
            <div className="dm-head"><b>{name}</b></div>
            {narrow && (
              <>
                <div className="dm-h">File</div>
                <Item close={close} icon="sketch" label="New" testid="cmd-new" onClick={() => st().newDoc()} />
                <Item close={close} icon="library" label="Examples…" testid="cmd-examples" onClick={() => st().openModal("examples")} />
                <Item close={close} label="Open…" testid="cmd-open" onClick={() => void openDoc()} />
                <Item close={close} label="Save" hint=".arucostudio-web.json" testid="cmd-save" onClick={saveDoc} />
                <div className="dm-h">Edit</div>
                <Item close={close} label="Undo" testid="cmd-undo" disabled={!canUndo} onClick={() => st().undo()} />
                <Item close={close} label="Redo" testid="cmd-redo" disabled={!canRedo} onClick={() => st().redo()} />
                <Item close={close} icon="marker" label="ArUco Re-ID…" testid="cmd-reid" disabled={!markers} onClick={() => st().openModal("reid")} />
                <Item close={close} icon="inkjet" label="Presets…" testid="cmd-presets" onClick={() => st().openModal("presets")} />
                <div className="dm-h">Export</div>
                <Item close={close} icon="print" label="Print…" testid="cmd-print" onClick={openPrint} />
                <Item close={close} label="SVG" hint="the marker, true size" testid="cmd-svg" onClick={() => void exportSvg()} />
                <Item close={close} label="PDF" hint="the marker's preset's page" testid="cmd-pdf" onClick={() => void exportPdf()} />
                <div className="dm-h">Download for CAD</div>
                <Item close={close} icon="cube" label="Fusion 360" hint="coming soon" testid="cad-fusion" disabled onClick={() => {}} />
                <Item close={close} icon="cube" label="Onshape" hint="coming soon" testid="cad-onshape" disabled onClick={() => {}} />
                <div className="dm-sep" />
                <a className="dm-item" href={GITHUB} target="_blank" rel="noreferrer" data-testid="github-menu" onClick={close}>
                  <span className="ic dm-gh"><GithubMark /></span><span className="dm-label">GitHub</span>
                </a>
                <Item close={close} label="Keyboard shortcuts and status" testid="help-menu" onClick={onHelp} />
                <div className="dm-sep" />
              </>
            )}
            <Preferences />
          </Popover.Popup>
        </Popover.Positioner>
      </Popover.Portal>
    </Popover.Root>
  );
}

/** The top-left pill: the logo, File, Edit, Export, the document ⌄. */
export function DocPill({ onHelp }: { onHelp: () => void }) {
  return (
    <div className="pill doc-pill" data-testid="doc-pill">
      {/* the brand goes to the landing page (Zach, 2026-10-20); a real navigation, not a route */}
      <a className="brand" href="/about/" title="About ArUco Studio" aria-label="About ArUco Studio" data-testid="brand"><BrandCube /></a>
      <span className="pill-menus">
        <FileMenu />
        <EditMenu />
        <ExportMenu />
      </span>
      <span className="pill-sep" />
      <DocMenu onHelp={onHelp} />
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
  ["S", "Print (P too)"], ["K", "Verify"],
  ["Ctrl+Z", "Undo"], ["Ctrl+Shift+Z", "Redo (Ctrl+Y too)"], ["Ctrl+C", "Copy"], ["Ctrl+X", "Cut"], ["Ctrl+V", "Paste at the pointer"],
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
