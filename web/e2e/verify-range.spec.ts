// Verify's range strip (V4 "Range strip", Zach 2026-10-21) on the REAL core:
// two markers (the plate's single, a grid beside it), the Verify button,
// the camera picked from the library by search, every marker's band on one
// shared axis, then a required distance batch-set on both: one PASS, one
// FAIL with its fix. Each check measures: the bands' pixels against the
// axis (getBoundingClientRect), the probe's document, the slices sent, and
// the browser's ranges against a CPython on the OpenCV each range names
// (found by aruco_studio/opencv_choice.py: for the browser's 4.11,
// .venv-cv411, tools/requirements-browser-opencv.txt) byte for byte. Then
// the cache keyed on what the camera sees (core scene_keys): a moved and
// turned marker keeps its range, no slice sent; its size, id or label
// measure it again, and the other marker keeps its own.
// Screenshots go to E2E_SHOTS (default test-results/shots).
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";
import { clickAt, CORE, coreReady, dragWorld, idle, loadExample, openStudio, panelTab, state, toClient } from "./helpers";

const SHOTS = process.env.E2E_SHOTS ?? "test-results/shots";
const here = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(here, "..", "..");
const PY = [path.join(ROOT, ".venv", "bin", "python"), path.join(ROOT, ".venv", "Scripts", "python.exe")].find((p) => fs.existsSync(p));

test.describe.configure({ mode: "serial" });

