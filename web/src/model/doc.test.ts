import { describe, expect, it } from "vitest";
import type { Preset, Suggestion } from "../core/contract";
import { circleShape, rectShape } from "../sketch/model";
import v1Fixture from "../../e2e/fixtures/v1-plate.arucostudio-web.json?raw";
import v2Fixture from "../../e2e/fixtures/v2-rect.arucostudio-web.json?raw";
import v3Fixture from "../../e2e/fixtures/v3-a4.arucostudio-web.json?raw";
import {
  DEFAULT_MARKER, addFeature, addShape, applyIds, deleteShape, emptyDoc, featureNumber, featurePreset, fillPresets, featureOfProfile, featureOfRect, featureRect, idCount, idItems,
  idRange, idRequest, isSet, keyOwner, newFeature, nextTurn, parseDoc, pickSuggestion, planRequest, rectProfile, referenceFace, removeFeature,
  resetField, serialise, setField, setMarker, setType, sheetGroups, sheetItems, withFeatures } from "./doc";

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
  const f0 = newFeature(rectProfile("r1"), "f1");

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
  const plate = {
    ...emptyDoc("p", [rectShape("p", 0, 0, 120, 80), circleShape("h", 25, 55, 20), rectShape("r1", 40, 20, 80, 60)]), default_preset: preset,
  };

  it("a feature has a stable id, and its key is the id", () => {
    const f = newFeature(rectProfile("r1"));
    expect(f.id).toMatch(/^f/);
    expect(f.key).toBe(f.id);
    expect(newFeature(rectProfile("r1")).id).not.toBe(f.id);
  });

  it("no request without a feature, a profile whose shapes exist and a preset", () => {
    expect(planRequest(base, null)).toBeNull();
    expect(planRequest(base, newFeature(null))).toBeNull();
    expect(planRequest(base, newFeature(rectProfile("gone")))).toBeNull();
    expect(planRequest({ ...base, default_preset: null }, newFeature(rectProfile("r1")))).toBeNull();
  });

  it("the request carries the profile's loops, its holes and the trim, never a rect (the core places the marker)", () => {
    const face = planRequest(plate, newFeature({ outer: "p", holes: ["h", "r1"] }))!;
    expect(face).not.toHaveProperty("rect");
    expect(face).toMatchObject({ trim: "profile", holes: "avoid", reference_face: true });
    expect(face.profile!.loops).toHaveLength(3);
    expect(face.profile!.loops[0]).toEqual([[0, 0], [120, 0], [120, 80], [0, 80]]);
    // the holes go clockwise, the rectangle hole too
    expect(face.profile!.loops[2]).toEqual([[40, 60], [80, 60], [80, 20], [40, 20]]);
  });

  it("a rectangle on its own is a rectangle profile: its four corners, no reference face", () => {
    const f = newFeature(rectProfile("r1"));
    const req = planRequest(plate, f)!;
    expect(req.profile!.loops).toEqual([[[40, 20], [80, 20], [80, 60], [40, 60]]]);
    expect(req.reference_face).toBe(false);
    expect(featureRect(plate, f)?.id).toBe("r1");
    expect(referenceFace(plate, f)).toBe(false);
    // the plate's outer edges alone (a double-click on it) are a rectangle profile too
    expect(featureRect(plate, newFeature(rectProfile("p")))?.id).toBe("p");
    // a region with holes is a face
    const face = newFeature({ outer: "p", holes: ["h"] });
    expect(featureRect(plate, face)).toBeNull();
    expect(referenceFace(plate, face)).toBe(true);
  });

  it("holes: avoid by default, ignore as chosen", () => {
    const f = { ...newFeature({ outer: "p", holes: ["h"] }), holes: "ignore" as const };
    expect(planRequest(plate, f)!.holes).toBe("ignore");
  });

  it("a profile's owner: one feature per profile, the holes in any order", () => {
    const d = addFeature(addFeature(plate, newFeature({ outer: "p", holes: ["h", "r1"] }, "fa")), newFeature(rectProfile("r1"), "fb"));
    expect(featureOfProfile(d, { outer: "p", holes: ["r1", "h"] })?.id).toBe("fa");
    expect(featureOfProfile(d, { outer: "p", holes: ["h"] })).toBeNull();
    expect(featureOfRect(d, "r1")?.id).toBe("fb");
    expect(featureOfRect(d, "p")).toBeNull();
  });

  it("many features: each by its profile, numbered in order, every one a sheet item", () => {
    const a = newFeature(rectProfile("r1"), "fa"), b = setField(newFeature(rectProfile("r2"), "fb"), "marker.first_id", 5);
    const waiting = newFeature(null, "fc");
    const d = addFeature(addFeature(addFeature(base, a), b), waiting);
    expect(featureOfRect(d, "r2")?.id).toBe("fb");
    expect(featureNumber(d, "fb")).toBe(2);
    const items = sheetItems(d);
    expect(items).toHaveLength(2);
    expect(items.map((r) => r.profile!.loops[0][0])).toEqual([[0, 0], [50, 0]]);
    expect(items[1].marker.first_id).toBe(5);
    expect(idItems(d).map((i) => [i.key, i.first_id])).toEqual([["fa", null], ["fb", 5], ["fc", null]]);
  });

  it("removing a feature keeps its profile's shapes", () => {
    const d = removeFeature(addFeature(base, newFeature(rectProfile("r1"), "fa")), "fa");
    expect(d.features).toHaveLength(0);
    expect(d.shapes.map((s) => s.id)).toEqual(["r1", "r2"]);
  });

  it("deleting a profile's outer shape deletes its feature; deleting a hole takes it out of the profile", () => {
    const d0 = addFeature(addFeature(plate, newFeature(rectProfile("r1"), "fa")), newFeature({ outer: "p", holes: ["h", "r1"] }, "fb"));
    const d = deleteShape(d0, "r1");
    expect(d.shapes.map((s) => s.id)).toEqual(["p", "h"]);
    expect(d.features.map((f) => f.id)).toEqual(["fb"]);
    expect(d.features[0].profile).toEqual({ outer: "p", holes: ["h"] });
    expect(deleteShape(d0, "p").features.map((f) => f.id)).toEqual(["fa"]);
  });

  it("moving a profile's shape moves its request (the planner re-plans on it)", () => {
    const f = newFeature(rectProfile("r1"));
    const moved = { ...plate, shapes: plate.shapes.map((s) => (s.id === "r1" ? { ...s, cx: (s as { cx: number }).cx + 20 } : s)) };
    expect(planRequest(moved, f)!.profile!.loops[0][0]).toEqual([60, 20]);
  });

  it("saves and reads back (version 4, with the ledger and each feature's preset)", () => {
    const d = { ...addFeature(base, setField(newFeature(rectProfile("r1"), undefined, preset), "label.side", "above")), id_ledger: { k: 3 } };
    const text = serialise(d);
    expect(JSON.parse(text).version).toBe(4);
    expect(JSON.parse(text).features[0].preset).toEqual(preset);
    expect(JSON.parse(text)).not.toHaveProperty("preset");
    expect(JSON.parse(text).features[0]).not.toHaveProperty("rectId");
    expect(parseDoc(text)).toEqual(d);
  });

  it("refuses a file that is not one, by name", () => {
    expect(() => parseDoc("{}")).toThrow(/arucostudio-web/);
    expect(() => parseDoc(JSON.stringify({ format: "arucostudio-web", version: 5 }))).toThrow(/version 5/);
  });

  it("fills missing fields from the defaults", () => {
    const d = parseDoc(JSON.stringify({ format: "arucostudio-web", version: 3, shapes: [], features: [{ id: "fx", profile: null, marker: { type: "grid" } }] }));
    expect(d.features[0].marker).toMatchObject({ type: "grid", dictionary: "DICT_4X4_50", auto: true });
    expect(d.features[0]).toMatchObject({ id: "fx", key: "fx", set: [], trim: "profile" });
    expect(d.id_ledger).toEqual({});
  });
});

