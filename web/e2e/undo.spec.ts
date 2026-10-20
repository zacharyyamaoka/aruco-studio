// Undo / redo of the document (web/src/store.ts) and live typing into the
// canvas dimensions (web/src/sketch/Dims.tsx DimEditor), on the static build.
// Each check measures the probe's numbers: the document, the plan the core
// drew, and the history's canUndo / canRedo.
import { expect, test, type Page } from "@playwright/test";
import { CORE, coreReady, dragWorld, idle, openStudio, planOutline, state } from "./helpers";

async function blank(page: Page): Promise<void> {
  await openStudio(page);
  await coreReady(page);
  await page.getByTestId("menu-file").click();
  await page.getByTestId("cmd-new").click();
}

/** R, a 60 × 60 rectangle about the origin, A: the panel open on the new feature. Returns its id. */
async function rectAndExtrude(page: Page): Promise<string> {
  await page.keyboard.press("r");
  await dragWorld(page, [-30, -30], [30, 30]);
  await page.keyboard.press("a");
  await expect(page.getByTestId("extrude-panel")).toBeVisible();
  await idle(page);
  const s = await state(page);
  expect(s.plan, "the new feature is planned").toBeTruthy();
  return s.panel.featureId;
}

const undo = async (page: Page) => { await page.keyboard.press("Control+z"); await idle(page); };
const redo = async (page: Page) => { await page.keyboard.press("Control+Shift+z"); await idle(page); };

const rectOf = (s: any, id: string) => s.doc.shapes.find((x: any) => x.id === id);

