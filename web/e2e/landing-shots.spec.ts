// The landing page's own captures (docs/build_landing.py), from a running
// site (usually the live one), beside the review report's stills:
//
//   E2E_BASE_URL=https://arucostudio.com LANDING_SRC=/abs/landing-src npx playwright test --project=e2e e2e/landing-shots.spec.ts
//
// Skipped unless LANDING_SRC is set, so the normal e2e run is unchanged.
// Writes <src>/shots/*.png (2x pixel density) and <src>/shots/landing-facts.json,
// and the marker-maker clip <src>/canvas.webm with the moment of each step
// beside it (canvas.marks.json, seconds from the page's start) so the builder
// can cut the core's loading out. Each test checks the state it photographs.
import { copyFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { expect, test, type Locator, type Page } from "@playwright/test";
import { clickAt, coreReady, dragWorld, idle, loadExample, openPresets, openStudio, panelTab, planOutline, state, toClient, openMenu } from "./helpers";

const SRC = process.env.LANDING_SRC ?? "";
const SHOTS = path.join(SRC, "shots");
const facts: Record<string, unknown> = {};
const OVER = '[data-testid="extrude-panel"], [data-testid="shape-dims"], [data-testid="toolbar"]';

test.skip(!SRC, "LANDING_SRC is not set");
test.use({ deviceScaleFactor: 2 });

test.beforeAll(() => { if (SRC) mkdirSync(SHOTS, { recursive: true }); });
test.afterAll(() => {
  if (!SRC) return;
  // merged, so a partial run (-g) keeps what the other tests measured before
  const file = path.join(SHOTS, "landing-facts.json");
  const before = existsSync(file) ? JSON.parse(readFileSync(file, "utf8")) : {};
  writeFileSync(file, JSON.stringify({ ...before, ...facts }, null, 2));
});

async function calm(page: Page): Promise<void> {
  await page.mouse.move(2, 2); // no hover state in the picture
  await page.waitForTimeout(300);
}

/** The union of some elements' boxes as a clipped screenshot, with the panel,
 *  the toolbar and the shape's dims hidden. */
async function clip(page: Page, name: string, locs: Locator[], pad = 14, points: [number, number][] = []): Promise<void> {
  await calm(page);
  const bs = [...await Promise.all(locs.map(async (l) => (await l.boundingBox())!)), ...points.map(([x, y]) => ({ x, y, width: 0, height: 0 }))];
  const vw = page.viewportSize()!;
  const x0 = Math.max(0, Math.min(...bs.map((b) => b.x)) - pad), y0 = Math.max(0, Math.min(...bs.map((b) => b.y)) - pad);
  const x1 = Math.min(vw.width, Math.max(...bs.map((b) => b.x + b.width)) + pad);
  const y1 = Math.min(vw.height, Math.max(...bs.map((b) => b.y + b.height)) + pad);
  await page.evaluate((s) => document.querySelectorAll<HTMLElement>(s).forEach((e) => { e.style.visibility = "hidden"; }), OVER);
  await page.screenshot({ path: path.join(SHOTS, `${name}.png`), clip: { x: x0, y: y0, width: x1 - x0, height: y1 - y0 } });
  await page.evaluate((s) => document.querySelectorAll<HTMLElement>(s).forEach((e) => { e.style.visibility = ""; }), OVER);
}

/** The whole plate (its shapes) and the marker on it. */
async function plateClip(page: Page, name: string): Promise<void> {
  const fid = (await state(page)).panel.featureId as string;
  const dims = (await page.getByTestId("dims").count()) ? [page.getByTestId("dims")] : [];
  await clip(page, name, [...(await page.locator("[data-shape]").all()), page.locator(`[data-marker="${fid}"]`), ...dims]);
}

/** Examples › Plate, click the face between the holes, A: the panel open (on Manufacture). */
async function plateWithMarker(page: Page): Promise<void> {
  await openStudio(page);
  await coreReady(page);
  await loadExample(page, "plate");
  await clickAt(page, 60, 40);
  await expect.poll(async () => (await state(page)).sel?.kind).toBe("profile");
  await page.keyboard.press("a");
  await idle(page);
  await expect(page.locator("[data-marker-black]")).toBeVisible();
  await expect(page.getByTestId("extrude-panel")).toBeVisible();
}

test("1 · the plate: Single, Grid, ChArUco; then Trim Profile and Marker", async ({ page }) => {
  await plateWithMarker(page);
  const seg = (p: string, v: string) => page.locator(`[data-path="${p}"] [data-value="${v}"]`);
  await panelTab(page, "marker");
  for (const type of ["grid", "charuco", "single"]) {
    await seg("marker.type", type).click();
    await idle(page);
    expect((await state(page)).feature.marker.type).toBe(type);
    await plateClip(page, `type-${type}`);
  }
  await panelTab(page, "make");
  for (const trim of ["profile", "marker"]) {
    await page.locator(`[data-row="trim"] .kit-seg-btn[data-value="${trim}"]`).click();
    await idle(page);
    expect((await state(page)).feature.trim).toBe(trim);
    await plateClip(page, `trim-${trim}`);
  }
  facts.tabs = await page.locator('[data-testid="extrude-panel"] [role=tab]').allTextContents();
});

test("2 · heights on the model: the 3D view, the white and black arrows with their value boxes (3D print preset)", async ({ page }) => {
  await openStudio(page);
  await coreReady(page);
  await loadExample(page, "custom-placement");
  await idle(page);
  // the tile's panel, then the first built-in 3D print preset on it (a preset is per marker)
  const o = await planOutline(page);
  await clickAt(page, o.cx, o.cy);
  await expect(page.getByTestId("extrude-panel")).toBeVisible();
  const modal = await openPresets(page);
  await modal.locator('[data-coll="builtin"]').click();
  await modal.getByTestId("presets-nav").locator('[data-chip="3D print"]').click();
  await modal.locator(".card[data-card]").first().click();
  await page.getByTestId("presets-select").click();
  await expect(modal).toHaveCount(0);
  await idle(page);
  await page.keyboard.press("3");
  await expect(page.getByTestId("view3d")).toBeVisible();
  const v3 = () => page.evaluate(() => JSON.parse(JSON.stringify((window as any).__aruco.view3d())));
  await expect.poll(async () => Object.keys((await v3())?.solids ?? {}).length).toBeGreaterThan(0);
  // zoom in at the tile (the wheel zooms at the cursor)
  const at = await page.evaluate(([x, y]) => (window as any).__aruco.project3d(x, y, 0), [o.cx, o.cy]);
  await page.mouse.move(at[0], at[1]);
  for (let i = 0; i < 5; i++) { await page.mouse.wheel(0, -200); await page.waitForTimeout(30); }
  await expect.poll(async () => (await v3()).arrows.map((a: any) => a.key).sort()).toEqual(["black_mm", "white_mm"]);
  await expect(page.locator('[data-testid="v3-box"]')).toHaveCount(2);
  await page.waitForTimeout(400);
  const s = await state(page);
  const arrows = (await v3()).arrows;
  facts.heights = { preset: s.feature.preset.name, extrude: s.plan.extrude, arrows: arrows.map((a: any) => ({ key: a.key, value: a.value, driven: a.driven })) };
  await page.mouse.move(2, 2);
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(SHOTS, "heights-3d.png") });
  // the tile and its two arrows, close up: framed on the tile's corners (bottom and top face) and the value boxes
  const W = s.plan.extrude.white_mm as number;
  const corners = await page.evaluate(([cx, cy, w, h, z]) => [-1, 1].flatMap((sx) => [-1, 1].flatMap((sy) => [0, z].map((zz) =>
    (window as any).__aruco.project3d(cx + (sx * w) / 2, cy + (sy * h) / 2, zz)))), [o.cx, o.cy, o.w, o.h, W]);
  const boxes = [page.locator('[data-testid="v3-box"]').first(), page.locator('[data-testid="v3-box"]').last()];
  await clip(page, "heights-driven", boxes, 36, corners);
  // override one: the black typed, the white still driven from the preset
  const input = page.locator('[data-testid="v3-box"][data-key="black_mm"] input');
  await input.click();
  await page.keyboard.press("Control+a");
  await page.keyboard.type("1.2");
  await page.keyboard.press("Enter");
  await idle(page);
  const s2 = await state(page);
  expect(s2.plan.extrude).toMatchObject({ white_mm: W, black_mm: 1.2 });
  await expect(page.locator('[data-testid="v3-box"][data-key="black_mm"]')).toHaveAttribute("data-driven", "false");
  await expect(page.locator('[data-testid="v3-box"][data-key="white_mm"]')).toHaveAttribute("data-driven", "true");
  facts.heights_set = { extrude: s2.plan.extrude };
  await page.waitForTimeout(300);
  await clip(page, "heights-set", boxes, 36, corners);
});

