// A selected shape's handles (M8 §2.2) and what dragging one writes. Pure:
// a handle's place on the canvas, and the new shape dict for a pointer at
// p (canvas mm). Sizes snap to 0.5 mm, turns to 15° (Alt: no snap).
import type { Pt } from "../api/types";
import { snap, snapDeg } from "../model/design";
import { applyXf, invert, kindOf, outline, turn, xfOf, type Xf } from "../model/shapes";

export interface Handle { id: string; at: Pt; kind: "size" | "rot" | "vertex" | "rim" }

const ROT_GAP = 8;   // mm past the top edge

function bbox(pts: Pt[]) {
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  return { x0: Math.min(...xs), y0: Math.min(...ys), x1: Math.max(...xs), y1: Math.max(...ys) };
}

/** The handles of a shape whose frame on the canvas is `xf`. */
export function handlesOf(shape: any, xf: Xf, zoom = 4): Handle[] {
  const k = kindOf(shape);
  const out: Handle[] = [];
  const at = (p: Pt) => applyXf(xf, p);
  const pts = outline(shape);
  if (!pts.length) return out;
  const b = bbox(pts);
  if (k === "rect") {
    const [w, h] = shape.rect.map(Number);
    const W = w / 2, H = h / 2;
    const spots: [string, Pt][] = [["sw", [-W, -H]], ["s", [0, -H]], ["se", [W, -H]], ["e", [W, 0]],
      ["ne", [W, H]], ["n", [0, H]], ["nw", [-W, H]], ["w", [-W, 0]]];
    for (const [id, p] of spots) out.push({ id, at: at(p), kind: "size" });
  } else if (k === "circle") {
    out.push({ id: "rim", at: at([Number(shape.circle) / 2, 0]), kind: "rim" });
  } else if (k === "polygon") {
    (shape.polygon as number[][]).forEach((p, i) => out.push({ id: `v${i}`, at: at([p[0], p[1]]), kind: "vertex" }));
  } else if (k === "slot") {
    const [L, Wd] = shape.slot.map(Number);
    out.push({ id: "end0", at: at([-L / 2, 0]), kind: "size" });
    out.push({ id: "end1", at: at([L / 2, 0]), kind: "size" });
    out.push({ id: "width", at: at([0, Wd / 2]), kind: "size" });
  }
  out.push({ id: "rot", at: at([0, b.y1 + Math.max(ROT_GAP, 24 / Math.max(zoom, 0.1))]), kind: "rot" });
  return out;
}

const r6 = (v: number) => Math.round(v * 1e6) / 1e6;

/** The shape after its handle `id` is dragged to p (canvas mm). `xf` is the
 *  shape's frame on the canvas, `parentXf` the frame its at / rot are in.
 *  -> the new dict (a copy), or null when nothing changes. */
export function dragHandle(shape: any, xf: Xf, parentXf: Xf, id: string, p: Pt, free = false): any | null {
  const k = kindOf(shape);
  const s = (v: number) => (free ? r6(v) : snap(v));
  const local = applyXf(invert(xf), p);
  const next = JSON.parse(JSON.stringify(shape));
  // a move of the centre by (dx, dy) in the shape's own frame
  const shift = (dx: number, dy: number) => {
    const [ox, oy] = xfOf(shape);
    const [mx, my] = turn(Number(shape.rot) || 0, [dx, dy]);
    const x = r6(ox + mx), y = r6(oy + my);
    if (!x && !y) delete next.at;
    else next.at = [x, y];
  };
  if (id === "rot") {
    const [cx, cy] = [xf[0], xf[1]];
    const deg = (Math.atan2(p[1] - cy, p[0] - cx) * 180) / Math.PI - 90 - parentXf[2];
    const r = free ? r6(deg) : snapDeg(deg);
    const norm = ((((r + 180) % 360) + 360) % 360) - 180;
    const v = norm === -180 ? 180 : norm;
    if (!v) delete next.rot;
    else next.rot = v;
    return (Number(shape.rot) || 0) === (Number(next.rot) || 0) ? null : next;
  }
  if (k === "rect") {
    const [w, h] = shape.rect.map(Number);
    let x0 = -w / 2, x1 = w / 2, y0 = -h / 2, y1 = h / 2;
    if (id.includes("e")) x1 = x0 + Math.max(0.5, s(local[0] - x0));
    if (id.includes("w")) x0 = x1 - Math.max(0.5, s(x1 - local[0]));
    if (id.includes("n")) y1 = y0 + Math.max(0.5, s(local[1] - y0));
    if (id.includes("s")) y0 = y1 - Math.max(0.5, s(y1 - local[1]));
    const nw = r6(x1 - x0), nh = r6(y1 - y0);
    if (nw === w && nh === h) return null;
    next.rect = [nw, nh];
    shift((x0 + x1) / 2, (y0 + y1) / 2);
    return next;
  }
  if (k === "circle" && id === "rim") {
    const d = Math.max(0.5, s(2 * Math.hypot(local[0], local[1])));
    if (d === Number(shape.circle)) return null;
    next.circle = d;
    return next;
  }
  if (k === "polygon" && id.startsWith("v")) {
    const i = Number(id.slice(1));
    const q: Pt = [s(local[0]), s(local[1])];
    const old = shape.polygon[i];
    if (old && old[0] === q[0] && old[1] === q[1]) return null;
    next.polygon[i] = q;
    return next;
  }
  if (k === "slot") {
    const [L, W] = shape.slot.map(Number);
    if (id === "width") {
      const nw = Math.max(0.5, s(2 * Math.abs(local[1])));
      if (nw === W || nw >= L) return null;
      next.slot = [L, nw];
      return next;
    }
    const a = -L / 2, b = L / 2;
    let na = a, nb = b;
    if (id === "end1") nb = a + Math.max(W + 0.5, s(local[0] - a));
    if (id === "end0") na = b - Math.max(W + 0.5, s(b - local[0]));
    const nl = r6(nb - na);
    if (nl === L) return null;
    next.slot = [nl, W];
    shift((na + nb) / 2, 0);
    return next;
  }
  return null;
}

