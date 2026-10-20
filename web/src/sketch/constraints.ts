// Sketch dimensions (D): Fusion's Sketch Dimension, driving, hand-rolled for
// the shapes the sketch draws (axis-aligned rectangles and circles). Pure:
// the store and the viewport call these; vitest covers them.
//
// A dimension is one linear equation on one shape's numbers along one axis:
// a rectangle's W (x1 - x0) or H, a circle's Ø, or a distance along x or y
// from a reference (an origin axis, or another shape's edge or centre) to the
// dependent's edge or centre. The reference drives the dependent, never the
// other way: solve() walks the shapes reference-first (one order per axis),
// so moving a reference moves what it dimensions, and a dimension that would
// close a loop is refused. A rectangle has two numbers per axis (its two
// edges), a circle one (its centre) and its radius: more dimensions than that
// on one shape are refused too.
//
// WHY hand-rolled (Zach, 2026-10-20 night: "I say we hand roll and if we run
// into issues we can fix them there"): rectangles and circles only. The stock
// part for real constraints (coincident, tangent, angles) is planegcs,
// FreeCAD's solver (docs/design/sketch_tools_survey.md).
//
// WHY locked (Fusion): a dimensioned number does not move by hand. A
// rectangle with a W keeps it under a handle drag; a shape whose position a
// distance sets does not move on that axis (lockedAxes, resizable).
import type { Vec2 } from "../core/contract";
import type { Shape } from "./model";

export type Axis = "x" | "y";

/** A picked reference: a rectangle's edge (l r b t) or centre (c), a circle's
 *  centre (c) or outline (o, for its Ø), or an origin axis. `{ axis: "y" }` is
 *  the Y axis (the line x = 0): a distance along x can start there. */
export type DimRef =
  | { shape: string; at: "l" | "r" | "b" | "t" | "c" | "o" }
  | { axis: Axis };

export interface SketchDim {
  id: string;
  /** w / h: a rectangle's width / height; d: a circle's diameter; x / y: the
   *  distance along x / y from `a` (the reference) to `b` (the dependent) */
  kind: "w" | "h" | "d" | "x" | "y";
  /** w, h, d: the shape measured */
  shape?: string;
  /** x, y: the reference and the dependent (always a shape's edge or centre) */
  a?: DimRef;
  b?: DimRef;
  /** w, h, d: the size (mm, > 0); x, y: coord(b) - coord(a), signed, so the
   *  dependent keeps the side it was on */
  value: number;
  /** where it was placed: the value's offset from the dependent shape's centre (mm) */
  at: Vec2;
}

const r6 = (v: number) => { const r = +v.toFixed(6); return Object.is(r, -0) ? 0 : r; };

/** The shape a dimension sizes or places. */
export function dependent(d: SketchDim): string {
  return d.shape ?? (d.b && "shape" in d.b ? d.b.shape : "");
}

/** Every shape a dimension names. */
export function dimShapes(d: SketchDim): string[] {
  const ids = [d.shape, d.a && "shape" in d.a ? d.a.shape : undefined, d.b && "shape" in d.b ? d.b.shape : undefined];
  return ids.filter((x): x is string => !!x);
}

/** The axes a reference has a coordinate on. */
export function refAxes(ref: DimRef): Axis[] {
  if ("axis" in ref) return [ref.axis === "y" ? "x" : "y"];
  if (ref.at === "l" || ref.at === "r") return ["x"];
  if (ref.at === "b" || ref.at === "t") return ["y"];
  return ref.at === "c" ? ["x", "y"] : [];
}

/** A shape's extent along an axis: its low and high edge and its centre. */
function span(s: Shape, axis: Axis): { lo: number; hi: number; c: number } | null {
  if (s.kind === "rect") {
    const c = axis === "x" ? s.cx : s.cy, h = (axis === "x" ? s.w : s.h) / 2;
    return { lo: c - h, hi: c + h, c };
  }
  if (s.kind === "circle") {
    const c = axis === "x" ? s.cx : s.cy;
    return { lo: c - s.r, hi: c + s.r, c };
  }
  return null;
}

/** Which of a shape's numbers a reference names along an axis. */
function refPart(ref: DimRef, axis: Axis): "lo" | "hi" | "c" | null {
  if ("axis" in ref || !refAxes(ref).includes(axis)) return null;
  if (ref.at === "l" || ref.at === "b") return "lo";
  if (ref.at === "r" || ref.at === "t") return "hi";
  return "c";
}

