import { describe, expect, it } from "vitest";
import type * as THREE from "three";
import type { Polygon } from "../core/contract";
import { carved } from "./carve";

const sq = (x0: number, y0: number, x1: number, y1: number, holes: Polygon["holes"] = []): Polygon =>
  ({ outer: [[x0, y0], [x1, y0], [x1, y1], [x0, y1]], holes });

/** The area of the geometry's flat faces at height z facing up (+1) or down (-1), mm². */
function capArea(geo: THREE.BufferGeometry, z: number, facing: 1 | -1): number {
  const p = geo.getAttribute("position");
  let area = 0;
  for (let i = 0; i < p.count; i += 3) {
    const [a, b, c] = [i, i + 1, i + 2].map((k) => [p.getX(k), p.getY(k), p.getZ(k)]);
    if (![a, b, c].every((v) => Math.abs(v[2] - z) < 1e-6)) continue;
    const nz = ((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) / 2;
    if (Math.sign(nz) === facing) area += Math.abs(nz);
  }
  return area;
}

describe("carved: a body less the pockets cut into it", () => {
  // inkjet's numbers: paper [0, 0.1], the ink's pocket the top half
  const paper = [sq(0, 0, 10, 10)];

  it("a pocket is a hole in the outer face, the full underside stays", () => {
    const g = carved(paper, 0, 0.1, [{ z: [0.05, 0.1], polygons: [sq(3, 3, 7, 7)] }]);
    expect(capArea(g, 0.1, 1)).toBeCloseTo(100 - 16, 6);
    expect(capArea(g, 0, -1)).toBeCloseTo(100, 6);
  });

  it("a pocket's own hole is the body again (an island), pockets touching at a corner both cut", () => {
    const island = carved(paper, 0, 0.1, [{ z: [0.05, 0.1], polygons: [sq(1, 1, 9, 9, [[[4, 4], [4, 6], [6, 6], [6, 4]]])] }]);
    expect(capArea(island, 0.1, 1)).toBeCloseTo(100 - 64 + 4, 6);
    const corner = carved(paper, 0, 0.1, [{ z: [0.05, 0.1], polygons: [sq(2, 2, 4, 4), sq(4, 4, 6, 6)] }]);
    expect(capArea(corner, 0.1, 1)).toBeCloseTo(100 - 8, 6);
  });

  it("flipped (z below the face): the pocket opens at the bottom", () => {
    const g = carved(paper, -0.1, 0, [{ z: [-0.1, -0.05], polygons: [sq(3, 3, 7, 7)] }]);
    expect(capArea(g, -0.1, -1)).toBeCloseTo(100 - 16, 6);
    expect(capArea(g, 0, 1)).toBeCloseTo(100, 6);
  });

  it("a cut across the body's edge is a notch in it", () => {
    const g = carved(paper, 0, 0.1, [{ z: [0.05, 0.1], polygons: [sq(8, 8, 12, 12)] }]);
    expect(capArea(g, 0.1, 1)).toBeCloseTo(100 - 4, 6);
    expect(capArea(g, 0, -1)).toBeCloseTo(100, 6);
    // the walls: the upper slab's outline (40 less the notch's 4 plus its 4) by 0.05, the lower's 40 by 0.05
    expect(wallArea(g)).toBeCloseTo(40 * 0.05 + 40 * 0.05, 6);
  });
});

/** The area of the geometry's vertical faces, mm². */
function wallArea(geo: THREE.BufferGeometry): number {
  const p = geo.getAttribute("position");
  let area = 0;
  for (let i = 0; i < p.count; i += 3) {
    const [a, b, c] = [i, i + 1, i + 2].map((k) => [p.getX(k), p.getY(k), p.getZ(k)]);
    const u = [b[0] - a[0], b[1] - a[1], b[2] - a[2]], v = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
    const n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]];
    if (Math.abs(n[2]) < 1e-12) area += Math.hypot(...n) / 2;
  }
  return area;
}

