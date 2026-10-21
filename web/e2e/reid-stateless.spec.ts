// ArUco Re-ID is stateless (Zach, 2026-10-20: "Make sure that reids work even
// when you do them multiple times ... purely functional, stateless, and you
// get the desired behaviour for free ... the Re-ID downstream should account
// properly for Re-IDs upstream"). On the real core and the sticker sheet
// example: the same Re-ID gives the same ids whatever came before, auto id
// leaves an applied Re-ID where it is, a pasted marker is numbered with the
// rest, a typed id survives every Re-ID, the preview is exactly what Apply
// writes, and every Apply is one Ctrl+Z step. The core's own property test:
// tests/web/test_web_reid_stateless.py.
import { expect, test, type Page } from "@playwright/test";
import { CORE, clickAt, coreReady, idle, loadExample, openStudio, panelTab, state, toClient } from "./helpers";

async function sheet(page: Page): Promise<void> {
  await openStudio(page);
  await coreReady(page);
  await loadExample(page, "sticker-sheet");
  await idle(page);
  const s = await state(page);
  expect(s.doc.features).toHaveLength(12);
}

/** Every feature's printed ids, in document order. */
const idsOf = (s: any): number[][] => s.doc.features.map((f: any) => s.plans[f.id].ids);
const flat = (s: any): number[] => idsOf(s).flat();
const range = (ids: number[]) => (ids.length === 1 ? `#${ids[0]}` : `#${ids[0]}–${ids[ids.length - 1]}`);

/** The preview's new-ids column, row by row: what Apply is about to write. */
const preview = (page: Page) => page.locator("[data-reid-row]").evaluateAll((rows) => rows.map((r) => r.getAttribute("data-new")));

/** Edit › ArUco Re-ID…, Sequential from `start`, once the preview answers that request. */
async function openReId(page: Page, start: number): Promise<void> {
  await page.getByTestId("menu-edit").click();
  await page.getByTestId("cmd-reid").click();
  await expect(page.getByTestId("reid-dialog")).toBeVisible();
  await expect(page.getByTestId("reid-mode")).toHaveAttribute("data-value", "sequential");
  const input = page.locator('input[data-path="reid.start"]');
  await input.fill(String(start));
  await input.press("Enter");
  await expect(input).toHaveValue(String(start));
  await expect(page.getByTestId("reid-apply")).toBeEnabled();
  await expect.poll(async () => (await preview(page)).every((n) => n && n !== "…")).toBe(true);
}

/** Re-ID sequential from `start`, applied; the planner and auto id settled after it. Returns what the preview showed. */
async function reId(page: Page, start: number): Promise<(string | null)[]> {
  await openReId(page, start);
  const shown = await preview(page);
  await page.getByTestId("reid-apply").click();
  await expect(page.getByTestId("reid-dialog")).toHaveCount(0);
  await idle(page);
  return shown;
}

