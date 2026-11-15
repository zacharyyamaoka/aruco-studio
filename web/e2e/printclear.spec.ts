// Print margins and keep-clear boxes (Zach, 2026-11-13: "custom spacing
// margins, top bottom left right, when I go to print ... draw an avoid box and
// then you recalculate it ... it's on a per page basis"). Six features, then
// Print: Top = 60 moves every sticker under 60 mm; a box drawn by mouse on
// page 1 keeps every sticker of page 1 out of it; both survive closing and
// reopening the dialog; deleting the box by its × brings the layout back.
// Every check reads the core's answer (the side's data-placements, the
// request it was laid out from), never the overlay's presence alone.
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { CORE, coreReady, dragWorld, idle, labelOn, openStudio, state, openMenu } from "./helpers";

const SHOTS = process.env.E2E_SHOTS ?? "test-results/shots";
const TOP = 60;
type Placement = { item: number; page: number; x_mm: number; y_mm: number; w_mm: number; h_mm: number };
type Box = [number, number, number, number];   // x0, y0, x1, y1 mm

// six of sheet.spec.ts's rectangles
const RECTS: [[number, number], [number, number]][] = [
  [[-100, -45], [-60, -20]], [[-50, -45], [-10, -15]], [[0, -45], [35, -10]], [[45, -45], [85, -20]],
  [[-100, 10], [-60, 40]], [[-50, 5], [-15, 40]],
];

async function feature(page: Page, a: [number, number], b: [number, number]): Promise<void> {
  await page.keyboard.press("r");
  await dragWorld(page, a, b);
  expect((await state(page)).sel?.kind, `the rectangle from ${a} to ${b}`).toBe("shape");
  await page.keyboard.press("a");
  await expect(page.getByTestId("extrude-panel")).toBeVisible();
  await labelOn(page);
  await idle(page);
  await page.getByTestId("panel-ok").click();
  await idle(page);
}

async function openSheet(page: Page): Promise<void> {
  await page.getByTestId("act-print").click();
  await expect(page.getByTestId("print-dialog")).toBeVisible();
  await expect(page.locator('[data-testid="print-page"] svg').first()).toBeVisible({ timeout: 45_000 });
  await idle(page);
}

/** The request the sheet on screen was laid out from, once it is the one the
 *  controls ask for, and where the core put each sticker. */
async function laid(page: Page, want: (r: Record<string, any>) => boolean): Promise<{ request: Record<string, any>; placements: Placement[] }> {
  const side = page.getByTestId("sheet-side");
  await expect.poll(async () => {
    await idle(page);
    const raw = await side.getAttribute("data-request");
    const busy = await page.locator(".sheet-body").getAttribute("data-busy");
    return !!raw && busy === "0" && want(JSON.parse(raw));
  }, { message: "the sheet is laid out from the expected request" }).toBe(true);
  return { request: JSON.parse((await side.getAttribute("data-request"))!), placements: JSON.parse((await side.getAttribute("data-placements"))!) };
}

const rect = (p: Placement): Box => [p.x_mm, p.y_mm, p.x_mm + p.w_mm, p.y_mm + p.h_mm];
const overlaps = (a: Box, b: Box) => Math.min(a[2], b[2]) - Math.max(a[0], b[0]) > 1e-6 && Math.min(a[3], b[3]) - Math.max(a[1], b[1]) > 1e-6;

/** Drag on page `n` (1-based) of the preview from one page point (mm) to another. */
async function drawOn(page: Page, n: number, from: [number, number], to: [number, number]): Promise<void> {
  const layer = page.locator(`[data-testid="keep-layer"][data-page="${n}"]`).first();
  await layer.scrollIntoViewIfNeeded();
  const r = (await layer.boundingBox())!;
  const [pw, ph] = (await page.getByTestId("print-page").nth(n - 1).getAttribute("data-page-mm"))!.split("x").map(Number);
  const at = ([x, y]: [number, number]) => [r.x + (x / pw) * r.width, r.y + (y / ph) * r.height] as const;
  const [ax, ay] = at(from), [bx, by] = at(to);
  await page.mouse.move(ax, ay);
  await page.mouse.down();
  for (let i = 1; i <= 10; i++) await page.mouse.move(ax + ((bx - ax) * i) / 10, ay + ((by - ay) * i) / 10);
  await page.mouse.up();
}

