// The 2D model in the Studio (2026-10-17, Zach's 2D pivot: inkjet on
// vinyl). Every bar reads the DOM, the store or the API:
// * a rule-2 sticker's inspector: Made by "Inkjet printer", the Make tab
//   named Inkjet with Paper thickness (its stock suggestions fill it in),
//   Paper size and Page margins; no tag margin / cut line (Q7); the grey
//   t/2 line;
// * the page lint: a sticker over its page has a red row on Marker size
//   (an error, the plan still built), the summary red, its cut line red;
// * Shift: the inspector's X / Y and the canvas crosshair drag;
// * the sheet dialog: Sticker margin and Cut lines (from the file's
//   `sheet`), the preview follows them.
// The light screenshots go to docs/status/2d_core_*.png (the lane's record).
import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { API, ROOT, choose, freshFile, idle, issueTexts, probe, sceneTags, tab, type } from "./helpers";

const GALLERY = path.join(ROOT, "examples", "gallery");
const STATUS = path.join(ROOT, "docs", "status");

async function openGallery(page: Page, name: string): Promise<string> {
  return freshFile(page, `e2e-${name}`, fs.readFileSync(path.join(GALLERY, `${name}.arucostudio.json`), "utf-8"));
}

async function select(page: Page, name: string) {
  await page.locator(`[data-ids-row="${name}"]`).click();
  await idle(page);
  await expect(page.getByTestId("inspector")).toHaveAttribute("data-tag", name);
}

async function statusShot(page: Page, name: string, clip?: "inspector") {
  await idle(page);
  await page.waitForTimeout(200);
  const file = path.join(STATUS, `2d_core_${name}.png`);
  if (clip === "inspector") await page.getByTestId("inspector").screenshot({ path: file });
  else await page.screenshot({ path: file });
}

async function light(page: Page) {
  const t = await page.evaluate(() => document.documentElement.dataset.theme);
  if (t !== "light") await page.getByTestId("theme").click();
  expect(await page.evaluate(() => document.documentElement.dataset.theme)).toBe("light");
}

test("the inspector's Inkjet rows, the stock suggestions, and the red page lint", async ({ page }) => {
  await page.setViewportSize({ width: 1500, height: 940 });
  await openGallery(page, "page_lint");
  await light(page);
  await select(page, "typed");
  const insp = page.getByTestId("inspector");
  await expect(insp).toHaveAttribute("data-made-by", "sticker");
  await expect(page.getByTestId("made-by")).toContainText("Inkjet printer");
  // the red lint on Marker size: an error, the plan still built
  await tab(page, "marker");
  const lint = page.locator('[data-issues-for="numbers.size"] .issue[data-level="error"]');
  await expect(lint).toHaveCount(1);
  expect((await issueTexts(page, "numbers.size")).some((t) => t.startsWith("Over the page by 70.6 mm"))).toBeTruthy();
  await expect(page.locator('[data-row="numbers.size"]')).toHaveClass(/has-error/);
  await expect(page.getByTestId("summary")).toHaveClass(/lv-error/);
  const t = (await sceneTags(page.request)).find((x: any) => x.name === "typed");
  expect(t.plan.ok).toBeTruthy();
  expect(t.plan.sticker.page.fits).toBe(false);
  await expect(page.locator('.canvas2d g[data-tag="typed"] [data-guide="cut_line"][data-overpage="1"]')).toHaveCount(1);
  await expect(page.locator('.canvas2d g[data-tag="capped"] [data-guide="cut_line"][data-overpage="1"]')).toHaveCount(0);
  await page.evaluate(() => (window as any).__studio.store.getState().zoomToFit());
  await statusShot(page, "lint");
  await statusShot(page, "lint_inspector", "inspector");
  // Auto stops at the page: the capped tag says so under its size
  await select(page, "capped");
  await tab(page, "marker");
  expect((await issueTexts(page, "numbers.size")).some((x) => /capped by the page/.test(x))).toBeTruthy();
  await expect(page.locator('[data-issues-for="numbers.size"] .issue[data-level="error"]')).toHaveCount(0);

  // the Inkjet rows (the Make tab named after the method)
  await select(page, "typed");
  await expect(page.locator('[role="tab"][data-tab="print"]')).toContainText("Inkjet");
  await tab(page, "print");
  for (const [p, label] of [["settings.make.thickness_mm", "Paper thickness"], ["settings.make.page", "Paper size"],
    ["settings.make.page_margin_mm", "Page margins"]]) {
    await expect(page.locator(`[data-row="${p}"] .row-label`)).toHaveText(label);
  }
  for (const p of ["settings.make.margin_mm", "settings.make.cut_line", "settings.mode", "numbers.black_height"]) {
    await expect(page.locator(`[data-row="${p}"]`)).toHaveCount(0);
  }
  expect((await issueTexts(page, "settings.make.thickness_mm")).some((x) => /0\.05 mm into the 0\.1 mm paper/.test(x))).toBeTruthy();
  await statusShot(page, "inkjet_rows", "inspector");
  // a stock suggestion fills the thickness in (a local override: the Preset row reads modified)
  await choose(page, "settings.make.thickness_mm:suggest", "0.18");
  let tg = (await sceneTags(page.request)).find((x: any) => x.name === "typed");
  expect(tg.spec.settings.make.thickness_mm).toBe(0.18);
  expect(tg.plan.sticker.frame_z_mm).toBeCloseTo(0.18, 9);
  await expect(page.locator('.kit-select[data-path="preset"]')).toContainText("This tag (modified)");
  await type(page, "settings.make.thickness_mm", "0.1");
  tg = (await sceneTags(page.request)).find((x: any) => x.name === "typed");
  expect(tg.spec.settings.make.thickness_mm).toBe(0.1);
  // a bigger page clears the lint (A3 prints 277 x 354 mm)
  await choose(page, "settings.make.page", "a3");
  await tab(page, "marker");
  await expect(page.locator('[data-issues-for="numbers.size"] .issue[data-level="error"]')).toHaveCount(0);
  await expect(page.locator('.canvas2d g[data-tag="typed"] [data-guide="cut_line"][data-overpage="1"]')).toHaveCount(0);
});

