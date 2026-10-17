// M6b.6: the sticker sheet dialog. Tight shows the shelf layout in the
// preview, Spaced shows captions and crop marks; the preview's sticker
// boxes equal sheet.json; Export writes sheet.pdf, sheet.svg, sheet.json.
import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { API, idle, openExample, segment, shot } from "./helpers";

async function previewBoxes(page: Page) {
  return page.locator('[data-testid="sheet-preview"] rect[data-sticker]').evaluateAll((els) => els.map((e) => ({
    key: e.getAttribute("data-sticker"), page: Number(e.getAttribute("data-page")), x: Number(e.getAttribute("data-x")),
    y: Number(e.getAttribute("data-y")), w: Number(e.getAttribute("data-w")), h: Number(e.getAttribute("data-h")),
  })));
}

async function sheetJson(page: Page, mode: string) {
  return (await page.request.get(`${API}/api/scene/sheet.json?page=letter&landscape=false&mode=${mode}&margin_mm=10`)).json();
}

function same(boxes: any[], json: any) {
  expect(boxes.length).toBe(json.stickers.length);
  for (const s of json.stickers) {
    const b = boxes.find((x) => x.key === s.key)!;
    expect(b, s.key).toBeTruthy();
    expect(b.page).toBe(s.page);
    for (const [k, v] of [["x", s.x_mm], ["y", s.y_mm], ["w", s.w_mm], ["h", s.h_mm]] as [string, number][]) {
      expect(Math.abs((b as any)[k] - v), `${s.key}.${k}`).toBeLessThanOrEqual(0.01);
    }
  }
}

test("M6b.6 the sheet dialog: tight shelves, spaced captions and crop marks, the preview = sheet.json, Export", async ({ page }) => {
  await openExample(page, "e2e-sheet", "sticker_sheet.arucostudio.json");
  await page.getByTestId("menu-export").click();
  await page.getByTestId("export-sheet").click();
  const dlg = page.getByTestId("dialog-sheet");
  await expect(dlg).toBeVisible();
  // the file's sheet says tight
  await expect(page.locator('.kit-seg[data-path="sheet.mode"]')).toHaveAttribute("data-value", "tight");
  const pv = page.getByTestId("sheet-preview");
  await expect(pv.locator("svg[data-mode='tight']")).toHaveCount(1);
  const tight = await sheetJson(page, "tight");
  expect(tight.shelves.length).toBeGreaterThan(0);
  await expect(pv.locator("text", { hasText: /^row 1:/ })).toHaveCount(1);                 // one line per shelf
  await expect(pv.locator("line")).toHaveCount(0);                                          // no crop marks
  same(await previewBoxes(page), tight);
  await expect(page.getByTestId("sheet-stats")).toHaveAttribute("data-cuts", String(tight.cuts));
  await shot(page, "m8b2_sheet_tight");

  await segment(page, "sheet.mode", "spaced");
  await expect(pv.locator("svg[data-mode='spaced']")).toHaveCount(1);
  const spaced = await sheetJson(page, "spaced");
  same(await previewBoxes(page), spaced);
  for (const s of spaced.stickers) {
    const cap = Array.isArray(s.caption) ? s.caption.join(" ") : String(s.caption);
    if (cap) await expect(pv.locator("text", { hasText: cap.split(" · ")[0] }).first()).toBeVisible();
  }
  expect(await pv.locator("line").count()).toBeGreaterThanOrEqual(8 * spaced.stickers.length - 8);   // crop marks at the corners
  await expect(pv.locator("text", { hasText: /^row 1:/ })).toHaveCount(0);
  await shot(page, "m8b2_sheet_spaced");

  // A4: the page changes the preview's size
  await page.locator('.kit-select[data-path="sheet.page"] .kit-select-trigger').click();
  await page.locator('.kit-select-popup[data-for="sheet.page"][data-open] [data-value="a4"]').click();
  await expect(pv.locator("svg")).toHaveAttribute("width", "210mm");

  // Export: the sheet's files only (sheet.pdf, sheet.svg, sheet.json), never
  // the 3D parts (audit 2026-10-17); "written to <folder>" and Reveal
  await page.evaluate(() => { (window as any).__studio.revealOpen = false; });
  await page.getByTestId("sheet-export").click();
  await idle(page);
  const files = page.getByTestId("sheet-files");
  await expect(files).toBeVisible();
  const listed: string[] = JSON.parse((await files.getAttribute("data-files"))!);
  for (const f of ["sheet.pdf", "sheet.svg", "sheet.json"]) expect(listed, f).toContain(f);
  expect(listed.filter((f) => f.startsWith("print3d/"))).toEqual([]);
  const dir = (await files.getAttribute("data-dir"))!;
  expect(fs.existsSync(path.join(dir, "sheet.pdf"))).toBeTruthy();
  await expect(files).toContainText(dir);
  const [rev] = await Promise.all([page.waitForResponse("**/api/scene/export/reveal"), page.getByTestId("sheet-reveal").click()]);
  expect((await rev.json()).opened).toBe(false);
  await shot(page, "m8b2_sheet_exported");
});
