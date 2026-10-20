// npm run bench:feature: how long ArUco Extrude takes to compute, the
// producer of Vibe Tracks' feature_compute_ms (vibetracks docs/peps/0005,
// contract vt-kpi/1). Zach, 2026-10-20: "time to compute the feature in CAD.
// It's really frustrating when it takes a while... performance matters."
//
//   node scripts/bench-feature.mjs                       cpython, pyodide-node, browser
//   node scripts/bench-feature.mjs --hosts cpython,pyodide-node --runs 30 --budget-s 8
//   node scripts/bench-feature.mjs --fusion perf.jsonl   + the Fusion add-in's own timings
//   node scripts/bench-feature.mjs --dry                 measure and print, write nothing
//
// The golden cases: single, grid 3x1 / 3x3, ChArUco 5x4 / 8x2, each on a
// face profile with holes and on a rectangle profile, under an inkjet and a
// 3D-print preset, through web_api.plan (what the panel waits for) and
// web_api.svg; the requests are the app's own (model/doc.ts planRequest,
// extrude always sent). WHY these: they are the Fusion host's golden cases
// too, so the hosts line up; a 3x1 grid in Fusion was Zach's complaint.
//
// Hosts, one fresh runtime per case so its first call is a true cold one:
//   cpython        tools/bench_feature.py in the repo's .venv
//   pyodide-node   this file again (--pyodide-worker) on the zip pack-core builds
//   browser        the static build under `vite preview` on --port (5396),
//                  headless Chrome, window.__aruco.plan through the core's
//                  worker (plan only: the probe has no svg)
//   fusion         --fusion <perf.jsonl>, the add-in's lines (Windows:
//                  %USERPROFILE%\CADExporter\_aruco_perf\perf.jsonl), read,
//                  never measured here; each line read once (fusion_seen.json)
// cold = the first call (startup, the runtime's load and import, apart);
// warm = up to --runs more calls of the same request, as median and p95.
//
// Writes ~/.local/share/aruco_studio_bench/kpi (--out): kpi_catalog.json,
// kpi_series.jsonl and runs_table.jsonl (appended), items/<run_id>.jsonl.
// A host not measured is a null point, never 0.
import { spawn, spawnSync } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.resolve(here, "..");
const root = path.resolve(web, "..");
const LIB = "/lib/aruco_studio";
const BENCH_VERSION = "feature-bench/1";
const FEATURE = "aruco_extrude";
const HOSTS = ["cpython", "pyodide-node", "browser", "fusion"];
const MIN_WARM = 10;   // tools/bench_feature.py's too

// ------------------------------------------------------------------ the Pyodide worker: one case, stdin -> stdout

if (process.argv[2] === "--pyodide-worker") {
  const { loadPyodide } = await import("pyodide");
  const c = JSON.parse(fs.readFileSync(0, "utf8"));
  const t0 = performance.now();
  const py = await loadPyodide();
  py.unpackArchive(new Uint8Array(fs.readFileSync(process.argv[3])), "zip", { extractDir: LIB });
  py.runPython(`import sys\nsys.path.insert(0, ${JSON.stringify(LIB)})`);
  const api = py.pyimport("aruco_studio.web_api");
  const startup = performance.now() - t0;
  const text = JSON.stringify(c.payload);
  let t = performance.now();
  const out = api.call(c.call, text);
  const cold = performance.now() - t;
  const warm = [];
  const spent = performance.now();
  while (warm.length < c.runs) {
    t = performance.now();
    api.call(c.call, text);
    warm.push(performance.now() - t);
    if (warm.length >= MIN_WARM && performance.now() - spent > c.budget_s * 1000) break;
  }
  process.stdout.write(JSON.stringify({ host: "pyodide-node", runtime: `Pyodide ${py.version} in Node ${process.version}`,
    startup_ms: startup, cold_ms: cold, warm_ms: warm, bytes: out.length, error: JSON.parse(out).error ?? null }));
  process.exit(0);
}