/** A reference's coordinate along an axis (null: it has none there). */
export function refCoord(shapes: Shape[], ref: DimRef, axis: Axis): number | null {
  if ("axis" in ref) return refAxes(ref)[0] === axis ? 0 : null;
  const s = shapes.find((x) => x.id === ref.shape);
  const part = refPart(ref, axis);
  const sp = s && span(s, axis);
  return sp && part ? sp[part] : null;
}

/** What a dimension measures on the shapes now (x / y: signed). null: a shape it names is gone. */
export function measure(shapes: Shape[], d: SketchDim): number | null {
  if (d.kind === "x" || d.kind === "y") {
    const a = refCoord(shapes, d.a!, d.kind), b = refCoord(shapes, d.b!, d.kind);
    return a === null || b === null ? null : r6(b - a);
  }
  const s = shapes.find((x) => x.id === d.shape);
  if (!s) return null;
  if (d.kind === "d") return s.kind === "circle" ? r6(2 * s.r) : null;
  if (s.kind !== "rect") return null;
  return d.kind === "w" ? s.w : s.h;
}

// ------------------------------------------------------------ the equations

type Row = { part: "size" | "lo" | "hi" | "c"; v: number; dim: string };

/** The dimensions on one shape along one axis, each as (part = v), the
 *  references' coordinates read from `shapes`. */
function rows(shapes: Shape[], dims: SketchDim[], id: string, axis: Axis): Row[] {
  const out: Row[] = [];
  for (const d of dims) {
    if ((d.kind === "w" && axis === "x") || (d.kind === "h" && axis === "y")) {
      if (d.shape === id) out.push({ part: "size", v: d.value, dim: d.id });
    } else if (d.kind === axis && d.b && "shape" in d.b && d.b.shape === id) {
      const a = refCoord(shapes, d.a!, axis), part = refPart(d.b, axis);
      if (a !== null && part) out.push({ part, v: a + d.value, dim: d.id });
    }
  }
  return out;
}

/** (lo, hi) coefficients of each part's equation. */
const COEF: Record<Row["part"], [number, number]> = { size: [-1, 1], lo: [1, 0], hi: [0, 1], c: [0.5, 0.5] };

/** One shape with its rows along an axis satisfied, moving as little as
 *  the rows leave free: a size alone keeps the centre (as the old W × H box
 *  did), a position alone keeps the size. */
function applyRows(s: Shape, axis: Axis, rs: Row[]): Shape {
  const sp = span(s, axis);
  if (!sp || !rs.length) return s;
  if (s.kind === "circle") {
    const c = rs.find((r) => r.part === "c");
    return c ? (axis === "x" ? { ...s, cx: r6(c.v) } : { ...s, cy: r6(c.v) }) : s;
  }
  if (s.kind !== "rect") return s;
  let lo = sp.lo, hi = sp.hi;
  if (rs.length === 1) {
    const r = rs[0];
    if (r.part === "size") { lo = sp.c - r.v / 2; hi = sp.c + r.v / 2; }
    else { const t = r.v - sp[r.part]; lo += t; hi += t; }
  } else {
    const [[a1, b1], [a2, b2]] = [COEF[rs[0].part], COEF[rs[1].part]];
    const det = a1 * b2 - a2 * b1;
    if (Math.abs(det) < 1e-9) return applyRows(s, axis, rs.slice(0, 1));
    lo = (rs[0].v * b2 - rs[1].v * b1) / det;
    hi = (a1 * rs[1].v - a2 * rs[0].v) / det;
  }
  const c = r6((lo + hi) / 2), size = r6(hi - lo);
  return axis === "x" ? { ...s, cx: c, w: size } : { ...s, cy: c, h: size };
}

/** The shapes along one axis, references before what they dimension
 *  (Kahn's order; a loop, which canAdd refuses, keeps the document's order). */
function order(shapes: Shape[], dims: SketchDim[], axis: Axis): string[] {
  const ids = shapes.map((s) => s.id);
  const into = new Map<string, number>(ids.map((id) => [id, 0]));
  const out = new Map<string, string[]>();
  for (const d of dims) {
    if (d.kind !== axis || !d.a || !("shape" in d.a) || !d.b || !("shape" in d.b)) continue;
    if (!into.has(d.a.shape) || !into.has(d.b.shape)) continue;
    out.set(d.a.shape, [...(out.get(d.a.shape) ?? []), d.b.shape]);
    into.set(d.b.shape, into.get(d.b.shape)! + 1);
  }
  const done: string[] = [];
  const ready = ids.filter((id) => !into.get(id));
  while (ready.length) {
    const id = ready.shift()!;
    done.push(id);
    for (const n of out.get(id) ?? []) {
      into.set(n, into.get(n)! - 1);
      if (!into.get(n)) ready.push(n);
    }
  }
  return [...done, ...ids.filter((id) => !done.includes(id))];
}