test.describe(`ArUco Re-ID is stateless (${CORE} core)`, () => {
  test.skip(CORE === "mock", "the mock core has no assign_ids");

  test("a · from 0 gives A, from 10 gives A + 10 in the same order, from 0 again gives exactly A", async ({ page }) => {
    await sheet(page);
    await reId(page, 0);
    const a = await state(page);
    const A = idsOf(a);
    expect(flat(a)).toEqual(Array.from({ length: flat(a).length }, (_, i) => i));      // contiguous from 0
    await reId(page, 10);
    const b = await state(page);
    expect(idsOf(b)).toEqual(A.map((ids) => ids.map((i) => i + 10)));
    await reId(page, 0);
    const c = await state(page);
    expect(idsOf(c)).toEqual(A);
    // the ledger is the last answer's alone, not an accumulation
    expect(c.doc.id_ledger).toEqual(a.doc.id_ledger);
    expect(c.doc.features.map((f: any) => f.marker.first_id)).toEqual(a.doc.features.map((f: any) => f.marker.first_id));
  });

  test("b · after Apply, auto id does not renumber an applied Re-ID", async ({ page }) => {
    await sheet(page);
    await reId(page, 10);
    const applied = await state(page);
    await page.waitForTimeout(1500);
    await idle(page);
    const later = await state(page);
    expect(idsOf(later)).toEqual(idsOf(applied));
    expect(later.doc.id_ledger).toEqual(applied.doc.id_ledger);
    expect(later.doc.features.map((f: any) => f.marker.first_id)).toEqual(applied.doc.features.map((f: any) => f.marker.first_id));
    expect(flat(later)[0]).toBe(10);
  });

  test("c · a copy-pasted marker is numbered with the rest: contiguous in document order", async ({ page }) => {
    await sheet(page);
    // marker 4 (a single): click, close its panel, copy, paste in the empty bottom right
    await clickAt(page, 175, 150);
    await expect(page.getByTestId("extrude-panel")).toBeVisible();
    await page.getByTestId("panel-ok").click();
    await expect(page.getByTestId("extrude-panel")).toHaveCount(0);
    await page.keyboard.press("Control+c");
    const [px, py] = await toClient(page, 200, 30);
    await page.mouse.move(px, py);
    await page.keyboard.press("Control+v");
    await idle(page);
    expect((await state(page)).doc.features).toHaveLength(13);
    await reId(page, 0);
    const s = await state(page);
    expect(s.doc.features).toHaveLength(13);
    expect(idsOf(s).every((ids) => ids.length > 0)).toBe(true);
    expect(flat(s)).toEqual(Array.from({ length: flat(s).length }, (_, i) => i));
    // the pasted one is last in the document and numbered last
    const last = idsOf(s)[12];
    expect(last[last.length - 1]).toBe(flat(s).length - 1);
  });

  test("d · a typed id keeps its number through two Re-IDs; the others are identical across them", async ({ page }) => {
    await sheet(page);
    const f4 = (await state(page)).doc.features[3];
    await clickAt(page, 175, 150);
    await expect(page.getByTestId("extrude-panel")).toBeVisible();
    await panelTab(page, "marker");
    const id = page.locator('input[data-path="marker.first_id"]');
    await id.fill("1");
    await id.press("Enter");
    await idle(page);
    await page.getByTestId("panel-ok").click();
    await expect(page.getByTestId("extrude-panel")).toHaveCount(0);
    await idle(page);

    await reId(page, 0);
    const one = await state(page);
    expect(one.plans[f4.id].ids).toEqual([1]);
    expect(one.doc.features[3].marker.first_id).toBe(1);
    await reId(page, 0);
    const two = await state(page);
    expect(two.plans[f4.id].ids).toEqual([1]);
    expect(idsOf(two)).toEqual(idsOf(one));
    // no id printed twice
    expect(new Set(flat(two)).size).toBe(flat(two).length);
    // and from another start: the typed one still 1, the others around it
    await reId(page, 10);
    const three = await state(page);
    expect(three.plans[f4.id].ids).toEqual([1]);
    expect(flat(three).filter((n) => n !== 1).sort((x, y) => x - y)[0]).toBe(10);
  });

  test("e · the preview table is what Apply writes", async ({ page }) => {
    await sheet(page);
    for (const start of [0, 10, 3]) {
      await openReId(page, start);
      const shown = await preview(page);
      await page.getByTestId("reid-apply").click();
      await expect(page.getByTestId("reid-dialog")).toHaveCount(0);
      await idle(page);
      const s = await state(page);
      expect(idsOf(s).map(range), `start ${start}`).toEqual(shown);
    }
  });

  test("f · every Apply is one Ctrl+Z step", async ({ page }) => {
    await sheet(page);
    const shots = [await state(page)];
    for (const start of [0, 10, 0]) {
      await reId(page, start);
      shots.push(await state(page));
    }
    for (let i = shots.length - 2; i >= 0; i--) {
      await page.keyboard.press("Control+z");
      await idle(page);
      const s = await state(page);
      expect(idsOf(s), `undo back to step ${i}`).toEqual(idsOf(shots[i]));
      expect(s.doc.id_ledger).toEqual(shots[i].doc.id_ledger);
    }
  });
});
