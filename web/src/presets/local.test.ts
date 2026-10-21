import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { Preset } from "../core/contract";
import { blankPreset, cleanPreset, exportJson, importJson } from "./local";
import { Thumb } from "./Thumb";

// A shared preset whose paper name closes the thumbnail's <text> and adds an
// SVG element with an event handler (review finding #1, 2026-10-21).
const EVIL = "</text><image href=\"x\" onerror=\"window.__pwned=1\"/><text>";

describe("importing presets", () => {
  it("a well-formed file round-trips (fresh ids, never builtin)", () => {
    const mine = [blankPreset("inkjet"), blankPreset("print3d")];
    const got = importJson(exportJson(mine));
    expect(got.map((p) => p.name)).toEqual(["My inkjet", "My 3D printer"]);
    expect(got.every((p) => p.id.startsWith("my:") && !p.builtin && !mine.some((m) => m.id === p.id))).toBe(true);
    expect({ ...got[0], id: "" }).toEqual({ ...mine[0], id: "" });
  });

  it("a malicious paper name is refused, with the preset and field named", () => {
    const p = { ...blankPreset("inkjet"), page: EVIL };
    expect(() => importJson(JSON.stringify([p]))).toThrow(/preset 1 .*page/);
  });

  it("every field is checked: wrong types, pairs, steps and unknown methods are refused", () => {
    const ink = blankPreset("inkjet"), fdm = blankPreset("print3d");
    const bad: [Record<string, unknown>, RegExp][] = [
      [{ ...ink, name: 3 }, /name/],
      [{ ...ink, name: "x".repeat(500) }, /name/],
      [{ ...ink, method: "laser" }, /method/],
      [{ ...ink, page_mm: [210, "<svg>"] }, /page_mm/],
      [{ ...ink, page_mm: [210] }, /page_mm/],
      [{ ...ink, page_mm: [-1, 297] }, /page_mm/],
      [{ ...ink, dpi: "600\" onload=\"x" }, /dpi/],
      [{ ...ink, margin_mm: "6" }, /margin_mm/],
      [{ ...ink, thickness_mm: 1e9 }, /thickness_mm/],
      [{ ...ink, margin_mm: -2 }, /margin_mm/],
      [{ ...fdm, line_mm: "0.45 mm</text>" }, /line_mm/],
      [{ ...fdm, bed_mm: { 0: 1, 1: 2 } }, /bed_mm/],
      [{ ...ink, size_step: { of: "mm", mm: "<b>" } }, /size_step/],
      [{ ...ink, size_step: { of: "furlong" } }, /size_step/],
    ];
    for (const [p, why] of bad) expect(() => importJson(JSON.stringify([p])), JSON.stringify(p)).toThrow(why);
  });

  it("one bad preset refuses the whole file (nothing half-imported)", () => {
    const good = blankPreset("inkjet"), evil = { ...blankPreset("inkjet"), page: EVIL };
    expect(() => importJson(JSON.stringify({ presets: [good, evil] }))).toThrow(/preset 2/);
  });

  it("unknown fields are dropped", () => {
    const p = { ...blankPreset("print3d"), onclick: "alert(1)", __proto__x: 1 };
    const got = importJson(JSON.stringify([p]))[0] as unknown as Record<string, unknown>;
    expect("onclick" in got).toBe(false);
    expect("__proto__x" in got).toBe(false);
  });

  it("null optional fields are kept as unset", () => {
    const got = cleanPreset({ ...blankPreset("print3d"), first_line_mm: null, bed_mm: null }, "preset 1");
    expect("first_line_mm" in got).toBe(false);
    expect("bed_mm" in got).toBe(false);
  });
});

describe("my presets kept in this browser", () => {
  it("are cleaned on read: a good one keeps its id, a malicious one is dropped", async () => {
    const store: Record<string, string> = {
      "aruco-web.presets.mine": JSON.stringify([
        { ...blankPreset("inkjet"), id: "my:good", margin_mm: 7.5 },
        { ...blankPreset("inkjet"), id: "my:evil", page: EVIL },
      ]),
    };
    vi.stubGlobal("window", { localStorage: { getItem: (k: string) => store[k] ?? null, setItem: (k: string, v: string) => { store[k] = v; } } });
    vi.resetModules();
    try {
      const fresh = await import("./local");
      expect(fresh.myPresets().map((p) => [p.id, p.margin_mm])).toEqual([["my:good", 7.5]]);
    } finally {
      vi.unstubAllGlobals();
    }
  });
});

describe("the preset thumbnail", () => {
  it("draws the paper name as text, never as markup", () => {
    // what a preset kept in localStorage before import validation can still hold
    const p = { ...blankPreset("inkjet"), page: EVIL } as Preset;
    const html = renderToStaticMarkup(createElement(Thumb, { p }));
    expect(html).not.toMatch(/<image/);
    expect(html).not.toMatch(/onerror="/);     // the handler only as escaped text
    expect(html).toContain("&lt;/text&gt;");
  });
  it("draws a 3D preset's line width as text", () => {
    const p = { ...blankPreset("print3d"), line_mm: "</text><script>x</script>" as unknown as number } as Preset;
    const html = renderToStaticMarkup(createElement(Thumb, { p }));
    expect(html).not.toMatch(/<script/);
  });
});
