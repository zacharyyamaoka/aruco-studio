// Drawing helpers. The app computes no tag geometry: every outline comes
// from a TagPlan, a Target or a plan's top view. What is here only turns
// those numbers into SVG path text and places them on the canvas (the
// scene's pose, a plan's pattern_in_target): display maths.
import type { Layer, Loop, Pt, SceneTag, Target, TopView } from "../api/types";

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

/** Loops (an outer and its holes, any number of pieces) as one path:
 *  drawn with fill-rule="evenodd" the holes stay open. */
export function loopsD(loops: Loop[]): string {
  return loops.map(loopD).join("");
}

/** A plan layer's polygons with holes ({outer, holes}) as one path. */
export function layerD(layer: Pick<Layer, "polygons">): string {
  return (layer.polygons || []).map((p) => loopD(p.outer as Loop) + (p.holes || []).map((h) => loopD(h as Loop)).join("")).join("");
}

/** The top view's polygons of one colour (each polygon = [outer, ...holes]). */
export function topD(top: TopView | undefined, colour: "body" | "white" | "black"): string {
  const polys = top?.[colour];
  if (!polys) return "";
  return polys.map((poly) => loopsD(poly)).join("");
}

/** [u0, v0, u1, v1] as a closed loop. */
export function rectLoop(r: number[]): Loop {
  const [u0, v0, u1, v1] = r;
  return [[u0, v0], [u1, v0], [u1, v1], [u0, v1]];
}

/** A target's outline: its loops, or its w x h box when it has none. */
export function targetLoops(t: Target): Loop[] {
  if (t.loops_mm && t.loops_mm.length) return t.loops_mm;
  return [rectLoop([-t.w_mm / 2, -t.h_mm / 2, t.w_mm / 2, t.h_mm / 2])];
}

/** A row-major 4x4 (mm) as SVG's matrix(a b c d e f) of its xy part. */
export function svgMatrix(m: number[]): string {
  return `matrix(${f(m[0])} ${f(m[4])} ${f(m[1])} ${f(m[5])} ${f(m[3])} ${f(m[7])})`;
}

/** The scene pose of a tag (scene/model.pose_of): x right, y up, turned
 *  by rotation_deg about +z. */
export function poseOf(x: number, y: number, rot: number): number[] {
  const a = (rot * Math.PI) / 180;
  let c = Math.cos(a), s = Math.sin(a);
  if (Math.abs(rot % 90) < 1e-12) { c = Math.round(c); s = Math.round(s); }
  return [c, -s, 0, x, s, c, 0, y, 0, 0, 1, 0, 0, 0, 0, 1];
}

export function matMul(a: number[], b: number[]): number[] {
  const out = new Array(16).fill(0);
  for (let r = 0; r < 4; r++)
    for (let c = 0; c < 4; c++) {
      let s = 0;
      for (let k = 0; k < 4; k++) s += a[r * 4 + k] * b[k * 4 + c];
      out[r * 4 + c] = s;
    }
  return out;
}

export function apply(m: number[], p: Pt): Pt {
  return [m[0] * p[0] + m[1] * p[1] + m[3], m[4] * p[0] + m[5] * p[1] + m[7]];
}

export interface Box { x0: number; y0: number; x1: number; y1: number }

export function boxOf(pts: Pt[]): Box | null {
  if (!pts.length) return null;
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const [x, y] of pts) {
    if (x < x0) x0 = x; if (x > x1) x1 = x;
    if (y < y0) y0 = y; if (y > y1) y1 = y;
  }
  return { x0, y0, x1, y1 };
}

export function unionBox(bs: (Box | null)[]): Box | null {
  const ok = bs.filter(Boolean) as Box[];
  if (!ok.length) return null;
  return {
    x0: Math.min(...ok.map((b) => b.x0)), y0: Math.min(...ok.map((b) => b.y0)),
    x1: Math.max(...ok.map((b) => b.x1)), y1: Math.max(...ok.map((b) => b.y1)),
  };
}

/** A scene tag's box in scene mm: its target outline, and its plan's
 *  layers when they hang off the target (a label strip, Build anyway). */
export function tagBox(t: Pick<SceneTag, "x_mm" | "y_mm" | "rotation_deg" | "spec" | "plan">): Box | null {
  const pose = poseOf(t.x_mm, t.y_mm, t.rotation_deg);
  const pts: Pt[] = [];
  for (const lp of targetLoops(t.spec.target)) for (const p of lp) pts.push(apply(pose, p));
  const pit = t.plan?.frames?.pattern_in_target;
  if (pit && t.plan?.guides) {
    const m = matMul(pose, pit);
    const g = t.plan.guides;
    for (const r of [g.sticker, g.tile].filter(Boolean) as number[][])
      for (const p of rectLoop(r)) pts.push(apply(m, p));
  }
  return boxOf(pts);
}

export function boxesTouch(a: Box, b: Box): boolean {
  return a.x0 <= b.x1 && b.x0 <= a.x1 && a.y0 <= b.y1 && b.y0 <= a.y1;
}

export function snap(v: number, step = 0.5): number {
  const r = Math.round(v / step) * step;
  return Object.is(r, -0) ? 0 : Math.round(r * 1e6) / 1e6;
}

/** The z extent of a plan (mm): its material layers (the trim's keep
 *  column is not material), the body under it, and its mesh. */
export function planZ(plan: { layers?: { op: string; z: [number, number] | number[] }[]; mesh?: { z: number[] }[] | null } | null | undefined,
  target?: Target): [number, number] | null {
  if (!plan) return null;
  let lo = Infinity, hi = -Infinity;
  for (const L of plan.layers || []) {
    if (L.op === "keep") continue;
    lo = Math.min(lo, L.z[0]); hi = Math.max(hi, L.z[1]);
  }
  for (const m of plan.mesh || []) { lo = Math.min(lo, m.z[0]); hi = Math.max(hi, m.z[1]); }
  if (target?.body_mm) { lo = Math.min(lo, target.body_mm.z0); hi = Math.max(hi, target.body_mm.z1); }
  return Number.isFinite(lo) ? [lo, hi] : null;
}

/** The scene's z extent (window.__studio.zRange). */
export function sceneZ(tags: Pick<SceneTag, "plan" | "spec" | "hidden">[]): [number, number] | null {
  let out: [number, number] | null = null;
  for (const t of tags) {
    if (t.hidden) continue;
    const z = planZ(t.plan, t.spec.target);
    if (!z) continue;
    out = out ? [Math.min(out[0], z[0]), Math.max(out[1], z[1])] : z;
  }
  return out;
}
