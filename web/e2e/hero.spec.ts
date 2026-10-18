// The hero video: the primary flow at a watchable pace, recorded from the
// real build (the "hero" project records video at 1280 × 800). A drawn
// cursor follows the mouse, since a headless recording has none.
// Saved to test-results/hero/hero.webm.
import path from "node:path";
import { expect, test } from "@playwright/test";
import { clickAt, coreReady, dragWorld, featureRect, idle, openStudio, toClient } from "./helpers";

const BEAT = 900;

test("hero · plate → face → A → Grid → a suggestion → drag → Print…", async ({ page }) => {
  await page.addInitScript(() => {
    addEventListener("DOMContentLoaded", () => {
      const dot = document.createElement("div");
      dot.style.cssText = "position:fixed;z-index:9999;width:18px;height:18px;margin:-3px 0 0 -3px;pointer-events:none;left:-40px;top:-40px;"
        + "background:no-repeat url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpath d='M2 1l11 6-5 1.4 3 5-2 1.1-3-5L2 13z' fill='%23111' stroke='%23fff' stroke-width='1'/%3E%3C/svg%3E\");";
      document.body.appendChild(dot);
      addEventListener("mousemove", (e) => { dot.style.left = `${e.clientX}px`; dot.style.top = `${e.clientY}px`; }, true);
    });
  });
  const glide = async (x: number, y: number) => { await page.mouse.move(x, y, { steps: 18 }); };

  await openStudio(page);
  await coreReady(page);
  await page.waitForTimeout(BEAT);

  // the plate example
  await page.getByTestId("menu-file").hover();
  await page.getByTestId("menu-file").click();
  await page.waitForTimeout(BEAT / 2);
  await page.getByTestId("cmd-examples").click();
  await page.waitForTimeout(BEAT);
  await page.locator('[data-example="plate"]').hover();
  await page.waitForTimeout(BEAT / 2);
  await page.locator('[data-example="plate"]').click();
  await page.waitForTimeout(BEAT);

  // click the face (inside the material, between the holes): the profile lights up
  const [fx, fy] = await toClient(page, 60, 40);
  await glide(fx - 120, fy + 60);
  await page.waitForTimeout(BEAT / 2);
  await glide(fx, fy);
  await page.waitForTimeout(BEAT / 2);
  await clickAt(page, 60, 40);
  await page.waitForTimeout(BEAT);

  // A: the rectangle is inscribed and the marker fills it
  await page.keyboard.press("a");
  await idle(page);
  await expect(page.locator("[data-marker-black]")).toBeVisible();
  await page.waitForTimeout(BEAT * 2);

  // Grid
  const grid = page.locator('[data-path="marker.type"] [data-value="grid"]');
  await glide(...(await centre(grid)));
  await page.waitForTimeout(BEAT / 2);
  await grid.click();
  await idle(page);
  await page.waitForTimeout(BEAT * 1.5);

  // a suggestion from the dropdown (the second: a different layout than auto's)
  const trigger = page.getByTestId("suggest-trigger");
  await expect(trigger).toBeEnabled();
  await glide(...(await centre(trigger)));
  await page.waitForTimeout(BEAT / 2);
  await trigger.click();
  const sugg = page.getByTestId("suggestion");
  await expect(sugg.first()).toBeVisible();
  await page.waitForTimeout(BEAT);
  const pick = (await sugg.count()) > 1 ? sugg.nth(1) : sugg.first();
  await glide(...(await centre(pick)));
  await page.waitForTimeout(BEAT / 2);
  await pick.click();
  await idle(page);
  await page.waitForTimeout(BEAT * 1.5);

  // drag the rectangle by its edge: the marker follows live
  const r = await featureRect(page);
  const from: [number, number] = [r.cx! - r.w! / 2, r.cy! + r.h! * 0.3];
  await glide(...(await toClient(page, ...from)));
  await page.waitForTimeout(BEAT / 2);
  await dragWorld(page, from, [from[0] + 12, from[1] - 4], 30, 40);
  await idle(page);
  await page.waitForTimeout(BEAT * 1.5);

  // Print…
  await page.getByTestId("panel-ok").click();
  await page.waitForTimeout(BEAT / 2);
  await page.getByTestId("menu-export").click();
  await page.waitForTimeout(BEAT / 2);
  await page.getByTestId("cmd-print").click();
  await expect(page.getByTestId("print-page")).toBeVisible();
  await page.waitForTimeout(BEAT * 3);

  await page.close();
  await page.video()!.saveAs(path.join("test-results", "hero", "hero.webm"));
});

async function centre(loc: import("@playwright/test").Locator): Promise<[number, number]> {
  const b = (await loc.boundingBox())!;
  return [b.x + b.width / 2, b.y + b.height / 2];
}
