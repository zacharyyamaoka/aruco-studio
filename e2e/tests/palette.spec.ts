// M8b1.5: the bottom toolbar and the command palette. Every tool has a key
// badge and the active one is lit; S then "verify" Enter runs Verify; S
// lists exactly the commands of docs/STUDIO.md's keys table (the two lists
// diffed, keys included); Esc cancels a tool; ? shows the map.
import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { ROOT, add, freshFile, idle, probe, shot } from "./helpers";

/** docs/STUDIO.md's "Commands and keys" table: [[key, command], ...]. */
function docTable(): [string, string][] {
  const md = fs.readFileSync(path.join(ROOT, "docs", "STUDIO.md"), "utf-8");
  const part = md.split("## Commands and keys")[1];
  const lines = part.split("\n");
  const start = lines.findIndex((l) => l.startsWith("| Key | Command |"));
  const out: [string, string][] = [];
  for (const l of lines.slice(start + 2)) {
    if (!l.startsWith("|")) break;
    const cells = l.split("|").slice(1, -1).map((c) => c.trim());
    out.push([cells[0], cells[1]]);
  }
  return out;
}

test("M8b1.5 the toolbar's badges, the lit tool, the palette = the keys table, Esc, ?", async ({ page }) => {
  await freshFile(page, "e2e-palette");
  const tools = page.locator('.bottombar .kit-tool[data-testid^="tool-"]');
  const n = await tools.count();
  expect(n).toBe(10);                                                   // nine tools and Search
  for (let i = 0; i < n; i++) {
    const badge = tools.nth(i).locator(".kit-badge");
    expect(((await badge.getAttribute("data-badge")) || "").length).toBeGreaterThan(0);
  }
  await expect(page.getByTestId("tool-select")).toHaveAttribute("data-active", "1");
  for (const [key, id] of [["r", "rect"], ["c", "circle"], ["p", "polygon"], ["o", "slot"], ["h", "hole"], ["e", "extrude"], ["a", "aruco"], ["v", "select"]]) {
    await page.keyboard.press(key);
    await expect(page.getByTestId(`tool-${id}`)).toHaveAttribute("data-active", "1");
    await expect(page.locator('.bottombar .kit-tool[data-active="1"]')).toHaveCount(1);
  }
  await page.keyboard.press("Shift+H");
  await expect(page.getByTestId("tool-rhole")).toHaveAttribute("data-active", "1");
  await page.keyboard.press("Escape");                                  // Esc cancels a tool
  await expect(page.getByTestId("tool-select")).toHaveAttribute("data-active", "1");
  await page.keyboard.press("c");
  await page.keyboard.type("25");
  await expect(page.getByTestId("typed")).toContainText("25");
  await shot(page, "m8b1_palette_tool_lit");
  await page.keyboard.press("Escape");
  expect((await probe(page)).tool).toBe("select");
  expect((await probe(page)).typed).toBe("");

  // S lists every command of the keys table, and only those
  await page.keyboard.press("s");
  await expect(page.getByTestId("palette")).toBeVisible();
  const items = await page.locator("[cmdk-item]").evaluateAll((els) => els.map((e) => [
    (e.querySelector(".kit-kbd") as HTMLElement | null)?.dataset.key ?? "", e.getAttribute("data-command") ?? ""]));
  const doc = docTable();
  expect(items.length).toBeGreaterThan(30);
  expect([...items].map(([k, c]) => `${k} | ${c}`).sort()).toEqual([...doc].map(([k, c]) => `${k} | ${c}`).sort());
  await shot(page, "m8b1_palette_open");
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("palette")).toHaveCount(0);

  // S, "verify", Enter: Verify runs (every tag)
  await add(page, "single");
  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");
  await page.keyboard.press("s");
  await page.getByTestId("palette-input").fill("verify");
  await expect(page.locator('[cmdk-item][data-selected="true"]')).toHaveAttribute("data-command", "Verify");
  await shot(page, "m8b1_palette_verify");
  await page.keyboard.press("Enter");
  await idle(page);
  await expect(page.getByTestId("drawer-verify")).toBeVisible();
  await expect(page.locator('[data-verify-row="tag1"] td[data-ok]')).toHaveAttribute("data-ok", "1");

  // ? shows the map: every command with its key
  await page.keyboard.press("?");
  await expect(page.getByTestId("drawer-messages")).toBeVisible();
  for (const [, c] of doc) await expect(page.locator(`[data-key-row="${c}"]`)).toHaveCount(1);
  await shot(page, "m8b1_palette_keymap");
});

// the 2026-10-17 audit: "send" Enter ran Search commands. A command is found
// by its name first: its whole name selects it, and so does the start of it.
test("S + a command's whole name selects that command first; short names too", async ({ page }) => {
  await freshFile(page, "e2e-palette-rank");
  await page.keyboard.press("s");
  const input = page.getByTestId("palette-input");
  await expect(input).toBeVisible();
  const names = await page.locator('[cmdk-item]:not([aria-disabled="true"])').evaluateAll((els) => els.map((e) => e.getAttribute("data-command") || ""));
  expect(names.length).toBeGreaterThan(30);
  const first = page.locator('[cmdk-item][data-selected="true"]');
  for (const n of names) {
    await input.fill(n);
    await expect(first, n).toHaveAttribute("data-command", n);
  }
  const short: [string, string][] = [["send", "Send to PrusaSlicer…"], ["new", "New scene"], ["save", "Save as"],
    ["fit", "Zoom to fit"], ["delete", "Delete"], ["redo", "Redo"], ["undo", "Undo"], ["verify", "Verify"]];
  for (const [typed, want] of short) {
    if (!names.includes(want)) continue;                                  // off in this scene
    await input.fill(typed);
    await expect(first, typed).toHaveAttribute("data-command", want);
  }
  await page.keyboard.press("Escape");
});