test("Shift: the inspector's X / Y and the canvas crosshair", async ({ page }) => {
  await page.setViewportSize({ width: 1500, height: 940 });
  await openGallery(page, "shift");
  await light(page);
  await select(page, "moved");
  await tab(page, "marker");
  await expect(page.locator('input[data-path="settings.shift.x_mm"]')).toHaveValue("20");
  await expect(page.locator('input[data-path="settings.shift.y_mm"]')).toHaveValue("8");
  // typed
  await type(page, "settings.shift.y_mm", "-6");
  let t = (await sceneTags(page.request)).find((x: any) => x.name === "moved");
  expect(t.spec.settings.shift).toEqual({ rule: 1, x_mm: 20, y_mm: -6 });
  expect(t.plan.placement.shift_mm).toEqual([20, -6]);
  // dragged: the crosshair 6 mm to the left (0.5 mm steps)
  const h = page.locator('[data-shift-handle="moved"] circle');
  await expect(h).toHaveCount(1);
  const b = (await h.boundingBox())!;
  const z = (await probe(page)).zoom as number;
  const x0 = b.x + b.width / 2, y0 = b.y + b.height / 2;
  await page.mouse.move(x0, y0);
  await page.mouse.down();
  await page.mouse.move(x0 - 3 * z, y0, { steps: 4 });
  await page.mouse.move(x0 - 6 * z, y0, { steps: 4 });
  await statusShot(page, "shift_drag");
  await page.mouse.up();
  await idle(page);
  t = (await sceneTags(page.request)).find((x: any) => x.name === "moved");
  expect(t.spec.settings.shift.x_mm).toBeCloseTo(14, 6);
  expect(t.spec.settings.shift.y_mm).toBeCloseTo(-6, 6);
  // back to where the fit puts it
  await page.getByTestId("shift-reset").click();
  await idle(page);
  t = (await sceneTags(page.request)).find((x: any) => x.name === "moved");
  expect(t.spec.settings.shift ?? null).toBeNull();
  expect(t.plan.placement.shift_mm).toBeUndefined();
  // a 3D tag has no Shift row and no crosshair (3D is a placeholder)
  expect(await page.locator('[data-shift-handle]').count()).toBe(1);
});

test("the Print dialog's Sticker margin and Cut lines", async ({ page }) => {
  await page.setViewportSize({ width: 1500, height: 940 });
  await openGallery(page, "sheet_options");
  await light(page);
  await page.getByTestId("menu-export").click();
  await page.getByTestId("export-sheet").click();
  const dlg = page.getByTestId("dialog-sheet");
  await expect(dlg).toBeVisible();
  // from the file's `sheet`: 3 mm, cut lines on
  await expect(page.locator('input[data-path="sheet.sticker_margin_mm"]')).toHaveValue("3");
  await expect(page.locator('[role="switch"][data-path="sheet.cut_lines"]')).toHaveAttribute("aria-checked", "true");
  const preview = page.getByTestId("sheet-preview");
  await expect(preview.locator("[data-cut]").first()).toBeAttached();
  const j = await (await page.request.get(`${API}/api/scene/sheet.json?page=letter&mode=spaced&sticker_margin_mm=3`)).json();
  expect(j.sticker_margin_mm).toBe(3);
  await statusShot(page, "print_dialog");
  // cut lines off: the preview has none, the stickers stay
  await page.locator('[role="switch"][data-path="sheet.cut_lines"]').click();
  await idle(page);
  await expect(preview.locator("[data-cut]")).toHaveCount(0);
  await expect(page.getByTestId("sheet-stats")).toHaveAttribute("data-stickers", "4");
  // the margin to 0: the stickers shrink back to their plans' outlines
  const area = async () => preview.locator("[data-sticker]").evaluateAll((els) =>
    els.reduce((s, e) => s + Number(e.getAttribute("data-w")) * Number(e.getAttribute("data-h")), 0));
  const before = await area();
  await page.locator('[role="switch"][data-path="sheet.cut_lines"]').click();
  await type(page, "sheet.sticker_margin_mm", "0");
  await expect.poll(area).toBeLessThan(before - 100);
  await page.getByTestId("sheet-close").click();
});
