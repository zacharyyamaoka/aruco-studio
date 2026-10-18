import { describe, expect, it } from "vitest";
import { BENCH_FILL, BENCH_PX_PER_CELL, BENCH_RES, CALC0, SWEEP_TILTS, benchCamera, calcCamera, focalPx, loadCalc, readsTo, share } from "./bench";

describe("the bench camera", () => {
  it("puts BENCH_PX_PER_CELL on a small marker's cells", () => {
    const cam = benchCamera({ cell_mm: 5, outer_mm: [40, 40] });
    expect((5 * focalPx(cam.resolution[0], cam.hfov_deg)) / cam.distance_mm).toBeCloseTo(BENCH_PX_PER_CELL, 6);
  });
  it("sets back a big board until its outline fits", () => {
    const cam = benchCamera({ cell_mm: 2, outer_mm: [400, 300] });
    const px = (400 * focalPx(cam.resolution[0], cam.hfov_deg)) / cam.distance_mm;
    expect(px).toBeCloseTo(BENCH_FILL * Math.min(...BENCH_RES), 6);
  });
});

describe("the sweep", () => {
  it("tilts 0 to 85 in 5 degree steps", () => {
    expect(SWEEP_TILTS[0]).toBe(0);
    expect(SWEEP_TILTS[SWEEP_TILTS.length - 1]).toBe(85);
    expect(SWEEP_TILTS).toHaveLength(18);
  });
  it("reads to the last full read before the first miss", () => {
    expect(readsTo([0, 5, 10, 15], [1, 1, 0.5, 1])).toBe(5);
    expect(readsTo([0, 5, 10], [1, 1, 1])).toBe(10);
    expect(readsTo([0, 5, 10], [0.5, 1, 1])).toBeNull();
  });
  it("is not known until it reaches a miss or the end", () => {
    expect(readsTo([0, 5, 10], [1, 1, null])).toBeUndefined();
    expect(readsTo([0, 5, 10], [null, null, null])).toBeUndefined();
    expect(readsTo([0, 5, 10], [1, 0, null])).toBe(0);
  });
  it("counts the share of the marker's own ids", () => {
    expect(share(3, 1)).toBe(0.75);
    expect(share(0, 0)).toBe(0);
  });
});

describe("the calculator's camera", () => {
  it("is 16:9", () => {
    expect(calcCamera({ distance_mm: 300, width_px: 1920, hfov_deg: 70 })).toEqual({ distance_mm: 300, resolution: [1920, 1080], hfov_deg: 70 });
  });
  it("falls back to the defaults without storage", () => {
    expect(loadCalc()).toEqual(CALC0);
  });
});