// ------------------------------------------------------------------ arguments

function args(argv) {
  const a = { hosts: ["cpython", "pyodide-node", "browser"], runs: 30, budget_s: 8, port: 5396, fusion: [],
    out: path.join(os.homedir(), ".local", "share", "aruco_studio_bench", "kpi"), dry: false, build: true };
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i], v = () => argv[++i];
    if (k === "--hosts") a.hosts = v().split(",").filter(Boolean);
    else if (k === "--runs") a.runs = Number(v());
    else if (k === "--budget-s") a.budget_s = Number(v());
    else if (k === "--port") a.port = Number(v());
    else if (k === "--fusion") a.fusion.push(path.resolve(v()));
    else if (k === "--out") a.out = path.resolve(v());
    else if (k === "--dry") a.dry = true;
    else if (k === "--no-build") a.build = false;
    else throw new Error(`unknown argument ${k}`);
  }
  for (const h of a.hosts) if (!HOSTS.includes(h) || h === "fusion") throw new Error(`--hosts: ${h} is not one of cpython, pyodide-node, browser`);
  return a;
}

// ------------------------------------------------------------------ the golden cases

const PY = [path.join(root, ".venv", "bin", "python"), path.join(root, ".venv", "Scripts", "python.exe")]
  .find((p) => fs.existsSync(p));

function python(code, input = "") {
  const r = spawnSync(PY, ["-c", code], { cwd: root, input, encoding: "utf8", maxBuffer: 1 << 28,
    env: { ...process.env, PYTHONPATH: root, PYTHONDONTWRITEBYTECODE: "1" } });
  if (r.status !== 0) throw new Error(`CPython failed: ${r.stderr}`);
  return r.stdout;
}

const marker = (m = {}) => ({
  type: "single", dictionary: "DICT_4X4_50", first_id: 0, auto: true, marker_mm: 0, checker_mm: 0,
  separation_mm: 0, cols: 1, rows: 1, turn: 0, flip: false, quiet_modules: 1, corner_mark: "none", ...m,
});
const label = { on: false, text: "", height_mm: 0, side: "below", gap_mm: 2, offset_mm: [0, 0] };
const disc = (cx, cy, rad, n = 72) => Array.from({ length: n }, (_, k) =>
  [cx + rad * Math.cos(-2 * Math.PI * k / n), cy + rad * Math.sin(-2 * Math.PI * k / n)]);
// the parity suite's plate (a 120 x 80 face, two 20 mm holes) and a 60 x 40 rectangle
const PROFILES = {
  face: { loops: [[[-60, -40], [60, -40], [60, 40], [-60, 40]], disc(-35, 0, 10), disc(35, 0, 10)] },
  rectangle: { loops: [[[-30, -20], [30, -20], [30, 20], [-30, 20]]] },
};
const LAYOUTS = [["single", 1, 1], ["grid", 3, 1], ["grid", 3, 3], ["charuco", 5, 4], ["charuco", 8, 2]];

function goldenCases(presets) {
  const byMethod = { inkjet: presets.find((p) => p.method === "inkjet"), print3d: presets.find((p) => p.method === "print3d") };
  const out = [];
  for (const [type, cols, rows] of LAYOUTS) {
    for (const [profileKind, profile] of Object.entries(PROFILES)) {
      for (const [method, preset] of Object.entries(byMethod)) {
        for (const call of ["plan", "svg"]) {
          const facets = { feature: FEATURE, marker_type: type, cells: cols * rows, layout: `${cols}x${rows}`,
            profile_kind: profileKind, method, call };
          out.push({ id: [type, `${cols}x${rows}`, profileKind, method, call].join("-"), call, facets,
            payload: { trim: "profile", profile, holes: "avoid", marker: marker({ type, cols, rows }), label,
              preset, reference_face: false, extrude: {} } });
        }
      }
    }
  }
  return out;
}