describe("version 2 files migrate: a feature's rectangle becomes its profile (2026-10-20 evening)", () => {
  it("rectId + trim rectangle opens as that rectangle on its own, trim profile (driven), and requests that rectangle", () => {
    const d = parseDoc(v2Fixture);
    expect(d.version).toBe(4);
    expect(d.shapes.map((s) => s.id)).toEqual(["plate", "plate-h1", "plate-h2", "r1", "r2"]);
    const f1 = d.features[0];
    expect(f1).not.toHaveProperty("rectId");
    expect(f1.profile).toEqual({ outer: "r1", holes: [] });
    expect(f1.trim).toBe("profile");
    expect(isSet(f1, "trim")).toBe(false);
    expect(f1.set).toEqual(["marker.first_id"]);
    expect(f1.marker.first_id).toBe(7);
    const req = planRequest(d, f1)!;
    expect(req.trim).toBe("profile");
    expect(req.profile!.loops).toEqual([[[150, 10], [190, 10], [190, 40], [150, 40]]]);
    expect(req.reference_face).toBe(false);
  });

  it("a rectangle inscribed in a face keeps its spot: the inscribed rectangle is the profile; a set trim marker stays", () => {
    const f2 = parseDoc(v2Fixture).features[1];
    expect(f2.profile).toEqual({ outer: "r2", holes: [] });
    expect(f2.trim).toBe("marker");
    expect(isSet(f2, "trim")).toBe(true);
    expect(f2.marker).toMatchObject({ type: "grid", cols: 2, rows: 3, first_id: 20 });
  });

  it("an old set trim rectangle is profile, driven; a waiting feature (no rectangle) has no profile", () => {
    const raw = JSON.parse(v2Fixture);
    raw.features[0].set = ["trim"];
    raw.features[1] = { ...raw.features[1], rectId: null };
    const d = parseDoc(JSON.stringify(raw));
    expect(d.features[0].trim).toBe("profile");
    expect(isSet(d.features[0], "trim")).toBe(false);
    expect(d.features[1].profile).toBeNull();
    expect(sheetItems(d)).toHaveLength(1);
  });

  it("a migrated file saves as version 4 and reads back the same", () => {
    const d = parseDoc(v2Fixture);
    expect(parseDoc(serialise(d))).toEqual(d);
  });
});

