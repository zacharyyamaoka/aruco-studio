// ST-T-UI-11: the target editor. Zach's disc (four holes): Auto size reads
// what /api/validate says; a 2 mm thickness and round pins on a New tile
// give pin and hole layers; Trim excess gives a trim_keep layer; a typed
// box with a hole draws the hole.
import { expect, test } from "@playwright/test";
import { API, add, choose, expectIssues, fresh, idle, probe, shot, tab, type } from "./helpers";

test("target editor: a palette face, a thickness, pins, trim, a typed hole", async ({ page, request }) => {
  await fresh(page, "e2e-target");
  await add(page, "single");
  await choose(page, "target", "disc4");
  let spec = (await probe(page)).doc.tags[0].spec;
  expect(spec.target.loops_mm.length).toBe(5);
  const issues = await (await request.post(`${API}/api/validate`, { data: spec })).json();
  const size = issues.filter((i: any) => i.field === "numbers.size").map((i: any) => i.text);
  await expectIssues(page, "numbers.size", size);
  const tag = page.locator('g[data-tag="tag1"]');
  expect(((await tag.locator('[data-layer="target"]').getAttribute("d")) || "").match(/M/g)!.length).toBe(5);

  // White + black, New body, round pins, a 2 mm plate
  await type(page, "target.thickness", "2");
  spec = (await probe(page)).doc.tags[0].spec;
  expect(spec.target.body_mm.z0).toBe(-2);
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
  await page.keyboard.press("l");                  // layer outlines on
  await shot(page, "target_disc_pins_trim");
  await page.keyboard.press("l");

  // a typed box with a round hole
  await add(page, "single");
  await choose(page, "target", "box");
  await type(page, "target.w_mm", "70");
  await type(page, "target.h_mm", "45");
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