// ------------------------------------------------------------------ hosts

function child(cmd, argv, c, a) {
  const r = spawnSync(cmd, argv, { cwd: root, encoding: "utf8", maxBuffer: 1 << 28,
    input: JSON.stringify({ call: c.call, payload: c.payload, runs: a.runs, budget_s: a.budget_s }),
    env: { ...process.env, PYTHONPATH: root, PYTHONDONTWRITEBYTECODE: "1" } });
  if (r.status !== 0) throw new Error(`${c.id}: ${cmd} failed: ${r.stderr}`);
  return JSON.parse(r.stdout);
}

function runCpython(cases, a) {
  return cases.map((c) => child(PY, [path.join(root, "tools", "bench_feature.py")], c, a));
}

async function runPyodide(cases, a) {
  const { packCore } = await import("./pack-core.mjs");
  const zipFile = path.join(os.tmpdir(), `aruco_studio-bench-${process.pid}.zip`);
  packCore(zipFile);
  try {
    return cases.map((c) => child(process.execPath, [fileURLToPath(import.meta.url), "--pyodide-worker", zipFile], c, a));
  } finally {
    fs.rmSync(zipFile, { force: true });
  }
}

async function waitFor(url, ms, proc) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    if (proc.exitCode !== null) return false;
    try { if ((await fetch(url)).ok) return true; } catch { /* not up yet */ }
    await new Promise((r) => setTimeout(r, 250));
  }
  return false;
}

/** The browser host: null (with why) when it cannot run, never a guess. */
async function runBrowser(cases, a) {
  const plans = cases.filter((c) => c.call === "plan");
  if (a.build) {
    const b = spawnSync("npm", ["run", "build"], { cwd: web, encoding: "utf8", maxBuffer: 1 << 28 });
    if (b.status !== 0) return { skipped: `npm run build failed: ${(b.stderr || b.stdout).slice(-400)}` };
  }
  if (!fs.existsSync(path.join(web, "dist", "index.html"))) return { skipped: "no web/dist (run without --no-build)" };
  const url = `http://127.0.0.1:${a.port}/`;
  const server = spawn(path.join(web, "node_modules", ".bin", "vite"),
    ["preview", "--host", "127.0.0.1", "--port", String(a.port), "--strictPort"], { cwd: web, stdio: ["ignore", "pipe", "pipe"] });
  let log = "";
  server.stdout.on("data", (d) => { log += d; });
  server.stderr.on("data", (d) => { log += d; });
  let browser = null;
  try {
    // WHY strictPort and no kill on "in use": a busy port is Zach's or a peer's server, never ours to stop
    if (!(await waitFor(url, 30000, server))) return { skipped: `vite preview on ${a.port} did not come up: ${log.trim().slice(-300)}` };
    const { chromium } = await import("@playwright/test");
    browser = await chromium.launch({ channel: "chrome", headless: true });
    const out = [];
    for (const c of plans) {
      const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
      const page = await ctx.newPage();
      await page.goto(url);
      await page.waitForFunction(() => window.__aruco && window.__aruco.state().core.state !== "loading", null, { timeout: 120000 });
      const r = await page.evaluate(async ({ payload, runs, budget_s, minWarm }) => {
        const p = window.__aruco;
        const s = p.state();
        if (s.core.state !== "ready") return { error: `core ${s.core.state}: ${s.core.detail}` };
        await p.idle(60000);
        let t = performance.now(), error = null, bytes = null;
        try { bytes = JSON.stringify(await p.plan(payload)).length; } catch (e) { error = String(e); }
        const cold = performance.now() - t;
        const warm = [];
        const spent = performance.now();
        while (warm.length < runs) {
          t = performance.now();
          try { await p.plan(payload); } catch { /* timed all the same; the cold call said why */ }
          warm.push(performance.now() - t);
          if (warm.length >= minWarm && performance.now() - spent > budget_s * 1000) break;
        }
        return { startup_ms: s.core.ms ?? null, cold_ms: cold, warm_ms: warm, bytes, error,
          app_plans: Object.keys(s.plans || {}).length, ua: navigator.userAgent };
      }, { payload: c.payload, runs: a.runs, budget_s: a.budget_s, minWarm: MIN_WARM });
      await ctx.close();
      const chrome = /Chrome\/([\d.]+)/.exec(r.ua || "")?.[1];
      out.push({ host: "browser", runtime: `Pyodide worker in headless Chrome ${chrome ?? "?"}`, ...r });
    }
    return { results: out, plans };
  } finally {
    if (browser) await browser.close();
    server.kill("SIGTERM");   // the preview this run started, by its own handle
  }
}

