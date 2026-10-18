// Display maths for the sketch plane: path text, hit tests, the rectangle's
// handles, snapping, the camera. The UI computes no marker geometry (it
// draws what plan() returns); what is here only places and picks.
// Frame: x right, y up, millimetres (web/src/core/contract.ts).
import type { Loop, Polygon, Profile, Rect, Vec2 } from "../core/contract";

const f = (v: number) => {
  const r = Math.round(v * 10000) / 10000;
  return Object.is(r, -0) ? "0" : String(r);
};

/** One closed loop as SVG path text ("M x y L ... Z"). */
export function loopD(loop: Loop): string {
  if (!loop || loop.length < 2) return "";
  let d = `M${f(loop[0][0])} ${f(loop[0][1])}`;
  for (let i = 1; i < loop.length; i++) d += `L${f(loop[i][0])} ${f(loop[i][1])}`;
  return d + "Z";
}

/** Polygons with holes as one path (fill-rule evenodd keeps the holes open). */
export function polysD(polys: Polygon[]): string {
  return polys.map((p) => loopD(p.outer) + p.holes.map(loopD).join("")).join("");
}

/** A profile's loops as one path: the outer first, then its holes. */
export function profileD(p: Profile): string {
  return p.loops.map(loopD).join("");
}

export const SNAP = 0.5;
export function snap(v: number, step = SNAP): number {
  const r = Math.round(v / step) * step;
  return Object.is(r, -0) ? 0 : +r.toFixed(6);
}

// ------------------------------------------------------------ rectangles

/** The rectangle's four corners, counter-clockwise from bottom-left. */
export function rectCorners(r: Rect): Vec2[] {
  const a = (r.angle_deg * Math.PI) / 180, c = Math.cos(a), s = Math.sin(a);
  const hw = r.w / 2, hh = r.h / 2;
  return ([[-hw, -hh], [hw, -hh], [hw, hh], [-hw, hh]] as Vec2[]).map(([u, v]) => [r.cx + u * c - v * s, r.cy + u * s + v * c]);
}

/** A world point in the rectangle's own frame (centre origin, unrotated). */
export function toLocal(r: Rect, p: Vec2): Vec2 {
  const a = (-r.angle_deg * Math.PI) / 180, c = Math.cos(a), s = Math.sin(a);
  const dx = p[0] - r.cx, dy = p[1] - r.cy;
  return [dx * c - dy * s, dx * s + dy * c];
}

export function fromLocal(r: Rect, p: Vec2): Vec2 {
  const a = (r.angle_deg * Math.PI) / 180, c = Math.cos(a), s = Math.sin(a);
  return [r.cx + p[0] * c - p[1] * s, r.cy + p[0] * s + p[1] * c];
}

export function inRect(r: Rect, p: Vec2, pad = 0): boolean {
  const [u, v] = toLocal(r, p);
  return Math.abs(u) <= r.w / 2 + pad && Math.abs(v) <= r.h / 2 + pad;
}

/** The eight handles: corners and edge middles, by compass name. */
export type Handle = "sw" | "s" | "se" | "e" | "ne" | "n" | "nw" | "w";
export const HANDLES: Handle[] = ["sw", "s", "se", "e", "ne", "n", "nw", "w"];
const HANDLE_UV: Record<Handle, Vec2> = {
  sw: [-1, -1], s: [0, -1], se: [1, -1], e: [1, 0], ne: [1, 1], n: [0, 1], nw: [-1, 1], w: [-1, 0],
};

export function handlePoint(r: Rect, h: Handle): Vec2 {
  const [su, sv] = HANDLE_UV[h];
  return fromLocal(r, [(su * r.w) / 2, (sv * r.h) / 2]);
}

/** Resize by dragging a handle to a world point: the opposite side stays,
 *  the moved sides snap (in the rectangle's own frame). Never below `min`. */
export function resizeRect(r: Rect, h: Handle, p: Vec2, step = SNAP, min = 1): Rect {
  const [su, sv] = HANDLE_UV[h];
  const [u, v] = toLocal(r, p);
  let u0 = -r.w / 2, u1 = r.w / 2, v0 = -r.h / 2, v1 = r.h / 2;
  // snap in world terms for an unrotated rectangle (the usual case)
  const su_ = (x: number, c: number) => (r.angle_deg === 0 ? snap(x + c, step) - c : snap(x, step));
  if (su > 0) u1 = Math.max(u0 + min, su_(u, r.cx));
  if (su < 0) u0 = Math.min(u1 - min, su_(u, r.cx));
  if (sv > 0) v1 = Math.max(v0 + min, su_(v, r.cy));
  if (sv < 0) v0 = Math.min(v1 - min, su_(v, r.cy));
  const [cx, cy] = fromLocal(r, [(u0 + u1) / 2, (v0 + v1) / 2]);
  return { ...r, cx: +cx.toFixed(6), cy: +cy.toFixed(6), w: +(u1 - u0).toFixed(6), h: +(v1 - v0).toFixed(6) };
}

/** Move by a world delta, the centre snapped. */
export function moveRect(r: Rect, dx: number, dy: number, step = SNAP): Rect {
  return { ...r, cx: snap(r.cx + dx, step), cy: snap(r.cy + dy, step) };
}

/** A rectangle from two dragged corners, snapped. */
export function rectFromCorners(a: Vec2, b: Vec2, step = SNAP): Rect {
  const x0 = snap(Math.min(a[0], b[0]), step), x1 = snap(Math.max(a[0], b[0]), step);
  const y0 = snap(Math.min(a[1], b[1]), step), y1 = snap(Math.max(a[1], b[1]), step);
  return { cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, w: x1 - x0, h: y1 - y0, angle_deg: 0 };
}

// ------------------------------------------------------------ loops

