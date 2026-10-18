// The online Studio's screen (docs/design/online_studio_v1.md, "The screen"):
// the top bar, the sketch viewport with its toolbar (bottom centre), the
// floating ArUco Extrude panel; the presets modal, Print and Examples.
// WHY no timeline (Zach, 2026-10-18): "too specific to CAD … just clicking the
// marker on the screen is what brings up the relevant inspector window".
import { useEffect } from "react";
import { TooltipProvider } from "@bam/ui";
import { ExamplesDialog } from "./app/ExamplesDialog";
import { openPrint } from "./app/commands";
import { Toolbar } from "./app/Toolbar";
import { TopBar } from "./app/TopBar";
import { onCoreStatus, coreStatus } from "./coreSource";
import { ExtrudePanel } from "./panel/ExtrudePanel";
import { startPlanner } from "./planner";
import { PresetsModal } from "./presets/PresetsModal";
import { PrintDialog } from "./print/PrintDialog";
import { ShapeDims } from "./sketch/ShapeDims";
import { Viewport } from "./sketch/Viewport";
import { loadCoreFacts, useStudio } from "./store";

/** A key the tool should not take: typing in a field, or a list / menu / dialog open. */
function keyIsElsewhere(e: KeyboardEvent): boolean {
  const t = e.target as HTMLElement | null;
  if (t?.closest?.("input,textarea,select,[contenteditable=true]")) return true;
  if (document.querySelector("[data-kit-popup][data-open]")) return true;
  return useStudio.getState().modal !== null;
}

function onKey(e: KeyboardEvent) {
  if (e.ctrlKey || e.metaKey || e.altKey || keyIsElsewhere(e)) return;
  const st = useStudio.getState();
  const k = e.key.length === 1 ? e.key.toLowerCase() : e.key;
  if (k === "v") st.setTool("select");
  else if (k === "r") st.setTool("rect");
  else if (k === "c") st.setTool("circle");
  else if (k === "a") void st.extrude();
  else if (k === "f") st.fit();
  else if (k === "p") openPrint();
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
          <Viewport />
          <Toolbar />
          <ShapeDims />
          <ExtrudePanel />
          {note && <div className="toast" role="status" data-testid="note">{note}</div>}
        </main>
      </div>
      <PresetsModal />
      <PrintDialog />
      <ExamplesDialog />
    </TooltipProvider>
  );
}
