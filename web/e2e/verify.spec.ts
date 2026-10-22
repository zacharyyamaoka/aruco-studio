// Verify accuracy (web/src/verify): the simulated camera bench on the REAL
// core: OpenCV loads on the first call. One page for the file: the plate's
// marker (single) and a grid beside it, then the dialog's image, its ids,
// the Tilt drag, the angle sweep and the camera calculator. Each check
// measures: the image's data URL and natural size, the ids drawn, the
// calculator's numbers against core.readable and the pinhole formula. Then
// the one OpenCV (docs/peps/0003 decision 3): the choice lists only what
// this browser can load (the oracle: the Pyodide lock and the wheels the site
// serves), the newest by default, and every answer names the one that ran.
// Screenshots go to E2E_SHOTS (default test-results/shots).
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";
import { clickAt, CORE, coreReady, dragWorld, idle, loadExample, openStudio, panelTab, state, toClient } from "./helpers";

const SHOTS = process.env.E2E_SHOTS ?? "test-results/shots";
const WEB = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
/** what this browser can load, by version (cv2's three parts), newest first: the lock's opencv-python and the site's wheels */
const LOADABLE = (() => {
  const lock = JSON.parse(fs.readFileSync(path.join(WEB, "node_modules", "pyodide", "pyodide-lock.json"), "utf8"));
  const dir = path.join(WEB, "public", "opencv");
  const wheels = fs.existsSync(dir) ? fs.readdirSync(dir).filter((f) => f.endsWith(".whl")) : [];
  const vs = [lock.packages["opencv-python"]?.version, ...wheels.map((f) => f.split("-")[1])].filter(Boolean)
    .map((v: string) => v.split(".").slice(0, 3).join("."));
  const key = (v: string) => v.split(".").map(Number);
  return [...new Set(vs)].sort((a, b) => { const x = key(a), y = key(b); return y[0] - x[0] || y[1] - x[1] || y[2] - x[2]; });
})();
const NEWEST = LOADABLE[0];
const short = (v: string) => v.split(".").slice(0, 2).join(".");

test.describe.configure({ mode: "serial" });

