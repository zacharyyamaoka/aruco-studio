// M8b1.1 / M8b1.2: the mini CAD. R 80 50, H 18, E 5, A on the top face: the
// file on disk holds the plate, and it plans to the same digests as
// examples/plate_charuco.arucostudio.json once the example's sugar is typed
// in. The handles: every shape kind's handles write their numbers (0.5 mm,
// 15°), and a wider rectangle gives its tag a larger marker.
import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { API, ROOT, centre, dragPx, freshFile, idle, probe, readFile, sceneTags, screenOf, shot } from "./helpers";

test("M8b1.1 R 80 50 · H 18 · E 5 · A on the top: the file holds the plate, the example's digests", async ({ page, request }) => {
  const file = await freshFile(page, "e2e-plate");
  await page.keyboard.press("r");
  await expect(page.getByTestId("tool-rect")).toHaveAttribute("data-active", "1");
  await page.keyboard.type("80 50");
  await expect(page.getByTestId("typed")).toContainText("80 50");
  await shot(page, "m8b1_sketch_typing");
  await page.keyboard.press("Enter");
  await idle(page);
  let f = readFile(file);
  expect(f.sketches).toHaveLength(1);
  expect(f.sketches[0].shapes).toHaveLength(1);
  expect(f.sketches[0].shapes[0].rect).toEqual([80, 50]);
  await expect(page.locator("[data-shape]")).toHaveCount(1);
  await expect(page.locator("[data-shape]")).toHaveAttribute("data-points", "4");
  const rectId = f.sketches[0].shapes[0].id;
  expect((await probe(page)).shapeSel).toEqual([rectId]);

  // H, 18: a round hole at the selected shape's centre
  await page.keyboard.press("h");
  await page.keyboard.type("18");
  await page.keyboard.press("Enter");
  await idle(page);
  f = readFile(file);
  expect(f.sketches[0].shapes[0].holes).toEqual([{ circle: 18 }]);
  await expect(page.locator("[data-hole]")).toHaveCount(1);
  await shot(page, "m8b1_sketch_rect_hole");

  // E, 5: an Extrude, and the view goes 3D
  await page.keyboard.press("e");
  await page.keyboard.type("5");
  await page.keyboard.press("Enter");
  await idle(page);
  f = readFile(file);
  expect(f.features).toEqual([{ id: "body1", extrude: rectId, height: 5 }]);
  expect((await probe(page)).view).toBe("3d");
  await expect(page.locator('canvas[data-canvas3d="1"]')).toBeVisible();
  await page.waitForTimeout(300);
  await shot(page, "m8b1_sketch_extruded_3d");

  // A, a click on the top face, Enter: a tag
  await page.keyboard.press("a");
  await page.waitForTimeout(200);
  const top = await page.evaluate(() => (window as any).__studio3d.screenOf("body1.top"));
  await page.mouse.click(top[0], top[1]);
  await expect.poll(async () => (await probe(page)).picks).toEqual(["body1.top"]);
  await shot(page, "m8b1_sketch_aruco_pick_top");
  await page.keyboard.press("Enter");
  await idle(page);
  f = readFile(file);
  expect(f.features).toHaveLength(2);
  expect(f.features[1].aruco).toBe("body1.top");
  const tagId = f.features[1].id;
  expect((await probe(page)).sel).toEqual([tagId]);
  await expect(page.getByTestId("aruco-on")).toContainText("body1.top");
  await page.waitForTimeout(300);
  await shot(page, "m8b1_sketch_tag_3d");

  // the example's sugar typed into the Studio's file (as a person or an AI
  // would): the same plan, digest for digest
  const exText = fs.readFileSync(path.join(ROOT, "examples", "plate_charuco.arucostudio.json"), "utf-8");
  const ex = JSON.parse(exText);
  const sugar = { ...ex.features[1] };
  delete sugar.id;
  delete sugar.aruco;
  f.preset = ex.preset;
  Object.assign(f.features[1], sugar);
  fs.writeFileSync(file, JSON.stringify(f, null, 1) + "\n", "utf-8");
  await expect.poll(async () => (await probe(page)).file?.preset, { timeout: 5000 }).toBe(ex.preset);
  await idle(page);
  const mine = (await sceneTags(request)).find((t: any) => t.name === tagId);
  const theirs = (await (await request.post(`${API}/api/design/preview`, { data: { text: exText } })).json()).scene.tags[0];
  expect(mine.plan.ok).toBeTruthy();
  expect(mine.plan.digest).toBe(theirs.plan.digest);
  expect(mine.spec.target).toEqual(theirs.spec.target);
  await page.getByTestId("view-2d").click();
  await idle(page);
  await page.keyboard.press("f");
  await shot(page, "m8b1_sketch_plate_2d");
});

