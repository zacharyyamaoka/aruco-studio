// The Studio: the top bar, IDs on the left, the canvas (2D or 3D) in the
// middle with the tools at its foot, the inspector on the right, the status
// bar and the drawer below. The keys are the commands of commands.ts.
// The landing page is the gallery (N-3): golden examples; a card opens a
// copy in the Studio with its note. The drawing tools' keys work only with
// the dev flag ?draw=1 (flags.ts).
import { useEffect } from "react";
import { ExampleNote, Gallery } from "../gallery/Gallery";
import { toolOn } from "./flags";
import { Canvas2D } from "../canvas/Canvas2D";
import { IdsTable } from "../ids/IdsTable";
import { Inspector } from "../inspector/Inspector";
import { Library } from "../library/Library";
import { TYPED_TOOLS, useStudio } from "../store";
import { Glyph as Icon } from "@bam/ui";
import { View3D } from "../view3d/View3D";
import { BottomBar } from "./BottomBar";
import { Dialogs } from "./Dialogs";
import { Drawer, StatusBar } from "./Drawer";
import { Palette } from "./Palette";
import { Toolbar } from "./Toolbar";

function typing(e: KeyboardEvent) {
  const t = e.target as HTMLElement | null;
  return !!t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable);
}

/** Is focus on the page itself or the canvas (not on a button, a field or
 *  a menu)? Tab toggles 2D / 3D only there; elsewhere it moves focus (audit F18). */
function onCanvas(e: KeyboardEvent) {
  const t = e.target as HTMLElement | null;
  return !t || t === document.body || t === document.documentElement || !!t.closest?.(".canvas2d, .canvas3d, .stage-wrap");
}

const TOOL_KEYS: Record<string, Parameters<ReturnType<typeof useStudio.getState>["setTool"]>[0]> = {
  v: "select", r: "rect", c: "circle", p: "polygon", o: "slot", h: "hole", e: "extrude", a: "aruco",
};

function useKeys() {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const st = useStudio.getState();
      if (st.page === "gallery") return;                     // the gallery is a page, not a canvas
      if (st.libraryOpen || st.dialog || st.palette || typing(e)) return;
      // an open list, menu or dialog takes its own keys (audit F3)
      if (document.querySelector("[data-kit-popup][data-open]")) return;
      // what a tool takes typed: 80 50, 18, 5
      if (!e.ctrlKey && !e.metaKey && !e.altKey && TYPED_TOOLS.includes(st.tool) && (/^[0-9.\- ,x]$/.test(e.key) || (e.key === "Backspace" && st.typed))) {
        e.preventDefault();
        st.typeKey(e.key);
        return;
      }
      if (e.defaultPrevented) return;                      // an open list's Escape (audit F3)
      const k = e.key.toLowerCase();
      const ctrl = e.ctrlKey || e.metaKey;
      const go = (fn: () => unknown) => { e.preventDefault(); fn(); };
      if (ctrl && k === "z" && !e.shiftKey) return go(() => st.undo());
      if (ctrl && ((k === "z" && e.shiftKey) || k === "y")) return go(() => st.redo());
      if (ctrl && k === "d") return go(() => st.duplicateSel());
      if (ctrl && k === "a") return go(() => st.selectAll());
      if (ctrl && k === "s") return go(() => st.say(st.design.path ? `saved as you typed: every change is in ${st.design.path}` : "in memory: Save as… gives it a file (then every change is saved as you go)"));
      if (ctrl && k === "o") return go(() => st.setDialog({ kind: "open" }));
      if (ctrl || e.altKey) return;
      if (k === "escape") return go(() => st.cancel());
      if (k === "enter") return go(() => st.confirm());
      if (k === "delete" || k === "backspace") return go(() => st.deleteSel());
      if (k === "tab") {
        if (e.shiftKey || !onCanvas(e)) return;
        return go(() => st.toggleView());
      }
      const step = e.shiftKey ? 5 : 0.5;
      if (k === "arrowleft") return go(() => st.nudge(-step, 0));
      if (k === "arrowright") return go(() => st.nudge(step, 0));
      if (k === "arrowup") return go(() => st.nudge(0, step));
      if (k === "arrowdown") return go(() => st.nudge(0, -step));
      if (e.key === "?") return go(() => st.setDrawer(st.drawer === "messages" ? null : "messages"));
      if (e.key === "]") return go(() => st.rotateSel(-90));
      if (e.key === "[") return go(() => st.rotateSel(90));
      if (k === "s" && !e.shiftKey) return go(() => st.setPalette(true));
      if (k === "f") return go(() => st.zoomToFit(st.sel.length ? st.sel : undefined));
      if (k === "h" && e.shiftKey && toolOn("rhole")) return go(() => st.setTool("rhole"));
      if (TOOL_KEYS[k] && !e.shiftKey && toolOn(TOOL_KEYS[k])) return go(() => st.setTool(TOOL_KEYS[k]));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}

let started = false;

export function App() {
  const ready = useStudio((s) => s.ready);
  const view = useStudio((s) => s.view);
  const status = useStudio((s) => s.status);
  const page = useStudio((s) => s.page);
  useKeys();
  useEffect(() => {
    if (started) return;
    started = true;
    useStudio.getState().init().catch((e) => useStudio.getState().say(`The Studio's server did not answer on /api (${e}). Start it: .venv/Scripts/python -m aruco_studio.server`, "error"));
  }, []);
  const st = useStudio.getState();
  return (
    <div className="app" data-ready={ready ? "1" : "0"} data-view={view} data-page={page}>
      <Toolbar />
      {page === "gallery" ? <Gallery /> : <div className="body">
        <IdsTable />
        <main className="stage-wrap">
          {view === "2d" ? <Canvas2D /> : <View3D />}
          <BottomBar />
          <button className="maptoggle" data-testid="map-toggle" title={`Switch to ${view === "2d" ? "3D" : "2D"} (Tab)`} onClick={() => st.toggleView()}>
            <Icon name={view === "2d" ? "view3d" : "view2d"} /><span>{view === "2d" ? "3D" : "2D"}</span>
          </button>
          <ExampleNote />
          {!ready && status.level === "error" && <div className="fatal">{status.text}</div>}
        </main>
        <Inspector />
      </div>}
      <StatusBar />
      <Drawer />
      <Library />
      <Dialogs />
      <Palette />
    </div>
  );
}
