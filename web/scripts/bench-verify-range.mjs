// npm run bench:verify-range: how long Verify's reading range takes, one
// marker at a time, the producer of Vibe Tracks' verify_range_ms (contract
// vt-kpi/1, as scripts/bench-feature.mjs is of feature_compute_ms). The
// proposal estimated ~32 s a board in the browser (CPython x Pyodide's factor
// on `readable`, 2026-10-21); this measures it.
//
//   node scripts/bench-verify-range.mjs                        browser, cpython (+ cpython-cv411 when .venv-cv411 is there)
//   node scripts/bench-verify-range.mjs --hosts browser --port 5402 --no-build --dry
//
// The golden document: Zach's of 2026-10-21 (docs/build_verify_test_proposals.py's
// fixture): Grid 3x1 #16-18 with its label typed 5 mm (a whole module: the
// lint's failure), #19-21, #22-24, Grid 2x1 #25-26; 30 mm DICT_4X4_50, inkjet
// vinyl; on the RealSense D435.
// Hosts:
//   browser        the static build under `vite preview` on --port (5402), headless
//                  Chrome, window.__arucoRange.run: the core's worker in 250 ms
//                  slices, as the strip runs it; wall time per marker (OpenCV's
//                  first load apart, as opencv_load_ms)
//   cpython        web_verify.reading_range in the repo's .venv (its OpenCV)
//   cpython-cv411  the same with the browser's OpenCV (tools/requirements-browser-opencv.txt)
// Writes ~/.local/share/aruco_studio_bench/verify_range (--out): kpi_catalog.json,
// kpi_series.jsonl and runs_table.jsonl (appended), items/<run_id>.jsonl.
// WHY its own directory: bench-feature rewrites its kpi_catalog.json each run,
// so a second producer there would lose its KPIs; a track binds a list of dirs.
import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.resolve(here, "..");
const root = path.resolve(web, "..");
const BENCH_VERSION = "verify-range-bench/1";
const HOSTS = ["browser", "cpython", "cpython-cv411"];
const CAMERA = "d435";

function args(argv) {
  const a = { hosts: null, port: 5402, out: path.join(os.homedir(), ".local", "share", "aruco_studio_bench", "verify_range"), dry: false, build: true };
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i], v = () => argv[++i];
    if (k === "--hosts") a.hosts = v().split(",").filter(Boolean);
    else if (k === "--port") a.port = Number(v());
    else if (k === "--out") a.out = path.resolve(v());
    else if (k === "--dry") a.dry = true;
    else if (k === "--no-build") a.build = false;
    else throw new Error(`unknown argument ${k}`);
  }
  for (const h of a.hosts ?? []) if (!HOSTS.includes(h)) throw new Error(`--hosts: ${h} is not one of ${HOSTS.join(", ")}`);
  return a;
}

const PY = [path.join(root, ".venv", "bin", "python"), path.join(root, ".venv", "Scripts", "python.exe")].find((p) => fs.existsSync(p));
const PY411 = [path.join(root, ".venv-cv411", "bin", "python"), path.join(root, "..", "aruco-studio", ".venv-cv411", "bin", "python")].find((p) => fs.existsSync(p));

function python(exe, code, input = "") {
  const r = spawnSync(exe, ["-c", code], { cwd: root, input, encoding: "utf8", maxBuffer: 1 << 28,
    env: { ...process.env, PYTHONPATH: root, PYTHONDONTWRITEBYTECODE: "1" } });
  if (r.status !== 0) throw new Error(`${exe} failed: ${r.stderr}`);
  return r.stdout;
}

// ------------------------------------------------------------------ the golden document (the proposal's req())

function boards(presets) {
  const ink = presets.find((p) => p.name === "Inkjet · Letter vinyl");
  const req = (cols, first, mm = 30, label = {}) => {
    const sep = Math.round((mm / 3) * 10) / 10;
    return {
      rect: { cx: 0, cy: 0, w: cols * mm + (cols - 1) * sep + 3.5, h: mm + 10, angle_deg: 0 },
      marker: { type: "grid", dictionary: "DICT_4X4_50", first_id: first, auto: false, marker_mm: mm, checker_mm: 0, separation_mm: sep,
        cols, rows: 1, turn: 0, flip: false, quiet_modules: 1, corner_mark: "none" },
      label: { on: true, text: "#{ids}", height_mm: 0, side: "below", gap_mm: 2, offset_mm: [0, 0], place: "on_marker", ...label },
      preset: ink, reference_face: false,
    };
  };
  return [
    { id: "A", name: "Grid 3×1 #16–18 (label typed 5 mm)", req: req(3, 16, 30, { height_mm: 5 }) },
    { id: "B", name: "Grid 3×1 #19–21", req: req(3, 19) },
    { id: "C", name: "Grid 3×1 #22–24", req: req(3, 22) },
    { id: "D", name: "Grid 2×1 #25–26", req: req(2, 25) },
  ];
}

