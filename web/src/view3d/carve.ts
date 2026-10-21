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

/** Even-odd: is p inside the ring? */
function inRing(r: Vec2[], [x, y]: Vec2): boolean {
  let inside = false;
  for (let i = 0, j = r.length - 1; i < r.length; j = i++) {
    const [xi, yi] = r[i], [xj, yj] = r[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

/** A point just inside a ring (off its first edge's midpoint), never on a shared edge or corner. */
function inner(r: Vec2[]): Vec2 {
  const area = r.reduce((a, p, i) => { const q = r[(i + 1) % r.length]; return a + p[0] * q[1] - q[0] * p[1]; }, 0);
  const [a, b] = [r[0], r[1 % r.length]];
  const dx = b[0] - a[0], dy = b[1] - a[1], n = Math.hypot(dx, dy) || 1, k = (Math.sign(area) || 1) * 1e-4 / n;
  return [(a[0] + b[0]) / 2 - dy * k, (a[1] + b[1]) / 2 + dx * k];
}

const ringArea = (r: Vec2[]) => Math.abs(r.reduce((a, p, i) => { const q = r[(i + 1) % r.length]; return a + p[0] * q[1] - q[0] * p[1]; }, 0)) / 2;

/** `polys` less the cut polygons that lie inside them: each cut's outer a hole
 *  in the polygon (or island) holding it, each of its holes an island of the
 *  body again. A cut not wholly inside the body (a notch across its edge) is
 *  left out: the body is drawn whole there (as every body was before the
 *  carving, 2026-10-20). */
export function less(polys: Polygon[], cuts: Polygon[]): Polygon[] {
  const out: Polygon[] = polys.map((p) => ({ outer: p.outer, holes: [...p.holes] }));
  for (const c of [...cuts].sort((a, b) => ringArea(b.outer) - ringArea(a.outer))) {
    const at = inner(c.outer);
    const holder = out.filter((p) => inRing(p.outer, at) && !p.holes.some((h) => inRing(h, at)))
      .sort((a, b) => ringArea(a.outer) - ringArea(b.outer))[0];
    if (!holder || !c.outer.every((q) => inRing(holder.outer, q))) continue;
    holder.holes.push(c.outer);
    for (const h of c.holes) out.push({ outer: h, holes: [] });
  }
  return out;
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
    parts.push(solid(open.length ? less(polys, open) : polys, a, b));
  }
  const geo = mergeGeometries(parts);
  for (const p of parts) p.dispose();
  return geo ?? solid(polys, z0, z1);
}
