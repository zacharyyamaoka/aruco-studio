import { describe, expect, it } from "vitest";
import type { Preset, Suggestion } from "../core/contract";
import { rectShape } from "../sketch/model";
import v1Fixture from "../../e2e/fixtures/v1-plate.arucostudio-web.json?raw";
import {
  DEFAULT_MARKER, addFeature, addShape, deleteShape, emptyDoc, featureNumber, featureOfRect, idCount, idItems, idRange, isSet, newFeature,
  nextTurn, parseDoc, pickSuggestion, planRequest, removeFeature, resetField, serialise, setField, setMarker, setType, sheetItems,
} from "./doc";

const preset: Preset = { id: "builtin:x", name: "X", method: "inkjet", builtin: true, page: "A4", page_mm: [210, 297] };

describe("the marker's numbers", () => {
  it("typing a size turns auto off; nothing else does", () => {
    expect(setMarker(DEFAULT_MARKER, "marker_mm", 50)).toMatchObject({ marker_mm: 50, auto: false });
    expect(setMarker(DEFAULT_MARKER, "first_id", 3).auto).toBe(true);
    expect(setMarker(DEFAULT_MARKER, "checker_mm", 6).auto).toBe(true);
  });
  it("switching type sets a grid's start and back", () => {
    const g = setType(DEFAULT_MARKER, "grid");
    expect(g).toMatchObject({ type: "grid", cols: 2, rows: 2, auto: true });
    expect(setType(g, "single")).toMatchObject({ cols: 1, rows: 1 });
    expect(setType(g, "charuco")).toMatchObject({ cols: 5, rows: 4, separation_mm: 0 });
    expect(setMarker(DEFAULT_MARKER, "type", "grid").cols).toBe(2);
  });
  it("turn steps by 90 and wraps", () => {
    expect(nextTurn(0)).toBe(90);
    expect(nextTurn(270)).toBe(0);
  });
  it("id ranges", () => {
    expect(idRange(DEFAULT_MARKER)).toBe("#0");
    expect(idRange({ ...DEFAULT_MARKER, type: "grid", cols: 3, rows: 2, first_id: 4 })).toBe("#4–9");
    expect(idRange(DEFAULT_MARKER, [7, 8, 9])).toBe("#7–9");
    expect(idCount({ ...DEFAULT_MARKER, type: "charuco", cols: 5, rows: 4 })).toBe(10);
  });
});

