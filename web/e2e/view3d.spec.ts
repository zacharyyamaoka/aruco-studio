// The 3D view (V3 "3D Toggle", web/src/view3d): 3 or the canvas's 2D | 3D
// toggle shows every feature's planned layers as solids; on the feature in
// focus, Fusion's Extrude manipulator: a drag arrow per height with a value
// box at it. Each check measures: the probe's numbers (window.__aruco.view3d:
// the arrows' client positions, the plan's layers and MarkerPlan.extrude),
// never DOM presence alone. Screenshots (1280 × 800) go to VIEW3D_SHOTS
// (default test-results/view3d); VIEW3D_VIDEO records the drag-then-type
// flow into that folder.
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { CORE, clickAt, coreReady, idle, loadExample, openStudio, planOutline, state } from "./helpers";

const SHOTS = process.env.VIEW3D_SHOTS ?? "test-results/view3d";

type Arrow = { key: string; field: string; value: number; driven: boolean; base3d: [number, number, number]; dir: number;
  base: [number, number]; tip: [number, number]; box: { x: number; y: number; w: number; h: number } | null };

const v3 = (page: Page): Promise<{ feature: string | null; arrows: Arrow[]; solids: Record<string, number>; faces: number } | null> =>
  page.evaluate(() => JSON.parse(JSON.stringify((window as any).__aruco.view3d())));

async function arrow(page: Page, key: string): Promise<Arrow> {
  await expect.poll(async () => (await v3(page))?.arrows.some((a) => a.key === key), { message: `the ${key} arrow is drawn` }).toBe(true);
  return (await v3(page))!.arrows.find((a) => a.key === key)!;
}

/** Choose the first built-in preset of a method in the presets modal. */
async function preset(page: Page, chip: "3D print" | "Inkjet"): Promise<void> {
  await page.getByTestId("preset-chip").click();
  const modal = page.getByTestId("presets-modal");
  await modal.locator('[data-coll="builtin"]').click();
  await modal.getByTestId("presets-nav").locator(`[data-chip="${chip}"]`).click();
  await modal.locator(".card[data-card]").first().click();
  await page.getByTestId("presets-select").click();
  await expect(modal).toHaveCount(0);
  await idle(page);
}

/** Examples › Custom placement (a rectangle profile: a tile in open space), on a 3D-print preset unless `inkjet`. */
async function tile(page: Page, inkjet = false): Promise<string> {
  await openStudio(page);
  await coreReady(page);
  await loadExample(page, "custom-placement");
  await idle(page);
  if (!inkjet) await preset(page, "3D print");
  const s = await state(page);
  expect(s.doc.preset.method).toBe(inkjet ? "inkjet" : "print3d");
  expect(s.plan?.extrude, "the core answers MarkerPlan.extrude").toBeTruthy();
  return s.feature.id;
}

async function to3d(page: Page): Promise<void> {
  await page.keyboard.press("3");
  await expect(page.getByTestId("view3d")).toBeVisible();
  await expect.poll(async () => Object.keys((await v3(page))?.solids ?? {}).length).toBeGreaterThan(0);
}

/** Zoom the 3D view in at a client point (the wheel zooms at the cursor). */
async function zoomAt(page: Page, at: [number, number], ticks: number): Promise<void> {
  await page.mouse.move(...at);
  for (let i = 0; i < ticks; i++) { await page.mouse.wheel(0, -200); await page.waitForTimeout(30); }
}

/** Press an arrow halfway along it and drag by (dx, dy) px in small steps. */
async function dragArrow(page: Page, a: Arrow, dx: number, dy: number, steps = 10): Promise<void> {
  const g: [number, number] = [(a.base[0] + a.tip[0]) / 2, (a.base[1] + a.tip[1]) / 2];
  await page.mouse.move(...g);
  await page.mouse.down();
  for (let i = 1; i <= steps; i++) { await page.mouse.move(g[0] + (dx * i) / steps, g[1] + (dy * i) / steps); await page.waitForTimeout(15); }
  await page.mouse.up();
  await idle(page);
}

const layer = (plan: any, colour: string) => plan.layers.find((L: any) => L.op === "add" && L.colour === colour && L.part !== "label");