/** Even-odd point in loop (the loop's winding does not matter). */
export function inLoop(loop: Loop, p: Vec2): boolean {
  let inside = false;
  for (let i = 0, j = loop.length - 1; i < loop.length; j = i++) {
    const [xi, yi] = loop[i], [xj, yj] = loop[j];
    if ((yi > p[1]) !== (yj > p[1]) && p[0] < ((xj - xi) * (p[1] - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

/** Inside the profile's material: in the outer loop and in no hole. */
export function inProfile(pr: Profile, p: Vec2): boolean {
  if (!pr.loops.length || !inLoop(pr.loops[0], p)) return false;
  return !pr.loops.slice(1).some((h) => inLoop(h, p));
}

export interface Box { x0: number; y0: number; x1: number; y1: number }

export function boxOf(points: Vec2[]): Box {
  const b = { x0: Infinity, y0: Infinity, x1: -Infinity, y1: -Infinity };
  for (const [x, y] of points) {
    b.x0 = Math.min(b.x0, x); b.y0 = Math.min(b.y0, y);
    b.x1 = Math.max(b.x1, x); b.y1 = Math.max(b.y1, y);
  }
  return b;
}

export function boxUnion(a: Box | null, b: Box | null): Box | null {
  if (!a) return b;
  if (!b) return a;
  return { x0: Math.min(a.x0, b.x0), y0: Math.min(a.y0, b.y0), x1: Math.max(a.x1, b.x1), y1: Math.max(a.y1, b.y1) };
}

/** Signed area (positive = counter-clockwise). */
export function loopArea(loop: Loop): number {
  let a = 0;
  for (let i = 0, j = loop.length - 1; i < loop.length; j = i++) a += loop[j][0] * loop[i][1] - loop[i][0] * loop[j][1];
  return a / 2;
}

/** The centroid of a loop's vertices' box: the middle of what is drawn. */
export function loopCentre(loop: Loop): Vec2 {
  const b = boxOf(loop);
  return [(b.x0 + b.x1) / 2, (b.y0 + b.y1) / 2];
}

/** A circle as a loop (counter-clockwise; `cw` for a hole). */
export function circleLoop(cx: number, cy: number, r: number, n = 64, cw = false): Loop {
  const out: Loop = [];
  for (let i = 0; i < n; i++) {
    const a = ((cw ? -i : i) / n) * Math.PI * 2;
    out.push([+(cx + r * Math.cos(a)).toFixed(4), +(cy + r * Math.sin(a)).toFixed(4)]);
  }
  return out;
}

/** Does a loop (as a polygon) come within `pad` of the rectangle's area?
 *  Used to prove an inscribed rectangle keeps off a hole. */
export function loopHitsRect(loop: Loop, r: Rect, pad = 0): boolean {
  if (loop.some((p) => inRect(r, p, pad))) return true;
  if (rectCorners(r).some((c) => inLoop(loop, c))) return true;
  // edges crossing
  const cs = rectCorners(r);
  for (let i = 0; i < loop.length; i++) {
    const a = loop[i], b = loop[(i + 1) % loop.length];
    for (let k = 0; k < 4; k++) if (segsCross(a, b, cs[k], cs[(k + 1) % 4])) return true;
  }
  return false;
}

function segsCross(a: Vec2, b: Vec2, c: Vec2, d: Vec2): boolean {
  const o = (p: Vec2, q: Vec2, r: Vec2) => Math.sign((q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]));
  return o(a, b, c) !== o(a, b, d) && o(c, d, a) !== o(c, d, b);
}

// ------------------------------------------------------------ the camera

/** zoom = screen px per mm; (cx, cy) = the world point at the view's centre. */
export interface Camera { cx: number; cy: number; zoom: number }

export function toScreen(cam: Camera, w: number, h: number, p: Vec2): Vec2 {
  return [w / 2 + (p[0] - cam.cx) * cam.zoom, h / 2 - (p[1] - cam.cy) * cam.zoom];
}

export function toWorld(cam: Camera, w: number, h: number, s: Vec2): Vec2 {
  return [(s[0] - w / 2) / cam.zoom + cam.cx, -(s[1] - h / 2) / cam.zoom + cam.cy];
}

/** Zoom by k about a screen point: the world point under it stays put. */
export function zoomAt(cam: Camera, w: number, h: number, s: Vec2, k: number): Camera {
  const zoom = Math.max(0.2, Math.min(200, cam.zoom * k));
  const [wx, wy] = toWorld(cam, w, h, s);
  return { zoom, cx: wx - (s[0] - w / 2) / zoom, cy: wy + (s[1] - h / 2) / zoom };
}

/** The camera that shows a box with a margin (px) on every side. */
export function fitBox(b: Box, w: number, h: number, margin = 48): Camera {
  const bw = Math.max(b.x1 - b.x0, 1), bh = Math.max(b.y1 - b.y0, 1);
  const zoom = Math.max(0.2, Math.min(200, Math.min((w - 2 * margin) / bw, (h - 2 * margin) / bh)));
  return { cx: (b.x0 + b.x1) / 2, cy: (b.y0 + b.y1) / 2, zoom };
}

const STEPS = [0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000];
/** The grid's major step: the first that is at least `px` apart on screen. */
export function niceStep(zoom: number, px = 70): number {
  for (const s of STEPS) if (s * zoom >= px) return s;
  return STEPS[STEPS.length - 1];
}

// ------------------------------------------------------------ the plan's frame

/** A row-major 4x4 (mm): its origin and x / y axes in the sketch plane. */
export function frameOf(m: number[]): { o: Vec2; x: Vec2; y: Vec2 } | null {
  if (!m || m.length !== 16) return null;
  return { o: [m[3], m[7]], x: [m[0], m[4]], y: [m[1], m[5]] };
}
