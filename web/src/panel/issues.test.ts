import { describe, expect, it } from "vitest";
import type { Issue } from "../core/contract";
import { DEFAULT_MARKER } from "../model/doc";
import { routeIssues, shownRows, tabLevel, worstLevel } from "./issues";

const I = (field: string, level: Issue["level"] = "error"): Issue => ({ field, level, text: field });

describe("per-row issues", () => {
  it("an issue goes under its own row", () => {
    const shown = shownRows(DEFAULT_MARKER, true, false);
    expect(routeIssues([I("marker.marker_mm")], shown)["marker.marker_mm"]).toHaveLength(1);
  });
  it("a hidden row's issue goes to its owner", () => {
    const shown = shownRows(DEFAULT_MARKER, true, true);   // single, reference face: no Flip, no Columns
    const r = routeIssues([I("marker.flip"), I("marker.rows"), I("marker.checker_mm")], shown);
    expect(r["marker.turn"]).toHaveLength(1);
    expect(r["marker.marker_mm"]).toHaveLength(2);
  });
  it("rows go to the Columns × Rows row on a grid", () => {
    const shown = shownRows({ ...DEFAULT_MARKER, type: "grid" }, true, false);
    expect(routeIssues([I("marker.rows")], shown)["marker.cols"]).toHaveLength(1);
    expect(shown).toContain("marker.separation_mm");
  });
  it("preset.* goes to the Preset row, tag and unknowns to the summary", () => {
    const r = routeIssues([I("preset.page"), I("tag"), I("nonsense")], shownRows(DEFAULT_MARKER, true, false));
    expect(r.preset).toHaveLength(1);
    expect(r.summary).toHaveLength(2);
  });
  it("a label issue with the label off goes to On", () => {
    const r = routeIssues([I("label.height_mm", "warn")], shownRows(DEFAULT_MARKER, false, false));
    expect(r["label.on"]).toHaveLength(1);
  });
  it("tab dots show the worst level", () => {
    const r = routeIssues([I("marker.turn", "info"), I("marker.first_id", "warn"), I("label.text", "error")], shownRows(DEFAULT_MARKER, true, false));
    expect(tabLevel(r, "marker.")).toBe("warn");
    expect(tabLevel(r, "label.")).toBe("error");
    expect(worstLevel([])).toBeNull();
  });
});