test.describe(`the 3D view (${CORE} core)`, () => {
  test.skip(CORE === "mock", "the mock core plans no layers");

  test("a · 3 shows a WebGL canvas over the stage; the toggle back restores the SVG viewport, the selection and the panel", async ({ page }) => {
    await tile(page);
    // inspect the marker in 2D: selected, its panel open
    const o = await planOutline(page);
    await clickAt(page, o.cx, o.cy);
    await expect(page.getByTestId("extrude-panel")).toBeVisible();
    const before = await state(page);
    expect(before.sel?.kind).toBe("feature");

    await to3d(page);
    const canvas = page.locator('[data-testid="view3d"] canvas');
    expect(await canvas.evaluate((c) => !!((c as HTMLCanvasElement).getContext("webgl2") ?? (c as HTMLCanvasElement).getContext("webgl")))).toBe(true);
    const cb = (await canvas.boundingBox())!, sb = (await page.locator(".stage").boundingBox())!;
    expect(Math.abs(cb.width - sb.width) + Math.abs(cb.height - sb.height)).toBeLessThan(2);
    await expect(page.getByTestId("viewport")).toBeHidden();
    expect((await state(page)).view3d).toBe(true);
    await expect(page.getByTestId("view-toggle")).toHaveAttribute("data-view", "3d");

    await page.getByTestId("view-seg").locator('[data-value="2d"]').click();
    await expect(page.getByTestId("view3d")).toHaveCount(0);
    await expect(page.locator('[data-testid="viewport"] svg')).toBeVisible();
    const after = await state(page);
    expect(after.view3d).toBe(false);
    expect(after.sel).toEqual(before.sel);
    expect(after.panel).toEqual(before.panel);
    expect(after.camera).toEqual(before.camera);
    await expect(page.getByTestId("extrude-panel")).toBeVisible();
    // and the toggle's 3D button
    await page.getByTestId("view-seg").locator('[data-value="3d"]').click();
    await expect(page.getByTestId("view3d")).toBeVisible();
  });

  test("b · 3D print: the white arrow stands on the white's outer face; a drag up sets white_mm (one undo step), typed 2.4 is planned, ↺ drives it again", async ({ page }) => {
    const fid = await tile(page);
    await to3d(page);
    let s = await state(page);
    const white = layer(s.plan, "white");
    expect(s.plan.extrude.flipped).toBe(false);
    const W0 = s.plan.extrude.white_mm as number;
    expect(white.z[1]).toBeCloseTo(W0, 6);
    await zoomAt(page, await page.evaluate(([x, y]) => (window as any).__aruco.project3d(x, y, 0), [(await planOutline(page)).cx, (await planOutline(page)).cy]), 6);

    // on the outer face: the arrow's base is the face's point, projected (3 px)
    let a = await arrow(page, "white_mm");
    expect(a).toMatchObject({ value: W0, driven: true, dir: 1 });
    expect(a.base3d[2]).toBeCloseTo(white.z[1], 6);
    const xs = white.polygons[0].outer.map((p: number[]) => p[0]), ys = white.polygons[0].outer.map((p: number[]) => p[1]);
    expect(a.base3d[0]).toBeGreaterThan(Math.min(...xs));
    expect(a.base3d[0]).toBeLessThan(Math.max(...xs));
    expect(a.base3d[1]).toBeGreaterThan(Math.min(...ys));
    expect(a.base3d[1]).toBeLessThan(Math.max(...ys));
    const face = await page.evaluate(([x, y, z]) => (window as any).__aruco.project3d(x, y, z), [a.base3d[0], a.base3d[1], white.z[1]]);
    expect(Math.hypot(face[0] - a.base[0], face[1] - a.base[1]), "the arrow's base on the white's outer face (px)").toBeLessThanOrEqual(3);
    expect(a.tip[1], "the arrow points up the screen (out of the face)").toBeLessThan(a.base[1] - 20);
    // the value box sits at the arrow's head, grey (driven)
    expect(a.box).toBeTruthy();
    expect(Math.abs(a.box!.x - a.tip[0])).toBeLessThan(40);
    expect(Math.abs(a.box!.y + a.box!.h / 2 - a.tip[1])).toBeLessThan(20);
    const box = page.locator('[data-testid="v3-box"][data-key="white_mm"]');
    await expect(box).toHaveAttribute("data-driven", "true");
    await expect(box.locator("input")).toHaveValue(`${W0.toFixed(2)} mm`);
    await page.screenshot({ path: path.join(SHOTS, "3d-print-driven.png") });

    // drag up by 40 px: white_mm set, larger; the plan's white z1 follows
    await dragArrow(page, a, 0, -40);
    s = await state(page);
    const W1 = s.feature.extrude.white_mm as number;
    expect(W1, "the drag set white_mm").toBeGreaterThan(W0);
    expect(Math.abs(W1 / 0.05 - Math.round(W1 / 0.05)), "snapped to 0.05 mm (no layer height)").toBeLessThan(1e-6);
    expect(s.plan.extrude.white_mm).toBeCloseTo(W1, 6);
    expect(s.plan.extrude.driven).not.toContain("white_mm");
    expect(layer(s.plan, "white").z[1]).toBeCloseTo(W1, 6);
    a = await arrow(page, "white_mm");
    expect(a).toMatchObject({ value: W1, driven: false });
    expect(a.base3d[2]).toBeCloseTo(W1, 6);
    await expect(box).toHaveAttribute("data-driven", "false");

    // Ctrl+Z: the whole drag in one step
    await page.keyboard.press("Control+z");
    await idle(page);
    s = await state(page);
    expect(s.feature.extrude.white_mm, "one Ctrl+Z undoes the drag").toBeUndefined();
    expect(s.plan.extrude.white_mm).toBeCloseTo(W0, 6);
    expect(layer(s.plan, "white").z[1]).toBeCloseTo(W0, 6);

    // type 2.4 in the box, Enter
    await box.locator("input").click();
    await page.keyboard.press("Control+a");
    await page.keyboard.type("2.4");
    await page.keyboard.press("Enter");
    await idle(page);
    s = await state(page);
    expect(s.feature.extrude.white_mm).toBe(2.4);
    expect(s.plan.extrude.white_mm).toBe(2.4);
    expect(layer(s.plan, "white").z[1]).toBeCloseTo(2.4, 6);
    await expect(box.locator("input")).toHaveValue("2.40 mm");
    await expect(box).toHaveAttribute("data-driven", "false");
    // Esc cancels a typed value
    await box.locator("input").click();
    await page.keyboard.press("Control+a");
    await page.keyboard.type("9");
    await page.keyboard.press("Escape");
    await idle(page);
    expect((await state(page)).feature.extrude.white_mm).toBe(2.4);
    await expect(box.locator("input")).toHaveValue("2.40 mm");

    // ↺: driven again
    await box.locator('[data-reset="extrude.white_mm"]').click();
    await idle(page);
    s = await state(page);
    expect(s.feature.extrude.white_mm).toBeUndefined();
    expect(s.plan.extrude.driven).toContain("white_mm");
    await expect(box).toHaveAttribute("data-driven", "true");
    expect(s.feature.id).toBe(fid);
  });

  test("c · the black arrow writes black_mm, measured from the white's outer face: the black spans [white − black, white]", async ({ page }) => {
    await tile(page);
    await to3d(page);
    await zoomAt(page, await page.evaluate(([x, y]) => (window as any).__aruco.project3d(x, y, 0), [(await planOutline(page)).cx, (await planOutline(page)).cy]), 6);
    let s = await state(page);
    const W = s.plan.extrude.white_mm as number, K0 = s.plan.extrude.black_mm as number;
    let a = await arrow(page, "black_mm");
    expect(a).toMatchObject({ value: K0, driven: true, dir: -1 });
    expect(a.base3d[2]).toBeCloseTo(W - K0, 6);
    expect(a.tip[1], "the black's arrow points into the tile (down the screen)").toBeGreaterThan(a.base[1] + 20);

    // drag along it (down): deeper
    await dragArrow(page, a, 0, 30);
    s = await state(page);
    const K1 = s.feature.extrude.black_mm as number;
    expect(K1, "the drag set black_mm").toBeGreaterThan(K0);
    expect(s.feature.extrude.white_mm, "the white stays driven").toBeUndefined();
    expect(s.plan.extrude.black_mm).toBeCloseTo(K1, 6);
    const black = layer(s.plan, "black");
    expect(black.z[0]).toBeCloseTo(W - K1, 6);
    expect(black.z[1]).toBeCloseTo(W, 6);
    a = await arrow(page, "black_mm");
    expect(a.base3d[2]).toBeCloseTo(W - K1, 6);
    await page.screenshot({ path: path.join(SHOTS, "3d-print-black-set.png") });

    // typed, with the white set too: the black still hangs from the white's outer face
    const typeIn = async (key: string, v: string) => {
      const input = page.locator(`[data-testid="v3-box"][data-key="${key}"] input`);
      await input.click();
      await page.keyboard.press("Control+a");
      await page.keyboard.type(v);
      await page.keyboard.press("Enter");
      await idle(page);
    };
    await typeIn("white_mm", "3");
    await typeIn("black_mm", "1.2");
    s = await state(page);
    expect(s.plan.extrude).toMatchObject({ white_mm: 3, black_mm: 1.2 });
    expect(layer(s.plan, "black").z[0]).toBeCloseTo(1.8, 6);
    expect(layer(s.plan, "black").z[1]).toBeCloseTo(3, 6);
    expect((await arrow(page, "black_mm")).base3d[2]).toBeCloseTo(1.8, 6);
    await page.waitForTimeout(100);
    await page.screenshot({ path: path.join(SHOTS, "3d-print-both-set.png") });
  });

  test("d · inkjet: ONE arrow, the paper (driven from the preset's thickness)", async ({ page }) => {
    await tile(page, true);
    await to3d(page);
    await zoomAt(page, await page.evaluate(([x, y]) => (window as any).__aruco.project3d(x, y, 0), [(await planOutline(page)).cx, (await planOutline(page)).cy]), 8);
    const s = await state(page);
    const v = (await v3(page))!;
    expect(v.arrows.map((a) => a.key)).toEqual(["paper_mm"]);
    expect(v.arrows[0]).toMatchObject({ field: "extrude.paper_mm", value: s.doc.preset.thickness_mm, driven: true, dir: 1 });
    expect(v.arrows[0].base3d[2]).toBeCloseTo(layer(s.plan, "white").z[1], 6);
    await expect(page.locator('[data-testid="v3-box"]')).toHaveCount(1);
    await page.waitForTimeout(100);
    await page.screenshot({ path: path.join(SHOTS, "inkjet.png") });
  });

  test("e · a face profile, 3D print: Black only goes into the face, drawn as a neutral body; one arrow, into it", async ({ page }) => {
    await openStudio(page);
    await coreReady(page);
    await loadExample(page, "plate");
    await preset(page, "3D print");
    await clickAt(page, 60, 40);
    await page.keyboard.press("a");
    await idle(page);
    await expect(page.getByTestId("extrude-panel")).toBeVisible();
    let s = await state(page);
    expect(s.plan.extrude).toMatchObject({ mode: "black", flipped: false });
    const K = s.plan.extrude.black_mm as number;
    await to3d(page);
    const v = (await v3(page))!;
    expect(v.arrows.map((a) => a.key), "Black only: no white arrow").toEqual(["black_mm"]);
    expect(v.arrows[0]).toMatchObject({ dir: -1 });
    expect(v.arrows[0].base3d[2]).toBeCloseTo(-K, 6);
    expect(layer(s.plan, "black").z).toEqual([-K, 0]);
    const drawn = await page.evaluate(() => (window as any).__aruco.view3d());
    expect(drawn.solids[s.feature.id], "the black is drawn").toBeGreaterThan(0);
    expect(drawn.faces, "the face under it, as a body").toBe(1);
    await zoomAt(page, await page.evaluate(([x, y]) => (window as any).__aruco.project3d(x, y, 0), [(await planOutline(page)).cx, (await planOutline(page)).cy]), 5);
    await page.waitForTimeout(100);
    await page.screenshot({ path: path.join(SHOTS, "face-black-only.png") });

  });

  test("f · Flip (the panel's row): the tile turns over, the white's arrow points down from its outer face, the black's up", async ({ page }) => {
    await tile(page);
    const o = await planOutline(page);
    await clickAt(page, o.cx, o.cy);
    await expect(page.getByTestId("extrude-panel")).toBeVisible();
    // the row, wherever the panel keeps it
    const flip = page.locator('[role="switch"][data-path="marker.flip"]');
    for (const tab of await page.locator('.fpanel [role="tab"]').all()) {
      if (await flip.isVisible()) break;
      await tab.click();
    }
    await flip.click();
    await idle(page);
    const s = await state(page);
    const W = s.plan.extrude.white_mm as number, K = s.plan.extrude.black_mm as number;
    expect(s.plan.extrude.flipped).toBe(true);
    expect(layer(s.plan, "white").z).toEqual([-W, 0]);
    await to3d(page);
    const w = await arrow(page, "white_mm"), k = await arrow(page, "black_mm");
    expect(w).toMatchObject({ dir: -1 });
    expect(w.base3d[2]).toBeCloseTo(-W, 6);
    expect(k).toMatchObject({ dir: 1 });
    expect(k.base3d[2]).toBeCloseTo(-W + K, 6);
    expect(w.tip[1], "the white's arrow points down the screen").toBeGreaterThan(w.base[1] + 20);
    await page.screenshot({ path: path.join(SHOTS, "3d-print-flipped.png") });
  });

  test("video · the drag-then-type flow (VIEW3D_VIDEO)", async ({ browser }) => {
    test.skip(!process.env.VIEW3D_VIDEO, "VIEW3D_VIDEO=1 records it");
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, recordVideo: { dir: path.join(SHOTS, "raw"), size: { width: 1280, height: 800 } } });
    const t0 = Date.now();
    const page = await ctx.newPage();
    await tile(page);
    await to3d(page);
    await zoomAt(page, await page.evaluate(([x, y]) => (window as any).__aruco.project3d(x, y, 0), [(await planOutline(page)).cx, (await planOutline(page)).cy]), 6);
    await page.waitForTimeout(600);
    // the flow starts here: the video's first seconds are the core loading (trim them: ffmpeg -ss)
    test.info().annotations.push({ type: "flow starts at (s)", description: ((Date.now() - t0) / 1000 - 0.5).toFixed(1) });
    const a = await arrow(page, "white_mm");
    const g: [number, number] = [(a.base[0] + a.tip[0]) / 2, (a.base[1] + a.tip[1]) / 2];
    await page.mouse.move(...g, { steps: 8 });
    await page.mouse.down();
    for (let i = 1; i <= 12; i++) { await page.mouse.move(g[0], g[1] - i * 3); await page.waitForTimeout(30); }
    await page.mouse.up();
    await idle(page);
    await page.waitForTimeout(700);
    const k = await arrow(page, "black_mm");
    const h: [number, number] = [(k.base[0] + k.tip[0]) / 2, (k.base[1] + k.tip[1]) / 2];
    await page.mouse.move(...h, { steps: 8 });
    await page.mouse.down();
    for (let i = 1; i <= 8; i++) { await page.mouse.move(h[0], h[1] + i * 2); await page.waitForTimeout(30); }
    await page.mouse.up();
    await idle(page);
    await page.waitForTimeout(700);
    const input = page.locator('[data-testid="v3-box"][data-key="white_mm"] input');
    await input.click();
    await page.waitForTimeout(300);
    await page.keyboard.press("Control+a");
    await page.keyboard.type("2.4", { delay: 120 });
    await page.waitForTimeout(300);
    await page.keyboard.press("Enter");
    await idle(page);
    await page.waitForTimeout(900);
    expect((await state(page)).plan.extrude.white_mm).toBe(2.4);
    const video = page.video()!;
    await ctx.close();
    await video.saveAs(path.join(SHOTS, "view3d-drag-type-raw.webm"));
    await video.delete();
    console.log(test.info().annotations.map((x) => `${x.type}: ${x.description}`).join("\n"));
  });
});