/** How many up-facing triangles at height z cover the point. */
function cover(geo: THREE.BufferGeometry, z: number, [x, y]: [number, number]): number {
  const p = geo.getAttribute("position");
  let n = 0;
  for (let i = 0; i < p.count; i += 3) {
    const v = [i, i + 1, i + 2].map((k) => [p.getX(k), p.getY(k), p.getZ(k)]);
    if (!v.every((q) => Math.abs(q[2] - z) < 1e-6)) continue;
    const d = (a: number[], b: number[]) => (b[0] - a[0]) * (y - a[1]) - (b[1] - a[1]) * (x - a[0]);
    if ([d(v[0], v[1]), d(v[1], v[2]), d(v[2], v[0])].every((q) => q > 0)) n++;
  }
  return n;
}

/** Every grid point (off the edges) covered once by the top where `want` says paper, never where it says ink. */
function expectTop(geo: THREE.BufferGeometry, z: number, box: [number, number, number, number], want: (p: [number, number]) => boolean) {
  const bad: string[] = [];
  for (let x = box[0] + 0.0731; x < box[2]; x += 0.25) {
    for (let y = box[1] + 0.0617; y < box[3]; y += 0.25) {
      const n = cover(geo, z, [x, y]);
      if (n !== (want([x, y]) ? 1 : 0)) bad.push(`${x.toFixed(2)},${y.toFixed(2)}: ${n}`);
    }
  }
  expect(bad.slice(0, 5)).toEqual([]);
}

describe("carved: cuts that touch (Zach 2026-10-21, the inkjet sheet's slivers)", () => {
  const inside = (polys: Polygon[], [x, y]: [number, number]) => polys.some((p) => {
    const xs = p.outer.map((q) => q[0]), ys = p.outer.map((q) => q[1]);
    return x > Math.min(...xs) && x < Math.max(...xs) && y > Math.min(...ys) && y < Math.max(...ys);
  });

  it("a marker's cells, sharing edges: the white's top is exactly the paper less them", () => {
    const cells = [sq(-3, 2, 3, 3), sq(-3, -3, 3, -2), sq(-3, -2, -2, 2), sq(2, -2, 3, 2), sq(-1, -1, 0, 0), sq(0, 0, 1, 1), sq(-2, 0, -1, 1)];
    const g = carved([sq(-5, -5, 5, 5)], 0, 0.1, [{ z: [0.05, 0.1], polygons: cells }]);
    expectTop(g, 0.1, [-5, -5, 5, 5], (p) => !inside(cells, p));
    expect(capArea(g, 0.1, 1)).toBeCloseTo(100 - 6 - 6 - 4 - 4 - 3, 6);
    expect(capArea(g, 0, -1)).toBeCloseTo(100, 6);
  });

  it("a ChArUco's squares, meeting at corners and at the sticker's edge: every one carved", () => {
    const squares = [sq(-18, 18, -6, 30), sq(6, 18, 18, 30), sq(-6, 6, 6, 18), sq(-18, -6, -6, 6), sq(6, -6, 18, 6), sq(-6, -18, 6, -6), sq(-18, -30, -6, -18), sq(6, -30, 18, -18)];
    const g = carved([sq(-20, -30, 20, 30)], 0, 0.1, [{ z: [0.05, 0.1], polygons: squares }]);
    expectTop(g, 0.1, [-20, -30, 20, 30], (p) => !inside(squares, p));
    expect(capArea(g, 0.1, 1)).toBeCloseTo(2400 - 8 * 144, 6);
  });

  it("a corner triangle and overlapping cuts: the union is taken out", () => {
    const tri: Polygon = { outer: [[0, 10], [0, 7], [3, 10]], holes: [] };
    const g = carved([sq(0, 0, 10, 10)], 0, 0.1, [{ z: [0.05, 0.1], polygons: [tri, sq(2, 2, 6, 6), sq(4, 4, 8, 8)] }]);
    expect(capArea(g, 0.1, 1)).toBeCloseTo(100 - 4.5 - 28, 6);
    expectTop(g, 0.1, [0, 0, 10, 10], ([x, y]) => !(x > 0 && y < 10 && y - x > 7) && !inside([sq(2, 2, 6, 6), sq(4, 4, 8, 8)], [x, y]));
  });
});
