// The online Studio's screen (docs/design/online_studio_v1.md, "The screen"):
// the sketch viewport over the whole window, Figma's chrome floating on it
// (V2, Zach's pick 2026-10-20 night; ./app/TopBar.tsx): the document pill top
// left (the main menu behind the logo, the file's name), Download for CAD and
// Verify | Print top right, the dock of tools with 2D | 3D bottom centre, ?
// and GitHub bottom right; the floating ArUco Extrude panel; the presets
// modal, Print, Verify, Examples and Re-ID; Home ("Back to files") over it all;
// the zoom in the bottom-right pill with ? (Miro's, 2026-10-21) and the
// canvas's right-click menu, Actual size among their zooms (./zoom/: the
// screen's millimetre, calibrated per screen); the dock's Layers menu
// (./overlays/: what the canvas shows, Dots | Grid | Blank behind it).
// WHY no timeline (Zach, 2026-10-18): "too specific to CAD … just clicking the
// marker on the screen is what brings up the relevant inspector window".
import { useEffect, useState } from "react";
import { TooltipProvider } from "@bam/ui";
import { ExamplesDialog } from "./app/ExamplesDialog";
import { openPrint, openVerify } from "./app/commands";
import { ReIdDialog } from "./app/ReIdDialog";
import { Toolbar } from "./app/Toolbar";
import { ActionsPill, BrandCube, DocPill, HelpCorner } from "./app/TopBar";
import { isHome } from "./app/home";
import { HostedDialogs, HostedProvider, HostedToast } from "./hosted/ui/HostedDialogs";
import { HostedHome } from "./hosted/ui/HostedHome";
import { onCoreStatus, coreStatus } from "./coreSource";
import { ExtrudePanel } from "./panel/ExtrudePanel";
import { startPlanner } from "./planner";
import { PresetsModal } from "./presets/PresetsModal";
import { PrintDialog } from "./print/PrintDialog";
import { VerifyDialog } from "./verify/VerifyDialog";
import { pointer } from "./sketch/pointer";
import { Viewport } from "./sketch/Viewport";
import { View3D } from "./view3d/View3D";
import { loadCoreFacts, useStudio } from "./store";
import { CalibrateDialog } from "./zoom/CalibrateDialog";
import { watchScreen } from "./zoom/scale";
import { actualSize, followScale, zoomToSelection } from "./zoom/zoom";

/** A key the tool should not take: typing in a field, a list / menu / dialog
 *  open, or Home in front. */
function keyIsElsewhere(e: KeyboardEvent): boolean {
  if (isHome()) return true;
  const t = e.target as HTMLElement | null;
  if (t?.closest?.("input,textarea,select,[contenteditable=true]")) return true;
  if (document.querySelector("[data-kit-popup][data-open]")) return true;
  return useStudio.getState().modal !== null;
}

/** Ctrl+Z / Cmd+Z undoes; Ctrl+Shift+Z, Ctrl+Y and Cmd+Shift+Z redo. In a
 *  field they are the field's own. */
function onUndoKey(e: KeyboardEvent): boolean {
  if (!(e.ctrlKey || e.metaKey) || e.altKey) return false;
  const k = e.key.toLowerCase();
  const redo = (k === "z" && e.shiftKey) || (k === "y" && e.ctrlKey && !e.shiftKey);
  if (!redo && !(k === "z" && !e.shiftKey)) return false;
  if (keyIsElsewhere(e)) return true;
  e.preventDefault();
  if (redo) useStudio.getState().redo();
  else useStudio.getState().undo();
  return true;
}

/** Ctrl+C / Ctrl+X / Ctrl+V (Cmd on a Mac): the selected shapes, the features
 *  on them and their dims; a paste lands at the pointer. Ctrl+D duplicates
 *  them beside themselves (Figma's). In a field they are the field's own. */
function onClipKey(e: KeyboardEvent): boolean {
  if (!(e.ctrlKey || e.metaKey) || e.altKey || e.shiftKey) return false;
  const k = e.key.toLowerCase();
  if (k !== "c" && k !== "x" && k !== "v" && k !== "d") return false;
  if (keyIsElsewhere(e) || window.getSelection()?.toString()) return true;
  e.preventDefault();
  const st = useStudio.getState();
  if (k === "c") st.copy();
  else if (k === "x") st.cut();
  else if (k === "d") st.duplicate();
  else st.paste(pointer.at);
  return true;
}

/** The arrows nudge the selected shapes 1 mm (Shift: 10 mm), one undo step each. */
const NUDGE: Record<string, [number, number]> = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, 1], ArrowDown: [0, -1] };

