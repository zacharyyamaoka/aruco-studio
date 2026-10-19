import { describe, expect, it } from "vitest";
import type { Preset, Suggestion } from "../core/contract";
import { rectShape } from "../sketch/model";
import v1Fixture from "../../e2e/fixtures/v1-plate.arucostudio-web.json?raw";
import {
  DEFAULT_MARKER, addFeature, addShape, applyIds, deleteShape, emptyDoc, featureNumber, featureOfRect, idCount, idItems, idRange, idRequest,
  isSet, keyOwner, newFeature, nextTurn, parseDoc, pickSuggestion, planRequest, removeFeature, resetField, serialise, setField, setMarker, setType, sheetItems, effectiveTrim } from "./doc";

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

  it("deleting a feature's rectangle deletes the feature; a profile that named a shape loses it", () => {
    const d = deleteShape(addFeature(addFeature(base, newFeature("r1", null, "fa")), newFeature("r2", { outer: "p", holes: ["r1"] }, "fb")), "r1");
    expect(d.shapes).toHaveLength(1);
    expect(d.features.map((f) => f.id)).toEqual(["fb"]);
    expect(d.features[0]).toMatchObject({ rectId: "r2", profile: null });
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

describe("auto id", () => {
  const two = () => addFeature(addFeature(emptyDoc("D"), newFeature("r1", null, "f1")), setField(newFeature("r2", null, "f2"), "marker.first_id", 9));

  it("the request: a driven first id is null, a typed one kept, with the ledger", () => {
    const d = { ...two(), id_ledger: { f1: 3 } };
    expect(idRequest(d)).toEqual({
      items: [
        { key: "f1", type: "single", dictionary: "DICT_4X4_50", count: 1, first_id: null },
        { key: "f2", type: "single", dictionary: "DICT_4X4_50", count: 1, first_id: 9 },
      ],
      ledger: { f1: 3 },
    });
  });

  it("the answer: a driven feature takes its id, a typed one keeps its own, the ledger is the core's", () => {
    const d = two();
    const out = applyIds(d, {
      items: [{ key: "f1", first_id: 31, ids: [31], driven: true }, { key: "f2", first_id: 9, ids: [9], driven: false }],
      ledger: { f1: 31 }, warnings: [],
    });
    expect(out.features.map((f) => f.marker.first_id)).toEqual([31, 9]);
    expect(isSet(out.features[0], "marker.first_id")).toBe(false);
    expect(out.id_ledger).toEqual({ f1: 31 });
    // the same answer again: the same document (no re-plan)
    expect(applyIds(out, { items: [{ key: "f1", first_id: 31, ids: [31], driven: true }, { key: "f2", first_id: 9, ids: [9], driven: false }], ledger: { f1: 31 }, warnings: [] })).toBe(out);
  });

  it("a removed feature's ledger entry goes when the core drops it", () => {
    const d = { ...removeFeature(two(), "f1"), id_ledger: { f1: 31, f2: 4 } };
    const out = applyIds(d, { items: [{ key: "f2", first_id: 9, ids: [9], driven: false }], ledger: { f2: 4 }, warnings: [] });
    expect(out.id_ledger).toEqual({ f2: 4 });
  });

  it("keys are unique: the owner of a key", () => {
    const d = two();
    expect(keyOwner(d, "f1", "f2")?.id).toBe("f2");
    expect(keyOwner(d, "f2", "f2")).toBeNull();
  });

  it("a board's origin square is driven at null (the corner), set as typed, and a new type drops it", () => {
    const c = setField(newFeature("r1", null, "f1"), "marker.type", "charuco");
    expect(isSet(c, "marker.origin_square")).toBe(false);
    const s = setField(c, "marker.origin_square", [1, 1]);
    expect(s.marker.origin_square).toEqual([1, 1]);
    expect(isSet(s, "marker.origin_square")).toBe(true);
    expect(resetField(s, "marker.origin_square").marker.origin_square).toBeNull();
    expect(setField(s, "marker.type", "grid").marker.origin_square).toBeNull();
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

describe("trim (2026-10-18)", () => {
  const plate = { ...emptyDoc("p", [rectShape("p", 0, 0, 120, 80), { kind: "circle", id: "h", cx: 25, cy: 55, r: 10 }, rectShape("r1", 40, 20, 80, 60)]), preset };

  it("a new feature is cut to the rectangle, driven; set and reset like any row", () => {
    const f = newFeature("r1", null);
    expect(f.trim).toBe("rectangle");
    expect(isSet(f, "trim")).toBe(false);
    const m = setField(f, "trim", "marker");
    expect(m.trim).toBe("marker");
    expect(isSet(m, "trim")).toBe(true);
    const r = resetField(m, "trim");
    expect(r.trim).toBe("rectangle");
    expect(isSet(r, "trim")).toBe(false);
  });

  it("the request sends the trim, and for profile the profile's loops as inscribe gets them", () => {
    const f = newFeature("r1", { outer: "p", holes: ["h"] });
    const rq = planRequest(plate, f)!;
    expect(rq.trim).toBe("rectangle");
    expect(rq.profile).toBeUndefined();
    const pq = planRequest(plate, setField(f, "trim", "profile"))!;
    expect(pq.trim).toBe("profile");
    expect(pq.profile!.loops).toHaveLength(2);
    expect(pq.profile!.loops[0]).toEqual([[0, 0], [120, 0], [120, 80], [0, 80]]);
    // no profile: the request is cut to the rectangle (the panel says so under
    // Trim); the feature keeps its Profile choice for when one comes back
    const nf = setField(newFeature("r1", null), "trim", "profile");
    const np = planRequest(plate, nf)!;
    expect(np.trim).toBe("rectangle");
    expect(np.profile).toBeUndefined();
    expect(nf.trim).toBe("profile");
    expect(effectiveTrim(nf)).toBe("rectangle");
  });

  it("files from before trim open on the rectangle, driven; a saved trim round-trips", () => {
    const f = parseDoc(v1Fixture).features[0];
    expect(f.trim).toBe("rectangle");
    expect(isSet(f, "trim")).toBe(false);
    const d = addFeature(plate, setField(newFeature("r1", null, "fm"), "trim", "marker"));
    const back = parseDoc(serialise(d)).features[0];
    expect(back.trim).toBe("marker");
    expect(isSet(back, "trim")).toBe(true);
    const raw = JSON.parse(serialise(d));
    raw.features[0].trim = "bogus";
    const bad = parseDoc(JSON.stringify(raw)).features[0];
    expect(bad.trim).toBe("rectangle");
    expect(isSet(bad, "trim")).toBe(false);
  });
});
