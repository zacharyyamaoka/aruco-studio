import { describe, expect, it } from "vitest";
import type { IdResult, MarkerPlan, Preset } from "../core/contract";
import { rectShape } from "../sketch/model";
import { MIXED, applyBatch, batchRows, batchSummary, growForStart, idRuns, readingFeatures, reIdDoc, reIdItems, resetBatch, type BatchRow } from "./batch";
import { emptyDoc, isSet, newFeature, rectProfile, setField, type Feature } from "./doc";

const inkjet: Preset = { id: "builtin:ink", name: "Ink", method: "inkjet", builtin: true, page: "A4", page_mm: [210, 297], dpi: 600, thickness_mm: 0.1 };
const print3d: Preset = { id: "builtin:3d", name: "3D", method: "print3d", builtin: true, nozzle_mm: 0.4, line_mm: 0.42, layer_mm: 0.2 };

const single = (n: number, p: Preset = inkjet): Feature => ({ ...newFeature(rectProfile(`r${n}`), `f${n}`, p), marker: { ...newFeature(null).marker, first_id: n } });
const typed = (f: Feature, type: "grid" | "charuco"): Feature => setField(f, "marker.type", type);
const row = (rows: BatchRow[], path: string) => rows.find((r) => r.path === path);
const plan = (ids: number[], marker_mm: number): MarkerPlan => ({ ids, marker_mm } as unknown as MarkerPlan);

describe("batchRows: which rows a batch may set", () => {
  const singles = Array.from({ length: 8 }, (_, i) => single(i));
  const board = typed(single(8), "charuco");

  it("8 singles + 1 ChArUco: the per-marker rows are editable, identity and geometry are not, a board's own rows are hidden", () => {
    const rows = batchRows([...singles, board], { rect: () => true });
    for (const p of ["preset", "marker.dictionary", "marker.marker_mm", "marker.turn", "marker.quiet_modules", "marker.corner_mark",
      "label.on", "marker.size_step", "trim", "extrude.paper_mm", "marker.flip"]) {
      expect(row(rows, p), p).toMatchObject({ editable: true, ids: [...singles, board].map((f) => f.id) });
    }
    for (const p of ["profile", "marker.type", "marker.first_id", "feature.key", "marker.suggest", "profile.angle_deg"]) {
      const r = row(rows, p)!;
      expect(r.editable, p).toBe(false);
      expect(r.reason, p).toBeTruthy();
    }
    expect(row(rows, "marker.first_id")!.reason).toMatch(/Re-ID/);
    // a type mix: Columns × Rows, Checker, Origin are hidden
    for (const p of ["marker.cols", "marker.checker_mm", "marker.origin_square", "marker.separation_mm"]) expect(row(rows, p), p).toBeUndefined();
    // the types differ, the ids too
    expect(row(rows, "marker.type")!.value).toBe(MIXED);
    expect(row(rows, "marker.first_id")!.value).toBe(MIXED);
    // the same everywhere: one value, driven
    expect(row(rows, "marker.dictionary")).toMatchObject({ value: "DICT_4X4_50", driven: true });
    expect(row(rows, "marker.corner_mark")).toMatchObject({ value: "none", driven: true });
  });

  it("all singles: no board rows; a value set on some is Mixed, driven Mixed", () => {
    const some = singles.map((f, i) => (i < 3 ? setField(f, "marker.corner_mark", "triangle") : f));
    const rows = batchRows(some);
    expect(row(rows, "marker.cols")).toBeUndefined();
    expect(row(rows, "marker.corner_mark")).toMatchObject({ value: MIXED, driven: MIXED });
    expect(row(rows, "profile.angle_deg")).toBeUndefined();
    // the marker size: the plans' driven sizes, one value when they agree
    const plans = Object.fromEntries(singles.map((f) => [f.id, plan([f.marker.first_id], 28)]));
    expect(row(batchRows(singles, { plans }), "marker.marker_mm")).toMatchObject({ value: 28, driven: true });
    plans.f0 = plan([0], 30);
    expect(row(batchRows(singles, { plans }), "marker.marker_mm")!.value).toBe(MIXED);
  });

  it("all grids, or all ChArUco: the board's rows are shown, read-only", () => {
    const grids = [typed(single(0), "grid"), typed(single(1), "grid")];
    const rows = batchRows(grids);
    expect(row(rows, "marker.cols")).toMatchObject({ editable: false });
    expect(row(rows, "marker.separation_mm")).toMatchObject({ editable: false });
    expect(row(rows, "marker.checker_mm")).toBeUndefined();
    const boards = batchRows([typed(single(0), "charuco"), typed(single(1), "charuco")]);
    expect(row(boards, "marker.checker_mm")).toMatchObject({ editable: false });
    expect(row(boards, "marker.origin_square")).toMatchObject({ editable: false });
    expect(row(boards, "marker.separation_mm")).toBeUndefined();
  });

  it("a row applies to the features that have it: the label's rows to those whose label is on, heights by method", () => {
    const a = setField(single(0), "label.on", true), b = single(1), c = setField(single(2, print3d), "label.on", true);
    const rows = batchRows([a, b, c]);
    expect(row(rows, "label.on")).toMatchObject({ value: MIXED, ids: ["f0", "f1", "f2"] });
    expect(row(rows, "label.text")).toMatchObject({ editable: true, value: "#{ids}", ids: ["f0", "f2"] });
    expect(row(rows, "label.offset_mm")).toMatchObject({ editable: false, ids: ["f0", "f2"] });
    expect(row(rows, "extrude.paper_mm")!.ids).toEqual(["f0", "f1"]);
    expect(row(rows, "extrude.white_mm")!.ids).toEqual(["f2"]);
    // inkjet and 3D print: the size step is not one kind
    expect(row(rows, "marker.size_step")).toMatchObject({ editable: false });
    expect(row(rows, "preset")!.value).toBe(MIXED);
  });

  it("Holes only where a profile has holes", () => {
    const face: Feature = { ...single(0), profile: { outer: "p", holes: ["h"] } };
    expect(row(batchRows([face, single(1)]), "holes")).toMatchObject({ editable: true, ids: ["f0"], value: "avoid" });
    expect(row(batchRows([single(0), single(1)]), "holes")).toBeUndefined();
  });
});

