// Review finding #1 (2026-10-21): a shared preset file must never run its
// markup. Import checks every field and refuses a bad file; a preset already
// kept in this browser is cleaned on read; the thumbnail draws text as text.
import { expect, test } from "@playwright/test";
import { openPresets, openStudio } from "./helpers";

const EVIL = "</text><image href=\"x\" onerror=\"window.__pwned=1\"/><text>";
const evilPreset = (id: string) => ({
  id, name: "Shared inkjet", method: "inkjet", builtin: false, page: EVIL, page_mm: [215.9, 279.4],
  margin_mm: 6.35, thickness_mm: 0.1, dpi: 600, min_cell_mm: 1, cell_step_mm: 0,
});

test("an imported preset with markup in its paper name is refused and runs nothing", async ({ page }) => {
  await openStudio(page);
  const modal = await openPresets(page);
  await modal.getByTestId("preset-import-file").setInputFiles({
    name: "shared.json", mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify({ format: "arucostudio-web-presets", version: 1, presets: [evilPreset("my:x")] })),
  });
  await expect(modal.locator(".notes")).toContainText(/Import failed: preset 1 .*page/);
  await modal.locator('[data-coll="mine"]').click();
  await expect(modal.locator('.card[data-card^="my:"]')).toHaveCount(0);
  await page.waitForTimeout(300);
  expect(await page.evaluate(() => (window as any).__pwned)).toBeUndefined();
  expect(await modal.locator(".thumb image").count()).toBe(0);
});

test("a preset already kept in this browser with markup in it runs nothing", async ({ page }) => {
  await page.addInitScript((p) => {
    try { window.localStorage.setItem("aruco-web.presets.mine", JSON.stringify([p])); } catch { /* blocked */ }
  }, evilPreset("my:kept"));
  await openStudio(page);
  const modal = await openPresets(page);
  await modal.locator('[data-coll="mine"]').click();
  await page.waitForTimeout(300);
  expect(await page.evaluate(() => (window as any).__pwned)).toBeUndefined();
  expect(await modal.locator(".thumb image").count()).toBe(0);
});
