// The 3D view's numbers, pure (vitest: heights.test.ts): a feature's heights
// as planned (MarkerPlan.extrude, else read off its `layers` -- a core from
// before barrier 10 sends only those), the drag arrows they give (Fusion's
// Extrude manipulator: one per height, on the face it moves), and the snap a
// drag lands on.
//
// Frame: the sketch's, z along the face normal (mm, 0 = the face plane);
// `out` is +1, or -1 when the marker is turned over (Flip).
import type { MarkerPlan, Method, Preset, Vec2 } from "../core/contract";
import { isSet, type Feature } from "../model/doc";

export type Mode = "both" | "black" | "white";
export type HeightKey = "white_mm" | "black_mm" | "paper_mm";

export interface Heights {
  method: Method;
  mode: Mode;
  white_mm: number;
  black_mm: number;
  paper_mm: number;
  flipped: boolean;
}

type Layer = NonNullable<MarkerPlan["layers"]>[number];

/** to the micron, as the core rounds (web_api._r) */
const um = (v: number) => Math.round(v * 1e6) / 1e6;
const span = (L: Layer) => um(L.z[1] - L.z[0]);
const mid = (L: Layer) => (L.z[0] + L.z[1]) / 2;
/** how far a layer reaches from the face plane, either side */
const reach = (L: Layer) => Math.max(Math.abs(L.z[0]), Math.abs(L.z[1]));

/** The solids that are made (op add), not the cut tools; the label's ink rides on the black. */
function made(plan: MarkerPlan, colour: "white" | "black"): Layer | undefined {
  return plan.layers?.find((L) => L.op === "add" && L.colour === colour && L.part !== "label");
}

/** The heights the core planned: MarkerPlan.extrude when it sends it, else
 *  read off the layers (white: the tile's outer face; black: its depth;
 *  paper: the sticker's thickness; flipped: the side the solids stand on). */
export function heightsOf(plan: MarkerPlan, method: Method): Heights | null {
  if (plan.extrude) {
    const e = plan.extrude;
    return { method: e.method, mode: e.mode, white_mm: e.white_mm, black_mm: e.black_mm, paper_mm: e.paper_mm, flipped: e.flipped };
  }
  const white = made(plan, "white"), black = made(plan, "black");
  if (!white && !black) return null;
  if (method === "inkjet") {
    const paper = white ?? black!;
    return { method, mode: "both", white_mm: 0, black_mm: black ? span(black) : 0, paper_mm: span(paper), flipped: mid(paper) < 0 };
  }
  const mode: Mode = white && black ? "both" : black ? "black" : "white";
  // black only goes INTO the body (z below the face): it is out of the face when z sits above
  const flipped = white ? mid(white) < 0 : mid(black!) > 0;
  return { method, mode, white_mm: white ? reach(white) : 0, black_mm: black ? span(black) : 0, paper_mm: 0, flipped };
}

export interface ArrowSpec {
  key: HeightKey;
  field: `extrude.${HeightKey}`;
  /** the value shown: the feature's own when set, else the planned (driven) one */
  value: number;
  driven: boolean;
  /** where it stands on the face (sketch frame) and the face's z */
  at: Vec2;
  z: number;
  /** +1 / -1: the z direction that makes the value grow (the arrow points that way) */
  dir: number;
  /** the dimension line: beside the outline, from z0 (where the height is measured from) to z1,
   *  its extension lines running in from `edge` (the outline's side) */
  dim: { at: Vec2; edge: Vec2; z0: number; z1: number };
}

function box(loop: Vec2[]) {
  const xs = loop.map((p) => p[0]), ys = loop.map((p) => p[1]);
  return { x0: Math.min(...xs), y0: Math.min(...ys), x1: Math.max(...xs), y1: Math.max(...ys) };
}

/** The value a height row shows: set (the feature's) or driven (the plan's). */
function shown(f: Feature, h: Heights, key: HeightKey): { value: number; driven: boolean } {
  const driven = !isSet(f, `extrude.${key}`);
  return { value: driven ? h[key] : (f.extrude[key] as number), driven };
}

/** The arrows on a feature: 3D print, the WHITE at its outer face (out) and
 *  the BLACK at its inner end, measured from that same outer face (in);
 *  inkjet, the PAPER at its outer face. `white` / `black` only show what is
 *  made (black only: the black goes into the face from z 0). */
export function arrowsOf(f: Feature, plan: MarkerPlan, h: Heights): ArrowSpec[] {
  const out = h.flipped ? -1 : 1;
  const b = box(plan.outer);
  const c: Vec2 = [(b.x0 + b.x1) / 2, (b.y0 + b.y1) / 2];
  const size = Math.max(b.x1 - b.x0, b.y1 - b.y0);
  // the dimension lines stand off the outline's left edge, the black's further out
  const gap = Math.max(1, size * 0.05);
  const edge: Vec2 = [b.x0, c[1]];
  const dimAt = (k: number): Vec2 => [b.x0 - gap * k, c[1]];
  const arrows: ArrowSpec[] = [];
  if (h.method === "inkjet") {
    const p = shown(f, h, "paper_mm");
    arrows.push({ key: "paper_mm", field: "extrude.paper_mm", ...p, at: c, z: out * p.value, dir: out, dim: { at: dimAt(1), edge, z0: 0, z1: out * p.value } });
    return arrows;
  }
  const w = shown(f, h, "white_mm");
  const face = h.mode === "black" ? 0 : w.value;
  if (h.mode !== "black") {
    arrows.push({ key: "white_mm", field: "extrude.white_mm", ...w, at: c, z: out * face, dir: out, dim: { at: dimAt(1), edge, z0: 0, z1: out * face } });
  }
  if (h.mode !== "white") {
    const k = shown(f, h, "black_mm");
    // WHY beside the white's (Zach, 2026-10-20 night): "black height is always measured from the outer face of the white"
    const at: Vec2 = [c[0] - (b.x1 - b.x0) * 0.25, c[1]];
    const z = out * (face - k.value);
    arrows.push({ key: "black_mm", field: "extrude.black_mm", ...k, at, z, dir: -out, dim: { at: dimAt(2), edge, z0: out * face, z1: z } });
  }
  return arrows;
}

/** The step a free drag would snap to, mm. */
export const FINE_MM = 0.05;

/** Where a dragged height lands.
 *  WHY whole layers (lane view3d, 2026-10-20 night): a printed height is
 *  always the first layer plus whole layers, so a drag that lands between
 *  them is a height the slicer rounds anyway; a preset with `layer_mm`
 *  snaps to first_layer_mm + k × layer_mm (first_layer_mm 0 or absent:
 *  k × layer_mm), one layer at the least. Without a layer height (inkjet,
 *  the built-in Default) it snaps to FINE_MM. Shift (`free`) does not snap
 *  (to the micron); the typed box never snaps. */
export function snapHeight(v: number, preset: Preset | null | undefined, free = false): number {
  const r6 = (x: number) => Math.round(x * 1e6) / 1e6;
  if (free) return r6(Math.max(0.001, Math.round(v * 1000) / 1000));
  const layer = preset?.layer_mm ?? 0;
  if (layer > 0) {
    const first = preset?.first_layer_mm && preset.first_layer_mm > 0 ? preset.first_layer_mm : layer;
    return r6(first + Math.max(0, Math.round((v - first) / layer)) * layer);
  }
  return r6(Math.max(FINE_MM, Math.round(v / FINE_MM) * FINE_MM));
}

/** "1.80 mm", as Fusion's value box. */
export const fmtMm = (v: number) => `${v.toFixed(2)} mm`;
