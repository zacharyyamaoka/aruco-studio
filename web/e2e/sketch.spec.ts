// The sketch's own tools (web/src/sketch/): Dimension (D, Fusion's Sketch
// Dimension, driving), the value boxes while drawing, the right-button
// selection box (window / crossing), moving and nudging many shapes, Ctrl+C /
// Ctrl+V, and A on several rectangles ("an ArUco marker maker on a canvas",
// Zach 2026-10-20 night). Sizes are measured on what is drawn
// (getBoundingClientRect over the probe's toClient scale), never on DOM
// presence alone. SKETCH_MEDIA=<dir> also writes the screenshots and the
// marker-maker video there.
import { copyFileSync, mkdirSync } from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { coreReady, dragWorld, idle, openStudio, state, toClient, type Shape, panelTab, openMenu } from "./helpers";

const MEDIA = process.env.SKETCH_MEDIA ?? "";

async function blank(page: Page): Promise<void> {
  await openStudio(page);
  await coreReady(page);
  await openMenu(page, "file");
  await page.getByTestId("cmd-new").click();
}

async function shot(page: Page, name: string): Promise<void> {
  if (!MEDIA) return;
  mkdirSync(MEDIA, { recursive: true });
  await page.screenshot({ path: path.join(MEDIA, `${name}.png`) });
}

/** px per mm on screen, from the probe's mapping. */
async function scale(page: Page): Promise<number> {
  const [a] = await toClient(page, 0, 0), [b] = await toClient(page, 1, 0);
  return b - a;
}

/** A shape's drawn size (mm): its path's getBoundingClientRect (the geometry;
 *  Playwright's boundingBox() takes in the stroke) over the scale. */
async function drawnSize(page: Page, id: string): Promise<{ w: number; h: number; x0: number; y1: number }> {
  const box = await page.locator(`[data-shape="${id}"]`).evaluate((el) => {
    const r = el.getBoundingClientRect();
    return { x: r.x, y: r.y, width: r.width, height: r.height };
  });
  const k = await scale(page);
  const [ox, oy] = await toClient(page, 0, 0);
  return { w: box.width / k, h: box.height / k, x0: (box.x - ox) / k, y1: (oy - box.y) / k };
}

/** Draw a rectangle by its corners (mm); returns its id. */
async function rect(page: Page, a: [number, number], b: [number, number]): Promise<string> {
  await page.keyboard.press("r");
  await dragWorld(page, a, b);
  const s = await state(page);
  expect(s.sel?.kind).toBe("shape");
  return s.sel.id;
}

/** A right-button drag (mm to mm), in steps. */
async function rightDrag(page: Page, from: [number, number], to: [number, number], hold?: (page: Page) => Promise<void>): Promise<void> {
  const [ax, ay] = await toClient(page, ...from);
  const [bx, by] = await toClient(page, ...to);
  await page.mouse.move(ax, ay);
  await page.mouse.down({ button: "right" });
  for (let i = 1; i <= 10; i++) await page.mouse.move(ax + ((bx - ax) * i) / 10, ay + ((by - ay) * i) / 10);
  if (hold) await hold(page);
  await page.mouse.up({ button: "right" });
}

const shapeOf = (s: any, id: string): Shape => s.doc.shapes.find((x: Shape) => x.id === id);

/** A feature's black ink's client box. */
async function ink(page: Page, fid: string) {
  return (await page.locator(`[data-marker="${fid}"] [data-marker-black]`).boundingBox())!;
}

