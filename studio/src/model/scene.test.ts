// M3.2: the store's reducers (add placement, move, select, toggle view,
// lock, history) and the SVG path builder for a polygon with holes.
import { describe, expect, it } from "vitest";
import type { SceneDoc, SceneTag } from "../api/types";
import { layerD, loopD, loopsD, poseOf, sceneZ, snap, svgMatrix, tagBox, topD } from "./geom";
import {
  docOf, duplicates, idsText, issuesFor, marqueeSelect, moveLocal, patchFor, placeNew, pushHistory,
  redoStep, rotateLocal, routeIssues, selectClick, setLocked, summaryLine, toggleView, undoStep,
} from "./scene";

function tag(name: string, x = 0, y = 0, w = 40, h = 40, ids = [0], extra: Partial<SceneTag> = {}): SceneTag {
  return {
    name, uid: `u-${name}`, x_mm: x, y_mm: y, rotation_deg: 0, pose: poseOf(x, y, 0), locked: false, hidden: false,
    spec: {
      schema: "arucostudio.tagspec/1", settings: { layout: "single" }, numbers: {}, name: "", key: name,
      target: { kind: "face", w_mm: w, h_mm: h, loops_mm: [], has_body: true, z_sign: 1, x_ref: null, body_mm: null, body_loops_mm: null, face_loops_mm: null, name: "" },
    },
    plan: { ok: true, ids, marker: { dictionary: "DICT_4X4_50" }, layers: [{ op: "add", z: [-0.6, 0] }, { op: "keep", z: [-88, 87] }] } as any,
    ...extra,
  };
}

function doc(tags: SceneTag[]): SceneDoc {
  return { schema: "arucostudio.scene/1", units: "mm", name: "t", tags, ledger: null, overrides: {}, presets_used: [] };
}

describe("selection", () => {
  it("click selects one, shift toggles, empty click clears", () => {
    expect(selectClick([], "a", false)).toEqual(["a"]);
    expect(selectClick(["a"], "b", false)).toEqual(["b"]);
    expect(selectClick(["a"], "b", true)).toEqual(["a", "b"]);
    expect(selectClick(["a", "b"], "a", true)).toEqual(["b"]);
    expect(selectClick(["a", "b"], null, false)).toEqual([]);
    expect(selectClick(["a", "b"], null, true)).toEqual(["a", "b"]);
  });
  it("marquee takes every visible tag it touches", () => {
    const ts = [tag("a", 0, 0), tag("b", 100, 0), tag("c", 200, 0, 40, 40, [0], { hidden: true })];
    expect(marqueeSelect(ts, { x0: -30, y0: -30, x1: 90, y1: 30 }, [], false)).toEqual(["a", "b"]);
    expect(marqueeSelect(ts, { x0: 150, y0: -30, x1: 300, y1: 30 }, [], false)).toEqual([]);
    expect(marqueeSelect(ts, { x0: 90, y0: -1, x1: 91, y1: 1 }, ["a"], true)).toEqual(["a", "b"]);
  });
});

describe("move, rotate, lock, view", () => {
  it("moves only the named tags, snapped to 0.5 mm", () => {
    const d = doc([tag("a"), tag("b", 50, 0)]);
    const m = moveLocal(d, ["a"], 10.26, -3.1);
    expect(m.tags[0].x_mm).toBe(10.5);
    expect(m.tags[0].y_mm).toBe(-3);
    expect(m.tags[1].x_mm).toBe(50);
    const from = moveLocal(m, ["a"], 1, 1, 0.5, { a: [0, 0] });
    expect([from.tags[0].x_mm, from.tags[0].y_mm]).toEqual([1, 1]);
    expect(d.tags[0].x_mm).toBe(0);                   // the input is never changed
  });
  it("rotates by 90 and keeps the angle in 0..360", () => {
    const d = doc([tag("a")]);
    expect(rotateLocal(d, ["a"], -90).tags[0].rotation_deg).toBe(270);
    expect(rotateLocal(rotateLocal(d, ["a"], 90), ["a"], 270).tags[0].rotation_deg).toBe(0);
  });
  it("locks and toggles the view", () => {
    const d = setLocked(doc([tag("a"), tag("b")]), ["b"], true);
    expect(d.tags.map((t) => t.locked)).toEqual([false, true]);
    expect(toggleView("2d")).toBe("3d");
    expect(toggleView(toggleView("2d"))).toBe("2d");
  });
  it("places a new tag right of everything, 10 mm apart", () => {
    expect(placeNew([], 40)).toEqual([0, 0]);
    expect(placeNew([tag("a", 0, 5)], 30)).toEqual([20 + 10 + 15, 5]);
  });
  it("snaps without a negative zero", () => {
    expect(Object.is(snap(-0.1), 0)).toBe(true);
    expect(snap(1.26)).toBe(1.5);
  });
});

