// Multi-feature documents, WYSIWYG inspection (a click on a marker opens its
// panel; no timeline) and driven vs set values (docs/design/online_studio_v1.md,
// "Many features, driven vs set"), on the static build. Each
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

/** A click in the middle of a feature's marker (its black or its white quiet zone). */
async function clickMarker(page: Page, fid: string): Promise<void> {
  const b = (await page.locator(`[data-marker="${fid}"]`).boundingBox())!;
  await page.mouse.click(b.x + b.width / 2, b.y + b.height / 2);
}

async function colour(page: Page, path: string): Promise<string> {
  return page.locator(`input[data-path="${path}"]`).evaluate((e) => getComputedStyle(e).color);
}

test.describe(`multi-feature documents (${CORE} core)`, () => {
  test("a · two rectangles, A on each: two markers, each in its rectangle; a click on each opens its panel; Print has both", async ({ page }) => {
    await blank(page);
    const r1 = await drawRect(page, [-60, -20], [-20, 20]);
    const f1 = await extrudeOk(page);
    const r2 = await drawRect(page, [20, -20], [60, 20]);
    const f2 = await extrudeOk(page, 5);
    expect(f1).not.toBe(f2);

    const s = await state(page);
    // A on a drawn (selected) rectangle: that rectangle on its own is the profile
    expect(s.doc.features.map((f: any) => [f.id, f.key, f.profile])).toEqual([[f1, f1, { outer: r1, holes: [] }], [f2, f2, { outer: r2, holes: [] }]]);
    expect(Object.keys(s.plans).sort()).toEqual([f1, f2].sort());

    // drawn: two black paths, each inside its own rectangle's box
    await expect(page.locator("[data-marker-black]")).toHaveCount(2);
    for (const [f, r] of [[f1, r1], [f2, r2]]) {
      // WHY a poll (2026-10-20, ~1 run in 12 under parallel load): idle() settles
      // on the store; React can paint the marker a frame later, so the box read
      // right after it was 0 px wide. The final width must still be the marker's.
      const ink = page.locator(`[data-marker="${f}"] [data-marker-black]`);
      await expect.poll(async () => (await ink.boundingBox())?.width ?? 0, { timeout: 5000 }).toBeGreaterThan(20);
      const black = (await ink.boundingBox())!;
      const rect = (await page.locator(`[data-shape="${r}"]`).boundingBox())!;
      const pl = (await state(page)).plans[f];
      expect(black.width, `marker ${f}: plan ok=${pl?.ok} black=${pl?.black?.length} ids=${JSON.stringify(pl?.ids)} warnings=${JSON.stringify((pl?.warnings ?? []).filter((w: any) => w.level !== "info"))}`).toBeGreaterThan(20);
      expect(inside(rect, black), `marker ${f} ${JSON.stringify(black)} in rectangle ${r} ${JSON.stringify(rect)}`).toBe(true);
    }
    await page.screenshot({ path: path.join(SHOTS, "two-features-canvas.png") });

    // no timeline: a click on a marker opens that feature's panel
    await expect(page.getByTestId("timeline")).toHaveCount(0);
    await expect(page.getByTestId("extrude-panel")).toHaveCount(0);
    // f1's id is driven: auto id's (core.assign_ids), the one its plan prints
    const id1 = String(s.plans[f1].ids[0]);
    expect(s.doc.features[0].marker.first_id).toBe(Number(id1));
    for (const [f, n, first] of [[f1, 1, id1], [f2, 2, "5"], [f1, 1, id1]] as const) {
      await clickMarker(page, f);
      await expect(page.getByTestId("extrude-panel")).toBeVisible();
      await expect(page.getByTestId("extrude-panel")).toContainText(`ArUco Extrude ${n}`);
      await expect(page.locator('input[data-path="marker.first_id"]')).toHaveValue(first);
      const st = await state(page);
      expect(st.panel.featureId).toBe(f);
      expect(st.sel).toEqual({ kind: "feature", id: f });
    }
    // a click on empty canvas closes it
    await clickAt(page, 0, 45);
    await expect(page.getByTestId("extrude-panel")).toHaveCount(0);
    expect((await state(page)).sel).toBeNull();
    expect((await state(page)).doc.features).toHaveLength(2);

    // Print: one sheet with both id sets
    await page.keyboard.press("p");
    const sheet = page.locator('[data-testid="print-page"] svg');
    await expect(sheet).toBeVisible({ timeout: 45_000 });
    const texts = await sheet.locator("text").allTextContents();
    expect(texts).toContain(`#${id1}`);
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

    await clickMarker(page, f1);
    await expect.poll(async () => (await state(page)).sel).toEqual({ kind: "feature", id: f1 });
    await expect(page.getByTestId("extrude-panel")).toBeVisible();
    await page.keyboard.press("Delete");
    await idle(page);

    await expect(page.locator("[data-marker-black]")).toHaveCount(1);
    await expect(page.locator(`[data-marker="${f2}"] [data-marker-black]`)).toHaveCount(1);
    await expect(page.locator(`[data-marker="${f1}"]`)).toHaveCount(0);
    await expect(page.locator(`[data-shape="${r1}"]`)).toHaveCount(1);
    await expect(page.getByTestId("extrude-panel")).toHaveCount(0);
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
    await expect(markerBox).toHaveAttribute("title", /fills the profile/);
    let s = await state(page);
    const v0 = Number(await marker.inputValue());
    expect(v0).toBeCloseTo(s.plan.marker_mm, 4);
    expect(s.feature.marker.auto).toBe(true);

    // a set row: First ID 3 (its driven value is auto id's)
    const first = page.locator('input[data-path="marker.first_id"]');
    const autoId = await first.inputValue();
    expect(Number(autoId)).toBe(s.plan.ids[0]);
    // WHY not a fixed "3": the key is random, so its hashed auto id sometimes IS
    // 3, and typing the value a field already shows is no edit (no change event)
    const typed = String((Number(autoId) + 1) % 50);
    await first.fill(typed);
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
    await first.fill(String((Number(typed) + 1) % 50));
    await first.press("Escape");
    await expect(first).toHaveValue(typed);
    expect((await state(page)).feature.marker.first_id).toBe(Number(typed));
    await first.fill("");
    await first.press("Enter");
    await idle(page);
    await expect(page.locator('[data-drv="marker.first_id"]')).toHaveAttribute("data-driven", "1");
    await expect(first).toHaveValue(autoId);
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
    expect(s.doc).toMatchObject({ version: 3, name: "Old plate", id_ledger: {} });
    expect(s.doc.features).toHaveLength(1);
    const f = s.doc.features[0];
    expect(f.key).toBe(f.id);
    // its rectangle on its own is its profile now (2026-10-20 evening)
    expect(f.profile).toEqual({ outer: "r1", holes: [] });
    expect(s.plans[f.id]?.ids).toEqual([4, 5, 6, 7]);
    const black = (await page.locator(`[data-marker="${f.id}"] [data-marker-black]`).boundingBox())!;
    const rect = (await page.locator('[data-shape="r1"]').boundingBox())!;
    expect(inside(rect, black)).toBe(true);
    // its typed values are set, the rest driven
    await clickMarker(page, f.id);
    await expect(page.getByTestId("extrude-panel")).toBeVisible();
    await expect(page.locator('[data-drv="marker.first_id"]')).toHaveAttribute("data-driven", "0");
    await expect(page.locator('[data-drv="marker.marker_mm"]')).toHaveAttribute("data-driven", "1");
    await expect(page.locator('[data-drv="marker.cols"]')).toHaveAttribute("data-driven", "1");
  });

  test("e · Suggest is one dropdown; each option shows its whole reason; picking one sets the fields", async ({ page }) => {
    await openStudio(page);
    await coreReady(page);
    await clickAt(page, 60, 40);
    await page.keyboard.press("a");
    await idle(page);
    await page.locator('[data-path="marker.type"] [data-value="grid"]').click();
    await idle(page);
    const s = await state(page);
    expect(s.suggestions.length).toBeGreaterThan(1);
    // compact: one row, its options only in the popup
    await expect(page.getByTestId("suggestion")).toHaveCount(0);
    const trigger = page.getByTestId("suggest-trigger");
    expect((await trigger.boundingBox())!.height).toBeLessThanOrEqual(26);
    await trigger.click();
    const reasons = page.getByTestId("suggestion-reason");
    await expect(reasons).toHaveCount(s.suggestions.length);
    for (let i = 0; i < s.suggestions.length; i++) {
      const r = reasons.nth(i);
      await expect(r).toBeVisible();
      await expect(r).toHaveText(s.suggestions[i].reason);
      await expect(page.getByTestId("suggestion").nth(i)).toContainText(s.suggestions[i].label);
      const clip = await r.evaluate((e) => ({ sw: e.scrollWidth, cw: e.clientWidth, sh: e.scrollHeight, ch: e.clientHeight }));
      expect(clip.sw, `reason ${i} is not clipped across`).toBeLessThanOrEqual(clip.cw + 1);
      expect(clip.sh, `reason ${i} is not clipped down`).toBeLessThanOrEqual(clip.ch + 1);
    }
    await page.screenshot({ path: path.join(SHOTS, "suggest-dropdown.png") });
    const pick = s.suggestions[1];
    await page.getByTestId("suggestion").nth(1).click();
    await idle(page);
    const after = await state(page);
    expect(after.feature.marker).toMatchObject({ auto: false, cols: pick.params.cols, rows: pick.params.rows, marker_mm: pick.params.marker_mm });
    expect(after.feature.set).toEqual(expect.arrayContaining(["marker.cols", "marker.rows"]));
    await expect(page.locator('[data-drv="marker.marker_mm"]')).toHaveAttribute("data-driven", "0");
    await expect(trigger).toContainText(pick.label);
  });

  test("g · the toolbar floats at the bottom centre of the viewport", async ({ page }) => {
    await openStudio(page);
    const vp = (await page.getByTestId("viewport").boundingBox())!;
    const tb = (await page.getByTestId("toolbar").boundingBox())!;
    expect(Math.abs(tb.x + tb.width / 2 - (vp.x + vp.width / 2))).toBeLessThanOrEqual(1);
    expect(vp.y + vp.height - (tb.y + tb.height)).toBeGreaterThanOrEqual(4);
    expect(vp.y + vp.height - (tb.y + tb.height)).toBeLessThanOrEqual(20);
    await expect(page.getByTestId("timeline")).toHaveCount(0);
  });

  test("f · a phone: the docked panel takes about 45 %, the toolbar sits above it, the marker is fitted above both", async ({ page }) => {
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
    expect(tools.y + tools.height).toBeLessThanOrEqual(panel.y);
    expect(Math.abs(tools.x + tools.width / 2 - 195)).toBeLessThanOrEqual(1);
    const vp = (await page.getByTestId("viewport").boundingBox())!;
    const fid = (await state(page)).feature.id;
    await expect.poll(async () => {
      const boxes = [await page.locator("[data-marker-outline]").boundingBox(), await page.locator(`[data-fit-rect="${fid}"]`).boundingBox()];
      return boxes.every((m) => !!m && m.y >= vp.y + 18 && m.y + m.height <= tools.y && m.x >= 0 && m.x + m.width <= 390);
    }, { message: "the marker and the box it was placed in are fully between the ruler and the toolbar" }).toBe(true);
    const m = (await page.locator("[data-marker-outline]").boundingBox())!;
    expect(m.height).toBeGreaterThan(60);   // fitted, not a speck
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: path.join(SHOTS, "phone-panel-fit.png") });
  });
});

