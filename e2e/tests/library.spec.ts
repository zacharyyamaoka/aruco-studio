// ST-T-UI-8 (M5.1 brought forward): the preset Library window, like
// Fusion's Machine Library. Collections, cards with thumbs, Filters | Info,
// Select applies a preset to the tag (its cells and heights), New / Edit /
// Duplicate / Delete of your own presets, all on /api/presets.
import { expect, test } from "@playwright/test";
import { API, add, fresh, idle, probe, shot } from "./helpers";

test("the Library: browse, filter, select a preset, make and edit your own", async ({ page, request }) => {
  await fresh(page, "e2e-library");
  await add(page, "single");
  await page.getByTestId("library-btn").first().click();
  const lib = page.getByTestId("library");
  await expect(lib).toBeVisible();
  await expect(lib.locator(".card").first()).toBeVisible();
  for (const c of ["recent", "document", "mine", "prusa", "builtin"]) await expect(lib.locator(`[data-coll="${c}"]`)).toBeVisible();
  await expect(lib.locator('[data-coll="document"] .n')).toHaveText("1");          // the tag's own (Default)
  await lib.locator('[data-coll="builtin"]').click();
  await expect(lib.locator('.card[data-card="builtin:Default"] .thumb svg')).toBeVisible();
  await shot(page, "library");

  // filters: nozzle 0.6 only
  const all = Number((await lib.getByTestId("lib-count").textContent())!.split(" of ")[0]);
  await lib.locator('[data-side="filters"]').click();
  await lib.locator('.chip[data-filter="nozzle:0.6"]').click();
  const some = Number((await lib.getByTestId("lib-count").textContent())!.split(" of ")[0]);
  expect(some).toBeLessThan(all);
  await shot(page, "library_filters");

  // pick the PrusaSlicer "Aruco 0.6" built-in: Info, then Select
  const presets = (await (await request.get(`${API}/api/presets`)).json()).items;
  const want = presets.find((p: any) => /Aruco/.test(p.name) && /0\.6/.test(p.name));
  expect(want).toBeTruthy();
  const card = lib.locator(`.card[data-card="builtin:${want.name}"]`);
  await card.click();
  await expect(lib.getByTestId("lib-info")).toContainText(want.name);
  await expect(lib.getByTestId("lib-info")).toContainText("Changes the tag:");
  await shot(page, "library_info");
  // a print preset that changes the dictionary asks first (audit F10)
  const inkWarn = await lib.getByTestId("lib-ink-warn").count();
  await lib.getByTestId("lib-select").click();
  if (inkWarn) {
    await expect(lib.locator(".prompt")).toContainText("also changes this tag's dictionary");
    await lib.getByTestId("prompt-ok").click();
  }
  await idle(page);
  await expect(lib).toHaveCount(0);
  const spec = (await probe(page)).doc.tags[0].spec;
  const of = await (await request.post(`${API}/api/preset/of`, { data: { spec } })).json();
  expect(of.matches).toBe(want.name);
  expect(spec.numbers.white_height).toBe(want.preset.tag.white_height_mm);
  expect(spec.settings.cells.of).toBe(want.preset.cells.of);
  await expect(page.locator('.kit-select[data-path="preset"]')).toHaveAttribute("data-value", want.name);

  // New: the tag's print settings as a preset of mine (an empty name is refused there)
  await page.getByTestId("library-btn").first().click();
  await lib.getByTestId("lib-new").click();
  await lib.getByTestId("prompt-input").fill("  ");
  await lib.getByTestId("prompt-ok").click();
  await expect(lib.getByTestId("prompt-error")).toHaveText("a preset needs a name");
  await lib.getByTestId("prompt-input").fill("E2E preset");
  await lib.getByTestId("prompt-ok").click();
  await expect(lib.locator('.card[data-card="user:E2E preset"]')).toBeVisible();
  let mine = (await (await request.get(`${API}/api/presets`)).json()).items.filter((p: any) => p.kind === "user");
  expect(mine.map((p: any) => p.name)).toContain("E2E preset");

  // Edit: the quiet zone 1.5
  await lib.locator('.card[data-card="user:E2E preset"]').click();
  await lib.getByTestId("lib-edit").click();
  // a value a preset would drop is refused under its field, nothing saved (audit F16)
  await lib.locator('[data-testid="lib-form"] input[data-path="tag.quiet_modules"]').fill("-3");
  await lib.getByTestId("lib-save").click();
  await expect(lib.locator('[data-error-for="tag.quiet_modules"]')).toContainText("outside 0 to 4");
  const kept = (await (await request.get(`${API}/api/presets`)).json()).items.find((p: any) => p.name === "E2E preset");
  expect(kept.preset.tag.quiet_modules).not.toBe(-3);                // nothing saved
  await lib.locator('[data-testid="lib-form"] input[data-path="tag.quiet_modules"]').fill("1.5");
  await lib.getByTestId("lib-save").click();
  await expect(lib.getByTestId("lib-status")).toContainText("saved");
  await expect.poll(async () => (await (await request.get(`${API}/api/presets`)).json()).items
    .find((p: any) => p.kind === "user" && p.name === "E2E preset").preset.tag.quiet_modules).toBe(1.5);

  // Duplicate, then Delete the copy
  await lib.getByTestId("lib-dup").click();
  await lib.getByTestId("prompt-ok").click();
  await expect(lib.locator('.card[data-card="user:E2E preset copy"]')).toBeVisible();
  await lib.getByTestId("lib-delete").click();
  await lib.getByTestId("prompt-ok").click();
  await expect(lib.locator('.card[data-card="user:E2E preset copy"]')).toHaveCount(0);
  await lib.getByTestId("lib-cancel").click();
  await expect(lib).toHaveCount(0);

  // clean up what the test made
  await request.delete(`${API}/api/presets/${encodeURIComponent("E2E preset")}`);
  for (const p of (await (await request.get(`${API}/api/presets`)).json()).items)
    if (p.kind === "user" && /Aruco/.test(p.name)) await request.delete(`${API}/api/presets/${encodeURIComponent(p.name)}`);
});