/** The shapes with every dimension satisfied, references first. The same
 *  array when nothing moves (so a document that already agrees is unchanged). */
export function solve(shapes: Shape[], dims: SketchDim[]): Shape[] {
  if (!dims.length) return shapes;
  const byId = new Map(shapes.map((s) => [s.id, s]));
  for (const d of dims) {
    const s = d.kind === "d" ? byId.get(d.shape!) : undefined;
    if (s?.kind === "circle" && Math.abs(2 * s.r - d.value) > 1e-9) byId.set(s.id, { ...s, r: r6(d.value / 2) });
  }
  for (const axis of ["x", "y"] as Axis[]) {
    for (const id of order(shapes, dims, axis)) {
      const s = byId.get(id)!;
      const rs = rows([...byId.values()], dims, id, axis);
      if (rs.length) byId.set(id, applyRows(s, axis, rs));
    }
  }
  const next = shapes.map((s) => byId.get(s.id)!);
  return next.every((s, i) => JSON.stringify(s) === JSON.stringify(shapes[i])) ? shapes : next;
}

// ------------------------------------------------------------ the locks

/** The axes a shape's position is dimensioned on: it does not move there by hand. */
export function lockedAxes(shapes: Shape[], dims: SketchDim[], id: string): Record<Axis, boolean> {
  const pos = (axis: Axis) => rows(shapes, dims, id, axis).some((r) => r.part !== "size");
  return { x: pos("x"), y: pos("y") };
}

/** Whether a handle may move a rectangle's `side` (-1 low, +1 high) along an
 *  axis: not when its size is dimensioned, nor when that edge (or its centre)
 *  is placed by one. */
export function resizable(shapes: Shape[], dims: SketchDim[], id: string, axis: Axis, side: -1 | 1): boolean {
  const parts = rows(shapes, dims, id, axis).map((r) => r.part);
  if (!parts.length) return true;
  return parts.length === 1 && parts[0] === (side > 0 ? "lo" : "hi");
}

/** Whether a circle's Ø is dimensioned. */
export function diameterLocked(dims: SketchDim[], id: string): boolean {
  return dims.some((d) => d.kind === "d" && d.shape === id);
}

// ------------------------------------------------------------ adding one

/** Why a new dimension cannot be added (null: it can): its shapes are gone,
 *  it would close a loop, or its shape has no number left to dimension. */
export function refusal(shapes: Shape[], dims: SketchDim[], d: SketchDim): string | null {
  const id = dependent(d);
  const s = shapes.find((x) => x.id === id);
  if (!s || dimShapes(d).some((x) => !shapes.some((y) => y.id === x))) return "That shape is gone.";
  if (s.kind === "rect" && s.angle_deg !== 0) return "A turned rectangle cannot be dimensioned here.";
  if (d.kind === "d") return diameterLocked(dims, id) ? "That circle's Ø is already dimensioned." : null;
  const axis: Axis = d.kind === "w" || d.kind === "x" ? "x" : "y";
  if ((d.kind === "x" || d.kind === "y") && d.a && "shape" in d.a) {
    // a loop: the dependent already drives the reference, through any chain
    const seen = new Set<string>();
    const walk = (from: string): boolean => {
      if (from === (d.a as { shape: string }).shape) return true;
      if (seen.has(from)) return false;
      seen.add(from);
      return dims.some((e) => e.kind === axis && e.a && "shape" in e.a && e.a.shape === from && walk(dependent(e)));
    };
    if (walk(id)) return "That dimension would make a loop: one of these shapes already drives the other.";
  }
  const have = rows(shapes, dims, id, axis).map((r) => r.part);
  const part = d.kind === "w" || d.kind === "h" ? "size" : refPart(d.b!, axis);
  if (!part) return "Those can't be dimensioned along that axis.";
  const room = s.kind === "rect" ? 2 : part === "c" ? 1 : 0;
  if (have.includes(part)) return "That is already dimensioned.";
  if (have.length >= room) return "That shape is fully dimensioned: delete one of its dimensions first.";
  if (have.length === 1) {
    const [a1, b1] = COEF[have[0]], [a2, b2] = COEF[part];
    if (Math.abs(a1 * b2 - a2 * b1) < 1e-9) return "That is already dimensioned.";
  }
  return null;
}

