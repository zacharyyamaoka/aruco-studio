// New marker ids and Re-ID of a selection (Zach, 2026-11-13), on the real core:
// "when you copy paste markers they should increment to the next available
// IDs in order left to right ... deleted markers need to release" and "batch
// select a bunch of ids and then set the starting ID and then it will Re-ID
// all of them, left to right, top to bottom in priority ... starting ID 100
// and then all of them would go 100, 101, etc."
//
// The ruler is independent of the code under test: each marker's place comes
// from its own rectangle in the document (drawn on a known grid, out of
// order), and its ids from the probe's plans -- what the core will print --
// never from DOM presence. Reading order here is by construction: rows top
// (larger y) to bottom, each left to right.
import { expect, test, type Page } from "@playwright/test";
import { CORE, coreReady, dragWorld, idle, openMenu, openStudio, state, toClient } from "./helpers";

const SIDE = 16;                                   // mm: each rectangle profile
const XS = [-40, -10, 20];                         // three columns ...
const YS = [20, -10];                              // ... two rows (y is up)
// drawn out of reading order, so document order is not the answer
const DRAW: [number, number][] = [[20, -10], [-40, 20], [-10, -10], [20, 20], [-40, -10], [-10, 20]];

async function blank(page: Page): Promise<void> {
  await openStudio(page);
  await coreReady(page);
  await openMenu(page, "file");
  await page.getByTestId("cmd-new").click();
}

/** A drag (mm to mm) with the right button: the selection box. */
async function rightDrag(page: Page, from: [number, number], to: [number, number]): Promise<void> {
  const [ax, ay] = await toClient(page, ...from);
  const [bx, by] = await toClient(page, ...to);
  await page.mouse.move(ax, ay);
  await page.mouse.down({ button: "right" });
  for (let i = 1; i <= 10; i++) await page.mouse.move(ax + ((bx - ax) * i) / 10, ay + ((by - ay) * i) / 10);
  await page.mouse.up({ button: "right" });
}

/** Six rectangles (DRAW order), all selected, A: one ArUco Extrude in each, OK. */
async function sixMarkers(page: Page): Promise<void> {
  for (const [x, y] of DRAW) {
    await page.keyboard.press("r");
    await dragWorld(page, [x - SIDE / 2, y - SIDE / 2], [x + SIDE / 2, y + SIDE / 2]);
  }
  await page.keyboard.press("Escape");
  await rightDrag(page, [-60, 40], [40, -30]);
  await page.keyboard.press("a");
  await expect(page.getByTestId("extrude-panel")).toBeVisible();
  await idle(page);
  await page.getByTestId("panel-ok").click();
  await expect(page.getByTestId("extrude-panel")).toHaveCount(0);
  await idle(page);
}

interface Placed { fid: string; cx: number; cy: number; ids: number[]; typed: boolean }

/** Every feature with its rectangle's centre and its printed ids, in reading order (the oracle). */
function placed(s: any): Placed[] {
  const out: Placed[] = s.doc.features.map((f: any) => {
    const r = s.doc.shapes.find((x: any) => x.id === f.profile.outer);
    return { fid: f.id, cx: r.cx, cy: r.cy, ids: s.plans[f.id]?.ids ?? [], typed: f.set.includes("marker.first_id") };
  });
  // rows are exactly level by construction (the grid), so a plain sort is the oracle
  return out.sort((a, b) => b.cy - a.cy || a.cx - b.cx);
}

const firstIds = (ps: Placed[]) => ps.map((p) => p.ids[0]);

/** The marker whose rectangle is centred at (x, y). */
const at = (ps: Placed[], x: number, y: number) => ps.find((p) => Math.abs(p.cx - x) < 0.6 && Math.abs(p.cy - y) < 0.6)!;

