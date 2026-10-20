// The sketch model: closed shapes (rectangle, circle, polygon), the texts
// placed on the plane, the selection, and the pure hit tests over them.
//
// WHY one seam: the viewport only renders this model and turns pointer
// events into its actions, so the canvas can be swapped (Zach is weighing
// tldraw, 2026-10-18) without touching the panel, the presets or Print.
// Nothing outside web/src/sketch/ and Viewport.tsx knows how a shape is
// drawn or picked.
//
// Fusion's selection: a click on a shape's EDGE picks the shape (to move or
// resize it); a click INSIDE a region picks the profile there: the innermost
// closed shape around the point minus the closed shapes directly inside it
// (its holes); a DOUBLE-click on a rectangle (its edge or inside it) picks the
// rectangle's outer edges alone as the profile (rectAt). plan() gets the
// profile and places the marker in it (contract.ts, barrier 9).
import type { Loop, Profile, Rect, Vec2 } from "../core/contract";
import {
  boxOf, boxUnion, circleLoop, inLoop, loopArea, rectCorners, resizeRect, snap, toLocal, type Box, type Handle,
} from "../model/geom";

export interface RectShape extends Rect { kind: "rect"; id: string }
export interface CircleShape { kind: "circle"; id: string; cx: number; cy: number; r: number }
export interface PolyShape { kind: "poly"; id: string; pts: Vec2[] }
export type Shape = RectShape | CircleShape | PolyShape;

/** A sketch text (the marker's label): placed by the core, moved by a drag. */
export interface SketchText { id: string; text: string; at: Vec2; height_mm: number; angle_deg: number }

/** A profile by the ids that bound it: the outer shape and its direct holes. */
export interface ProfileRef { outer: string; holes: string[] }

export type Selection =
  | { kind: "shape"; id: string }
  | { kind: "profile"; ref: ProfileRef }
  | { kind: "text"; id: string }          // a feature's label: id = the feature's
  | { kind: "feature"; id: string }
  | { kind: "origin"; id: string }        // a feature's Joint Origin
  | { kind: "sketch" }
  | null;

// ------------------------------------------------------------ loops

/** A shape's boundary as a counter-clockwise loop. */
export function shapeLoop(s: Shape): Loop {
  if (s.kind === "rect") return rectCorners(s);
  if (s.kind === "circle") return circleLoop(s.cx, s.cy, s.r, 96);
  return loopArea(s.pts) >= 0 ? s.pts : [...s.pts].reverse();
}

export function shapeBox(s: Shape): Box {
  if (s.kind === "circle") return { x0: s.cx - s.r, y0: s.cy - s.r, x1: s.cx + s.r, y1: s.cy + s.r };
  return boxOf(shapeLoop(s));
}

export function sketchBox(shapes: Shape[]): Box | null {
  return shapes.reduce<Box | null>((b, s) => boxUnion(b, shapeBox(s)), null);
}

/** Inside a shape's boundary (a circle exactly, the rest as polygons). */
export function inShape(s: Shape, p: Vec2): boolean {
  if (s.kind === "circle") return Math.hypot(p[0] - s.cx, p[1] - s.cy) <= s.r;
  if (s.kind === "rect") {
    const [u, v] = toLocal(s, p);
    return Math.abs(u) <= s.w / 2 && Math.abs(v) <= s.h / 2;
  }
  return inLoop(s.pts, p);
}

/** b lies inside a (every point of b's boundary is in a, and b is smaller). */
export function contains(a: Shape, b: Shape): boolean {
  if (a.id === b.id) return false;
  if (Math.abs(loopArea(shapeLoop(b))) >= Math.abs(loopArea(shapeLoop(a)))) return false;
  return shapeLoop(b).every((p) => inShape(a, p));
}

/** The closed shapes directly inside `outer` (inside it, and not inside
 *  another shape that is itself inside it): the outer's holes. */
