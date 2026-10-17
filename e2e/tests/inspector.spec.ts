// M3.4 / ST-T-UI-2: the inspector from /api/form. The size line under the
// size field is /api/validate's Issue text; cells "each cell a multiple of
// 0.68 mm" changes the pattern; every tab; per-field validation errors and
// the summary line; a typed non-number never reaches the server.
import { expect, test } from "@playwright/test";
import { API, add, choose, expectIssues, fresh, idle, probe, shot, tab, tagOn, type } from "./helpers";

async function validateText(request: any, spec: any, field: string) {
  const issues = await (await request.post(`${API}/api/validate`, { data: spec })).json();
  return issues.filter((i: any) => i.field === field).map((i: any) => i.text);
}

async function specOf(page: any, name: string) {
  return (await probe(page)).doc.tags.find((t: any) => t.name === name).spec;
}

test("the size line is the plan's Issue; cells change the pattern; every tab", async ({ page, request }) => {
  await fresh(page, "e2e-inspector");
  // a tag on a disc (C, 40, A): Auto size, its size line
  const disc = await tagOn(page, "c", "40");
  let want = await validateText(request, await specOf(page, disc), "numbers.size");
  expect(want.length).toBeGreaterThan(0);
  await expectIssues(page, "numbers.size", want);
  // a typed 28 mm on a 40 mm box, 3 mm thick (R, 40 40, E 3, A): tag2
  expect(await tagOn(page, "r", "40 40", 3)).toBe("tag2");
  await page.locator('[role="switch"][data-path="numbers.size:auto"]').click();
  await idle(page);
  await type(page, "numbers.size", "28");
  const spec28 = await specOf(page, "tag2");
  expect(spec28.numbers.size).toBe(28);
  want = await validateText(request, spec28, "numbers.size");
  await expectIssues(page, "numbers.size", want);
  const d0 = await page.locator('g[data-tag="tag2"] [data-layer="pattern"]').getAttribute("d");
  await shot(page, "inspector_marker");

  // Print: cells, every cell a multiple of 0.68 mm
  await tab(page, "print");
  await choose(page, "settings.cells", "cell");
  await type(page, "settings.cells.mm", "0.68");
  const sc = await specOf(page, "tag2");
  expect(sc.settings.cells).toMatchObject({ rule: 1, of: "cell", mm: 0.68 });
  const d1 = await page.locator('g[data-tag="tag2"] [data-layer="pattern"]').getAttribute("d");
  expect(d1).not.toBe(d0);
  want = await validateText(request, sc, "numbers.size");
  await tab(page, "marker");
  await expectIssues(page, "numbers.size", want);
  const p = await (await request.post(`${API}/api/plan`, { data: sc })).json();
  const mm = p.marker.marker_length_m * 1000;
  expect(Math.abs(mm / 6 / 0.68 - Math.round(mm / 6 / 0.68))).toBeLessThan(1e-6);   // whole 0.68 mm cells
  await tab(page, "print");
  await shot(page, "inspector_print");

  await tab(page, "heights");
  await choose(page, "settings.mode", "both");
  await expect(page.locator('[data-row="numbers.white_height"]')).toBeVisible();
  await shot(page, "inspector_heights");

  await tab(page, "label");
  await page.locator('[role="switch"][data-path="settings.label.on"]').click();
  await idle(page);
  await expect(page.locator('[data-row="settings.label.content"]')).toBeVisible();
  await expect(page.locator('g[data-tag="tag2"] [data-layer^="label_"]').first()).toBeAttached();
  await shot(page, "inspector_label");

  await tab(page, "advanced");
  await expect(page.locator('[data-row="settings.trim"]')).toBeVisible();
  await expect(page.locator('[data-row="settings.origin_v"] .ro')).toHaveText("rule 2");
  await shot(page, "inspector_advanced");
});

test("validation: each error under its field, one summary line, typed text checked", async ({ page }) => {
  await fresh(page, "e2e-validation");
  await add(page, "single");
  await tab(page, "print");
  await type(page, "settings.quiet_modules", "0.2");
  const q = page.locator('[data-issues-for="settings.quiet_modules"] .issue[data-level="error"]');
  await expect(q).toHaveCount(1);
  await expect(page.locator('[data-row="settings.quiet_modules"]')).toHaveClass(/has-error/);
  await expect(page.locator('[role="tab"][data-tab="print"]')).toHaveClass(/has-error/);
  await expect(page.getByTestId("summary")).toHaveClass(/lv-error/);
  await expect(page.getByTestId("summary")).toContainText("Quiet zone");
  await tab(page, "marker");
  await type(page, "numbers.marker_id", "60");
  await expect(page.locator('[data-issues-for="numbers.marker_id"] .issue[data-level="error"]')).toContainText(/50|capacity|exceed/);
  await expect(page.getByTestId("summary")).toContainText("2 issues");
  // text that is not a number: refused in the field, never sent
  const before = (await probe(page)).doc.tags[0].spec.numbers.marker_id;
  await type(page, "numbers.marker_id", "abc");
  await expect(page.locator('[data-issues-for="numbers.marker_id"] [data-local="1"]')).toHaveText("'abc' is not a number");
  expect((await probe(page)).doc.tags[0].spec.numbers.marker_id).toBe(before);
  await shot(page, "validation_error");
  // fixed: the errors go, the summary is green again
  await type(page, "numbers.marker_id", "3");
  await tab(page, "print");
  await type(page, "settings.quiet_modules", "1");
  await expect(page.getByTestId("summary")).toHaveClass(/lv-ok/);
  expect((await probe(page)).tags[0].ids).toEqual([3]);
});
