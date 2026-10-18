import { describe, expect, it } from "vitest";
import type { Preset } from "../core/contract";
import { chipValues, filterPresets, infoRows, NO_FILTERS, withField } from "./fields";
import { blankPreset } from "./local";

const ink: Preset = { ...blankPreset("inkjet"), id: "builtin:a4", name: "Inkjet · A4 vinyl", builtin: true, page: "A4", page_mm: [210, 297] };
const fdm: Preset = { ...blankPreset("print3d"), id: "builtin:fdm", name: "Default", builtin: true, nozzle_mm: 0.6 };

describe("Info rows", () => {
  it("inkjet: page, page_mm, margin, thickness, dpi, min cell, cell step", () => {
    expect(infoRows("inkjet").map((r) => r.key)).toEqual(["page", "page_mm", "margin_mm", "thickness_mm", "dpi", "min_cell_mm", "cell_step_mm"]);
  });
  it("3D: nozzle, line, first line, layer, first layer, bed, min cell, cell step", () => {
    expect(infoRows("print3d").map((r) => r.key))
      .toEqual(["nozzle_mm", "line_mm", "first_line_mm", "layer_mm", "first_layer_mm", "bed_mm", "min_cell_mm", "cell_step_mm"]);
  });
  it("every row of a blank preset has a value (no field of the contract left out)", () => {
    for (const m of ["inkjet", "print3d"] as const) {
      const p = blankPreset(m);
      const shown = new Set<string>(infoRows(m).map((r) => r.key));
      const fields = Object.keys(p).filter((k) => !["id", "name", "method", "builtin"].includes(k));
      expect(fields.sort()).toEqual([...shown].sort());
    }
  });
});

describe("left bar filters", () => {
  it("the chips come from the presets", () => {
    expect(chipValues([fdm, ink])).toEqual({ method: ["3D print", "Inkjet"], paper: ["A4"], nozzle: ["0.6 mm"] });
  });
  it("a method chip keeps that method only", () => {
    expect(filterPresets([fdm, ink], "", { ...NO_FILTERS, method: ["Inkjet"] })).toEqual([ink]);
    expect(filterPresets([fdm, ink], "", { ...NO_FILTERS, method: ["3D print"] })).toEqual([fdm]);
  });
  it("the search matches the method's name too", () => {
    expect(filterPresets([fdm, ink], "3d print", NO_FILTERS)).toEqual([fdm]);
  });
});

describe("editing a field", () => {
  it("a named paper sets the page size", () => {
    expect(withField(ink, "page", "Letter").page_mm).toEqual([215.9, 279.4]);
  });
  it("a typed page size that is not the paper's is Custom", () => {
    expect(withField(ink, "page_mm", [200, 297]).page).toBe("Custom");
    expect(withField(ink, "page_mm", [210, 297]).page).toBe("A4");
  });
});
