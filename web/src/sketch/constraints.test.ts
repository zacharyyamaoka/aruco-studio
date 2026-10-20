import { describe, expect, it } from "vitest";
import {
  dimFromPicks, dimsAmong, lockedAxes, measure, refusal, renameDim, resizable, solve, typedValue, type SketchDim,
} from "./constraints";
import { circleShape, rectShape, type RectShape, type Shape } from "./model";

const shapes: Shape[] = [rectShape("a", 10, 10, 50, 40), rectShape("b", 70, 10, 90, 30), circleShape("c", 120, 20, 10)];
const rect = (ss: Shape[], id: string) => ss.find((s) => s.id === id) as RectShape;
const dim = (d: Omit<SketchDim, "at">): SketchDim => ({ at: [0, -10], ...d });

describe("sketch dimensions", () => {
  it("a W keeps the rectangle's centre; an H likewise", () => {
    const out = solve(shapes, [dim({ id: "w", kind: "w", shape: "a", value: 20 }), dim({ id: "h", kind: "h", shape: "a", value: 10 })]);
    expect(rect(out, "a")).toMatchObject({ cx: 30, w: 20, cy: 25, h: 10 });
  });

  it("a distance from the Y axis to a left edge moves the rectangle, keeping its size", () => {
    const d = dimFromPicks(shapes, [{ axis: "y" }, { shape: "a", at: "l" }], [20, 60], "d1");
    expect(d && "dim" in d && d.dim).toMatchObject({ kind: "x", value: 10 });
    const out = solve(shapes, [{ ...(d as { dim: SketchDim }).dim, value: 25 }]);
    expect(rect(out, "a")).toMatchObject({ cx: 45, w: 40 });
    expect(lockedAxes(out, [{ ...(d as { dim: SketchDim }).dim, value: 25 }], "a")).toEqual({ x: true, y: false });
  });

  it("a shape-to-shape distance propagates: move the reference and the dependent follows", () => {
    const d = dim({ id: "d", kind: "x", a: { shape: "a", at: "r" }, b: { shape: "b", at: "l" }, value: 20 });
    expect(measure(shapes, d)).toBe(20);
    const moved = shapes.map((s) => (s.id === "a" ? { ...s, cx: (s as RectShape).cx + 15 } : s));
    expect(rect(solve(moved, [d]), "b").cx).toBe(95);
  });

  it("a loop is refused, an over-dimensioned shape is refused", () => {
    const ab = dim({ id: "1", kind: "x", a: { shape: "a", at: "r" }, b: { shape: "b", at: "l" }, value: 20 });
    const ba = dim({ id: "2", kind: "x", a: { shape: "b", at: "r" }, b: { shape: "a", at: "l" }, value: -80 });
    expect(refusal(shapes, [ab], ba)).toMatch(/loop/);
    // along y the other way round is fine
    expect(refusal(shapes, [ab], { ...ba, kind: "y", a: { shape: "b", at: "t" }, b: { shape: "a", at: "b" } })).toBeNull();
    const w = dim({ id: "w", kind: "w", shape: "b", value: 20 });
    const r = dim({ id: "r", kind: "x", a: { axis: "y" }, b: { shape: "b", at: "r" }, value: 90 });
    expect(refusal(shapes, [ab, w], r)).toMatch(/fully/);
    expect(refusal(shapes, [ab], w)).toBeNull();
    expect(refusal(shapes, [w], w)).toMatch(/already/);
  });

  it("locks: a W'd rectangle's handles do not resize it on x; a left edge placed lets the right handle go", () => {
    const w = [dim({ id: "w", kind: "w", shape: "a", value: 40 })];
    expect(resizable(shapes, w, "a", "x", 1)).toBe(false);
    expect(resizable(shapes, w, "a", "y", 1)).toBe(true);
    const l = [dim({ id: "l", kind: "x", a: { axis: "y" }, b: { shape: "a", at: "l" }, value: 10 })];
    expect(resizable(shapes, l, "a", "x", 1)).toBe(true);
    expect(resizable(shapes, l, "a", "x", -1)).toBe(false);
  });

  it("two edges of one rectangle are its W; a circle's outline is its Ø; two centres measure along the placement's axis", () => {
    expect((dimFromPicks(shapes, [{ shape: "a", at: "l" }, { shape: "a", at: "r" }], [0, 0], "x") as { dim: SketchDim }).dim).toMatchObject({ kind: "w", value: 40 });
    const d = (dimFromPicks(shapes, [{ shape: "c", at: "o" }], [140, 40], "x") as { dim: SketchDim }).dim;
    expect(d).toMatchObject({ kind: "d", value: 10 });
    expect(rect(solve(shapes, [{ ...d, value: 30 }]), "c")).toMatchObject({ r: 15 });
    const above = (dimFromPicks(shapes, [{ shape: "a", at: "c" }, { shape: "b", at: "c" }], [55, 80], "x") as { dim: SketchDim }).dim;
    expect(above).toMatchObject({ kind: "x", value: 50 });
    const beside = (dimFromPicks(shapes, [{ shape: "a", at: "c" }, { shape: "b", at: "c" }], [150, 22], "x") as { dim: SketchDim }).dim;
    expect(beside).toMatchObject({ kind: "y", value: -5 });
    expect(typedValue(beside, 12)).toBe(-12);
  });

  it("a solved document is unchanged (the same array), and a copy takes only the dims among its shapes", () => {
    const ds = [dim({ id: "w", kind: "w", shape: "a", value: 40 }), dim({ id: "x", kind: "x", a: { axis: "y" }, b: { shape: "b", at: "l" }, value: 70 })];
    expect(solve(shapes, ds)).toBe(shapes);
    expect(dimsAmong(ds, ["a", "b"]).map((d) => d.id)).toEqual(["w"]);
    expect(renameDim(ds[0], "w2", { a: "a2" })).toEqual({ ...ds[0], id: "w2", shape: "a2" });
  });
});
