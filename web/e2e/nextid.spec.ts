// Next id (core autoid rule 3', IdRequest.mode "next", the default since
// 2026-10-20 night). Zach: "As I copy paste new single markers, how are the
// new IDs calculated? It seems like it would be simplest if they simply
// increment". On the real core: one rectangle profile, A, then Ctrl+C and
// Ctrl+V three times gives ids n, n+1, n+2, n+3 in document order; a typed id
// pasted becomes driven in the copy (web/src/store.ts paste) and takes the
// next id, 30 -> 31. Ids come from the probe's plans, never DOM presence.
import { expect, test, type Page } from "@playwright/test";
import { CORE, coreReady, dragWorld, idle, openStudio, panelTab, state, toClient, openMenu } from "./helpers";

async function blank(page: Page): Promise<void> {
  await openStudio(page);
  await coreReady(page);
  await openMenu(page, "file");
  await page.getByTestId("cmd-new").click();
}

/** A 20 mm square profile at (-30..-10, -10..10) with its ArUco Extrude (A), the panel closed. */
async function oneMarker(page: Page, typed?: number): Promise<void> {
  await page.keyboard.press("r");
  await dragWorld(page, [-30, -10], [-10, 10]);
  expect((await state(page)).sel?.kind).toBe("shape");
  await page.keyboard.press("a");
  await expect(page.getByTestId("extrude-panel")).toBeVisible();
  if (typed !== undefined) {
    await panelTab(page, "marker");
    const id = page.locator('input[data-path="marker.first_id"]');
    await id.fill(String(typed));
    await id.press("Enter");
  }
  await idle(page);
  await page.getByTestId("panel-ok").click();
  await expect(page.getByTestId("extrude-panel")).toHaveCount(0);
  await idle(page);
}

/** Pick the first feature by its rectangle's left edge and Ctrl+C it. */
async function copyFirst(page: Page): Promise<void> {
  const [ex, ey] = await toClient(page, -30, 0);
  await page.mouse.click(ex, ey);
  expect((await state(page)).sel.kind).toBe("feature");
  await page.keyboard.press("Control+c");
}

/** Ctrl+V with the pointer at (x, y) mm. */
async function pasteAt(page: Page, x: number, y: number): Promise<void> {
  const [px, py] = await toClient(page, x, y);
  await page.mouse.move(px, py);
  await page.keyboard.press("Control+v");
  await idle(page);
}

/** Every feature's printed ids, in document order. */
const idsOf = (s: any): number[][] => s.doc.features.map((f: any) => s.plans[f.id]?.ids);

test.describe(`Next id (${CORE} core)`, () => {
  test.skip(CORE === "mock", "the mock core has no assign_ids");

  test("a · one marker, Ctrl+C, Ctrl+V three times: ids n, n+1, n+2, n+3", async ({ page }) => {
    await blank(page);
    await oneMarker(page);
    await copyFirst(page);
    await pasteAt(page, 25, 0);
    await pasteAt(page, 25, -40);
    await pasteAt(page, -20, -40);
    const s = await state(page);
    expect(s.doc.features).toHaveLength(4);
    const ids = idsOf(s);
    const n = ids[0][0];
    expect(n).toBe(0);                                   // a new document starts at 0
    expect(ids).toEqual([[n], [n + 1], [n + 2], [n + 3]]);
    // driven, and in the ledger: what the core gave out
    for (const f of s.doc.features) {
      expect(f.set).not.toContain("marker.first_id");
      expect(s.doc.id_ledger[f.key]).toBe(s.plans[f.id].ids[0]);
    }
  });

  test("b · typed 30 on the first, pasted: the copy is driven and gets 31", async ({ page }) => {
    await blank(page);
    await oneMarker(page, 30);
    let s = await state(page);
    expect(s.doc.features[0].set).toContain("marker.first_id");
    expect(idsOf(s)).toEqual([[30]]);
    await copyFirst(page);
    await pasteAt(page, 25, 0);
    s = await state(page);
    expect(s.doc.features).toHaveLength(2);
    expect(idsOf(s)).toEqual([[30], [31]]);
    expect(s.doc.features[0].set).toContain("marker.first_id");
    expect(s.doc.features[1].set).not.toContain("marker.first_id");
    expect(s.doc.id_ledger[s.doc.features[1].key]).toBe(31);
    // a second paste carries on: 32
    await pasteAt(page, 25, -40);
    expect(idsOf(await state(page))).toEqual([[30], [31], [32]]);
  });
});