// ------------------------------------------------------------------ the hosts

function runCpython(exe, list) {
  const code = [
    "import json, sys, time",
    "import cv2",
    "from aruco_studio import web_verify as V",
    "out = []",
    "for b in json.load(sys.stdin):",
    "    t = time.perf_counter()",
    `    r = V.reading_range(b['req'], ${JSON.stringify(CAMERA)})`,
    "    out.append({'ms': (time.perf_counter() - t) * 1000.0, 'result': r, 'renders': r['renders']})",
    "sys.stdout.write(json.dumps({'runtime': 'CPython ' + sys.version.split()[0] + ' + OpenCV ' + cv2.__version__, 'rows': out}))",
  ].join("\n");
  return JSON.parse(python(exe, code, JSON.stringify(list)));
}

async function waitFor(url, ms) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    try { if ((await fetch(url)).ok) return true; } catch { /* not up yet */ }
    await new Promise((r) => setTimeout(r, 300));
  }
  return false;
}

async function runBrowser(list, a) {
  let chromium;
  try { ({ chromium } = await import("@playwright/test")); } catch { return { skipped: "@playwright/test is not installed" }; }
  if (a.build) {
    const b = spawnSync("npm", ["run", "build"], { cwd: web, encoding: "utf8" });
    if (b.status !== 0) throw new Error(`npm run build failed: ${b.stderr || b.stdout}`);
  }
  // WHY our own server, stopped by its pid: a port someone else holds is theirs
  const server = spawn(path.join(web, "node_modules", ".bin", "vite"), ["preview", "--host", "127.0.0.1", "--port", String(a.port), "--strictPort"],
    { cwd: web, stdio: "ignore" });
  const url = `http://127.0.0.1:${a.port}/`;
  try {
    if (!(await waitFor(url, 30_000))) return { skipped: `vite preview did not come up on ${a.port}` };
    const browser = await chromium.launch({ channel: "chrome" });
    try {
      const page = await browser.newPage();
      await page.goto(url);
      await page.waitForFunction(() => window.__aruco?.state().core.state === "ready", null, { timeout: 120_000 });
      await page.waitForFunction(() => !!window.__arucoRange, null, { timeout: 60_000 });
      const rows = [];
      let opencv = null;
      for (const b of list) {
        const r = await page.evaluate(([req, cam]) => window.__arucoRange.run(req, cam), [b.req, CAMERA]);
        // the first start loads OpenCV: kept apart, never counted in a marker's time
        if (opencv === null) opencv = r.start_ms;
        rows.push({ ms: r.wall_ms - r.start_ms, start_ms: r.start_ms, render_ms: r.render_ms, steps: r.steps, worst_step_ms: r.worst_step_ms,
          renders: r.renders, result: r.result });
      }
      const ua = await page.evaluate(() => navigator.userAgent);
      return { runtime: `Chrome headless (${/Chrome\/[\d.]+/.exec(ua)?.[0] ?? "?"}) · Pyodide worker · OpenCV ${rows[0]?.result.opencv}`, rows, opencv_load_ms: opencv };
    } finally {
      await browser.close();
    }
  } finally {
    server.kill("SIGTERM");
  }
}

// ------------------------------------------------------------------ the vt-kpi/1 directory

const r3 = (v) => (v == null ? null : Math.round(v * 1000) / 1000);

function gitSha() {
  const r = spawnSync("git", ["rev-parse", "--short=8", "HEAD"], { cwd: root, encoding: "utf8" });
  const dirty = spawnSync("git", ["status", "--porcelain", "--", "aruco_studio", "web/src"], { cwd: root, encoding: "utf8" }).stdout.trim();
  return { sha: r.status === 0 ? r.stdout.trim() : null, dirty: dirty ? dirty.split("\n").length : 0 };
}