// ------------------------------------------------------------------ Fusion's perf.jsonl

const FUSION_PARTS = { total: "ms_total", core: "ms_core", fusion: "ms_fusion" };

function fusionType(v) {
  const s = String(v ?? "").toLowerCase();
  return s.includes("charuco") ? "charuco" : s.includes("grid") ? "grid" : s ? (s === "aruco" ? "single" : s) : null;
}

function fusionProfile(v) {
  const s = String(v ?? "").toLowerCase();
  return s.includes("face") ? "face" : /rect|sketch|profile/.test(s) ? "rectangle" : s || null;
}

/** Lines of perf.jsonl not read before: {ts, op, node_kind, marker_type, cells, bodies, ms_core, ms_fusion, ms_total, substeps}. */
function readFusion(files, seenFile) {
  const seen = new Set(fs.existsSync(seenFile) ? JSON.parse(fs.readFileSync(seenFile, "utf8")).lines : []);
  const fresh = [], problems = [];
  for (const f of files) {
    if (!fs.existsSync(f)) { problems.push(`${f}: no such file`); continue; }
    fs.readFileSync(f, "utf8").split(/\r?\n/).forEach((line, i) => {
      if (!line.trim()) return;
      const h = crypto.createHash("sha1").update(line.trim()).digest("hex");
      if (seen.has(h)) return;
      let row;
      try { row = JSON.parse(line); } catch { problems.push(`${path.basename(f)}:${i + 1}: not JSON`); return; }
      seen.add(h);
      fresh.push({ ...row, _line: `${path.basename(f)}:${i + 1}` });
    });
  }
  return { fresh, seen: [...seen], problems };
}

// ------------------------------------------------------------------ statistics and the vt-kpi/1 directory

function median(xs) {
  if (!xs.length) return null;
  const s = [...xs].sort((x, y) => x - y), m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}
/** Nearest rank: the smallest sample with at least 95 % of the samples at or below it. */
function p95(xs) {
  if (!xs.length) return null;
  const s = [...xs].sort((x, y) => x - y);
  return s[Math.ceil(0.95 * s.length) - 1];
}
const r3 = (v) => (v == null ? null : Math.round(v * 1000) / 1000);
const maxBy = (rows, f) => rows.reduce((best, r) => (f(r) != null && (best == null || f(r) > f(best)) ? r : best), null);

function gitSha() {
  const r = spawnSync("git", ["rev-parse", "--short=8", "HEAD"], { cwd: root, encoding: "utf8" });
  const dirty = spawnSync("git", ["status", "--porcelain", "--", "aruco_studio"], { cwd: root, encoding: "utf8" }).stdout.trim();
  return { sha: r.status === 0 ? r.stdout.trim() : null, dirty: dirty ? dirty.split("\n").length : 0 };
}

