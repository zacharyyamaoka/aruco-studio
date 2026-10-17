// The speed spec's drags (e2e/tests/speed.spec.ts) against the SERVED
// Studio on 5360, with a different box length / height per run, so every
// step is a new plan (no cache hit), as a real drag is. Not part of
// tools/check.py: start the server first, then
//   npx playwright test --config verify/served.config.ts   (from e2e/)
// The numbers land in e2e/.tmp/verify_numbers.json. First run: 2026-10-17
// (docs/status/verify-2026-10-17.md, reports/verify_speed_2026-10-17.json).
import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { ROOT, centre, freshFile, idle, probe, readFile, screenOf } from "../tests/helpers";

const NUMBERS = path.join(__dirname, "..", ".tmp", "verify_numbers.json");
function record(key: string, v: unknown) {
  let all: Record<string, unknown> = {};
  try { all = JSON.parse(fs.readFileSync(NUMBERS, "utf-8")); } catch { /* first */ }
  all[key] = v;
  fs.writeFileSync(NUMBERS, JSON.stringify(all, null, 1));
}
function median(xs: number[]): number {
  const s = [...xs].sort((a, b) => a - b);
  return s.length ? s[Math.floor((s.length - 1) / 2)] : NaN;
}
function watch(page: Page) {
  const seen: string[] = [];
  page.on("request", (r) => { if (r.url().includes("/api/design/preview")) seen.push(r.url().split("?")[1] || ""); });
  return seen;
}
async function trips(page: Page, since: number): Promise<number[]> {
  return page.evaluate((n) => performance.getEntriesByType("resource")
    .filter((e) => e.name.includes("/api/design/preview")).slice(n).map((e) => Math.round(e.duration)), since);
}
async function count(page: Page): Promise<number> {
  return page.evaluate(() => performance.getEntriesByType("resource").filter((e) => e.name.includes("/api/design/preview")).length);
}
function forearm(length: number, height: number): string {
  const doc = JSON.parse(fs.readFileSync(path.join(ROOT, "examples", "forearm.arucostudio.json"), "utf-8"));
  doc.sketches[0].shapes[0].rect = [length, 40];
  doc.features[0].height = height;
  return JSON.stringify(doc, null, 1) + "\n";
}

for (const [run, length, height] of [[1, 133, 40], [2, 146.5, 43], [3, 161, 46]] as const) {
  test(`2D drag, run ${run} (box ${length} mm)`, async ({ page }) => {
    const file = await freshFile(page, `v-2d-${run}`, forearm(length, height));
    await page.keyboard.press("f");
    await idle(page);
    await expect(page.locator("g[data-tag]")).toHaveCount(4);
    await page.mouse.click(...(await screenOf(page, 0, 0)));
    await expect.poll(async () => (await probe(page)).shapeSel).toEqual(["outline"]);
    const seen = watch(page);
    const n0 = await count(page);
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
    const t = await trips(page, n0);
    expect(seen.every((q) => !q.includes("mesh=1"))).toBe(true);
    expect(readFile(file).sketches[0].shapes[0].rect[0]).toBeGreaterThan(length);
    record(`2d.run${run}`, { round_trips_ms: t, median_ms: median(t), requests: seen });
    console.log(`V 2D run ${run}: ${t.join(", ")}; median ${median(t)}`);
  });

  test(`3D arrow drag, run ${run} (box ${length} x ${height} mm)`, async ({ page }) => {
    const file = await freshFile(page, `v-3d-${run}`, forearm(length + 0.5, height));
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
    const seen = watch(page);
    const n0 = await count(page);
    await page.mouse.move(a[0], a[1]);
    await page.mouse.down();
    for (let i = 1; i <= 10; i++) {
      await page.mouse.move(a[0], a[1] - 6 * i);
      await page.waitForTimeout(60);
    }
    await page.waitForFunction(() => {
      const d = (window as any).__studio3d?.drawn || {};
      return Object.keys(d).length === 4 && Object.values(d).every((v) => v === "light");
    }, null, { timeout: 10000 });
    const during = seen.length;
    const drag = await trips(page, n0);
    const up = Date.now();
    await page.mouse.up();
    await page.waitForFunction(() => {
      const d = (window as any).__studio3d?.drawn || {};
      return Object.keys(d).length === 4 && Object.values(d).every((v) => v === "mesh");
    }, null, { timeout: 15000 });
    const meshed = Date.now() - up;
    await idle(page);
    const all = await trips(page, n0);
    const release = all.slice(drag.length);
    expect(seen.slice(during).filter((q) => q.includes("mesh=1")).length).toBe(1);
    expect(readFile(file).features[0].height).toBeGreaterThan(h0);
    record(`3d.run${run}`, { drag_round_trips_ms: drag, drag_median_ms: median(drag), release_round_trip_ms: release,
      release_to_meshes_ms: meshed, requests: seen });
    console.log(`V 3D run ${run}: drag ${drag.join(", ")}; median ${median(drag)}; release request ${release.join(", ")} ms; release to meshes ${meshed} ms`);
  });
}
