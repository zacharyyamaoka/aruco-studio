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

  it("a cut across the body's edge is left out: the body is drawn whole", () => {
    const g = carved(paper, 0, 0.1, [{ z: [0.05, 0.1], polygons: [sq(8, 8, 12, 12)] }]);
    expect(capArea(g, 0.1, 1)).toBeCloseTo(100, 6);
  });
});
