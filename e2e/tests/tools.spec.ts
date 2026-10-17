// The tools beyond the done checks: a rectangle dragged, a polygon closed on
// its first point, a point added (Alt+click) and removed (Del), a
// rectangular hole clicked, a shape copied, nudged, deleted with what stands
// on it; a tag deleted (its shape stays); the gizmo's ring turns a sketch
// 15° at a time; a circle's side refuses a tag; the File drawer lights the
// selection.
import { expect, test } from "@playwright/test";
import { centre, dragPx, freshFile, idle, probe, readFile, screenOf, shot } from "./helpers";

test("tools: drag a box, close a polygon, points, a rectangular hole, copy, nudge, delete", async ({ page }) => {
  const file = await freshFile(page, "e2e-tools");
  // R, a dragged box 30 x 20 from (-60, 10) to (-30, -10)
  await page.keyboard.press("r");
  await dragPx(page, await screenOf(page, -60, 10), await screenOf(page, -30, -10));
  let f = readFile(file);
  expect(f.sketches[0].shapes[0].rect).toEqual([30, 20]);
  expect(f.sketches[0].at).toEqual([-45, 0]);
  expect((await probe(page)).tool).toBe("select");

  // Shift+H, typed 10 6, a click inside: a rectangular hole there
  await page.keyboard.press("Shift+H");
  await page.keyboard.type("10 6");
  await page.mouse.click(...(await screenOf(page, -50, 2)));
  await idle(page);
  f = readFile(file);
  expect(f.sketches[0].shapes[0].holes).toEqual([{ rect: [10, 6], at: [-5, 2] }]);

  // P: three clicks, then a click on the first point closes it
  await page.keyboard.press("p");
  for (const [x, y] of [[10, 0], [40, 0], [25, 30]]) await page.mouse.click(...(await screenOf(page, x, y)));
  await page.mouse.click(...(await screenOf(page, 10, 0)));
  await idle(page);
  f = readFile(file);
  const poly = f.sketches[1];
  expect(poly.shapes[0].polygon).toHaveLength(3);
  // Alt+click its bottom edge: a fourth point; drag it; Del removes it again
  await page.keyboard.down("Alt");
  await page.mouse.click(...(await screenOf(page, 25, 0.3)));
  await page.keyboard.up("Alt");
  await idle(page);
  expect(readFile(file).sketches[1].shapes[0].polygon).toHaveLength(4);
  const v1 = await centre(page, '[data-handle="v1"]');
  await dragPx(page, v1, [v1[0], v1[1] + 20]);
  expect(readFile(file).sketches[1].shapes[0].polygon).toHaveLength(4);
  await page.keyboard.press("Delete");
  await idle(page);
  expect(readFile(file).sketches[1].shapes[0].polygon).toHaveLength(3);
  await shot(page, "m8b1_tools_polygon");

  // the box: A (a tag on it), then copy the box (Ctrl+D), nudge the copy, delete it
  await page.mouse.click(...(await screenOf(page, -58, -8)));
  await expect.poll(async () => (await probe(page)).shapeSel).toEqual(["rect1"]);
  await page.keyboard.press("a");
  await page.keyboard.press("Enter");
  await idle(page);
  expect((await probe(page)).sel).toEqual(["tag1"]);
  await page.getByTestId("aruco-shape").click();
  await page.keyboard.press("Control+d");
  await idle(page);
  f = readFile(file);
  expect(f.features.map((x: any) => x.id)).toEqual(["tag1", "tag2"]);
  expect(f.features[1].aruco).toBe("rect2");
  const copy = (await probe(page)).shapeSel[0];
  expect(copy).toBe("rect2");
  const at0 = readFile(file).sketches[2].at;
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("Shift+ArrowUp");
  await idle(page);
  expect(readFile(file).sketches[2].at).toEqual([at0[0] + 0.5, at0[1] + 5]);
  await page.keyboard.press("Delete");
  await idle(page);
  f = readFile(file);
  expect(f.sketches).toHaveLength(2);
  expect(f.features.map((x: any) => x.id)).toEqual(["tag1"]);

  // a tag deleted: its feature goes, its shape stays
  await page.locator('[data-ids-row="tag1"]').click();
  await page.keyboard.press("Delete");
  await idle(page);
  f = readFile(file);
  expect(f.features).toEqual([]);
  expect(f.sketches[0].shapes[0].id).toBe("rect1");
  await shot(page, "m8b1_tools_after_delete");
});

test("tools in 3D: the gizmo's ring turns the sketch; a circle's side has no face; the File drawer lights the selection", async ({ page }) => {
  const file = await freshFile(page, "e2e-tools3d", JSON.stringify({
    schema: "arucostudio.scene/2", name: "t",
    sketches: [{ id: "sk", shapes: [{ id: "box", rect: [60, 40] }] }, { id: "sk2", at: [70, 0], shapes: [{ id: "disc", circle: 40 }] }],
    features: [{ id: "b1", extrude: "box", height: 10 }, { id: "b2", extrude: "disc", height: 10 }],
  }, null, 1) + "\n");
  await page.keyboard.press("f");
  await idle(page);
  await page.mouse.click(...(await screenOf(page, 0, 0)));
  await expect.poll(async () => (await probe(page)).shapeSel).toEqual(["box"]);
  await page.getByTestId("sb-file").click();
  await expect(page.getByTestId("file-lit")).toHaveText("sketches[0].shapes[0]");
  await expect(page.locator(".file-text .fl.lit").first()).toBeVisible();
  await shot(page, "m8b1_tools_file_lit");
  await page.getByTestId("sb-file").click();
  await page.getByTestId("view-3d").click();
  await idle(page);
  await page.waitForTimeout(400);
  const g = await page.evaluate(() => (window as any).__studio3d.gizmo());
  // drag the ring a quarter turn about the centre (counter-clockwise on screen)
  const r = [g.ring[0] - g.centre[0], g.ring[1] - g.centre[1]];
  const to = [g.centre[0] + r[1] * 0.9 + r[0] * 0.45, g.centre[1] - r[0] * 0.9 + r[1] * 0.45];
  await dragPx(page, g.ring, [to[0], to[1]], 12);
  await page.waitForTimeout(200);
  await idle(page);
  const rot = readFile(file).sketches[0].rot;
  expect(rot).toBeTruthy();
  expect(rot % 15).toBe(0);
  await shot(page, "m8b1_tools_gizmo_turned");
  // A on the disc's side: refused, it is curved
  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");
  await page.keyboard.press("a");
  await page.waitForTimeout(200);
  const side = await page.evaluate(() => (window as any).__studio3d.project(70, -19.9, 5));
  await page.mouse.click(side[0], side[1]);
  await idle(page);
  await expect(page.getByTestId("status")).toContainText(/curved|no flat face/);
  expect((await probe(page)).picks).not.toContain("b2.side0");
});
