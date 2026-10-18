import { describe, expect, it } from "vitest";
import { loopArea } from "../model/geom";
import { EXAMPLES } from "./examples";
import {
  circleFrom, circleShape, contains, directChildren, edgeDistance, hitTest, moveShape, plainRect, profileAt, profileLoops,
  rectShape, resizeShape, sameProfile, shapeLoop, type Shape,
} from "./model";

const plate = EXAMPLES.find((e) => e.id === "plate")!.shapes;

describe("profiles", () => {
  it("a click on the plate's material is the plate minus its two holes", () => {
    const ref = profileAt(plate, [60, 40]);
    expect(ref).toEqual({ outer: "plate", holes: ["plate-h1", "plate-h2"] });
  });

  it("a click inside a hole is the hole's own profile", () => {
    expect(profileAt(plate, [25, 55])).toEqual({ outer: "plate-h1", holes: [] });
  });

  it("outside every shape there is no profile", () => {
    expect(profileAt(plate, [-10, -10])).toBeNull();
  });

  it("holes are the direct children only: a shape inside a hole is not the plate's hole", () => {
    const shapes: Shape[] = [rectShape("o", 0, 0, 100, 100), circleShape("h", 50, 50, 40), circleShape("hh", 50, 50, 10)];
    expect(directChildren(shapes, shapes[0]).map((s) => s.id)).toEqual(["h"]);
    expect(profileAt(shapes, [30, 50])).toEqual({ outer: "h", holes: ["hh"] });
    expect(profileAt(shapes, [5, 5])).toEqual({ outer: "o", holes: ["h"] });
  });

  it("a ring: a circle drawn inside a rectangle makes the rectangle's profile a ring", () => {
    const shapes: Shape[] = [rectShape("r", 0, 0, 80, 60), circleShape("c", 40, 30, 20)];
    const ref = profileAt(shapes, [5, 5])!;
    expect(ref).toEqual({ outer: "r", holes: ["c"] });
    const pr = profileLoops(shapes, ref)!;
    expect(pr.loops).toHaveLength(2);
    expect(loopArea(pr.loops[0])).toBeGreaterThan(0);   // outer counter-clockwise
    expect(loopArea(pr.loops[1])).toBeLessThan(0);      // hole clockwise
  });

  it("a plain rectangle profile is used as is, a rectangle with a hole is not", () => {
    const shapes: Shape[] = [rectShape("r", 0, 0, 80, 60)];
    expect(plainRect(shapes, profileAt(shapes, [5, 5])!)?.id).toBe("r");
    expect(plainRect(plate, profileAt(plate, [60, 40])!)).toBeNull();
  });

  it("containment needs every point inside and a smaller shape", () => {
    const a = rectShape("a", 0, 0, 10, 10), b = rectShape("b", 5, 5, 15, 15);
    expect(contains(a, b)).toBe(false);
    expect(contains(b, a)).toBe(false);
    expect(contains(a, a)).toBe(false);
  });

  it("sameProfile ignores hole order", () => {
    expect(sameProfile({ outer: "p", holes: ["a", "b"] }, { outer: "p", holes: ["b", "a"] })).toBe(true);
    expect(sameProfile({ outer: "p", holes: ["a"] }, { outer: "p", holes: [] })).toBe(false);
    expect(sameProfile(null, null)).toBe(true);
  });
});

describe("hit tests: edge picks the shape, inside picks the profile", () => {
  it("near the plate's edge picks the plate", () => {
    expect(hitTest(plate, [0.5, 40], 1)).toEqual({ kind: "edge", id: "plate" });
  });
  it("on a hole's rim picks the circle", () => {
    expect(hitTest(plate, [35.3, 55], 1)).toEqual({ kind: "edge", id: "plate-h1" });
  });
  it("inside the material picks the profile", () => {
    expect(hitTest(plate, [60, 40], 1)).toEqual({ kind: "region", ref: { outer: "plate", holes: ["plate-h1", "plate-h2"] } });
  });
  it("the tolerance is in mm: farther than it is not an edge", () => {
    expect(hitTest(plate, [2, 40], 1)?.kind).toBe("region");
  });
  it("edge distance of a circle is from its rim", () => {
    expect(edgeDistance(circleShape("c", 0, 0, 20), [13, 0])).toBeCloseTo(3);
  });
});

describe("edits snap to 0.5 mm", () => {
  it("move snaps the delta, keeping the shape's own offset", () => {
    const r = { ...rectShape("r", 0, 0, 10, 10), cx: 60.25 };
    expect((moveShape(r, 19.9, 0.2) as typeof r).cx).toBeCloseTo(80.25);
    expect((moveShape(r, 19.9, 0.2) as typeof r).cy).toBeCloseTo(5);
  });
  it("a polygon moves every vertex", () => {
    const p: Shape = { kind: "poly", id: "p", pts: [[0, 0], [10, 0], [0, 10]] };
    expect((moveShape(p, 5.2, -1.1) as typeof p).pts).toEqual([[5, -1], [15, -1], [5, 9]]);
  });
  it("a circle's handle sets its radius", () => {
    const c = circleShape("c", 0, 0, 10);
    expect((resizeShape(c, "e", [7.8, 0]) as typeof c).r).toBe(8);
  });
  it("a circle from its centre and a point", () => {
    expect(circleFrom([1.2, 0.1], [11.3, 0.1], "c")).toEqual({ kind: "circle", id: "c", cx: 1, cy: 0, r: 10 });
  });
  it("a rectangle's corner handle keeps the opposite corner", () => {
    const r = rectShape("r", 0, 0, 10, 10);
    const n = resizeShape(r, "ne", [20.2, 14.8]) as typeof r;
    expect([n.cx - n.w / 2, n.cy - n.h / 2, n.cx + n.w / 2, n.cy + n.h / 2]).toEqual([0, 0, 20, 15]);
  });
});

describe("the golden examples", () => {
  it("every example's shapes are closed loops, outers counter-clockwise", () => {
    for (const ex of EXAMPLES) for (const s of ex.shapes) {
      const loop = shapeLoop(s);
      expect(loop.length).toBeGreaterThanOrEqual(4);
      expect(loopArea(loop)).toBeGreaterThan(0);
    }
  });
  it("each face has its holes inside it", () => {
    for (const id of ["plate", "bracket", "disc", "forearm"]) {
      const ex = EXAMPLES.find((e) => e.id === id)!;
      const outer = ex.shapes[0];
      expect(directChildren(ex.shapes, outer).length, id).toBe(ex.shapes.length - 1);
    }
  });
});
