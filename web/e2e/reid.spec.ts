// Edit › Re-ID all markers… (web/src/app/ReIdDialog.tsx) on the sticker
// sheet example (web/src/model/examples.ts): 12 markers whose auto ids the
// hash scattered, numbered 0, 1, 2… in document order by the real core
// (core.assign_ids mode "sequential", fresh), as one undo step. Numbers come
// from the probe's document and plans, and the labels drawn on the canvas.
// REID_SHOTS=<dir> also saves 1280 × 800 screenshots of before, the dialog and after.
import { expect, test, type Page } from "@playwright/test";
import { CORE, clickAt, coreReady, idle, loadExample, openStudio, state } from "./helpers";

const SHOTS = process.env.REID_SHOTS;

async function shot(page: Page, name: string): Promise<void> {
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/${name}.png` });
}

async function sheet(page: Page): Promise<any> {
  await openStudio(page);
  await coreReady(page);
  await loadExample(page, "sticker-sheet");
  await idle(page);
  const s = await state(page);
  expect(s.doc.features).toHaveLength(12);
  for (const f of s.doc.features) expect(s.plans[f.id]?.ids?.length, `${f.id} is planned`).toBeGreaterThan(0);
  return s;
}

/** How many ids each feature prints: the plan's own. */
const counts = (s: any): number[] => s.doc.features.map((f: any) => s.plans[f.id].ids.length);
const firsts = (s: any): number[] => s.doc.features.map((f: any) => f.marker.first_id);

/** Sequential from `start`: each feature's block right after the last. */
function sequential(ns: number[], start = 0): number[][] {
  let next = start;
  return ns.map((n) => { const ids = Array.from({ length: n }, (_, k) => next + k); next += n; return ids; });
}

async function openReId(page: Page): Promise<void> {
  await page.getByTestId("menu-edit").click();
  await page.getByTestId("cmd-reid").click();
  await expect(page.getByTestId("reid-dialog")).toBeVisible();
  await expect(page.getByTestId("reid-apply")).toBeEnabled();
}

/** The new-ids column of the preview, row by row. */
const preview = (page: Page) => page.locator("[data-reid-row]").evaluateAll((rows) => rows.map((r) => r.getAttribute("data-new")));

const range = (ids: number[]) => (ids.length === 1 ? `#${ids[0]}` : `#${ids[0]}–${ids[ids.length - 1]}`);

/** Every id printed once: no two features share one. */
function unique(s: any): boolean {
  const all = s.doc.features.flatMap((f: any) => s.plans[f.id].ids);
  return new Set(all).size === all.length;
}

test.describe(`Re-ID (${CORE} core)`, () => {
  test.skip(CORE === "mock", "the mock core has no assign_ids");

  test("a–c · the sticker sheet's hashed ids: Re-ID sequential from 0 numbers them in document order, the canvas labels follow, Ctrl+Z puts them back in one step", async ({ page }) => {
    const before = await sheet(page);
    const want = sequential(counts(before));
    // (a) scattered by the hash, not 0, 1, 2…
    expect(firsts(before)).not.toEqual(want.map((ids) => ids[0]));
    expect(unique(before)).toBe(true);
    await shot(page, "reid-before");

    // (b) Edit › Re-ID…: Sequential from 0 is the default; the preview is the answer
    await openReId(page);
    await expect(page.getByTestId("reid-mode")).toHaveAttribute("data-value", "sequential");
    await expect(page.locator('input[data-path="reid.start"]')).toHaveValue("0");
    expect(await preview(page)).toEqual(want.map(range));
    const olds = await page.locator("[data-reid-row]").evaluateAll((rows) => rows.map((r) => r.getAttribute("data-old")));
    expect(olds).toEqual(before.doc.features.map((f: any) => range(before.plans[f.id].ids)));
    await shot(page, "reid-dialog");
    await page.getByTestId("reid-apply").click();
    await expect(page.getByTestId("reid-dialog")).toHaveCount(0);
    await idle(page);

    const after = await state(page);
    expect(after.doc.features.map((f: any) => after.plans[f.id].ids)).toEqual(want);
    expect(firsts(after)).toEqual(want.map((ids) => ids[0]));
    expect(unique(after)).toBe(true);
    expect(after.doc.id_ledger).toEqual(Object.fromEntries(after.doc.features.map((f: any, i: number) => [f.key, want[i][0]])));
    // the labels drawn on the canvas say the new ids (#{ids}: every id of a grid, each board's own)
    for (const [i, f] of after.doc.features.entries()) {
      const text = after.plans[f.id].label?.text as string;
      expect(text, `${f.id}'s label`).toContain(`#${want[i][0]}`);
      await expect(page.locator(`[data-label][data-feature="${f.id}"]`)).toHaveCount(1);
    }
    await shot(page, "reid-after");
    expect(after.canUndo).toBe(true);

    // (c) one Ctrl+Z: every id back as it was
    await page.keyboard.press("Control+z");
    await idle(page);
    const undone = await state(page);
    expect(firsts(undone)).toEqual(firsts(before));
    expect(undone.doc.id_ledger).toEqual(before.doc.id_ledger);
    expect(undone.doc.features.map((f: any) => undone.plans[f.id].ids)).toEqual(before.doc.features.map((f: any) => before.plans[f.id].ids));
    expect(undone.canRedo).toBe(true);
    // and Edit › Redo is the same step forward
    await page.getByTestId("menu-edit").click();
    await page.getByTestId("cmd-redo").click();
    await idle(page);
    expect(firsts(await state(page))).toEqual(want.map((ids) => ids[0]));
  });

  test("d · a typed id is kept and the others number around it", async ({ page }) => {
    const s0 = await sheet(page);
    // marker 4 (a single, sequential's #6) typed to 1
    const f4 = s0.doc.features[3];
    expect(f4.marker.type).toBe("single");
    await clickAt(page, 175, 150);
    await expect(page.getByTestId("extrude-panel")).toBeVisible();
    expect((await state(page)).panel.featureId).toBe(f4.id);
    const id = page.locator('input[data-path="marker.first_id"]');
    await id.fill("1");
    await id.press("Enter");
    await idle(page);
    await page.getByTestId("panel-ok").click();
    await expect(page.getByTestId("extrude-panel")).toHaveCount(0);
    await idle(page);
    const typed = await state(page);
    expect(typed.doc.features[3].marker.first_id).toBe(1);

    await openReId(page);
    await expect(page.locator(`[data-reid-row="${f4.id}"]`)).toHaveAttribute("data-typed", "1");
    await page.getByTestId("reid-apply").click();
    await idle(page);
    const s = await state(page);
    const ids = s.doc.features.map((f: any) => s.plans[f.id].ids as number[]);
    expect(ids[3]).toEqual([1]);
    expect(unique(s)).toBe(true);
    // the rest: 0, then from 2 on, contiguous and in document order around the typed 1
    const rest = ids.filter((_: number[], i: number) => i !== 3);
    expect(rest).toEqual([[0], ...sequential(rest.slice(1).map((b: number[]) => b.length), 2)]);
  });

  test("e · start 100 on DICT_4X4_50 warns that the numbering wraps to 0", async ({ page }) => {
    await sheet(page);
    await openReId(page);
    const start = page.locator('input[data-path="reid.start"]');
    await start.fill("100");
    await start.press("Enter");
    const warn = page.locator('[data-issues-for="reid"] [data-level="warn"]');
    await expect(warn).toHaveAttribute("data-text", "start 100 is past DICT_4X4_50's last id 49: numbering wraps to 0");
    // still unique, from 0
    const got = await preview(page);
    expect(got[0]).toBe("#0");
    await shot(page, "reid-wrap-warning");
    await page.getByTestId("reid-cancel").click();
  });

  test("f · Cancel changes nothing", async ({ page }) => {
    const s0 = await sheet(page);
    await openReId(page);
    await page.getByTestId("reid-mode").locator('[data-value="hash"]').click();
    await expect(page.locator('input[data-path="reid.start"]')).toBeDisabled();
    await expect(page.getByTestId("reid-apply")).toBeEnabled();
    await page.getByTestId("reid-cancel").click();
    await expect(page.getByTestId("reid-dialog")).toHaveCount(0);
    await idle(page);
    const s = await state(page);
    expect(s.doc).toEqual(s0.doc);
    expect(s.canUndo).toBe(s0.canUndo);
    expect(s.modal).toBeNull();
  });
});
