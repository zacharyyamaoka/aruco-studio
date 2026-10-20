import { describe, expect, it } from "vitest";
import type { MarkerPlan, Preset } from "../core/contract";
import { newFeature, setField } from "../model/doc";
import { arrowsOf, heightsOf, snapHeight } from "./heights";

const sq = (a: number, b: number) => [{ outer: [[a, a], [b, a], [b, b], [a, b]] as [number, number][], holes: [] }];

/** The real core's layers for a 3D-print tile (web_api.cad_layers), white [0, w], black [w - k, w]. */
function tilePlan(w: number, k: number, flip = false, extrude?: MarkerPlan["extrude"]): MarkerPlan {
  const z = (lo: number, hi: number): [number, number] => (flip ? [-hi, -lo] : [lo, hi]);
  return {
    outer: [[0, 0], [30, 0], [30, 30], [0, 30]], extrude,
    layers: [
      { name: "tile", part: "tile", colour: "white", op: "add", z: z(0, w), polygons: sq(0, 30) },
      { name: "pocket", part: "pocket", colour: "none", op: "cut", z: z(w - k, w), polygons: sq(5, 25), into: "tile" },
      { name: "pattern", part: "pattern", colour: "black", op: "add", z: z(w - k, w), polygons: sq(5, 25) },
    ],
  } as unknown as MarkerPlan;
}

const PRUSA = { method: "print3d", layer_mm: 0.32, first_layer_mm: 0.2 } as Preset;

describe("heightsOf", () => {
  it("reads the heights off the layers when the core sends no extrude", () => {
    expect(heightsOf(tilePlan(2, 0.6), "print3d")).toEqual({ method: "print3d", mode: "both", white_mm: 2, black_mm: 0.6, paper_mm: 0, flipped: false });
    expect(heightsOf(tilePlan(2, 0.6, true), "print3d")).toMatchObject({ white_mm: 2, flipped: true });
  });
  it("black only goes into the face: out of it when its z sits above", () => {
    const black = (z: [number, number]) => ({ outer: [], layers: [{ name: "pattern", part: "pattern", colour: "black", op: "add", z, polygons: [] }] }) as unknown as MarkerPlan;
    expect(heightsOf(black([-0.6, 0]), "print3d")).toMatchObject({ mode: "black", black_mm: 0.6, flipped: false });
    expect(heightsOf(black([0, 0.6]), "print3d")).toMatchObject({ mode: "black", flipped: true });
  });
  it("takes MarkerPlan.extrude when the core sends it", () => {
    const e = { method: "print3d" as const, mode: "both" as const, white_mm: 1.8, black_mm: 0.52, paper_mm: 0, flipped: false, driven: [] };
    expect(heightsOf(tilePlan(2, 0.6, false, e), "print3d")).toMatchObject({ white_mm: 1.8, black_mm: 0.52 });
  });
});

describe("arrowsOf", () => {
  it("3D print: the white on its outer face, out; the black at its inner end, in, measured from that face", () => {
    const f = newFeature(null);
    const [w, k] = arrowsOf(f, tilePlan(2, 0.6), heightsOf(tilePlan(2, 0.6), "print3d")!);
    expect(w).toMatchObject({ key: "white_mm", value: 2, driven: true, at: [15, 15], z: 2, dir: 1, dim: { z0: 0, z1: 2 } });
    expect(k).toMatchObject({ key: "black_mm", value: 0.6, driven: true, dir: -1, dim: { z0: 2 } });
    expect(k.z).toBeCloseTo(1.4, 9);
  });
  it("a set value is shown (and placed) at once; Flip turns the arrows over", () => {
    const f = setField(newFeature(null), "extrude.white_mm", 2.4);
    const plan = tilePlan(2, 0.6, true);
    const [w, k] = arrowsOf(f, plan, heightsOf(plan, "print3d")!);
    expect(w).toMatchObject({ value: 2.4, driven: false, z: -2.4, dir: -1 });
    expect(k).toMatchObject({ dir: 1 });
    expect(k.z).toBeCloseTo(-1.8, 9);
  });
  it("inkjet: one arrow, the paper", () => {
    const plan = { outer: [[0, 0], [30, 0], [30, 30], [0, 30]], layers: [
      { name: "sticker", part: "sticker", colour: "white", op: "add", z: [0, 0.1], polygons: sq(0, 30) },
      { name: "ink", part: "ink", colour: "black", op: "add", z: [0.05, 0.1], polygons: sq(5, 25) },
    ] } as unknown as MarkerPlan;
    const arrows = arrowsOf(newFeature(null), plan, heightsOf(plan, "inkjet")!);
    expect(arrows.map((a) => [a.key, a.value, a.z])).toEqual([["paper_mm", 0.1, 0.1]]);
  });
});

describe("snapHeight", () => {
  it("whole layers when the preset has a layer height", () => {
    expect(snapHeight(1.9, PRUSA)).toBeCloseTo(1.8, 9);      // 0.2 + 5 × 0.32
    expect(snapHeight(0.6, PRUSA)).toBeCloseTo(0.52, 9);     // 0.2 + 1 × 0.32
    expect(snapHeight(0.01, PRUSA)).toBeCloseTo(0.2, 9);     // never under the first layer
  });
  it("0.05 mm without one; Shift is free", () => {
    expect(snapHeight(2.43, { method: "print3d", layer_mm: 0 } as Preset)).toBeCloseTo(2.45, 9);
    expect(snapHeight(0.01, null)).toBeCloseTo(0.05, 9);
    expect(snapHeight(2.4321, PRUSA, true)).toBeCloseTo(2.432, 9);
  });
});
