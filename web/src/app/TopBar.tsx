// The top bar: the name, File and Export, the Download for CAD menu, the
// preset chip (opens the presets modal), the core chip, the theme, the
// GitHub link.
import { Glyph, Menu, MenuItem, MenuSeparator, useTheme } from "@bam/ui";
import { LoaderCircle, Moon, Sun } from "lucide-react";
import { coreKind, useCoreStatus } from "../coreSource";
import { useStudio } from "../store";
import { exportPdf, exportSvg, openDoc, openPrint, saveDoc } from "./commands";

const GITHUB = "https://github.com/zacharyyamaoka/aruco-studio";

function GithubMark() {
  return (
    <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">
      <path fill="currentColor" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}

// The brand mark: the Extrude Cube, an extruded block with a marker-like
// bitmap on top, drawn with no tile (the same paths as public/icon.svg).
// WHY: Zach's round-3 pick on 2026-10-18 (reports/media/logo-cube-variants-
// 2026-10-18.html). The top bitmap is checked not to decode as any OpenCV
// dictionary, and the white halo keeps it readable on the dark theme; do not
// swap in a real marker or drop the halo.
function BrandCube() {
  return (
    <svg className="brand-cube" viewBox="0 0 64 64" width="18" height="18" aria-hidden="true">
      <path fill="#ffffff" stroke="#ffffff" strokeWidth="2.4" strokeLinejoin="round" d="M5.6 41.2L32 62L32 43.61L5.6 22.8z" />
      <path fill="#ffffff" stroke="#ffffff" strokeWidth="2.4" strokeLinejoin="round" d="M58.4 41.2L32 62L32 43.61L58.4 22.8z" />
      <path fill="#ffffff" stroke="#ffffff" strokeWidth="2.4" strokeLinejoin="round" d="M32 2L58.4 22.8L32 43.61L5.6 22.8z" />
      <path fill="#3a4250" d="M5.6 41.2L32 62L32 43.61L5.6 22.8z" />
      <path fill="#69727f" d="M58.4 41.2L32 62L32 43.61L58.4 22.8z" />
      <path fill="#ffffff" d="M32 2L58.4 22.8L32 43.61L5.6 22.8z" />
      <path fill="#ffffff" d="M32 2L58.4 22.8L32 43.61L5.6 22.8z" />
      <path fill="#111418" d="M32 6.16L53.12 22.8L49.5 25.66L28.37 9.02zM28.59 8.85L32.21 11.71L28.48 14.65L24.85 11.79zM35.52 14.32L39.25 17.26L35.52 20.2L31.79 17.26zM46.08 22.64L49.71 25.5L45.98 28.44L42.35 25.58zM25.07 11.63L32.21 17.26L28.48 20.2L21.33 14.57zM35.52 19.86L39.25 22.8L35.52 25.75L31.79 22.8zM42.56 25.41L46.19 28.27L42.46 31.21L38.83 28.35zM21.54 14.4L25.17 17.26L21.44 20.2L17.81 17.34zM28.48 19.86L35.73 25.58L32 28.52L24.75 22.8zM39.04 28.19L42.67 31.04L38.93 33.98L35.31 31.13zM18.02 17.17L21.65 20.03L17.92 22.97L14.29 20.11zM24.96 22.64L28.69 25.58L24.96 28.52L21.23 25.58zM35.52 30.96L39.15 33.82L35.41 36.76L31.79 33.9zM14.5 19.95L35.63 36.59L32 39.45L10.88 22.8z" />
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

export function TopBar() {
  const preset = useStudio((s) => s.doc.preset);
  const name = useStudio((s) => s.doc.name);
  const [theme, setTheme] = useTheme();
  const st = useStudio.getState;
  return (
    <header className="topbar" data-testid="topbar">
      <span className="brand"><BrandCube /><b>ArUco Studio</b></span>
      <Menu label="File" testid="menu-file">
        <MenuItem icon="sketch" label="New" testid="cmd-new" onClick={() => st().newDoc()} />
        <MenuItem icon="library" label="Examples…" testid="cmd-examples" onClick={() => st().openModal("examples")} />
        <MenuItem label="Open…" testid="cmd-open" onClick={() => void openDoc()} />
        <MenuSeparator />
        <MenuItem label="Save" hint=".arucostudio-web.json" testid="cmd-save" onClick={saveDoc} />
      </Menu>
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
      <button type="button" className="kit-ib" data-testid="theme-toggle" title={theme === "dark" ? "Light theme" : "Dark theme"}
        aria-label="Toggle theme" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
        {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
      </button>
      <a className="kit-ib" href={GITHUB} target="_blank" rel="noreferrer" title="Source on GitHub" aria-label="GitHub" data-testid="github"><GithubMark /></a>
    </header>
  );
}
