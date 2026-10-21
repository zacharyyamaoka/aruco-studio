// Batch editing (web/src/panel/BatchPanel.tsx, web/src/model/batch.ts) on the
// sticker sheet example: 8 single markers and the ChArUco board Shift+clicked,
// then A -- the ArUco Extrude panel opens on all 9 ("ArUco Extrude · 9 markers").
// A batchable row sets every one of them through the real core, as one undo
// step; ID and Type are read-only, with the reason; where they differ a row
// reads "Mixed". Numbers come from the probe's document and plans.
// BATCH_SHOTS=<dir> also saves screenshots of batch mode on each tab.
// WHY (Zach, 2026-10-21): "I want to be able to turn the triangle on on many of them".
import { expect, test, type Page } from "@playwright/test";
import { CORE, coreReady, idle, loadExample, openStudio, panelTab, state } from "./helpers";

const SHOTS = process.env.BATCH_SHOTS;
async function shot(page: Page, name: string): Promise<void> {
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/${name}.png` });
}

/** 8 of the sheet's singles and its ChArUco board (examples.ts sticker-sheet). */
const SINGLES = [1, 2, 4, 5, 7, 9, 10, 11].map((n) => `sheet-f${n}`);
const BOARD = "sheet-f6";
const NINE = [...SINGLES, BOARD];

async function sheet(page: Page): Promise<void> {
  await openStudio(page);
  await coreReady(page);
  await loadExample(page, "sticker-sheet");
  await idle(page);
  const s = await state(page);
  for (const id of NINE) expect(s.plans[id]?.ids?.length, `${id} is planned`).toBeGreaterThan(0);
}

/** Shift+click each feature's marker (its first black), then A: the batch panel. */
async function batch(page: Page, fids: string[]): Promise<void> {
  for (const fid of fids) {
    const ink = (await page.locator(`[data-marker="${fid}"] [data-marker-black]`).first().boundingBox())!;
    await page.keyboard.down("Shift");
    await page.mouse.click(ink.x + ink.width / 2, ink.y + ink.height / 2);
    await page.keyboard.up("Shift");
  }
  const s = await state(page);
  const rects = fids.map((fid) => s.doc.features.find((f: any) => f.id === fid).profile.outer);
  expect([...s.selection].sort()).toEqual([...rects].sort());
  await page.keyboard.press("a");
  await idle(page);
  await expect(page.getByTestId("batch-title")).toHaveText(` · ${fids.length} markers`);
}

const feature = (s: any, id: string) => s.doc.features.find((f: any) => f.id === id);
const panel = (page: Page) => page.getByTestId("extrude-panel");

test.describe(`batch editing (${CORE} core)`, () => {
  test.skip(CORE === "mock", "the batch is checked against the real core's plans and auto id");

  test("a · 8 singles + 1 ChArUco: Corner mark Triangle sets all 9 plans; one Ctrl+Z reverts all 9", async ({ page }) => {
    await sheet(page);
    await batch(page, NINE);
    const before = await state(page);
    await expect(page.getByTestId("batch-summary")).toHaveText(/^9 markers · 4X4_50 · ids #/);
    await panelTab(page, "marker");
    await shot(page, "batch-marker");
    await panelTab(page, "make");
    await shot(page, "batch-make");
    await panelTab(page, "label");
    await shot(page, "batch-label");
    await panel(page).locator('[data-batch="marker.corner_mark"] [data-value="triangle"]').click();
    await idle(page);
    let s = await state(page);
    for (const id of NINE) {
      expect(feature(s, id).marker.corner_mark, id).toBe("triangle");
      // the triangle is drawn: a single's ink gains it; the board's merges into its corner square's ink
      expect(JSON.stringify(s.plans[id].black), `${id}'s plan has the triangle`).not.toBe(JSON.stringify(before.plans[id].black));
      if (SINGLES.includes(id)) expect(s.plans[id].black.length, id).toBe(before.plans[id].black.length + 1);
    }
    // a feature outside the selection is untouched
    expect(feature(s, "sheet-f3").marker.corner_mark).toBe("none");
    await expect(panel(page).locator('[data-batch="marker.corner_mark"]')).toHaveAttribute("data-mixed", "0");
    await shot(page, "batch-label-triangle");
    await page.keyboard.press("Control+z");
    await idle(page);
    s = await state(page);
    for (const id of NINE) {
      expect(feature(s, id).marker.corner_mark, id).toBe("none");
      expect(s.plans[id].black, id).toEqual(before.plans[id].black);
    }
    expect(s.canUndo).toBe(false);
  });

  test("b · ID and Type are read-only in batch mode, with reasons; Re-ID… numbers only the selection", async ({ page }) => {
    await sheet(page);
    const before = await state(page);
    await batch(page, NINE);
    await panelTab(page, "marker");
    for (const [path, why] of [["marker.first_id", /Re-ID/], ["marker.type", /Type changes which rows/], ["feature.key", /unique/], ["profile", /own profile/]] as const) {
      const ro = panel(page).locator(`[data-batch-ro="${path}"]`);
      await expect(ro, path).toHaveText("—");
      await expect(ro, path).toHaveAttribute("title", why);
    }
    await expect(panel(page).locator('input[data-path="marker.first_id"]')).toHaveCount(0);
    await expect(panel(page).locator('[data-path="marker.type"]')).toHaveCount(0);
    // a type mix: the board's own rows are hidden
    await expect(panel(page).locator('[data-row="marker.cols"]')).toHaveCount(0);
    // Re-ID…: only the 9 are listed, numbered sequentially from 0; the rest keep their ids
    await panel(page).getByTestId("batch-reid").click();
    const dialog = page.getByTestId("reid-dialog");
    await expect(dialog).toBeVisible();
    await expect(page.getByTestId("reid-apply")).toBeEnabled();
    await expect(dialog.locator("[data-reid-row]")).toHaveCount(9);
    await expect(page.getByTestId("reid-summary")).toContainText("selected markers change");
    await shot(page, "batch-reid");
    await page.getByTestId("reid-apply").click();
    await idle(page);
    const s = await state(page);
    const all = s.doc.features.flatMap((f: any) => s.plans[f.id].ids);
    expect(new Set(all).size, "every id printed once").toBe(all.length);
    for (const f of s.doc.features.filter((g: any) => !NINE.includes(g.id))) {
      expect(s.plans[f.id].ids, `${f.id} is not in the selection: unmoved`).toEqual(before.plans[f.id].ids);
    }
    // the selection's ids: 0, 1, 2 … in document order, stepping over the others'
    const taken = new Set(before.doc.features.filter((g: any) => !NINE.includes(g.id)).flatMap((g: any) => before.plans[g.id].ids));
    const want: number[] = [];
    for (let id = 0; want.length < NINE.reduce((n, fid) => n + before.plans[fid].ids.length, 0); id++) if (!taken.has(id)) want.push(id);
    const order = s.doc.features.filter((g: any) => NINE.includes(g.id));
    expect(order.flatMap((f: any) => s.plans[f.id].ids)).toEqual(want);
  });

  test("c · Label On for all, then Text \"#{id}\": every label shows its own id", async ({ page }) => {
    await sheet(page);
    await batch(page, NINE);
    await panelTab(page, "label");
    const on = panel(page).locator('[data-batch="label.on"] [role="switch"]');
    // the sheet's labels are on: off for all, then on for all
    await on.click();
    await idle(page);
    let s = await state(page);
    for (const id of NINE) expect(feature(s, id).label.on, id).toBe(false);
    await expect(panel(page).locator('[data-batch="label.text"]')).toHaveCount(0);
    await on.click();
    await idle(page);
    s = await state(page);
    for (const id of NINE) expect(feature(s, id).label.on, id).toBe(true);
    const text = panel(page).locator('[data-batch="label.text"] textarea');
    await text.fill("#{id}");
    await page.waitForTimeout(300);
    await idle(page);
    s = await state(page);
    for (const id of NINE) {
      expect(feature(s, id).label.text, id).toBe("#{id}");
      const label = s.plans[id].label;
      expect(label, `${id} has a label`).toBeTruthy();
      const ids: number[] = s.plans[id].ids;
      if (ids.length === 1) expect(label.text, id).toBe(`#${ids[0]}`);
      else expect(label.text, `${id}: a board's own ids`).toContain(`#${ids[0]}`);
    }
    // the labels drawn on the canvas say so too
    const drawn = await page.locator("[data-label]").evaluateAll((els) => els.map((e) => e.textContent ?? ""));
    for (const id of SINGLES) expect(drawn.join(" ")).toContain(`#${s.plans[id].ids[0]}`);
    await shot(page, "batch-label-text");
  });

  test("d · a mixed Dictionary shows Mixed; setting it applies to all", async ({ page }) => {
    await sheet(page);
    // one of them on another dictionary, through its own panel
    const ink = (await page.locator(`[data-marker="${SINGLES[0]}"] [data-marker-black]`).first().boundingBox())!;
    await page.mouse.click(ink.x + ink.width / 2, ink.y + ink.height / 2);
    await expect(panel(page)).toBeVisible();
    await panelTab(page, "marker");
    await page.getByTestId("dd:marker.dictionary").click();
    await page.locator('.kit-select-popup[data-for="marker.dictionary"] [data-value="DICT_5X5_50"]').click();
    await idle(page);
    await page.getByTestId("panel-ok").click();
    await page.keyboard.press("Escape");
    await batch(page, NINE);
    await panelTab(page, "marker");
    const row = panel(page).locator('[data-batch="marker.dictionary"]');
    await expect(row).toHaveAttribute("data-mixed", "1");
    await expect(row.locator(".kit-select-label")).toHaveText("Mixed");
    await expect(page.getByTestId("batch-summary")).toHaveText(/^9 markers · Mixed · ids #/);
    await shot(page, "batch-marker-mixed");
    await page.getByTestId("dd:marker.dictionary").click();
    await page.locator('.kit-select-popup[data-for="marker.dictionary"] [data-value="DICT_4X4_100"]').click();
    await idle(page);
    const s = await state(page);
    for (const id of NINE) expect(feature(s, id).marker.dictionary, id).toBe("DICT_4X4_100");
    expect(feature(s, "sheet-f12").marker.dictionary).toBe("DICT_4X4_50");
    await expect(row).toHaveAttribute("data-mixed", "0");
    await expect(row.locator(".kit-select-label")).toHaveText("4X4_100");
    await expect(page.getByTestId("batch-summary")).toHaveText(/^9 markers · 4X4_100 · ids #/);
  });

  test("e · a typed Marker size 20 applies to all the singles; ↺ makes them driven again", async ({ page }) => {
    await sheet(page);
    await batch(page, SINGLES);
    await panelTab(page, "marker");
    const row = panel(page).locator('[data-batch="marker.marker_mm"]');
    const input = row.locator("input");
    // the singles' driven sizes all fill the same 30 mm squares: one grey value
    await expect(row.locator("[data-driven]")).toHaveAttribute("data-driven", "1");
    await input.fill("20");
    await input.press("Enter");
    await idle(page);
    let s = await state(page);
    for (const id of SINGLES) {
      expect(feature(s, id).marker, id).toMatchObject({ marker_mm: 20, auto: false });
      expect(s.plans[id].marker_mm, id).toBe(20);
    }
    expect(feature(s, "sheet-f12").marker.auto, "not selected").toBe(true);
    await expect(row.locator("[data-driven]")).toHaveAttribute("data-driven", "0");
    await row.locator('[data-reset="marker.marker_mm"]').click();
    await idle(page);
    s = await state(page);
    for (const id of SINGLES) expect(feature(s, id).marker.auto, id).toBe(true);
    for (const id of SINGLES) expect(s.plans[id].marker_mm, id).toBeGreaterThan(20);
    await expect(row.locator("[data-driven]")).toHaveAttribute("data-driven", "1");
  });

  test("f · with the ChArUco in it, the sizes differ: Mixed, and a typed size still sets them all", async ({ page }) => {
    await sheet(page);
    await batch(page, NINE);
    await panelTab(page, "marker");
    const row = panel(page).locator('[data-batch="marker.marker_mm"]');
    await expect(row).toHaveAttribute("data-mixed", "1");
    await expect(row.locator("input")).toHaveAttribute("placeholder", "Mixed");
    await row.locator("input").fill("12");
    await row.locator("input").press("Enter");
    await idle(page);
    const s = await state(page);
    for (const id of NINE) expect(feature(s, id).marker, id).toMatchObject({ marker_mm: 12, auto: false });
    await expect(row).toHaveAttribute("data-mixed", "0");
  });
});