describe("driven vs set", () => {
  const f0 = newFeature("r1", null, "f1");

  it("a new feature is all driven", () => {
    for (const p of ["marker.marker_mm", "marker.checker_mm", "marker.separation_mm", "label.height_mm", "marker.first_id", "marker.cols",
      "marker.type", "marker.dictionary", "label.gap_mm", "label.side"]) {
      expect(isSet(f0, p), p).toBe(false);
    }
  });

  it("the encoded fields map onto the contract: auto, and 0", () => {
    const f = setField(setField(setField(f0, "marker.marker_mm", 12), "marker.separation_mm", 4), "label.height_mm", 3);
    expect(f.marker).toMatchObject({ auto: false, marker_mm: 12, separation_mm: 4 });
    expect(f.label.height_mm).toBe(3);
    expect(f.set).toEqual([]);
    expect(isSet(f, "marker.marker_mm") && isSet(f, "marker.separation_mm") && isSet(f, "label.height_mm")).toBe(true);
    const r = resetField(resetField(resetField(f, "marker.marker_mm"), "marker.separation_mm"), "label.height_mm");
    expect(r.marker).toMatchObject({ auto: true, marker_mm: 12, separation_mm: 0 });
    expect(r.label.height_mm).toBe(0);
    expect(isSet(r, "marker.marker_mm")).toBe(false);
  });

  it("the other fields are listed while set, and reset to the default", () => {
    const f = setField(setField(f0, "marker.first_id", 7), "label.gap_mm", 5);
    expect(f.set).toEqual(["marker.first_id", "label.gap_mm"]);
    expect(f.marker.first_id).toBe(7);
    expect(isSet(f, "marker.first_id")).toBe(true);
    const r = resetField(f, "marker.first_id");
    expect(r.marker.first_id).toBe(0);
    expect(r.set).toEqual(["label.gap_mm"]);
    expect(resetField(r, "label.gap_mm").label.gap_mm).toBe(2);
  });

  it("an edit to the same value as the driven one is still set", () => {
    expect(isSet(setField(f0, "marker.first_id", 0), "marker.first_id")).toBe(true);
  });

  it("a new type drives its counts again; a reset count is the type's default", () => {
    const g = setField(setField(f0, "marker.type", "grid"), "marker.cols", 4);
    expect(g.marker).toMatchObject({ type: "grid", cols: 4, rows: 2 });
    expect(isSet(g, "marker.cols")).toBe(true);
    expect(resetField(g, "marker.cols").marker.cols).toBe(2);
    const c = setField(g, "marker.type", "charuco");
    expect(c.marker).toMatchObject({ cols: 5, rows: 4, auto: true });
    expect(isSet(c, "marker.cols")).toBe(false);
    expect(isSet(c, "marker.type")).toBe(true);
    expect(resetField(c, "marker.type").marker).toMatchObject({ type: "single", cols: 1, rows: 1 });
  });

  it("a suggestion sets the size and a grid's counts; a 0 checker / separation stays driven", () => {
    const g = setField(f0, "marker.type", "grid");
    const s: Suggestion = { label: "3×2 @ 19 mm", reason: "best fill", params: { cols: 3, rows: 2, marker_mm: 19, checker_mm: 0, separation_mm: 0 } };
    const p = pickSuggestion(g, s);
    expect(p.marker).toMatchObject({ cols: 3, rows: 2, marker_mm: 19, auto: false });
    expect(["marker.marker_mm", "marker.cols", "marker.rows"].every((k) => isSet(p, k))).toBe(true);
    expect(isSet(p, "marker.separation_mm")).toBe(false);
  });
});

describe("the document", () => {
  const base = addShape(addShape(emptyDoc("t", [], preset), rectShape("r1", 0, 0, 40, 20)), rectShape("r2", 50, 0, 80, 30));

  it("a feature has a stable id, and its key is the id", () => {
    const f = newFeature("r1", null);
    expect(f.id).toMatch(/^f/);
    expect(f.key).toBe(f.id);
    expect(newFeature("r1", null).id).not.toBe(f.id);
  });

  it("no request without a feature, a rectangle and a preset", () => {
    expect(planRequest(base, null)).toBeNull();
    expect(planRequest(base, newFeature(null, null))).toBeNull();
    expect(planRequest({ ...base, preset: null }, newFeature("r1", null))).toBeNull();
  });

  it("the request carries the rectangle without its id, and the reference face", () => {
    const req = planRequest(base, newFeature("r1", { outer: "p", holes: [] }))!;
    expect(req.rect).toEqual({ cx: 20, cy: 10, w: 40, h: 20, angle_deg: 0 });
    expect(req.reference_face).toBe(true);
    expect(planRequest(base, newFeature("r1", null))!.reference_face).toBe(false);
  });

  it("many features: each by its rectangle, numbered in order, every one a sheet item", () => {
    const a = newFeature("r1", null, "fa"), b = setField(newFeature("r2", null, "fb"), "marker.first_id", 5);
    const waiting = newFeature(null, null, "fc");
    const d = addFeature(addFeature(addFeature(base, a), b), waiting);
    expect(featureOfRect(d, "r2")?.id).toBe("fb");
    expect(featureNumber(d, "fb")).toBe(2);
    const items = sheetItems(d);
    expect(items).toHaveLength(2);
    expect(items.map((r) => r.rect.cx)).toEqual([20, 65]);
    expect(items[1].marker.first_id).toBe(5);
    expect(idItems(d).map((i) => [i.key, i.first_id])).toEqual([["fa", null], ["fb", 5], ["fc", null]]);
  });

  it("removing a feature keeps its rectangle", () => {
    const d = removeFeature(addFeature(base, newFeature("r1", null, "fa")), "fa");
    expect(d.features).toHaveLength(0);
    expect(d.shapes.map((s) => s.id)).toEqual(["r1", "r2"]);
  });

  it("deleting a feature's rectangle leaves the feature without one", () => {
    const d = deleteShape(addFeature(base, newFeature("r1", { outer: "p", holes: ["r1"] }, "fa")), "r1");
    expect(d.shapes).toHaveLength(1);
    expect(d.features[0]).toMatchObject({ rectId: null, profile: null });
  });

  it("saves and reads back (version 2, with the ledger)", () => {
    const d = { ...addFeature(base, setField(newFeature("r1", null), "label.side", "above")), id_ledger: { k: 3 } };
    const text = serialise(d);
    expect(JSON.parse(text).version).toBe(2);
    expect(parseDoc(text)).toEqual(d);
  });

  it("refuses a file that is not one, by name", () => {
    expect(() => parseDoc("{}")).toThrow(/arucostudio-web/);
    expect(() => parseDoc(JSON.stringify({ format: "arucostudio-web", version: 3 }))).toThrow(/version 3/);
  });

  it("fills missing fields from the defaults", () => {
    const d = parseDoc(JSON.stringify({ format: "arucostudio-web", version: 2, shapes: [], features: [{ id: "fx", rectId: null, marker: { type: "grid" } }] }));
    expect(d.features[0].marker).toMatchObject({ type: "grid", dictionary: "DICT_4X4_50", auto: true });
    expect(d.features[0]).toMatchObject({ id: "fx", key: "fx", set: [] });
    expect(d.id_ledger).toEqual({});
  });
});

