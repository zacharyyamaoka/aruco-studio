// Review finding #9 (2026-10-21): preset fields that do nothing are not
// offered as if they did, and custom paper prints at its own size.
import { expect, test } from "@playwright/test";
import { CORE, coreReady, dragWorld, idle, openPresets, openStudio, state } from "./helpers";

const mine = [
  { id: "my:fdm", name: "My FDM", method: "print3d", builtin: false, nozzle_mm: 0.4, line_mm: 0.45, first_line_mm: 0.5, layer_mm: 0.2, first_layer_mm: 0.2, bed_mm: [250, 210], min_cell_mm: 1.8, cell_step_mm: 0.45 },
  { id: "my:square", name: "Square paper", method: "inkjet", builtin: false, page: "Custom", page_mm: [100, 100], margin_mm: 5, thickness_mm: 0.1, dpi: 600, min_cell_mm: 1, cell_step_mm: 0 },
];

test.beforeEach(async ({ page }) => {
  await page.addInitScript((list) => { try { localStorage.setItem("aruco-web.presets.mine", JSON.stringify(list)); } catch { /* blocked */ } }, mine);
  await openStudio(page);
  await coreReady(page);
});

test("a 3D preset of mine: First line and Bed are disabled, saying not used yet; the rest edit", async ({ page }) => {
  const modal = await openPresets(page);
  await modal.locator('[data-coll="mine"]').click();
  await modal.locator('.card[data-card="my:fdm"]').click();
  const info = modal.getByTestId("preset-info");
  for (const k of ["first_line_mm", "bed_mm.0", "bed_mm.1"]) await expect(info.locator(`input[data-path="preset.${k}"]`), k).toBeDisabled();
  await expect(info.getByTestId("preset-unused-first_line_mm")).toHaveText("not used yet");
  await expect(info.getByTestId("preset-unused-bed_mm")).toHaveText("not used yet");
  await expect(info.locator('input[data-path="preset.line_mm"]')).toBeEnabled();
});

test("custom 100 × 100 mm paper: the sheet is 100 × 100 mm, not Letter", async ({ page }) => {
  test.skip(CORE === "mock", "the sheet is the real core's");
  const modal = await openPresets(page);
  await modal.locator('[data-coll="mine"]').click();
  await modal.locator('.card[data-card="my:square"]').click();
  await page.getByTestId("presets-select").click();
  expect((await state(page)).doc.default_preset.id).toBe("my:square");
  await page.keyboard.press("r");
  await dragWorld(page, [10, 10], [40, 40]);
  await page.keyboard.press("a");
  await idle(page);
  await page.getByTestId("panel-ok").click();
  await idle(page);
  await page.keyboard.press("p");
  await expect(page.getByTestId("print-go")).toBeEnabled({ timeout: 30_000 });
  await expect(page.getByTestId("print-page")).toHaveAttribute("data-page-mm", "100x100");
});
