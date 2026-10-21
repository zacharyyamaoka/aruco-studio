// The 2D canvas's zoom commands (Figma's: Shift+1 zoom to fit, Shift+2 zoom
// to selection, and its 100 %), plus Actual size (Shift+0; ./scale.ts): the
// context menu, the zoom indicator, View and the keys share them.
import type { MarkerPlan, Vec2 } from "../core/contract";
import { getFeature, type Doc } from "../model/doc";
import { boxOf, boxUnion, fitBox, rectCorners, toWorld, type Box, type Camera } from "../model/geom";
import { sketchBox, type Selection } from "../sketch/model";
import { useStudio } from "../store";
import { CSS_PX_PER_MM, isActual, useScale } from "./scale";

/** The camera at exactly `zoom` (CSS px per mm), the world point under the
 *  view point `s` staying put (model/geom.ts zoomAt multiplies; this sets). */
export function zoomTo(cam: Camera, w: number, h: number, s: Vec2, zoom: number): Camera {
  const [wx, wy] = toWorld(cam, w, h, s);
  return { zoom, cx: wx - (s[0] - w / 2) / zoom, cy: wy + (s[1] - h / 2) / zoom };
}

/** What a plan covers on the sketch: its outline, the box it was placed in, its label. */
function planBox(plan: MarkerPlan): Box {
  const lab = plan.label ? [[plan.label.at[0], plan.label.at[1] - plan.label.height_mm], [plan.label.at[0], plan.label.at[1] + plan.label.height_mm]] as Vec2[] : [];
  return boxOf([...(plan.fit_rect ? rectCorners(plan.fit_rect) : []), ...plan.outer, ...lab]);
}

/** The box (mm) the selection covers, or null when nothing is selected: a
 *  marker (or its Joint Origin or label) is its plan's box, as the panel's
 *  fit frames it; shapes (one, several, a profile) are their outlines and the
 *  markers on them. */
export function selectionBox(doc: Doc, plans: Record<string, MarkerPlan>, sel: Selection, multi: string[]): Box | null {
  if (multi.length <= 1 && (sel?.kind === "feature" || sel?.kind === "origin" || sel?.kind === "text")) {
    const f = getFeature(doc, sel.id);
    const plan = f ? plans[f.id] : undefined;
    if (plan) return planBox(plan);
    const ref = f?.profile;
    return ref ? sketchBox(doc.shapes.filter((s) => s.id === ref.outer)) : null;
  }
  const ids = multi.length ? multi : sel?.kind === "shape" ? [sel.id] : sel?.kind === "profile" ? [sel.ref.outer] : [];
  let b = sketchBox(doc.shapes.filter((s) => ids.includes(s.id)));
  if (!b) return null;
  for (const f of doc.features) if (f.profile && ids.includes(f.profile.outer) && plans[f.id]) b = boxUnion(b, planBox(plans[f.id]));
  return b;
}

const st = () => useStudio.getState();
/** The view's centre (view px): where a zoom from a key or the indicator is about. */
const centre = (): Vec2 => [st().view.w / 2, st().view.h / 2];
/** The fit's margin (px), store.fit's: less on a phone. */
const margin = () => (st().view.w < 640 ? 28 : 84);

/** Zoom to `zoom` px/mm about a view point (default: the view's centre). */
export function setZoom(zoom: number, at: Vec2 = centre()): void {
  const { camera, view, setCamera } = st();
  setCamera(zoomTo(camera, view.w, view.h, at, zoom));
}

/** Shift+1, F: everything in view (the store's fit). */
export const zoomToFit = (): void => st().fit();
/** Shift+2: the selection in view; false (nothing done) when nothing is selected. */
export function zoomToSelection(): boolean {
  const { doc, plans, sel, multi, view, setCamera } = st();
  const b = selectionBox(doc, plans, sel, multi);
  if (!b) return false;
  setCamera(fitBox(b, view.w, view.h, margin()));
  return true;
}
export const hasSelection = (): boolean => { const { doc, plans, sel, multi } = st(); return !!selectionBox(doc, plans, sel, multi); };
/** Shift+0: this screen's millimetre (calibrated, else estimated: ./scale.ts). */
export const actualSize = (at?: Vec2): void => setZoom(useScale.getState().scale.pxPerMm, at);
/** 100 %: CSS's millimetre, 96 px per inch (what a browser calls 1 mm). */
export const zoom100 = (at?: Vec2): void => setZoom(CSS_PX_PER_MM, at);
export const openCalibrate = (): void => useScale.getState().setCalibrating(true);

/** Keep Actual size actual: when the scale changes (another monitor, a page
 *  zoom, a calibration saved) and the camera was at the old one, it moves to
 *  the new one, about the view's centre. In 3D the 2D camera waits (setting it
 *  there refits the 3D view): it follows on the way back to 2D. */
export function followScale(): () => void {
  let behind = false;
  const offScale = useScale.subscribe((s, prev) => {
    if (s.scale.pxPerMm === prev.scale.pxPerMm) return;
    const { camera, view3d } = st();
    if (!behind && !isActual(camera.zoom, prev.scale.pxPerMm)) return;
    if (view3d) { behind = true; return; }
    behind = false;
    setZoom(s.scale.pxPerMm);
  });
  const offStudio = useStudio.subscribe((s, prev) => {
    if (behind && prev.view3d && !s.view3d) { behind = false; setZoom(useScale.getState().scale.pxPerMm); }
    // the 2D camera was set meanwhile (F in 3D fits it): it no longer follows
    else if (behind && s.camera !== prev.camera) behind = false;
  });
  return () => { offScale(); offStudio(); };
}