describe("version 1 files migrate", () => {
  it("the old one-feature fixture becomes one feature that plans", () => {
    const d = parseDoc(v1Fixture);
    expect(d.version).toBe(2);
    expect(d.name).toBe("Old plate");
    expect(d.features).toHaveLength(1);
    expect(d.id_ledger).toEqual({});
    expect((d as unknown as { feature?: unknown }).feature).toBeUndefined();
    const f = d.features[0];
    expect(f.id).toBeTruthy();
    expect(f.key).toBe(f.id);
    expect(f.rectId).toBe("r1");
    expect(f.marker).toMatchObject({ type: "grid", dictionary: "DICT_5X5_100", first_id: 4, cols: 2, rows: 2, auto: true });
    // what differs from its driven value was typed: set; the rest is driven
    expect([...f.set].sort()).toEqual(["label.gap_mm", "marker.dictionary", "marker.first_id", "marker.type"]);
    expect(isSet(f, "marker.cols")).toBe(false);
    expect(isSet(f, "marker.marker_mm")).toBe(false);
    const req = planRequest(d, f)!;
    expect(req.rect).toEqual({ cx: 60, cy: 40, w: 30, h: 30, angle_deg: 0 });
    expect(req.preset.id).toBe("builtin:inkjet-letter-vinyl");
    expect(sheetItems(d)).toHaveLength(1);
  });

  it("an old file with no feature has none; the id is kept across a save", () => {
    const old = JSON.parse(v1Fixture);
    expect(parseDoc(JSON.stringify({ ...old, feature: null })).features).toEqual([]);
    const d = parseDoc(v1Fixture);
    expect(parseDoc(serialise(d)).features[0].id).toBe(d.features[0].id);
  });

  it("an old typed size stays set", () => {
    const old = JSON.parse(v1Fixture);
    old.feature.marker.auto = false;
    old.feature.marker.marker_mm = 12;
    const f = parseDoc(JSON.stringify(old)).features[0];
    expect(isSet(f, "marker.marker_mm")).toBe(true);
    expect(f.marker.marker_mm).toBe(12);
  });
});
