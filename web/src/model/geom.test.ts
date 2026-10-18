import { describe, expect, it } from "vitest";
import {
  boxOf, circleLoop, fitBox, frameOf, handlePoint, inLoop, inRect, loopArea, loopD, loopHitsRect, niceStep, rectCorners, rectFromCorners,
  resizeRect, snap, toScreen, toWorld, zoomAt,
} from "./geom";

describe("geometry", () => {
  it("snaps to 0.5 mm", () => {
    expect(snap(1.24)).toBe(1);
    expect(snap(1.26)).toBe(1.5);
    expect(snap(-0.2)).toBe(0);
  });
  it("a rectangle from two corners in any order", () => {
    expect(rectFromCorners([10.2, 5.1], [0.1, 20.3])).toEqual({ cx: 5, cy: 12.75, w: 10, h: 15.5, angle_deg: 0 });
  });
  it("rotated rectangles: corners, inside, handles", () => {
    const r = { cx: 0, cy: 0, w: 20, h: 10, angle_deg: 90 };
    const b = boxOf(rectCorners(r));
    expect([b.x0, b.x1, b.y0, b.y1].map((v) => +v.toFixed(6))).toEqual([-5, 5, -10, 10]);
    expect(inRect(r, [0, 9])).toBe(true);
    expect(inRect(r, [9, 0])).toBe(false);
    expect(handlePoint(r, "e").map((v) => +v.toFixed(6))).toEqual([0, 10]);
  });
  it("resizing from the west edge keeps the east edge", () => {
    const r = resizeRect({ cx: 10, cy: 0, w: 20, h: 10, angle_deg: 0 }, "w", [-4.9, 3]);
    expect(r.cx + r.w / 2).toBe(20);
    expect(r.cx - r.w / 2).toBe(-5);
    expect(r.h).toBe(10);
  });
  it("never resizes below the minimum", () => {
    const r = resizeRect({ cx: 0, cy: 0, w: 10, h: 10, angle_deg: 0 }, "e", [-30, 0]);
    expect(r.w).toBe(1);
  });
  it("loops: area sign, inside, path text", () => {
    const sq: [number, number][] = [[0, 0], [1, 0], [1, 1], [0, 1]];
    expect(loopArea(sq)).toBe(1);
    expect(loopArea([...sq].reverse())).toBe(-1);
    expect(inLoop(sq, [0.5, 0.5])).toBe(true);
    expect(loopD(sq)).toBe("M0 0L1 0L1 1L0 1Z");
    expect(loopArea(circleLoop(0, 0, 1, 64, true))).toBeLessThan(0);
  });
  it("a hole near a rectangle: hits only when it overlaps", () => {
    const hole = circleLoop(25, 55, 10, 96);
    expect(loopHitsRect(hole, { cx: 60, cy: 40, w: 49.9, h: 79.8, angle_deg: 0 })).toBe(false);
    expect(loopHitsRect(hole, { cx: 60, cy: 40, w: 60, h: 79.8, angle_deg: 0 })).toBe(true);
  });
  it("camera: world and screen are inverses; zoom keeps the point under the cursor", () => {
    const cam = { cx: 10, cy: 20, zoom: 4 };
    const s = toScreen(cam, 800, 600, [15, 25]);
    expect(s).toEqual([420, 280]);
    expect(toWorld(cam, 800, 600, s)).toEqual([15, 25]);
    const z = zoomAt(cam, 800, 600, s, 2);
    expect(toWorld(z, 800, 600, s).map((v) => +v.toFixed(9))).toEqual([15, 25]);
  });
  it("fit shows the box inside the margins", () => {
    const c = fitBox({ x0: 0, y0: 0, x1: 120, y1: 80 }, 800, 600, 50);
    expect(c.cx).toBe(60);
    expect(c.zoom).toBeCloseTo(Math.min(700 / 120, 500 / 80));
  });
  it("grid steps are at least 70 px apart", () => {
    expect(niceStep(4)).toBe(20);
    expect(niceStep(100)).toBe(1);
  });
  it("a 4x4's frame", () => {
    expect(frameOf([1, 0, 0, 5, 0, 1, 0, 6, 0, 0, 1, 0, 0, 0, 0, 1])).toEqual({ o: [5, 6], x: [1, 0], y: [0, 1] });
    expect(frameOf([])).toBeNull();
  });
});
