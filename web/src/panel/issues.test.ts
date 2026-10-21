import { describe, expect, it } from "vitest";
import type { Issue } from "../core/contract";
import { DEFAULT_LABEL, DEFAULT_MARKER } from "../model/doc";
import { routeIssues, shownRows, tabLevel, tabRows, worstLevel } from "./issues";

const I = (field: string, level: Issue["level"] = "error"): Issue => ({ field, level, text: field });
// the label is off by default (2026-10-20 night): the label rows' cases turn it on
const ON = { ...DEFAULT_LABEL, on: true };
const OUTSIDE = { ...ON, place: "outside" as const };

describe("per-row issues", () => {
  it("an issue goes under its own row", () => {
    const shown = shownRows(DEFAULT_MARKER, DEFAULT_LABEL, "inkjet");
    expect(routeIssues([I("marker.marker_mm")], shown)["marker.marker_mm"]).toHaveLength(1);
  });
  it("a hidden row's issue goes to its owner", () => {
    const shown = shownRows(DEFAULT_MARKER, DEFAULT_LABEL, "inkjet");   // single: no Columns
    const r = routeIssues([I("marker.rows"), I("marker.checker_mm")], shown);
    expect(r["marker.marker_mm"]).toHaveLength(2);
  });
  it("Flip is a row of Manufacture on every profile (barrier 10: it always applies)", () => {
    const t = tabRows(DEFAULT_MARKER, DEFAULT_LABEL, "inkjet");
    expect(t.make).toContain("marker.flip");
    expect(routeIssues([I("marker.flip")], shownRows(DEFAULT_MARKER, DEFAULT_LABEL, "print3d"))["marker.flip"]).toHaveLength(1);
  });
  it("Manufacture: Size step, Trim, the method's heights, Flip, in that order (the skeleton)", () => {
    expect(tabRows(DEFAULT_MARKER, DEFAULT_LABEL, "inkjet").make).toEqual(["marker.size_step", "trim", "extrude.paper_mm", "marker.flip"]);
    expect(tabRows(DEFAULT_MARKER, DEFAULT_LABEL, "print3d").make)
      .toEqual(["marker.size_step", "trim", "extrude.mode", "extrude.white_mm", "extrude.black_mm", "marker.flip"]);
  });
  it("Marker: Profile and Preset first, then the skeleton's rows, Key last", () => {
    expect(tabRows(DEFAULT_MARKER, DEFAULT_LABEL, "inkjet").marker).toEqual(["profile", "preset", "marker.type", "marker.dictionary", "marker.first_id",
      "marker.marker_mm", "marker.suggest", "marker.turn", "marker.quiet_modules", "feature.key"]);
    expect(tabRows({ ...DEFAULT_MARKER, type: "grid" }, DEFAULT_LABEL, "inkjet").marker.slice(5, 9))
      .toEqual(["marker.marker_mm", "marker.cols", "marker.separation_mm", "marker.suggest"]);
    expect(tabRows({ ...DEFAULT_MARKER, type: "charuco" }, DEFAULT_LABEL, "inkjet").marker.slice(5, 10))
      .toEqual(["marker.marker_mm", "marker.cols", "marker.checker_mm", "marker.origin_square", "marker.suggest"]);
  });
  it("a height issue goes under its row; the other method's goes to Preset", () => {
    const ink = shownRows(DEFAULT_MARKER, DEFAULT_LABEL, "inkjet");
    const fdm = shownRows(DEFAULT_MARKER, DEFAULT_LABEL, "print3d");
    expect(routeIssues([I("extrude.paper_mm", "warn")], ink)["extrude.paper_mm"]).toHaveLength(1);
    expect(routeIssues([I("extrude.white_mm", "info")], fdm)["extrude.white_mm"]).toHaveLength(1);
    expect(routeIssues([I("extrude.white_mm", "info"), I("extrude")], ink).preset).toHaveLength(2);
    expect(routeIssues([I("extrude.paper_mm", "warn")], fdm).preset).toHaveLength(1);
  });
  it("rows go to the Columns × Rows row on a grid", () => {
    const shown = shownRows({ ...DEFAULT_MARKER, type: "grid" }, DEFAULT_LABEL, "inkjet");
    expect(routeIssues([I("marker.rows")], shown)["marker.cols"]).toHaveLength(1);
    expect(shown).toContain("marker.separation_mm");
  });
  it("a board's origin square has its own row; elsewhere it goes to Type", () => {
    expect(routeIssues([I("marker.origin_square")], shownRows({ ...DEFAULT_MARKER, type: "charuco" }, DEFAULT_LABEL, "inkjet"))["marker.origin_square"]).toHaveLength(1);
    expect(routeIssues([I("marker.origin_square", "info")], shownRows(DEFAULT_MARKER, DEFAULT_LABEL, "inkjet"))["marker.type"]).toHaveLength(1);
  });
  it("preset.* goes to the Preset row, tag and unknowns to the summary", () => {
    const r = routeIssues([I("preset.page"), I("tag"), I("nonsense")], shownRows(DEFAULT_MARKER, DEFAULT_LABEL, "inkjet"));
    expect(r.preset).toHaveLength(1);
    expect(r.summary).toHaveLength(2);
  });
  it("a label issue with the label off goes to On", () => {
    const r = routeIssues([I("label.height_mm", "warn"), I("label.gap_mm", "warn")], shownRows(DEFAULT_MARKER, { on: false }, "inkjet"));
    expect(r["label.on"]).toHaveLength(2);
  });
  it("Gap is a row outside the marker, Surface on it; the hidden one's issue goes to Place", () => {
    const on = shownRows(DEFAULT_MARKER, ON, "inkjet"), out = shownRows(DEFAULT_MARKER, OUTSIDE, "inkjet");
    expect(on).toContain("label.surface");
    expect(on).not.toContain("label.gap_mm");
    expect(out).toContain("label.gap_mm");
    expect(out).not.toContain("label.surface");
    expect(routeIssues([I("label.gap_mm")], on)["label.place"]).toHaveLength(1);
    expect(routeIssues([I("label.surface")], out)["label.place"]).toHaveLength(1);
  });
  it("Corner mark is a row of Label, the key and the quiet zone of Marker", () => {
    const t = tabRows(DEFAULT_MARKER, { on: false }, "inkjet");
    expect(t.label).toContain("marker.corner_mark");
    expect(t.marker).not.toContain("marker.corner_mark");
    expect(t.marker).toEqual(expect.arrayContaining(["marker.quiet_modules", "feature.key"]));
  });
  it("tab dots show the worst level of the tab's own rows", () => {
    const t = tabRows(DEFAULT_MARKER, DEFAULT_LABEL, "inkjet");
    const r = routeIssues([I("marker.turn", "info"), I("marker.first_id", "warn"), I("label.text", "error"), I("marker.corner_mark", "error"),
      I("extrude.paper_mm", "warn")], shownRows(DEFAULT_MARKER, DEFAULT_LABEL, "inkjet"));
    expect(tabLevel(r, t.marker)).toBe("warn");
    expect(tabLevel(r, t.label)).toBe("error");
    expect(tabLevel(r, t.make)).toBe("warn");
    expect(worstLevel([])).toBeNull();
  });
});