test.describe(`Verify (${CORE} core)`, () => {
  test.skip(CORE === "mock", "the mock core has no verify / readable");

  let page: Page;
  let single = "", grid = "";
  let opened = 0;
  const timing: Record<string, number> = {};

  const image = () => page.getByTestId("verify-image");
  const src = () => image().getAttribute("src");
  /** no verify in flight in the dialog (the last view is drawn) */
  const settled = async () => {
    await expect(page.locator('.vf-frame[data-busy="0"]')).toHaveCount(1, { timeout: 60_000 });
  };
  const knob = (k: string) => page.locator(`input[data-knob="${k}"]`);
  /** a slider to `steps` steps above its minimum, by keyboard */
  const setKnob = async (k: string, steps: number) => {
    await knob(k).focus();
    await page.keyboard.press("Home");
    for (let i = 0; i < steps; i++) await page.keyboard.press("ArrowRight");
  };

  test.beforeAll(async ({ browser }) => {
    test.setTimeout(180_000);
    page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
    await openStudio(page);
    await coreReady(page);
    await loadExample(page, "plate");
    // the plate's face → A → OK: a single marker
    await clickAt(page, 60, 40);
    await expect.poll(async () => (await state(page)).sel?.kind).toBe("profile");
    await page.keyboard.press("a");
    await idle(page);
    single = (await state(page)).panel.featureId;
    await page.getByTestId("panel-ok").click();
    await idle(page);
    // a rectangle beside the plate → A → Grid → OK; the canvas has the whole
    // window since the Figma layout (no top bar), so the fit is closer: zoom
    // out at the plate's middle until the rectangle's spot is on screen
    const [cx, cy] = await toClient(page, 60, 40);
    await page.mouse.move(cx, cy);
    await page.mouse.wheel(0, 300);
    await expect.poll(async () => (await toClient(page, 144, 40))[0]).toBeLessThan(1200);
    const [x1] = await toClient(page, 144, 40);
    expect(x1, "the second rectangle is on screen").toBeLessThan(1270);
    await page.keyboard.press("r");
    await dragWorld(page, [124, 10], [144, 40]);
    await page.keyboard.press("a");
    await expect(page.getByTestId("extrude-panel")).toBeVisible();
    await panelTab(page, "marker");
    await page.locator('[data-path="marker.type"] [data-value="grid"]').click();
    await idle(page);
    grid = (await state(page)).panel.featureId;
    await page.getByTestId("panel-ok").click();
    await idle(page);
    const s = await state(page);
    expect(s.doc.features.map((f: any) => f.id)).toEqual([single, grid]);
    expect(s.plans[single]?.ids).toHaveLength(1);
    expect(s.plans[grid]?.ids.length).toBeGreaterThan(1);
  });

  test.afterAll(async () => {
    console.log(`verify timings (ms): ${JSON.stringify(timing)}`);
    await page.close();
  });

  test("a · opens on the plate's marker: a PNG of the view, and it reads the marker's id", async () => {
    test.setTimeout(120_000);
    opened = Date.now();
    await page.evaluate((id) => (window as any).__arucoVerify.open(id), single);
    await expect(page.getByTestId("verify-dialog")).toBeVisible();
    await expect(page.getByTestId("verify-dialog")).toContainText("Verify · Marker #");
    // OpenCV's first load says so while it is pending, and which one
    await expect(page.getByTestId("verify-loading")).toHaveText(new RegExp(`^Loading OpenCV ${short(NEWEST).replace(".", "\\.")} \\(\\d+ MB\\)…$`));
    await expect(image()).toBeVisible({ timeout: 60_000 });
    timing.first_verify_incl_opencv = Date.now() - opened;
    expect(await src()).toMatch(/^data:image\/png;base64,/);
    const w = await image().evaluate((e: HTMLImageElement) => e.naturalWidth);
    expect(w).toBeGreaterThan(100);
    const id = (await state(page)).plans[single].ids[0];
    await expect(page.locator(`[data-testid="verify-ids"] [data-id="${id}"]`)).toHaveAttribute("data-state", "found");
    await expect(page.getByTestId("verify-verdict")).toContainText(`Reads #${id}`);
    await expect(page.locator('[data-testid="verify-ids"] [data-state="missing"], [data-testid="verify-ids"] [data-state="wrong"]')).toHaveCount(0);
    // the one OpenCV: the newest this browser loads, chosen, loaded, and named by the answer itself
    await expect(page.getByTestId("verify-opencv")).toHaveAttribute("data-wanted", NEWEST);
    await expect(page.getByTestId("verify-opencv")).toHaveAttribute("data-loaded", NEWEST);
    await expect(page.getByTestId("verify-verdict")).toHaveAttribute("data-opencv", NEWEST);
    await expect(page.getByTestId("verify-opencv-badge")).toHaveText(`OpenCV ${short(NEWEST)}`);
    // one verify, OpenCV warm: Yaw 10° and back to the drawn image
    await settled();
    const before = await src();
    const t0 = Date.now();
    await setKnob("yaw_deg", 10);
    await expect.poll(src, { timeout: 30_000 }).not.toBe(before);
    await settled();
    timing.one_verify_warm = Date.now() - t0;
    await setKnob("yaw_deg", 0);
    await settled();
  });

  test("d · the sweep: one line per marker, and each says how far it reads", async () => {
    test.setTimeout(240_000);
    const legend = page.getByTestId("sweep-legend");
    await expect(legend).toHaveCount(2);
    await expect(page.locator('[data-testid="sweep-chart"] [data-series]')).toHaveCount(2);
    expect(await page.locator('[data-testid="sweep-chart"] [data-series]').evaluateAll((els) => els.map((e) => e.getAttribute("data-series")))).toEqual([single, grid]);
    for (const fid of [single, grid]) {
      const key = page.locator(`[data-testid="sweep-legend"][data-feature="${fid}"]`);
      await expect(key).toHaveText(/reads to \d+°$/, { timeout: 200_000 });
      const n = Number(await key.getAttribute("data-reads-to"));
      expect(n).toBeGreaterThanOrEqual(0);
      expect(n).toBeLessThanOrEqual(85);
    }
    timing.full_sweep_from_open = Date.now() - opened;
    // every point drawn: 18 tilts per line
    for (const fid of [single, grid]) await expect(page.locator(`[data-point^="${fid}@"]`)).toHaveCount(18);
    // a click on a point sets Tilt there
    await page.locator(`[data-point="${single}@40"]`).click();
    await expect(page.getByTestId("knob-tilt_deg")).toHaveText("40°");
    await expect(knob("tilt_deg")).toHaveValue("40");
    // hovering a column sets it too
    await page.locator('[data-testid="sweep-chart"] .vf-col[data-tilt="20"]').hover();
    await expect(knob("tilt_deg")).toHaveValue("20");
    await setKnob("tilt_deg", 0);
    await settled();
  });

  test("c · dragging Tilt from 0 to 60 re-renders while dragging, and changes the image", async () => {
    test.setTimeout(120_000);
    await expect(knob("tilt_deg")).toHaveValue("0");
    await settled();
    const at0 = await src();
    const n0 = Number(await image().getAttribute("data-renders"));
    const box = (await knob("tilt_deg").boundingBox())!;
    const y = box.y + box.height / 2;
    // the thumb travels the track less its own width (about 16 px)
    const xAt = (v: number) => box.x + 8 + ((box.width - 16) * v) / 85;
    await page.mouse.move(xAt(0), y);
    await page.mouse.down();
    for (let i = 1; i <= 24; i++) {
      await page.mouse.move(xAt((60 * i) / 24), y);
      await page.waitForTimeout(80);
    }
    await page.mouse.up();
    // land on exactly 60
    const v = Number(await knob("tilt_deg").inputValue());
    for (let i = 0; i < Math.abs(60 - v); i++) await page.keyboard.press(v < 60 ? "ArrowRight" : "ArrowLeft");
    await expect(page.getByTestId("knob-tilt_deg")).toHaveText("60°");
    await settled();
    const at60 = await src();
    expect(at60).toMatch(/^data:image\/png;base64,/);
    expect(at60).not.toBe(at0);
    const n1 = Number(await image().getAttribute("data-renders"));
    expect(n1 - n0, "renders during the drag, not only at its end").toBeGreaterThanOrEqual(3);
  });

  test("b · Occlusion 60 % on the grid: at least one id is missing, drawn red", async () => {
    test.setTimeout(120_000);
    // the picker: the grid
    await page.getByTestId("dd:verify.feature").click();
    await page.locator(`.kit-select-popup[data-for="verify.feature"] [data-value="${grid}"]`).click();
    await expect(page.getByTestId("verify-dialog")).toContainText("Verify · Grid");
    await setKnob("tilt_deg", 0);
    await setKnob("occlusion", 12);
    await expect(page.getByTestId("knob-occlusion")).toHaveText("60 %");
    await settled();
    const ids = (await state(page)).plans[grid].ids as number[];
    const shown = page.locator('[data-testid="verify-ids"] [data-id]');
    await expect(shown).toHaveCount(ids.length + (await page.locator('[data-testid="verify-ids"] [data-state="wrong"]').count()));
    const missing = page.locator('[data-testid="verify-ids"] [data-state="missing"]');
    // WHY a poll (the full e2e, 2026-10-21): settled() can see the frame idle before the
    // knob's 30 ms debounce has sent the occluded view; the page then showed all four missing
    await expect.poll(() => missing.count(), { timeout: 60_000 }).toBeGreaterThanOrEqual(1);
    const [colour, bad] = await missing.first().evaluate((e) => [getComputedStyle(e).color, getComputedStyle(e).getPropertyValue("--bad")]);
    const probe = await page.evaluate((c) => { const d = document.createElement("i"); d.style.color = c; document.body.appendChild(d); const v = getComputedStyle(d).color; d.remove(); return v; }, bad.trim());
    expect(colour).toBe(probe);
    await expect(page.getByTestId("verify-verdict")).toHaveAttribute("data-ok", "0");
    await setKnob("occlusion", 0);
    await settled();
  });

  test("e · the calculator: 300 mm / 1920 px / 70° matches core.readable; 10 m is poor", async () => {
    test.setTimeout(180_000);
    const fid = await page.locator('[data-path="verify.feature"]').getAttribute("data-value");
    const type = async (p: string, v: string) => {
      const i = page.locator(`input[data-path="verify.${p}"]`);
      await i.fill(v);
      await i.press("Enter");
    };
    await type("distance_mm", "300");
    await type("width_px", "1920");
    await type("hfov_deg", "70");
    const out = page.locator('.vf-out[data-job="current"][data-busy="0"]');
    await expect(out).toHaveCount(1, { timeout: 120_000 });
    const verdict = await page.getByTestId("calc-verdict").textContent();
    expect(["good", "marginal", "poor"]).toContain(verdict);
    const shown = parseFloat((await page.getByTestId("calc-ppc").textContent())!);
    const oracle = await page.evaluate((id) => (window as any).__arucoVerify.readable(id, { distance_mm: 300, width_px: 1920, hfov_deg: 70 }), fid);
    expect(Math.abs(shown - oracle.px_per_cell)).toBeLessThanOrEqual(0.1);
    expect(verdict).toBe(oracle.verdict);
    // and the pinhole: cell_mm × f / distance
    const cell = (await state(page)).plans[fid!].cell_mm;
    const f = 960 / Math.tan((35 * Math.PI) / 180);
    expect(Math.abs(shown - (cell * f) / 300)).toBeLessThanOrEqual(0.1);
    // remembered for this viewer
    expect(await page.evaluate(() => JSON.parse(localStorage.getItem("aruco-web.verify.camera")!))).toEqual({ distance_mm: 300, width_px: 1920, hfov_deg: 70 });
    // the answer names the OpenCV that measured it
    await expect(page.getByTestId("calc-text")).toHaveAttribute("data-opencv", NEWEST);
    await expect(page.getByTestId("calc-text")).toContainText(`· OpenCV ${short(NEWEST)}`);
    expect(oracle.opencv).toBe(NEWEST);
    await type("distance_mm", "10000");
    await expect(out).toHaveCount(1, { timeout: 120_000 });
    await expect(page.getByTestId("calc-verdict")).toHaveText("poor");
    await expect(page.locator('input[data-path="verify.distance_mm"]')).toHaveValue("10000");
  });

  test("shot · the dialog at 1280 × 800", async () => {
    test.setTimeout(120_000);
    await page.getByTestId("dd:verify.feature").click();
    await page.locator(`.kit-select-popup[data-for="verify.feature"] [data-value="${single}"]`).click();
    await page.locator('input[data-path="verify.distance_mm"]').fill("1500");
    await page.locator('input[data-path="verify.distance_mm"]').press("Enter");
    await setKnob("tilt_deg", 30);
    await settled();
    await expect(page.locator('.vf-out[data-job="current"][data-busy="0"]')).toHaveCount(1, { timeout: 120_000 });
    await page.mouse.move(5, 5);
    await page.screenshot({ path: path.join(SHOTS, "verify-dialog-1280x800.png") });
  });
});

