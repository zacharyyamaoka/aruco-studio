// The online Studio's screen (docs/design/online_studio_v1.md, "The screen"):
// the top bar, the sketch viewport with its toolbar (bottom centre), the
// floating ArUco Extrude panel; the presets modal, Print, Examples and Re-ID.
// WHY no timeline (Zach, 2026-10-18): "too specific to CAD … just clicking the
// marker on the screen is what brings up the relevant inspector window".
import { useEffect } from "react";
import { TooltipProvider } from "@bam/ui";
import { ExamplesDialog } from "./app/ExamplesDialog";
import { openPrint, openVerify } from "./app/commands";
import { ReIdDialog } from "./app/ReIdDialog";
import { Toolbar } from "./app/Toolbar";
import { TopBar } from "./app/TopBar";
import { onCoreStatus, coreStatus } from "./coreSource";
import { ExtrudePanel } from "./panel/ExtrudePanel";
import { startPlanner } from "./planner";
import { PresetsModal } from "./presets/PresetsModal";
import { PrintDialog } from "./print/PrintDialog";
import { VerifyDialog } from "./verify/VerifyDialog";
import { pointer } from "./sketch/pointer";
import { Viewport } from "./sketch/Viewport";
import { View3D } from "./view3d/View3D";
import { ViewToggle } from "./view3d/ViewToggle";
import { loadCoreFacts, useStudio } from "./store";

/** A key the tool should not take: typing in a field, or a list / menu / dialog open. */
function keyIsElsewhere(e: KeyboardEvent): boolean {
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
 *  on them and their dims; a paste lands at the pointer. In a field they are the field's own. */
function onClipKey(e: KeyboardEvent): boolean {
  if (!(e.ctrlKey || e.metaKey) || e.altKey || e.shiftKey) return false;
  const k = e.key.toLowerCase();
  if (k !== "c" && k !== "x" && k !== "v") return false;
  if (keyIsElsewhere(e) || window.getSelection()?.toString()) return true;
  e.preventDefault();
  const st = useStudio.getState();
  if (k === "c") st.copy();
  else if (k === "x") st.cut();
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
  useEffect(() => {
    const stop = startPlanner();
    window.addEventListener("keydown", onKey);
    // the dictionaries and presets once the core answers (the sketch works before)
    let asked = false;
    const ask = () => {
      if (asked || coreStatus().state !== "ready") return;
      asked = true;
      loadCoreFacts().catch((e) => useStudio.getState().say(`The core did not answer: ${(e as Error).message}`));
    };
    const un = onCoreStatus(ask);
    ask();
    return () => { stop(); un(); window.removeEventListener("keydown", onKey); };
  }, []);
  useEffect(() => {
    if (!note) return;
    const t = setTimeout(() => useStudio.getState().say(null), 4000);
    return () => clearTimeout(t);
  }, [note]);

  return (
    <TooltipProvider>
      <div className="app" data-testid="app">
        <TopBar />
        <main className="stage">
          {/* WHY hidden, not unmounted: back in 2D the sketch keeps its camera */}
          <div className="vp-2d" style={{ display: view3d ? "none" : "contents" }}><Viewport /></div>
          {view3d && <View3D />}
          <ViewToggle />
          <Toolbar />
          <ExtrudePanel />
          {note && <div className="toast" role="status" data-testid="note">{note}</div>}
        </main>
      </div>
      <PresetsModal />
      <PrintDialog />
      <VerifyDialog />
      <ExamplesDialog />
      <ReIdDialog />
    </TooltipProvider>
  );
}
