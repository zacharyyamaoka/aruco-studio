// M3.5 / ST-T-UI-3: 2D -> 3D -> 2D keeps the view's centre (within 1 px);
// the store's zRange[1] is the plan's top for a raised tag (within 0.01
// mm); a screenshot of each type in each view; a click selects in 3D.
import { expect, test } from "@playwright/test";
import { API, add, choose, fresh, idle, probe, shot, tab } from "./helpers";

test("2D / 3D toggle keeps the centre; the 3D view shows the heights", async ({ page, request }) => {
  await fresh(page, "e2e-views");
  await add(page, "single");
  // raised: White + black, New body, the white 2 mm over the face
  await tab(page, "heights");
  await choose(page, "settings.mode", "both");
  await choose(page, "settings.op", "new");
  await add(page, "grid");
  await add(page, "charuco");
  await page.keyboard.press("Escape");
  await page.keyboard.press("f");
  await idle(page);
  await shot(page, "2d_view");

  const before = await probe(page);
  await page.getByTestId("view-3d").click();
  await idle(page);
  await expect(page.locator('canvas[data-canvas3d="1"]')).toBeVisible();
  await page.waitForTimeout(400);
  const in3d = await probe(page);
  expect(in3d.view).toBe("3d");
  expect(Math.abs(in3d.center[0] - before.center[0])).toBeLessThanOrEqual(1);
  expect(Math.abs(in3d.center[1] - before.center[1])).toBeLessThanOrEqual(1);
  await shot(page, "3d_view");

  // zRange[1] = the raised tag's top, as /api/plan says
  const t = before.doc.tags.find((x: any) => x.name === "tag1");
  const p = await (await request.post(`${API}/api/plan?mesh=1`, { data: t.spec })).json();
  const top = Math.max(...p.layers.filter((L: any) => L.op !== "keep").map((L: any) => L.z[1]));
  expect(top).toBeGreaterThan(1.9);
  const z = (await probe(page)).zRange;
  expect(Math.abs(z[1] - top)).toBeLessThanOrEqual(0.01);
  // the 3D view draws the server's mesh: every tag has one
  const meshes = await page.evaluate(() => (window as any).__studio.store.getState().scene.tags.map((x: any) => (x.plan?.mesh || []).length));
  expect(meshes.every((n: number) => n > 0)).toBeTruthy();

  // a click on the middle tag selects it in 3D
  await page.keyboard.press("Escape");
  await page.locator('[data-ids-row="board1"]').dblclick();     // zoom to it (the camera follows)
  await page.getByTestId("view-2d").click();
  await idle(page);
  await page.getByTestId("view-3d").click();
  await idle(page);
  await page.keyboard.press("Escape");
  const box = (await page.locator('canvas[data-canvas3d="1"]').boundingBox())!;
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  await expect.poll(async () => (await probe(page)).sel).toEqual(["board1"]);
  await page.locator("select[data-testid=zscale]").selectOption("5");
  await shot(page, "3d_selected_z5");

  // back to 2D: the centre where it was
  const c3 = (await probe(page)).center;
  await page.getByTestId("map-toggle").click();
  await idle(page);
  const after = await probe(page);
  expect(after.view).toBe("2d");
  expect(Math.abs(after.center[0] - c3[0])).toBeLessThanOrEqual(1);
  expect(Math.abs(after.center[1] - c3[1])).toBeLessThanOrEqual(1);

  // each type alone, 2D and 3D
  for (const name of ["tag1", "board1", "charuco1"]) {
    await page.locator(`[data-ids-row="${name}"]`).dblclick();
    await idle(page);
    await shot(page, `2d_${name}`);
    await page.keyboard.press("Tab");
    await idle(page);
    await page.waitForTimeout(400);
    await shot(page, `3d_${name}`);
    await page.keyboard.press("Tab");
    await idle(page);
  }
});
