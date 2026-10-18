// Multi-feature documents and driven vs set values (docs/design/online_studio_v1.md,
// "Multi-feature documents" and "Driven vs set"), on the static build. Each
// check measures: the probe's numbers, the drawn elements' boxes, the
// computed colours. Screenshots go to E2E_SHOTS (default test-results/shots).
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { CORE, clickAt, coreReady, dragWorld, idle, openStudio, state } from "./helpers";

const SHOTS = process.env.E2E_SHOTS ?? "test-results/shots";
const FIXTURE = path.join(import.meta.dirname, "fixtures", "v1-plate.arucostudio-web.json");

async function blank(page: Page): Promise<void> {
  await openStudio(page);
  await coreReady(page);
  await page.getByTestId("menu-file").click();
  await page.getByTestId("cmd-new").click();
}

/** R, drag a rectangle (mm corners); it is left selected. Returns its id. */
async function drawRect(page: Page, a: [number, number], b: [number, number]): Promise<string> {
  await page.keyboard.press("r");
  await dragWorld(page, a, b);
  const s = await state(page);
  expect(s.sel?.kind).toBe("shape");
  return s.sel.id;
}

/** A on the selected rectangle, then OK. Returns the feature's id. */
async function extrudeOk(page: Page, firstId?: number): Promise<string> {
  await page.keyboard.press("a");
  await expect(page.getByTestId("extrude-panel")).toBeVisible();
  if (firstId !== undefined) {
    const id = page.locator('input[data-path="marker.first_id"]');
    await id.fill(String(firstId));
    await id.press("Enter");
  }
  await idle(page);
  const fid = (await state(page)).panel.featureId as string;
  await page.getByTestId("panel-ok").click();
  await idle(page);
  return fid;
}

/** b lies inside a (px, with a pixel of slack). */
function inside(a: { x: number; y: number; width: number; height: number }, b: { x: number; y: number; width: number; height: number }) {
  return b.x >= a.x - 1 && b.y >= a.y - 1 && b.x + b.width <= a.x + a.width + 1 && b.y + b.height <= a.y + a.height + 1;
}

async function colour(page: Page, path: string): Promise<string> {
  return page.locator(`input[data-path="${path}"]`).evaluate((e) => getComputedStyle(e).color);
}

