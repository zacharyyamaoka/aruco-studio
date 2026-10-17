// bam.form/1's pure half: show_when, the anchors, mixed values.
import { describe, expect, it } from "vitest";
import { common, routeIssues, shortText, shows, summaryLine, visibleRows, type FormCtx, type FormRow, type Issue } from "./formModel";
import { themed } from "./Glyph";

const ROWS: FormRow[] = [
  { path: "settings.layout", type: "choice", label: "Type", tab: "marker", default: "single", show_when: {} },
  { path: "numbers.size", type: "mm", label: "Size", tab: "marker", default: 0, show_when: {} },
  { path: "numbers.square", type: "mm", label: "Square", tab: "marker", show_when: { layouts: ["charuco"] }, anchor: "numbers.size" },
  { path: "settings.make.thickness_mm", type: "mm", label: "Sticker thickness", tab: "print", show_when: { made_by: ["sticker"] }, anchor: "preset" },
  { path: "settings.holes", type: "choice", label: "Holes", tab: "marker", show_when: { target: ["holes"] }, anchor: "numbers.size" },
  { path: "settings.mode", type: "choice", label: "Colours", tab: "heights", default: "auto", show_when: { made_by: ["print3d"] }, anchor: "preset" },
  { path: "settings.op", type: "choice", label: "Operation", tab: "heights", show_when: { made_by: ["print3d"], values: { "settings.mode": ["both"] } }, anchor: "settings.mode" },
  { path: "settings.label.on", type: "bool", label: "Label", tab: "label", show_when: {} },
  { path: "settings.label.text", type: "text", label: "Custom", tab: "label", anchor: "settings.label.on",
    show_when: { truthy: ["settings.label.on"], values: { "settings.label.content": ["custom"] } } },
  { path: "settings.label.offset_x_mm", type: "mm", label: "Nudge X", tab: "label", anchor: "settings.label.on",
    show_when: { any_truthy: ["settings.label.offset_x_mm", "settings.label.offset_y_mm"] } },
  { path: "target.loops_mm", type: "loops", label: "Outline", tab: "none", anchor: "target" },
];

const ctx = (v: Record<string, unknown>, extra: Partial<FormCtx> = {}): FormCtx => ({
  get: (p) => v[p], made_by: "print3d", ...extra,
});
const paths = (c: FormCtx) => visibleRows(ROWS, c).map((r) => r.path);

describe("show_when", () => {
  it("layouts, made_by, target", () => {
    expect(paths(ctx({}))).not.toContain("numbers.square");
    expect(paths(ctx({}, { layout: "charuco" }))).toContain("numbers.square");
    expect(paths(ctx({}))).not.toContain("settings.make.thickness_mm");
    expect(paths(ctx({}, { made_by: "sticker" }))).toContain("settings.make.thickness_mm");
    expect(paths(ctx({}, { made_by: "sticker" }))).not.toContain("settings.mode");
    expect(paths(ctx({}))).not.toContain("settings.holes");
    expect(paths(ctx({}, { target: ["holes"] }))).toContain("settings.holes");
  });
  it("values (the row's default when absent), truthy, any_truthy; tab none never", () => {
    expect(paths(ctx({}))).not.toContain("settings.op");                 // mode absent = auto
    expect(paths(ctx({ "settings.mode": "both" }))).toContain("settings.op");
    expect(paths(ctx({ "settings.label.content": "custom" }))).not.toContain("settings.label.text");
    expect(paths(ctx({ "settings.label.content": "custom", "settings.label.on": true }))).toContain("settings.label.text");
    expect(paths(ctx({}))).not.toContain("settings.label.offset_x_mm");
    expect(paths(ctx({ "settings.label.offset_y_mm": 0.5 }))).toContain("settings.label.offset_x_mm");
    expect(paths(ctx({}))).not.toContain("target.loops_mm");
    expect(shows(ROWS[0], ctx({}))).toBe(true);
  });
});

describe("messages", () => {
  const I = (field: string, level = "warn"): Issue => ({ field, level, text: `${field} says so` });
  it("a shown row keeps its own; a hidden row's go to its anchor, then the anchor's anchor", () => {
    const c = ctx({});
    const shown = paths(c);
    const r = routeIssues([I("numbers.square"), I("settings.op"), I("settings.make.thickness_mm"), I("numbers.size"), I("target.loops_mm")],
      ROWS, shown, ["target", "preset"]);
    expect(r["numbers.size"].map((i) => i.field)).toEqual(["numbers.square", "numbers.size"]);
    expect(r["settings.mode"].map((i) => i.field)).toEqual(["settings.op"]);
    expect(r["preset"].map((i) => i.field)).toEqual(["settings.make.thickness_mm"]);
    expect(r["target"].map((i) => i.field)).toEqual(["target.loops_mm"]);
    // a sticker: Colours is hidden too, so Operation goes on to the Preset
    const s = ctx({}, { made_by: "sticker" });
    const r2 = routeIssues([I("settings.op")], ROWS, paths(s), ["target", "preset"]);
    expect(Object.keys(r2)).toEqual(["preset"]);
  });
  it("a deeper key path finds its row; nothing known goes to the summary's line", () => {
    const r = routeIssues([I("settings.label.on.x"), I("nothing.here")], ROWS, paths(ctx({})), []);
    expect(r["settings.label.on"]).toHaveLength(1);
    expect(r["tag"]).toHaveLength(1);
  });
  it("the summary: the worst first", () => {
    expect(summaryLine([], () => "", "Ready").level).toBe("ok");
    const s = summaryLine([I("a", "warn"), I("b", "error")], (f) => f);
    expect(s.level).toBe("error");
    expect(s.text).toContain("2 issues");
  });
});

describe("several at once", () => {
  it("one value or mixed", () => {
    expect(common([1, 1, 1])).toEqual({ value: 1, mixed: false });
    expect(common(["none", "triangle"]).mixed).toBe(true);
    expect(common([{ a: 1 }, { a: 1 }]).mixed).toBe(false);
    expect(common([]).mixed).toBe(false);
  });
});

describe("glyphs", () => {
  it("fixed colours become tokens, one style per element", () => {
    const out = themed('<path d="M0 0" fill="#38a6e8" fill-opacity=".3" stroke="#38A6E8"/><path stroke="#123456"/>', { "#38a6e8": "var(--accent)" });
    expect(out).toBe('<path d="M0 0" fill-opacity=".3" style="fill:var(--accent);stroke:var(--accent)"/><path stroke="#123456"/>');
  });
});

describe("shortText of label rule 4 (audit 2026-10-17)", () => {
  it("a ChArUco square too small says what to change, in one line", () => {
    const t = "Label not built: no room in a 13.0 mm ChArUco square for '#0-3', even at 3.0 mm letters. Fewer columns (bigger squares), a bigger checker or Content #id; Build anyway builds it there.";
    expect(shortText(t)).toBe("No room in a 13 mm square for '#0-3': fewer columns (bigger squares) or Content #id");
  });
});
