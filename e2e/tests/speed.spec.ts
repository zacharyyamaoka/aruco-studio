// Lane speed (audit B1): live re-placement on the forearm feels instant.
// A drag asks the server for the top views only (the light preview): in 2D
// that is all the view draws; in 3D each tag stands as a flat slab of its
// top view while the pointer is down, and the release brings the meshes
// (one request with mesh=1). The round trips are recorded in
// e2e/.tmp/speed_numbers.json; the bars are generous (a loaded machine).
import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { ROOT, centre, idle, openExample, probe, readFile, screenOf, shot, SCREENS } from "./helpers";

const NUMBERS = path.join(ROOT, "e2e", ".tmp", "speed_numbers.json");
const DRAG_MS = 400;          // the preview's round trip, median (about 100 ms on Zach's box)

function record(key: string, v: unknown) {
  let all: Record<string, unknown> = {};
  try { all = JSON.parse(fs.readFileSync(NUMBERS, "utf-8")); } catch { /* first */ }
  all[key] = v;
  fs.mkdirSync(path.dirname(NUMBERS), { recursive: true });
  fs.writeFileSync(NUMBERS, JSON.stringify(all, null, 1));
}

function median(xs: number[]): number {
  const s = [...xs].sort((a, b) => a - b);
  return s.length ? s[Math.floor((s.length - 1) / 2)] : NaN;
}

/** Every /api/design/preview request from now on: its query and when it was sent. */
function watchPreviews(page: Page) {
  const seen: { url: string; t: number }[] = [];
  page.on("request", (r) => { if (r.url().includes("/api/design/preview")) seen.push({ url: r.url(), t: Date.now() }); });
  return seen;
}

async function roundTrips(page: Page, since: number): Promise<number[]> {
  return page.evaluate((n) => performance.getEntriesByType("resource")
    .filter((e) => e.name.includes("/api/design/preview")).slice(n).map((e) => Math.round(e.duration)), since);
}

async function previewCount(page: Page): Promise<number> {
  return page.evaluate(() => performance.getEntriesByType("resource").filter((e) => e.name.includes("/api/design/preview")).length);
}

test("speed: a 2D handle drag on the forearm previews its four tags in well under the bar", async ({ page }) => {
  const file = await openExample(page, "e2e-speed2d", "forearm.arucostudio.json");
  await page.keyboard.press("f");
  await idle(page);
  await expect(page.locator("g[data-tag]")).toHaveCount(4);
  await page.mouse.click(...(await screenOf(page, 0, 0)));               // the outline (its top has no tag)
  await expect.poll(async () => (await probe(page)).shapeSel).toEqual(["outline"]);
  const seen = watchPreviews(page);
  const n0 = await previewCount(page);
  const zoom = (await probe(page)).zoom;
  const e = await centre(page, '[data-handle="e"]');
  await page.mouse.move(e[0], e[1]);
  await page.mouse.down();
  for (let i = 1; i <= 12; i++) {
    await page.mouse.move(e[0] + (10 * zoom * i) / 12, e[1]);
    await page.waitForTimeout(60);
  }
  await page.waitForTimeout(300);
  await page.mouse.up();
  await idle(page);
  const trips = await roundTrips(page, n0);
  record("speed.2d", { round_trips_ms: trips, median_ms: median(trips), requests: seen.map((s) => s.url.split("?")[1]) });
  console.log(`speed 2D: preview round trips (ms) ${trips.join(", ")}; median ${median(trips)}`);
  expect(trips.length).toBeGreaterThan(2);
  expect(seen.every((s) => !s.url.includes("mesh=1"))).toBe(true);
  expect(median(trips)).toBeLessThan(DRAG_MS);
  const w = readFile(file).sketches[0].shapes[0].rect[0];
  expect(w).toBeGreaterThan(120);
  await expect(page.locator("g[data-tag]")).toHaveCount(4);
  await shot(page, "speed_2d_after_drag");
});

test("speed: a 3D arrow drag draws the light slabs, the release the meshes", async ({ page }) => {
  const file = await openExample(page, "e2e-speed3d", "forearm.arucostudio.json");
  await page.keyboard.press("f");
  await idle(page);
  await page.mouse.click(...(await screenOf(page, 0, 0)));
  await expect.poll(async () => (await probe(page)).shapeSel).toEqual(["outline"]);
  await page.getByTestId("view-3d").click();
  await idle(page);
  await page.waitForFunction(() => Object.values((window as any).__studio3d?.drawn || {}).filter((v) => v === "mesh").length === 4,
    null, { timeout: 15000 });
  const a = await page.evaluate(() => (window as any).__studio3d.arrow());
  expect(a).toBeTruthy();
  const h0 = readFile(file).features[0].height;
  const seen = watchPreviews(page);
  const n0 = await previewCount(page);
  await page.mouse.move(a[0], a[1]);
  await page.mouse.down();
  for (let i = 1; i <= 10; i++) {
    await page.mouse.move(a[0], a[1] - 6 * i);
    await page.waitForTimeout(60);
  }
  // the pointer is still down: four light slabs, no meshes asked
  await page.waitForFunction(() => {
    const d = (window as any).__studio3d?.drawn || {};
    return Object.keys(d).length === 4 && Object.values(d).every((v) => v === "light");
  }, null, { timeout: 10000 });
  const during = seen.length;
  expect(during).toBeGreaterThan(0);
  expect(seen.every((s) => !s.url.includes("mesh=1"))).toBe(true);
  await page.screenshot({ path: path.join(SCREENS, "speed_3d_light_drag.png") });
  const drag = await roundTrips(page, n0);
  const up = Date.now();
  await page.mouse.up();
  // the release: one request with the meshes, then four meshes on screen
  await page.waitForFunction(() => {
    const d = (window as any).__studio3d?.drawn || {};
    return Object.keys(d).length === 4 && Object.values(d).every((v) => v === "mesh");
  }, null, { timeout: 15000 });
  const meshed = Date.now() - up;
  await idle(page);
  const after = seen.slice(during);
  expect(after.filter((s) => s.url.includes("mesh=1")).length).toBe(1);
  const h = readFile(file).features[0].height;
  expect(h).toBeGreaterThan(h0);
  record("speed.3d", { drag_round_trips_ms: drag, drag_median_ms: median(drag), release_to_meshes_ms: meshed,
    requests: seen.map((s) => s.url.split("?")[1]) });
  console.log(`speed 3D: drag round trips (ms) ${drag.join(", ")}; release to meshes ${meshed} ms`);
  expect(median(drag)).toBeLessThan(DRAG_MS);
  await shot(page, "speed_3d_after_release");
});
