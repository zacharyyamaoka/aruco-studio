// The design file's shapes, for DRAWING only (the 2D outline, the 3D prism,
// where a handle or a face sits). The loops the planner fits are the
// server's (plan/shapes.py strokes them at 0.05 mm); nothing here is sent to
// it. Same frames and names as plan/shapes.py and docs/FILE_FORMAT.md.
import type { Pt } from "../api/types";

export type Xf = [number, number, number];          // x, y (mm), rot (deg, CCW)
export const IDENT: Xf = [0, 0, 0];
export type ShapeKind = "rect" | "circle" | "polygon" | "slot" | "loops";
export const KINDS: ShapeKind[] = ["rect", "circle", "polygon", "slot", "loops"];
export const RECT_SIDES = ["front", "right", "back", "left"];

/** cos, sin exact at quarter turns (scene.pose_of's rule). */
export function cosSin(deg: number): [number, number] {
  const a = (deg * Math.PI) / 180;
  let c = Math.cos(a), s = Math.sin(a);
  if (Math.abs(deg % 90) < 1e-12) { c = Math.round(c); s = Math.round(s); }
  return [c + 0, s + 0];
}

/** a after b: b's frame placed in a's (scene/design.compose). */
export function compose(a: Xf, b: Xf): Xf {
  const [c, s] = cosSin(a[2]);
  return [a[0] + c * b[0] - s * b[1], a[1] + s * b[0] + c * b[1], a[2] + b[2]];
}

export function invert(a: Xf): Xf {
  const [c, s] = cosSin(-a[2]);
  return [-(c * a[0] - s * a[1]), -(s * a[0] + c * a[1]), -a[2]];
}

export function applyXf(xf: Xf, p: Pt): Pt {
  const [c, s] = cosSin(xf[2]);
  return [xf[0] + c * p[0] - s * p[1], xf[1] + s * p[0] + c * p[1]];
}

/** A vector turned by `deg` (no move). */
export function turn(deg: number, v: Pt): Pt {
  const [c, s] = cosSin(deg);
  return [c * v[0] - s * v[1], s * v[0] + c * v[1]];
}

export function xfOf(d: any): Xf {
  const at = Array.isArray(d?.at) ? d.at : [0, 0];
  return [Number(at[0]) || 0, Number(at[1]) || 0, Number(d?.rot) || 0];
}

export function kindOf(shape: any): ShapeKind | null {
  if (!shape || typeof shape !== "object") return null;
  const ks = KINDS.filter((k) => k in shape);
  return ks.length === 1 ? ks[0] : null;
}

function area2(pts: Pt[]): number {
  let a = 0;
  for (let i = 0; i < pts.length; i++) {
    const p = pts[(i + pts.length - 1) % pts.length], q = pts[i];
    a += p[0] * q[1] - q[0] * p[1];
  }
  return a;
}

/** n points on a circle of radius r at the 0.05 mm chord (core.faces' rule). */
export function circlePts(r: number, cx = 0, cy = 0, a0 = 0, a1 = 2 * Math.PI, closed = true): Pt[] {
  const chord = 0.05;
  const step = r > chord ? 2 * Math.acos(Math.max(-1, 1 - chord / r)) : Math.PI / 4;
  const n = Math.max(closed ? 12 : 4, Math.ceil(Math.abs(a1 - a0) / step));
  const out: Pt[] = [];
  const m = closed ? n : n + 1;
  for (let i = 0; i < m; i++) {
    const a = a0 + ((a1 - a0) * i) / n;
    out.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]);
  }
  return out;
}

/** The outer loop, counter-clockwise, in the shape's own frame; [] when the
 *  shape is not drawable (the server says why). */
export function outline(shape: any): Pt[] {
  const k = kindOf(shape);
  try {
    if (k === "rect") {
      const [w, h] = shape.rect.map(Number);
      if (!(w > 0 && h > 0)) return [];
      return [[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2], [-w / 2, h / 2]];
    }
    if (k === "circle") {
      const d = Number(shape.circle);
      return d > 0 ? circlePts(d / 2) : [];
    }
    if (k === "polygon") {
      const pts: Pt[] = shape.polygon.map((p: number[]) => [Number(p[0]), Number(p[1])]);
      if (pts.length < 3) return [];
      return area2(pts) < 0 ? [pts[0], ...pts.slice(1).reverse()] : pts;
    }
    if (k === "slot") {
      const [L, W] = shape.slot.map(Number);
      if (!(L > W && W > 0)) return [];
      const h = (L - W) / 2, r = W / 2;
      return [...circlePts(r, h, 0, -Math.PI / 2, Math.PI / 2, false), ...circlePts(r, -h, 0, Math.PI / 2, (3 * Math.PI) / 2, false)];
    }
    if (k === "loops") {
      const lp: Pt[] = (shape.loops[0] || []).map((p: number[]) => [Number(p[0]), Number(p[1])]);
      if (lp.length < 3) return [];
      return area2(lp) > 0 ? lp : [...lp].reverse();
    }
  } catch { /* drawn as nothing; the compile's issue says why */ }
  return [];
}

