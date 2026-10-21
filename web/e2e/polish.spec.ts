// The panel polish (Zach's feedback, 2026-10-20 night, carried over from the
// Fusion add-in): the label off by default; the ↺ INSIDE a set field (and an
// emptied field back to driven); Fusion-style groups with Suggest first in
// Size and a divider before Corner mark; small icons beside the row names;
// the turn arc of a rectangle profile as a rotate manipulator (15° snap, a
// typed angle, one undo step). Every check measures the probe's numbers or
// the drawn boxes (getBoundingClientRect), never DOM presence alone.
// Screenshots (1280 × 800) go to POLISH_SHOTS (default test-results/polish).
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { clickAt, coreReady, fitRect, idle, loadExample, openStudio, panelTab, state, toClient } from "./helpers";

const SHOTS = process.env.POLISH_SHOTS ?? "test-results/polish";

type Box = { left: number; top: number; right: number; bottom: number };
const within = (a: Box, b: Box, eps = 0.5) => a.left >= b.left - eps && a.right <= b.right + eps && a.top >= b.top - eps && a.bottom <= b.bottom + eps;
const rectOf = (page: Page, sel: string) => page.locator(sel).first().evaluate((e) => {
  const r = e.getBoundingClientRect();
  return { left: r.left, top: r.top, right: r.right, bottom: r.bottom };
});
/** An angle's distance from another, on the circle (degrees). */
const angDist = (a: number, b: number) => Math.abs((((a - b) % 360) + 540) % 360 - 180);

/** Examples › Plate, click the face, A: a new feature, its panel open. */
async function platePanel(page: Page): Promise<string> {
  await openStudio(page);
  await coreReady(page);
  await loadExample(page, "plate");
  await clickAt(page, 60, 40);
  await expect.poll(async () => (await state(page)).sel?.kind).toBe("profile");
  await page.keyboard.press("a");
  await expect(page.getByTestId("extrude-panel")).toBeVisible();
  await idle(page);
  return (await state(page)).panel.featureId as string;
}

/** Examples › Custom placement (a rectangle profile), its marker clicked: the panel open on it. */
async function customPanel(page: Page): Promise<string> {
  await openStudio(page);
  await coreReady(page);
  await loadExample(page, "custom-placement");
  await idle(page);
  const b = (await page.locator('[data-marker="custom-f1"]').boundingBox())!;
  await page.mouse.click(b.x + b.width / 2, b.y + b.height / 2);
  await expect(page.getByTestId("extrude-panel")).toBeVisible();
  await idle(page);
  return "custom-f1";
}

/** The presets dialog from the Preset row (on Marker, the skeleton): the first built-in preset of a method, Select. */
async function usePreset(page: Page, method: "inkjet" | "print3d"): Promise<void> {
  await panelTab(page, "marker");
  await page.getByTestId("panel-preset").click();
  const modal = page.getByTestId("presets-modal");
  await modal.locator('[data-coll="builtin"]').click();
  await modal.locator(`[data-group="${method}"] .card[data-card]`).first().click();
  await page.getByTestId("presets-select").click();
  await expect(modal).toHaveCount(0);
  await idle(page);
}

/** Every ↺ in the panel lies inside its own control's box: a number field's
 *  box, a segmented row's / a switch's box, or a select's trigger. */
async function resetsInside(page: Page): Promise<number> {
  const out = await page.locator('[data-testid="extrude-panel"] [data-reset]').evaluateAll((els) => els.map((e) => {
    const box = e.closest(".kit-num") ?? e.parentElement?.querySelector(".kit-select-trigger") ?? e.closest(".drv-box");
    const a = e.getBoundingClientRect(), b = box?.getBoundingClientRect();
    return { path: e.getAttribute("data-reset"), a: { left: a.left, top: a.top, right: a.right, bottom: a.bottom },
      b: b ? { left: b.left, top: b.top, right: b.right, bottom: b.bottom } : null, w: a.width };
  }));
  for (const r of out) {
    expect(r.b, `${r.path}: a box round its ↺`).not.toBeNull();
    expect(r.w, `${r.path}: the ↺ is drawn`).toBeGreaterThan(4);
    expect(within(r.a, r.b!), `${r.path}: ↺ ${JSON.stringify(r.a)} inside ${JSON.stringify(r.b)}`).toBe(true);
    // at the right end: its centre right of the box's middle
    expect((r.a.left + r.a.right) / 2, `${r.path}: ↺ at the right`).toBeGreaterThan((r.b!.left + r.b!.right) / 2);
  }
  return out.length;
}

