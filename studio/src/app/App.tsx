// The Studio: toolbar on top, IDs on the left, the canvas (2D or 3D) in the
// middle, the inspector on the right, the status bar and drawer below.
import { useEffect } from "react";
import { Canvas2D } from "../canvas/Canvas2D";
import { IdsTable } from "../ids/IdsTable";
import { Inspector } from "../inspector/Inspector";
import { Library } from "../library/Library";
import { useStudio } from "../store";
import { Icon } from "../ui/controls";
import { View3D } from "../view3d/View3D";
import { Dialogs } from "./Dialogs";
import { Drawer, StatusBar } from "./Drawer";
import { Toolbar } from "./Toolbar";

function typing(e: KeyboardEvent) {
  const t = e.target as HTMLElement | null;
  return !!t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable);
}

function useKeys() {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const st = useStudio.getState();
      if (st.libraryOpen || st.dialog || typing(e)) return;
      const k = e.key.toLowerCase();
      const ctrl = e.ctrlKey || e.metaKey;
      const step = e.shiftKey ? 5 : 0.5;
      const go = (fn: () => unknown) => { e.preventDefault(); fn(); };
      if (ctrl && k === "z" && !e.shiftKey) return go(() => st.undo());
      if (ctrl && ((k === "z" && e.shiftKey) || k === "y")) return go(() => st.redo());
      if (ctrl && k === "d") return go(() => st.duplicateSel());
      if (ctrl && k === "a") return go(() => st.selectAll());
      if (ctrl && k === "s") return go(() => st.saveScene());
      if (ctrl && k === "o") return go(() => st.setDialog({ kind: "open" }));
      if (ctrl) return;
      if (k === "delete" || k === "backspace") return go(() => st.deleteSel());
      if (k === "escape") return go(() => st.setSel([]));
      if (k === "tab") return go(() => st.toggleView());
      if (k === "arrowleft") return go(() => st.nudge(-step, 0));
      if (k === "arrowright") return go(() => st.nudge(step, 0));
      if (k === "arrowup") return go(() => st.nudge(0, step));
      if (k === "arrowdown") return go(() => st.nudge(0, -step));
      if (k === "r") return go(() => st.rotateSel(e.shiftKey ? 90 : -90));
      if (k === "s") return go(() => st.addTag("single"));
      if (k === "g") return go(() => st.addTag("grid"));
      if (k === "c") return go(() => st.addTag("charuco"));
      if (k === "f") return go(() => st.zoomToFit(st.sel.length ? st.sel : undefined));
      if (k === "q") return go(() => st.setShow("quiet", !st.show.quiet));
      if (k === "a" && e.shiftKey) return go(() => st.arrange());
      if (k === "a") return go(() => st.setShow("axes", !st.show.axes));
      if (k === "l") return go(() => st.setShow("outlines", !st.show.outlines));
      if (k === "v") return go(() => st.verifySel());
      if (e.key === "?") return go(() => st.setDrawer(st.drawer === "messages" ? null : "messages"));
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
  useKeys();
  useEffect(() => {
    if (started) return;
    started = true;
    useStudio.getState().init().catch((e) => useStudio.getState().say(`The Studio's server did not answer on /api (${e}). Start it: .venv/Scripts/python -m aruco_studio.server`, "error"));
  }, []);
  const st = useStudio.getState();
  return (
    <div className="app" data-ready={ready ? "1" : "0"} data-view={view}>
      <Toolbar />
      <div className="body">
        <IdsTable />
        <main className="stage-wrap">
          {view === "2d" ? <Canvas2D /> : <View3D />}
          <button className="maptoggle" data-testid="map-toggle" title={`Switch to ${view === "2d" ? "3D" : "2D"} (Tab)`} onClick={() => st.toggleView()}>
            <Icon name={view === "2d" ? "view3d" : "view2d"} /><span>{view === "2d" ? "3D" : "2D"}</span>
          </button>
          {!ready && status.level === "error" && <div className="fatal">{status.text}</div>}
        </main>
        <Inspector />
      </div>
      <StatusBar />
      <Drawer />
      <Library />
      <Dialogs />
    </div>
  );
}
