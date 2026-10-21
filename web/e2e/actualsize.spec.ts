// The canvas's right-click menu and Actual size (Zach, 2026-10-21: "Please
// add a right click menu to arucostudio.com. I want the option to scale to
// actual size, vs fit. When actual size it should determine my screen
// resolution etc and correctly display it so I can see the things to
// scale"). Measured, never assumed: what a right-click opens and where, what a
// right-drag still selects (the box and its bounds on screen), a 30 mm marker
// at Actual size as 30 x px/mm CSS px (getBoundingClientRect), the
// calibration kept across a reload, and the scale following the screen when
// its DPR or its size changes (Chrome's device metrics, as another monitor).
// Screenshots go to ACTUAL_SHOTS (default test-results/actualsize).
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { coreReady, dragWorld, idle, openMenu, openStudio, panelTab, state, toClient } from "./helpers";

const SHOTS = process.env.ACTUAL_SHOTS ?? "test-results/actualsize";
const shot = (page: Page, name: string) => page.screenshot({ path: path.join(SHOTS, `${name}.png`) });
const KEY = "arucoStudio.actualSize";
const CSS_MM = 96 / 25.4;
const menu = (page: Page) => page.getByTestId("canvas-menu");
const indicator = (page: Page) => page.getByTestId("zoom-indicator");
const zoom = async (page: Page): Promise<number> => (await state(page)).camera.zoom;

/** Calibrations in this browser before the page loads: { "1280x800@1": px/mm, … }. */
async function stub(page: Page, screens: Record<string, number>): Promise<void> {
  await page.addInitScript(([key, s]) => {
    const all = Object.fromEntries(Object.entries(s).map(([k, v]) => [k, { pxPerMm: v, by: "card", at: "2026-10-21T00:00:00.000Z" }]));
    window.localStorage.setItem(key, JSON.stringify({ v: 1, screens: all }));
  }, [KEY, screens] as const);
}

/** This page's screen key, as the Studio keys it (src/zoom/scale.ts screenKey). */
const screenKey = (page: Page) => page.evaluate(() => `${screen.width}x${screen.height}@${+devicePixelRatio.toFixed(3)}`);

async function fresh(page: Page): Promise<void> {
  await openStudio(page);
  await coreReady(page);
  await openMenu(page, "file");
  await page.getByTestId("cmd-new").click();
}

/** A rectangle by its corners (mm); its id. */
async function rect(page: Page, a: [number, number], b: [number, number]): Promise<string> {
  await page.keyboard.press("r");
  await dragWorld(page, a, b);
  const s = await state(page);
  expect(s.sel?.kind, `the rectangle ${a} to ${b}`).toBe("shape");
  return s.sel.id;
}

/** A 30 mm marker in a 40 mm rectangle about the origin; its feature id. Nothing selected after. */
async function marker30(page: Page): Promise<string> {
  await rect(page, [-20, -20], [20, 20]);
  await page.keyboard.press("a");
  await expect(page.getByTestId("extrude-panel")).toBeVisible();
  await idle(page);
  await panelTab(page, "marker");
  const size = page.locator('input[data-path="marker.marker_mm"]');
  await size.fill("30");
  await size.press("Enter");
  await idle(page);
  await page.getByTestId("panel-ok").click();
  await idle(page);
  const s = await state(page);
  const fid = s.doc.features[0].id;
  expect(s.plans[fid].marker_mm).toBe(30);
  await page.keyboard.press("Escape");
  return fid;
}

/** The marker's black, as drawn (client px). */
const black = async (page: Page, fid: string) => (await page.locator(`[data-marker="${fid}"] [data-marker-black]`).first().boundingBox())!;

/** A right-click (no move) at client px. */
const rightClick = (page: Page, x: number, y: number) => page.mouse.click(x, y, { button: "right" });

