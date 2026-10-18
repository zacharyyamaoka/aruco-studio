// window.__aruco: a small probe for the e2e tests. State getters in
// millimetres, a world → client mapping for pointer drags, and idle(),
// which resolves once no core call is in flight or scheduled.
import { callsInFlight, coreKind, coreStatus } from "./coreSource";
import { toScreen } from "./model/geom";
import { plannerBusy } from "./planner";
import { useStudio } from "./store";

export interface Probe {
  kind: "real" | "mock";
  state: () => ReturnType<typeof snapshot>;
  /** a sketch point (mm) as client pixels in the page */
  toClient: (x: number, y: number) => [number, number];
  idle: (timeoutMs?: number) => Promise<void>;
  printHook: (() => void) | null;
}

function snapshot() {
  const s = useStudio.getState();
  return {
    core: coreStatus(), doc: s.doc, sel: s.sel, tool: s.tool, camera: s.camera, view: s.view,
    panel: { open: s.panel.open, tab: s.panel.tab, selector: s.panel.selector, collapsed: s.panel.collapsed },
    plan: s.plan, suggestions: s.suggestions, modal: s.modal, inscribing: s.inscribing,
  };
}

function toClient(x: number, y: number): [number, number] {
  const s = useStudio.getState();
  const el = document.querySelector('[data-testid="viewport"]');
  const r = el?.getBoundingClientRect() ?? { left: 0, top: 0 };
  const [sx, sy] = toScreen(s.camera, s.view.w, s.view.h, [x, y]);
  return [r.left + sx, r.top + sy];
}

function idle(timeoutMs = 15000): Promise<void> {
  const t0 = performance.now();
  return new Promise((resolve, reject) => {
    let quiet = 0;
    const tick = () => {
      const busy = callsInFlight() > 0 || plannerBusy() || useStudio.getState().inscribing;
      quiet = busy ? 0 : quiet + 1;
      if (quiet >= 3) return resolve();
      if (performance.now() - t0 > timeoutMs) return reject(new Error("core calls still in flight"));
      setTimeout(tick, 20);
    };
    tick();
  });
}

export function installProbe(): void {
  const probe: Probe = { kind: coreKind, state: snapshot, toClient, idle, printHook: null };
  (window as unknown as { __aruco: Probe }).__aruco = probe;
}
