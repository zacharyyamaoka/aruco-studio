// M3.8 / ST-T-UI-6 and the canvas's editing: select, shift-select, marquee,
// drag (0.5 mm snap), rotate 90, duplicate, delete, undo / redo, keys, pan
// and zoom; then save the scene, reload the page, open it: the same tags at
// the same poses.
import { expect, test } from "@playwright/test";
import { add, fresh, idle, probe, shot } from "./helpers";

async function centreOf(page: any, name: string) {
  const b = (await page.locator(`g[data-tag="${name}"] [data-layer="target"]`).boundingBox())!;
  return [b.x + b.width / 2, b.y + b.height / 2];
}

test("edit on the canvas: select, marquee, drag, rotate, duplicate, delete, undo, redo", async ({ page }) => {
  await fresh(page, "e2e-edit");
  await add(page, "single");
  await add(page, "single");
  await add(page, "grid");
  await page.keyboard.press("Escape");
  await page.keyboard.press("f");
  await idle(page);
  const st0 = await probe(page);

  // click selects, shift-click adds, a click on empty canvas clears
  let [x, y] = await centreOf(page, "tag1");
  await page.mouse.click(x, y);
  expect((await probe(page)).sel).toEqual(["tag1"]);
  [x, y] = await centreOf(page, "tag2");
  await page.keyboard.down("Shift");
  await page.mouse.click(x, y);
  await page.keyboard.up("Shift");
  expect((await probe(page)).sel).toEqual(["tag1", "tag2"]);
  const stage = (await page.locator(".canvas2d").boundingBox())!;
  await page.mouse.click(stage.x + stage.width - 60, stage.y + 60);
  expect((await probe(page)).sel).toEqual([]);

  // marquee over everything
  await page.mouse.move(stage.x + 30, stage.y + 30);
  await page.mouse.down();
  await page.mouse.move(stage.x + stage.width - 30, stage.y + stage.height - 30, { steps: 6 });
  await page.mouse.up();
  expect((await probe(page)).sel.sort()).toEqual(["board1", "tag1", "tag2"]);
  await page.keyboard.press("Escape");

  // drag tag1 by 20 mm right and 10 mm down: snapped to 0.5 mm
  const zoom = (await probe(page)).zoom;
  [x, y] = await centreOf(page, "tag1");
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x + 10 * zoom, y + 5 * zoom, { steps: 4 });
  await page.mouse.move(x + 20.2 * zoom, y + 10.1 * zoom, { steps: 4 });
  await page.mouse.up();
  await idle(page);
  let t1 = (await probe(page)).tags.find((t: any) => t.name === "tag1");
  const t1was = st0.tags.find((t: any) => t.name === "tag1");
  expect(t1.x_mm - t1was.x_mm).toBeCloseTo(20, 5);
  expect(t1.y_mm - t1was.y_mm).toBeCloseTo(-10, 5);
  expect((t1.x_mm * 2) % 1).toBe(0);
  await shot(page, "edit_dragged");

  // rotate 90 (R), arrows nudge, duplicate (Ctrl+D), delete (Del)
  await page.keyboard.press("r");
  await idle(page);
  t1 = (await probe(page)).tags.find((t: any) => t.name === "tag1");
  expect(t1.rotation_deg).toBe(270);
  await page.keyboard.press("ArrowLeft");
  await idle(page);
  expect((await probe(page)).tags.find((t: any) => t.name === "tag1").x_mm).toBeCloseTo(t1.x_mm - 0.5, 6);
  await page.keyboard.press("Control+d");
  await idle(page);
  let p = await probe(page);
  expect(p.tags.length).toBe(4);
  expect(p.sel).toEqual(["tag3"]);
  await page.keyboard.press("Delete");
  await idle(page);
  expect((await probe(page)).tags.map((t: any) => t.name)).toEqual(["tag1", "tag2", "board1"]);

  // undo three times: the copy back, then the nudge, then the turn
  await page.keyboard.press("Control+z");
  await idle(page);
  expect((await probe(page)).tags.length).toBe(4);
  await page.getByTestId("undo").click();
  await idle(page);
  await page.getByTestId("undo").click();
  await idle(page);
  await page.getByTestId("undo").click();
  await idle(page);
  p = await probe(page);
  expect(p.tags.length).toBe(3);
  expect(p.tags.find((t: any) => t.name === "tag1").rotation_deg).toBe(0);
  // redo the turn
  await page.keyboard.press("Control+Shift+z");
  await idle(page);
  expect((await probe(page)).tags.find((t: any) => t.name === "tag1").rotation_deg).toBe(270);

  // the toolbar's own buttons
  await page.locator('[data-ids-row="tag2"]').click();
  await page.getByTestId("rotate").click();
  await idle(page);
  expect((await probe(page)).tags.find((t: any) => t.name === "tag2").rotation_deg).toBe(270);
  await page.getByTestId("duplicate").click();
  await idle(page);
  await page.getByTestId("delete").click();
  await idle(page);
  expect((await probe(page)).tags.length).toBe(3);

  // zoom at the cursor and pan with space-drag
  const z0 = (await probe(page)).zoom;
  await page.mouse.move(stage.x + stage.width / 2, stage.y + stage.height / 2);
  await page.mouse.wheel(0, -300);
  await expect.poll(async () => (await probe(page)).zoom).toBeGreaterThan(z0 * 1.2);
  const c0 = (await probe(page)).center_mm;
  await page.keyboard.down("Space");
  await page.mouse.down();
  await page.mouse.move(stage.x + stage.width / 2 + 100, stage.y + stage.height / 2 + 40, { steps: 4 });
  await page.mouse.up();
  await page.keyboard.up("Space");
  const c1 = (await probe(page)).center_mm;
  const z1 = (await probe(page)).zoom;
  expect(c1[0]).toBeCloseTo(c0[0] - 100 / z1, 3);
  expect(c1[1]).toBeCloseTo(c0[1] + 40 / z1, 3);
});