test("M8b1.2 handles: the rectangle's edge, a polygon vertex, a circle's rim, a slot's end, the turn", async ({ page, request }) => {
  const file = await freshFile(page, "e2e-handles");
  // a 40 x 60 rectangle with a single marker on it (the width limits the marker)
  await page.keyboard.press("r");
  await page.keyboard.type("40 60");
  await page.keyboard.press("Enter");
  await idle(page);
  await page.keyboard.press("a");
  await page.keyboard.press("Enter");
  await idle(page);
  let f = readFile(file);
  const tag = f.features[0].id;
  const size0 = (await sceneTags(request)).find((t: any) => t.name === tag).plan.marker.marker_length_m;
  await page.getByTestId("aruco-shape").click();                       // the shape under the tag
  const rect = f.sketches[0].shapes[0].id;
  expect((await probe(page)).shapeSel).toEqual([rect]);
  await expect(page.locator("[data-handle]")).toHaveCount(9);           // 8 + the turn
  await shot(page, "m8b1_handles_rect");
  const zoom = (await probe(page)).zoom;
  const e = await centre(page, '[data-handle="e"]');
  await dragPx(page, e, [e[0] + 10 * zoom, e[1] + 3], 8);
  f = readFile(file);
  expect(f.sketches[0].shapes[0].rect).toEqual([50, 60]);
  expect(f.sketches[0].shapes[0].at).toEqual([5, 0]);                    // the left edge stayed
  const size1 = (await sceneTags(request)).find((t: any) => t.name === tag).plan.marker.marker_length_m;
  expect(size1).toBeGreaterThan(size0);
  await shot(page, "m8b1_handles_rect_wider");

  // the turn: the handle past the top edge, dragged about the centre to ~30°
  const c = await screenOf(page, 5, 0);
  const rot = await centre(page, '[data-handle="rot"]');
  const r = Math.hypot(rot[0] - c[0], rot[1] - c[1]);
  const a = (120 * Math.PI) / 180;                                        // 30° past straight up
  await dragPx(page, rot, [c[0] + r * Math.cos(a) + 2, c[1] - r * Math.sin(a) + 1], 8);
  f = readFile(file);
  expect(f.sketches[0].shapes[0].rot).toBe(30);
  await shot(page, "m8b1_handles_rect_turned");

  // a circle, drawn by dragging its diameter, then its rim
  await page.keyboard.press("Escape");
  await page.keyboard.press("c");
  await dragPx(page, await screenOf(page, 60, 0), await screenOf(page, 90, 0));
  f = readFile(file);
  const circle = f.sketches[1].shapes[0];
  expect(circle.circle).toBe(30);
  expect(f.sketches[1].at).toEqual([75, 0]);
  const rim = await centre(page, '[data-handle="rim"]');
  await dragPx(page, rim, [rim[0] + 5 * zoom, rim[1]]);
  expect(readFile(file).sketches[1].shapes[0].circle).toBe(40);

  // a slot: O, typed 40 12 (at the view's centre), then its right end
  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");
  await page.evaluate(() => (window as any).__studio.store.getState().setCamera({ cx: 0, cy: -70 }));
  await page.keyboard.press("o");
  await page.keyboard.type("40 12");
  await page.keyboard.press("Enter");
  await idle(page);
  f = readFile(file);
  expect(f.sketches[2].shapes[0].slot).toEqual([40, 12]);
  expect(f.sketches[2].at).toEqual([0, -70]);
  const end = await centre(page, '[data-handle="end1"]');
  await dragPx(page, end, [end[0] + 5 * zoom, end[1]]);
  f = readFile(file);
  expect(f.sketches[2].shapes[0].slot).toEqual([45, 12]);
  expect(f.sketches[2].shapes[0].at).toEqual([2.5, 0]);

  // a polygon: four clicks, Enter; then its first vertex
  await page.keyboard.press("Escape");
  await page.keyboard.press("p");
  for (const [x, y] of [[-90, -40], [-60, -40], [-60, -10], [-90, -20]]) await page.mouse.click(...(await screenOf(page, x, y)));
  await expect(page.getByTestId("draft-points")).toContainText("4 points");
  await shot(page, "m8b1_handles_polygon_draft");
  await page.keyboard.press("Enter");
  await idle(page);
  f = readFile(file);
  const poly = f.sketches[3];
  expect(poly.shapes[0].polygon).toHaveLength(4);
  const v0 = await centre(page, '[data-handle="v0"]');
  await dragPx(page, v0, [v0[0] - 5 * zoom, v0[1] + 5 * zoom]);
  f = readFile(file);
  const p0 = f.sketches[3].shapes[0].polygon[0];
  const at = f.sketches[3].at;
  expect([p0[0] + at[0], p0[1] + at[1]]).toEqual([-95, -45]);
  await page.keyboard.press("f");
  await shot(page, "m8b1_handles_all");
});