function onKey(e: KeyboardEvent) {
  if (onUndoKey(e)) return;
  if (onClipKey(e)) return;
  if (e.ctrlKey || e.metaKey || e.altKey || keyIsElsewhere(e)) return;
  const st = useStudio.getState();
  // Figma's zoom keys, by the key's place (Shift+1 types "!" on a US layout):
  // Shift+1 fits (F too), Shift+2 the selection, Shift+0 Actual size (Figma's
  // 100 %; here the screen's real millimetre, ./zoom/scale.ts)
  if (e.shiftKey && (e.code === "Digit1" || e.code === "Digit2" || e.code === "Digit0")) {
    if (e.code === "Digit1") st.fit();
    else if (!st.view3d) { if (e.code === "Digit2") zoomToSelection(); else actualSize(); }
    e.preventDefault();
    return;
  }
  const k = e.key.length === 1 ? e.key.toLowerCase() : e.key;
  // a sketch tool in 3D goes back to the sketch first (as entering a sketch does in Fusion)
  if (st.view3d && (k === "r" || k === "c" || k === "d")) st.setView3d(false);
  if (k === "v") st.setTool("select");
  else if (k === "r") st.setTool("rect");
  else if (k === "c") st.setTool("circle");
  else if (k === "d") st.setTool("dim");
  else if (NUDGE[k]) { const [x, y] = NUDGE[k], n = e.shiftKey ? 10 : 1; st.nudge(x * n, y * n); }
  else if (k === "a") void st.extrude();
  else if (k === "f") st.fit();
  else if (k === "s" || k === "p") openPrint();   // Sheet (P kept: the print key everyone tries)
  else if (k === "k") openVerify();
  else if (k === "3") st.setView3d(!st.view3d);   // the 2D | 3D toggle
  else if (k === "Escape") {
    if (st.tool !== "select") st.setTool("select");
    else if (st.panel.selector) st.setSelector(null);
    else if (st.panel.open) st.cancel();
    else st.select(null);
  } else if (k === "Delete" || k === "Backspace") st.deleteSelection();
  else return;
  e.preventDefault();
}

export function App() {
  const note = useStudio((s) => s.note);
  const view3d = useStudio((s) => s.view3d);
  const [help, setHelp] = useState(false);
  useEffect(() => {
    const stop = startPlanner();
    window.addEventListener("keydown", onKey);
    // the dictionaries and presets each time the core becomes ready without
    // them (the sketch works before); loadCoreFacts retries, then holds its
    // error in the store for the panel's Retry
    let was: string | null = null;
    const ask = () => {
      const now = coreStatus().state;
      const rose = now === "ready" && was !== "ready";
      was = now;
      if (rose && useStudio.getState().facts.state !== "ok") void loadCoreFacts();
    };
    const un = onCoreStatus(ask);
    ask();
    // Actual size: this screen's scale, kept up as the window moves between monitors
    const unScreen = watchScreen();
    const unFollow = followScale();
    return () => { stop(); un(); unScreen(); unFollow(); window.removeEventListener("keydown", onKey); };
  }, []);
  useEffect(() => {
    if (!note) return;
    const t = setTimeout(() => useStudio.getState().say(null), 4000);
    return () => clearTimeout(t);
  }, [note]);

  return (
    <TooltipProvider>
      {/* Simple Hosted Files: the title bar in the document pill, its dialogs below */}
      <HostedProvider icon={<BrandCube />}>
        <div className="app" data-testid="app">
          <main className="stage">
            {/* WHY hidden, not unmounted: back in 2D the sketch keeps its camera */}
            <div className="vp-2d" style={{ display: view3d ? "none" : "contents" }}><Viewport /></div>
            {view3d && <View3D />}
            <DocPill onHelp={() => setHelp(true)} />
            <ActionsPill />
            <Toolbar />
            {/* ? and GitHub, and the zoom pill (Miro's: in one pill with ?) */}
            <HelpCorner help={help} setHelp={setHelp} />
            <ExtrudePanel />
            {note && <div className="toast" role="status" data-testid="note">{note}</div>}
            <HostedToast />
          </main>
        </div>
        <HostedHome />
        <HostedDialogs icon={<BrandCube />} />
        <PresetsModal />
        <PrintDialog />
        <VerifyDialog />
        <ExamplesDialog />
        <ReIdDialog />
        <CalibrateDialog />
      </HostedProvider>
    </TooltipProvider>
  );
}