test.describe(`New ids and Re-ID of a selection (${CORE} core)`, () => {
  test.skip(CORE === "mock", "the mock core has no assign_ids");

  test("a · A on six rectangles drawn out of order: ids 0–5 left to right, top to bottom", async ({ page }) => {
    await blank(page);
    await sixMarkers(page);
    const ps = placed(await state(page));
    expect(ps).toHaveLength(6);
    expect(firstIds(ps)).toEqual([0, 1, 2, 3, 4, 5]);
  });

  test("b · a deleted marker releases its id: the next paste takes it; pasted rows fill the lowest free ids left to right", async ({ page }) => {
    await blank(page);
    await sixMarkers(page);
    // delete the marker printing #1 (top row, middle): its rectangle stays, its id is free
    const [mx, my] = await toClient(page, XS[1], YS[0]);
    await page.mouse.click(mx, my);
    expect((await state(page)).sel?.kind).toBe("feature");
    await page.keyboard.press("Delete");
    await idle(page);
    let ps = placed(await state(page));
    expect(ps.map((p) => p.ids[0]).sort((a, b) => a - b)).toEqual([0, 2, 3, 4, 5]);
    // copy #0 (top-left) and paste it to the right: the copy takes the released #1, not #6
    const [cx, cy] = await toClient(page, XS[0], YS[0]);
    await page.mouse.click(cx, cy);
    await page.keyboard.press("Control+c");
    const [px, py] = await toClient(page, 60, 20);
    await page.mouse.move(px, py);
    await page.keyboard.press("Control+v");
    await idle(page);
    ps = placed(await state(page));
    expect(at(ps, 60, 20).ids).toEqual([1]);
    // the bottom row (#3 #4 #5) copied and pasted lower down: #6 #7 #8, left to right
    await page.keyboard.press("Escape");
    await rightDrag(page, [-60, 0], [40, -25]);
    await page.keyboard.press("Control+c");
    const [qx, qy] = await toClient(page, -10, -45);
    await page.mouse.move(qx, qy);
    await page.keyboard.press("Control+v");
    await idle(page);
    ps = placed(await state(page));
    const pasted = ps.filter((p) => p.cy < -30);
    expect(pasted).toHaveLength(3);
    expect(firstIds(pasted)).toEqual([6, 7, 8]);
    // nothing printed twice
    const all = ps.flatMap((p) => p.ids);
    expect(new Set(all).size).toBe(all.length);
  });

  test("c · six selected, A, First ID 100: they go 100–105 left to right, top to bottom, a typed id too; DICT_4X4_50 grows to 250", async ({ page }) => {
    await blank(page);
    await sixMarkers(page);
    // type #30 on the bottom-right marker first (a typed id)
    const [tx, ty] = await toClient(page, XS[2], YS[1]);
    await page.mouse.dblclick(tx, ty);
    await expect(page.getByTestId("extrude-panel")).toBeVisible();
    const id = page.locator('input[data-path="marker.first_id"]');
    await id.fill("30");
    await id.press("Enter");
    await idle(page);
    await page.getByTestId("panel-ok").click();
    await idle(page);
    expect(at(placed(await state(page)), XS[2], YS[1])).toMatchObject({ ids: [30], typed: true });
    // all six, A: the batch panel; First ID 100
    await page.keyboard.press("Escape");
    await rightDrag(page, [-60, 40], [40, -30]);
    await page.keyboard.press("a");
    await expect(page.getByTestId("batch-first-id")).toBeVisible();
    const first = page.getByTestId("batch-first-id").locator("input");
    await expect(first).toHaveValue("0");
    await first.fill("100");
    await first.press("Enter");
    await expect.poll(async () => firstIds(placed(await state(page)))).toEqual([100, 101, 102, 103, 104, 105]);
    await idle(page);
    const s = await state(page);
    const ps = placed(s);
    expect(firstIds(ps)).toEqual([100, 101, 102, 103, 104, 105]);
    // DICT_4X4_50 ends at #49: the dictionary grew to DICT_4X4_250 (same patterns, more ids), and the note says so
    for (const f of s.doc.features) expect(f.marker.dictionary).toBe("DICT_4X4_250");
    await expect(page.getByTestId("note")).toContainText("4X4_50 → 4X4_250");
    // driven now, every one in the ledger (so they stay), the typed one included
    for (const p of ps) {
      expect(p.typed).toBe(false);
      expect(s.doc.id_ledger[s.doc.features.find((f: any) => f.id === p.fid).key]).toBe(p.ids[0]);
    }
    await page.getByTestId("panel-ok").click();
    await idle(page);
    // the ids hold once the panel is closed and auto id has run again
    expect(firstIds(placed(await state(page)))).toEqual([100, 101, 102, 103, 104, 105]);
    // and a start that fits keeps the dictionary: the top row from 10
    await page.keyboard.press("Escape");
    await rightDrag(page, [-60, 40], [40, 5]);
    await page.keyboard.press("a");
    const again = page.getByTestId("batch-first-id").locator("input");
    await expect(again).toHaveValue("100");
    await again.fill("10");
    await again.press("Enter");
    await expect.poll(async () => firstIds(placed(await state(page)))).toEqual([10, 11, 12, 103, 104, 105]);
    await page.getByTestId("panel-ok").click();
    await idle(page);
    expect(firstIds(placed(await state(page)))).toEqual([10, 11, 12, 103, 104, 105]);
  });

  test("d · a canvas selection, right-click › ArUco Re-ID 3 selected…, Start 100: only those, left to right", async ({ page }) => {
    await blank(page);
    await sixMarkers(page);
    await page.keyboard.press("Escape");
    // the bottom row only
    await rightDrag(page, [-60, 0], [40, -25]);
    const [rx, ry] = await toClient(page, XS[1], YS[1]);
    await page.mouse.click(rx, ry, { button: "right" });
    await expect(page.getByTestId("canvas-menu")).toBeVisible();
    await page.getByTestId("cm-reid").click();
    await expect(page.getByTestId("reid-dialog")).toBeVisible();
    await expect(page.getByTestId("reid-dialog")).toContainText("3 selected");
    // the preview lists the selection in reading order
    await expect(page.locator("[data-reid-row]")).toHaveCount(3);
    const start = page.getByTestId("reid-start").locator("input");
    await start.fill("100");
    await start.press("Enter");
    await expect.poll(() => page.locator("[data-reid-row]").evaluateAll((rows) => rows.map((r) => r.getAttribute("data-new"))))
      .toEqual(["#100", "#101", "#102"]);
    await expect(page.getByTestId("reid-grow")).toContainText("4X4_50 → 4X4_250");
    await page.getByTestId("reid-apply").click();
    await expect(page.getByTestId("reid-dialog")).toHaveCount(0);
    await idle(page);
    const ps = placed(await state(page));
    expect(firstIds(ps)).toEqual([0, 1, 2, 100, 101, 102]);
    // Edit › ArUco Re-ID… reads the same selection
    await openMenu(page, "edit");
    await page.getByTestId("cmd-reid").click();
    await expect(page.getByTestId("reid-dialog")).toContainText("3 selected");
    await page.getByTestId("reid-cancel").click();
  });
});