describe("applying a batch row", () => {
  it("sets and resets through doc.ts per feature", () => {
    const f = applyBatch(single(0), "marker.marker_mm", 20);
    expect(f.marker).toMatchObject({ marker_mm: 20, auto: false });
    expect(isSet(resetBatch(f, "marker.marker_mm"), "marker.marker_mm")).toBe(false);
    expect(applyBatch(single(0), "holes", "ignore").holes).toBe("ignore");
    expect(applyBatch(single(0), "preset", print3d).preset).toBe(print3d);
    expect(applyBatch(single(0), "marker.corner_mark", "triangle").marker.corner_mark).toBe("triangle");
  });
});

describe("the summary line", () => {
  it("counts, the dictionary or Mixed, the ids as runs", () => {
    const fs = [single(0), single(1), single(2), typed(single(3), "charuco")];
    const plans = { f0: plan([0], 28), f1: plan([1], 28), f2: plan([2], 28), f3: plan([3, 4, 5, 6, 7, 8, 9, 10, 11, 12], 18) };
    expect(batchSummary(fs, plans)).toBe("4 markers · 4X4_50 · ids #0–12");
    fs[1] = setField(fs[1], "marker.dictionary", "DICT_5X5_50");
    expect(batchSummary(fs, plans)).toBe("4 markers · Mixed · ids #0–12");
    expect(idRuns([5, 0, 1, 2, 9, 10])).toBe("#0–2, 5, 9–10");
  });
});