test("save, reload, open: the same tags at the same poses", async ({ page }) => {
  const name = `e2e-scene-${Date.now()}`;
  await fresh(page, "e2e-save");
  await add(page, "single");
  await add(page, "grid");
  await add(page, "charuco");
  await page.locator('[data-ids-row="board1"]').click();
  await page.keyboard.press("r");
  await page.keyboard.press("ArrowUp");
  await idle(page);
  await page.getByTestId("renumber").click();
  await idle(page);
  const before = (await probe(page)).tags;

  await page.getByTestId("menu-file").click();
  await page.getByTestId("file-saveas").click();
  await page.getByTestId("dialog-name").fill(name);
  await page.getByTestId("dialog-ok").click();
  await idle(page);
  await expect(page.getByTestId("status")).toContainText(`${name}.arucostudio.json`);
  await expect(page.getByTestId("scene-name")).toHaveText(name);

  // a new scene, a reload: nothing on the canvas
  await page.getByTestId("menu-file").click();
  await page.getByTestId("file-new").click();
  await page.getByTestId("dialog-name").fill("empty");
  await page.getByTestId("dialog-ok").click();
  await idle(page);
  await page.reload();
  await expect(page.locator('.app[data-ready="1"]')).toBeVisible();
  await expect(page.locator("g[data-tag]")).toHaveCount(0);

  await page.getByTestId("menu-file").click();
  await page.getByTestId("file-open").click();
  await page.locator(`.scene-item[data-scene="${name}"]`).click();
  await idle(page);
  const after = (await probe(page)).tags;
  expect(after).toEqual(before);
  await expect(page.getByTestId("scene-name")).toHaveText(name);
  await expect(page.locator("g[data-tag]")).toHaveCount(3);
  await shot(page, "scene_reopened");
});
