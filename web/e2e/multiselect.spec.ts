// Multi-selection, every way to start one on every target (Zach, 2026-10-20
// night: "multi select by right click drag doesn't work, or by shift click").
// Two causes. The input: the pointer handlers read the gesture from the last
// render, so a release that came right after the last move (a real hand, a
// busy page) saw the box unmoved and selected nothing -- only real X11 input
// shows it (scripts/real-input-check.mjs, its "flick" cases; CDP waits for
// each step). The targets: Shift+click took an edge or a marker only (a press
// on a fill selected the region), a left-drag on empty canvas did nothing, a
// right-drag could not start on a dimension's label, and two quick
// Shift+clicks were a double-click. Here: a right-drag and a
// left-drag (from empty canvas, a fill, an edge, a dimension label), Shift+
// and Ctrl+click (an edge, a fill, a marker), Shift+drag adding, and the
// selection drawn: every selected edge, the bounds, "N selected". The same
// gestures under real X11 input: scripts/real-input-check.mjs.
import { expect, test, type Page } from "@playwright/test";
import { clickAt, coreReady, idle, openMenu, openStudio, state, toClient, dragWorld } from "./helpers";

/** The plate P (100 x 70), A and B drawn inside it; A gets a marker. Ids by name. */
async function scene(page: Page): Promise<{ P: string; A: string; B: string }> {
  await openStudio(page);
  await coreReady(page);
  await openMenu(page, "file");
  await page.getByTestId("cmd-new").click();
  const rect = async (a: [number, number], b: [number, number]) => {
    await page.keyboard.press("r");
    await dragWorld(page, a, b);
    return (await state(page)).sel.id as string;
  };
  const P = await rect([-50, -35], [50, 35]);
  const A = await rect([-40, -20], [-10, 10]);
  const B = await rect([5, -20], [35, 10]);
  await page.keyboard.press("Escape");
  // fitted, then zoomed out: empty canvas all round the plate
  await page.keyboard.press("f");
  const [cx, cy] = await toClient(page, 0, 0);
  await page.mouse.move(cx, cy);
  await page.mouse.wheel(0, 400);
  await page.waitForTimeout(100);
  return { P, A, B };
}

/** A drag (mm to mm) with `button`, in steps; `mods` held through it. */
async function drag(page: Page, button: "left" | "right", from: [number, number], to: [number, number], mods: string[] = []): Promise<void> {
  const [ax, ay] = await toClient(page, ...from);
  const [bx, by] = await toClient(page, ...to);
  await page.mouse.move(ax, ay);
  for (const m of mods) await page.keyboard.down(m);
  await page.mouse.down({ button });
  for (let i = 1; i <= 10; i++) await page.mouse.move(ax + ((bx - ax) * i) / 10, ay + ((by - ay) * i) / 10);
  await page.mouse.up({ button });
  for (const m of mods.reverse()) await page.keyboard.up(m);
}

async function modClick(page: Page, at: [number, number], mod: string): Promise<void> {
  await page.keyboard.down(mod);
  await clickAt(page, ...at);
  await page.keyboard.up(mod);
}

const selection = async (page: Page): Promise<string[]> => [...(await state(page)).selection].sort();
const EMPTY: [number, number] = [70, -40];
const fresh = async (page: Page) => { await clickAt(page, ...EMPTY); await page.keyboard.press("Escape"); expect(await selection(page)).toEqual([]); };

/** What is drawn as selected: the edges marked on, the chip, the bounds. */
async function drawn(page: Page) {
  return page.evaluate(() => ({
    on: [...document.querySelectorAll("[data-shape].on")].map((e) => e.getAttribute("data-shape")!).sort(),
    chip: document.querySelector("[data-testid=selection-count]")?.textContent ?? null,
    bounds: (() => { const r = document.querySelector("[data-testid=selection-bounds]")?.getBoundingClientRect(); return r ? { x: r.x, y: r.y, w: r.width, h: r.height } : null; })(),
    shapes: Object.fromEntries([...document.querySelectorAll("[data-shape]")].map((e) => { const r = e.getBoundingClientRect(); return [e.getAttribute("data-shape"), { x: r.x, y: r.y, w: r.width, h: r.height }]; })),
  }));
}