describe("auto id", () => {
  const two = () => addFeature(addFeature(emptyDoc("D"), newFeature(rectProfile("r1"), "f1")), setField(newFeature(rectProfile("r2"), "f2"), "marker.first_id", 9));

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
    const c = setField(newFeature(rectProfile("r1"), "f1"), "marker.type", "charuco");
    expect(isSet(c, "marker.origin_square")).toBe(false);
    const s = setField(c, "marker.origin_square", [1, 1]);
    expect(s.marker.origin_square).toEqual([1, 1]);
    expect(isSet(s, "marker.origin_square")).toBe(true);
    expect(resetField(s, "marker.origin_square").marker.origin_square).toBeNull();
    expect(setField(s, "marker.type", "grid").marker.origin_square).toBeNull();
  });

  it("a size step is driven while absent (the preset's), set when present, ↺ back to null (barrier 11)", () => {
    const f = newFeature(rectProfile("r1"), "f1");
    expect(isSet(f, "marker.size_step")).toBe(false);
    const s = setField(f, "marker.size_step", { of: "dots" });
    expect(s.marker.size_step).toEqual({ of: "dots" });
    expect(isSet(s, "marker.size_step")).toBe(true);
    const r = resetField(s, "marker.size_step");
    expect(r.marker.size_step).toBeNull();
    expect(isSet(r, "marker.size_step")).toBe(false);
  });
});