/** A right-button press, moved `dx` px, released. */
async function rightNudge(page: Page, x: number, y: number, dx: number): Promise<void> {
  await page.mouse.move(x, y);
  await page.mouse.down({ button: "right" });
  await page.mouse.move(x + dx, y);
  await page.mouse.up({ button: "right" });
}

test.describe("the canvas's right-click menu", () => {
  test("a · a right-click opens it where it was released; a right-drag is still the selection box, and selects what it boxes", async ({ page }) => {
    await fresh(page);
    const P = await rect(page, [-50, -35], [50, 35]);
    const A = await rect(page, [-40, -20], [-10, 10]);
    const B = await rect(page, [5, -20], [35, 10]);
    await page.keyboard.press("Escape");
    await page.keyboard.press("f");
    const [ox, oy] = await toClient(page, 0, 0);
    await page.mouse.move(ox, oy);
    await page.mouse.wheel(0, 400);
    await page.waitForTimeout(100);

    // a right-click on empty canvas: the menu, its corner at the pointer (room below it); the canvas rows and the zoom
    const [ex, ey] = await toClient(page, 70, 20);
    await rightClick(page, ex, ey);
    await expect(menu(page)).toBeVisible();
    await expect(menu(page)).toHaveAttribute("data-target", "canvas");
    const m = (await menu(page).boundingBox())!;
    expect(Math.abs(m.x - ex), "the menu's left at the pointer").toBeLessThanOrEqual(4);
    expect(Math.abs(m.y - ey), "the menu's top at the pointer").toBeLessThanOrEqual(4);
    for (const id of ["cm-paste", "cm-zoom-fit", "cm-zoom-selection", "cm-actual-size", "cm-zoom-100", "cm-calibrate"]) await expect(page.getByTestId(id), id).toBeVisible();
    for (const id of ["cm-copy", "cm-duplicate", "cm-delete", "cm-edit"]) await expect(page.getByTestId(id), id).toHaveCount(0);
    await expect(page.getByTestId("cm-paste")).toHaveAttribute("data-disabled", "");
    await expect(page.getByTestId("cm-zoom-selection"), "nothing selected").toHaveAttribute("data-disabled", "");
    expect((await state(page)).selection).toEqual([]);
    await shot(page, "a-menu-empty-canvas");
    await page.keyboard.press("Escape");
    await expect(menu(page)).toHaveCount(0);

    // the threshold: 3 px of travel is still a click (the menu), 10 px is a drag (no menu)
    await rightNudge(page, ex, ey, 3);
    await expect(menu(page)).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(menu(page)).toHaveCount(0);
    await rightNudge(page, ex, ey, 10);
    await page.waitForTimeout(150);
    await expect(menu(page)).toHaveCount(0);

    // a right-drag round everything: the box is drawn while it drags, no menu after, all three selected
    const [ax, ay] = await toClient(page, -60, 45);
    const [bx, by] = await toClient(page, 60, -45);
    await page.mouse.move(ax, ay);
    await page.mouse.down({ button: "right" });
    for (let i = 1; i <= 10; i++) await page.mouse.move(ax + ((bx - ax) * i) / 10, ay + ((by - ay) * i) / 10);
    const box = (await page.getByTestId("select-box").boundingBox())!;
    expect(Math.abs(box.width - (bx - ax)), "the box spans the drag").toBeLessThanOrEqual(1.5);
    await page.mouse.up({ button: "right" });
    await page.waitForTimeout(150);
    await expect(menu(page)).toHaveCount(0);
    expect([...(await state(page)).selection].sort()).toEqual([P, A, B].sort());
    await expect(page.getByTestId("selection-count")).toHaveText("3 selected");
    // the selection's bounds on screen are the boxed shapes' (the plate's outline)
    const bounds = (await page.getByTestId("selection-bounds").boundingBox())!;
    const plate = (await page.locator(`[data-shape="${P}"]`).boundingBox())!;
    for (const k of ["x", "y", "width", "height"] as const) expect(Math.abs(bounds[k] - plate[k]), `bounds ${k}`).toBeLessThanOrEqual(1.5);

    // a right-click inside the selection keeps it; Duplicate puts all three down beside it (100 + 10 mm on)
    const [ix, iy] = await toClient(page, -25, -5);
    await rightClick(page, ix, iy);
    await expect(menu(page)).toHaveAttribute("data-target", "shapes");
    expect([...(await state(page)).selection].sort()).toEqual([P, A, B].sort());
    await page.getByTestId("cm-duplicate").click();
    await expect(menu(page)).toHaveCount(0);
    const s = await state(page);
    expect(s.doc.shapes).toHaveLength(6);
    const copies = s.doc.shapes.slice(3);
    expect(s.selection).toEqual(copies.map((c: { id: string }) => c.id));
    expect(copies.map((c: { cx: number; cy: number }) => [c.cx, c.cy])).toEqual([[110, 0], [85, -5], [130, -5]]);
  });

  test("b · on a marker: Edit ArUco Extrude, Copy, Paste here, Duplicate, Delete, Turn, Export SVG; each runs, the marker selected first", async ({ page }) => {
    await fresh(page);
    const fid = await marker30(page);
    const ink = await black(page, fid);
    await rightClick(page, ink.x + ink.width / 2, ink.y + ink.height / 2);
    await expect(menu(page)).toHaveAttribute("data-target", "marker");
    for (const id of ["cm-edit", "cm-copy", "cm-paste", "cm-duplicate", "cm-delete", "cm-turn", "cm-svg", "cm-zoom-fit", "cm-zoom-selection", "cm-actual-size", "cm-zoom-100", "cm-calibrate"]) {
      await expect(page.getByTestId(id), id).toBeVisible();
    }
    await expect(menu(page).locator(".kit-menu-label")).toHaveText([
      "Edit ArUco Extrude", "Copy", "Paste here", "Duplicate", "Delete", "Turn 90°", "Export SVG",
      "Zoom to fit", "Zoom to selection", /^Actual size/, "Zoom 100 %", /Calibrate actual size…$/,
    ]);
    // selected as a click selects it, without its panel (Edit opens that)
    let s = await state(page);
    expect(s.sel).toEqual({ kind: "feature", id: fid });
    expect(s.panel.open).toBe(false);
    await shot(page, "b-menu-on-marker");

    // Duplicate: its rectangle and its marker, 40 + 10 mm to the right, the copy selected
    await page.getByTestId("cm-duplicate").click();
    await idle(page);
    s = await state(page);
    expect(s.doc.features).toHaveLength(2);
    const copy = s.doc.shapes[1];
    expect([copy.cx, copy.cy, copy.w, copy.h]).toEqual([50, 0, 40, 40]);
    const f2 = s.doc.features[1];
    expect(f2.profile.outer).toBe(copy.id);
    await expect.poll(async () => (await state(page)).plans[f2.id]?.ids?.[0]).toBeDefined();
    expect((await state(page)).plans[f2.id].ids[0], "the copy takes the next id").not.toBe((await state(page)).plans[fid].ids[0]);

    // Delete on the copy's marker: its marker goes (its rectangle stays, as Del after a click)
    const ink2 = await black(page, f2.id);
    await rightClick(page, ink2.x + ink2.width / 2, ink2.y + ink2.height / 2);
    await expect(menu(page)).toHaveAttribute("data-target", "marker");
    await page.getByTestId("cm-delete").click();
    s = await state(page);
    expect(s.doc.features.map((f: { id: string }) => f.id)).toEqual([fid]);
    expect(s.doc.shapes).toHaveLength(2);

    // Turn 90°
    await rightClick(page, ink.x + ink.width / 2, ink.y + ink.height / 2);
    await page.getByTestId("cm-turn").click();
    await idle(page);
    expect((await state(page)).doc.features[0].marker.turn).toBe(90);

    // Copy, then Paste here on empty canvas: the copy centred where the menu was opened
    await rightClick(page, ink.x + ink.width / 2, ink.y + ink.height / 2);
    await page.getByTestId("cm-copy").click();
    const [px, py] = await toClient(page, -70, 30);
    await rightClick(page, px, py);
    await expect(menu(page)).toHaveAttribute("data-target", "canvas");
    await expect(page.getByTestId("cm-paste")).not.toHaveAttribute("data-disabled", "");
    await page.getByTestId("cm-paste").click();
    s = await state(page);
    const pasted = s.doc.shapes[2];
    expect(Math.abs(pasted.cx - -70), "pasted at the click (x)").toBeLessThanOrEqual(0.5);
    expect(Math.abs(pasted.cy - 30), "pasted at the click (y)").toBeLessThanOrEqual(0.5);
    expect(s.doc.features).toHaveLength(2);

    // Edit ArUco Extrude opens its panel; with it open, Edit is greyed
    await rightClick(page, ink.x + ink.width / 2, ink.y + ink.height / 2);
    await page.getByTestId("cm-edit").click();
    await expect(page.getByTestId("extrude-panel")).toBeVisible();
    expect((await state(page)).panel.featureId).toBe(fid);
    await rightClick(page, ink.x + ink.width / 2, ink.y + ink.height / 2);
    await expect(page.getByTestId("cm-edit")).toHaveAttribute("data-disabled", "");
    await page.keyboard.press("Escape");
    await expect(menu(page)).toHaveCount(0);
  });
});

