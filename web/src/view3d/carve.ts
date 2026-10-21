// The solids the 3D view draws (./View3D.tsx), from the plan's layers
// (MarkerPlan.layers): each body as its true solid, the pockets cut into it
// (a cut layer's `into`) taken out, so an inlay fills a real hole.
import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import type { Polygon, Vec2 } from "../core/contract";

/** One polygon set as an extruded solid from z0 to z1. */
export function solid(polys: Polygon[], z0: number, z1: number): THREE.BufferGeometry {
  const v = (p: Vec2) => new THREE.Vector2(p[0], p[1]);
  const shapes = polys.map((p) => {
    const sh = new THREE.Shape(p.outer.map(v));
    for (const h of p.holes) sh.holes.push(new THREE.Path(h.map(v)));
    return sh;
  });
  const geo = new THREE.ExtrudeGeometry(shapes, { depth: Math.max(1e-3, z1 - z0), bevelEnabled: false, curveSegments: 1 });
  geo.translate(0, 0, z0);
  return geo;
}

/** A pocket (or recess) a cut layer takes out of the body it names: its z range and polygons. */
export interface Cut { z: [number, number]; polygons: Polygon[] }

const EPS = 1e-6;

/** A ring edge left to right (never vertical), from a body ring (`cut` -1) or cut `cut`'s. */
interface Seg { a: Vec2; b: Vec2; cut: number }

/** y on the edge at x (its end's own y at either end). */
function yAt(s: Seg, x: number): number {
  if (x <= s.a[0]) return s.a[1];
  if (x >= s.b[0]) return s.b[1];
  return s.a[1] + ((s.b[1] - s.a[1]) * (x - s.a[0])) / (s.b[0] - s.a[0]);
}

/** Where two edges cross inside both (an x), or null. */
function crossX(s: Seg, t: Seg): number | null {
  const rx = s.b[0] - s.a[0], ry = s.b[1] - s.a[1], qx = t.b[0] - t.a[0], qy = t.b[1] - t.a[1];
  const den = rx * qy - ry * qx;
  if (Math.abs(den) < 1e-12) return null;
  const u = ((t.a[0] - s.a[0]) * qy - (t.a[1] - s.a[1]) * qx) / den, v = ((t.a[0] - s.a[0]) * ry - (t.a[1] - s.a[1]) * rx) / den;
  return u > 0 && u < 1 && v > 0 && v < 1 ? s.a[0] + u * rx : null;
}

/** `a` less `b` (both sorted, disjoint y intervals), pieces longer than EPS. */
function minus(a: [number, number][], b: [number, number][]): [number, number][] {
  const out: [number, number][] = [];
  for (const [lo0, hi] of a) {
    let lo = lo0;
    for (const [c, d] of b) {
      if (d <= lo || c >= hi) continue;
      if (c - lo > EPS) out.push([lo, c]);
      lo = Math.max(lo, d);
    }
    if (hi - lo > EPS) out.push([lo, hi]);
  }
  return out;
}

/** Touching intervals as one. */
function merged(iv: [number, number][]): [number, number][] {
  const out: [number, number][] = [];
  for (const [lo, hi] of iv) {
    const last = out[out.length - 1];
    if (last && lo - last[1] <= EPS) last[1] = Math.max(last[1], hi); else out.push([lo, hi]);
  }
  return out;
}

/** `polys` less every cut polygon, from z0 to z1, as a solid: a planar
 *  sweep in x cuts the region into trapezoids (the caps), its edges where
 *  inside meets outside are the walls. Whatever the cuts do -- touch each
 *  other along an edge or at a corner, overlap, run along or across the
 *  body's outline -- the region is exact: inside is the body's rings even-odd
 *  and no cut's.
 *
 *  WHY not holes in a THREE.Shape (Zach, 2026-10-21: "white and black not
 *  rendering properly ... you need to properly cut away the black shape from
 *  the white"): earcut wants holes that touch nothing, but a marker's cells
 *  share edges and a ChArUco's squares meet at corners and at the sticker's
 *  edge, so the white's top came out with slivers over the ink and the edge
 *  squares were left uncarved (the white fought the ink flush there). */
