// M3.7 / ST-T-UI-5: six tags of one family; Renumber all gives six distinct
// ids; a second Renumber changes nothing; a typed first id is kept; a locked
// (printed) tag keeps its ids.
import { expect, test } from "@playwright/test";
import { add, fresh, idle, openExample, probe, readFile, shot } from "./helpers";

async function idsOf(page: any): Promise<Record<string, string>> {
  const rows = page.locator("[data-ids-row]");
  const out: Record<string, string> = {};
  for (let i = 0; i < (await rows.count()); i++) {
    const r = rows.nth(i);
    out[(await r.getAttribute("data-ids-row"))!] = (await r.locator("td.idc").getAttribute("data-ids"))!;
  }
  return out;
}

test("Renumber all: unique, stable, typed ids kept", async ({ page }) => {
  await fresh(page, "e2e-ids");
  for (let i = 0; i < 6; i++) await add(page, "single");
  await expect(page.locator("[data-ids-row]")).toHaveCount(6);
  // a new tag takes the next free id at once (audit F5): no duplicates to start with
  await expect(page.getByTestId("dup-count")).toHaveAttribute("data-dups", "0");
  expect(new Set(Object.values(await idsOf(page))).size).toBe(6);
  // two tags on the same id by hand: the duplicate is flagged, Renumber fixes it
  await page.locator('input[data-path="override:tag4"]').fill("0");
  await page.locator('input[data-path="override:tag4"]').press("Enter");
  await idle(page);
  await page.locator('[data-ids-row="tag4"]').click();
  await page.locator('[data-ids-row="tag4"] button[title="Back to auto"]').click();
  await idle(page);
  await expect(page.getByTestId("dup-count")).toHaveAttribute("data-dups", "1");
  await shot(page, "ids_before_renumber");

  await page.getByTestId("renumber").click();
  await idle(page);
  const a = await idsOf(page);
  expect(new Set(Object.values(a)).size).toBe(6);
  await expect(page.getByTestId("dup-count")).toHaveAttribute("data-dups", "0");
  await expect(page.locator(".taglabel .ids")).toHaveCount(6);

  await page.getByTestId("renumber").click();
  await idle(page);
  expect(await idsOf(page)).toEqual(a);
  await expect(page.getByTestId("status")).toContainText("nothing changed");

  // a typed first id for tag3, then Renumber: kept, the others go round it
  const inp = page.locator('input[data-path="override:tag3"]');
  await inp.fill("40");
  await inp.press("Enter");
  await idle(page);
  await page.getByTestId("renumber").click();
  await idle(page);
  const b = await idsOf(page);
  expect(b.tag3).toBe("40");
  expect(new Set(Object.values(b)).size).toBe(6);

  // a locked (printed) tag keeps its id when another takes it by hand
  await page.locator('[data-ids-row="tag2"]').click();
  await page.getByTestId("lock").click();
  await idle(page);
  const kept = b.tag2;
  await page.locator('input[data-path="override:tag5"]').fill(kept);
  await page.locator('input[data-path="override:tag5"]').press("Enter");
  await idle(page);
  await page.getByTestId("renumber").click();
  await idle(page);
  const c = await idsOf(page);
  expect(c.tag2).toBe(kept);
  expect((await probe(page)).tags.find((t: any) => t.name === "tag2").locked).toBe(true);
  await shot(page, "ids_renumbered");
});

// lane/scene-fixes (the gallery's finding 1): the sticker sheet types its ids
// (first_id 0, 1, 2, 8). Renumber all keeps them on the canvas, in the IDs
// table's First column and in the file it writes; a reload plans them again
// (the write used to send every tag to #0).
test("Renumber all keeps a file's typed ids (the sticker sheet)", async ({ page }) => {
  const file = await openExample(page, "e2e-ids-typed", "sticker_sheet.arucostudio.json");
  await expect(page.locator("[data-ids-row]")).toHaveCount(4);
  const before = await idsOf(page);
  expect([before.t1, before.t2, before.t3.split(",")[0], before.t4.split(",")[0]]).toEqual(["0", "1", "2", "8"]);
  await expect(page.getByTestId("dup-count")).toHaveAttribute("data-dups", "0");

  await page.getByTestId("renumber").click();
  await idle(page);
  expect(await idsOf(page)).toEqual(before);
  await expect(page.getByTestId("dup-count")).toHaveAttribute("data-dups", "0");
  for (const [name, id] of Object.entries({ t1: "0", t2: "1", t3: "2", t4: "8" }))
    await expect(page.locator(`input[data-path="override:${name}"]`)).toHaveValue(id);
  const doc = readFile(file);
  expect(doc.overrides).toEqual({ t1: 0, t2: 1, t3: 2, t4: 8 });
  expect(doc.features.filter((f: any) => f.aruco).map((f: any) => f.numbers.marker_id)).toEqual([0, 1, 2, 8]);

  await page.reload();
  await expect(page.locator('.app[data-ready="1"]')).toBeVisible();
  await idle(page);
  expect(await idsOf(page)).toEqual(before);
  await shot(page, "ids_typed_kept");
});