test.describe("Actual size", () => {
  test("c · at a stubbed 4.37 px/mm a 30 mm marker is 131.1 CSS px (±1), about the right-click; 100 % is 96 px/in; Shift+0 / 1 / 2", async ({ page }) => {
    await stub(page, { "1280x800@1": 4.37 });
    await fresh(page);
    expect(await screenKey(page), "the screen this test stubbed").toBe("1280x800@1");
    expect((await state(page)).scale).toMatchObject({ key: "1280x800@1", pxPerMm: 4.37, calibrated: true });
    const fid = await marker30(page);
    // and a rectangle off to the side, so the fit (everything) is not the marker's frame
    await rect(page, [60, 30], [100, 55]);
    await page.keyboard.press("Escape");

    // the menu's Actual size, on the marker: the zoom is the scale; the marker stays under the pointer
    const ink = await black(page, fid);
    const at: [number, number] = [ink.x + ink.width / 2, ink.y + ink.height / 2];
    await rightClick(page, ...at);
    await expect(page.getByTestId("cm-actual-size").locator(".kit-menu-label")).toHaveText("Actual size");
    await page.getByTestId("cm-actual-size").click();
    expect(await zoom(page)).toBe(4.37);
    let b = await black(page, fid);
    expect(Math.abs(b.width - 30 * 4.37), `the black is ${b.width} px wide`).toBeLessThanOrEqual(1);
    expect(Math.abs(b.height - 30 * 4.37), `the black is ${b.height} px tall`).toBeLessThanOrEqual(1);
    expect(Math.abs(b.x + b.width / 2 - at[0]), "about the click (x)").toBeLessThanOrEqual(1);
    expect(Math.abs(b.y + b.height / 2 - at[1]), "about the click (y)").toBeLessThanOrEqual(1);
    // calibrated: the indicator says Actual size, and nothing else
    await expect(indicator(page)).toHaveText("Actual size");
    await expect(indicator(page)).toHaveAttribute("data-calibrated", "1");
    await expect(page.getByTestId("zoom-estimated")).toHaveCount(0);

    // Zoom 100 %: CSS's millimetre
    await rightClick(page, ...at);
    await page.getByTestId("cm-zoom-100").click();
    expect(await zoom(page)).toBeCloseTo(CSS_MM, 12);
    b = await black(page, fid);
    expect(Math.abs(b.width - 30 * CSS_MM)).toBeLessThanOrEqual(1);
    await expect(indicator(page)).toHaveText("100 %");

    // the keys: Shift+0 Actual size, Shift+1 the fit (F's), Shift+2 the selection (the marker, framed in the middle)
    await page.keyboard.press("Shift+Digit0");
    expect(await zoom(page)).toBe(4.37);
    await page.keyboard.press("Shift+Digit1");
    const fitted = (await state(page)).camera;
    await page.keyboard.press("Shift+Digit0");
    await page.keyboard.press("f");
    expect((await state(page)).camera).toEqual(fitted);
    await page.keyboard.press("Escape");
    expect((await state(page)).sel).toBeNull();
    await page.keyboard.press("Shift+Digit2");
    expect((await state(page)).camera, "nothing selected: Shift+2 leaves the view").toEqual(fitted);
    // the marker selected (a right-click; Esc closes the menu and keeps it), Shift+2 frames it
    const ink3 = await black(page, fid);
    await rightClick(page, ink3.x + ink3.width / 2, ink3.y + ink3.height / 2);
    await page.keyboard.press("Escape");
    await expect(menu(page)).toHaveCount(0);
    expect((await state(page)).sel).toEqual({ kind: "feature", id: fid });
    await page.keyboard.press("Shift+Digit2");
    const vp = (await page.getByTestId("viewport").boundingBox())!;
    b = await black(page, fid);
    expect(Math.abs(b.x + b.width / 2 - (vp.x + vp.width / 2)), "framed in the middle").toBeLessThanOrEqual(2);
    expect(await zoom(page)).toBeGreaterThan(fitted.zoom);
  });

  test("d · uncalibrated it says so: Actual size (estimated — calibrate), in the menu too", async ({ page }) => {
    await fresh(page);
    const sc = (await state(page)).scale;
    expect(sc.calibrated).toBe(false);
    await page.keyboard.press("Shift+Digit0");
    expect(await zoom(page)).toBe(sc.pxPerMm);
    await expect(indicator(page)).toHaveText("Actual size (estimated — calibrate)");
    await expect(indicator(page)).toHaveAttribute("data-calibrated", "0");
    const [ex, ey] = await toClient(page, 70, -40);
    await rightClick(page, ex, ey);
    await expect(page.getByTestId("cm-actual-size").locator(".kit-menu-label")).toHaveText("Actual size estimated");
    await page.keyboard.press("Escape");
    // any other zoom: a percent (of 96 px/in)
    await page.keyboard.press("Shift+Digit1");
    const z = await zoom(page);
    await expect(indicator(page)).toHaveText(`${Math.round((z / CSS_MM) * 100)} %`);
  });

  test("e · calibrate: the card's edge, the slider, −/+ and a ruler set the scale; Save keeps it for this screen, across a reload; Reset forgets it", async ({ page }) => {
    await fresh(page);
    const est = (await state(page)).scale.pxPerMm;
    await page.keyboard.press("Shift+Digit0");
    await page.getByTestId("zoom-calibrate").click();
    const dlg = page.getByTestId("calibrate-dialog");
    await expect(dlg).toBeVisible();
    const card = page.getByTestId("cal-card");
    const width = async () => (await card.boundingBox())!.width;
    expect(Math.abs((await width()) - 85.6 * est), "the card at the estimate").toBeLessThanOrEqual(0.5);
    await expect(page.getByTestId("cal-status")).toContainText("not calibrated: estimated from");

    // drag its edge 43 px wider: the scale follows the card
    const grip = (await page.getByTestId("cal-grip").boundingBox())!;
    await page.mouse.move(grip.x + grip.width / 2, grip.y + grip.height / 2);
    await page.mouse.down();
    for (let i = 1; i <= 5; i++) await page.mouse.move(grip.x + grip.width / 2 + (43 * i) / 5, grip.y + grip.height / 2);
    await page.mouse.up();
    const w1 = await width();
    expect(Math.abs(w1 - (85.6 * est + 43))).toBeLessThanOrEqual(1);
    expect(Number(await page.getByTestId("cal-value").getAttribute("data-px-per-mm"))).toBeCloseTo(w1 / 85.6, 2);
    // + and − step 0.2 %
    const v = async () => Number(await page.getByTestId("cal-value").getAttribute("data-px-per-mm"));
    const v0 = await v();
    await page.getByTestId("cal-plus").click();
    expect(await v()).toBeCloseTo(v0 * 1.002, 9);
    await page.getByTestId("cal-minus").click();
    expect(await v()).toBeCloseTo(v0 * 1.002 * 0.998, 9);
    // the ruler: the line measures 80 mm, so it is (its px / 80) px per mm
    const line = Number(await page.getByTestId("cal-line").getAttribute("data-px"));
    expect((await page.getByTestId("cal-line").boundingBox())!.width).toBeCloseTo(line, 1);
    await page.getByTestId("cal-ruler-mm").fill("80");
    const want = line / 80;
    expect(await v()).toBeCloseTo(want, 9);
    expect(Math.abs((await width()) - 85.6 * want)).toBeLessThanOrEqual(0.5);
    await shot(page, "c-calibration-card");
    await page.getByTestId("cal-save").click();
    await expect(dlg).toHaveCount(0);

    // kept for this screen; Actual size was showing, so it moved to the new scale at once
    const key = await screenKey(page);
    expect((await state(page)).scale).toMatchObject({ key, pxPerMm: want, calibrated: true });
    expect(await zoom(page)).toBe(want);
    await expect(indicator(page)).toHaveText("Actual size");
    const kept = JSON.parse((await page.evaluate((k) => localStorage.getItem(k), KEY))!);
    expect(kept.screens[key]).toMatchObject({ pxPerMm: want, by: "ruler" });

    // across a reload
    await page.reload();
    await coreReady(page);
    expect((await state(page)).scale).toMatchObject({ key, pxPerMm: want, calibrated: true });
    await page.keyboard.press("Shift+Digit0");
    expect(await zoom(page)).toBe(want);
    await expect(indicator(page)).toHaveText("Actual size");

    // Reset to estimate: forgotten, and the Actual size showing goes back to the guess, said to be one
    await openMenu(page, "view");
    await page.getByTestId("cmd-calibrate").click();
    await expect(page.getByTestId("cal-status")).toContainText("calibrated with a ruler");
    await page.getByTestId("cal-forget").click();
    expect((await state(page)).scale).toMatchObject({ calibrated: false, pxPerMm: est });
    expect(await zoom(page)).toBe(est);
    await expect(indicator(page)).toHaveText("Actual size (estimated — calibrate)");
    expect(JSON.parse((await page.evaluate((k) => localStorage.getItem(k), KEY))!).screens[key]).toBeUndefined();
  });

  test("f · it follows the screen: another DPR (a monitor, a page zoom) or another size at the same DPR is another key, and Actual size moves to its scale", async ({ page }) => {
    await stub(page, { "1280x800@1": 4.37, "1280x800@2": 2.9 });
    await fresh(page);
    await marker30(page);
    await page.keyboard.press("Shift+Digit0");
    expect(await zoom(page)).toBe(4.37);
    const cdp = await page.context().newCDPSession(page);
    const metrics = (dpr: number, sw = 1280, sh = 800) =>
      cdp.send("Emulation.setDeviceMetricsOverride", { width: 1280, height: 800, deviceScaleFactor: dpr, mobile: false, screenWidth: sw, screenHeight: sh });
    // x2: its own calibration
    await metrics(2);
    await expect.poll(() => screenKey(page)).toBe("1280x800@2");
    await expect.poll(() => zoom(page), { timeout: 5000 }).toBe(2.9);
    await expect(indicator(page)).toHaveText("Actual size");
    // x1.5: none, so the estimate, and the indicator says it is one
    await metrics(1.5);
    await expect.poll(async () => (await state(page)).scale.key, { timeout: 5000 }).toBe("1280x800@1.5");
    const est = (await state(page)).scale;
    expect(est.calibrated).toBe(false);
    await expect.poll(() => zoom(page), { timeout: 5000 }).toBe(est.pxPerMm);
    await expect(indicator(page)).toHaveText("Actual size (estimated — calibrate)");
    // back at x1, then a bigger screen at the same x1 (an X11 monitor: no DPR event): a 4K's estimate
    await metrics(1);
    await expect.poll(() => zoom(page), { timeout: 5000 }).toBe(4.37);
    await metrics(1, 3840, 2160);
    await expect.poll(async () => (await state(page)).scale.key, { timeout: 5000 }).toBe("3840x2160@1");
    await expect.poll(() => zoom(page), { timeout: 5000 }).toBeCloseTo(150 / 25.4, 9);
    await expect(indicator(page)).toHaveText("Actual size (estimated — calibrate)");
    // not at Actual size: a change of screen leaves the zoom alone
    await page.keyboard.press("Shift+Digit1");
    const fitted = await zoom(page);
    await metrics(1);
    await expect.poll(async () => (await state(page)).scale.key, { timeout: 5000 }).toBe("1280x800@1");
    expect(await zoom(page)).toBe(fitted);
    await cdp.send("Emulation.clearDeviceMetricsOverride");
  });
});

