// The range strip's hero video and stills for its report (docs/build_verify_range_report.py):
// the REAL app (the static build under `vite preview` on --port) driven in
// headless Chrome and recorded by Playwright: two markers (the plate's single,
// a grid beside it), Verify -> the strip measures -> both bands -> both selected,
// a required distance typed -> one PASS, one FAIL with its fix -> the camera
// library searched. Writes <out>/hero.webm, <out>/marks.json (when each step
// began, seconds into the video) and the stills.
//   node docs/record_verify_range_hero.mjs --port 5402 --out <dir>
// (start the server yourself: npx --prefix web vite preview --port 5402 --strictPort)
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(path.resolve("web/package.json"));
const { chromium } = require("@playwright/test");
const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const port = Number(arg("--port", "5402"));
const out = path.resolve(arg("--out", "reports/media/verify-range-src"));
fs.mkdirSync(out, { recursive: true });

const browser = await chromium.launch({ channel: "chrome" });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, recordVideo: { dir: out, size: { width: 1280, height: 800 } } });
const page = await ctx.newPage();
const t0 = Date.now();
const marks = {};
const mark = (k) => { marks[k] = (Date.now() - t0) / 1000; };
const idle = () => page.evaluate(() => window.__aruco.idle(30000));
const toClient = (x, y) => page.evaluate(([a, c]) => window.__aruco.toClient(a, c), [x, y]);
await page.goto(`http://127.0.0.1:${port}/`);
await page.evaluate(() => { localStorage.setItem("aruco-web.verify.rangeCamera", JSON.stringify({ id: "d435" })); localStorage.removeItem("arucoStudio.verify.ranges"); });
await page.waitForFunction(() => window.__aruco?.state().core.state === "ready", null, { timeout: 120000 });
// the document: File > Examples > Plate, its face -> A; a rectangle beside it -> A -> Grid
await page.getByTestId("menu-main").click();
const fr = await page.getByTestId("menu-file").boundingBox();
await page.mouse.move(fr.x + fr.width / 2, fr.y + fr.height / 2, { steps: 3 });
await page.getByTestId("cmd-examples").click();
await page.locator('[data-example="plate"]').click();
await idle();
let [cx, cy] = await toClient(60, 40);
await page.mouse.click(cx, cy);
await page.keyboard.press("a"); await idle();
await page.getByTestId("panel-ok").click(); await idle();
[cx, cy] = await toClient(60, 40);
await page.mouse.move(cx, cy); await page.mouse.wheel(0, 300); await page.waitForTimeout(400);
await page.keyboard.press("r");
const [ax, ay] = await toClient(124, 10), [bx, by] = await toClient(164, 40);
await page.mouse.move(ax, ay); await page.mouse.down();
for (let i = 1; i <= 12; i++) await page.mouse.move(ax + (bx - ax) * i / 12, ay + (by - ay) * i / 12);
await page.mouse.up();
await page.keyboard.press("a");
await page.waitForSelector('[data-testid="extrude-panel"]');
const tab = page.locator('[data-testid="panel-tab-marker"], [data-tab="marker"]').first();
if (await tab.count()) await tab.click().catch(() => {});
await page.locator('[data-path="marker.type"] [data-value="grid"]').click(); await idle();
await page.getByTestId("panel-ok").click(); await idle();
await page.mouse.move(640, 760);
await page.waitForTimeout(600);
// the flow
mark("open");
const verify = (await page.getByTestId("act-verify").boundingBox());
await page.mouse.move(verify.x + verify.width / 2, verify.y + verify.height / 2, { steps: 12 });
await page.getByTestId("act-verify").click();
await page.waitForSelector('[data-testid="range-progress"]', { timeout: 60000 });
mark("measuring");
await page.waitForTimeout(1200);
await page.screenshot({ path: path.join(out, "strip-measuring.png") });
await page.waitForFunction(() => [...document.querySelectorAll('[data-testid="range-col"]')].every((e) => e.getAttribute("data-state") === "done"), null, { timeout: 300000 });
mark("measured");
await page.waitForTimeout(900);
const cols = page.getByTestId("range-col");
const box = async (i) => cols.nth(i).boundingBox();
const b0 = await box(0), b1 = await box(1);
await page.mouse.move(b0.x + 100, b0.y + 40, { steps: 10 });
await cols.nth(0).click();
await page.waitForTimeout(300);
await page.mouse.move(b1.x + 100, b1.y + 40, { steps: 10 });
await cols.nth(1).click({ modifiers: ["Shift"] });
mark("selected");
const fars = await cols.evaluateAll((els) => els.map((e) => Number(e.getAttribute("data-far"))));
const nears = await cols.evaluateAll((els) => els.map((e) => Number(e.getAttribute("data-near"))));
const between = Math.round(Math.sqrt(fars[0] * fars[1]) / 50) * 50;
const from = Math.ceil((Math.max(...nears) + 10) / 10) * 10;
const typeIn = async (p, v) => {
  const i = page.locator(`input[data-path="${p}"]`);
  const ib = await i.boundingBox();
  await page.mouse.move(ib.x + ib.width / 2, ib.y + ib.height / 2, { steps: 8 });
  await i.click();
  await i.fill("");
  await page.keyboard.type(String(v), { delay: 90 });
  await page.keyboard.press("Enter");
};
await typeIn("verify.min_mm", from);
await typeIn("verify.max_mm", between);
await page.waitForFunction(() => [...document.querySelectorAll('[data-testid="range-col"]')].every((e) => e.getAttribute("data-verdict")), null, { timeout: 30000 });
mark("verdicts");
await page.mouse.move(640, 600, { steps: 8 });
await page.waitForTimeout(1800);
await page.screenshot({ path: path.join(out, "strip-verdicts.png") });
const chip = await page.getByTestId("camera-chip").boundingBox();
await page.mouse.move(chip.x + chip.width / 2, chip.y + chip.height / 2, { steps: 10 });
await page.getByTestId("camera-chip").click();
mark("library");
await page.waitForTimeout(500);
await page.keyboard.type("realsense", { delay: 80 });
await page.waitForTimeout(900);
await page.screenshot({ path: path.join(out, "camera-picker.png") });
await page.keyboard.press("Escape");
await page.waitForTimeout(600);
mark("end");
// a band's far end opens the bench there (a still, after the video's flow)
await cols.nth(0).locator('circle[data-end="far"]').click();
await page.waitForSelector('[data-testid="verify-image"]', { timeout: 60000 });
await page.waitForTimeout(1200);
await page.screenshot({ path: path.join(out, "bench-at-far.png") });
const video = page.video();
await ctx.close();
await browser.close();
const vpath = await video.path();
fs.renameSync(vpath, path.join(out, "hero.webm"));
fs.writeFileSync(path.join(out, "marks.json"), JSON.stringify({ ...marks, fars, nears, from, between }, null, 1));
console.log(JSON.stringify(marks));