/** The dimension that picks (one or two references) make, placed at `place`
 *  (a sketch point), its value what the shapes measure now. An error says
 *  why those picks make none. */
export function dimFromPicks(shapes: Shape[], picks: DimRef[], place: Vec2, id: string): { dim: SketchDim } | { error: string } | null {
  const shapeOf = (r: DimRef) => ("shape" in r ? shapes.find((s) => s.id === r.shape) : undefined);
  const centre = (s: Shape): Vec2 => (s.kind === "poly" ? [0, 0] : [s.cx, s.cy]);
  const make = (kind: SketchDim["kind"], dep: Shape, rest: Partial<SketchDim>): { dim: SketchDim } | { error: string } => {
    const c = centre(dep);
    const dim: SketchDim = { id, kind, value: 0, at: [r6(place[0] - c[0]), r6(place[1] - c[1])], ...rest };
    const v = measure(shapes, dim);
    if (v === null) return { error: "That shape is gone." };
    return { dim: { ...dim, value: v } };
  };
  if (picks.length === 1) {
    const p = picks[0];
    const s = shapeOf(p);
    if (!s || !("shape" in p)) return null;
    if (s.kind === "circle" && p.at === "o") return make("d", s, { shape: s.id });
    if (s.kind === "rect" && (p.at === "b" || p.at === "t")) return make("w", s, { shape: s.id });
    if (s.kind === "rect" && (p.at === "l" || p.at === "r")) return make("h", s, { shape: s.id });
    return null;   // a centre or an axis: waits for a second pick
  }
  if (picks.length !== 2) return null;
  let [a, b] = picks;
  if ("axis" in b) [a, b] = [b, a];
  if ("axis" in b) return { error: "Pick a shape's edge or centre: two axes have no distance." };
  const sb = shapeOf(b)!;
  if ("shape" in a && a.shape === b.shape) {
    // two edges of one rectangle: its W or H
    const ends = [a.at, b.at].sort().join("");
    if (sb.kind === "rect" && ends === "lr") return make("w", sb, { shape: sb.id });
    if (sb.kind === "rect" && ends === "bt") return make("h", sb, { shape: sb.id });
    return { error: "Pick another shape, or that shape's opposite edge." };
  }
  if (a && "shape" in a && a.at === "o") a = { shape: a.shape, at: "c" };
  if (b.at === "o") b = { shape: b.shape, at: "c" };
  const both = refAxes(a).filter((x) => refAxes(b).includes(x));
  if (!both.length) return { error: "Pick a parallel edge, a centre or an origin axis." };
  let axis = both[0];
  if (both.length === 2) {
    // two centres: placed above or below them it measures along x, beside them along y (Fusion)
    const ca = "axis" in a ? [0, 0] : centre(shapeOf(a)!), cb = centre(sb);
    const mid = [(ca[0] + cb[0]) / 2, (ca[1] + cb[1]) / 2];
    axis = Math.abs(place[1] - mid[1]) >= Math.abs(place[0] - mid[0]) ? "x" : "y";
  }
  return make(axis, sb, { a, b });
}

/** A dimension's new value typed as a size (> 0): a distance keeps its side. */
export function typedValue(d: SketchDim, typed: number): number {
  if (d.kind === "x" || d.kind === "y") return r6((d.value < 0 ? -1 : 1) * Math.abs(typed));
  return r6(Math.abs(typed));
}

/** The dimensions among a set of shapes (each names only them, and no axis): what a copy takes. */
export function dimsAmong(dims: SketchDim[], ids: string[]): SketchDim[] {
  return dims.filter((d) => {
    const refs = [d.a, d.b].filter((r): r is DimRef => !!r);
    return !refs.some((r) => "axis" in r) && dimShapes(d).every((x) => ids.includes(x));
  });
}

/** A dimension with its shapes renamed (a paste). */
export function renameDim(d: SketchDim, id: string, map: Record<string, string>): SketchDim {
  const ref = (r: DimRef): DimRef => ("shape" in r ? { ...r, shape: map[r.shape] ?? r.shape } : r);
  return {
    ...d, id, ...(d.shape ? { shape: map[d.shape] ?? d.shape } : {}), ...(d.a ? { a: ref(d.a) } : {}), ...(d.b ? { b: ref(d.b) } : {}),
  };
}