// WHY (2026-10-18): the label commits ~120 ms after each keystroke; a click on
// another marker inside that window used to land the keystrokes on the newly
// selected marker. Each edit now belongs to the marker it was typed into.
test("label keystrokes land on the marker they were typed into, even with an immediate click on another", async ({ page }) => {
  await blank(page);
  const r1 = await drawRect(page, [-60, -20], [-20, 20]);
  const f1 = await extrudeOk(page);
  await drawRect(page, [20, -20], [60, 20]);
  const f2 = await extrudeOk(page);
  await clickMarker(page, f1);                                   // marker 1's panel
  await expect.poll(async () => (await state(page)).panel.featureId).toBe(f1);
  await page.locator('[role=tab][data-tab="label"]').click();
  const before2 = (await state(page)).doc.features.find((f: any) => f.id === f2).label.text;
  await page.locator('textarea[data-path="label.text"]').fill("RACE");
  await clickMarker(page, f2);                                   // marker 2, inside the 120 ms window
  await idle(page);
  await expect.poll(async () => (await state(page)).doc.features.find((f: any) => f.id === f1).label.text,
    { timeout: 3000 }).toBe("RACE");
  const s = await state(page);
  expect(s.doc.features.find((f: any) => f.id === f2).label.text).toBe(before2);
  expect(s.doc.features.find((f: any) => f.id === f1).profile).toEqual({ outer: r1, holes: [] });
});