function catalog() {
  const facets = ["feature", "host", "phase", "marker_type", "cells", "layout", "profile_kind", "method", "call", "part"];
  return {
    schema: "vt-kpi-catalog/1", unit_of_iteration: "run",
    title: "CAD feature compute time (ArUco Studio)",
    producer: { name: "aruco-studio web/scripts/bench-feature.mjs", bench_version: BENCH_VERSION,
      hosts: HOSTS, features: [FEATURE] },
    kpis: [
      { id: "feature_compute_ms", title: "CAD feature compute time (p95)", unit: "ms", direction: "lower", level: 0,
        parent: null, target: null, computed_from: "runs", scale: "linear",
        description: "How long a CAD feature takes to compute, warm: the slowest golden case's 95th-percentile call. " +
          "The whole-bench point is web_api.plan in the browser's worker (what the panel waits for); hollow when " +
          "Pyodide in Node stood in for an unmeasured browser. Slices carry each host, case and phase (a cold " +
          "slice is the one first call; a Fusion slice's phase is the add-in's op).",
        formula: "max over golden plan cases of p95(warm call ms), browser host",
        facets, reference_lines: [{ value: 100, label: "100 ms: feels instant (suggested, not a gate)" }] },
      { id: "feature_compute_ms_p50", title: "CAD feature compute time (median)", unit: "ms", direction: "lower", level: 1,
        parent: "feature_compute_ms", target: null, computed_from: "runs", scale: "linear",
        description: "The same cases as the headline, the median warm call instead of the p95: the typical wait.",
        formula: "max over golden plan cases of median(warm call ms), browser host", facets },
    ],
    gates: [],
  };
}