export function directChildren(shapes: Shape[], outer: Shape, skip: string[] = []): Shape[] {
  const inner = shapes.filter((s) => !skip.includes(s.id) && contains(outer, s));
  return inner.filter((s) => !inner.some((o) => o.id !== s.id && contains(o, s)));
}

/** The profile around a point: the innermost shape that contains it, minus
 *  its direct children. null = outside every shape. */
export function profileAt(shapes: Shape[], p: Vec2, skip: string[] = []): ProfileRef | null {
  const around = shapes.filter((s) => !skip.includes(s.id) && inShape(s, p));
  if (!around.length) return null;
  const innermost = around.reduce((a, b) => (Math.abs(loopArea(shapeLoop(b))) < Math.abs(loopArea(shapeLoop(a))) ? b : a));
  return { outer: innermost.id, holes: directChildren(shapes, innermost, skip).map((s) => s.id) };
}

/** A profile's loops for the core: the outer counter-clockwise, the holes
 *  clockwise. null when a shape it names is gone. */
export function profileLoops(shapes: Shape[], ref: ProfileRef): Profile | null {
  const byId = (id: string) => shapes.find((s) => s.id === id);
  const outer = byId(ref.outer);
  if (!outer) return null;
  const holes = ref.holes.map(byId).filter((s): s is Shape => !!s);
  return { loops: [shapeLoop(outer), ...holes.map((h) => [...shapeLoop(h)].reverse())] };
}

/** A profile that is just a rectangle with nothing inside: the marker fills
 *  that rectangle itself (the core uses a rectangle profile exactly). */
export function plainRect(shapes: Shape[], ref: ProfileRef): RectShape | null {
  const s = shapes.find((x) => x.id === ref.outer);
  return s && s.kind === "rect" && !ref.holes.length ? s : null;
}

export function sameProfile(a: ProfileRef | null, b: ProfileRef | null): boolean {
  if (!a || !b) return a === b;
  return a.outer === b.outer && a.holes.length === b.holes.length && a.holes.every((h) => b.holes.includes(h));
}

// ------------------------------------------------------------ hit tests

function distToSeg(p: Vec2, a: Vec2, b: Vec2): number {
  const dx = b[0] - a[0], dy = b[1] - a[1];
  const l2 = dx * dx + dy * dy;
  const t = l2 ? Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2)) : 0;
  return Math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy));
}

/** How far a point is from a shape's edge (mm). */
export function edgeDistance(s: Shape, p: Vec2): number {
  if (s.kind === "circle") return Math.abs(Math.hypot(p[0] - s.cx, p[1] - s.cy) - s.r);
  const loop = shapeLoop(s);
  let d = Infinity;
  for (let i = 0; i < loop.length; i++) d = Math.min(d, distToSeg(p, loop[i], loop[(i + 1) % loop.length]));
  return d;
}

export type Hit =
  | { kind: "edge"; id: string }
  | { kind: "region"; ref: ProfileRef }
  | null;

/** What a click at p picks: the nearest edge within `tol` mm (the smallest
 *  shape wins a tie), else the region around p. */
export function hitTest(shapes: Shape[], p: Vec2, tol: number): Hit {
  let best: { id: string; d: number; a: number } | null = null;
  for (const s of shapes) {
    const d = edgeDistance(s, p);
    if (d > tol) continue;
    const a = Math.abs(loopArea(shapeLoop(s)));
    if (!best || d < best.d - 1e-9 || (Math.abs(d - best.d) < 1e-9 && a < best.a)) best = { id: s.id, d, a };
  }
  if (best) return { kind: "edge", id: best.id };
  const ref = profileAt(shapes, p);
  return ref ? { kind: "region", ref } : null;
}

/** The rectangle a double-click at p picks: the nearest rectangle edge within
 *  `tol` mm (the smallest rectangle wins a tie), else the innermost rectangle
 *  around p. null = no rectangle there. */