test.describe(`Verify · range strip (${CORE} core)`, () => {
  test.skip(CORE === "mock", "the mock core has no reading range");

  let page: Page;
  let single = "", grid = "";
  const timing: Record<string, number> = {};

  const col = (fid: string) => page.locator(`[data-testid="range-col"][data-feature="${fid}"]`);
  const num = async (fid: string, k: "near" | "far") => Number(await col(fid).getAttribute(`data-${k}`));
  /** every column measured, on this camera */
  const allDone = async (camera: string, timeout = 300_000) => {
    await expect.poll(async () => page.locator('[data-testid="range-col"]').evaluateAll(
      (els, cam) => els.every((e) => e.getAttribute("data-state") === "done" && e.getAttribute("data-camera") === cam), camera),
    { timeout, intervals: [500] }).toBe(true);
  };

  test.beforeAll(async ({ browser }) => {
    test.setTimeout(180_000);
    page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
    await openStudio(page);
    // the dialog opens on the camera this viewer last picked: the C920, so picking the D435 is a change
    await page.evaluate(() => { localStorage.setItem("aruco-web.verify.rangeCamera", JSON.stringify({ id: "c920" })); localStorage.removeItem("arucoStudio.verify.ranges"); });
    await coreReady(page);
    await loadExample(page, "plate");
    await clickAt(page, 60, 40);
    await expect.poll(async () => (await state(page)).sel?.kind).toBe("profile");
    await page.keyboard.press("a");
    await idle(page);
    single = (await state(page)).panel.featureId;
    await page.getByTestId("panel-ok").click();
    await idle(page);
    const [cx, cy] = await toClient(page, 60, 40);
    await page.mouse.move(cx, cy);
    await page.mouse.wheel(0, 300);
    await expect.poll(async () => (await toClient(page, 144, 40))[0]).toBeLessThan(1200);
    await page.keyboard.press("r");
    await dragWorld(page, [124, 10], [164, 40]);
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
  });

  test.afterAll(async () => {
    console.log(`verify-range timings (ms): ${JSON.stringify(timing)}`);
    await page.close();
  });

  test("a · Verify opens on the strip; the D435 is picked from the library by search; every marker gets a band on one axis", async () => {
    test.setTimeout(420_000);
    const t0 = Date.now();
    await page.getByTestId("act-verify").click();
    await expect(page.getByTestId("range-view")).toBeVisible();
    await expect(page.getByTestId("camera-chip")).toHaveAttribute("data-camera", "c920");
    // the library: search narrows it, a click picks
    await page.getByTestId("camera-chip").click();
    await expect(page.getByTestId("camera-picker")).toBeVisible();
    const rows = page.getByTestId("camera-row");
    await expect(rows).toHaveCount(12);
    await page.getByTestId("camera-search").fill("d435");
    await expect(rows).toHaveCount(1);
    await expect(rows.first()).toHaveAttribute("data-camera", "d435");
    await expect(rows.first()).toContainText("1920×1080");
    await expect(rows.first().locator(".vr-src a").first()).toHaveAttribute("href", /realsenseai\.com/);
    await page.getByTestId("camera-search").fill("realsense");
    await expect(rows).toHaveCount(4);
    await page.screenshot({ path: path.join(SHOTS, "verify-range-camera-picker.png") });
    await page.locator('[data-testid="camera-row"][data-camera="d435"]').click();
    await expect(page.getByTestId("camera-picker")).toHaveCount(0);
    await expect(page.getByTestId("camera-chip")).toHaveAttribute("data-camera", "d435");
    await expect(page.getByTestId("camera-chip")).toContainText("RealSense D435");
    // the first marker shows its progress while it is measured
    await expect(page.getByTestId("range-progress").first()).toBeVisible({ timeout: 60_000 });
    await allDone("d435");
    timing.two_markers_from_open = Date.now() - t0;
    expect(await page.evaluate(() => JSON.parse(localStorage.getItem("aruco-web.verify.rangeCamera")!))).toEqual({ id: "d435" });
    for (const fid of [single, grid]) {
      const near = await num(fid, "near"), far = await num(fid, "far");
      expect(near).toBeGreaterThan(10);
      expect(far).toBeGreaterThan(near);
      await expect(col(fid).getByTestId("range-num")).toContainText("–");
      // the band's pixels: its ends where the shared log axis puts near and far
      const band = col(fid).getByTestId("range-band");
      const [lo, hi, x0, x1] = await Promise.all(["data-lo", "data-hi", "data-x0", "data-x1"].map(async (a) => Number(await band.getAttribute(a))));
      const svg = (await band.boundingBox())!;
      const bar = (await col(fid).getByTestId("range-bar").boundingBox())!;
      const X = (mm: number) => svg.x + x0 + (Math.log(mm / lo) / Math.log(hi / lo)) * (x1 - x0);
      // the bar is drawn with round caps 3 px past each end
      expect(Math.abs(bar.x + 3 - X(near))).toBeLessThanOrEqual(1.5);
      expect(Math.abs(bar.x + bar.width - 3 - X(far))).toBeLessThanOrEqual(1.5);
    }
    // ONE axis: both bands drawn on the same lo..hi
    const axes = await page.getByTestId("range-band").evaluateAll((els) => els.map((e) => `${e.getAttribute("data-lo")}..${e.getAttribute("data-hi")}`));
    expect(new Set(axes).size).toBe(1);
    // one OpenCV: the strip names the one the choice names (the newest this browser loads), every band is it, its key says so
    const wanted = await page.getByTestId("verify-opencv").getAttribute("data-wanted");
    await expect(page.getByTestId("range-foot")).toContainText(`OpenCV ${wanted} reading the marker as planned, in this browser`);
    for (const fid of [single, grid]) {
      await expect(col(fid)).toHaveAttribute("data-opencv", wanted!);
      expect(JSON.parse((await col(fid).getAttribute("data-key"))!)[4]).toBe(wanted);
    }
  });

  test("b · a required distance set on both markers at once: one PASS, one FAIL with its fix", async () => {
    test.setTimeout(120_000);
    const [fs1, fg] = [await num(single, "far"), await num(grid, "far")];
    const [farMore, farLess] = fs1 > fg ? [single, grid] : [grid, single];
    const between = Math.round(Math.sqrt(fs1 * fg));      // reached by one, not the other
    const from = Math.ceil(Math.max(await num(single, "near"), await num(grid, "near")) + 10);
    // select both: a click, then a Shift-click (the batch pattern)
    await col(single).click();
    await col(grid).click({ modifiers: ["Shift"] });
    await expect(page.getByTestId("range-req-bar")).toHaveAttribute("data-selected", "2");
    await expect(col(single)).toHaveAttribute("data-selected", "1");
    const type = async (p: string, v: number) => {
      const i = page.locator(`input[data-path="${p}"]`);
      await i.fill(String(v));
      await i.press("Enter");
    };
    await type("verify.min_mm", from);
    await type("verify.max_mm", between);
    await expect(col(farMore)).toHaveAttribute("data-verdict", "pass", { timeout: 30_000 });
    await expect(col(farLess)).toHaveAttribute("data-verdict", "fail", { timeout: 30_000 });
    await expect(col(farMore).getByTestId("range-verdict")).toContainText("PASS");
    await expect(col(farLess).getByTestId("range-verdict")).toContainText("FAIL");
    await expect(col(farLess).getByTestId("range-hint").first()).toContainText(/Short by .*marker would read to/);
    await expect(page.getByTestId("range-status")).toHaveText("1 pass · 1 fail");
    // the document holds it, on both features (one batch edit)
    const doc = (await state(page)).doc;
    for (const f of doc.features) expect(f.verify).toEqual({ min_mm: from, max_mm: between });
    // the requirement is drawn on each axis, from `from` to `between`
    for (const fid of [single, grid]) {
      const band = col(fid).getByTestId("range-band");
      const [lo, hi, x0, x1] = await Promise.all(["data-lo", "data-hi", "data-x0", "data-x1"].map(async (a) => Number(await band.getAttribute(a))));
      const svg = (await band.boundingBox())!;
      const req = (await col(fid).getByTestId("range-req").boundingBox())!;
      const X = (mm: number) => svg.x + x0 + (Math.log(mm / lo) / Math.log(hi / lo)) * (x1 - x0);
      expect(Math.abs(req.x - X(from))).toBeLessThanOrEqual(1.5);
      expect(Math.abs(req.x + req.width - X(between))).toBeLessThanOrEqual(1.5);
    }
    // a third, mixed state: one marker's max typed alone shows Mixed for both
    await col(single).click();
    await type("verify.max_mm", between + 100);
    await col(grid).click({ modifiers: ["Shift"] });
    await expect(page.locator('[data-mixed-for="verify"]')).toBeVisible();
    await expect(page.locator('input[data-path="verify.max_mm"]')).toHaveValue("");
    await type("verify.max_mm", between);
    await expect(page.locator('[data-mixed-for="verify"]')).toHaveCount(0);
    await page.mouse.move(5, 700);
    await page.screenshot({ path: path.join(SHOTS, "verify-range-strip.png") });
  });

  test("c · reopened, every range is there at once: no slice sent", async () => {
    test.setTimeout(60_000);
    const steps = await page.evaluate(() => (window as any).__arucoRange.steps());
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("verify-dialog")).toHaveCount(0);
    const t0 = Date.now();
    await page.getByTestId("act-verify").click();
    await allDone("d435", 5_000);
    timing.reopen_all_done = Date.now() - t0;
    expect(await page.evaluate(() => (window as any).__arucoRange.steps())).toBe(steps);
    await expect(col(single)).toHaveAttribute("data-verdict", /pass|fail/);
  });

  test("d · a band's far end opens the bench on that camera at that distance", async () => {
    test.setTimeout(120_000);
    const far = await num(single, "far");
    await col(single).locator('circle[data-end="far"]').click();
    await expect(page.getByTestId("verify-image")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("bench-note")).toContainText("RealSense D435 at");
    await expect(page.getByTestId("bench-note")).toContainText(`${Math.round(far)} mm away`);
    await page.getByTestId("bench-camera").click();
    await expect(page.getByTestId("bench-note")).toContainText("The bench:");
    // and back to the strip: still measured
    await page.locator('[data-testid="verify-view"] [data-value="range"]').click();
    await allDone("d435", 5_000);
  });

  test("f · while a range runs the page never stalls, and a plan waits one slice at most", async () => {
    test.setTimeout(240_000);
    // a camera never measured here: fresh work in the core's one worker
    await page.getByTestId("camera-chip").click();
    await page.getByTestId("camera-search").fill("d455");
    await page.locator('[data-testid="camera-row"][data-camera="d455"]').click();
    await expect(page.getByTestId("range-progress").first()).toBeVisible({ timeout: 60_000 });
    const req = await page.evaluate(() => (window as any).__arucoRange.finished()[0].req);
    const got = await page.evaluate(async (r) => {
      const long: number[] = [];
      const obs = new PerformanceObserver((l) => { for (const e of l.getEntries()) long.push(e.duration); });
      obs.observe({ type: "longtask", buffered: false });
      const plans: number[] = [];
      for (let k = 0; k < 4; k++) {
        const t0 = performance.now();
        await (window as any).__aruco.plan(r);
        plans.push(performance.now() - t0);
        await new Promise((res) => setTimeout(res, 400));
      }
      obs.disconnect();
      const running = [...document.querySelectorAll('[data-testid="range-col"]')].some((e) => e.getAttribute("data-state") === "running");
      return { plans, long, running };
    }, req);
    console.log(`plans during a range (ms): ${got.plans.map(Math.round).join(", ")}; main-thread long tasks: ${got.long.map(Math.round).join(", ") || "none"}`);
    expect(got.running, "the range was still running throughout").toBe(true);
    // a slice is 250 ms; one view near the camera can run past it (the worst seen: ~650 ms)
    for (const ms of got.plans) expect(ms).toBeLessThan(1500);
    for (const ms of got.long) expect(ms).toBeLessThan(250);
    timing.plan_during_range_worst = Math.round(Math.max(...got.plans));
    await allDone("d455");
    // and back on the D435: kept, at once
    await page.getByTestId("camera-chip").click();
    await page.locator('[data-testid="camera-row"][data-camera="d435"]').click();
    await allDone("d435", 5_000);
  });

  test("e · the browser's ranges are a CPython's on the same OpenCV, byte for byte", async () => {
    test.skip(!PY, "no .venv here: the CPython oracle cannot run");
    test.setTimeout(300_000);
    const done = await page.evaluate(() => (window as any).__arucoRange.finished()) as { key: string; req: any; camera: any; result: any }[];
    const mine = done.filter((d) => d.result.camera.id === "d435");
    expect(mine.length).toBeGreaterThanOrEqual(2);
    for (const d of mine) {
      const { req, camera } = d;
      const opencv = JSON.parse(d.key)[4];
      expect(d.result.opencv, "the range ran on the OpenCV its key names").toBe(opencv);
      // the same call in the CPython that has that OpenCV (opencv_choice finds it: this checkout's venvs, the main one's)
      const code = ["import json, sys", "from aruco_studio import opencv_choice as OC", "a = json.load(sys.stdin)",
        "c = OC.choose(a['opencv'])",
        "sys.stdout.write(json.dumps(OC.call(c, 'aruco_studio.web_verify', 'reading_range', a['req'], a['camera']), sort_keys=True))"].join("\n");
      const r = spawnSync(PY!, ["-c", code], { cwd: ROOT, input: JSON.stringify({ req, camera, opencv }), encoding: "utf8",
        env: { ...process.env, PYTHONPATH: ROOT, PYTHONDONTWRITEBYTECODE: "1" }, maxBuffer: 1 << 26 });
      test.skip(r.status !== 0 && /not installed here/.test(r.stderr), `OpenCV ${opencv} is not installed here (tools/requirements-browser-opencv.txt)`);
      expect(r.status, r.stderr).toBe(0);
      const sorted = (o: unknown): unknown => Array.isArray(o) ? o.map(sorted)
        : o && typeof o === "object" ? Object.fromEntries(Object.keys(o as object).sort().map((k) => [k, sorted((o as any)[k])])) : o;
      expect(JSON.stringify(sorted(JSON.parse(r.stdout)))).toBe(JSON.stringify(sorted(d.result)));
    }
  });

  test("g · a move and a turn keep each marker's range (no slice sent); a size, an id or a label measures it again", async () => {
    test.setTimeout(420_000);
    const verifyOpen = async () => {
      await page.getByTestId("act-verify").click();
      await expect(page.getByTestId("range-view")).toBeVisible();
    };
    const close = async () => {
      await page.keyboard.press("Escape");
      await expect(page.getByTestId("verify-dialog")).toHaveCount(0);
    };
    const steps = () => page.evaluate(() => (window as any).__arucoRange.steps()) as Promise<number>;
    const shape = async () => {
      const s = await state(page);
      return s.doc.shapes.find((x: any) => x.id === s.doc.features.find((f: any) => f.id === grid).profile.outer);
    };
    const panel = async () => {
      await page.locator(`[data-marker="${grid}"]`).click();
      await expect(page.getByTestId("extrude-panel")).toBeVisible();
      await idle(page);
    };
    const type = async (path: string, v: string) => {
      const i = page.locator(`input[data-path="${path}"]`);
      await i.fill(v);
      await i.press("Enter");
      await idle(page);
    };
    await allDone("d435");
    const [keyS, keyG, farG] = [await col(single).getAttribute("data-key"), await col(grid).getAttribute("data-key"), await num(grid, "far")];
    await close();
    // turn the grid's rectangle 30° (its panel's Rotation row) and move it 10 mm right (Shift+Arrow nudges the selection)
    const before = await shape();
    await panel();
    await panelTab(page, "marker");
    await type("profile.angle_deg", "30");
    await page.getByTestId("panel-ok").click();
    await idle(page);
    await page.keyboard.press("Shift+ArrowRight");
    await idle(page);
    const after = await shape();
    expect(after.angle_deg).toBe(30);
    expect(after.cx).toBeCloseTo(before.cx + 10, 6);
    // reopened: every range is there, from the cache: no slice sent, the same scene keys
    const s0 = await steps();
    await verifyOpen();
    await allDone("d435", 15_000);
    expect(await steps(), "no range was measured again").toBe(s0);
    await expect(col(grid)).toHaveAttribute("data-key", keyG!);
    await expect(col(single)).toHaveAttribute("data-key", keyS!);
    expect(await num(grid, "far")).toBe(farG);
    await page.screenshot({ path: path.join(SHOTS, "verify-range-moved-turned-cached.png") });
    await close();
    // each edit that changes what the camera reads measures the grid again, and only the grid
    const edits: [string, () => Promise<void>][] = [
      ["size", async () => { await panelTab(page, "marker"); await type("marker.marker_mm", "9"); }],
      ["id", async () => { await panelTab(page, "marker"); await type("marker.first_id", "31"); }],
      ["label", async () => { await panelTab(page, "label"); await page.locator('[data-path="label.on"]').click(); await idle(page); }],
    ];
    const seen = new Set([keyG]);
    for (const [what, edit] of edits) {
      await panel();
      await edit();
      await page.getByTestId("panel-ok").click();
      await idle(page);
      const s1 = await steps();
      await verifyOpen();
      await expect.poll(async () => col(grid).getAttribute("data-key"), { message: `${what}: a new scene` }).not.toBe([...seen].pop());
      const k = (await col(grid).getAttribute("data-key"))!;
      expect(seen.has(k), `${what}: never an earlier scene's range`).toBe(false);
      seen.add(k);
      await allDone("d435");
      expect(await steps(), `${what}: measured again`).toBeGreaterThan(s1);
      await expect(col(single)).toHaveAttribute("data-key", keyS!);
      await close();
    }
  });
});
