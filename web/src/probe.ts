// window.__aruco: a small probe for the e2e tests. State getters in
// millimetres, a world → client mapping for pointer drags, and idle(),
// which resolves once no core call is in flight or scheduled; plan() asks the
// core directly (an e2e compares a request the UI no longer sends).
import type { MarkerPlan, PlanRequest } from "./core/contract";
import { callsInFlight, core, coreKind, coreStatus } from "./coreSource";
import { toScreen } from "./model/geom";
import { plannerBusy } from "./planner";
import { getFeature } from "./model/doc";
import { activeFeatureId, useStudio } from "./store";
import { view3d, type View3DProbe } from "./view3d/probe3d";
import { exampleMarksKnown } from "./app/thumbs";
import { useScale } from "./zoom/scale";
import { useOverlays } from "./overlays/overlays";

export interface Probe {
  kind: "real" | "mock";
  state: () => ReturnType<typeof snapshot>;
  /** a sketch point (mm) as client pixels in the page */
  toClient: (x: number, y: number) => [number, number];
  idle: (timeoutMs?: number) => Promise<void>;
  plan: (req: PlanRequest) => Promise<MarkerPlan>;
  printHook: (() => void) | null;
  /** the 3D view's arrows (client px), heights and solids; null in 2D */
  view3d: () => Omit<View3DProbe, "project" | "top"> | null;
  /** a 3D scene point (mm, z along the face normal) as client pixels; null in 2D */
  project3d: (x: number, y: number, z: number) => [number, number] | null;
  /** the 3D camera straight down on the feature in focus, or `tilt` degrees off (marks false: no arrows / boxes) */
  top3d: (marks?: boolean, tilt?: number) => void;
}

/** `feature` and `plan` are the feature in focus (the panel's, the selected
 *  one, else the last made) and its plan; `plans` has every feature's. */
function snapshot() {
  const s = useStudio.getState();
  const active = activeFeatureId(s);
  return {
    core: coreStatus(), doc: s.doc, sel: s.sel, tool: s.tool, camera: s.camera, view: s.view,
    panel: { open: s.panel.open, featureId: s.panel.featureId, tab: s.panel.tab, selector: s.panel.selector, collapsed: s.panel.collapsed },
    feature: getFeature(s.doc, active), plan: active ? s.plans[active] ?? null : null, plans: s.plans,
    suggestions: s.suggestions, modal: s.modal,
    canUndo: s.canUndo, canRedo: s.canRedo, view3d: s.view3d,
    // the sketch lane (2026-10-20 night): every selected shape, the selected sketch dim
    selection: s.multi, dimSel: s.dimSel,
    // the canvas3 lane (2026-10-21): View › Marker info, and how many markers each example's thumbnail knows
    markerInfo: s.markerInfo, thumbs: exampleMarksKnown(),
    // the actualsize lane (2026-10-21): this screen's scale (px per mm) for Actual size, and whether it is calibrated
    scale: (({ key, pxPerMm, calibrated, basis }) => ({ key, pxPerMm, calibrated, basis }))(useScale.getState().scale),
    // the calmcanvas lane (2026-10-21): the Layers menu's background and switches
    overlays: useOverlays.getState().overlays,
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
      const busy = callsInFlight() > 0 || plannerBusy();
      quiet = busy ? 0 : quiet + 1;
      if (quiet >= 3) return resolve();
      if (performance.now() - t0 > timeoutMs) return reject(new Error("core calls still in flight"));
      setTimeout(tick, 20);
    };
    tick();
  });
}

export function installProbe(): void {
  const probe: Probe = {
    kind: coreKind, state: snapshot, toClient, idle, plan: (req) => core.plan(req), printHook: null,
    view3d: () => { const p = view3d.probe?.(); if (!p) return null; const { project: _p, top: _t, ...rest } = p; return rest; },
    project3d: (x, y, z) => view3d.probe?.().project(x, y, z) ?? null,
    top3d: (marks, tilt) => view3d.probe?.().top(marks, tilt),
  };
  (window as unknown as { __aruco: Probe }).__aruco = probe;
}
