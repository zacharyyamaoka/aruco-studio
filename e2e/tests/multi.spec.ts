// M6b.5: multi-select edit. Four tags selected, the Corner mark set once:
// every tag's plan has the triangle; one Undo restores all four. A value
// the selected tags do not share shows "—" until it is set.
import { expect, test } from "@playwright/test";
import { add, choose, freshFile, idle, probe, sceneTags, shot } from "./helpers";

test("M6b.5 four tags, one change, one undo", async ({ page }) => {
  await freshFile(page, "e2e-multi");
  const names: string[] = [];
  for (let i = 0; i < 4; i++) {
    await page.keyboard.press("Escape");
    await page.keyboard.press("Escape");
    await add(page, "single");
    names.push((await probe(page)).sel[0]);
  }
  expect(new Set(names).size).toBe(4);
  // one of them differs first: the row shows "—"
  await page.locator(`[data-ids-row="${names[0]}"]`).click();
  await choose(page, "settings.corner_mark", "cut");
  for (const n of names.slice(1)) await page.locator(`[data-ids-row="${n}"]`).click({ modifiers: ["Shift"] });
  await idle(page);
  expect((await probe(page)).sel.sort()).toEqual([...names].sort());
  await expect(page.getByTestId("inspector")).toHaveAttribute("data-count", "4");
  await expect(page.getByTestId("multi-note")).toContainText("4 tags selected");
  await expect(page.locator('.kit-select[data-path="settings.corner_mark"]')).toHaveAttribute("data-mixed", "1");
  await shot(page, "m8b2_multi_mixed");
  const undo0 = (await probe(page)).undo;
  await choose(page, "settings.corner_mark", "triangle");
  for (const t of await sceneTags(page.request)) {
    expect(t.spec.settings.corner_mark).toBe("triangle");
    expect(t.plan.layers.map((L: any) => L.name)).toContain("mark_triangle");
  }
  await expect(page.locator('.kit-select[data-path="settings.corner_mark"]')).toHaveAttribute("data-value", "triangle");
  expect((await probe(page)).undo).toBe(undo0 + 1);                                   // one history step
  await shot(page, "m8b2_multi_set");
  await page.keyboard.press("Control+z");
  await idle(page);
  const back = await sceneTags(page.request);
  expect(back.find((t) => t.name === names[0]).spec.settings.corner_mark).toBe("cut");
  for (const n of names.slice(1)) expect(back.find((t) => t.name === n).spec.settings.corner_mark).toBe("none");
});
