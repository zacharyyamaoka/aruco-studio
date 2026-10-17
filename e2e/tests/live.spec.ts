// M8b1.3 / M8b1.4: the file is the truth. Ten tags on ten rectangles: one
// handle drag re-places its marker, and the canvas shows the new plan within
// 100 ms of the pointer's release. The test writes the forearm example over
// the open file: four tags on the canvas within 500 ms, no reload; a broken
// write keeps the canvas, says "line N col M", and refuses every write;
// Undo after three edits restores each text byte for byte.
import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { ROOT, centre, freshFile, idle, probe, readFile, screenOf, shot } from "./helpers";

const NUMBERS = path.join(ROOT, "e2e", ".tmp", "m8b1_numbers.json");

function record(key: string, v: unknown) {
  let all: Record<string, unknown> = {};
  try { all = JSON.parse(fs.readFileSync(NUMBERS, "utf-8")); } catch { /* first */ }
  all[key] = v;
  fs.mkdirSync(path.dirname(NUMBERS), { recursive: true });
  fs.writeFileSync(NUMBERS, JSON.stringify(all, null, 1));
}

function tenTags(): string {
  const sketches = [], features = [];
  for (let i = 0; i < 10; i++) {
    const x = (i % 5) * 75 - 150, y = i < 5 ? 40 : -40;
    sketches.push({ id: `sk${i + 1}`, at: [x, y], shapes: [{ id: `r${i + 1}`, rect: [60, 30] }] });
    features.push({ id: `t${i + 1}`, aruco: `r${i + 1}`, layout: "single", first_id: i });
  }
  return JSON.stringify({ schema: "arucostudio.scene/2", name: "ten", sketches, features }, null, 1) + "\n";
}

/** In the page: the time from the next pointer-up to the canvas's next
 *  data-revision change (ms). */
async function armTimer(page: Page) {
  await page.evaluate(() => {
    const w = window as any;
    w.__live = { up: 0, drawn: 0 };
    const svg = document.querySelector("svg.stage")!;
    const rev = svg.getAttribute("data-revision");
    window.addEventListener("pointerup", () => { w.__live.up = performance.now(); }, { capture: true, once: true });
    const mo = new MutationObserver(() => {
      if (w.__live.up && svg.getAttribute("data-revision") !== rev && !w.__live.drawn) {
        w.__live.drawn = performance.now();
        mo.disconnect();
      }
    });
    mo.observe(svg, { attributes: true, attributeFilter: ["data-revision"] });
  });
}

test("M8b1.3 live re-placement: a handle drag on one of ten tags, redrawn under 100 ms", async ({ page }) => {
  const file = await freshFile(page, "e2e-ten", tenTags());
  await page.keyboard.press("f");
  await idle(page);
  await expect(page.locator("g[data-tag]")).toHaveCount(10);
  await shot(page, "m8b1_live_ten");
  const times: number[] = [];
  const sizes: number[] = [];
  for (let k = 0; k < 5; k++) {
    // select r3 by its end (outside its marker), then drag its right edge
    const r3 = readFile(file).sketches[2];
    const w = r3.shapes[0].rect[0];
    await page.mouse.click(...(await screenOf(page, r3.at[0] + (r3.shapes[0].at?.[0] ?? 0) - w / 2 + 2, r3.at[1] + 12)));
    await expect.poll(async () => (await probe(page)).shapeSel).toEqual(["r3"]);
    const zoom = (await probe(page)).zoom;
    const e = await centre(page, '[data-handle="e"]');
    await armTimer(page);
    await page.mouse.move(e[0], e[1]);
    await page.mouse.down();
    const dx = (k % 2 === 0 ? 8 : -8) * zoom;
    for (let i = 1; i <= 8; i++) {
      await page.mouse.move(e[0] + (dx * i) / 8, e[1]);
      await page.waitForTimeout(40);
    }
    await page.mouse.up();
    await page.waitForFunction(() => (window as any).__live.drawn > 0, null, { timeout: 5000 });
    const t = await page.evaluate(() => (window as any).__live.drawn - (window as any).__live.up);
    times.push(Math.round(t * 10) / 10);
    await idle(page);
    sizes.push(readFile(file).sketches[2].shapes[0].rect[0]);
  }
  record("M8b1.3", { ms: times, widths: sizes, store_last_live_ms: (await probe(page)).lastLive });
  console.log(`M8b1.3 pointer-up to redraw (ms): ${times.join(", ")}`);
  expect(sizes).toEqual([68, 60, 68, 60, 68]);
  for (const t of times) expect(t).toBeLessThan(100);
  await shot(page, "m8b1_live_after_drag");
});

