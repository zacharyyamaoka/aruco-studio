// npm run test:parity: the facade (aruco_studio.web_api.call) in Pyodide
// (Node, the zip scripts/pack-core.mjs builds for the browser) and in
// CPython (the repo's .venv) on the same cases; the JSON answers must be
// byte-identical. Exit 1 on any difference. info() is compared without the
// fields that name the runtime (python, pyodide, core_version).
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { loadPyodide } from "pyodide";
import { packCore } from "./pack-core.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..", "..");
const PY = [path.join(root, ".venv", "bin", "python"), path.join(root, ".venv", "Scripts", "python.exe")]
  .find((p) => fs.existsSync(p));
const LIB = "/lib/aruco_studio";

const marker = (m = {}) => ({
  type: "single", dictionary: "DICT_4X4_50", first_id: 0, auto: true, marker_mm: 0, checker_mm: 0,
  separation_mm: 0, cols: 1, rows: 1, turn: 0, flip: false, quiet_modules: 1, corner_mark: "none", ...m,
});
const label = (l = {}) => ({ on: false, text: "", height_mm: 0, side: "below", gap_mm: 2, offset_mm: [0, 0], ...l });
const rect = (r = {}) => ({ cx: 0, cy: 0, w: 60, h: 40, angle_deg: 0, ...r });

function cases(presets) {
  const [d3, letter, a4] = presets;
  const req = (m, r = {}, l = {}, preset = letter, face = false) =>
    ({ rect: rect(r), marker: marker(m), label: label(l), preset, reference_face: face });
  const disc = (cx, cy, rad, n = 72) => Array.from({ length: n }, (_, k) =>
    [cx + rad * Math.cos(-2 * Math.PI * k / n), cy + rad * Math.sin(-2 * Math.PI * k / n)]);
  const plate = { loops: [[[-60, -40], [60, -40], [60, 40], [-60, 40]], disc(-35, 0, 10), disc(35, 0, 10)] };
  return [
    ["presets", "presets", {}],
    ["plan single auto", "plan", req({}, { w: 20, h: 20 })],
    ["plan single 30 mm in 20 x 20 (overflow)", "plan", req({ auto: false, marker_mm: 30 }, { w: 20, h: 20 })],
    ["plan grid 3x2 auto", "plan", req({ type: "grid", cols: 3, rows: 2 })],
    ["plan grid 2x1 manual, separation 5", "plan", req({ type: "grid", cols: 2, rows: 1, auto: false, marker_mm: 10, separation_mm: 5 })],
    ["plan grid turn 90, rotated rect", "plan", req({ type: "grid", cols: 3, rows: 2, auto: false, marker_mm: 12, turn: 90 }, { cx: 15, cy: -8, angle_deg: 30 })],
    ["plan charuco 5x4 auto", "plan", req({ type: "charuco", cols: 5, rows: 4 }, { w: 80, h: 60 })],
    ["plan charuco manual 9 / 13 mm", "plan", req({ type: "charuco", cols: 4, rows: 3, auto: false, marker_mm: 9, checker_mm: 13 }, { w: 80, h: 60 })],
    ["plan charuco 10 / 13 mm (no white round the marker: refused)", "plan", req({ type: "charuco", cols: 4, rows: 3, auto: false, marker_mm: 10, checker_mm: 13 }, { w: 80, h: 60 })],
    ["plan single flip + corner mark + label", "plan", req({ flip: true, first_id: 7, corner_mark: "triangle" }, { w: 30, h: 30, angle_deg: 12.5 }, { on: true, text: "{type} {dict} #{id}", side: "right" })],
    ["plan grid on a face, 3D printed (A4 unused)", "plan", req({ type: "grid", cols: 2, rows: 2 }, { w: 50, h: 50 }, {}, d3, true)],
    ["plan refused (100 markers on DICT_4X4_50)", "plan", req({ type: "grid", cols: 10, rows: 10 }, { w: 200, h: 200 }, {}, a4)],
    ["inscribe avoid", "inscribe", { profile: plate, holes: "avoid" }],
    ["inscribe ignore", "inscribe", { profile: plate, holes: "ignore" }],
    ["suggest grid", "suggest", req({ type: "grid" })],
    ["suggest charuco, 3D lines", "suggest", req({ type: "charuco" }, { w: 80, h: 60 }, {}, { ...d3, cell_step_mm: 0.675 })],
    ["svg single with label", "svg", req({ auto: false, marker_mm: 15 }, { w: 20, h: 20 }, { on: true, text: "#{id} {dict}" })],
    ["sheet letter, 3 items", "sheet", { items: [req({}, { w: 20, h: 20 }, { on: true, text: "part {id}" }), req({ type: "grid", cols: 3, rows: 2, first_id: 10 }), req({ auto: false, marker_mm: 300 }, { w: 300, h: 300 })], cut_lines: true, date: "2026-10-18" }],
    ["bad request", "plan", {}],
  ];
}

