// M8b1.6 / M8b1.7: 3D. The gizmo moves a sketch's `at` in 0.5 mm steps; the
// extrude arrow changes `height`; a tag on forearm.right stands on +x and is
// drawn in 2D as a flap with its hinge. A with four Shift-clicked faces,
// then Enter: one feature with a four-face list, four tags, and Renumber
// makes their ids unique.
import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { ROOT, centre, dragPx, freshFile, idle, palette, probe, readFile, screenOf, shot } from "./helpers";

const plate = JSON.stringify({
  schema: "arucostudio.scene/2", name: "plate",
  sketches: [{ id: "sk", shapes: [{ id: "plate", rect: [80, 50] }] }],
  features: [{ id: "body", extrude: "plate", height: 5 }, { id: "tag", aruco: "body.top", layout: "single" }],
}, null, 1) + "\n";

test("M8b1.6 the gizmo moves the sketch, the arrow sets the height; forearm.right stands on +x", async ({ page }) => {
  const file = await freshFile(page, "e2e-drag3d", plate);
  await page.keyboard.press("f");
  await idle(page);
  await page.mouse.click(...(await screenOf(page, -37, 22)));            // the plate, outside its marker
  await expect.poll(async () => (await probe(page)).shapeSel).toEqual(["plate"]);
  await page.getByTestId("view-3d").click();
  await idle(page);
  await page.waitForTimeout(400);
  const v = await page.evaluate(() => (window as any).__studio3d);
  expect(v.gizmoOn).toBe("sk");
  expect(v.arrowOn).toBe("body");
  await shot(page, "m8b1_3d_gizmo");

  // the gizmo's X arrow, dragged along its own screen direction
  const g = await page.evaluate(() => (window as any).__studio3d.gizmo());
  const dir = [g.x[0] - g.centre[0], g.x[1] - g.centre[1]];
  const len = Math.hypot(dir[0], dir[1]);
  await dragPx(page, g.x, [g.x[0] + (dir[0] / len) * 90, g.x[1] + (dir[1] / len) * 90], 10);
  await page.waitForTimeout(200);
  await idle(page);
  let f = readFile(file);
  const at = f.sketches[0].at;
  expect(at).toBeTruthy();
  expect(at[0]).toBeGreaterThan(1);
  expect((at[0] * 2) % 1).toBe(0);                                       // 0.5 mm steps
  expect(at[1]).toBe(0);
  const tagX = (await probe(page)).tags.find((t: any) => t.name === "tag").x_mm;
  expect(tagX).toBeCloseTo(at[0], 6);                                    // the tag went with it
  await shot(page, "m8b1_3d_gizmo_moved");

  // the extrude arrow, dragged up
  await page.waitForTimeout(200);
  const a = await page.evaluate(() => (window as any).__studio3d.arrow());
  expect(a).toBeTruthy();
  await dragPx(page, a, [a[0], a[1] - 60], 10);
  await page.waitForTimeout(200);
  await idle(page);
  f = readFile(file);
  const h = f.features[0].height;
  expect(h).toBeGreaterThan(5);
  expect((h * 2) % 1).toBe(0);
  await page.waitForTimeout(300);
  await shot(page, "m8b1_3d_arrow_height");

  // the forearm: tag.right's normal is +x in 3D; in 2D a flap with a hinge
  const forearm = fs.readFileSync(path.join(ROOT, "examples", "forearm.arucostudio.json"), "utf-8");
  await idle(page);
  fs.writeFileSync(file, forearm, "utf-8");
  await expect.poll(async () => (await probe(page)).tags.length, { timeout: 10000 }).toBe(4);
  await page.waitForFunction(() => Object.keys((window as any).__studio3d?.normals || {}).length === 4, null, { timeout: 10000 });
  const normals = await page.evaluate(() => (window as any).__studio3d.normals);
  expect(normals["tag.right"]).toEqual([1, 0, 0]);
  expect(normals["tag.front"]).toEqual([0, -1, 0]);
  expect(normals["tag.back"]).toEqual([0, 1, 0]);
  expect(normals["tag.left"]).toEqual([-1, 0, 0]);
  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");
  await page.keyboard.press("f");                                        // the 3D camera fits the forearm
  await page.waitForTimeout(400);
  await shot(page, "m8b1_3d_forearm");
  await page.getByTestId("view-2d").click();
  await idle(page);
  await page.keyboard.press("f");
  const hinge = page.locator('[data-hinge="tag.right"]');
  await expect(hinge).toHaveCount(1);
  const hx1 = Number(await hinge.getAttribute("x1")), hx2 = Number(await hinge.getAttribute("x2"));
  expect(Math.abs(hx1 - hx2)).toBeLessThan(0.01);                        // the hinge: the right edge, x = 60
  const [sx] = await screenOf(page, 60, 0);
  const box = (await page.locator(".canvas2d").boundingBox())!;
  expect(Math.abs(box.x + hx1 - sx)).toBeLessThan(1);
  const flap = (await page.locator('g[data-tag="tag.right"] [data-layer="target"]').boundingBox())!;
  expect(flap.x).toBeGreaterThanOrEqual(sx - 3);                         // unfolded outwards
  await shot(page, "m8b1_2d_forearm_net");
});