export function rectAt(shapes: Shape[], p: Vec2, tol: number): RectShape | null {
  const rects = shapes.filter((s): s is RectShape => s.kind === "rect");
  const hit = hitTest(rects, p, tol);
  if (hit?.kind === "edge") return rects.find((s) => s.id === hit.id) ?? null;
  const around = rects.filter((s) => inShape(s, p));
  if (!around.length) return null;
  return around.reduce((a, b) => (b.w * b.h < a.w * a.h ? b : a));
}

// ------------------------------------------------------------ box selection

function segsCross(a: Vec2, b: Vec2, c: Vec2, d: Vec2): boolean {
  const o = (p: Vec2, q: Vec2, r: Vec2) => Math.sign((q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]));
  return o(a, b, c) !== o(a, b, d) && o(c, d, a) !== o(c, d, b);
}

/** The shapes a selection box picks (a box in sketch mm). A WINDOW (dragged
 *  left to right) takes the shapes wholly inside it; a CROSSING (right to
 *  left) also takes those its edges touch: the CAD convention (Fusion,
 *  AutoCAD). A box wholly inside a shape does not touch it. */
export function boxPick(shapes: Shape[], box: Box, crossing: boolean): string[] {
  const inBox = (p: Vec2) => p[0] >= box.x0 && p[0] <= box.x1 && p[1] >= box.y0 && p[1] <= box.y1;
  const edges: [Vec2, Vec2][] = [
    [[box.x0, box.y0], [box.x1, box.y0]], [[box.x1, box.y0], [box.x1, box.y1]],
    [[box.x1, box.y1], [box.x0, box.y1]], [[box.x0, box.y1], [box.x0, box.y0]],
  ];
  return shapes.filter((s) => {
    const loop = shapeLoop(s);
    if (loop.every(inBox)) return true;
    if (!crossing) return false;
    if (loop.some(inBox)) return true;
    return loop.some((p, i) => edges.some(([c, d]) => segsCross(p, loop[(i + 1) % loop.length], c, d)));
  }).map((s) => s.id);
}

// ------------------------------------------------------------ edits

/** Move by a delta snapped to the step: a shape keeps its own offsets from
 *  the grid (an inscribed rectangle at 60.25 moves to 80.25). */
export function moveShape(s: Shape, dx: number, dy: number, step = 0.5): Shape {
  const sx = snap(dx, step), sy = snap(dy, step);
  if (s.kind === "poly") return { ...s, pts: s.pts.map(([x, y]) => [+(x + sx).toFixed(6), +(y + sy).toFixed(6)] as Vec2) };
  return { ...s, cx: +(s.cx + sx).toFixed(6), cy: +(s.cy + sy).toFixed(6) };
}

/** Drag a handle to p. A rectangle has eight; a circle one (its radius). */
export function resizeShape(s: Shape, h: Handle, p: Vec2, step = 0.5): Shape {
  if (s.kind === "rect") return { ...s, ...resizeRect(s, h, p, step), kind: "rect", id: s.id };
  if (s.kind === "circle") return { ...s, r: Math.max(step, snap(Math.hypot(p[0] - s.cx, p[1] - s.cy), step)) };
  return s;
}

/** A circle from its centre and a dragged point on it. */
export function circleFrom(c: Vec2, p: Vec2, id: string, step = 0.5): CircleShape {
  return { kind: "circle", id, cx: snap(c[0], step), cy: snap(c[1], step), r: snap(Math.hypot(p[0] - c[0], p[1] - c[1]), step) };
}

/** The rectangle part of a rect shape (what the core sees). */
export function rectOf(s: RectShape): Rect {
  return { cx: s.cx, cy: s.cy, w: s.w, h: s.h, angle_deg: s.angle_deg };
}

// ------------------------------------------------------------ the golden examples' shapes

export function rectShape(id: string, x0: number, y0: number, x1: number, y1: number): RectShape {
  return { kind: "rect", id, cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, w: x1 - x0, h: y1 - y0, angle_deg: 0 };
}

export function circleShape(id: string, cx: number, cy: number, d: number): CircleShape {
  return { kind: "circle", id, cx, cy, r: d / 2 };
}