/** A vertex added on the polygon edge nearest p (Alt+click): -> the dict. */
export function addVertex(shape: any, xf: Xf, p: Pt): any | null {
  if (kindOf(shape) !== "polygon") return null;
  const local = applyXf(invert(xf), p);
  const pts: Pt[] = shape.polygon.map((q: number[]) => [q[0], q[1]]);
  let best = -1, bd = Infinity;
  for (let i = 0; i < pts.length; i++) {
    const a = pts[i], b = pts[(i + 1) % pts.length];
    const dx = b[0] - a[0], dy = b[1] - a[1];
    const t = Math.max(0, Math.min(1, ((local[0] - a[0]) * dx + (local[1] - a[1]) * dy) / (dx * dx + dy * dy || 1)));
    const d = Math.hypot(a[0] + t * dx - local[0], a[1] + t * dy - local[1]);
    if (d < bd) { bd = d; best = i; }
  }
  const next = JSON.parse(JSON.stringify(shape));
  next.polygon.splice(best + 1, 0, [snap(local[0]), snap(local[1])]);
  return next;
}

/** A polygon without vertex i (it keeps three at least). */
export function removeVertex(shape: any, i: number): any | null {
  if (kindOf(shape) !== "polygon" || shape.polygon.length <= 3) return null;
  const next = JSON.parse(JSON.stringify(shape));
  next.polygon.splice(i, 1);
  return next;
}

/** A new shape from a drag on the canvas, a (start) to b (now), in mm:
 *  -> {shape, at, rot} or null when it is too small. Alt: from the centre;
 *  Shift: a square / the drag's own direction for a slot. */
export function shapeFromDrag(tool: "rect" | "circle" | "slot", a: Pt, b: Pt, opts: { centre?: boolean; square?: boolean; width?: number } = {}):
  { shape: any; at: Pt; rot: number } | null {
  const A: Pt = [snap(a[0]), snap(a[1])], B: Pt = [snap(b[0]), snap(b[1])];
  if (tool === "rect") {
    let w = Math.abs(B[0] - A[0]), h = Math.abs(B[1] - A[1]);
    if (opts.square) w = h = Math.max(w, h);
    let cx = (A[0] + B[0]) / 2, cy = (A[1] + B[1]) / 2;
    if (opts.centre) { w *= 2; h *= 2; cx = A[0]; cy = A[1]; }
    else if (opts.square) { cx = A[0] + Math.sign(B[0] - A[0] || 1) * w / 2; cy = A[1] + Math.sign(B[1] - A[1] || 1) * h / 2; }
    if (w < 0.5 || h < 0.5) return null;
    return { shape: { rect: [r6(w), r6(h)] }, at: [r6(cx), r6(cy)], rot: 0 };
  }
  if (tool === "circle") {
    const d = snap(Math.hypot(B[0] - A[0], B[1] - A[1]) * (opts.centre ? 2 : 1));
    if (d < 0.5) return null;
    const c: Pt = opts.centre ? A : [(A[0] + B[0]) / 2, (A[1] + B[1]) / 2];
    return { shape: { circle: d }, at: [r6(c[0]), r6(c[1])], rot: 0 };
  }
  const L = snap(Math.hypot(B[0] - A[0], B[1] - A[1]));
  const W = opts.width ?? Math.max(1, snap(L / 4));
  if (L <= W || L < 1) return null;
  let rot = (Math.atan2(B[1] - A[1], B[0] - A[0]) * 180) / Math.PI;
  rot = opts.square ? rot : snapDeg(rot);
  return { shape: { slot: [L, W] }, at: [r6((A[0] + B[0]) / 2), r6((A[1] + B[1]) / 2)], rot: rot || 0 };
}

/** "80 50", "80x50", "18" -> the numbers typed (null when not numbers). */
export function typedNumbers(text: string): number[] | null {
  const parts = text.trim().split(/[\s,x×*]+/).filter(Boolean);
  if (!parts.length) return null;
  const v = parts.map(Number);
  return v.every((x) => Number.isFinite(x)) ? v : null;
}