function catalog() {
  return {
    schema: "vt-kpi-catalog/1", unit_of_iteration: "run",
    title: "Verify's reading range compute time (ArUco Studio)",
    producer: { name: "aruco-studio web/scripts/bench-verify-range.mjs", bench_version: BENCH_VERSION, hosts: HOSTS },
    kpis: [
      { id: "verify_range_ms", title: "Reading range of one marker (slowest board)", unit: "ms", direction: "lower", level: 0,
        parent: null, target: null, computed_from: "runs", scale: "linear",
        description: "How long Verify's range strip takes to answer one marker on the RealSense D435: the golden 4-board " +
          "document's slowest board, wall time in the browser's core worker (OpenCV's first load apart). Hollow when a " +
          "CPython host stood in for an unmeasured browser. Slices carry each host and board.",
        formula: "max over the golden boards of the wall ms of reading_range, browser host",
        facets: ["host", "board", "camera", "opencv"], reference_lines: [{ value: 32000, label: "the proposal's estimate, 32 s a board" }] },
      { id: "verify_range_doc_ms", title: "Reading range of the whole golden document", unit: "ms", direction: "lower", level: 1,
        parent: "verify_range_ms", target: null, computed_from: "runs", scale: "linear",
        description: "The four boards one after another, as the strip measures them in one worker.",
        formula: "sum over the golden boards of the wall ms, browser host", facets: ["host"] },
      { id: "verify_range_ms_per_view", title: "Time per view (render + detect)", unit: "ms", direction: "lower", level: 1,
        parent: "verify_range_ms", target: null, computed_from: "runs", scale: "linear",
        description: "The document's rendering time over its views: what one simulated camera view costs on the host.",
        formula: "sum(ms) / sum(renders) over the golden boards", facets: ["host"] },
    ],
    gates: [],
  };
}

function emit(t, stamp, git, measured) {
  const runs = [], points = [], items = {};
  const source = (ids) => ({ code_sha: git.sha, ...(git.dirty ? { dirty_files: git.dirty } : {}), bench_version: BENCH_VERSION, run_ids: ids });
  const point = (kpi, value, slice, n, ids, labels, status = "measured") => points.push({ schema: "vt-kpi-point/1", kpi, t,
    value: r3(value), n, status, ...(slice ? { slice } : {}), labels, source: source(ids) });
  for (const [host, m] of Object.entries(measured)) {
    const ids = [];
    m.rows.forEach((row, i) => {
      const b = m.boards[i];
      const run_id = `${stamp}-${host}-${b.id}`;
      ids.push(run_id);
      const rr = row.result;
      items[run_id] = [{ item_id: `${run_id}#1`, latency_ms: r3(row.ms), renders: row.renders, steps: row.steps ?? null, worst_step_ms: r3(row.worst_step_ms ?? null),
        near_mm: rr.near_mm, far_mm: rr.far_mm, band_mm: rr.band_mm, facets: { board: b.id } }];
      runs.push({ schema: "vt-run/1", run_id, t, facets: { host, lane: host, board: b.id, camera: CAMERA, opencv: rr.opencv },
        metrics: { boards: 1, ms_sum: r3(row.ms), renders_sum: row.renders, steps_sum: row.steps ?? 0 },
        detail: { runtime: m.runtime, name: b.name, near_mm: rr.near_mm, far_mm: rr.far_mm, band_mm: rr.band_mm, version: rr.version,
          ...(m.opencv_load_ms != null && i === 0 ? { opencv_load_ms: r3(m.opencv_load_ms) } : {}) },
        items: { path: `items/${run_id}.jsonl`, schema: "aruco-verify-range-sample/1", n: 1 } });
      point("verify_range_ms", row.ms, { host, board: b.id, camera: CAMERA, opencv: rr.opencv }, 1, [run_id], { lane: host, host });
    });
    const slow = m.rows.reduce((x, r, i) => (r.ms > m.rows[x].ms ? i : x), 0);
    const sum = m.rows.reduce((x, r) => x + r.ms, 0), views = m.rows.reduce((x, r) => x + r.renders, 0);
    point("verify_range_ms", m.rows[slow].ms, { host }, m.rows.length, ids, { lane: host, host, slowest: ids[slow] });
    point("verify_range_doc_ms", sum, { host }, m.rows.length, ids, { lane: host, host });
    point("verify_range_ms_per_view", sum / views, { host }, views, ids, { lane: host, host });
  }
  const head = ["browser", "cpython-cv411", "cpython"].find((h) => measured[h]);
  if (head) {
    const m = measured[head], ids = runs.filter((r) => r.facets.host === head).map((r) => r.run_id);
    const status = head === "browser" ? "measured" : "stand-in";
    const slow = m.rows.reduce((x, r, i) => (r.ms > m.rows[x].ms ? i : x), 0);
    const sum = m.rows.reduce((x, r) => x + r.ms, 0), views = m.rows.reduce((x, r) => x + r.renders, 0);
    point("verify_range_ms", m.rows[slow].ms, null, m.rows.length, ids, { lane: head, host: head, slowest: ids[slow] }, status);
    point("verify_range_doc_ms", sum, null, m.rows.length, ids, { lane: head, host: head }, status);
    point("verify_range_ms_per_view", sum / views, null, views, ids, { lane: head, host: head }, status);
  } else {
    point("verify_range_ms", null, null, 0, [], { lane: "none" }, "not_measured");
  }
  return { runs, points, items, head };
}