test("M8b1.7 A, four Shift-clicked faces, Enter: one feature, four tags; Renumber makes them unique", async ({ page }) => {
  const file = await freshFile(page, "e2e-faces");
  await page.keyboard.press("r");
  await page.keyboard.type("120 40");
  await page.keyboard.press("Enter");
  await idle(page);
  await page.keyboard.press("e");
  await page.keyboard.type("40");
  await page.keyboard.press("Enter");
  await idle(page);
  // a side face picked in 3D
  await page.keyboard.press("a");
  await page.waitForTimeout(300);
  const fr = await page.evaluate(() => (window as any).__studio3d.screenOf("body1.front"));
  await page.mouse.click(fr[0], fr[1]);
  await expect.poll(async () => (await probe(page)).picks).toEqual(["body1.front"]);
  await shot(page, "m8b1_3d_pick_front");
  // the rest in 2D, on the net drawn around the body
  await page.keyboard.press("Tab");
  await idle(page);
  await page.keyboard.press("f");
  await expect(page.locator("[data-face]")).toHaveCount(5);              // bottom, front, right, back, left
  for (const face of ["right", "back", "left"]) {
    const [x, y] = await centre(page, `[data-face="body1.${face}"]`);
    await page.keyboard.down("Shift");
    await page.mouse.click(x, y);
    await page.keyboard.up("Shift");
  }
  await expect.poll(async () => (await probe(page)).picks).toEqual(["body1.front", "body1.right", "body1.back", "body1.left"]);
  await shot(page, "m8b1_2d_four_faces_picked");
  await page.keyboard.press("Enter");
  await idle(page);
  const f = readFile(file);
  const tags = f.features.filter((x: any) => x.aruco);
  expect(tags).toHaveLength(1);
  expect(tags[0].aruco).toEqual(["body1.front", "body1.right", "body1.back", "body1.left"]);
  await expect(page.locator("g[data-tag]")).toHaveCount(4);
  const names = (await probe(page)).tags.map((t: any) => t.name).sort();
  expect(names).toEqual(["tag1.back", "tag1.front", "tag1.left", "tag1.right"]);
  await palette(page, "Renumber all");
  const ids = (await probe(page)).tags.flatMap((t: any) => t.ids);
  expect(new Set(ids).size).toBe(ids.length);
  await expect(page.getByTestId("dup-count")).toHaveAttribute("data-dups", "0");
  await page.keyboard.press("Escape");
  await page.keyboard.press("f");
  await shot(page, "m8b1_2d_four_faces_renumbered");
});