test.describe("panel polish (real core)", () => {
  test("a · a new feature has its label off: the On switch driven and off, no label planned or drawn", async ({ page }) => {
    await platePanel(page);
    const s = await state(page);
    expect(s.feature.label.on).toBe(false);
    expect(s.feature.set).not.toContain("label.on");
    expect(s.plan.label?.text ?? "").toBe("");
    await expect(page.getByTestId("label-text")).toHaveCount(0);
    await panelTab(page, "label");
    await expect(page.locator('[data-drv="label.on"]')).toHaveAttribute("data-driven", "1");
    await expect(page.locator('[data-row="label.text"]')).toHaveCount(0);
    // turned on, it plans a label (the sticker sheet's example turns it on itself)
    await page.locator('[data-path="label.on"]').click();
    await idle(page);
    expect((await state(page)).feature.label.on).toBe(true);
    await expect(page.getByTestId("label-text")).toHaveCount(1);
  });

  test("b · a typed size shows ↺ INSIDE the field at its right, before the unit; ↺ and an emptied field both make it driven; no ↺ outside a field", async ({ page }) => {
    await platePanel(page);
    await panelTab(page, "marker");
    const field = page.locator('[data-drv="marker.marker_mm"]');
    const input = page.locator('input[data-path="marker.marker_mm"]');
    await expect(field).toHaveAttribute("data-driven", "1");
    await expect(page.locator('[data-reset="marker.marker_mm"]')).toHaveCount(0);

    await input.fill("20");
    await input.press("Enter");
    await idle(page);
    await expect(field).toHaveAttribute("data-driven", "0");
    const reset = page.locator('[data-reset="marker.marker_mm"]');
    await expect(reset).toBeVisible();
    const rb = await rectOf(page, '[data-reset="marker.marker_mm"]');
    const fb = await rectOf(page, '[data-drv="marker.marker_mm"]');
    const ub = await rectOf(page, '[data-drv="marker.marker_mm"] .unit');
    expect(within(rb, fb), `↺ ${JSON.stringify(rb)} inside the field ${JSON.stringify(fb)}`).toBe(true);
    expect((rb.left + rb.right) / 2).toBeGreaterThan((fb.left + fb.right) / 2);
    expect(rb.right, "before the unit").toBeLessThanOrEqual(ub.left + 0.5);
    // the input itself ends where the ↺ begins: typed text never runs under it
    const ib = await rectOf(page, 'input[data-path="marker.marker_mm"]');
    expect(ib.right).toBeLessThanOrEqual(rb.left + 0.5);
    await page.screenshot({ path: path.join(SHOTS, "b-reset-inside.png"), clip: { x: fb.left - 130, y: fb.top - 40, width: 340, height: 90 } });

    await reset.click();
    await idle(page);
    await expect(field).toHaveAttribute("data-driven", "1");
    expect((await state(page)).feature.marker.auto).toBe(true);
    await expect(reset).toHaveCount(0);

    // typed again, then emptied + Enter: driven again
    await input.fill("18");
    await input.press("Enter");
    await idle(page);
    await expect(field).toHaveAttribute("data-driven", "0");
    await input.click();
    await input.press("Control+a");
    await input.press("Backspace");
    await input.press("Enter");
    await idle(page);
    await expect(field).toHaveAttribute("data-driven", "1");
    expect((await state(page)).feature.marker.auto).toBe(true);
    // and emptied + blur
    await input.fill("18");
    await input.press("Enter");
    await idle(page);
    await expect(field).toHaveAttribute("data-driven", "0");
    await input.click();
    await input.press("Control+a");
    await input.press("Backspace");
    await page.locator('[data-tab-body="marker"] [data-group-title="Marker"]').click();
    await idle(page);
    await expect(field).toHaveAttribute("data-driven", "1");

    // a choice of every kind set, on every tab: each ↺ inside its control
    const seg = (p: string, v: string) => page.locator(`[data-path="${p}"] [data-value="${v}"]`);
    await seg("marker.turn", "90").click();
    await seg("marker.type", "grid").click();
    await idle(page);
    await page.locator('[data-path="marker.dictionary"]').click();
    await page.locator('.kit-select-item').nth(3).click();
    await idle(page);
    for (const p of ["marker.turn", "marker.type", "marker.dictionary"]) await expect(page.locator(`[data-reset="${p}"]`), p).toBeVisible();
    await input.fill("12");
    await input.press("Enter");
    await idle(page);
    expect(await resetsInside(page)).toBeGreaterThanOrEqual(4);
    await page.screenshot({ path: path.join(SHOTS, "b-marker-set.png") });
    await panelTab(page, "make");
    await seg("trim", "marker").click();
    await idle(page);
    expect(await resetsInside(page)).toBeGreaterThanOrEqual(1);
    await panelTab(page, "label");
    await page.locator('[data-path="label.on"]').click();
    await idle(page);
    await seg("label.side", "above").click();
    await idle(page);
    expect(await resetsInside(page)).toBeGreaterThanOrEqual(2);
  });

  test("c · Marker: groups Where, How, Marker, Size, Orientation, Details top to bottom, Suggest last in Size (the skeleton); Label: a divider before Corner mark", async ({ page }) => {
    await platePanel(page);
    await panelTab(page, "marker");
    const body = '[data-tab-body="marker"]';
    const titles = await page.locator(`${body} [data-group-title]`).evaluateAll((els) =>
      els.map((e) => ({ t: e.getAttribute("data-group-title"), y: e.getBoundingClientRect().top })));
    expect(titles.map((x) => x.t)).toEqual(["Where", "How", "Marker", "Size", "Orientation", "Details"]);
    for (let i = 1; i < titles.length; i++) expect(titles[i].y).toBeGreaterThan(titles[i - 1].y);
    const rows = await page.locator(`${body} [data-row]`).evaluateAll((els) =>
      els.map((e) => ({ r: e.getAttribute("data-row"), y: e.getBoundingClientRect().top })));
    const inGroup = (g: number) => rows.filter((x) => x.y > titles[g].y && (g + 1 >= titles.length || x.y < titles[g + 1].y)).sort((a, b) => a.y - b.y).map((x) => x.r);
    expect(inGroup(0)).toEqual(["profile", "holes"]);
    expect(inGroup(1)).toEqual(["preset"]);
    expect(inGroup(2)).toEqual(["marker.type", "marker.dictionary", "marker.first_id"]);
    expect(inGroup(3)).toEqual(["marker.marker_mm", "marker.suggest"]);
    // a face profile: Turn only (Rotation is a rectangle profile's, the skeleton)
    expect(inGroup(4)).toEqual(["marker.turn"]);
    expect(inGroup(5)).toEqual(["marker.quiet_modules", "feature.key"]);
    // each group's rule is drawn: a 1 px line after its title
    const rule = await page.locator(`${body} [data-group-title="Size"]`).evaluate((e) => getComputedStyle(e, "::after").borderTopWidth);
    expect(rule).toBe("1px");
    await page.screenshot({ path: path.join(SHOTS, "c-marker-groups.png") });

    await panelTab(page, "label");
    const lbody = '[data-tab-body="label"]';
    const divider = async () => {
      const ys = await page.locator(`${lbody} [data-row]`).evaluateAll((els) => els.map((e) => ({ r: e.getAttribute("data-row"), top: e.getBoundingClientRect().top, bottom: e.getBoundingClientRect().bottom })));
      const corner = ys.find((x) => x.r === "marker.corner_mark")!;
      const labelRows = ys.filter((x) => x.r !== "marker.corner_mark");
      const g = await rectOf(page, `${lbody} [data-group-title="Corner mark"]`);
      for (const x of labelRows) expect(x.bottom, `${x.r} above the divider`).toBeLessThanOrEqual(g.top + 0.5);
      expect(corner.top).toBeGreaterThanOrEqual(g.bottom - 0.5);
      expect(await page.locator(`${lbody} [data-group-title="Corner mark"]`).evaluate((e) => getComputedStyle(e, "::after").borderTopWidth)).toBe("1px");
      return labelRows.length;
    };
    expect(await divider()).toBe(1);   // the label off: On alone above it
    await page.locator('[data-path="label.on"]').click();
    await idle(page);
    expect(await divider()).toBeGreaterThanOrEqual(6);
    expect(await page.locator(`${lbody} [data-group-title]`).evaluateAll((els) => els.map((e) => e.getAttribute("data-group-title")))).toEqual(["Label", "Corner mark"]);
    await panelTab(page, "make");
    expect(await page.locator('[data-tab-body="make"] [data-group-title]').evaluateAll((els) => els.map((e) => e.getAttribute("data-group-title"))))
      .toEqual(["Size & cut", "Heights", "Outward side"]);
  });

  test("d · a rectangle profile rotates on the sketch: drag the arc ~40° → 45 (15° snap), type 30 → 30, the marker turns with it, Ctrl+Z restores it in one step", async ({ page }) => {
    await customPanel(page);
    const rect0 = (await state(page)).doc.shapes.find((x: any) => x.id === "custom");
    expect(rect0.angle_deg).toBe(0);
    expect(angDist((await fitRect(page)).angle_deg, 0)).toBeLessThan(1e-6);
    const arc = page.getByTestId("turn-arc");
    await expect(arc).toHaveAttribute("data-rotate", "1");

    // drag the knob ~40° counter-clockwise about the rectangle's centre
    const kb = (await arc.locator(".turn-knob").boundingBox())!;
    const k: [number, number] = [kb.x + kb.width / 2, kb.y + kb.height / 2];
    const [cx, cy] = await toClient(page, rect0.cx, rect0.cy);
    const R = Math.hypot(k[0] - cx, k[1] - cy);
    const t0 = Math.atan2(-(k[1] - cy), k[0] - cx);
    const at = (deg: number): [number, number] => [cx + R * Math.cos(t0 + (deg * Math.PI) / 180), cy - R * Math.sin(t0 + (deg * Math.PI) / 180)];
    await page.mouse.move(...k);
    await page.mouse.down();
    for (let i = 1; i <= 16; i++) await page.mouse.move(...at((40 * i) / 16));
    await idle(page);
    // mid-drag: the angle box shows the angle
    const box = page.getByTestId("rotate-angle");
    await expect(box).toBeVisible();
    await expect(box).toHaveValue("45");
    await page.screenshot({ path: path.join(SHOTS, "d-rotate-mid-drag.png") });
    await page.mouse.up();
    await idle(page);
    let s = await state(page);
    expect(s.doc.shapes.find((x: any) => x.id === "custom").angle_deg).toBe(45);
    expect(s.feature.marker.turn, "a drag is not a 90° turn").toBe(0);
    expect(angDist((await fitRect(page)).angle_deg, 45)).toBeLessThan(1e-6);

    // the box stays: type an exact angle
    await expect(box).toBeFocused();
    await page.keyboard.type("30");
    await page.keyboard.press("Enter");
    await idle(page);
    await expect(box).toHaveCount(0);
    s = await state(page);
    expect(s.doc.shapes.find((x: any) => x.id === "custom").angle_deg).toBe(30);
    const fr = await fitRect(page);
    expect(angDist(fr.angle_deg, 30), `fit_rect.angle_deg ${fr.angle_deg}`).toBeLessThan(1e-6);
    // the marker's outline turned with it: its edges run at 30°
    const outer: number[][] = s.plan.outer;
    const edge = Math.atan2(outer[1][1] - outer[0][1], outer[1][0] - outer[0][0]) * 180 / Math.PI;
    expect(Math.min(...[0, 90, 180, 270].map((q) => angDist(edge, 30 + q)))).toBeLessThan(0.01);
    // the panel's Rotation row reads it
    await panelTab(page, "marker");
    await expect(page.locator('input[data-path="profile.angle_deg"]')).toHaveValue("30");
    await page.screenshot({ path: path.join(SHOTS, "d-rotated-30.png") });

    // one undo step back to 0
    await page.locator('[data-tab-body="marker"] [data-group-title="Orientation"]').click();
    await page.keyboard.press("Control+z");
    await idle(page);
    s = await state(page);
    expect(s.doc.shapes.find((x: any) => x.id === "custom").angle_deg).toBe(0);
    expect(angDist((await fitRect(page)).angle_deg, 0)).toBeLessThan(1e-6);

    // the Rotation row types it too; Shift drags freely (no snap)
    const row = page.locator('input[data-path="profile.angle_deg"]');
    await row.fill("60");
    await row.press("Enter");
    await idle(page);
    expect((await state(page)).doc.shapes.find((x: any) => x.id === "custom").angle_deg).toBe(60);
    await page.keyboard.press("Control+z");
    await idle(page);
    const kb2 = (await arc.locator(".turn-knob").boundingBox())!;
    const k2: [number, number] = [kb2.x + kb2.width / 2, kb2.y + kb2.height / 2];
    const t2 = Math.atan2(-(k2[1] - cy), k2[0] - cx);
    await page.keyboard.down("Shift");
    await page.mouse.move(...k2);
    await page.mouse.down();
    for (let i = 1; i <= 10; i++) await page.mouse.move(cx + R * Math.cos(t2 + (i * 2 * Math.PI) / 180), cy - R * Math.sin(t2 + (i * 2 * Math.PI) / 180));
    await page.mouse.up();
    await page.keyboard.up("Shift");
    await page.keyboard.press("Escape");
    await idle(page);
    const free = (await state(page)).doc.shapes.find((x: any) => x.id === "custom").angle_deg;
    expect(angDist(free, 20)).toBeLessThan(1.5);
    expect(free % 15, `free: ${free}`).not.toBe(0);
  });

  test("d2 · a click on the arc still turns the marker 90°; a face profile has no Rotation row (the core places it: Turn only)", async ({ page }) => {
    await customPanel(page);
    const kb = (await page.getByTestId("turn-arc").locator(".turn-knob").boundingBox())!;
    await page.mouse.click(kb.x + kb.width / 2, kb.y + kb.height / 2);
    await idle(page);
    const s = await state(page);
    expect(s.feature.marker.turn).toBe(90);
    expect(s.doc.shapes.find((x: any) => x.id === "custom").angle_deg).toBe(0);
    await expect(page.getByTestId("rotate-angle")).toHaveCount(0);

    await platePanel(page);
    await panelTab(page, "marker");
    await expect(page.locator('[data-tab-body="marker"] [data-row="marker.turn"]')).toBeVisible();
    await expect(page.locator('[data-row="profile.angle_deg"]')).toHaveCount(0);
    await expect(page.locator('input[data-path="profile.angle_deg"]')).toHaveCount(0);
  });

  test("e · icons beside the row names: small, one per listed row", async ({ page }) => {
    await platePanel(page);
    const icon = (row: string) => page.locator(`[data-row="${row}"] > .kit-row > .row-label > svg.kit-glyph`);
    const expectIcon = async (row: string, name: string) => {
      await expect(icon(row), row).toHaveCount(1);
      await expect(icon(row), row).toHaveAttribute("data-icon", name);
      const b = (await icon(row).boundingBox())!;
      expect(b.width, `${row} icon is small`).toBeLessThanOrEqual(14);
      expect(b.width).toBeGreaterThanOrEqual(10);
    };
    await panelTab(page, "marker");
    for (const [r, n] of [["profile", "row-square-dashed-mouse-pointer"], ["marker.type", "row-grid-2x2"], ["marker.dictionary", "row-book-open"], ["marker.first_id", "row-hash"],
      ["marker.marker_mm", "row-ruler"], ["marker.turn", "row-rotate-cw"], ["marker.quiet_modules", "row-square-square"], ["feature.key", "row-key-round"]]) await expectIcon(r, n);
    await panelTab(page, "make");
    for (const [r, n] of [["trim", "row-scissors"], ["extrude.paper_mm", "row-arrow-up-from-line"], ["marker.flip", "row-flip-vertical"]]) await expectIcon(r, n);
    await panelTab(page, "label");
    for (const [r, n] of [["label.on", "row-type"], ["marker.corner_mark", "row-triangle-right"]]) await expectIcon(r, n);
  });

  test("shots · each tab, inkjet and 3D print, at 1280 × 800", async ({ page }) => {
    await platePanel(page);
    for (const method of ["inkjet", "print3d"] as const) {
      if (method === "print3d") await usePreset(page, "print3d");
      for (const t of ["marker", "label", "make"] as const) {
        await panelTab(page, t);
        if (t === "label" && !(await state(page)).feature.label.on) {
          await page.locator('[data-path="label.on"]').click();
          await idle(page);
        }
        await page.screenshot({ path: path.join(SHOTS, `tab-${method}-${t}.png`) });
      }
    }
  });
});
