// M3.6 / ST-T-UI-4: a label on the white, below; dragged on the canvas into
// the detector's clear zone it is refused: an Issue under a Label field, its
// preview in orange (data-state="refused"); Build anyway builds it (label_*).
import { expect, test } from "@playwright/test";
import { choose, fresh, idle, probe, shot, tab, tagOn, type } from "./helpers";

test("label: on the white, dragged into the quiet ring, refused, built anyway", async ({ page }) => {
  await fresh(page, "e2e-label");
  expect(await tagOn(page, "r", "60 60", 3)).toBe("tag1");             // a 60 mm plate, 3 mm thick
  await page.locator('.tog:has(input[data-path="numbers.size:auto"])').click();
  await idle(page);
  await type(page, "numbers.size", "20");
  await tab(page, "label");
  await page.locator('.tog:has(input[data-path="settings.label.on"])').click();
  await idle(page);
  await choose(page, "settings.label.place", "white");
  await choose(page, "settings.label.side", "below");
  const tag = page.locator('g[data-tag="tag1"]');
  const built = tag.locator('[data-layer^="label_"]:not([data-layer="label_preview"])');
  await expect(built.first()).toBeAttached();
  await expect(tag.locator('[data-state="refused"]')).toHaveCount(0);
  await page.keyboard.press("f");
  await idle(page);
  await shot(page, "label_on_white");

  // drag the label up, into the marker's clear zone
  const b = (await tag.locator("[data-label-hit]").first().boundingBox())!;
  const zoom = (await probe(page)).zoom;
  await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2);
  await page.mouse.down();
  await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2 - 2 * zoom, { steps: 3 });
  await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2 - 6 * zoom, { steps: 5 });
  await expect(tag.locator('[data-ghost="label"]')).toBeAttached();
  await page.mouse.up();
  await idle(page);
  const lab = (await probe(page)).doc.tags[0].spec.settings.label;
  expect(lab.position).toBe("manual");
  const err = page.locator('[data-tab-body="label"] [data-issues-for^="settings.label"] .issue[data-level="error"]');
  await expect(err.first()).toBeVisible();
  expect(await err.first().getAttribute("data-field")).toMatch(/^settings\.label/);
  await expect(tag.locator('[data-state="refused"]')).toHaveCount(1);
  await expect(built).toHaveCount(0);
  await shot(page, "label_refused");

  // Build anyway: built where it was asked for, warned
  await page.locator('.tog:has(input[data-path="settings.label.build_anyway"])').click();
  await idle(page);
  await expect(built.first()).toBeAttached();
  await expect(tag.locator('[data-state="refused"]')).toHaveCount(0);
  await expect(page.locator('[data-issues-for="settings.label.build_anyway"] .issue[data-level="warn"]')).toBeVisible();
  await shot(page, "label_built_anyway");
});