test.describe("multi-selection", () => {
  test("a · a left-drag is a box too: from empty canvas (window) and from a fill no marker owns; a click there still does what it did", async ({ page }) => {
    const { P, A, B } = await scene(page);
    // from empty canvas, left to right around everything: a window
    await drag(page, "left", [-60, 45], [60, -45]);
    expect(await selection(page)).toEqual([P, A, B].sort());
    // from the plate's fill, around A and B only
    await fresh(page);
    await drag(page, "left", [-45, 20], [40, -30]);
    expect(await selection(page)).toEqual([A, B].sort());
    // right to left: a crossing, it takes what it touches (A only)
    await fresh(page);
    await drag(page, "left", [-20, 0], [-45, -5]);
    expect(await selection(page)).toEqual([A]);
    // a click on the plate's fill still selects its profile; on empty canvas still clears
    await fresh(page);
    await clickAt(page, 0, 25);
    expect((await state(page)).sel?.kind).toBe("profile");
    await clickAt(page, ...EMPTY);
    expect((await state(page)).sel).toBeNull();
  });

  test("b · a right-drag starts anywhere: empty canvas, a fill, an edge, a shape's fill (crossing)", async ({ page }) => {
    const { P, A, B } = await scene(page);
    await drag(page, "right", [-60, 45], [60, -45]);
    expect(await selection(page)).toEqual([P, A, B].sort());
    await fresh(page);
    await drag(page, "right", [-45, 20], [40, -30]);
    expect(await selection(page)).toEqual([A, B].sort());
    // from A's top edge (1 mm above it: within the edge's 6 px), to the right: a window around B (A is not inside it)
    await fresh(page);
    await drag(page, "right", [-15, 11], [40, -30]);
    expect(await selection(page)).toEqual([B]);
    // from B's fill, right to left: a crossing through A
    await fresh(page);
    await drag(page, "right", [30, 0], [-20, -5]);
    expect(await selection(page)).toEqual([A, B].sort());
  });

  test("c · Shift+click and Ctrl+click add or take out a shape by its edge, its fill or its marker; Shift+drag adds a box", async ({ page }) => {
    const { P, A, B } = await scene(page);
    // A's marker
    await clickAt(page, -25, -5);
    await page.keyboard.press("a");
    await idle(page);
    await page.getByTestId("panel-ok").click();
    await idle(page);
    await fresh(page);
    // edge, then fill
    await clickAt(page, 5, -5);
    expect(await selection(page)).toEqual([B]);
    await modClick(page, [0, 30], "Shift");
    expect(await selection(page)).toEqual([P, B].sort());
    // the same fill again, at once (no double-click): out again
    await modClick(page, [0, 30], "Shift");
    expect(await selection(page)).toEqual([B]);
    // A's marker: Shift+click adds its rectangle
    const fid = (await state(page)).doc.features[0].id;
    const ink = (await page.locator(`[data-marker="${fid}"] [data-marker-black]`).boundingBox())!;
    await page.keyboard.down("Shift");
    await page.mouse.click(ink.x + ink.width / 2, ink.y + ink.height / 2);
    await page.keyboard.up("Shift");
    expect(await selection(page)).toEqual([A, B].sort());
    await expect(page.getByTestId("extrude-panel")).toHaveCount(0);
    // Ctrl+click on B's fill takes it out
    await modClick(page, [20, 0], "Control");
    expect(await selection(page)).toEqual([A]);
    // a click on a fill first (a profile), then Shift+click another fill: both shapes
    await fresh(page);
    await clickAt(page, 0, 30);
    expect((await state(page)).sel?.kind).toBe("profile");
    await modClick(page, [20, 0], "Shift");
    expect(await selection(page)).toEqual([P, B].sort());
    // Shift+drag on empty canvas adds what it boxes
    await fresh(page);
    await clickAt(page, 5, -5);
    await drag(page, "left", [-60, 45], [-5, -45], ["Shift"]);
    expect(await selection(page)).toEqual([A, B].sort());
  });

  test("d · a right-drag may start on a dimension's label", async ({ page }) => {
    const { A, B } = await scene(page);
    await clickAt(page, -25, -5);
    await page.keyboard.press("a");
    await idle(page);
    await expect(page.getByTestId("extrude-panel")).toBeVisible();
    await expect(page.locator("[data-dim-label]").first()).toBeVisible();
    // the topmost label: above A, left of B
    const boxes = await page.locator("[data-dim-label]").evaluateAll((els) => els.map((e) => { const b = e.getBoundingClientRect(); return { x: b.x, y: b.y, width: b.width, height: b.height }; }));
    const r = boxes.reduce((a, b) => (b.y < a.y ? b : a));
    const [bx, by] = await toClient(page, 40, -30);
    await page.mouse.move(r.x + r.width / 2, r.y + r.height / 2);
    await page.mouse.down({ button: "right" });
    for (let i = 1; i <= 10; i++) await page.mouse.move(r.x + r.width / 2 + ((bx - r.x - r.width / 2) * i) / 10, r.y + r.height / 2 + ((by - r.y - r.height / 2) * i) / 10);
    await expect(page.getByTestId("select-box")).toBeVisible();
    await page.mouse.up({ button: "right" });
    // a window from above A's middle: B is inside it, A is not
    expect(await selection(page)).toEqual([B]);
  });

  test("e · several selected are drawn so: every edge on, their bounds around them, \"N selected\" under them", async ({ page }) => {
    const { P, A, B } = await scene(page);
    let d = await drawn(page);
    expect(d.chip).toBeNull();
    expect(d.bounds).toBeNull();
    await drag(page, "right", [-60, 45], [60, -45]);
    d = await drawn(page);
    expect(d.on).toEqual([P, A, B].sort());
    expect(d.chip).toBe("3 selected");
    // the bounds hold every selected shape (P's, the outermost, within a stroke)
    const b = d.bounds!, p = d.shapes[P];
    expect(Math.abs(b.x - p.x)).toBeLessThanOrEqual(2);
    expect(Math.abs(b.w - p.w)).toBeLessThanOrEqual(3);
    // the chip sits under the bounds, centred
    const chip = (await page.getByTestId("selection-count").boundingBox())!;
    expect(chip.y).toBeGreaterThanOrEqual(b.y + b.h);
    expect(Math.abs(chip.x + chip.width / 2 - (b.x + b.w / 2))).toBeLessThanOrEqual(2);
    // two: the chip says 2; one: no chip, no bounds
    await modClick(page, [0, 30], "Shift");
    d = await drawn(page);
    expect(d.on).toEqual([A, B].sort());
    expect(d.chip).toBe("2 selected");
    await modClick(page, [-25, -5], "Shift");
    d = await drawn(page);
    expect(d.on).toEqual([B]);
    expect(d.chip).toBeNull();
    expect(d.bounds).toBeNull();
  });
});
