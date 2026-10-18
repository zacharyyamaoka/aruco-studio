import { describe, expect, it } from "vitest";
import type { Preset, Suggestion } from "../core/contract";
import { rectShape } from "../sketch/model";
import {
  DEFAULT_MARKER, addShape, deleteShape, emptyDoc, idCount, idRange, newFeature, nextTurn, parseDoc, pickSuggestion, planRequest,
  serialise, setMarker, setType,
} from "./doc";

const preset: Preset = { id: "builtin:x", name: "X", method: "inkjet", builtin: true, page: "A4", page_mm: [210, 297] };

describe("the marker's numbers", () => {
  it("typing a size turns Auto off", () => {
    expect(setMarker(DEFAULT_MARKER, "marker_mm", 50)).toMatchObject({ marker_mm: 50, auto: false });
    expect(setMarker(DEFAULT_MARKER, "first_id", 3).auto).toBe(true);
  });
  it("switching type sets a grid's start and back", () => {
    const g = setType(DEFAULT_MARKER, "grid");
    expect(g).toMatchObject({ type: "grid", cols: 2, rows: 2, auto: true });
    expect(setType(g, "single")).toMatchObject({ cols: 1, rows: 1 });
    expect(setType(g, "charuco")).toMatchObject({ cols: 5, rows: 4, separation_mm: 0 });
    expect(setMarker(DEFAULT_MARKER, "type", "grid").cols).toBe(2);
  });
  it("a suggestion sets its numbers and Auto off", () => {
    const s: Suggestion = { label: "3×2 @ 19 mm", reason: "best fill", params: { cols: 3, rows: 2, marker_mm: 19, checker_mm: 0, separation_mm: 4 } };
    expect(pickSuggestion({ ...DEFAULT_MARKER, type: "grid" }, s)).toMatchObject({ cols: 3, rows: 2, marker_mm: 19, separation_mm: 4, auto: false });
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

describe("the document", () => {
  const base = addShape(emptyDoc("t", [], preset), rectShape("r1", 0, 0, 40, 20));

  it("no request without a feature, a rectangle and a preset", () => {
    expect(planRequest(base)).toBeNull();
    expect(planRequest({ ...base, feature: newFeature(null, null) })).toBeNull();
    expect(planRequest({ ...base, preset: null, feature: newFeature("r1", null) })).toBeNull();
  });

  it("the request carries the rectangle without its id, and the reference face", () => {
    const req = planRequest({ ...base, feature: newFeature("r1", { outer: "p", holes: [] }) })!;
    expect(req.rect).toEqual({ cx: 20, cy: 10, w: 40, h: 20, angle_deg: 0 });
    expect(req.reference_face).toBe(true);
    expect(planRequest({ ...base, feature: newFeature("r1", null) })!.reference_face).toBe(false);
  });

  it("deleting the feature's rectangle leaves the feature without one", () => {
    const d = deleteShape({ ...base, feature: newFeature("r1", { outer: "p", holes: ["r1"] }) }, "r1");
    expect(d.shapes).toHaveLength(0);
    expect(d.feature).toMatchObject({ rectId: null, profile: null });
  });

  it("saves and reads back", () => {
    const d = { ...base, feature: newFeature("r1", null) };
    expect(parseDoc(serialise(d))).toEqual(d);
  });

  it("refuses a file that is not one, by name", () => {
    expect(() => parseDoc("{}")).toThrow(/arucostudio-web/);
    expect(() => parseDoc(JSON.stringify({ format: "arucostudio-web", version: 2 }))).toThrow(/version 2/);
  });

  it("fills missing marker fields from the defaults", () => {
    const d = parseDoc(JSON.stringify({ format: "arucostudio-web", version: 1, shapes: [], feature: { rectId: null, marker: { type: "grid" } } }));
    expect(d.feature!.marker).toMatchObject({ type: "grid", dictionary: "DICT_4X4_50", auto: true });
  });
});