export function region(polys: Polygon[], cuts: Polygon[], z0: number, z1: number): THREE.BufferGeometry {
  const segs: Seg[] = [];
  const add = (r: Vec2[], cut: number) => r.forEach((p, i) => {
    const q = r[(i + 1) % r.length];
    if (Math.abs(q[0] - p[0]) > EPS) segs.push(p[0] < q[0] ? { a: p, b: q, cut } : { a: q, b: p, cut });
  });
  for (const p of polys) for (const r of [p.outer, ...p.holes]) add(r, -1);
  cuts.forEach((c, i) => { for (const r of [c.outer, ...c.holes]) add(r, i); });
  const all = [...polys, ...cuts].flatMap((p) => [p.outer, ...p.holes]).flat().map((p) => p[0]);
  for (let i = 0; i < segs.length; i++) {
    for (let j = i + 1; j < segs.length; j++) {
      if (segs[i].b[0] <= segs[j].a[0] || segs[j].b[0] <= segs[i].a[0]) continue;
      const x = crossX(segs[i], segs[j]);
      if (x !== null) all.push(x);
    }
  }
  const xs: number[] = [];
  for (const x of all.sort((a, b) => a - b)) if (!xs.length || x - xs[xs.length - 1] > EPS) xs.push(x);

  const pos: number[] = [];
  const tri = (p: number[], q: number[], r: number[]) => {
    if (Math.abs((q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])) + Math.abs(q[2] - p[2]) + Math.abs(r[2] - p[2]) < 1e-12) return;
    pos.push(...p, ...q, ...r);
  };
  /** a wall from p to q (outside on its right, seen from above) */
  const wall = (p: Vec2, q: Vec2) => {
    if (Math.hypot(q[0] - p[0], q[1] - p[1]) <= EPS) return;
    tri([p[0], p[1], z0], [q[0], q[1], z0], [q[0], q[1], z1]);
    tri([p[0], p[1], z0], [q[0], q[1], z1], [p[0], p[1], z1]);
  };
  let before: [number, number][] = [];          // the region's y intervals at the last strip's right side
  const cutOdd = new Uint8Array(cuts.length);
  for (let k = 0; k + 1 < xs.length; k++) {
    const [xa, xb] = [xs[k], xs[k + 1]];
    const on = segs.filter((s) => s.a[0] <= xa + EPS && s.b[0] >= xb - EPS)
      .map((s) => ({ s, ya: yAt(s, xa), yb: yAt(s, xb) }))
      .sort((p, q) => p.ya + p.yb - q.ya - q.yb);
    let body = false, inCut = 0;
    cutOdd.fill(0);
    const left: [number, number][] = [], right: [number, number][] = [];
    for (let i = 0; i < on.length;) {
      // the edges here (coincident ones together): what is below them, what above
      const below = body && inCut === 0;
      let j = i;
      for (; j < on.length && Math.abs(on[j].ya - on[i].ya) <= EPS && Math.abs(on[j].yb - on[i].yb) <= EPS; j++) {
        const c = on[j].s.cut;
        if (c < 0) body = !body;
        else { cutOdd[c] ^= 1; inCut += cutOdd[c] ? 1 : -1; }
      }
      const above = body && inCut === 0;
      const e = on[i];
      if (below !== above) {
        if (below) wall([xb, e.yb], [xa, e.ya]); else wall([xa, e.ya], [xb, e.yb]);
      }
      if (above && j < on.length) {
        const n = on[j];
        const A = [xa, e.ya, z1], B = [xb, e.yb, z1], C = [xb, n.yb, z1], D = [xa, n.ya, z1];
        tri(A, B, C); tri(A, C, D);
        const [a, b, c, d] = [A, B, C, D].map((v) => [v[0], v[1], z0]);
        tri(a, c, b); tri(a, d, c);
        left.push([e.ya, n.ya]);
        right.push([e.yb, n.yb]);
      }
      i = j;
    }
    // the walls on x = xa: where the region starts or stops across it
    const here = merged(left);
    for (const [lo, hi] of minus(before, here)) wall([xa, lo], [xa, hi]);
    for (const [lo, hi] of minus(here, before)) wall([xa, hi], [xa, lo]);
    before = merged(right);
  }
  const x1 = xs[xs.length - 1];
  for (const [lo, hi] of before) wall([x1, lo], [x1, hi]);

  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute("uv", new THREE.Float32BufferAttribute(new Array((pos.length / 3) * 2).fill(0), 2));
  geo.computeVertexNormals();
  return geo;
}

/** A body as its true solid: `polys` from z0 to z1 less every pocket cut into
 *  it, slab by slab between the pockets' depths, so an inlay fills a real hole.
 *
 *  WHY not depth offsets (Zach, 2026-10-20 night: "the aruco markers shouldn't
 *  be showing on the underside"): the black used to share the white's top face
 *  and won it by polygonOffset, but on 0.1 mm paper with the ink 0.05 mm into
 *  it that push is bigger than the paper, so from below the ink came through
 *  the paper's underside. With the pocket cut out nothing overlaps flush. */
export function carved(polys: Polygon[], z0: number, z1: number, cuts: Cut[]): THREE.BufferGeometry {
  const eps = 1e-6;
  const cs = cuts.map((c) => ({ z: [Math.max(z0, c.z[0]), Math.min(z1, c.z[1])] as [number, number], polygons: c.polygons }))
    .filter((c) => c.z[1] - c.z[0] > eps);
  if (!cs.length) return solid(polys, z0, z1);
  const zs = [...new Set([z0, z1, ...cs.flatMap((c) => c.z)])].sort((a, b) => a - b);
  const parts: THREE.BufferGeometry[] = [];
  for (let i = 0; i + 1 < zs.length; i++) {
    const [a, b] = [zs[i], zs[i + 1]];
    if (b - a <= eps) continue;
    const open = cs.filter((c) => c.z[0] <= a + eps && c.z[1] >= b - eps).flatMap((c) => c.polygons);
    parts.push(open.length ? region(polys, open, a, b) : solid(polys, a, b));
  }
  const geo = mergeGeometries(parts);
  for (const p of parts) p.dispose();
  return geo ?? solid(polys, z0, z1);
}
