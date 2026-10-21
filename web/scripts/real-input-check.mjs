// node scripts/real-input-check.mjs: multi-selection under REAL X11 input.
// Zach, 2026-10-20 night: "multi select by right click drag doesn't work, or
// by shift click" -- in his Chrome (Ubuntu, X11, a mouse), while the same
// gestures sent as CDP input (Playwright's page.mouse) passed. So this check
// sends nothing through CDP: it starts its own Xvfb, a HEADED Chrome on it,
// and drives the pointer and keys with xdotool, the way a mouse does; the page
// is only read (window.__aruco.state().selection).
//
//   node scripts/real-input-check.mjs                    the build in dist/, served on --port 5380
//   node scripts/real-input-check.mjs --url http://127.0.0.1:5383   a running Studio instead
//   node scripts/real-input-check.mjs --display :97 --width 1184
//
// It draws two rectangles on the plate (as Zach did), then, each from a fresh
// selection: right-drag window and crossing (from empty canvas, from the
// plate's fill, from a shape), ten right "flicks" (released straight after the
// last move: the case that lost the selection, 2 in 10 before the fix),
// left-drag on empty canvas and on the plate's fill, Shift+click and
// Ctrl+click on an edge and on a fill, and checks the "N selected" chip.
// Exit 1 on any FAIL. Everything it starts it stops.
import { spawn, spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.resolve(here, "..");
const arg = (name, dflt) => {
  const i = process.argv.indexOf(`--${name}`);
  return i > 0 ? process.argv[i + 1] : dflt;
};
const DISPLAY = arg("display", ":97");
const PORT = Number(arg("port", 5380));
const WIDTH = Number(arg("width", 1184));
const HEIGHT = Number(arg("height", 800));
let URL_ = arg("url", null);

const started = [];   // [name, child] we stop at the end, by pid
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function reachable(url) {
  try { return (await fetch(url)).ok; } catch { return false; }
}

async function startXvfb() {
  const x = spawn("Xvfb", [DISPLAY, "-screen", "0", `${WIDTH + 200}x${HEIGHT + 200}x24`, "-nolisten", "tcp"], { stdio: "ignore" });
  started.push(["Xvfb", x]);
  for (let i = 0; i < 50; i++) {
    if (spawnSync("xdpyinfo", ["-display", DISPLAY], { stdio: "ignore" }).status === 0) return;
    await sleep(100);
  }
  // xdpyinfo may be missing: xdotool answers too
  if (spawnSync("xdotool", ["getdisplaygeometry"], { env: { ...process.env, DISPLAY } }).status !== 0) throw new Error(`Xvfb ${DISPLAY} did not come up`);
}

async function startServer() {
  // vite itself, not through npx: its pid is the server's, to stop
  const s = spawn(path.join(web, "node_modules", ".bin", "vite"), ["preview", "--host", "127.0.0.1", "--port", String(PORT), "--strictPort"], { cwd: web, stdio: "ignore" });
  started.push(["vite preview", s]);
  for (let i = 0; i < 100; i++) { if (await reachable(URL_)) return; await sleep(200); }
  throw new Error(`vite preview did not answer on ${URL_}`);
}

function stopAll() {
  for (const [name, child] of started.reverse()) {
    try { process.kill(child.pid, "SIGTERM"); } catch { /* gone */ }
    console.log(`stopped ${name} (pid ${child.pid})`);
  }
}

// ---- xdotool: the real input ----------------------------------------------------------------
const xdo = (...a) => {
  if (process.env.VERBOSE) console.log("xdotool", ...a);
  const r = spawnSync("xdotool", a.map(String), { env: { ...process.env, DISPLAY } });
  if (r.status !== 0) throw new Error(`xdotool ${a.join(" ")}: ${r.stderr}`);
};
let off = [0, 0];   // client px -> screen px, calibrated
const scr = ([x, y]) => [Math.round(x + off[0]), Math.round(y + off[1])];
const move = (p) => xdo("mousemove", ...scr(p));
/** a press, moves in steps, a release: one button held through the drag */
async function drag(button, a, b, { mods = [], steps = 12 } = {}) {
  move(a);
  await sleep(40);
  for (const m of mods) xdo("keydown", m);
  xdo("mousedown", button);
  for (let i = 1; i <= steps; i++) {
    move([a[0] + ((b[0] - a[0]) * i) / steps, a[1] + ((b[1] - a[1]) * i) / steps]);
    await sleep(16);
  }
  xdo("mouseup", button);
  for (const m of mods.reverse()) xdo("keyup", m);
  await sleep(120);
}
/** a flick: the press, two quick moves and the release at once, no pause (a fast hand on a busy page) */
async function flick(button, a, b) {
  move(a);
  await sleep(40);
  xdo("mousedown", button);
  move([(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]);
  move(b);
  xdo("mouseup", button);
  await sleep(150);
}
async function click(p, mods = []) {
  move(p);
  await sleep(40);
  for (const m of mods) xdo("keydown", m);
  xdo("click", 1);
  for (const m of [...mods].reverse()) xdo("keyup", m);
  await sleep(120);
}
async function key(k) { xdo("key", k); await sleep(80); }

// ---- the run ---------------------------------------------------------------------------------
const results = [];
function check(name, got, want, extra = "") {
  const ok = JSON.stringify([...got].sort()) === JSON.stringify([...want].sort());
  results.push(ok);
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}: selection ${JSON.stringify(got)}${ok ? "" : ` (want ${JSON.stringify(want)})`}${extra}`);
}

async function main() {
  if (!URL_) {
    URL_ = `http://127.0.0.1:${PORT}`;
    if (!(await reachable(URL_))) await startServer();
  }
  console.log(`serving ${URL_}`);
  await startXvfb();
  console.log(`Xvfb ${DISPLAY} up`);
  const browser = await chromium.launch({
    channel: "chrome", headless: false, env: { ...process.env, DISPLAY },
    args: ["--window-position=0,0", `--window-size=${WIDTH},${HEIGHT}`, "--no-first-run", "--disable-infobars"],
  });
  try {
    const page = await browser.newPage({ viewport: null });
    await page.goto(URL_);
    await page.waitForFunction(() => window.__aruco?.state().view.w > 0, null, { timeout: 60_000 });
    const st = () => page.evaluate(() => JSON.parse(JSON.stringify(window.__aruco.state())));
    const toClient = (x, y) => page.evaluate(([a, b]) => window.__aruco.toClient(a, b), [x, y]);
    const vw = await page.evaluate(() => [innerWidth, innerHeight]);
    console.log(`Chrome ${browser.version()} headed on Xvfb ${DISPLAY}, viewport ${vw[0]} x ${vw[1]}, ${URL_}`);

    // calibrate: where a real pointer at screen (s) lands in the page
    await page.evaluate(() => { window.__seen = null; addEventListener("pointermove", (e) => { window.__seen = [e.clientX, e.clientY]; }, true); });
    xdo("mousemove", 400, 400);
    await sleep(100);
    xdo("mousemove", 401, 401);
    await page.waitForFunction(() => window.__seen, null, { timeout: 5000 });
    const seen = await page.evaluate(() => window.__seen);
    off = [401 - seen[0], 401 - seen[1]];
    console.log(`client -> screen offset ${off.join(", ")}`);

    // the plate (120 x 80, holes at (25,55) and (95,25)), fitted; two rectangles drawn on it, as Zach did
    await page.evaluate(() => { localStorage.clear(); });
    const drawRect = async (a, b) => { await key("r"); await drag(1, await toClient(...a), await toClient(...b)); };
    const empty = await page.evaluate(() => window.__aruco.state().doc.shapes.length);
    if (empty !== 3) throw new Error(`expected the plate's 3 shapes at start, got ${empty}`);
    await drawRect([40, 8], [70, 32]);
    await drawRect([45, 44], [78, 70]);
    const s0 = await st();
    const [A, B] = s0.doc.shapes.filter((s) => s.kind === "rect" && s.id !== "plate").map((s) => s.id);
    if (!A || !B) throw new Error(`drawing with real input made ${s0.doc.shapes.length} shapes`);
    const ALL = s0.doc.shapes.map((s) => s.id);
    // zoom out with the real wheel (3 notches at the plate's centre): empty canvas all round it
    move(await toClient(60, 40));
    for (let i = 0; i < 3; i++) { xdo("click", 5); await sleep(60); }
    await sleep(150);
    const reset = async () => { await click(await toClient(-30, -30)); await key("Escape"); };
    const sel = async () => (await st()).selection;
    const chip = () => page.evaluate(() => document.querySelector('[data-testid="selection-count"]')?.textContent ?? null);

    // right-drag: a window (left to right) from empty canvas around the plate
    await reset();
    await drag(3, await toClient(-15, -15), await toClient(135, 95));
    check("right-drag window from empty canvas, around the plate", await sel(), ALL, `; chip ${JSON.stringify(await chip())}`);
    // right-drag: a window from the plate's fill around both rectangles
    await reset();
    await drag(3, await toClient(37, 75), await toClient(82, 4));
    check("right-drag window from the plate's fill, around A and B", await sel(), [A, B]);
    // right-drag: a crossing (right to left) through A and B only
    await reset();
    await drag(3, await toClient(60, 50), await toClient(55, 20));
    check("right-drag crossing (right to left) through A and B", await sel(), [A, B]);
    // right-drag starting ON a shape: from B's fill, a crossing (right to left) back through A
    await reset();
    await drag(3, await toClient(75, 60), await toClient(37, 15));
    check("right-drag crossing starting on B's fill, through A", await sel(), [A, B]);
    // right-drag starting on A's edge: a window to the right, around B (A is not inside it)
    await reset();
    await drag(3, await toClient(40, 20), await toClient(82, 75));
    check("right-drag window starting on A's edge, around B", await sel(), [B]);

    // a flick: released straight after the last move, before the page has drawn the box
    for (let i = 0; i < 10; i++) {
      await reset();
      await flick(3, await toClient(37, 75), await toClient(82, 4));
      check(`right-flick ${i + 1} from the plate's fill, around A and B, released at once`, await sel(), [A, B]);
    }
    await reset();
    await flick(1, await toClient(37, 75), await toClient(82, 4));
    check("left-flick from the plate's fill, around A and B, released at once", await sel(), [A, B]);

    // left-drag in Select: a marquee from empty canvas, and from the plate's fill
    await reset();
    await drag(1, await toClient(-15, 98), await toClient(135, -15));
    check("left-drag window from empty canvas, around the plate", await sel(), ALL);
    await reset();
    await drag(1, await toClient(37, 75), await toClient(82, 4));
    check("left-drag window from the plate's fill, around A and B", await sel(), [A, B], `; chip ${JSON.stringify(await chip())}`);

    // Shift+click and Ctrl+click: on an edge, on a fill
    await reset();
    await click(await toClient(40, 20));
    await click(await toClient(78, 57), ["shift"]);
    check("click A's edge, Shift+click B's edge", await sel(), [A, B]);
    await reset();
    await click(await toClient(55, 20));
    await click(await toClient(60, 57), ["shift"]);
    check("click inside A, Shift+click inside B", await sel(), [A, B], `; chip ${JSON.stringify(await chip())}`);
    await click(await toClient(60, 57), ["shift"]);
    check("Shift+click inside B again takes it out", await sel(), [A]);
    await reset();
    await click(await toClient(55, 20));
    await click(await toClient(60, 57), ["ctrl"]);
    check("click inside A, Ctrl+click inside B", await sel(), [A, B]);
    await reset();
    await click(await toClient(40, 20));
    await click(await toClient(10, 10), ["shift"]);
    check("click A's edge, Shift+click the plate's fill adds the plate", await sel(), [A, "plate"]);

    // the highlight: every selected edge drawn as selected
    await reset();
    await drag(3, await toClient(-15, -15), await toClient(135, 95));
    const on = await page.evaluate(() => [...document.querySelectorAll("[data-shape].on")].map((e) => e.getAttribute("data-shape")));
    check("every selected shape is highlighted", on, ALL);
    const c = await chip();
    results.push(c === `${ALL.length} selected`);
    console.log(`${c === `${ALL.length} selected` ? "PASS" : "FAIL"}  the count chip reads ${JSON.stringify(c)} (want "${ALL.length} selected")`);
  } finally {
    await browser.close().catch(() => {});
    stopAll();
  }
  const bad = results.filter((r) => !r).length;
  console.log(`${results.length - bad} passed, ${bad} failed`);
  process.exit(bad ? 1 : 0);
}

for (const sig of ["SIGINT", "SIGTERM"]) process.on(sig, () => { stopAll(); process.exit(130); });
main().catch((err) => { console.error(err); stopAll(); process.exit(2); });