test("3 · the marker maker (video): typed rectangles, D, a window round them, A on all, Ctrl+C / Ctrl+V", async ({ browser }) => {
  test.setTimeout(240_000);
  const ctx = await browser.newContext({ baseURL: test.info().project.use.baseURL, viewport: { width: 1280, height: 800 },
    recordVideo: { dir: path.join(SRC, "tmp-video"), size: { width: 1280, height: 800 } } });
  const page = await ctx.newPage();
  const t0 = Date.now();
  const marks: Record<string, number> = {};
  const mark = (k: string) => { marks[k] = +((Date.now() - t0) / 1000).toFixed(2); };
  // WHY a drawn cursor: a headless recording has none (as hero.spec.ts)
  await page.addInitScript(() => {
    addEventListener("DOMContentLoaded", () => {
      const dot = document.createElement("div");
      dot.style.cssText = "position:fixed;z-index:99999;width:18px;height:18px;margin:-3px 0 0 -3px;pointer-events:none;left:-40px;top:-40px;"
        + "background:no-repeat url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpath d='M2 1l11 6-5 1.4 3 5-2 1.1-3-5L2 13z' fill='%23111' stroke='%23fff' stroke-width='1'/%3E%3C/svg%3E\");";
      document.body.appendChild(dot);
      addEventListener("mousemove", (e) => { dot.style.left = `${e.clientX}px`; dot.style.top = `${e.clientY}px`; }, true);
      addEventListener("pointermove", (e) => { dot.style.left = `${e.clientX}px`; dot.style.top = `${e.clientY}px`; }, true);
    });
  });
  const pause = (ms = 350) => page.waitForTimeout(ms);
  const glideTo = async (x: number, y: number, steps = 12) => { const [cx, cy] = await toClient(page, x, y); await page.mouse.move(cx, cy, { steps }); };
  const rightDrag = async (from: [number, number], to: [number, number]) => {
    await glideTo(...from);
    await page.mouse.down({ button: "right" });
    const [ax, ay] = await toClient(page, ...from), [bx, by] = await toClient(page, ...to);
    for (let i = 1; i <= 16; i++) { await page.mouse.move(ax + ((bx - ax) * i) / 16, ay + ((by - ay) * i) / 16); await page.waitForTimeout(25); }
    await pause(400);
    await page.mouse.up({ button: "right" });
  };

  await openStudio(page);
  await coreReady(page);
  await openMenu(page, "file");
  await page.getByTestId("cmd-new").click();
  await pause(300);
  mark("start");
  // four 26 x 20 rectangles, typed into the value boxes while drawing; the second one 4 mm out of line
  const corners: [number, number][] = [[-64, 4], [-36, 4], [-64, -22], [-32, -22]];
  for (const [x, y] of corners) {
    await page.keyboard.press("r");
    await glideTo(x, y, 8);
    const [ax, ay] = await toClient(page, x, y);
    await page.mouse.click(ax, ay);
    await glideTo(x + 22, y + 17, 10);
    await page.keyboard.type("26", { delay: 70 });
    await page.keyboard.press("Tab");
    await page.keyboard.type("20", { delay: 70 });
    await pause(250);
    if (x === -64 && y === 4) { await calmShot(page, "maker-value-boxes"); }
    await page.keyboard.press("Enter");
    await pause(150);
  }
  mark("drawn");
  // D: the second one's right edge 6 from the Y axis (it moves into line with the one below)
  await page.keyboard.press("d");
  await glideTo(0, 34, 10);
  const [yx, yy] = await toClient(page, 0, 34);
  await page.mouse.click(yx, yy);
  await glideTo(-10, 14, 8);
  await dragWorld(page, [-10, 14], [-8, 31], 10, 20);
  const sdim = page.getByTestId("sdim-input");
  await expect(sdim).toBeVisible();
  await expect(sdim).toHaveValue("10");
  await sdim.press("Control+a");
  await page.keyboard.type("6", { delay: 120 });
  await pause(250);
  await sdim.press("Enter");
  await page.keyboard.press("Escape");
  await idle(page);
  let s = await state(page);
  expect(s.doc.shapes).toHaveLength(4);
  expect(s.doc.shapes[1]).toMatchObject({ cx: -19, w: 26, h: 20 });
  mark("dimmed");
  await pause(600);
  await calmShot(page, "maker-dims");
  // a right-drag window round all four, A on all
  await rightDrag([-70, 30], [-1, -28]);
  expect((await state(page)).selection).toHaveLength(4);
  mark("selected");
  await pause(400);
  await page.keyboard.press("a");
  await idle(page);
  await expect(page.getByTestId("extrude-panel")).toBeVisible();
  s = await state(page);
  expect(s.doc.features).toHaveLength(4);
  mark("extruded");
  await pause(900);
  await page.getByTestId("panel-ok").click();
  await idle(page);
  // copy all four, paste them to the right
  await rightDrag([-70, 30], [-1, -28]);
  await page.keyboard.press("Control+c");
  await glideTo(38, 1, 14);
  await page.keyboard.press("Control+v");
  await idle(page);
  s = await state(page);
  expect(s.doc.features).toHaveLength(8);
  const ids = s.doc.features.map((f: any) => f.marker.first_id);
  expect(new Set(ids).size, "eight markers, eight ids").toBe(8);
  mark("pasted");
  await page.mouse.move(2, 2, { steps: 6 });
  await pause(1500);
  mark("end");
  facts.canvas = { features: s.doc.features.length, ids, dims: s.doc.dims.length };
  await page.screenshot({ path: path.join(SHOTS, "maker-end.png") });
  const video = page.video()!;
  await ctx.close();
  copyFileSync(await video.path(), path.join(SRC, "canvas.webm"));
  writeFileSync(path.join(SRC, "canvas.marks.json"), JSON.stringify(marks, null, 2));
});

async function calmShot(page: Page, name: string): Promise<void> {
  await page.screenshot({ path: path.join(SHOTS, `${name}.png`) });
}
