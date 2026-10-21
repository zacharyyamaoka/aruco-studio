// A still of the range strip on Zach's own 4-board document (the proposal's
// fixture, as a file: reports/media/verify-range-2026-10-21-src/robot-cell.arucostudio-web.json),
// for the report: File > Open, Verify on the D435, every band, then a required
// 300 mm - 1.2 m set on all four at once.
//   node docs/shoot_verify_range_doc.mjs --port 5402 --doc <file> --out <png>
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(path.resolve("web/package.json"));
const { chromium } = require("@playwright/test");
const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const port = Number(arg("--port", "5402"));
const docFile = path.resolve(arg("--doc"));
const out = path.resolve(arg("--out"));
const need = (arg("--need", "300:1200")).split(":").map(Number);

const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
await page.goto(`http://127.0.0.1:${port}/`);
await page.evaluate(() => { localStorage.setItem("aruco-web.verify.rangeCamera", JSON.stringify({ id: "d435" })); });
await page.waitForFunction(() => window.__aruco?.state().core.state === "ready", null, { timeout: 120000 });
await page.getByTestId("menu-main").click();
const fr = await page.getByTestId("menu-file").boundingBox();
await page.mouse.move(fr.x + fr.width / 2, fr.y + fr.height / 2, { steps: 3 });
const [chooser] = await Promise.all([page.waitForEvent("filechooser"), page.getByTestId("cmd-open").click()]);
await chooser.setFiles(docFile);
await page.waitForFunction(() => window.__aruco.state().doc.features.length === 4, null, { timeout: 30000 });
await page.evaluate(() => window.__aruco.idle(60000));
const t0 = Date.now();
await page.getByTestId("act-verify").click();
await page.waitForFunction(() => [...document.querySelectorAll('[data-testid="range-col"]')].every((e) => e.getAttribute("data-state") === "done"),
  null, { timeout: 600000, polling: 1000 });
const secs = (Date.now() - t0) / 1000;
await page.getByTestId("range-select-all").click();
for (const [p, v] of [["verify.min_mm", need[0]], ["verify.max_mm", need[1]]]) {
  const i = page.locator(`input[data-path="${p}"]`);
  await i.fill(String(v));
  await i.press("Enter");
}
await page.waitForFunction(() => [...document.querySelectorAll('[data-testid="range-col"]')].every((e) => e.getAttribute("data-verdict")), null, { timeout: 30000 });
await page.mouse.move(5, 790);
await page.waitForTimeout(500);
await page.screenshot({ path: out });
const cols = await page.locator('[data-testid="range-col"]').evaluateAll((els) => els.map((e) => ({
  near: e.getAttribute("data-near"), far: e.getAttribute("data-far"), verdict: e.getAttribute("data-verdict"),
  hint: e.querySelector('[data-testid="range-hint"]')?.textContent ?? "" })));
console.log(JSON.stringify({ seconds: secs, cols }));
await browser.close();
