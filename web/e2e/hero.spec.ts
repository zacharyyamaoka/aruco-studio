// The hero video: the V1 primary flow at a watchable pace, recorded from the
// real build (the "hero" project records video at 1280 × 800). A drawn
// cursor follows the mouse, since a headless recording has none.
//
//   E2E_BASE_URL=https://arucostudio.com npx playwright test --project=hero
//
// Saved to HERO_OUT (default test-results/hero/hero.webm), with the moment of
// each step beside it (<same name>.marks.json, seconds from the page's
// start): docs/build_v1_report.py cuts the waits (the core loading, OpenCV
// loading) by them.
// WHY these steps (Zach's V1 pick, 2026-10-18): click-to-inspect (the panel
// beside the marker), words not icons, a dimension typed on the sketch
// (grey driven -> solid set), the Label tab (multi-line, typed offset), the
// Sheet's Fewest cuts | Fewest sheets, and Verify's Tilt as the manual sweep.
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { expect, test, type Locator } from "@playwright/test";
import { clickAt, coreReady, idle, openStudio, state, toClient } from "./helpers";

const BEAT = 800;
const OUT = process.env.HERO_OUT ?? path.join("test-results", "hero", "hero.webm");

test("hero · plate → face → A (panel beside) → Grid → type the marker size → Label → Sheet → Verify Tilt", async ({ page }) => {
  test.setTimeout(240_000);
  const t0 = Date.now();
  const marks: Record<string, number> = {};
  const mark = (k: string) => { marks[k] = +((Date.now() - t0) / 1000).toFixed(2); };
  await page.addInitScript(() => {
    addEventListener("DOMContentLoaded", () => {
      const dot = document.createElement("div");
      dot.style.cssText = "position:fixed;z-index:99999;width:18px;height:18px;margin:-3px 0 0 -3px;pointer-events:none;left:-40px;top:-40px;"
        + "background:no-repeat url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpath d='M2 1l11 6-5 1.4 3 5-2 1.1-3-5L2 13z' fill='%23111' stroke='%23fff' stroke-width='1'/%3E%3C/svg%3E\");";
      document.body.appendChild(dot);
      addEventListener("mousemove", (e) => { dot.style.left = `${e.clientX}px`; dot.style.top = `${e.clientY}px`; }, true);
    });
  });
  const glide = async (x: number, y: number) => { await page.mouse.move(x, y, { steps: 16 }); };
  const centre = async (loc: Locator): Promise<[number, number]> => {
    const b = (await loc.boundingBox())!;
    return [b.x + b.width / 2, b.y + b.height / 2];
  };
  const glideClick = async (loc: Locator) => {
    await glide(...(await centre(loc)));
    await page.waitForTimeout(BEAT / 3);
    await loc.click();
  };

  await openStudio(page);
  mark("open");
  await coreReady(page);
  mark("core_ready");
  await page.waitForTimeout(BEAT / 2);

  // 1 · the main menu › File › Examples › Plate
  await glideClick(page.getByTestId("menu-main"));
  await page.waitForTimeout(BEAT / 3);
  await glide(...(await centre(page.getByTestId("menu-file"))));
  await page.waitForTimeout(BEAT / 2);
  await glideClick(page.getByTestId("cmd-examples"));
  await page.waitForTimeout(BEAT / 2);
  await glideClick(page.locator('[data-example="plate"]'));
  await expect(page.getByTestId("examples-dialog")).toHaveCount(0);
  mark("plate");
  await page.waitForTimeout(BEAT);

  // 2 · click the face (between the holes), then A: the panel opens beside the marker
  const [fx, fy] = await toClient(page, 60, 40);
  await glide(fx - 140, fy + 50);
  await glide(fx, fy);
  await page.waitForTimeout(BEAT / 3);
  await clickAt(page, 60, 40);
  await expect.poll(async () => (await state(page)).sel?.kind).toBe("profile");
  await page.waitForTimeout(BEAT / 2);
  await page.keyboard.press("a");
  await idle(page);
  await expect(page.locator("[data-marker-black]")).toBeVisible();
  await expect(page.getByTestId("extrude-panel")).toBeVisible();
  mark("panel");
  await page.waitForTimeout(BEAT * 1.5);

  // 3 · the Marker tab (a new feature opens on Make), then Type: the "Grid" word
  await glideClick(page.locator('[role=tab][data-tab="marker"]'));
  await page.waitForTimeout(BEAT / 2);
  await glideClick(page.locator('[data-path="marker.type"] [data-value="grid"]'));
  await idle(page);
  mark("grid");
  await page.waitForTimeout(BEAT * 1.2);

  // 4 · the marker size, typed into its dimension on the sketch: grey (driven) -> solid (set)
  const dimLabel = page.locator('[data-dim-label="marker.marker_mm"]');
  await expect(dimLabel).toBeVisible();
  await glideClick(dimLabel);
  const dim = page.getByTestId("dim-input");
  await expect(dim).toBeVisible();
  await page.waitForTimeout(BEAT / 2);
  await dim.press("Control+a");
  await page.keyboard.type("16", { delay: 220 });
  await page.waitForTimeout(BEAT / 2);
  await dim.press("Enter");
  await expect(dim).toHaveCount(0);
  await idle(page);
  await expect(page.locator('[data-dim="marker.marker_mm"]')).toHaveAttribute("data-set", "1");
  mark("dim_set");
  await page.waitForTimeout(BEAT * 1.5);

  // 5 · the Label tab: two lines, then X offset
  await glideClick(page.locator('[role=tab][data-tab="label"]'));
  await page.waitForTimeout(BEAT / 2);
  const text = page.locator('textarea[data-path="label.text"]');
  await glideClick(text);
  await text.press("Control+a");
  await page.keyboard.type("PLATE", { delay: 110 });
  await page.keyboard.press("Enter");
  await page.keyboard.type("#{ids}", { delay: 110 });
  await page.waitForTimeout(BEAT / 3);
  const x = page.locator('input[data-path="label.offset_mm.x"]');
  await glideClick(x);              // the textarea commits on blur
  await idle(page);
  await x.press("Control+a");
  await page.keyboard.type("3", { delay: 200 });
  await x.press("Enter");
  await idle(page);
  expect((await state(page)).feature.label.offset_mm).toEqual([3, 0]);
  mark("label");
  await page.waitForTimeout(BEAT * 1.5);

  // 6 · Sheet: Fewest cuts | Fewest sheets
  await glideClick(page.getByTestId("act-print"));
  await expect(page.locator('[data-testid="print-page"] svg')).toBeVisible({ timeout: 45_000 });
  await idle(page);
  mark("sheet");
  await page.waitForTimeout(BEAT);
  const objective = page.getByTestId("sheet-objective");
  await glideClick(objective.locator('[data-value="fewest_cuts"]'));
  await expect(objective).toHaveAttribute("data-value", "fewest_cuts");
  await idle(page);
  await page.waitForTimeout(BEAT);
  await glideClick(objective.locator('[data-value="fewest_sheets"]'));
  await expect(objective).toHaveAttribute("data-value", "fewest_sheets");
  await idle(page);
  mark("sheet_toggled");
  await page.waitForTimeout(BEAT);
  await page.keyboard.press("Escape");
  await expect.poll(async () => (await state(page)).modal).toBeNull();
  await page.waitForTimeout(BEAT / 2);

  // 7 · Verify: OpenCV reads the marker; drag Tilt by hand (the manual sweep)
  await glideClick(page.getByTestId("act-verify"));
  await expect(page.getByTestId("verify-dialog")).toBeVisible();
  mark("verify_open");
  await expect(page.getByTestId("verify-image")).toBeVisible({ timeout: 90_000 });
  await expect(page.locator('.vf-frame[data-busy="0"]')).toHaveCount(1, { timeout: 60_000 });
  mark("verify_image");
  await page.waitForTimeout(BEAT);
  const tilt = page.locator('input[data-knob="tilt_deg"]');
  const box = (await tilt.boundingBox())!;
  const y = box.y + box.height / 2;
  const xAt = (v: number) => box.x + 8 + ((box.width - 16) * v) / 85;
  await glide(xAt(0), y);
  await page.waitForTimeout(BEAT / 3);
  await page.mouse.down();
  for (let i = 1; i <= 30; i++) { await page.mouse.move(xAt((65 * i) / 30), y); await page.waitForTimeout(90); }
  await page.waitForTimeout(BEAT / 2);
  for (let i = 1; i <= 15; i++) { await page.mouse.move(xAt(65 - (35 * i) / 15), y); await page.waitForTimeout(90); }
  await page.mouse.up();
  await expect(page.locator('.vf-frame[data-busy="0"]')).toHaveCount(1, { timeout: 60_000 });
  mark("tilt_done");
  await page.waitForTimeout(BEAT * 2);
  mark("end");

  await page.close();
  mkdirSync(path.dirname(OUT), { recursive: true });
  await page.video()!.saveAs(OUT);
  writeFileSync(OUT.replace(/\.webm$/, "") + ".marks.json", JSON.stringify(marks, null, 2));
});