test("M8b1.4 the file: an outside write is drawn, a broken one blocks writes, Undo is the text history", async ({ page }) => {
  const file = await freshFile(page, "e2e-file");
  await page.evaluate(() => { (window as any).__boot = "same page"; });

  // the forearm example written over the open file: four tags, no reload
  const forearm = fs.readFileSync(path.join(ROOT, "examples", "forearm.arucostudio.json"), "utf-8");
  const t0 = Date.now();
  fs.writeFileSync(file, forearm, "utf-8");
  await page.waitForFunction(() => document.querySelectorAll("g[data-tag]").length === 4, null, { timeout: 5000, polling: 10 });
  const dt = Date.now() - t0;
  record("M8b1.4.outside_write_ms", dt);
  console.log(`M8b1.4 outside write to four tags drawn: ${dt} ms`);
  expect(dt).toBeLessThan(500);
  expect(await page.evaluate(() => (window as any).__boot)).toBe("same page");
  await page.keyboard.press("f");
  await idle(page);
  await expect(page.locator("[data-hinge]")).toHaveCount(4);
  await shot(page, "m8b1_live_forearm_written");

  // a broken write: the old canvas stays, the bar says where, writes wait
  const broken = forearm.replace('"height": 40', '"height": 40,,');
  fs.writeFileSync(file, broken, "utf-8");
  const bar = page.getByTestId("file-bar");
  await expect(bar).toHaveAttribute("data-state", "broken", { timeout: 5000 });
  await expect(bar).toContainText(/line \d+ col \d+/);
  await expect(page.locator("g[data-tag]")).toHaveCount(4);
  await page.mouse.click(...(await screenOf(page, 0, 0)));              // the forearm's outline
  await expect.poll(async () => (await probe(page)).shapeSel).toEqual(["outline"]);
  await page.keyboard.press("]");
  await idle(page);
  await expect(page.getByTestId("status")).toContainText("does not parse");
  expect(fs.readFileSync(file, "utf-8")).toBe(broken);
  await shot(page, "m8b1_live_broken");

  // fixed again: three edits, then Undo three times, byte for byte
  fs.writeFileSync(file, forearm, "utf-8");
  await expect(bar).toHaveAttribute("data-state", "ok", { timeout: 5000 });
  await idle(page);
  const texts = [fs.readFileSync(file, "utf-8")];
  await page.mouse.click(...(await screenOf(page, 0, 0)));
  await expect.poll(async () => (await probe(page)).shapeSel).toEqual(["outline"]);
  await page.keyboard.press("]");                                       // 1: a turn
  await idle(page);
  texts.push(fs.readFileSync(file, "utf-8"));
  await page.keyboard.press("ArrowUp");                                 // 2: a nudge
  await idle(page);
  texts.push(fs.readFileSync(file, "utf-8"));
  const hgt = page.locator('input[data-path="extrude.height"]');        // 3: the height
  await hgt.fill("30");
  await hgt.press("Enter");
  await idle(page);
  texts.push(fs.readFileSync(file, "utf-8"));
  expect(new Set(texts).size).toBe(4);
  expect(readFile(file).features[0].height).toBe(30);
  for (let k = 3; k >= 1; k--) {
    await page.keyboard.press("Control+z");
    await idle(page);
    expect(fs.readFileSync(file, "utf-8")).toBe(texts[k - 1]);
  }
  await page.keyboard.press("Control+y");
  await idle(page);
  expect(fs.readFileSync(file, "utf-8")).toBe(texts[1]);
  await page.getByTestId("sb-file").click();
  await expect(page.getByTestId("file-text")).toBeVisible();
  await shot(page, "m8b1_live_file_drawer");
});