describe("version 1 files migrate", () => {
  it("the old one-feature fixture becomes one feature that plans", () => {
    const d = parseDoc(v1Fixture);
    expect(d.version).toBe(4);
    expect(d.name).toBe("Old plate");
    expect(d.features).toHaveLength(1);
    expect(d.id_ledger).toEqual({});
    expect((d as unknown as { feature?: unknown }).feature).toBeUndefined();
    const f = d.features[0];
    expect(f.id).toBeTruthy();
    expect(f.key).toBe(f.id);
    expect(f.profile).toEqual({ outer: "r1", holes: [] });
    expect(f.marker).toMatchObject({ type: "grid", dictionary: "DICT_5X5_100", first_id: 4, cols: 2, rows: 2, auto: true });
    // what differs from its driven value was typed: set; the rest is driven (its label
    // is on, the default off since 2026-10-20 night: the old file keeps it, set)
    expect([...f.set].sort()).toEqual(["label.gap_mm", "label.on", "marker.dictionary", "marker.first_id", "marker.type"]);
    expect(isSet(f, "marker.cols")).toBe(false);
    expect(isSet(f, "marker.marker_mm")).toBe(false);
    const req = planRequest(d, f)!;
    expect(req.profile!.loops).toEqual([[[45, 25], [75, 25], [75, 55], [45, 55]]]);
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

describe("trim (2026-10-18; profile | marker since 2026-10-20 evening)", () => {
  const plate = { ...emptyDoc("p", [rectShape("p", 0, 0, 120, 80), { kind: "circle", id: "h", cx: 25, cy: 55, r: 10 }, rectShape("r1", 40, 20, 80, 60)]), default_preset: preset };

  it("a new feature is cut to its profile, driven; set and reset like any row", () => {
    const f = newFeature(rectProfile("r1"));
    expect(f.trim).toBe("profile");
    expect(isSet(f, "trim")).toBe(false);
    const m = setField(f, "trim", "marker");
    expect(m.trim).toBe("marker");
    expect(isSet(m, "trim")).toBe(true);
    const r = resetField(m, "trim");
    expect(r.trim).toBe("profile");
    expect(isSet(r, "trim")).toBe(false);
  });

  it("the request sends the trim with the profile's loops either way", () => {
    const f = newFeature({ outer: "p", holes: ["h"] });
    const pq = planRequest(plate, f)!;
    expect(pq.trim).toBe("profile");
    expect(pq.profile!.loops).toHaveLength(2);
    const mq = planRequest(plate, setField(f, "trim", "marker"))!;
    expect(mq.trim).toBe("marker");
    expect(mq.profile!.loops).toHaveLength(2);
  });

  it("files from before trim open on the profile, driven; a saved trim round-trips; an unknown one is the profile", () => {
    const f = parseDoc(v1Fixture).features[0];
    expect(f.trim).toBe("profile");
    expect(isSet(f, "trim")).toBe(false);
    const d = addFeature(plate, setField(newFeature(rectProfile("r1"), "fm"), "trim", "marker"));
    const back = parseDoc(serialise(d)).features[0];
    expect(back.trim).toBe("marker");
    expect(isSet(back, "trim")).toBe(true);
    const raw = JSON.parse(serialise(d));
    raw.features[0].trim = "bogus";
    const bad = parseDoc(JSON.stringify(raw)).features[0];
    expect(bad.trim).toBe("profile");
    expect(isSet(bad, "trim")).toBe(false);
  });
});

describe("the heights (barrier 10, 2026-10-20 night): set only when typed, driven otherwise", () => {
  it("setField / resetField on extrude.*, isSet, and the request always carries extrude ({} = all driven)", () => {
    let d = addShape(emptyDoc("t", [], preset), rectShape("r", 0, 0, 40, 30));
    let f = newFeature(rectProfile("r"));
    d = addFeature(d, f);
    expect(f.extrude).toEqual({});
    expect(isSet(f, "extrude.white_mm")).toBe(false);
    expect(planRequest(d, f)!.extrude).toEqual({});
    f = setField(f, "extrude.white_mm", 2.4);
    f = setField(f, "extrude.mode", "black");
    expect(isSet(f, "extrude.white_mm")).toBe(true);
    expect(isSet(f, "extrude.black_mm")).toBe(false);
    expect(planRequest(d, f)!.extrude).toEqual({ white_mm: 2.4, mode: "black" });
    // 0 is a set value (honoured, never "unset")
    f = setField(f, "extrude.black_mm", 0);
    expect(isSet(f, "extrude.black_mm")).toBe(true);
    f = resetField(resetField(resetField(f, "extrude.white_mm"), "extrude.mode"), "extrude.black_mm");
    expect(f.extrude).toEqual({});
    expect(planRequest(d, f)!.extrude).toEqual({});
  });

  it("files from before barrier 10 open with every height driven", () => {
    const d = parseDoc(v2Fixture);
    for (const f of d.features) expect(f.extrude).toEqual({});
  });
});

describe("a preset per feature (version 4, Zach 2026-10-20 night: \"applied on a per marker basis\")", () => {
  const a4 = preset;
  const letter: Preset = { id: "builtin:letter", name: "Letter", method: "inkjet", builtin: true, page: "Letter", page_mm: [215.9, 279.4] };
  const print3d: Preset = { id: "builtin:default", name: "Default", method: "print3d", builtin: true, nozzle_mm: 0.6, line_mm: 0.675 };
  const sheet = () => {
    let d = emptyDoc("s", [rectShape("r1", 0, 0, 30, 30), rectShape("r2", 40, 0, 70, 30), rectShape("r3", 80, 0, 110, 30), rectShape("r4", 120, 0, 150, 30)], letter);
    d = addFeature(d, newFeature(rectProfile("r1"), "f1", a4));
    d = addFeature(d, newFeature(rectProfile("r2"), "f2", print3d));
    d = addFeature(d, newFeature(rectProfile("r3"), "f3", letter));
    return addFeature(d, newFeature(rectProfile("r4"), "f4", a4));
  };

  it("each feature plans with its own preset, not the document's default", () => {
    const d = sheet();
    expect(planRequest(d, d.features[0])!.preset).toEqual(a4);
    expect(planRequest(d, d.features[1])!.preset).toEqual(print3d);
    expect(planRequest(d, d.features[2])!.preset).toEqual(letter);
  });

  it("a feature without one (made before the core's presets arrived) plans with the default; fillPresets gives it the default", () => {
    const d = addFeature(emptyDoc("w", [rectShape("r1", 0, 0, 30, 30)], letter), newFeature(rectProfile("r1"), "f1"));
    expect(featurePreset(d, d.features[0])).toEqual(letter);
    expect(planRequest(d, d.features[0])!.preset).toEqual(letter);
    expect(fillPresets(d, letter).features[0].preset).toEqual(letter);
    const full = fillPresets(d, letter);
    expect(fillPresets(full, a4)).toBe(full);
  });

  it("Print: the inkjet features, one group per preset in first-seen order; 3D-print ones are not on paper", () => {
    const groups = sheetGroups(sheet());
    expect(groups.map((g) => g.preset.id)).toEqual(["builtin:x", "builtin:letter"]);
    expect(groups.map((g) => g.items.length)).toEqual([2, 1]);
    expect(groups.flatMap((g) => g.items).every((r) => r.preset.method === "inkjet")).toBe(true);
    // a modified copy of a preset (same id, another margin) is its own group
    const d = sheet();
    const mod = { ...d, features: d.features.map((f) => (f.id === "f4" ? { ...f, preset: { ...a4, margin_mm: 3 } } : f)) };
    expect(sheetGroups(mod).map((g) => g.items.length)).toEqual([1, 1, 1]);
    // sheetItems: the group of the named feature's preset, else the first
    expect(sheetItems(d, "f3").map((r) => r.preset.id)).toEqual(["builtin:letter"]);
    expect(sheetItems(d, "f2")).toHaveLength(2);
    expect(sheetItems(d)).toHaveLength(2);
  });

  it("Print's Selected: only the named features, each with its own preset and ids", () => {
    const s0 = sheet();
    const d = { ...s0, features: s0.features.map((f) => (f.id === "f4" ? { ...f, marker: { ...f.marker, first_id: 17 } } : f)) };
    const only = withFeatures(d, ["f4", "f3"]);
    expect(only.features.map((f) => f.id)).toEqual(["f3", "f4"]);
    expect(only.shapes).toBe(d.shapes);
    const groups = sheetGroups(only);
    expect(groups.map((g) => [g.preset.id, g.items.length])).toEqual([["builtin:letter", 1], ["builtin:x", 1]]);
    expect(groups[1].items[0].marker.first_id).toBe(17);
    expect(sheetGroups(withFeatures(d, ["f2"]))).toEqual([]);
  });
});

describe("version 3 files migrate: the file's preset goes on every feature (fixture v3-a4)", () => {
  it("every feature is made by the file's preset, which is also the default for a new marker", () => {
    const old = JSON.parse(v3Fixture);
    const d = parseDoc(v3Fixture);
    expect(d.version).toBe(4);
    expect(d).not.toHaveProperty("preset");
    expect(d.default_preset).toEqual(old.preset);
    expect(d.features.map((f) => f.preset)).toEqual([old.preset, old.preset]);
    expect(d.features.map((f) => planRequest(d, f)!.preset.id)).toEqual(["builtin:inkjet-a4-vinyl", "builtin:inkjet-a4-vinyl"]);
    expect(d.id_ledger).toEqual({ f1: 3, f2: 10 });
    expect(d.features[1].marker).toMatchObject({ type: "grid", cols: 2, rows: 2, first_id: 10 });
  });

  it("a v3 file without a preset opens with none (the core's presets fill them later)", () => {
    const old = JSON.parse(v3Fixture);
    delete old.preset;
    const d = parseDoc(JSON.stringify(old));
    expect(d.default_preset).toBeNull();
    expect(d.features.map((f) => f.preset)).toEqual([null, null]);
  });

  it("the migrated file saves as version 4 and reads back the same", () => {
    const d = parseDoc(v3Fixture);
    expect(JSON.parse(serialise(d)).version).toBe(4);
    expect(parseDoc(serialise(d))).toEqual(d);
  });
});
