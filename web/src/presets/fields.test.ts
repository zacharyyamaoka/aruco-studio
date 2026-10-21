import { describe, expect, it } from "vitest";
import type { Preset } from "../core/contract";
import { chipValues, filterPresets, infoRows, NO_FILTERS, presetStep, stepKey, stepLabel, stepOf, stepOptions, withField } from "./fields";
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

describe("the size step (barrier 11)", () => {
  it("a preset's own step, else derived from its cell step", () => {
    expect(presetStep({ ...ink, size_step: { of: "dots" } })).toEqual({ of: "dots" });
    expect(presetStep({ ...ink, cell_step_mm: 0 })).toEqual({ of: "mm", mm: 0.5 });
    expect(presetStep(fdm)).toEqual({ of: "line" });
  });
  it("keys round-trip and read in words", () => {
    for (const s of [{ of: "dots" }, { of: "mm", mm: 0.1 }, { of: "mm", mm: 1 }, { of: "line" }] as const) expect(stepOf(stepKey(s))).toEqual(s);
    expect(stepLabel({ of: "dots" })).toBe("Whole printer dots (exact)");
    expect(stepLabel({ of: "mm", mm: 0.5 })).toBe("0.5 mm");
    expect(stepLabel({ of: "line" }, fdm)).toBe("Line width (0.45 mm)");
    expect(stepOptions({ of: "mm", mm: 0.5 }, ink).map((o) => o.label)).toEqual(["Whole printer dots (exact)", "0.1 mm", "0.5 mm", "1 mm"]);
    expect(stepOptions({ of: "mm", mm: 0.25 }, ink).map((o) => o.value)).toEqual(["dots", "mm:0.1", "mm:0.5", "mm:1", "mm:0.25"]);
  });
});

describe("fields nothing reads yet (review finding #9)", () => {
  it("3D first line and bed are shown as not used yet; every other row is live", () => {
    const unused = (m: "inkjet" | "print3d") => infoRows(m).filter((r) => "unused" in r && r.unused).map((r) => r.key);
    expect(unused("print3d")).toEqual(["first_line_mm", "bed_mm"]);
    expect(unused("inkjet")).toEqual([]);
  });
});
