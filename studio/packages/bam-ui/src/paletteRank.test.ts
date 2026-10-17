// The palette ranks a command by its name (audit 2026-10-17).
import { describe, expect, it } from "vitest";
import { rankCommand } from "./paletteRank";

describe("rankCommand", () => {
  it("puts the exact name first, then a prefix, a word start, a substring, fuzzy", () => {
    const exact = rankCommand("Send to PrusaSlicer…", "send to prusaslicer…");
    const prefix = rankCommand("Send to PrusaSlicer…", "send");
    const word = rankCommand("Print sticker sheet…", "sheet");
    const inside = rankCommand("Renumber all", "umber");
    const fuzzy = rankCommand("Search commands", "send");
    expect(exact).toBe(1);
    expect(prefix).toBeGreaterThan(word);
    expect(word).toBeGreaterThan(inside);
    expect(inside).toBeGreaterThan(fuzzy);
    expect(fuzzy).toBeGreaterThan(0);
    expect(rankCommand("Undo", "zzz")).toBe(0);
  });
  it("a hint or group only ranks under any name match", () => {
    expect(rankCommand("Extrude", "delete", ["Tools", "the selected shape"])).toBeLessThan(rankCommand("Delete", "del"));
  });
});

import { rankedGroups, type PaletteItem } from "./CommandPalette";

describe("rankedGroups", () => {
  const it_ = (id: string, name: string, group: string): PaletteItem => ({ id, name, key: "", group, run: () => undefined });
  const items = [it_("tool.select", "Select / move", "Tools"), it_("tool.slot", "Slot", "Tools"), it_("tool.hole", "Hole", "Tools"),
    it_("edit.palette", "Search commands", "Edit"), it_("export.send", "Send to PrusaSlicer…", "Export")];
  it("the best match is first, its group first, whatever the case typed", () => {
    for (const q of ["Slot", "slot", "SLOT"]) expect(rankedGroups(items, q)[0][1][0].name).toBe("Slot");
    expect(rankedGroups(items, "send")[0]).toEqual(["Export", [items[4]]]);
    expect(rankedGroups(items, "").flatMap(([, l]) => l).map((i) => i.id)).toEqual(items.map((i) => i.id));
  });
});