describe("Re-ID of a selection", () => {
  // three 10 mm squares in a row, left to right, made in another order (f2, f0, f1)
  const shapes = [rectShape("r0", 0, 0, 10, 10), rectShape("r1", 20, 0, 30, 10), rectShape("r2", 40, 0, 50, 10)];
  const doc = { ...emptyDoc("t", shapes), features: [single(2), single(0), single(1)], id_ledger: { f0: 0, f1: 1, f2: 2 } };
  const ids = (items: { key: string }[]) => items.map((i) => i.key);

  it("asks in reading order, holding the features outside the selection at their ids, as typed", () => {
    const items = reIdItems(doc, ["f1"]);
    expect(ids(items)).toEqual(["f0", "f1", "f2"]);
    expect(items.map((i) => i.first_id)).toEqual([0, null, 2]);
    expect(reIdItems(doc, null).map((i) => i.first_id)).toEqual([null, null, null]);
  });

  it("a typed id: kept by default, renumbered with keepTyped false", () => {
    const t = { ...doc, features: doc.features.map((f) => (f.id === "f0" ? setField(f, "marker.first_id", 30) : f)) };
    expect(reIdItems(t, ["f0", "f1"]).find((i) => i.key === "f0")!.first_id).toBe(30);
    expect(reIdItems(t, ["f0", "f1"], false).find((i) => i.key === "f0")!.first_id).toBeNull();
    // the core's answer for f0, f1 from 100: f0 is driven at 100 now, with its ledger entry
    const res: IdResult = { items: [
      { key: "f0", first_id: 100, ids: [100], driven: true }, { key: "f1", first_id: 101, ids: [101], driven: true },
      { key: "f2", first_id: 2, ids: [2], driven: false }], ledger: { f0: 100, f1: 101 }, warnings: [] };
    const out = reIdDoc(t, ["f0", "f1"], res, false);
    const f0 = out.doc.features.find((f) => f.id === "f0")!;
    expect(isSet(f0, "marker.first_id")).toBe(false);
    expect(f0.marker.first_id).toBe(100);
    expect(out.doc.features.find((f) => f.id === "f1")!.marker.first_id).toBe(101);
    expect(out.doc.id_ledger).toEqual({ f0: 100, f1: 101, f2: 2 });
    // the answer comes back in document order (applyIds reads it by index)
    expect(ids(out.res.items)).toEqual(["f2", "f0", "f1"]);
  });

  it("keeps the document's ledger for the rest, the answer's for the selection", () => {
    const res: IdResult = { items: [{ key: "f1", first_id: 7, ids: [7], driven: true }], ledger: { f1: 7 }, warnings: [] };
    expect(reIdDoc(doc, ["f1"], res).doc.id_ledger).toEqual({ f0: 0, f1: 7, f2: 2 });
    // the whole document: the answer's ledger alone
    expect(reIdDoc(doc, null, { ...res, ledger: { f0: 5, f1: 6, f2: 7 } }).doc.id_ledger).toEqual({ f0: 5, f1: 6, f2: 7 });
  });

  it("reads rows top to bottom (the sketch's y is up), each left to right", () => {
    // two rows of three; the second marker of the top row sits 3 mm lower
    const grid = [rectShape("a", 40, 20, 50, 30), rectShape("b", 0, 20, 10, 30), rectShape("c", 20, 17, 30, 27),
      rectShape("d", 20, 0, 30, 10), rectShape("e", 40, 0, 50, 10), rectShape("f", 0, 0, 10, 10)];
    const fs = grid.map((sh, i) => ({ ...newFeature(rectProfile(sh.id), `g${i}`, inkjet), marker: { ...newFeature(null).marker, first_id: i } }));
    const d = { ...emptyDoc("g", grid), features: fs, id_ledger: {} };
    expect(readingFeatures(d).map((f) => f.profile!.outer)).toEqual(["b", "c", "a", "f", "d", "e"]);
    expect(readingFeatures(d, ["g3", "g0"]).map((f) => f.profile!.outer)).toEqual(["a", "d"]);
  });

  it("Re-ID from a start past the dictionary: its markers grow to the smallest of their bit size that holds the ids", () => {
    // three DICT_4X4_50 singles (0..49): from 20 they fit, from 100 they need DICT_4X4_250
    expect(growForStart(doc, null, 20)).toEqual({ doc, grown: [] });
    const g = growForStart(doc, null, 100);
    expect(g.grown).toEqual([["DICT_4X4_50", "DICT_4X4_250"]]);
    expect(g.doc.features.map((f) => f.marker.dictionary)).toEqual(["DICT_4X4_250", "DICT_4X4_250", "DICT_4X4_250"]);
    // 47 + three ids reach 49: still fits; 48 + three reach 50: DICT_4X4_100
    expect(growForStart(doc, null, 47).grown).toEqual([]);
    expect(growForStart(doc, null, 48).grown).toEqual([["DICT_4X4_50", "DICT_4X4_100"]]);
    // only the selection grows; a held id at or past the start pushes the numbering on
    const one = growForStart(doc, ["f1"], 49);
    expect(one.doc.features.map((f) => f.marker.dictionary)).toEqual(["DICT_4X4_50", "DICT_4X4_50", "DICT_4X4_50"]);
    const held = { ...doc, features: doc.features.map((f) => (f.id === "f2" ? { ...f, marker: { ...f.marker, first_id: 49 } } : f)) };
    expect(growForStart(held, ["f1"], 49).grown).toEqual([["DICT_4X4_50", "DICT_4X4_100"]]);
    // past DICT_4X4_1000 nothing bigger exists: left for the core's wrap warning
    expect(growForStart(doc, null, 2000).grown).toEqual([]);
  });
});