describe("history", () => {
  it("undo restores the doc before, redo the doc after; a new change clears redo", () => {
    const a = doc([tag("a")]);
    const b = moveLocal(a, ["a"], 10, 0);
    let h = pushHistory({ undo: [], redo: [] }, a);
    const u = undoStep(h, b)!;
    expect(u[0].tags[0].x_mm).toBe(0);
    expect(u[0].tags[0].plan).toBeNull();            // the file's shape: no plans
    h = u[1];
    const r = redoStep(h, u[0])!;
    expect(r[0].tags[0].x_mm).toBe(10);
    expect(pushHistory(r[1], b).redo).toEqual([]);
    expect(undoStep({ undo: [], redo: [] }, a)).toBeNull();
    expect(docOf(a).tags[0].plan).toBeNull();
  });
});

describe("the SVG path builder", () => {
  it("draws a polygon with a hole as two closed subpaths", () => {
    const outer: [number, number][] = [[0, 0], [10, 0], [10, 10], [0, 10]];
    const hole: [number, number][] = [[3, 3], [3, 7], [7, 7], [7, 3]];
    expect(loopD(outer)).toBe("M0 0L10 0L10 10L0 10Z");
    const d = layerD({ polygons: [{ outer, holes: [hole] }] } as any);
    expect(d).toBe("M0 0L10 0L10 10L0 10ZM3 3L3 7L7 7L7 3Z");
    expect(d.match(/M/g)!.length).toBe(2);
    expect(loopsD([outer, hole])).toBe(d);
    expect(topD({ black: [[outer, hole]] }, "black")).toBe(d);
    expect(topD({}, "white")).toBe("");
    expect(loopD([[-0.00001, 1.23456789]] as any)).toBe("");
  });
  it("writes no negative zero and 4 decimals", () => {
    expect(loopD([[-0.00001, 0], [1.234567, 2]])).toBe("M0 0L1.2346 2Z");
  });
  it("maps a row-major 4x4 onto SVG's matrix()", () => {
    expect(svgMatrix(poseOf(5, 7, 90))).toBe("matrix(0 1 -1 0 5 7)");
  });
});

describe("boxes, z, ids, messages", () => {
  it("a tag's box follows its pose", () => {
    const b = tagBox({ ...tag("a", 100, 0, 40, 20), rotation_deg: 90 })!;
    expect([b.x0, b.y0, b.x1, b.y1]).toEqual([90, -20, 110, 20]);
  });
  it("the scene's z extent leaves out the trim's keep column", () => {
    expect(sceneZ([tag("a")])).toEqual([-0.6, 0]);
    expect(sceneZ([tag("a", 0, 0, 40, 40, [0], { hidden: true })])).toBeNull();
  });
  it("finds duplicate ids per family and writes id runs", () => {
    const d = duplicates([tag("a", 0, 0, 40, 40, [0, 1]), tag("b", 0, 0, 40, 40, [1, 2])], () => "aruco4x4");
    expect(d).toEqual({ "aruco4x4#1": ["a", "b"] });
    expect(idsText([0, 1, 2, 3])).toBe("0–3");
    expect(idsText([4])).toBe("4");
    expect(idsText([1, 5])).toBe("1, 5");
  });
  it("routes each Issue to the deepest field it names", () => {
    const issues = [
      { field: "numbers.size", level: "info" as const, text: "marker 20 mm" },
      { field: "settings.label.cap_mm", level: "error" as const, text: "no room" },
      { field: "settings.label", level: "info" as const, text: "a preview" },
      { field: "tag", level: "warn" as const, text: "general" },
    ];
    const r = routeIssues(issues, ["numbers.size", "settings.label.on", "settings.label.cap_mm"]);
    expect(r["numbers.size"].map((i) => i.text)).toEqual(["marker 20 mm"]);
    expect(r["settings.label.cap_mm"].map((i) => i.text)).toEqual(["no room"]);
    expect(r["settings.label.on"].map((i) => i.text)).toEqual(["a preview"]);
    expect(r["tag"].map((i) => i.text)).toEqual(["general"]);
    expect(issuesFor("settings.label", issues).length).toBe(2);
    const s = summaryLine(issues, (f) => f);
    expect(s.level).toBe("error");
    expect(s.text).toContain("2 issues");
    expect(summaryLine([issues[0]], (f) => f).level).toBe("ok");
  });
  it("turns a key path into the PATCH body the server merges", () => {
    const spec = { target: { w_mm: 40 }, settings: { trim: { rule: 1, axes: "x", margin_mm: 0, force: false } } };
    expect(patchFor("numbers.size", 20, spec)).toEqual({ numbers: { size: 20 } });
    expect(patchFor("settings.label.on", true, spec)).toEqual({ settings: { label: { on: true } } });
    expect(patchFor("settings.trim.margin_mm", 2, spec)).toEqual({ settings: { trim: { rule: 1, axes: "x", margin_mm: 2, force: false } } });
    expect(patchFor("target.w_mm", 50, spec)).toEqual({ target: { w_mm: 50 } });
    expect(patchFor("key", "k", spec)).toEqual({ key: "k" });
  });
});