function cpython(calls) {
  const code = [
    "import json, sys",
    "from aruco_studio import web_api",
    "calls = json.load(sys.stdin)",
    "sys.stdout.write(json.dumps([web_api.call(n, p) for n, p in calls]))",
  ].join("\n");
  const r = spawnSync(PY, ["-c", code], {
    cwd: root, input: JSON.stringify(calls), encoding: "utf8", maxBuffer: 1 << 28,
    env: { ...process.env, PYTHONPATH: root, PYTHONDONTWRITEBYTECODE: "1" },
  });
  if (r.status !== 0) throw new Error(`CPython failed: ${r.stderr}`);
  return JSON.parse(r.stdout);
}

function firstDiff(a, b) {
  let i = 0;
  while (i < a.length && a[i] === b[i]) i++;
  return `at ${i}: pyodide …${a.slice(Math.max(0, i - 40), i + 40)}… cpython …${b.slice(Math.max(0, i - 40), i + 40)}…`;
}

if (!PY) throw new Error("no .venv python under the repo root");
const packed = packCore();
const t0 = performance.now();
const py = await loadPyodide();
py.unpackArchive(new Uint8Array(fs.readFileSync(packed.outFile)), "zip", { extractDir: LIB });
py.runPython(`import sys\nsys.path.insert(0, ${JSON.stringify(LIB)})`);
const api = py.pyimport("aruco_studio.web_api");
console.log(`parity: Pyodide ${py.version} + ${path.relative(root, packed.outFile)} loaded in ${Math.round(performance.now() - t0)} ms; CPython ${PY}`);

const presets = JSON.parse(api.call("presets", "{}")).result;
const extra = [];
const dir = path.join(here, "parity.d");     // a lane's own cases, one file each
for (const f of (fs.existsSync(dir) ? fs.readdirSync(dir) : []).filter((x) => x.endsWith(".mjs")).sort()) {
  const mod = await import(path.join(dir, f));
  extra.push(...mod.default(presets, { marker, label, rect }));
}
const list = [...cases(presets), ...extra];
const calls = list.map(([, name, payload]) => [name, JSON.stringify(payload)]);
const t1 = performance.now();
const inPyodide = calls.map(([n, p]) => api.call(n, p));
const pyodideMs = performance.now() - t1;
const t2 = performance.now();
const inCPython = cpython(calls);
const cpythonMs = performance.now() - t2;

let bad = 0;
list.forEach(([label], i) => {
  const a = inPyodide[i], b = inCPython[i];
  const same = a === b;
  if (!same) bad++;
  const kind = JSON.parse(a).error !== undefined ? "error" : "result";
  console.log(`${same ? "SAME" : "DIFF"}  ${label}  (${a.length} bytes, ${kind})${same ? "" : "\n      " + firstDiff(a, b)}`);
});
const strip = (s) => { const r = JSON.parse(s).result; delete r.python; delete r.pyodide; delete r.core_version; return JSON.stringify(r); };
const infoSame = strip(api.call("info", "{}")) === strip(cpython([["info", "{}"]])[0]);
if (!infoSame) bad++;
console.log(`${infoSame ? "SAME" : "DIFF"}  info (dictionaries)`);
console.log(`parity: ${list.length + 1 - bad} / ${list.length + 1} byte-identical (Pyodide ${Math.round(pyodideMs)} ms, CPython ${Math.round(cpythonMs)} ms incl. start)`);
process.exit(bad ? 1 : 0);