test.describe(`print margins and keep-clear boxes (${CORE} core)`, () => {
  test.skip(CORE === "mock", "the mock core has no packer: the layout is the real core's");

  test("Top 60 mm, a box drawn on page 1, kept over a reopen, deleted by its ×: the core lays the sheet out round them", async ({ page }) => {
    test.setTimeout(240_000);
    await openStudio(page);
    await coreReady(page);
    await page.evaluate(() => localStorage.removeItem("aruco-studio.print-clear.v1"));
    await openMenu(page, "file");
    await page.getByTestId("cmd-new").click();
    for (const [a, b] of RECTS) await feature(page, a, b);
    expect((await state(page)).doc.features).toHaveLength(RECTS.length);
    await openSheet(page);

    // nothing typed: every side is driven (grey), the request carries no margins and no boxes
    const plain = await laid(page, (r) => !("margins_mm" in r) && !("keep_clear" in r));
    expect(plain.placements).toHaveLength(RECTS.length);
    for (const s of ["top", "right", "bottom", "left"]) await expect(page.locator(`[data-testid="sheet-margin-${s}"] [data-driven]`)).toHaveAttribute("data-driven", "1");
    expect(Math.min(...plain.placements.map((p) => p.y_mm))).toBeLessThan(TOP);

    // Top = 60: every sticker starts at 60 mm or lower, the first exactly there
    const top = page.locator('[data-testid="sheet-margin-top"] input');
    await top.fill(String(TOP));
    await top.press("Enter");
    await expect(page.locator('[data-testid="sheet-margin-top"] [data-driven]')).toHaveAttribute("data-driven", "0");
    const margined = await laid(page, (r) => r.margins_mm?.top === TOP && !("keep_clear" in r));
    expect(margined.request.margins_mm).toEqual({ top: TOP });
    expect(margined.placements).toHaveLength(RECTS.length);
    for (const p of margined.placements) expect(p.y_mm, `item ${p.item}`).toBeGreaterThanOrEqual(TOP - 1e-6);
    expect(Math.min(...margined.placements.map((p) => p.y_mm))).toBeCloseTo(TOP, 4);
    await expect(page.getByTestId("keep-area").first()).toBeVisible();   // the printable area, while a margin is typed

    // a box drawn on page 1 where stickers are now
    const want: Box = [20, 70, 110, 150];
    expect(margined.placements.some((p) => p.page === 0 && overlaps(rect(p), want)), "stickers sit where the box goes").toBe(true);
    await page.getByTestId("keep-draw").click();
    await expect(page.locator(".keep-layer.drawing").first()).toBeVisible();
    await drawOn(page, 1, [want[0], want[1]], [want[2], want[3]]);
    await expect(page.getByTestId("keep-box")).toHaveCount(1);
    // Esc leaves Draw box, the dialog stays
    await page.keyboard.press("Escape");
    await expect(page.locator(".keep-layer.drawing")).toHaveCount(0);
    await expect(page.getByTestId("print-dialog")).toBeVisible();
    const kept = await laid(page, (r) => r.keep_clear?.length === 1);
    const k = kept.request.keep_clear[0];
    expect(k.page).toBe(0);
    const box: Box = [k.x_mm, k.y_mm, k.x_mm + k.w_mm, k.y_mm + k.h_mm];
    box.forEach((v, i) => expect(Math.abs(v - want[i]), `corner ${i} of the drawn box`).toBeLessThanOrEqual(0.5));
    expect(kept.request.margins_mm).toEqual({ top: TOP });
    expect(kept.placements).toHaveLength(RECTS.length);
    for (const p of kept.placements) {
      expect(p.y_mm).toBeGreaterThanOrEqual(TOP - 1e-6);
      if (p.page === 0) expect(overlaps(rect(p), box), `item ${p.item} on page 1 is clear of the box`).toBe(false);
    }
    await expect(page.getByTestId("keep-row-0")).toContainText("Page 1");

    // kept in this browser (a reload reads them back)
    const stored = await page.evaluate(() => JSON.parse(localStorage.getItem("aruco-studio.print-clear.v1") ?? "null"));
    expect(stored?.margins).toEqual({ top: TOP });
    expect(stored?.boxes).toHaveLength(1);

    // closed and opened again: the margin and the box are still there
    await page.locator(".kit-dialog-x").click();
    await expect(page.getByTestId("print-dialog")).toHaveCount(0);
    await openSheet(page);
    await expect(page.locator('[data-testid="sheet-margin-top"] input')).toHaveValue(String(TOP));
    await expect(page.locator('[data-testid="sheet-margin-top"] [data-driven]')).toHaveAttribute("data-driven", "0");
    await expect(page.getByTestId("keep-box")).toHaveCount(1);
    const again = await laid(page, (r) => r.keep_clear?.length === 1 && r.margins_mm?.top === TOP);
    expect(again.placements).toEqual(kept.placements);

    // a second box (the screenshots: margins and two boxes, Actual size and Fit)
    await page.getByTestId("keep-draw").click();
    await drawOn(page, 1, [125, 170], [195, 215]);
    await page.getByTestId("keep-draw").click();
    await expect(page.locator(".keep-layer.drawing")).toHaveCount(0);
    await expect(page.getByTestId("keep-box")).toHaveCount(2);
    const two = await laid(page, (r) => r.keep_clear?.length === 2);
    for (const p of two.placements.filter((q) => q.page === 0))
      for (const c of two.request.keep_clear.filter((q: any) => q.page === 0))
        expect(overlaps(rect(p), [c.x_mm, c.y_mm, c.x_mm + c.w_mm, c.y_mm + c.h_mm])).toBe(false);
    await page.getByTestId("print-page").first().scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(SHOTS, "printclear-actual.png") });
    await page.getByTestId("print-mode").locator('[data-value="fit"]').click();
    await expect(page.getByTestId("print-stage")).toHaveAttribute("data-mode", "fit");
    await page.getByTestId("keep-box").first().click();          // selected: the accent
    await page.screenshot({ path: path.join(SHOTS, "printclear-fit.png") });
    await page.getByTestId("keep-box").nth(1).hover();
    await page.screenshot({ path: path.join(SHOTS, "printclear-fit-hover.png") });
    // Delete removes the selected box
    await page.getByTestId("keep-box").nth(1).click();
    await page.keyboard.press("Delete");
    await expect(page.getByTestId("keep-box")).toHaveCount(1);
    await laid(page, (r) => r.keep_clear?.length === 1);

    // the box deleted by its ×: the layout comes back
    const only = page.getByTestId("keep-box").first();
    await only.hover();
    await only.getByTestId("keep-x").click();
    await expect(page.getByTestId("keep-box")).toHaveCount(0);
    const back = await laid(page, (r) => !("keep_clear" in r) && r.margins_mm?.top === TOP);
    expect(back.placements).toEqual(margined.placements);

    // and the margin back to driven: the plain layout
    await page.locator('[data-testid="sheet-margin-top"] [data-reset]').click();
    const plainAgain = await laid(page, (r) => !("margins_mm" in r) && !("keep_clear" in r));
    expect(plainAgain.placements).toEqual(plain.placements);
  });
});
