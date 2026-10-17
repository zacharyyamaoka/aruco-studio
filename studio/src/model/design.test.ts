// The design file in the Studio: its text written as the server writes it
// (so Undo restores bytes), the document's edits, the handles' numbers.
import { describe, expect, it } from "vitest";
import { dump, parse } from "./json";
import {
  addAruco, addHole, addShape, deleteShapes, deleteTag, duplicateShapes, extrude, findShape, moveShapes, newId,
  refOfShape, rotateShapes, shapesOf, snap, snapDeg, type Doc,
} from "./design";
import { faceNames, faceNet, outline } from "./shapes";
import { addVertex, dragHandle, handlesOf, removeVertex, shapeFromDrag, typedNumbers } from "../sketch/handles";

// what Python's json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n" gives
const PY = `{
 "features": [
  {
   "extrude": "plate",
   "height": 5.0,
   "id": "body"
  }
 ],
 "name": "plate · ü",
 "note": "a \\"quote\\"\\n",
 "schema": "arucostudio.scene/2",
 "sketches": [
  {
   "at": [
    -0.5,
    2
   ],
   "id": "sk",
   "shapes": [
    {
     "holes": [],
     "id": "plate",
     "rect": [
      80.0,
      50
     ]
    }
   ]
  }
 ],
 "x": {}
}
`;

describe("the file's text (model/json)", () => {
  it("reads and writes Python's text byte for byte, 5.0 stays 5.0", () => {
    const p = parse(PY);
    expect(p.value.sketches[0].shapes[0].rect).toEqual([80, 50]);
    expect(dump(p.value)).toBe(PY);
  });
  it("sorts keys and writes a new number without .0", () => {
    const p = parse(PY);
    p.value.features.push({ id: "tag", aruco: "body.top", layout: "single" });
    p.value.sketches[0].at = [3, 4.5];
    const t = dump(p.value);
    expect(t).toContain('"aruco": "body.top",\n   "id": "tag",\n   "layout": "single"');
    expect(t).toContain('"at": [\n    3,\n    4.5\n   ]');
    expect(t).toContain('"height": 5.0');                    // untouched: as typed
  });
  it("a changed number is written anew", () => {
    const p = parse(PY);
    p.value.features[0].height = 7;
    expect(dump(p.value)).toContain('"height": 7,');
  });
  it("keeps where each value is (lines) and says where a broken text breaks", () => {
    const p = parse(PY);
    expect(p.spans.get("sketches[0].shapes[0]")).toEqual({ line0: 20, line1: 27 });
    expect(p.spans.get("features[0]")).toEqual({ line0: 3, line1: 7 });
    expect(() => parse('{\n "a": [1,,2]\n}')).toThrow(/line 2 col 10/);
  });
});

const doc = (): Doc => ({ schema: "arucostudio.scene/2", name: "t", sketches: [], features: [] });