test.describe(`undo / redo (${CORE} core)`, () => {
  test("a · draw, A, marker 12 by its dimension, move: Ctrl+Z ×3 walks those back one by one, Ctrl+Shift+Z ×3 redoes them", async ({ page }) => {
    test.skip(CORE === "mock", "the mock core returns no dims");
    await blank(page);
    const fid = await rectAndExtrude(page);
    const sA = await state(page);
    const rid = sA.feature.rectId as string;
    expect(sA.feature.marker.auto).toBe(true);
    const driven = sA.plan.marker_mm as number;
    expect(Math.abs(driven - 12)).toBeGreaterThan(1);

    // the marker to 12 through its dimension
    await page.locator('[data-dim-label="marker.marker_mm"]').click();
    await page.getByTestId("dim-input").fill("12");
    await page.getByTestId("dim-input").press("Enter");
    await expect(page.getByTestId("dim-input")).toHaveCount(0);
    await idle(page);
    const s12 = await state(page);
    expect(s12.feature.marker).toMatchObject({ auto: false, marker_mm: 12 });
    expect(Math.abs(s12.plan.marker_mm - 12)).toBeLessThan(0.1);

    // move the rectangle by (10, 5): a press-drag on its marker
    await dragWorld(page, [0, 0], [10, 5]);
    await idle(page);
    const sMoved = await state(page);
    expect(rectOf(sMoved, rid).cx).toBeCloseTo(rectOf(sA, rid).cx + 10, 0);
    expect(rectOf(sMoved, rid).cy).toBeCloseTo(rectOf(sA, rid).cy + 5, 0);
    const movedPlan = await planOutline(page);
    expect(sMoved.canUndo).toBe(true);
    expect(sMoved.canRedo).toBe(false);

    // 1: the move back; the marker still 12, drawn back where it was
    await undo(page);
    let s = await state(page);
    expect(rectOf(s, rid)).toEqual(rectOf(sA, rid));
    expect(s.feature?.marker).toMatchObject({ auto: false, marker_mm: 12 });
    let o = await planOutline(page);
    expect(o.cx).toBeCloseTo(movedPlan.cx - 10, 1);
    expect(o.cy).toBeCloseTo(movedPlan.cy - 5, 1);
    expect(s.canRedo).toBe(true);

    // 2: the 12 back to driven
    await undo(page);
    s = await state(page);
    expect(s.doc.features.map((f: any) => f.id)).toEqual([fid]);
    expect(s.doc.features[0].marker.auto).toBe(true);
    expect(Math.abs(s.plans[fid].marker_mm - driven)).toBeLessThan(0.01);

    // 3: the feature gone (A undone); the rectangle stays, the panel closes
    await undo(page);
    s = await state(page);
    expect(s.doc.features).toHaveLength(0);
    expect(rectOf(s, rid)).toEqual(rectOf(sA, rid));
    expect(s.panel.open).toBe(false);
    await expect(page.locator("[data-marker]")).toHaveCount(0);

    // redo: A, the 12, the move
    await redo(page);
    s = await state(page);
    expect(s.doc.features.map((f: any) => f.id)).toEqual([fid]);
    expect(s.doc.features[0].marker.auto).toBe(true);
    expect(rectOf(s, rid)).toEqual(rectOf(sA, rid));
    await redo(page);
    s = await state(page);
    expect(s.doc.features[0].marker).toMatchObject({ auto: false, marker_mm: 12 });
    expect(Math.abs(s.plans[fid].marker_mm - 12)).toBeLessThan(0.1);
    await redo(page);
    s = await state(page);
    expect(rectOf(s, rid)).toEqual(rectOf(sMoved, rid));
    expect(s.canRedo).toBe(false);
    await expect(page.locator(`[data-marker="${fid}"]`)).toHaveCount(1);
  });

  test("b · typing 15 into a dimension redraws the marker before Enter; one Ctrl+Z takes the whole burst back", async ({ page }) => {
    test.skip(CORE === "mock", "the mock core returns no dims");
    await blank(page);
    const fid = await rectAndExtrude(page);
    const before = (await state(page)).plan.marker_mm as number;

    await page.locator('[data-dim-label="marker.marker_mm"]').click();
    const input = page.getByTestId("dim-input");
    await expect(input).toBeFocused();
    // slower than the live delay: "1" is drawn, then "15", as two live commits
    await page.keyboard.type("15", { delay: 300 });
    await expect.poll(async () => (await state(page)).plan?.marker_mm, { timeout: 2000 }).toBeCloseTo(15, 0);
    await expect(input).toBeVisible();   // not Enter: still typing
    const s15 = await state(page);
    expect(s15.feature.marker).toMatchObject({ auto: false, marker_mm: 15 });
    expect(Math.abs(s15.plan.marker_mm - 15)).toBeLessThan(0.1);

    await input.press("Enter");
    await expect(input).toHaveCount(0);
    await idle(page);
    await undo(page);
    const s = await state(page);
    expect(s.doc.features.map((f: any) => f.id), "one step: the feature is still there").toEqual([fid]);
    expect(s.doc.features[0].marker.auto).toBe(true);
    expect(Math.abs(s.plans[fid].marker_mm - before)).toBeLessThan(0.01);

    // Ctrl+Y redoes it
    await page.keyboard.press("Control+y");
    await idle(page);
    expect((await state(page)).doc.features[0].marker).toMatchObject({ auto: false, marker_mm: 15 });
  });

  test("c · Ctrl+Z in a focused field is the field's: the document stays", async ({ page }) => {
    await blank(page);
    await rectAndExtrude(page);
    const s0 = await state(page);
    expect(s0.canUndo).toBe(true);

    const field = page.locator('input[data-path="marker.marker_mm"]');
    await field.click();
    await expect(field).toBeFocused();
    await page.keyboard.press("Control+z");
    await idle(page);
    let s = await state(page);
    expect(s.doc).toEqual(s0.doc);
    expect(s.canRedo).toBe(false);
    await expect(field).toBeFocused();
    await field.press("Escape");

    if (CORE === "real") {
      await page.locator('[data-dim-label="marker.marker_mm"]').click();
      await expect(page.getByTestId("dim-input")).toBeFocused();
      await page.keyboard.press("Control+z");
      await idle(page);
      s = await state(page);
      expect(s.doc).toEqual(s0.doc);
      expect(s.canRedo).toBe(false);
    }
  });

  test("d · delete a feature, Ctrl+Z: it is back with its id, key and ledger entry", async ({ page }) => {
    await blank(page);
    await rectAndExtrude(page);
    await page.getByTestId("panel-ok").click();
    await page.keyboard.press("r");
    await dragWorld(page, [50, -30], [110, 30]);
    const fid = await rectAndExtrude(page);
    await page.getByTestId("panel-ok").click();
    await idle(page);
    const s0 = await state(page);
    const f0 = s0.doc.features.find((f: any) => f.id === fid);
    expect(s0.doc.features).toHaveLength(2);
    if (CORE === "real") expect(s0.doc.id_ledger[f0.key], "auto id gave it a ledger entry").toBe(f0.marker.first_id);

    // select it (a click on its marker) and delete it
    const b = (await page.locator(`[data-marker="${fid}"]`).boundingBox())!;
    await page.mouse.click(b.x + b.width / 2, b.y + b.height / 2);
    expect((await state(page)).sel).toEqual({ kind: "feature", id: fid });
    await page.keyboard.press("Delete");
    await idle(page);
    let s = await state(page);
    expect(s.doc.features.map((f: any) => f.id)).not.toContain(fid);
    if (CORE === "real") expect(s.doc.id_ledger[f0.key], "the ledger drops a removed feature").toBeUndefined();

    await undo(page);
    s = await state(page);
    const back = s.doc.features.find((f: any) => f.id === fid);
    expect(back).toBeTruthy();
    expect(back.key).toBe(f0.key);
    expect(back.marker.first_id).toBe(f0.marker.first_id);
    expect(s.doc.id_ledger).toEqual(s0.doc.id_ledger);
    expect(s.plans[fid], "it is drawn again").toBeTruthy();
    await expect(page.locator(`[data-marker="${fid}"]`)).toHaveCount(1);
  });
});