/** Per measured host and case: one run, its items file, and its slice points. */
function emit(a, t, stamp, git, measured, fusionRows, lastSha) {
  const runs = [], points = [], items = {};
  const source = (ids) => ({ code_sha: git.sha, ...(git.dirty ? { dirty_files: git.dirty } : {}), bench_version: BENCH_VERSION, run_ids: ids });
  const point = (kpi, value, slice, n, ids, labels, status = "measured") => points.push({ schema: "vt-kpi-point/1", kpi, t,
    value: r3(value), n, status, ...(slice ? { slice } : {}), labels, source: source(ids) });
  const cases = [];   // {host, facets, run_id, cold, warm95, warm50, n}

  for (const [host, list] of Object.entries(measured)) {
    for (const { c, r } of list) {
      const run_id = `${stamp}-${host}-${c.id}`;
      const lines = [{ item_id: `${run_id}#cold`, phase: "cold", latency_ms: r3(r.cold_ms), facets: { phase: "cold" } },
        ...r.warm_ms.map((ms, i) => ({ item_id: `${run_id}#w${i + 1}`, phase: "warm", latency_ms: r3(ms), facets: { phase: "warm" } }))];
      items[run_id] = lines;
      const facets = { ...c.facets, host, lane: host };
      runs.push({ schema: "vt-run/1", run_id, t, facets,
        metrics: { cold_calls: 1, cold_ms_sum: r3(r.cold_ms), warm_calls: r.warm_ms.length,
          warm_ms_sum: r3(r.warm_ms.reduce((x, y) => x + y, 0)), startup_ms_sum: r3(r.startup_ms), startups: r.startup_ms == null ? 0 : 1 },
        detail: { runtime: r.runtime, bytes: r.bytes, error: r.error, ...(r.app_plans != null ? { app_plans_at_ready: r.app_plans } : {}) },
        items: { path: `items/${run_id}.jsonl`, schema: "aruco-feature-sample/1", n: lines.length } });
      cases.push({ host, facets: c.facets, run_id, cold: r.cold_ms, warm95: p95(r.warm_ms), warm50: median(r.warm_ms), n: r.warm_ms.length, error: r.error });
    }
  }

  const labels = (host, extra = {}) => ({ lane: host, host, ...extra });
  for (const k of cases) {
    const s = { ...k.facets, host: k.host };
    point("feature_compute_ms", k.warm95, { ...s, phase: "warm" }, k.n, [k.run_id], labels(k.host));
    point("feature_compute_ms_p50", k.warm50, { ...s, phase: "warm" }, k.n, [k.run_id], labels(k.host));
    point("feature_compute_ms", k.cold, { ...s, phase: "cold" }, 1, [k.run_id], labels(k.host));
  }

  // per host: its slowest plan case (the headline's rule), cold beside it; a host not measured is null
  const planOf = (host) => cases.filter((k) => k.host === host && k.facets.call === "plan");
  for (const host of HOSTS.filter((h) => h !== "fusion")) {
    const list = planOf(host);
    if (!list.length) {
      point("feature_compute_ms", null, { host }, 0, [], labels(host), "not_measured");
      continue;
    }
    const w95 = maxBy(list, (k) => k.warm95), w50 = maxBy(list, (k) => k.warm50), cold = maxBy(list, (k) => k.cold);
    const ids = list.map((k) => k.run_id);
    point("feature_compute_ms", w95.warm95, { host }, w95.n, ids, labels(host, { slowest: w95.run_id }));
    point("feature_compute_ms_p50", w50.warm50, { host }, w50.n, ids, labels(host, { slowest: w50.run_id }));
    point("feature_compute_ms", cold.cold, { host, phase: "cold" }, 1, ids, labels(host, { slowest: cold.run_id }));
  }

  // the headline: the browser's worker, else Pyodide in Node standing in (hollow), else CPython (hollow)
  const head = ["browser", "pyodide-node", "cpython"].find((h) => planOf(h).length);
  if (head) {
    const list = planOf(head), ids = list.map((k) => k.run_id);
    const status = head === "browser" ? "measured" : "stand-in";
    const event = git.sha && git.sha !== lastSha ? { event: git.sha } : {};
    const w95 = maxBy(list, (k) => k.warm95), w50 = maxBy(list, (k) => k.warm50);
    point("feature_compute_ms", w95.warm95, null, w95.n, ids, labels(head, { slowest: w95.run_id, ...event }), status);
    point("feature_compute_ms_p50", w50.warm50, null, w50.n, ids, labels(head, { slowest: w50.run_id }), status);
    // one-facet breakdowns on the headline host (the drill-down's "Slice by" table reads these)
    for (const facet of ["feature", "marker_type", "layout", "profile_kind", "method"]) {
      for (const value of [...new Set(list.map((k) => k.facets[facet]))]) {
        const sub = list.filter((k) => k.facets[facet] === value), w = maxBy(sub, (k) => k.warm95);
        point("feature_compute_ms", w.warm95, { [facet]: value }, w.n, sub.map((k) => k.run_id), labels(head, { slowest: w.run_id }), status);
      }
    }
    const allHost = cases.filter((k) => k.host === head);
    for (const call of [...new Set(allHost.map((k) => k.facets.call))]) {
      const sub = allHost.filter((k) => k.facets.call === call), w = maxBy(sub, (k) => k.warm95);
      point("feature_compute_ms", w.warm95, { call }, w.n, sub.map((k) => k.run_id), labels(head, { slowest: w.run_id }), status);
    }
    const c = maxBy(list, (k) => k.cold);
    point("feature_compute_ms", c.cold, { phase: "cold" }, 1, ids, labels(head, { slowest: c.run_id }), status);
  } else {
    point("feature_compute_ms", null, null, 0, [], { lane: "none" }, "not_measured");
  }

  // Fusion: the add-in's lines, grouped by op x marker x cells x profile; core and Fusion halves as a part facet
  if (fusionRows.length) {
    const fstamp = fusionRows.map((x) => x.ts).filter(Boolean).sort().pop() ?? t;
    const groups = {};
    for (const row of fusionRows) {
      const f = { feature: FEATURE, host: "fusion", phase: row.op ?? null, marker_type: fusionType(row.marker_type),
        cells: row.cells ?? null, profile_kind: fusionProfile(row.node_kind) };
      const key = JSON.stringify(f);
      (groups[key] = groups[key] || { f, rows: [] }).rows.push(row);
    }
    // WHY no aruco-studio sha on Fusion points: the add-in's code is whatever ran on Windows, not this checkout
    const fsha = fusionRows.map((x) => x.code_sha ?? x.sha ?? null).filter(Boolean).pop() ?? null;
    const fsource = (ids) => ({ code_sha: fsha, bench_version: BENCH_VERSION, run_ids: ids });
    const halves = { total: [], core: [], fusion: [] };
    for (const { f, rows } of Object.values(groups)) {
      const run_id = `${stamp}-fusion-${[f.phase, f.marker_type, f.cells, f.profile_kind].join("-")}`.replace(/[^\w.-]+/g, "_");
      items[run_id] = rows.map((row, i) => ({ item_id: `${run_id}#${i + 1}`, t: row.ts ?? null, latency_ms: row.ms_total ?? null,
        ms_core: row.ms_core ?? null, ms_fusion: row.ms_fusion ?? null, bodies: row.bodies ?? null,
        facets: { phase: f.phase, node_kind: row.node_kind ?? null, marker_type: row.marker_type ?? null }, substeps: row.substeps ?? null, line: row._line }));
      const sum = (k) => r3(rows.reduce((x, row) => x + (typeof row[k] === "number" ? row[k] : 0), 0));
      runs.push({ schema: "vt-run/1", run_id, t: fstamp, facets: { ...f, lane: "fusion" },
        metrics: { calls: rows.length, ms_total_sum: sum("ms_total"), ms_core_sum: sum("ms_core"), ms_fusion_sum: sum("ms_fusion"), bodies_sum: sum("bodies") },
        items: { path: `items/${run_id}.jsonl`, schema: "aruco-fusion-perf/1", n: rows.length } });
      for (const [part, field] of Object.entries(FUSION_PARTS)) {
        const xs = rows.map((row) => row[field]).filter((v) => typeof v === "number");
        if (!xs.length) continue;
        halves[part].push({ v: p95(xs), n: xs.length, run_id });
        points.push({ schema: "vt-kpi-point/1", kpi: "feature_compute_ms", t: fstamp, value: r3(p95(xs)), n: xs.length, status: "measured",
          slice: { ...f, part }, labels: labels("fusion"), source: fsource([run_id]) });
        points.push({ schema: "vt-kpi-point/1", kpi: "feature_compute_ms_p50", t: fstamp, value: r3(median(xs)), n: xs.length, status: "measured",
          slice: { ...f, part }, labels: labels("fusion"), source: fsource([run_id]) });
      }
    }
    // the slow half, visible: each part's slowest group, and the host's slowest total
    for (const [part, list] of Object.entries(halves)) {
      const w = maxBy(list, (x) => x.v);
      if (!w) continue;
      const slice = part === "total" ? { host: "fusion" } : { part };
      points.push({ schema: "vt-kpi-point/1", kpi: "feature_compute_ms", t: fstamp, value: r3(w.v), n: w.n, status: "measured",
        slice, labels: labels("fusion", { slowest: w.run_id }), source: fsource(list.map((x) => x.run_id)) });
    }
  } else {
    point("feature_compute_ms", null, { host: "fusion" }, 0, [], labels("fusion"), "not_measured");
  }
  return { runs, points, items, cases, head };
}

