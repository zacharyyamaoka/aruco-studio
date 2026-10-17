// N-3's pictures for docs/status/gallery.md: the gallery and three opened
// examples, light and dark. Written only when ARUCO_GALLERY_SHOTS=1 (the
// full check leaves docs/ alone):
//   cd e2e; $env:ARUCO_GALLERY_SHOTS=1; npx playwright test tests/gallery_shots.spec.ts
import { expect, test, type Page } from "@playwright/test";
import path from "node:path";
import { API, ROOT, idle } from "./helpers";

const OUT = path.join(ROOT, "docs", "status");
const OPEN: [string, "2d" | "3d"][] = [["faces", "2d"], ["labels_charuco", "2d"], ["forearm", "3d"]];

async function theme(page: Page, t: "light" | "dark") {
  await page.evaluate((x) => (window as any).__studio.theme.set(x), t);
  await page.waitForTimeout(150);
}

test("the gallery and three examples, light and dark", async ({ page }) => {
  test.skip(process.env.ARUCO_GALLERY_SHOTS !== "1", "set ARUCO_GALLERY_SHOTS=1 to write docs/status/gallery_*.png");
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 1500, height: 900 });
  for (const t of ["light", "dark"] as const) {
    await page.request.post(`${API}/api/scene/new`, { data: { name: "e2e-gallery-shots" } });
    await page.goto("/");
    await expect(page.locator('.app[data-ready="1"]')).toBeVisible();
    await theme(page, t);
    await expect(page.locator('.gal-thumb[data-state="ready"]')).toHaveCount(await page.locator(".gal-thumb").count(), { timeout: 30_000 });
    await page.screenshot({ path: path.join(OUT, `gallery_landing_${t}.png`) });
    for (const [name, view] of OPEN) {
      if (await page.locator('.app[data-page="studio"]').count()) await page.getByTestId("gallery-button").click();
      await page.locator(`.gal-card[data-example="${name}"]`).click();
      await idle(page);
      if (view === "3d") {
        await page.getByTestId("view-3d").click();
        await idle(page);
        await expect(page.locator('canvas[data-canvas3d="1"]')).toBeVisible();
        await page.waitForTimeout(600);
      }
      await page.waitForTimeout(200);
      await page.screenshot({ path: path.join(OUT, `gallery_${name}_${view}_${t}.png`) });
    }
  }
  await theme(page, "light");
});
