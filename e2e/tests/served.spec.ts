// The built app as the server serves it on 5360 (studio/dist at /), the
// keyboard map, and the 3D view's canvas from the built bundle. Skipped
// when the server was started before `npm run build` (it mounts dist at
// start).
import { expect, test } from "@playwright/test";
import { API, SCREENS, add } from "./helpers";
import path from "node:path";

test("the server serves the built Studio on 5360", async ({ page, request }) => {
  const r = await request.get(`${API}/`);
  test.skip(!r.ok() || !(await r.text()).includes('id="root"'), "studio/dist was not built when the server started");
  await request.post(`${API}/api/scene/new`, { data: { name: "e2e-served" } });
  await page.goto(`${API}/`);
  await expect(page.locator('.app[data-ready="1"]')).toBeVisible();
  await add(page, "charuco");
  await expect(page.locator('g[data-tag="charuco1"] [data-layer="pattern"]')).toHaveCount(1);
  await page.keyboard.press("?");
  await expect(page.getByTestId("drawer-messages")).toBeVisible();
  await expect(page.locator("table.keys")).toContainText("2D / 3D");
  await page.screenshot({ path: path.join(SCREENS, "served_keys.png") });
  // Tab toggles 2D / 3D from the canvas, not from a focused button (audit F18)
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
  await page.keyboard.press("Tab");
  await expect(page.locator('canvas[data-canvas3d="1"]')).toBeVisible();
});