// ------------------------------------------------------------------ main

const a = args(process.argv.slice(2));
if (!PY) throw new Error("no .venv python under the repo root");
const presets = JSON.parse(python("import json\nfrom aruco_studio import web_api\nprint(web_api.call('presets', '{}'))")).result;
const cases = goldenCases(presets);
const git = gitSha();
const started = new Date();
const t = started.toISOString().replace(/\.\d+Z$/, "Z");
const stamp = t.replace(/[-:]/g, "").replace("T", "-").replace("Z", "");
console.log(`bench-feature: ${cases.length} cases, hosts ${a.hosts.join(", ")}, aruco-studio ${git.sha}${git.dirty ? ` (+${git.dirty} dirty)` : ""}, ${BENCH_VERSION}`);

const measured = {};
const skipped = {};
for (const host of a.hosts) {
  const t0 = performance.now();
  if (host === "cpython") measured.cpython = runCpython(cases, a).map((r, i) => ({ c: cases[i], r }));
  else if (host === "pyodide-node") measured["pyodide-node"] = (await runPyodide(cases, a)).map((r, i) => ({ c: cases[i], r }));
  else if (host === "browser") {
    const b = await runBrowser(cases, a);
    if (b.skipped) { skipped.browser = b.skipped; console.log(`  browser: not measured (${b.skipped})`); continue; }
    measured.browser = b.results.map((r, i) => ({ c: b.plans[i], r }));
  }
  const startups = measured[host].map(({ r }) => r.startup_ms).filter((v) => v != null);
  console.log(`  ${host}: ${measured[host].length} cases in ${((performance.now() - t0) / 1000).toFixed(1)} s; ` +
    `startup (load + import, apart from cold) median ${startups.length ? median(startups).toFixed(0) : "null"} ms; ${measured[host][0]?.r.runtime ?? ""}`);
}