// ------------------------------------------------------------------ main

const a = args(process.argv.slice(2));
if (!PY) throw new Error("no .venv python under the repo root");
const hosts = a.hosts ?? ["browser", "cpython", ...(PY411 ? ["cpython-cv411"] : [])];
const presets = JSON.parse(python(PY, "import json\nfrom aruco_studio import web_api\nprint(web_api.call('presets', '{}'))")).result;
const list = boards(presets);
const git = gitSha();
const t = new Date().toISOString().replace(/\.\d+Z$/, "Z");
const stamp = t.replace(/[-:]/g, "").replace("T", "-").replace("Z", "");
console.log(`bench-verify-range: ${list.length} boards on the ${CAMERA}, hosts ${hosts.join(", ")}, aruco-studio ${git.sha}${git.dirty ? ` (+${git.dirty} dirty)` : ""}, ${BENCH_VERSION}`);

const measured = {};
for (const host of hosts) {
  const t0 = performance.now();
  if (host === "browser") {
    const b = await runBrowser(list, a);
    if (b.skipped) { console.log(`  browser: not measured (${b.skipped})`); continue; }
    measured.browser = { ...b, boards: list };
  } else {
    const exe = host === "cpython" ? PY : PY411;
    if (!exe) { console.log(`  ${host}: not measured (no ${host === "cpython" ? ".venv" : ".venv-cv411"})`); continue; }
    measured[host] = { ...runCpython(exe, list), boards: list };
  }
  console.log(`  ${host}: ${list.length} boards in ${((performance.now() - t0) / 1000).toFixed(1)} s; ${measured[host].runtime}` +
    (measured[host].opencv_load_ms != null ? `; OpenCV's first load ${(measured[host].opencv_load_ms / 1000).toFixed(1)} s (apart)` : ""));
}

const fmt = (v) => (v == null ? "—" : `${(v / 1000).toFixed(1)} s`);
const m = (v) => (v == null ? "—" : v >= 1000 ? `${(v / 1000).toFixed(2)} m` : `${Math.round(v)} mm`);
console.log("\nboard                                  " + Object.keys(measured).map((h) => h.padEnd(30)).join(""));
list.forEach((b, i) => {
  console.log(b.name.padEnd(39) + Object.values(measured).map((x) => {
    const r = x.rows[i];
    return `${fmt(r.ms)} · ${r.renders} views · ${m(r.result.near_mm)}–${m(r.result.far_mm)}`.padEnd(30);
  }).join(""));
});
const out = emit(t, stamp, git, measured);
const head = out.points.find((p) => p.kpi === "verify_range_ms" && !p.slice);
console.log(`\nheadline verify_range_ms = ${head.value} ms (${head.labels.host ?? "none"}, ${head.status}); ${out.points.length} points, ${out.runs.length} runs`);
if (a.dry) {
  console.log("--dry: nothing written");
} else {
  fs.mkdirSync(path.join(a.out, "items"), { recursive: true });
  fs.writeFileSync(path.join(a.out, "kpi_catalog.json"), JSON.stringify(catalog(), null, 1) + "\n");
  fs.appendFileSync(path.join(a.out, "kpi_series.jsonl"), out.points.map((p) => JSON.stringify(p)).join("\n") + "\n");
  fs.appendFileSync(path.join(a.out, "runs_table.jsonl"), out.runs.map((r) => JSON.stringify(r)).join("\n") + "\n");
  for (const [id, lines] of Object.entries(out.items)) fs.writeFileSync(path.join(a.out, "items", `${id}.jsonl`), lines.map((l) => JSON.stringify(l)).join("\n") + "\n");
  console.log(`wrote ${a.out}`);
}
