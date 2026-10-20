// The top bar: the name, File, Edit and Export, the Download for CAD menu, the
// preset chip (opens the presets modal), the core chip, the skin, the theme,
// the GitHub link.
import { Glyph, Menu, MenuItem, MenuSeparator, useTheme } from "@bam/ui";
import { LoaderCircle, Moon, Sun } from "lucide-react";
import { coreKind, useCoreStatus } from "../coreSource";
import { useStudio } from "../store";
import { SKINS, useSkin } from "../skins/skins";
import { exportPdf, exportSvg, openDoc, openPrint, saveDoc } from "./commands";

const GITHUB = "https://github.com/zacharyyamaoka/aruco-studio";

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
    <svg className="brand-cube" viewBox="0 0 64 64" width="18" height="18" aria-hidden="true">
      <path fill="#f1f3f6" stroke="#111418" strokeWidth="2.6" strokeLinejoin="round" d="M2 40.31L32 57.63L32 41.01L2 23.69z" />
      <path fill="#dfe3e8" stroke="#111418" strokeWidth="2.6" strokeLinejoin="round" d="M62 40.31L32 57.63L32 41.01L62 23.69z" />
      <path fill="#ffffff" stroke="#111418" strokeWidth="2.6" strokeLinejoin="round" d="M32 6.37L62 23.69L32 41.01L2 23.69z" />
      <path fill="#111418" d="M32 10.87L54.2 23.69L50.39 25.89L28.19 13.07zM28.41 12.94L32.22 15.14L28.3 17.41L24.49 15.21zM35.7 17.15L39.62 19.41L35.7 21.68L31.78 19.41zM46.8 23.56L50.61 25.76L46.69 28.02L42.88 25.82zM24.71 15.08L32.22 19.41L28.3 21.68L20.79 17.34zM35.7 21.42L39.62 23.69L35.7 25.95L31.78 23.69zM43.1 25.69L46.91 27.89L42.99 30.16L39.18 27.96zM21.01 17.21L24.82 19.41L20.9 21.68L17.09 19.48zM28.3 21.42L35.92 25.82L32 28.09L24.38 23.69zM39.4 27.83L43.21 30.03L39.29 32.29L35.48 30.09zM17.31 19.35L21.12 21.55L17.2 23.81L13.39 21.61zM24.6 23.56L28.52 25.82L24.6 28.09L20.68 25.82zM35.7 29.97L39.51 32.17L35.59 34.43L31.78 32.23zM13.61 21.49L35.81 34.3L32 36.5L9.8 23.69z" />
    </svg>
  );
}

export function CoreChip() {
  const s = useCoreStatus();
  const text = s.state === "ready" ? (coreKind === "mock" ? "Mock core" : "Python ready") : s.state === "error" ? "Core failed" : "Core loading…";
  return (
    <span className={`chip-core st-${s.state}`} data-testid="core-chip" data-state={s.state} data-kind={coreKind}
      title={[s.detail, s.ms ? `${(s.ms / 1000).toFixed(1)} s` : null].filter(Boolean).join(" · ") || undefined}>
      {s.state === "loading" ? <LoaderCircle size={12} className="spin" /> : <i className="dot" />}
      <span className="chip-text">{text}</span>
    </span>
  );
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

/** The skin (../skins/skins.ts): how the Studio looks, CAD program by CAD
 *  program. Only tokens change, never the layout. */
function SkinMenu() {
  const [skin, setSkin] = useSkin();
  return (
    <Menu icon="skin" label="Skin" testid="menu-skin" align="end">
      {SKINS.map((s) => (
        <MenuItem key={s.id} testid={`skin-${s.id}`} onClick={() => setSkin(s.id)}
          hint={s.theme ? `${s.theme} only` : undefined}
          label={<>{s.name}{s.id === skin.id && <span className="skin-tick"> ✓</span>}</>} />
      ))}
    </Menu>
  );
}

/** Edit: the document's history (store.undo / redo, the keys App.tsx binds)
 *  and Re-ID all markers… (ReIdDialog.tsx). */
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
      <MenuItem icon="marker" label="Re-ID all markers…" testid="cmd-reid" disabled={!markers}
        title={markers ? undefined : "No markers yet: make an ArUco Extrude (A) first"} onClick={() => st().openModal("reid")} />
    </Menu>
  );
}

export function TopBar() {
  const preset = useStudio((s) => s.doc.preset);
  const name = useStudio((s) => s.doc.name);
  const [theme, setTheme] = useTheme();
  const [skin] = useSkin();
  const st = useStudio.getState;
  return (
    <header className="topbar" data-testid="topbar">
      {/* the brand goes to the landing page (Zach, 2026-10-20); a real navigation, not a route */}
      <a className="brand" href="/about/" title="About ArUco Studio" data-testid="brand"><BrandCube /><b>ArUco Studio</b></a>
      <Menu label="File" testid="menu-file">
        <MenuItem icon="sketch" label="New" testid="cmd-new" onClick={() => st().newDoc()} />
        <MenuItem icon="library" label="Examples…" testid="cmd-examples" onClick={() => st().openModal("examples")} />
        <MenuItem label="Open…" testid="cmd-open" onClick={() => void openDoc()} />
        <MenuSeparator />
        <MenuItem label="Save" hint=".arucostudio-web.json" testid="cmd-save" onClick={saveDoc} />
      </Menu>
      <EditMenu />
      <Menu label="Export" testid="menu-export">
        <MenuItem icon="print" label="Print…" hint="P" testid="cmd-print" onClick={openPrint} />
        <MenuItem label="SVG" hint="the marker, true size" testid="cmd-svg" onClick={() => void exportSvg()} />
        <MenuItem label="PDF" hint="the preset's page" testid="cmd-pdf" onClick={() => void exportPdf()} />
      </Menu>
      <span className="doc-name" title="The document">{name}</span>
      <span className="grow" />
      <CadMenu />
      <button type="button" className="chip-preset" data-testid="preset-chip" title="How it is made: the presets"
        onClick={() => st().openModal("presets")}>
        <Glyph name={preset?.method === "print3d" ? "print3d" : "inkjet"} />
        <span className="chip-text">{preset ? preset.name : "Preset…"}</span>
      </button>
      <CoreChip />
      <SkinMenu />
      {/* a one-theme skin (Fusion dark, Onshape light) greys the toggle out */}
      <button type="button" className="kit-ib" data-testid="theme-toggle" disabled={!!skin.theme}
        title={skin.theme ? `${skin.name} is ${skin.theme} only` : theme === "dark" ? "Light theme" : "Dark theme"}
        aria-label="Toggle theme" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
        {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
      </button>
      <a className="kit-ib" href={GITHUB} target="_blank" rel="noreferrer" title="Source on GitHub" aria-label="GitHub" data-testid="github"><GithubMark /></a>
    </header>
  );
}
