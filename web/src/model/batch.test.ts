import { describe, expect, it } from "vitest";
import type { IdResult, MarkerPlan, Preset } from "../core/contract";
import { rectShape } from "../sketch/model";
import { MIXED, applyBatch, batchRows, batchSummary, idRuns, reIdItems, reIdResult, resetBatch, type BatchRow } from "./batch";
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
  const doc = { ...emptyDoc("t", [rectShape("r0", 0, 0, 10, 10)]), features: [single(0), single(1), single(2)], id_ledger: { f0: 0, f1: 1, f2: 2 } };

  it("holds the features outside the selection at their ids, as typed", () => {
    const items = reIdItems(doc, ["f1"]);
    expect(items.map((i) => i.first_id)).toEqual([0, null, 2]);
    expect(reIdItems(doc, null).map((i) => i.first_id)).toEqual([null, null, null]);
  });

  it("keeps the document's ledger for the rest, the answer's for the selection", () => {
    const res: IdResult = { items: [], ledger: { f1: 7 }, warnings: [] };
    expect(reIdResult(doc, ["f1"], res).ledger).toEqual({ f0: 0, f1: 7, f2: 2 });
    expect(reIdResult(doc, null, res)).toBe(res);
  });
});