test.describe("the sketch's tools", () => {
  test("a · D on a rectangle's edge: 40 sets W; then a handle does not change W while H still resizes", async ({ page }) => {
    await blank(page);
    const id = await rect(page, [-30, -15], [30, 15]);
    await page.keyboard.press("d");
    await expect(page.getByTestId("tool-dim")).toHaveAttribute("data-active", "1");
    // press on the bottom edge, drag down to place the dimension: its value box opens there
    await dragWorld(page, [0, -15], [0, -25]);
    const box = page.getByTestId("sdim-input");
    await expect(box).toHaveValue("60");
    await box.fill("40");
    await box.press("Enter");
    let s = await state(page);
    expect(s.doc.dims).toHaveLength(1);
    expect(s.doc.dims[0]).toMatchObject({ kind: "w", shape: id, value: 40 });
    expect(shapeOf(s, id)).toMatchObject({ w: 40, h: 30, cx: 0, cy: 0 });
    let d = await drawnSize(page, id);
    expect(Math.abs(d.w - 40), `drawn ${d.w} mm`).toBeLessThan(0.15);
    // drawn like the marker's dims: a value on a line, solid
    await expect(page.locator(`[data-sketch-dim="${s.doc.dims[0].id}"] [data-sdim-label]`)).toContainText("40");
    await shot(page, "dim-w-placed");

    // select it, then drag its handles
    await page.keyboard.press("Escape");
    await dragWorld(page, [-20, 0], [-20, 0], 1);
    await expect.poll(async () => (await state(page)).sel).toEqual({ kind: "shape", id });
    const handle = async (h: string) => {
      const b = (await page.locator(`[data-handle="${h}"]`).boundingBox())!;
      return [b.x + b.width / 2, b.y + b.height / 2];
    };
    const k = await scale(page);
    let [hx, hy] = await handle("e");
    await page.mouse.move(hx, hy);
    await page.mouse.down();
    for (let i = 1; i <= 8; i++) await page.mouse.move(hx + (12 * k * i) / 8, hy);
    await page.mouse.up();
    s = await state(page);
    expect(shapeOf(s, id)).toMatchObject({ w: 40, cx: 0 });
    [hx, hy] = await handle("ne");
    await page.mouse.move(hx, hy);
    await page.mouse.down();
    for (let i = 1; i <= 8; i++) await page.mouse.move(hx + (10 * k * i) / 8, hy - (10 * k * i) / 8);
    await page.mouse.up();
    s = await state(page);
    expect(shapeOf(s, id)).toMatchObject({ w: 40, h: 40 });
    d = await drawnSize(page, id);
    expect(Math.abs(d.w - 40)).toBeLessThan(0.15);
    expect(Math.abs(d.h - 40)).toBeLessThan(0.15);
    // a double-click on its value edits it in place; one undo step puts it back
    const dimId = s.doc.dims[0].id;
    await page.locator(`[data-sketch-dim="${dimId}"] [data-sdim-label]`).dblclick();
    await expect(page.getByTestId("sdim-input")).toHaveValue("40");
    await page.getByTestId("sdim-input").fill("44");
    await page.getByTestId("sdim-input").press("Enter");
    s = await state(page);
    expect(s.doc.dims[0].value).toBe(44);
    expect(shapeOf(s, id)).toMatchObject({ w: 44, h: 40 });
    await page.keyboard.press("Control+z");
    s = await state(page);
    expect(s.doc.dims[0].value).toBe(40);
    expect(shapeOf(s, id)).toMatchObject({ w: 40, h: 40 });
  });

  test("b · R, click, W 30 Tab H 20 Enter: a 30 × 20 rectangle with two driving dims; no HUD", async ({ page }) => {
    await blank(page);
    await page.keyboard.press("r");
    const [ax, ay] = await toClient(page, -20, -10);
    await page.mouse.click(ax, ay);
    const [bx, by] = await toClient(page, 10, 12);
    await page.mouse.move(bx, by, { steps: 6 });
    await expect(page.getByTestId("draw-w")).toBeVisible();
    await expect(page.getByTestId("draw-h")).toBeVisible();
    await expect(page.getByTestId("draw-w")).toBeFocused();
    await page.keyboard.type("30");
    await page.keyboard.press("Tab");
    await expect(page.getByTestId("draw-h")).toBeFocused();
    await page.keyboard.type("20");
    await shot(page, "draw-value-boxes");
    await page.keyboard.press("Enter");
    const s = await state(page);
    expect(s.doc.shapes).toHaveLength(1);
    const r = s.doc.shapes[0];
    // from the first corner, toward the pointer
    expect(r).toMatchObject({ kind: "rect", w: 30, h: 20, cx: -5, cy: 0 });
    expect(s.doc.dims.map((x: any) => [x.kind, x.value]).sort()).toEqual([["h", 20], ["w", 30]]);
    const d = await drawnSize(page, r.id);
    expect(Math.abs(d.w - 30)).toBeLessThan(0.15);
    expect(Math.abs(d.h - 20)).toBeLessThan(0.15);
    await expect(page.locator('[data-testid="shape-dims"], .dims-box')).toHaveCount(0);
    await expect(page.locator("[data-sketch-dim]")).toHaveCount(2);
  });

  test("c · a right-drag window takes the 2 shapes inside it; a crossing that touches the 3rd takes it too", async ({ page }) => {
    await blank(page);
    const a = await rect(page, [-40, -10], [-20, 10]);
    const b = await rect(page, [-10, -10], [10, 10]);
    const c = await rect(page, [20, -10], [40, 10]);
    await page.keyboard.press("Escape");
    await rightDrag(page, [-45, 15], [15, -15], async (p) => {
      await expect(p.getByTestId("select-box")).toHaveAttribute("data-select-box", "window");
      await shot(p, "select-window");
    });
    await expect(page.getByTestId("select-box")).toHaveCount(0);
    let s = await state(page);
    expect([...s.selection].sort()).toEqual([a, b].sort());
    // a right-click without a drag is no box: on the selection it keeps it; since 2026-10-21 it
    // opens the canvas menu (e2e/actualsize.spec.ts), and on another shape it selects that one
    // first, as Figma's does (here c's fill: its profile)
    let [cx, cy] = await toClient(page, 0, 0);
    await page.mouse.click(cx, cy, { button: "right" });
    expect([...(await state(page)).selection].sort()).toEqual([a, b].sort());
    await expect(page.getByTestId("canvas-menu")).toHaveAttribute("data-target", "shapes");
    [cx, cy] = await toClient(page, 30, 0);
    await page.mouse.click(cx, cy, { button: "right" });
    expect((await state(page)).sel).toMatchObject({ kind: "profile", ref: { outer: c } });
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("canvas-menu")).toHaveCount(0);
    // right to left: a crossing that only touches c's left edge
    await rightDrag(page, [25, 15], [-45, -15], async (p) => {
      await expect(p.getByTestId("select-box")).toHaveAttribute("data-select-box", "crossing");
      await shot(p, "select-crossing");
    });
    s = await state(page);
    expect([...s.selection].sort()).toEqual([a, b, c].sort());
    // Shift+click takes one out; Esc clears
    const [ex, ey] = await toClient(page, 0, 10);
    await page.keyboard.down("Shift");
    await page.mouse.click(ex, ey);
    await page.keyboard.up("Shift");
    expect([...(await state(page)).selection].sort()).toEqual([a, c].sort());
    await page.keyboard.press("Escape");
    expect((await state(page)).selection).toEqual([]);
  });

  test("d · drag one of 3 selected rectangle profiles with markers 15 mm: all 3 and their markers move; Ctrl+Z puts them back in one step", async ({ page }) => {
    await blank(page);
    const ids = [await rect(page, [-40, -10], [-20, 10]), await rect(page, [-10, -10], [10, 10]), await rect(page, [20, -10], [40, 10])];
    await page.keyboard.press("Escape");
    await rightDrag(page, [-45, 15], [45, -15]);
    await page.keyboard.press("a");
    await idle(page);
    let s = await state(page);
    const fids = ids.map((id) => s.doc.features.find((f: any) => f.profile.outer === id).id);
    const before = { shapes: ids.map((id) => shapeOf(s, id)), ink: await Promise.all(fids.map((f) => ink(page, f))) };
    const k = await scale(page);
    expect([...s.selection].sort()).toEqual([...ids].sort());
    await dragWorld(page, [0, 10], [15, 10], 15);
    await idle(page);
    await shot(page, "multi-move");
    s = await state(page);
    for (const [i, id] of ids.entries()) {
      expect(shapeOf(s, id), `rectangle ${i}`).toMatchObject({ cx: (before.shapes[i] as any).cx + 15, cy: (before.shapes[i] as any).cy });
      const now = await ink(page, fids[i]);
      expect(Math.abs((now.x - before.ink[i].x) / k - 15), `marker ${i} moved ${(now.x - before.ink[i].x) / k} mm`).toBeLessThan(0.1);
      expect(Math.abs(now.y - before.ink[i].y)).toBeLessThan(0.5);
    }
    await page.keyboard.press("Control+z");
    await idle(page);
    s = await state(page);
    for (const [i, id] of ids.entries()) {
      expect(shapeOf(s, id)).toEqual(before.shapes[i]);
      expect(Math.abs((await ink(page, fids[i])).x - before.ink[i].x)).toBeLessThan(0.5);
    }
    // the arrows nudge them all: 1 mm, Shift 10 mm
    await page.keyboard.press("ArrowRight");
    await page.keyboard.press("Shift+ArrowUp");
    s = await state(page);
    for (const [i, id] of ids.entries()) expect(shapeOf(s, id)).toMatchObject({ cx: (before.shapes[i] as any).cx + 1, cy: (before.shapes[i] as any).cy + 10 });
  });

  test("e · Ctrl+C / Ctrl+V of a rectangle with a feature: a second rectangle and feature with its own marker id, every other setting equal", async ({ page }) => {
    await blank(page);
    await rect(page, [-30, -10], [-10, 10]);
    await page.keyboard.press("a");
    await expect(page.getByTestId("extrude-panel")).toBeVisible();
    // a new feature opens on Marker (V1 Command Dialog): Type is a Marker row
    await panelTab(page, "marker");
    await page.locator('[data-path="marker.type"] [data-value="grid"]').click();
    await idle(page);
    await page.getByTestId("panel-ok").click();
    // pick it by its edge (the feature is selected), copy, paste at the pointer
    const [ex, ey] = await toClient(page, -30, 0);
    await page.mouse.click(ex, ey);
    let s = await state(page);
    expect(s.sel.kind).toBe("feature");
    const orig = s.doc.features[0];
    await page.keyboard.press("Control+c");
    const [px, py] = await toClient(page, 25, 0);
    await page.mouse.move(px, py);
    await page.keyboard.press("Control+v");
    await idle(page);
    s = await state(page);
    expect(s.doc.shapes).toHaveLength(2);
    expect(s.doc.features).toHaveLength(2);
    const copy = s.doc.features[1];
    const r2 = shapeOf(s, copy.profile.outer) as any;
    expect(r2).toMatchObject({ kind: "rect", w: 20, h: 20, cx: 25, cy: 0 });
    expect(copy.id).not.toBe(orig.id);
    expect(copy.key).not.toBe(orig.key);
    const first = s.doc.features[0];
    expect(copy.marker.first_id).not.toBe(first.marker.first_id);
    expect(s.plans[copy.id]?.ids?.some((i: number) => s.plans[first.id].ids.includes(i))).toBe(false);
    const settings = (f: any) => ({ ...f, id: 0, key: 0, profile: 0, marker: { ...f.marker, first_id: 0 } });
    expect(settings(copy)).toEqual(settings(first));
    // one undo step takes the paste back
    await page.keyboard.press("Control+z");
    s = await state(page);
    expect(s.doc.shapes).toHaveLength(1);
    expect(s.doc.features).toHaveLength(1);
  });

  test("f · 4 rectangles selected, A: 4 features with 4 distinct ids, the panel on the first", async ({ page }) => {
    await blank(page);
    const ids = [
      await rect(page, [-40, 5], [-20, 25]), await rect(page, [-10, 5], [10, 25]),
      await rect(page, [-40, -25], [-20, -5]), await rect(page, [-10, -25], [10, -5]),
    ];
    await page.keyboard.press("Escape");
    await rightDrag(page, [-45, 30], [15, -30]);
    expect([...(await state(page)).selection].sort()).toEqual([...ids].sort());
    await page.keyboard.press("a");
    await idle(page);
    const s = await state(page);
    expect(s.doc.features).toHaveLength(4);
    expect(s.doc.features.map((f: any) => f.profile.outer).sort()).toEqual([...ids].sort());
    const firsts = s.doc.features.map((f: any) => f.marker.first_id);
    expect(new Set(firsts).size).toBe(4);
    expect(s.panel.open).toBe(true);
    expect(s.panel.featureId).toBe(s.doc.features[0].id);
    for (const f of s.doc.features) expect(s.plans[f.id]?.ids?.[0]).toBe(f.marker.first_id);
  });

  test("g · a distance from the Y axis to a left edge: 25 moves the rectangle to x = 25; x is then held, y still moves", async ({ page }) => {
    await blank(page);
    const id = await rect(page, [10, 10], [40, 30]);
    await page.keyboard.press("d");
    // the Y axis (clicked away from any shape), then the left edge, dragged up to place
    const [yx, yy] = await toClient(page, 0, -30);
    await page.mouse.click(yx, yy);
    await expect(page.getByTestId("dim-picks")).toHaveAttribute("data-picks", "1");
    await dragWorld(page, [10, 20], [8, 40]);
    const box = page.getByTestId("sdim-input");
    await expect(box).toHaveValue("10");
    await box.fill("25");
    await box.press("Enter");
    let s = await state(page);
    expect(s.doc.dims[0]).toMatchObject({ kind: "x", a: { axis: "y" }, b: { shape: id, at: "l" }, value: 25 });
    expect(shapeOf(s, id)).toMatchObject({ cx: 40, w: 30, cy: 20 });
    const d = await drawnSize(page, id);
    expect(Math.abs(d.x0 - 25), `left edge drawn at ${d.x0} mm`).toBeLessThan(0.15);
    // by hand: x holds (with a note), y moves
    await page.keyboard.press("Escape");
    await dragWorld(page, [25, 15], [35, 22]);
    s = await state(page);
    expect(shapeOf(s, id)).toMatchObject({ cx: 40, cy: 27 });
    await expect(page.getByTestId("note")).toContainText("Held on x");
    // Del on the selected dim deletes it; then x moves again
    await page.locator(`[data-sketch-dim="${s.doc.dims[0].id}"] [data-sdim-label]`).click();
    await expect.poll(async () => (await state(page)).dimSel).toBe(s.doc.dims[0].id);
    await page.keyboard.press("Delete");
    expect((await state(page)).doc.dims).toHaveLength(0);
    await dragWorld(page, [25, 27], [30, 27]);
    expect(shapeOf(await state(page), id)).toMatchObject({ cx: 45, cy: 27 });
  });

  test("media · dims on a rectangle: typed W and H, and its left edge 15 from the Y axis", async ({ page }) => {
    test.skip(!MEDIA, "SKETCH_MEDIA=<dir> writes the shot");
    await blank(page);
    await page.keyboard.press("r");
    const [ax, ay] = await toClient(page, 5, -10);
    await page.mouse.click(ax, ay);
    const [bx, by] = await toClient(page, 30, 15);
    await page.mouse.move(bx, by, { steps: 5 });
    await page.keyboard.type("40");
    await page.keyboard.press("Tab");
    await page.keyboard.type("25");
    await page.keyboard.press("Enter");
    await page.keyboard.press("d");
    const [yx, yy] = await toClient(page, 0, -30);
    await page.mouse.click(yx, yy);
    await dragWorld(page, [5, 0], [3, -22]);
    await page.getByTestId("sdim-input").fill("15");
    await page.getByTestId("sdim-input").press("Enter");
    await page.keyboard.press("Escape");
    await dragWorld(page, [55, 0], [55, 0], 1);
    const s = await state(page);
    expect(s.doc.dims).toHaveLength(3);
    expect(s.doc.shapes[0]).toMatchObject({ cx: 35, w: 40, h: 25 });
    await page.mouse.move(5, 5);
    await shot(page, "dims-on-rectangle");
  });

  test("media · the marker maker: 4 typed rectangles, select all, A, Ctrl+C / Ctrl+V, drag the group", async ({ browser }) => {
    test.skip(!MEDIA, "SKETCH_MEDIA=<dir> records it");
    const ctx = await browser.newContext({ baseURL: test.info().project.use.baseURL, viewport: { width: 1280, height: 800 }, recordVideo: { dir: MEDIA, size: { width: 1280, height: 800 } } });
    const page = await ctx.newPage();
    await blank(page);
    const pause = (ms = 350) => page.waitForTimeout(ms);
    const corners: [number, number][] = [[-45, 8], [-20, 8], [-45, -22], [-20, -22]];
    for (const [x, y] of corners) {
      await page.keyboard.press("r");
      const [ax, ay] = await toClient(page, x, y);
      await page.mouse.move(ax, ay, { steps: 5 });
      await page.mouse.click(ax, ay);
      const [bx, by] = await toClient(page, x + 18, y + 16);
      await page.mouse.move(bx, by, { steps: 8 });
      await page.keyboard.type("20", { delay: 60 });
      await page.keyboard.press("Tab");
      await page.keyboard.type("15", { delay: 60 });
      await pause(200);
      await page.keyboard.press("Enter");
      await pause(150);
    }
    await page.keyboard.press("Escape");
    await rightDrag(page, [-50, 30], [5, -30], () => pause(300));
    await pause();
    await page.keyboard.press("a");
    await idle(page);
    await pause(600);
    await page.getByTestId("panel-ok").click();
    await rightDrag(page, [-50, 30], [5, -30]);
    await page.keyboard.press("Control+c");
    const [px, py] = await toClient(page, 25, 0);
    await page.mouse.move(px, py, { steps: 8 });
    await page.keyboard.press("Control+v");
    await idle(page);
    await pause(600);
    const s = await state(page);
    expect(s.doc.features).toHaveLength(8);
    expect(new Set(s.doc.features.map((f: any) => f.marker.first_id)).size).toBe(8);
    await dragWorld(page, [5, 7.5], [15, 2.5], 20, 25);
    await idle(page);
    await pause(900);
    await shot(page, "marker-maker-end");
    const video = page.video()!;
    await ctx.close();
    copyFileSync(await video.path(), path.join(MEDIA, "marker-maker.webm"));
  });
});