test.describe(`multi-feature documents (${CORE} core)`, () => {
  test("a · two rectangles, A on each: two markers, each in its rectangle; the timeline and Print have both", async ({ page }) => {
    await blank(page);
    const r1 = await drawRect(page, [-60, -20], [-20, 20]);
    const f1 = await extrudeOk(page);
    const r2 = await drawRect(page, [20, -20], [60, 20]);
    const f2 = await extrudeOk(page, 5);
    expect(f1).not.toBe(f2);

    const s = await state(page);
    expect(s.doc.features.map((f: any) => [f.id, f.key, f.rectId])).toEqual([[f1, f1, r1], [f2, f2, r2]]);
    expect(Object.keys(s.plans).sort()).toEqual([f1, f2].sort());

    // drawn: two black paths, each inside its own rectangle's box
    await expect(page.locator("[data-marker-black]")).toHaveCount(2);
    for (const [f, r] of [[f1, r1], [f2, r2]]) {
      const black = (await page.locator(`[data-marker="${f}"] [data-marker-black]`).boundingBox())!;
      const rect = (await page.locator(`[data-shape="${r}"]`).boundingBox())!;
      expect(black.width).toBeGreaterThan(20);
      expect(inside(rect, black), `marker ${f} ${JSON.stringify(black)} in rectangle ${r} ${JSON.stringify(rect)}`).toBe(true);
    }
    await page.screenshot({ path: path.join(SHOTS, "two-features-canvas.png") });

    // the timeline: Sketch, then each feature's extrude and joint origin
    await expect(page.locator('[data-tl="extrude"]')).toHaveText(["ArUco Extrude 1", "ArUco Extrude 2"]);
    await expect(page.locator('[data-tl="origin"]')).toHaveText(["Joint Origin 1", "Joint Origin 2"]);

    // Print: one sheet with both id sets
    await page.keyboard.press("p");
    const sheet = page.locator('[data-testid="print-page"] svg');
    await expect(sheet).toBeVisible({ timeout: 45_000 });
    const texts = await sheet.locator("text").allTextContents();
    expect(texts).toContain("#0");
    expect(texts).toContain("#5");
    await page.screenshot({ path: path.join(SHOTS, "two-features-print.png") });
  });

  test("b · delete one feature: its marker goes, the other stays, its rectangle stays", async ({ page }) => {
    await blank(page);
    const r1 = await drawRect(page, [-60, -20], [-20, 20]);
    const f1 = await extrudeOk(page);
    await drawRect(page, [20, -20], [60, 20]);
    const f2 = await extrudeOk(page);
    await expect(page.locator("[data-marker-black]")).toHaveCount(2);

    await page.locator(`[data-tl="extrude"][data-feature="${f1}"]`).click();
    await expect.poll(async () => (await state(page)).sel).toEqual({ kind: "feature", id: f1 });
    await page.keyboard.press("Delete");
    await idle(page);

    await expect(page.locator("[data-marker-black]")).toHaveCount(1);
    await expect(page.locator(`[data-marker="${f2}"] [data-marker-black]`)).toHaveCount(1);
    await expect(page.locator(`[data-marker="${f1}"]`)).toHaveCount(0);
    await expect(page.locator(`[data-shape="${r1}"]`)).toHaveCount(1);
    await expect(page.locator('[data-tl="extrude"]')).toHaveText(["ArUco Extrude 1"]);
    const s = await state(page);
    expect(s.doc.features.map((f: any) => f.id)).toEqual([f2]);
    expect(Object.keys(s.plans)).toEqual([f2]);
    expect(s.doc.shapes.map((x: any) => x.id)).toContain(r1);
  });

  test("c · driven vs set: grey and following, typed and kept, ↺ back to driven", async ({ page }) => {
    await blank(page);
    await drawRect(page, [-20, -20], [20, 20]);
    await page.keyboard.press("a");
    await idle(page);
    const marker = page.locator('input[data-path="marker.marker_mm"]');
    const markerBox = page.locator('[data-drv="marker.marker_mm"]');
    await expect(page.locator('[data-path="marker.auto"]')).toHaveCount(0);   // no Auto switch

    // driven: the plan's value, grey, its driver in the tooltip
    await expect(markerBox).toHaveAttribute("data-driven", "1");
    await expect(markerBox).toHaveAttribute("title", /fills the rectangle/);
    let s = await state(page);
    const v0 = Number(await marker.inputValue());
    expect(v0).toBeCloseTo(s.plan.marker_mm, 4);
    expect(s.feature.marker.auto).toBe(true);

    // a set row: First ID 3
    const first = page.locator('input[data-path="marker.first_id"]');
    await first.fill("3");
    await first.press("Enter");
    await idle(page);
    await expect(page.locator('[data-drv="marker.first_id"]')).toHaveAttribute("data-driven", "0");
    const setColour = await colour(page, "marker.first_id");
    const drivenColour = await colour(page, "marker.marker_mm");
    expect(drivenColour).not.toBe(setColour);
    await page.screenshot({ path: path.join(SHOTS, "panel-driven-and-set.png") });

    // resize the rectangle: the driven marker size follows
    await dragWorld(page, [20, 20], [30, 30]);
    await idle(page);
    s = await state(page);
    expect(s.doc.shapes[0]).toMatchObject({ w: 50, h: 50 });
    const v1 = Number(await marker.inputValue());
    expect(v1).toBeGreaterThan(v0 + 5);
    expect(v1).toBeCloseTo(s.plan.marker_mm, 4);

    // type 12: set, the set colour; a later resize leaves 12
    await marker.fill("12");
    await marker.press("Enter");
    await idle(page);
    await expect(markerBox).toHaveAttribute("data-driven", "0");
    expect(await colour(page, "marker.marker_mm")).toBe(setColour);
    s = await state(page);
    expect(s.feature.marker).toMatchObject({ auto: false, marker_mm: 12 });
    // the core draws it on the preset's cell grid (12 -> a whole number of cells), as typed otherwise
    const planned12 = s.plan.marker_mm;
    expect(Math.abs(planned12 - 12)).toBeLessThan(0.1);
    await page.screenshot({ path: path.join(SHOTS, "panel-marker-set.png") });
    await dragWorld(page, [30, 30], [35, 35]);
    await idle(page);
    s = await state(page);
    expect(s.doc.shapes[0]).toMatchObject({ w: 55, h: 55 });
    await expect(marker).toHaveValue("12");
    expect(s.feature.marker).toMatchObject({ auto: false, marker_mm: 12 });
    expect(s.plan.marker_mm).toBe(planned12);

    // ↺: driven again, grey, following the rectangle
    await page.locator('[data-reset="marker.marker_mm"]').click();
    await idle(page);
    await expect(markerBox).toHaveAttribute("data-driven", "1");
    expect(await colour(page, "marker.marker_mm")).toBe(drivenColour);
    s = await state(page);
    expect(s.feature.marker.auto).toBe(true);
    const v2 = Number(await marker.inputValue());
    expect(v2).toBeGreaterThan(v1);
    expect(v2).toBeCloseTo(s.plan.marker_mm, 4);

    // keys: Esc reverts an edit; an empty field + Enter returns it to driven
    await first.fill("9");
    await first.press("Escape");
    await expect(first).toHaveValue("3");
    expect((await state(page)).feature.marker.first_id).toBe(3);
    await first.fill("");
    await first.press("Enter");
    await idle(page);
    await expect(page.locator('[data-drv="marker.first_id"]')).toHaveAttribute("data-driven", "1");
    await expect(first).toHaveValue("0");
    expect(await colour(page, "marker.first_id")).toBe(drivenColour);
  });

  test("d · an old one-feature file opens as one feature that plans", async ({ page }) => {
    await openStudio(page);
    await coreReady(page);
    await page.getByTestId("menu-file").click();
    const [chooser] = await Promise.all([page.waitForEvent("filechooser"), page.getByTestId("cmd-open").click()]);
    await chooser.setFiles(FIXTURE);
    await expect(page.getByTestId("note")).toContainText("Opened v1-plate");
    await idle(page);
    const s = await state(page);
    expect(s.doc).toMatchObject({ version: 2, name: "Old plate", id_ledger: {} });
    expect(s.doc.features).toHaveLength(1);
    const f = s.doc.features[0];
    expect(f.key).toBe(f.id);
    expect(f.rectId).toBe("r1");
    expect(s.plans[f.id]?.ids).toEqual([4, 5, 6, 7]);
    const black = (await page.locator(`[data-marker="${f.id}"] [data-marker-black]`).boundingBox())!;
    const rect = (await page.locator('[data-shape="r1"]').boundingBox())!;
    expect(inside(rect, black)).toBe(true);
    // its typed values are set, the rest driven
    await page.locator(`[data-tl="extrude"][data-feature="${f.id}"]`).dblclick();
    await expect(page.getByTestId("extrude-panel")).toBeVisible();
    await expect(page.locator('[data-drv="marker.first_id"]')).toHaveAttribute("data-driven", "0");
    await expect(page.locator('[data-drv="marker.marker_mm"]')).toHaveAttribute("data-driven", "1");
    await expect(page.locator('[data-drv="marker.cols"]')).toHaveAttribute("data-driven", "1");
  });

  test("e · the suggestions show their whole reason (wrapped, never clipped)", async ({ page }) => {
    await openStudio(page);
    await coreReady(page);
    await clickAt(page, 60, 40);
    await page.keyboard.press("a");
    await idle(page);
    await page.locator('[data-path="marker.type"] [data-value="grid"]').click();
    await idle(page);
    const s = await state(page);
    expect(s.suggestions.length).toBeGreaterThan(0);
    const reasons = page.getByTestId("suggestion-reason");
    await expect(reasons).toHaveCount(s.suggestions.length);
    for (let i = 0; i < s.suggestions.length; i++) {
      const r = reasons.nth(i);
      await expect(r).toHaveText(s.suggestions[i].reason);
      const clip = await r.evaluate((e) => ({ sw: e.scrollWidth, cw: e.clientWidth, sh: e.scrollHeight, ch: e.clientHeight }));
      expect(clip.sw, `reason ${i} is not clipped across`).toBeLessThanOrEqual(clip.cw + 1);
      expect(clip.sh, `reason ${i} is not clipped down`).toBeLessThanOrEqual(clip.ch + 1);
      await expect(page.getByTestId("suggestion").nth(i)).toHaveAttribute("title", new RegExp(s.suggestions[i].reason.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
    }
  });

  test("f · a phone: the docked panel takes about 45 %, the marker is fitted above it", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openStudio(page);
    await coreReady(page);
    await clickAt(page, 60, 40);
    await page.keyboard.press("a");
    await idle(page);
    const panel = (await page.getByTestId("extrude-panel").boundingBox())!;
    expect(panel.height).toBeGreaterThan(0.4 * 844);
    expect(panel.height).toBeLessThanOrEqual(0.46 * 844);
    expect(Math.abs(panel.y + panel.height - 844)).toBeLessThanOrEqual(1);
    const tools = (await page.getByTestId("toolbar").boundingBox())!;
    const rectId = (await state(page)).feature.rectId;
    await expect.poll(async () => {
      const boxes = [await page.locator("[data-marker-outline]").boundingBox(), await page.locator(`[data-shape="${rectId}"]`).boundingBox()];
      return boxes.every((m) => !!m && m.y >= tools.y + tools.height && m.y + m.height <= panel.y && m.x >= 0 && m.x + m.width <= 390);
    }, { message: "the marker and its rectangle are fully between the toolbar and the panel" }).toBe(true);
    const m = (await page.locator("[data-marker-outline]").boundingBox())!;
    expect(m.height).toBeGreaterThan(60);   // fitted, not a speck
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: path.join(SHOTS, "phone-panel-fit.png") });
  });
});
