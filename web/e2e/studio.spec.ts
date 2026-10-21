// The online Studio's flows (docs/design/online_studio_v1.md, "The flows"),
// on the static build. Each check measures: the probe's numbers in mm and
// the drawn elements' boxes in pixels.
import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { clickAt, CORE, coreReady, dragWorld, fitRect, idle, loadExample, openPresets, openStudio, overlaps, panelTab, planOutline, profileRect, state, toClient } from "./helpers";

test.describe(`online Studio (${CORE} core)`, () => {
  test("1 · the core reaches ready: ?'s status line says so (no chip in the chrome since the Figma layout)", async ({ page }) => {
    await openStudio(page);
    // usable before: the sketch draws and picks while the core loads
    await expect(page.locator("[data-shape]").first()).toBeVisible();
    await coreReady(page);
    await page.getByTestId("help").click();
    await expect(page.getByTestId("core-status")).toHaveAttribute("data-state", "ready");
    await expect(page.getByTestId("core-status")).toHaveText(/^Ready in \d+\.\d s$/);
  });

  // 2026-10-20 evening (barrier 9): the profile is the input; the core places
  // the marker (fit_rect) and no rectangle is added to the sketch
  test("2 · plate: click the face, A: the core places the marker off both holes (fit_rect, drawn dashed), a black marker", async ({ page }) => {
    await openStudio(page);
    await coreReady(page);
    await loadExample(page, "plate");
    await clickAt(page, 60, 40);
    await expect.poll(async () => (await state(page)).sel?.kind).toBe("profile");
    await page.keyboard.press("a");
    await idle(page);
    const r = await fitRect(page);
    const s = await state(page);
    expect(s.doc.shapes).toHaveLength(3);
    expect(s.feature.profile).toEqual({ outer: "plate", holes: ["plate-h1", "plate-h2"] });
    for (const hole of s.doc.shapes.filter((x: any) => x.kind === "circle")) {
      expect(overlaps(hole, r), `fit_rect ${JSON.stringify(r)} vs hole ${hole.id}`).toBe(false);
    }
    // drawn: the fit box on screen is its size in mm times the zoom
    // WHY getBoundingClientRect, not boundingBox(): Playwright's box of a stroked
    // dashed path takes in Chrome's stroke estimate (miter limit 4: 2 px a side)
    const el = page.locator(`[data-fit-rect="${s.feature.id}"]`);
    const box = await el.evaluate((e) => { const b = e.getBoundingClientRect(); return { x: b.left, y: b.top, width: b.width, height: b.height }; });
    const z = s.camera.zoom;
    expect(Math.abs(box.width - r.w * z)).toBeLessThan(3);
    expect(Math.abs(box.height - r.h * z)).toBeLessThan(3);
    // and it keeps off the holes on screen too: no hole's centre is inside its box
    for (const hole of s.doc.shapes.filter((x: any) => x.kind === "circle")) {
      const [hx, hy] = await toClient(page, hole.cx, hole.cy);
      expect(hx > box.x && hx < box.x + box.width && hy > box.y && hy < box.y + box.height).toBe(false);
    }
    // the marker: black paths, filled dark, inside the fit box
    const black = page.locator("[data-marker-black]");
    expect((await black.getAttribute("d"))!.length).toBeGreaterThan(20);
    const fill = await black.evaluate((e) => getComputedStyle(e).fill);
    const [R, G, B] = fill.match(/\d+/g)!.map(Number);
    expect(R + G + B).toBeLessThan(150);
    const bb = (await black.boundingBox())!;
    expect(bb.width).toBeGreaterThan(20);
    expect(bb.x).toBeGreaterThanOrEqual(box.x - 1);
    expect(bb.x + bb.width).toBeLessThanOrEqual(box.x + box.width + 1);
  });

  test("3 · grid: the ids range shows; a big typed size is drawn past the fit box and flagged red", async ({ page }) => {
    await openStudio(page);
    await coreReady(page);
    await loadExample(page, "plate");
    await clickAt(page, 60, 40);
    await page.keyboard.press("a");
    await idle(page);
    await panelTab(page, "marker");
    await page.locator('[data-path="marker.type"] [data-value="grid"]').click();
    await idle(page);
    await expect(page.getByTestId("id-range")).toHaveText(/^#\d+–\d+$/);
    const input = page.locator('input[data-path="marker.marker_mm"]');
    await input.fill("80");
    await input.press("Enter");
    await idle(page);
    const issue = page.locator('[data-issues-for="marker.marker_mm"] [data-level="error"]');
    await expect(issue.first()).toBeVisible();
    await expect(page.locator('[data-row="marker.marker_mm"]')).toHaveClass(/has-error/);
    const s = await state(page);
    expect(s.feature.marker).toMatchObject({ auto: false, marker_mm: 80 });
    expect(s.plan.overflow_mm).toBeGreaterThan(0);
    const rect = (await page.locator(`[data-fit-rect="${s.feature.id}"]`).boundingBox())!;
    const outline = (await page.locator("[data-marker-outline]").boundingBox())!;
    expect(outline.width).toBeGreaterThan(rect.width + 5);
    expect(outline.height).toBeGreaterThan(rect.height + 5);
    const stroke = await page.locator("[data-marker-outline]").evaluate((e) => getComputedStyle(e).stroke);
    const [R, G, B] = stroke.match(/\d+/g)!.map(Number);
    expect(R).toBeGreaterThan(150);
    expect(G + B).toBeLessThan(R);
  });

  // the custom placement (a rectangle profile) is what a drag moves now
  test("4 · drag the rectangle profile 20 mm: the marker's centre moves 20 mm", async ({ page }) => {
    await openStudio(page);
    await coreReady(page);
    await loadExample(page, "custom-placement");
    await idle(page);
    await page.locator('[data-marker="custom-f1"]').click();
    await idle(page);
    const r = await profileRect(page);
    const before = await planOutline(page);
    const px0 = (await page.locator("[data-marker-outline]").boundingBox())!;
    // grab the rectangle's left edge, away from its handles (a handle resizes)
    const from: [number, number] = [r.cx! - r.w! / 2, r.cy! + r.h! * 0.3];
    await dragWorld(page, from, [from[0] + 20, from[1]]);
    await idle(page);
    const after = await planOutline(page);
    expect(Math.abs(after.cx - before.cx - 20)).toBeLessThanOrEqual(0.5);
    expect(Math.abs(after.cy - before.cy)).toBeLessThanOrEqual(0.5);
    const z = (await state(page)).camera.zoom;
    const px1 = (await page.locator("[data-marker-outline]").boundingBox())!;
    expect(Math.abs((px1.x + px1.width / 2) - (px0.x + px0.width / 2) - 20 * z)).toBeLessThanOrEqual(0.5 * z + 1);
  });

  test("5 · the presets modal with no marker open: pick the A4 inkjet preset, a new marker starts with it", async ({ page }) => {
    await openStudio(page);
    await coreReady(page);
    const modal = await openPresets(page);
    await expect(page.getByTestId("presets-target")).toHaveAttribute("data-target", "new");
    await modal.locator('[data-coll="builtin"]').click();
    await modal.locator('[data-chip="Inkjet"]').click();
    await modal.locator('[data-chip="A4"]').click();
    const card = modal.locator(".card[data-card]").first();
    await expect(card).toBeVisible();
    const name = (await card.locator(".name").textContent())!;
    expect(name).toMatch(/A4/);
    await card.click();
    await page.getByTestId("presets-select").click();
    await expect(modal).toHaveCount(0);
    expect((await state(page)).doc.default_preset).toMatchObject({ method: "inkjet", page: "A4" });
    // the next marker is made by it, and its Preset row says so
    await clickAt(page, 60, 40);
    await page.keyboard.press("a");
    await idle(page);
    await expect(page.getByTestId("panel-preset")).toContainText(name);
    const s = await state(page);
    expect(s.feature.preset).toMatchObject({ method: "inkjet", page: "A4" });
    expect(s.plan.extrude.method).toBe("inkjet");
  });

  test("6 · Export SVG downloads a file whose root is sized in mm", async ({ page }) => {
    await openStudio(page);
    await coreReady(page);
    await loadExample(page, "plate");
    await clickAt(page, 60, 40);
    await page.keyboard.press("a");
    await idle(page);
    await page.getByTestId("menu-export").click();
    const [dl] = await Promise.all([page.waitForEvent("download"), page.getByTestId("cmd-svg").click()]);
    expect(dl.suggestedFilename()).toMatch(/\.svg$/);
    const text = readFileSync((await dl.path())!, "utf8");
    const root = /<svg\b[^>]*>/.exec(text)![0];
    expect(root).toMatch(/\swidth="[\d.]+mm"/);
    expect(root).toMatch(/\sheight="[\d.]+mm"/);
  });

  test("7 · 390 px wide: no horizontal scroll, the panel docks to the bottom", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openStudio(page);
    await coreReady(page);
    const noScroll = () => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth && document.body.scrollWidth <= window.innerWidth);
    expect(await noScroll()).toBe(true);
    await clickAt(page, 60, 40);
    await page.keyboard.press("a");
    await idle(page);
    const panel = (await page.getByTestId("extrude-panel").boundingBox())!;
    expect(panel.x).toBeLessThanOrEqual(1);
    expect(panel.width).toBeGreaterThanOrEqual(388);
    expect(Math.abs(panel.y + panel.height - 844)).toBeLessThanOrEqual(1);
    expect(await noScroll()).toBe(true);
  });

  test("8 · a circle inside a drawn rectangle: inside the ring, A: the marker's box keeps off the circle", async ({ page }) => {
    await openStudio(page);
    await coreReady(page);
    await page.getByTestId("menu-file").click();
    await page.getByTestId("cmd-new").click();
    await page.keyboard.press("r");
    await dragWorld(page, [-40, -30], [40, 30]);
    await page.keyboard.press("c");
    await dragWorld(page, [0, 0], [15, 0]);
    let s = await state(page);
    expect(s.doc.shapes.map((x: any) => x.kind)).toEqual(["rect", "circle"]);
    const circle = s.doc.shapes[1];
    expect(circle.r).toBe(15);
    await page.keyboard.press("v");
    await clickAt(page, -35, 0);
    await expect.poll(async () => (await state(page)).sel?.kind).toBe("profile");
    s = await state(page);
    expect(s.sel.ref).toEqual({ outer: s.doc.shapes[0].id, holes: [circle.id] });
    await page.keyboard.press("a");
    await idle(page);
    const r = await fitRect(page);
    s = await state(page);
    expect(s.doc.shapes).toHaveLength(2);
    expect(s.feature.profile).toEqual({ outer: s.doc.shapes[0].id, holes: [circle.id] });
    expect(overlaps(circle, r), `fit_rect ${JSON.stringify(r)} vs circle`).toBe(false);
    // inside the drawn rectangle
    expect(r.cx - r.w / 2).toBeGreaterThanOrEqual(-40 - 1e-6);
    expect(r.cx + r.w / 2).toBeLessThanOrEqual(40 + 1e-6);
    // drawn where the core says
    const box = (await page.locator(`[data-fit-rect="${s.feature.id}"]`).boundingBox())!;
    const [x0, y1] = await toClient(page, r.cx - r.w / 2, r.cy - r.h / 2);
    expect(Math.abs(box.x - x0)).toBeLessThan(3);
    expect(Math.abs(box.y + box.height - y1)).toBeLessThan(3);
  });
});