test.describe("the zoom indicator", () => {
  test("g · its longest words (Actual size, estimated) meet no other chrome: 1184, 1280, 768 wide; on a phone it shows only at Actual size, under the document pill", async ({ page }) => {
    const ids = ["zoom-indicator", "toolbar", "corner", "doc-pill", "actions-pill"];
    const boxes = () => page.evaluate((list) => list.flatMap((id) => {
      const e = document.querySelector(`[data-testid="${id}"]`);
      const r = e?.getBoundingClientRect();
      return r && r.width > 0 && r.height > 0 ? [{ id, x: r.x, y: r.y, w: r.width, h: r.height }] : [];
    }), ids);
    await openStudio(page);
    await coreReady(page);
    for (const [w, h] of [[1184, 800], [1280, 800], [768, 1024], [390, 844]] as const) {
      await page.setViewportSize({ width: w, height: h });
      await page.keyboard.press("Shift+Digit1");
      if (w === 390) await expect(indicator(page), "a phone, not at Actual size: hidden").toBeHidden();
      await page.keyboard.press("Shift+Digit0");
      await expect(indicator(page)).toHaveText("Actual size (estimated — calibrate)");
      const all = await boxes();
      const zi = all.find((b) => b.id === "zoom-indicator")!;
      expect(zi, `${w}: shown`).toBeTruthy();
      for (const b of all) {
        if (b === zi) continue;
        const meet = zi.x < b.x + b.w - 0.5 && b.x < zi.x + zi.w - 0.5 && zi.y < b.y + b.h - 0.5 && b.y < zi.y + zi.h - 0.5;
        expect(meet, `${w}: the indicator meets ${b.id}`).toBe(false);
      }
      expect(zi.x, `${w}: on screen`).toBeGreaterThanOrEqual(0);
      expect(zi.x + zi.w, `${w}: on screen`).toBeLessThanOrEqual(w);
      // nothing in it overflows its box
      const over = await indicator(page).evaluate((root) => [root, ...root.querySelectorAll("*")].filter((e) => (e as HTMLElement).scrollWidth > (e as HTMLElement).clientWidth + 1).length);
      expect(over, `${w}: overflow`).toBe(0);
      if (w === 390) {
        const pill = all.find((b) => b.id === "doc-pill")!;
        expect(zi.y, "under the document pill").toBeGreaterThanOrEqual(pill.y + pill.h);
      }
      await shot(page, `d-indicator-${w}`);
    }
  });
});