describe("the document's edits (model/design)", () => {
  it("R 80 50, H 18, E 5, A on the top: the plate", () => {
    const d = doc();
    const k = addShape(d, { rect: [80, 50] }, [0, 0]);
    expect(k).toBe("rect1");
    expect(addHole(d, k, { circle: 18 })).toBe("rect1/h0");
    expect(extrude(d, k, 5)).toBe("body1");
    expect(refOfShape(d, k)).toBe("body1.top");
    expect(addAruco(d, ["body1.top"])).toBe("tag1");
    expect(d).toEqual({
      schema: "arucostudio.scene/2", name: "t",
      sketches: [{ id: "sk1", shapes: [{ id: "rect1", rect: [80, 50], holes: [{ circle: 18 }] }] }],
      features: [{ id: "body1", extrude: "rect1", height: 5 }, { id: "tag1", aruco: "body1.top" }],
    });
    expect(extrude(d, k, 8)).toBe("body1");                   // E again: the height
    expect(d.features![0].height).toBe(8);
  });
  it("ids are unique across sketches, shapes and features", () => {
    const d = doc();
    addShape(d, { rect: [10, 10] }, [0, 0]);
    addShape(d, { circle: 10 }, [20, 0]);
    expect(newId(d, "sk")).toBe("sk3");
    expect(shapesOf(d).map((s) => s.key)).toEqual(["rect1", "circle1"]);
  });
  it("a move: a whole sketch moves its at; one of two shapes moves its own", () => {
    const d = doc();
    const a = addShape(d, { rect: [10, 10] }, [5, 5]);
    moveShapes(d, [a], 2, -1);
    expect(d.sketches![0].at).toEqual([7, 4]);
    d.sketches![0].shapes.push({ id: "b", circle: 4, at: [10, 0] });
    d.sketches![0].rot = 90;
    moveShapes(d, ["b"], 1, 0);                               // canvas +x is the sketch's -y
    expect(d.sketches![0].shapes[1].at).toEqual([10, -1]);
    expect(d.sketches![0].at).toEqual([7, 4]);
  });
  it("turns, deletes and copies", () => {
    const d = doc();
    const a = addShape(d, { rect: [120, 40] }, [0, 0]);
    extrude(d, a, 40);
    addAruco(d, ["body1.front", "body1.right", "body1.back", "body1.left"]);
    rotateShapes(d, [a], -90);
    expect(d.sketches![0].rot).toBe(-90);
    const copies = duplicateShapes(d, [a], 0, -60);
    expect(copies).toEqual(["rect2"]);
    expect(d.features!.map((f: any) => f.id)).toEqual(["body1", "tag1", "body2", "tag2"]);
    expect(d.features![3].aruco).toEqual(["body2.front", "body2.right", "body2.back", "body2.left"]);
    // a tag of the list out: its entry goes, the rest stay one feature
    deleteTag(d, { feature: 1, entry: 1 }, "tag1.right");
    expect(d.features![1].aruco).toEqual(["body1.front", "body1.back", "body1.left"]);
    // the shape out: its body and every reference to it go
    deleteShapes(d, [a]);
    expect(d.features!.map((f: any) => f.id)).toEqual(["body2", "tag2"]);
    expect(d.sketches!.map((s: any) => s.id)).toEqual(["sk2"]);
    expect(findShape(d, "rect2")?.xf).toEqual([0, -60, -90]);
  });
  it("the faces of an extrude and their net (plan/shapes' names and places)", () => {
    expect(faceNames({ rect: [120, 40] })).toEqual(["top", "bottom", "front", "right", "back", "left"]);
    expect(faceNames({ slot: [40, 12] })).toEqual(["top", "bottom", "side0", "side1"]);
    expect(faceNames({ circle: 50 })).toEqual(["top", "bottom"]);
    // the forearm's right side: hinged at x 60, unfolded outwards (+x), 40 wide
    const n = faceNet({ rect: [120, 40] }, 40, "right")!;
    expect(n.xf).toEqual([80, 0, 90]);
    expect([n.w, n.h]).toEqual([40, 40]);
    expect(faceNet({ rect: [120, 40] }, 40, "bottom")!.xf).toEqual([0, -80, 180]);
    expect(outline({ polygon: [[0, 0], [0, 10], [10, 0]] })).toEqual([[0, 0], [10, 0], [0, 10]]);
  });
});

describe("handles (sketch/handles)", () => {
  it("a rectangle's right edge: the width, the left edge stays", () => {
    const sh = { id: "r", rect: [40, 60] };
    const e = handlesOf(sh, [0, 0, 0]).find((h) => h.id === "e")!;
    expect(e.at).toEqual([20, 0]);
    const next = dragHandle(sh, [0, 0, 0], [0, 0, 0], "e", [30.2, 3], false);
    expect(next).toEqual({ id: "r", rect: [50, 60], at: [5, 0] });
  });
  it("a turned shape's corner, in its own frame", () => {
    const next = dragHandle({ rect: [10, 10], rot: 90 }, [0, 0, 90], [0, 0, 0], "ne", [-10, 10]);
    expect(next.rect).toEqual([15, 15]);
    expect(next.at).toEqual([-2.5, 2.5]);
  });
  it("a circle's rim, a slot's end, a polygon's point, the turn: 0.5 mm and 15°", () => {
    expect(dragHandle({ circle: 30 }, [75, 0, 0], [75, 0, 0], "rim", [95.1, 0]).circle).toBe(40);
    expect(dragHandle({ slot: [40, 12] }, [0, 0, 0], [0, 0, 0], "end1", [25.1, 0])).toEqual({ slot: [45, 12], at: [2.5, 0] });
    expect(dragHandle({ polygon: [[0, 0], [10, 0], [0, 10]] }, [0, 0, 0], [0, 0, 0], "v1", [12.3, -0.2]).polygon[1]).toEqual([12.5, 0]);
    expect(dragHandle({ rect: [10, 10] }, [0, 0, 0], [0, 0, 0], "rot", [-5, 8.66]).rot).toBe(30);
    expect(snapDeg(-187)).toBe(180);
    expect(snap(2.26)).toBe(2.5);
  });
  it("points added and removed; shapes from a drag; typed numbers", () => {
    const tri = { polygon: [[0, 0], [10, 0], [0, 10]] };
    expect(addVertex(tri, [0, 0, 0], [5, -0.2]).polygon).toEqual([[0, 0], [5, 0], [10, 0], [0, 10]]);
    expect(removeVertex(tri, 0)).toBeNull();
    expect(shapeFromDrag("rect", [0, 0], [20.2, -10.1])).toEqual({ shape: { rect: [20, 10] }, at: [10, -5], rot: 0 });
    expect(shapeFromDrag("circle", [60, 0], [90, 0])).toEqual({ shape: { circle: 30 }, at: [75, 0], rot: 0 });
    expect(typedNumbers("80 50")).toEqual([80, 50]);
    expect(typedNumbers("80x50")).toEqual([80, 50]);
    expect(typedNumbers("1.5")).toEqual([1.5]);
    expect(typedNumbers("a")).toBeNull();
  });
});
