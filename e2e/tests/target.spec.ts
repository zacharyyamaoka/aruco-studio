// ST-T-UI-11, rewritten for M8b1 (the target editor is gone: a tag's target
// is the shape or the face it stands on). A disc with four holes (C, H
// clicks), 2 mm thick (E): Auto size reads what /api/validate says; round
// pins on a New tile give pin and hole layers; Trim excess gives a trim_keep
// layer; a box with a hole typed in the shape's rows draws the hole.
import { expect, test } from "@playwright/test";
import { API, choose, expectIssues, freshFile, idle, palette, probe, screenOf, shapeOfTag, shot, tab, tagOn, type } from "./helpers";

test("shapes as targets: a disc with four holes, 2 mm thick, pins, trim; a box with a typed hole", async ({ page, request }) => {
  await freshFile(page, "e2e-target");
  await page.keyboard.press("c");
  await page.keyboard.type("40");
  await page.keyboard.press("Enter");
  await idle(page);
  for (const [x, y] of [[12, 0], [-12, 0], [0, 12], [0, -12]]) {
    await page.keyboard.press("h");
    await page.keyboard.type("5");
    await page.mouse.click(...(await screenOf(page, x, y)));
    await idle(page);
  }
  await expect(page.locator("[data-hole]")).toHaveCount(4);
  await page.keyboard.press("e");
  await page.keyboard.type("2");
  await page.keyboard.press("Enter");
  await idle(page);
  await page.getByTestId("view-2d").click();
  await idle(page);
  await page.keyboard.press("a");
  await page.keyboard.press("Enter");
  await idle(page);
  let spec = (await probe(page)).doc.tags[0].spec;
  expect(spec.target.loops_mm.length).toBe(5);
  const issues = await (await request.post(`${API}/api/validate`, { data: spec })).json();
  const size = issues.filter((i: any) => i.field === "numbers.size").map((i: any) => i.text);
  await expectIssues(page, "numbers.size", size);
  const tag = page.locator('g[data-tag="tag1"]');
  expect(((await tag.locator('[data-layer="target"]').getAttribute("d")) || "").match(/M/g)!.length).toBe(5);
  expect(spec.target.body_mm.z0).toBe(-2);

  // White + black, New body, round pins
  await tab(page, "heights");
  await choose(page, "settings.mode", "both");
  await choose(page, "settings.op", "new");
  await choose(page, "settings.pin", "round");
  await expect(tag.locator('[data-layer="pin"]').first()).toBeAttached();
  await expect(tag.locator('[data-layer="hole"]').first()).toBeAttached();

  // Trim excess, both axes
  await tab(page, "advanced");
  await choose(page, "settings.trim", "both");
  await expect(tag.locator('[data-layer="trim_keep"]')).toHaveCount(1);
  await expect(tag.locator('[data-guide="trim"]')).toHaveCount(1);
  await palette(page, "Layer outlines");
  await shot(page, "target_disc_pins_trim");
  await palette(page, "Layer outlines");

  // a box 70 x 45 with a round hole typed in its shape's rows
  expect(await tagOn(page, "r", "70 45", 3)).toBe("tag2");
  await shapeOfTag(page);
  await page.getByTestId("hole-add").click();
  await idle(page);
  await type(page, "hole.0.x", "25");
  await type(page, "hole.0.d", "8");
  const t2 = (await probe(page)).doc.tags.find((t: any) => t.name === "tag2").spec.target;
  expect(t2.loops_mm.length).toBe(2);
  expect(t2.w_mm).toBe(70);
  const xs = t2.loops_mm[1].map((p: number[]) => p[0]);
  expect(Math.min(...xs)).toBeCloseTo(21, 1);
  expect(Math.max(...xs)).toBeCloseTo(29, 1);
  await page.keyboard.press("f");
  await shot(page, "target_editor");
});
