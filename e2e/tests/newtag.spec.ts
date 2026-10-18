// 2026-10-17 (CF-13: tags are printed by inkjet on vinyl only): the
// new-tag form starts on "Inkjet · Letter vinyl" (GET /api/presets'
// `new_tag`, core.presets.NEW_TAG_PRESET), so a tag added without a pick is
// a vinyl sticker (make rule 2); a preset picked in the form still wins.
// Every bar is read from the DOM, the store or the API.
import { expect, test } from "@playwright/test";
import { API, add, choose, freshFile, idle, probe, readFile, sceneTags } from "./helpers";

const VINYL = "Inkjet · Letter vinyl";

test("CF-13 the new-tag form starts on Inkjet · Letter vinyl; a picked preset wins", async ({ page }) => {
  const file = await freshFile(page, "e2e-newtag", undefined, null);           // no pick: the app's own default
  const presets = await (await page.request.get(`${API}/api/presets`)).json();
  expect(presets.new_tag).toBe(VINYL);
  await expect(page.locator('.kit-select[data-path="new.preset"]')).toHaveAttribute("data-value", VINYL);
  await expect(page.getByTestId("made-by")).toHaveAttribute("data-made-by", "sticker");
  expect(await page.evaluate(() => (window as any).__studio.store.getState().newPreset)).toBe(VINYL);

  // a tag added with no pick: a vinyl sticker, make rule 2
  await add(page, "single");
  const first = (await probe(page)).sel[0];
  expect(first).toBeTruthy();
  await expect(page.getByTestId("inspector")).toHaveAttribute("data-made-by", "sticker");
  let tags = await sceneTags(page.request);
  const t1 = tags.find((t) => t.name === first);
  expect(t1.spec.settings.make.by).toBe("sticker");
  expect(t1.spec.settings.make.rule).toBe(2);
  expect(t1.spec.settings.make.page).toBe("letter");
  expect(t1.plan.made_by).toBe("sticker");
  expect(readFile(file).features.filter((f: any) => f.aruco).map((f: any) => f.preset)).toEqual([VINYL]);

  // the 3D Default picked in the form: the next tag is 3D printed
  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");
  await idle(page);
  await choose(page, "new.preset", "Default");
  await expect(page.locator('.kit-select[data-path="new.preset"]')).toHaveAttribute("data-value", "Default");
  await expect(page.getByTestId("made-by")).toHaveAttribute("data-made-by", "print3d");
  await add(page, "single");
  const second = (await probe(page)).sel[0];
  expect(second).toBeTruthy();
  expect(second).not.toBe(first);
  tags = await sceneTags(page.request);
  const t2 = tags.find((t) => t.name === second);
  expect(t2.plan.made_by).toBe("print3d");
  expect(t2.spec.settings.make?.by ?? "print3d").toBe("print3d");
  // the first tag kept its make
  expect(tags.find((t) => t.name === first).spec.settings.make.rule).toBe(2);
});