/** The holes, each a loop in the shape's frame (a `loops` shape's inner
 *  loops, then `holes` placed by their own at / rot). */
export function holeLoops(shape: any): Pt[][] {
  const out: Pt[][] = [];
  if (kindOf(shape) === "loops") {
    for (const lp of (shape.loops || []).slice(1)) out.push(lp.map((p: number[]) => [Number(p[0]), Number(p[1])]));
  }
  for (const h of Array.isArray(shape?.holes) ? shape.holes : []) {
    const xf = xfOf(h);
    out.push(outline(h).map((p) => applyXf(xf, p)));
  }
  return out;
}

/** The outer loop's straight edges, counter-clockwise: the side faces. */
export function edges(shape: any): [Pt, Pt][] {
  const k = kindOf(shape);
  if (k === "circle" || !k) return [];
  if (k === "slot") {
    const [L, W] = shape.slot.map(Number);
    const h = (L - W) / 2, r = W / 2;
    return [[[-h, -r], [h, -r]], [[h, r], [-h, r]]];
  }
  const pts = outline(shape);
  return pts.map((p, i) => [p, pts[(i + 1) % pts.length]] as [Pt, Pt]);
}

/** The faces of the shape's extrude, the way a file names them: a
 *  rectangle's sides by front / right / back / left, any other by side<i>. */
export function faceNames(shape: any): string[] {
  const n = edges(shape).length;
  const sides = kindOf(shape) === "rect" ? RECT_SIDES : Array.from({ length: n }, (_v, i) => `side${i}`);
  return ["top", "bottom", ...sides];
}

export function sideIndex(_shape: any, face: string): number {
  if (RECT_SIDES.includes(face)) return RECT_SIDES.indexOf(face);
  const m = /^side(\d+)$/.exec(face);
  return m ? Number(m[1]) : -1;
}

/** A face in the 2D net (plan/shapes.face_target's `net`): its w x h
 *  rectangle, centred at xf, in the shape's frame. */
export function faceNet(shape: any, height: number, face: string): { xf: Xf; w: number; h: number; hinge: [Pt, Pt] | null } | null {
  const th = Math.abs(height);
  const out = outline(shape);
  if (!out.length) return null;
  const xs = out.map((p) => p[0]), ys = out.map((p) => p[1]);
  const bw = Math.max(...xs) - Math.min(...xs), bh = Math.max(...ys) - Math.min(...ys);
  if (face === "top") return { xf: [0, 0, 0], w: bw, h: bh, hinge: null };
  if (face === "bottom") return { xf: [0, 2 * Math.min(...ys) - th, 180], w: bw, h: bh, hinge: null };
  const i = sideIndex(shape, face);
  const es = edges(shape);
  if (i < 0 || i >= es.length) return null;
  const [[x0, y0], [x1, y1]] = es[i];
  const len = Math.hypot(x1 - x0, y1 - y0);
  const dx = (x1 - x0) / len, dy = (y1 - y0) / len;
  const nx = dy, ny = -dx;
  let ang = (Math.atan2(dy, dx) * 180) / Math.PI;
  if (Math.abs(ang - Math.round(ang)) < 1e-9) ang = Math.round(ang);
  const mx = (x0 + x1) / 2, my = (y0 + y1) / 2;
  return { xf: [mx + (nx * th) / 2, my + (ny * th) / 2, ang], w: len, h: th, hinge: [[x0, y0], [x1, y1]] };
}

/** The rectangle [w, h] centred on xf as a loop. */
export function rectAt(xf: Xf, w: number, h: number): Pt[] {
  return ([[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2], [-w / 2, h / 2]] as Pt[]).map((p) => applyXf(xf, p));
}

export function inside(loop: Pt[], p: Pt): boolean {
  let hit = false;
  for (let i = 0, j = loop.length - 1; i < loop.length; j = i++) {
    const [x0, y0] = loop[j], [x1, y1] = loop[i];
    if ((y0 > p[1]) !== (y1 > p[1]) && x0 + ((p[1] - y0) * (x1 - x0)) / (y1 - y0) > p[0]) hit = !hit;
  }
  return hit;
}

export function centroid(loop: Pt[]): Pt {
  const xs = loop.map((p) => p[0]), ys = loop.map((p) => p[1]);
  return [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2];
}

/** The size words of a shape ("80 × 50", "⌀ 18", "slot 40 × 12"). */
export function sizeText(shape: any): string {
  const k = kindOf(shape);
  if (k === "rect") return `${shape.rect[0]} × ${shape.rect[1]}`;
  if (k === "circle") return `⌀ ${shape.circle}`;
  if (k === "slot") return `slot ${shape.slot[0]} × ${shape.slot[1]}`;
  if (k === "polygon") return `${shape.polygon.length} points`;
  if (k === "loops") return `${(shape.loops || []).length} loops`;
  return "?";
}