fs.mkdirSync(path.join(a.out, "items"), { recursive: true });
const seenFile = path.join(a.out, "fusion_seen.json");
const fusion = a.fusion.length ? readFusion(a.fusion, seenFile) : { fresh: [], seen: null, problems: [] };
for (const p of fusion.problems) console.log(`  fusion: ${p}`);
if (a.fusion.length) console.log(`  fusion: ${fusion.fresh.length} new lines from ${a.fusion.join(", ")}`);

const seriesFile = path.join(a.out, "kpi_series.jsonl");
const lastSha = fs.existsSync(seriesFile) ? fs.readFileSync(seriesFile, "utf8").trim().split("\n").filter(Boolean)
  .map((l) => { try { return JSON.parse(l); } catch { return null; } })
  .filter((p) => p && p.kpi === "feature_compute_ms" && !p.slice && p.value != null).map((p) => p.source?.code_sha).pop() : null;
const out = emit(a, t, stamp, git, measured, fusion.fresh, lastSha);

const fmt = (v) => (v == null ? "null" : v.toFixed(1).padStart(7));
console.log("\nhost          case                                    cold ms   warm p50   warm p95   n");
for (const k of [...out.cases].sort((x, y) => (y.warm95 ?? 0) - (x.warm95 ?? 0))) {
  const id = [k.facets.marker_type, k.facets.layout, k.facets.profile_kind, k.facets.method, k.facets.call].join(" ");
  console.log(`${k.host.padEnd(13)} ${id.padEnd(38)} ${fmt(k.cold)}   ${fmt(k.warm50)}    ${fmt(k.warm95)}  ${String(k.n).padStart(3)}${k.error ? `  ERROR ${k.error}` : ""}`);
}
const headline = out.points.find((p) => p.kpi === "feature_compute_ms" && !p.slice);
console.log(`\nheadline feature_compute_ms = ${headline.value} ms (${headline.labels.host ?? "none"}, ${headline.status}); ${out.points.length} points, ${out.runs.length} runs`);

if (a.dry) {
  console.log("--dry: nothing written");
} else {
  fs.writeFileSync(path.join(a.out, "kpi_catalog.json"), JSON.stringify(catalog(), null, 1) + "\n");
  fs.appendFileSync(seriesFile, out.points.map((p) => JSON.stringify(p)).join("\n") + "\n");
  fs.appendFileSync(path.join(a.out, "runs_table.jsonl"), out.runs.map((r) => JSON.stringify(r)).join("\n") + "\n");
  for (const [id, lines] of Object.entries(out.items)) {
    fs.writeFileSync(path.join(a.out, "items", `${id}.jsonl`), lines.map((l) => JSON.stringify(l)).join("\n") + "\n");
  }
  if (fusion.seen) fs.writeFileSync(seenFile, JSON.stringify({ lines: fusion.seen }) + "\n");
  console.log(`wrote ${a.out}`);
}