test.describe(`Verify · one OpenCV (${CORE} core)`, () => {
  test.skip(CORE === "mock", "the mock core has no OpenCV");

  test("the choice lists only what this browser loads, newest first and chosen; a remembered one it cannot load falls back", async ({ page }) => {
    test.setTimeout(240_000);
    // a choice from a build this browser no longer lists (say an older site's)
    await page.addInitScript(() => { if (!sessionStorage.getItem("seeded")) { localStorage.setItem("aruco-web.verify.opencv", "3.4.0"); sessionStorage.setItem("seeded", "1"); } });
    await page.goto("/?example=label-placement");
    await expect.poll(async () => (await page.evaluate(() => (window as any).__aruco?.state().doc.name)) ?? null, { timeout: 60_000 })
      .toBe("Label placement test board");
    await coreReady(page);
    await page.evaluate(() => (window as any).__arucoVerify.open("lp-A1"));
    const pick = page.getByTestId("verify-opencv");
    await expect(pick).toHaveAttribute("data-wanted", NEWEST);
    await page.getByTestId("dd:verify.opencv").click();
    const listed = await page.locator('.kit-select-popup[data-for="verify.opencv"] [data-value]')
      .evaluateAll((els) => els.map((e) => e.getAttribute("data-value")));
    expect(listed, "only the builds this browser can load, newest first").toEqual(LOADABLE);
    await page.keyboard.press("Escape");
    // the bench, the sweep and the strip all run it, and say so
    await expect(page.getByTestId("verify-verdict")).toHaveAttribute("data-opencv", NEWEST, { timeout: 90_000 });
    await expect(pick).toHaveAttribute("data-loaded", NEWEST);
    await expect(page.getByTestId("sweep-head")).toContainText(`OpenCV ${short(NEWEST)}`);
    // every other build this browser lists: chosen, the worker starts again on it, its answers name it, and it is remembered
    for (const v of LOADABLE.slice(1)) {
      await page.getByTestId("dd:verify.opencv").click();
      await page.locator(`.kit-select-popup[data-for="verify.opencv"] [data-value="${v}"]`).click();
      await expect(pick).toHaveAttribute("data-wanted", v);
      await expect(page.getByTestId("verify-verdict")).toHaveAttribute("data-opencv", v, { timeout: 120_000 });
      await expect(pick).toHaveAttribute("data-loaded", v);
      expect(await page.evaluate(() => localStorage.getItem("aruco-web.verify.opencv"))).toBe(v);
    }
  });
});

