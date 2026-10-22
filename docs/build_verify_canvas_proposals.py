"""Verify ON the canvas: 5 proposals, a babble gallery (Zach's feedback, 2026-10-21).

    python3 docs/build_verify_canvas_proposals.py               # data (cached) + capture (cached) + gallery + review
    python3 docs/build_verify_canvas_proposals.py --recompute   # the CPython numbers again (both OpenCVs)
    python3 docs/build_verify_canvas_proposals.py --recapture   # the live canvas and the browser timings again
    python3 docs/build_verify_canvas_proposals.py --no-review   # skip the 1280 / 390 renders

What Zach asked for (2026-10-21, after the unit-test round and V4 "Range strip"
going live): the live badge, marimo-style -- a marker turns green once verified
and fades, only errors stay; Verify flashes the cached passes and recomputes
what needs it, lazily, with spinners and results streaming in; the reach fan,
symmetric about the marker's axis; results ON the canvas so nothing needs to
be associated; concrete, numeric pass / fail ("a label fails if it makes you
miss more than x % compared to no label"); caching "essential".

The steps (each re-runnable; the cached ones kept unless asked):

1. data     CPython, both OpenCVs (.venv's 5.0, .venv-cv411's 4.11, the
            browser's today): on the 28-marker Label placement board
            (web/public/examples/label-placement.arucostudio-web.json), each
            marker's reading range on the D435 as planned and bare (label off,
            no corner mark) -- web_verify.reading_range, the live engine
            (core reading-range/1) --; the symmetric reach fan (the same engine
            with the camera held at +/- 0..75 deg of yaw) for three markers; the
            pose error of every marker at 0.3 and 0.5 m (24 Field cameras); the
            verify key (the scene in the marker's own frame) against today's
            request key under eight real edits. The label's read cost is the
            guide's own run (verify.json: web_marks.check v1, both OpenCVs).
2. capture  headless Chrome (playwright, from a temporary script outside the
            repo) on the running Preview (127.0.0.1:5383, main): the board at
            1440 x 900 as layers -- the canvas, the printed geometry alone, the
            app's chrome alone -- and each marker's box on screen; then the
            browser's own timings: one range computed cold in the core's
            Pyodide worker, and the cached path (28 lookups: today's
            localStorage store, and IndexedDB) repeated.
3. gallery  the babble skill's gallery.py; every mock is drawn over those
            captured layers in the canvas's own pixel frame.
4. review   the built page rendered headless at 1280 and 390 wide, every story
            step of every card; the PNGs land in the -src/review folder.

Writes reports/media/verify-on-canvas-proposals-2026-10-21.html (gitignored,
with its -src/ folder). Nothing in web/ or aruco_studio/ is changed.
"""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import html
import json
import math
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

NAME = "verify-on-canvas-proposals-2026-10-21"
OUT = ROOT / "reports" / "media" / f"{NAME}.html"
SRC = ROOT / "reports" / "media" / f"{NAME}-src"
DATA = SRC / "data.json"
SHOTS = SRC / "shots"
REVIEW = SRC / "review"
BOARD = ROOT / "web" / "public" / "examples" / "label-placement.arucostudio-web.json"
GUIDE = ROOT / "web" / "public" / "guides" / "label-placement" / "verify.json"
PREVIEW = os.environ.get("VC_SITE", "http://127.0.0.1:5383/")
GALLERY = Path.home() / "zach_brain" / "Settings" / "Skills" / "babble" / "scripts" / "gallery.py"
PYTHONS = {"5.0.0": ROOT / ".venv" / "bin" / "python", "4.11.0": ROOT / ".venv-cv411" / "bin" / "python"}
NEWEST = "5.0.0"          # Zach, 2026-10-21: one OpenCV, selectable, the newest by default
CAMERA = "d435"           # the camera BAM owns (core.cameras)
FAN_ANGLES = [-75.0, -60.0, -45.0, -30.0, -15.0, 0.0, 15.0, 30.0, 45.0, 60.0, 75.0]
FAN_KEYS = ["A1", "B6", "E2"]
POSE_AT = [300.0, 500.0]
POSE_CASES = 24
E = html.escape


# ================================================================== 1. data

def board() -> tuple[dict, list]:
    """The guide's board and its 28 cases in board order: key, title, group, feature, request."""
    doc = json.loads(BOARD.read_text())
    guide = json.loads(GUIDE.read_text())
    by_fid = {f["id"]: f for f in doc["features"]}
    cases = []
    for c in guide["cases"]:
        f = by_fid[c["feature"]]
        cases.append({"key": c["key"], "title": c["title"], "group": c["group"], "fid": c["feature"],
                      "number": c["number"], "req": plan_request(doc, f)})
    return doc, cases


def rect_corners(r: dict) -> list:
    """web/src/model/geom.ts rectCorners (docs/build_guides.py's copy)."""
    a = r["angle_deg"] * math.pi / 180.0
    c, s = math.cos(a), math.sin(a)
    hw, hh = r["w"] / 2.0, r["h"] / 2.0
    return [[r["cx"] + u * c - v * s, r["cy"] + u * s + v * c] for u, v in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh))]


def plan_request(doc: dict, f: dict) -> dict:
    """web/src/model/doc.ts planRequest for a feature on a plain rectangle (the board's only kind)."""
    shape = next(s for s in doc["shapes"] if s["id"] == f["profile"]["outer"])
    return {"trim": f["trim"], "profile": {"loops": [rect_corners(shape)]}, "holes": f["holes"],
            "marker": f["marker"], "label": f["label"], "preset": f["preset"], "reference_face": False,
            "extrude": f["extrude"]}


def bare(req: dict) -> dict:
    """The same marker with nothing printed beside it: no label, no corner mark."""
    r = copy.deepcopy(req)
    r["label"] = dict(r["label"], on=False)
    r["marker"] = dict(r["marker"], corner_mark="none")
    return r


def _small(rr: dict) -> dict:
    keep = ("near_mm", "far_mm", "band_mm", "pm", "near_by", "far_limit", "far_px_per_cell", "weakest_id",
            "renders", "opencv", "measured", "reason")
    return {k: rr.get(k) for k in keep}


def _job(args):
    """One unit of CPython work (in a worker process; this Python's OpenCV)."""
    kind = args["kind"]
    from aruco_studio import web_verify as V
    from aruco_studio.core import reading_range as RR
    t0 = time.perf_counter()
    if kind == "range":
        out = _small(V.reading_range(args["req"], CAMERA))
    elif kind == "fan":
        # the live engine, the camera held at one yaw: each case keeps its own
        # blur, grain, glare and seed from the Field budget, its tilt replaced
        geo, cam, read, measured = V._range_setup(args["req"], CAMERA)
        yaw = float(args["angle"])

        def at(distance_mm, view):
            return read(distance_mm, dict(view, tilt_deg=0.0, yaw_deg=yaw))
        out = _small(V._finish(RR.run(RR.sweep(geo, cam, RR.DEFAULT_BUDGET, RR.N_CASES, RR.SEED), at), cam, measured))
        out["angle"] = yaw
    elif kind == "check":
        from aruco_studio import web_marks as M
        c = M.check(args["req"])
        out = {k: c[k] for k in ("verdict", "reads_verdict", "cost_pts", "p", "lost", "gained", "easy", "text", "views")}
        out["pose"] = {k: c["pose"][k] for k in ("verdict", "growth", "p", "worse", "better", "judged")}
        out["opencv"] = __import__("cv2").__version__
    elif kind == "rules":
        from aruco_studio import web_api as W
        plan = W.plan(args["req"])
        hits = [w["text"] for w in plan.get("warnings", [])
                if w["level"] in ("warn", "error") and w["field"].startswith(("label.", "marker.corner_mark"))]
        out = {"verdict": "unsafe" if hits else "safe", "hits": hits}
    elif kind == "pose":
        from aruco_studio.verify import camera as C
        req = V.placed(args["req"])
        d = V._plan(req)
        scene = C.scene_of(d, V._label(req, d))
        cam_d = __import__("aruco_studio.core.cameras", fromlist=["x"]).camera_of(CAMERA)
        cam = C.Cam(float(args["distance"]), int(cam_d["resolution"][0]), int(cam_d["resolution"][1]), float(cam_d["hfov_deg"]))
        errs, reads = [], 0
        for v in RR.cases(POSE_CASES):
            o = V._view(d, scene, cam, v, picture=False)
            reads += bool(o["ok"])
            if o["pose_error_mm"] is not None:
                errs.append(float(o["pose_error_mm"]))
        errs.sort()

        def q(p):
            return None if not errs else round(RR.percentile(errs, p), 3)
        out = {"n": POSE_CASES, "posed": len(errs), "reads": reads, "p50": q(50), "p90": q(90), "max": q(100)}
    else:
        raise ValueError(kind)
    out["ms"] = round((time.perf_counter() - t0) * 1000.0, 1)
    return {"id": args["id"], "out": out}


def worker_main(workers: int) -> int:
    """--worker: jobs on stdin, results on stdout (run under each OpenCV's Python)."""
    jobs = json.load(sys.stdin)
    import cv2
    with ProcessPoolExecutor(workers) as ex:
        res = list(ex.map(_job, jobs))
    json.dump({"opencv": cv2.__version__, "results": res}, sys.stdout)
    return 0


def run_workers(jobs_by_cv: dict, workers: int) -> dict:
    """Each OpenCV's jobs in its own Python, at the same time."""
    procs = {}
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
    for cv, jobs in jobs_by_cv.items():
        p = subprocess.Popen([str(PYTHONS[cv]), str(Path(__file__).resolve()), "--worker", "--workers", str(workers)],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=ROOT, env=env)
        p.stdin.write(json.dumps(jobs))
        p.stdin.close()
        procs[cv] = p
    out = {}
    for cv, p in procs.items():
        so = p.stdout.read()
        se = p.stderr.read()
        if p.wait():
            raise RuntimeError(f"{cv} worker failed: {se[-2000:]}")
        got = json.loads(so)
        assert got["opencv"] == cv, (got["opencv"], cv)
        out[cv] = {r["id"]: r["out"] for r in got["results"]}
    return out


def verify_key(req: dict) -> str:
    """The proposed cache key's plan part: the scene the camera sees, in the
    marker's own frame (its layers, its ids, its label as drawn) -- so moving or
    turning a marker on the page keeps its results."""
    from aruco_studio import web_verify as V
    rq = V.placed(req)
    d = V._plan(rq)
    payload = canon({"layers": d["layers"], "ids": d["ids"], "label": V._label(rq, d)})
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:16]


def canon(x):
    """Numbers to 0.1 um, so a turn's float noise (2e-7 mm, measured on B1 at 30 deg) is not an edit."""
    if isinstance(x, float):
        v = round(x, 4)
        return 0.0 if v == 0 else v
    if isinstance(x, dict):
        return {k: canon(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [canon(v) for v in x]
    return x


def request_key(req: dict) -> str:
    """Today's key's plan part (web/src/verify/range.ts rangeKey): the whole request."""
    return hashlib.sha256(json.dumps(req, sort_keys=True).encode()).hexdigest()[:16]


EDITS = [
    # (label, case, how) -- how edits the document's feature / shape in place
    ("Move the marker 10 mm on the page", "B1", lambda doc, f, s: s.update(cx=s["cx"] + 10.0, cy=s["cy"] - 7.0)),
    ("Turn the profile 30°", "B1", lambda doc, f, s: s.update(angle_deg=30.0)),
    ("Grow the profile 30 → 36 mm (marker Auto)", "B1", lambda doc, f, s: s.update(w=36.0, h=36.0)),
    ("Re-ID: #1 → #31", "B1", lambda doc, f, s: f["marker"].update(first_id=31)),
    ("Label text “#{ids}” → “#{ids} {dict}”", "B1", lambda doc, f, s: f["label"].update(text="#{ids} {dict}")),
    ("Label height typed 3.75 mm (¾ cell)", "B1", lambda doc, f, s: f["label"].update(height_mm=3.75)),
    ("Corner mark: triangle", "B1", lambda doc, f, s: f["marker"].update(corner_mark="triangle")),
    ("Label off", "B1", lambda doc, f, s: f["label"].update(on=False)),
]


def edit_table() -> list:
    doc, cases = board()
    case = {c["key"]: c for c in cases}
    rows = []
    for label, key, how in EDITS:
        d2 = copy.deepcopy(doc)
        f = next(x for x in d2["features"] if x["id"] == case[key]["fid"])
        s = next(x for x in d2["shapes"] if x["id"] == f["profile"]["outer"])
        how(d2, f, s)
        r0, r1 = case[key]["req"], plan_request(d2, f)
        rows.append({"edit": label, "case": key,
                     "request_changed": request_key(r0) != request_key(r1),
                     "verify_changed": verify_key(r0) != verify_key(r1)})
    return rows


def compute(workers: int) -> dict:
    t0 = time.time()
    doc, cases = board()
    jobs = {cv: [] for cv in PYTHONS}
    for c in cases:
        for cv in PYTHONS:
            jobs[cv].append({"id": f"range|{c['key']}|marked", "kind": "range", "req": c["req"]})
            jobs[cv].append({"id": f"range|{c['key']}|bare", "kind": "range", "req": bare(c["req"])})
    by = {c["key"]: c for c in cases}
    for k in FAN_KEYS:
        for a in FAN_ANGLES:
            jobs[NEWEST].append({"id": f"fan|{k}|{a:g}", "kind": "fan", "req": by[k]["req"], "angle": a})
    for c in cases:
        for dist in POSE_AT:
            jobs[NEWEST].append({"id": f"pose|{c['key']}|{dist:g}", "kind": "pose", "req": c["req"], "distance": dist})
    res = run_workers(jobs, workers)
    print(f"workers: {sum(len(j) for j in jobs.values())} jobs in {time.time() - t0:.0f} s", flush=True)
    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    data = {"generated": time.strftime("%Y-%m-%d %H:%M"), "head": head, "camera": CAMERA, "newest": NEWEST,
            "cases": [{k: c[k] for k in ("key", "title", "group", "fid", "number")} for c in cases],
            "ranges": {}, "fan": {}, "pose": {}}
    for cv, got in res.items():
        for jid, out in got.items():
            kind, key, what = jid.split("|")
            if kind == "range":
                data["ranges"].setdefault(cv, {}).setdefault(key, {})[what] = out
            elif kind == "fan":
                data["fan"].setdefault(cv, {}).setdefault(key, []).append(out)
            else:
                data["pose"].setdefault(key, {})[what] = out
    for cv in data["fan"]:
        for k in data["fan"][cv]:
            data["fan"][cv][k].sort(key=lambda x: x["angle"])
    # the plan facts the page prints
    from aruco_studio import web_api as W
    for c, rec in zip(cases, data["cases"]):
        p = W.plan(c["req"])
        rec.update(ids=p["ids"], cell_mm=p["cell_mm"], marker_mm=p["marker_mm"], outer_mm=p["outer_mm"],
                   type=c["req"]["marker"]["type"], verify_key=verify_key(c["req"]), request_key=request_key(c["req"]))
    data["edits"] = edit_table()
    # one range timed alone per OpenCV (no other job from here), for the CPython side of the timing table
    data["clean"] = clean_timing(by)
    data["wall_s"] = round(time.time() - t0, 1)
    return data


def clean_timing(by: dict) -> dict:
    out = {}
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
    for cv, py in PYTHONS.items():
        jobs = [{"id": f"range|{k}|marked", "kind": "range", "req": by[k]["req"]} for k in ("A1", "E2")]
        p = subprocess.run([str(py), str(Path(__file__).resolve()), "--worker", "--workers", "1"], input=json.dumps(jobs),
                           capture_output=True, text=True, cwd=ROOT, env=env, check=True)
        got = json.loads(p.stdout)
        out[cv] = {r["id"].split("|")[1]: {"ms": r["out"]["ms"], "renders": r["out"]["renders"]} for r in got["results"]}
    return out


def b6_fixed(req: dict) -> dict:
    """The storyboard's edit: B6's typed whole-cell label set back to Auto (height 0)."""
    r = copy.deepcopy(req)
    r["label"] = dict(r["label"], height_mm=0)
    return r


def ensure_extras(data: dict) -> bool:
    """Keys added after the first compute: computed only when missing."""
    changed = False
    doc, cases = board()
    by = {c["key"]: c for c in cases}
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1")

    def run(cv, jobs, workers):
        p = subprocess.run([str(PYTHONS[cv]), str(Path(__file__).resolve()), "--worker", "--workers", str(workers)],
                           input=json.dumps(jobs), capture_output=True, text=True, cwd=ROOT, env=env)
        if p.returncode:
            raise RuntimeError(p.stderr[-2000:])
        return {r["id"]: r["out"] for r in json.loads(p.stdout)["results"]}
    if "fixed" not in data:
        # the storyboard's step 4: B6 with its label back on Auto, measured like the rest
        fx = b6_fixed(by["B6"]["req"])
        out = {}
        for cv in PYTHONS:
            got = run(cv, [{"id": "range", "kind": "range", "req": fx}, {"id": "check", "kind": "check", "req": fx},
                           {"id": "rules", "kind": "rules", "req": fx}], 3)
            out[cv] = got
        out["verify_key"] = verify_key(fx)
        data["fixed"] = out
        changed = True
    if "seq" not in data:
        # the board one marker after another in ONE process (the browser's shape: one worker), the
        # browser's OpenCV: each range's own time, and the label check's on four markers
        jobs = [{"id": f"range|{c['key']}", "kind": "range", "req": c["req"]} for c in cases]
        jobs += [{"id": f"check|{k}", "kind": "check", "req": by[k]["req"]} for k in ("A1", "B6", "D4", "E2")]
        t0 = time.time()
        got = run("4.11.0", jobs, 1)
        load = os.getloadavg()[0]
        data["seq"] = {"opencv": "4.11.0", "load": round(load, 1), "wall_s": round(time.time() - t0, 1),
                       "range": {k.split("|")[1]: {"ms": v["ms"], "renders": v["renders"]} for k, v in got.items() if k.startswith("range|")},
                       "check": {k.split("|")[1]: {"ms": v["ms"], "views": v["views"]} for k, v in got.items() if k.startswith("check|")}}
        changed = True
    if "fans_all" not in data:
        # every marker's symmetric fan (V3 draws one on each), the newest OpenCV
        jobs = [{"id": f"fan|{c['key']}|{a:g}", "kind": "fan", "req": c["req"], "angle": a}
                for c in cases for a in FAN_ANGLES if not (c["key"] in FAN_KEYS)]
        jobs += [{"id": f"fan|B6fix|{a:g}", "kind": "fan", "req": b6_fixed(by["B6"]["req"]), "angle": a} for a in FAN_ANGLES]
        got = run(NEWEST, jobs, 8)
        fans = {k: list(v) for k, v in data["fan"][NEWEST].items()}
        for jid, out in got.items():
            _, key, _a = jid.split("|")
            fans.setdefault(key, []).append(out)
        for k in fans:
            fans[k].sort(key=lambda x: x["angle"])
        data["fans_all"] = fans
        changed = True
    return changed


# ================================================================== 2. capture

CAPTURE_JS = r"""
// Generated by docs/build_verify_canvas_proposals.py: the running Preview, headless. Deleted after the run.
const { chromium } = require("@playwright/test");
const fs = require("fs");
const CFG = __CFG__;
const [W, H] = CFG.view;
const HIDE_ALWAYS = `.toast,.vp-hint{display:none!important} html>:not(head):not(body){display:none!important}`;
const ONLY_BG = `.vp-svg>:not(.grid):not(.ruler):not(defs){visibility:hidden!important}
  .pill,.toolbar,.corner,.zoom-pill,[data-testid="extrude-panel"]{visibility:hidden!important}`;
const ONLY_PRINT = `body *{visibility:hidden!important}
  .vp-svg .whites,.vp-svg .whites *,.vp-svg [data-marker-black],.vp-svg [data-marker-black] *,.vp-svg .label,.vp-svg .label *{visibility:visible!important}
  html,body,#root,.app,.stage,.viewport{background:transparent!important}`;
const ONLY_CHROME = `.viewport,[data-testid="extrude-panel"]{visibility:hidden!important}
  html,body,#root,.app,.stage{background:transparent!important}`;
const ONLY_PANEL = `body *{visibility:hidden!important}
  [data-testid="extrude-panel"],[data-testid="extrude-panel"] *{visibility:visible!important}
  html,body,#root,.app,.stage,.viewport{background:transparent!important}`;

async function alpha(p, css, path) {
  const tag = await p.addStyleTag({ content: css });
  await p.waitForTimeout(250);
  await p.screenshot({ path, omitBackground: true });
  await tag.evaluate((e) => e.remove());
  await p.waitForTimeout(150);
}

const GEOM = () => {
  const svg = document.querySelector(".vp-svg");
  const bb = (e) => { const b = e.getBoundingClientRect(); return [b.x, b.y, b.right, b.bottom].map((v) => +v.toFixed(2)); };
  const box = (s) => { const e = document.querySelector(s); return e ? bb(e) : null; };
  const s = window.__aruco.state();
  const markers = {};
  for (const f of s.doc.features) {
    const w = svg.querySelector(`[data-cut-white="${f.id}"]`);
    const o = svg.querySelector(`[data-marker="${f.id}"] .outline`);
    const t = svg.querySelector(`.triad[data-feature="${f.id}"]`);
    markers[f.id] = { white: w ? bb(w) : null, outline: o ? bb(o) : null, triad: t ? t.outerHTML : null,
      outline_d: o ? o.getAttribute("d") : null };
  }
  const edges = [...svg.querySelector(".sketch").children].filter((e) => e.tagName === "path").map((e) => e.getAttribute("d"));
  return { camera: s.camera, view: s.view, markers, edges,
    boxes: { verify: box('[data-testid="act-verify"]'), print: box('[data-testid="act-print"]'), actions: box('[data-testid="actions-pill"]'),
      doc: box('[data-testid="doc-pill"]'), toolbar: box('[data-testid="toolbar"]'), zoom: box('[data-testid="zoom-indicator"]'),
      corner: box('[data-testid="corner"]'), tools: [...document.querySelectorAll('[data-testid="toolbar"] button')].map(bb) } };
};

(async () => {
  const b = await chromium.launch({ channel: "chrome" });
  const S = CFG.shots, out = { view: CFG.view, dpr: CFG.dpr, site: CFG.site };
  const p = await b.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: CFG.dpr });
  p.on("pageerror", (e) => console.error("pageerror", e.message));
  const t0 = Date.now();
  await p.goto(CFG.site + "?example=label-placement");
  await p.getByTestId("viewport").waitFor();
  await p.waitForFunction(() => window.__aruco && window.__aruco.state().core.state === "ready", null, { timeout: 180000 });
  await p.evaluate(() => window.__aruco.idle(90000));
  out.boot_ms = Date.now() - t0;
  await p.addStyleTag({ content: HIDE_ALWAYS });
  await p.keyboard.press("Escape");
  await p.mouse.move(W - 3, H / 2);
  await p.waitForTimeout(600);
  out.geom = await p.evaluate(GEOM);
  await p.screenshot({ path: `${S}/today.png` });
  {
    const tag = await p.addStyleTag({ content: ONLY_BG });
    await p.waitForTimeout(250);
    await p.screenshot({ path: `${S}/bg.png` });
    await tag.evaluate((e) => e.remove());
  }
  await alpha(p, ONLY_PRINT, `${S}/print.png`);
  await alpha(p, ONLY_CHROME, `${S}/chrome.png`);
  // the panel, on the marker the mocks open (its Marker tab)
  const [cx, cy] = await p.evaluate((xy) => window.__aruco.toClient(xy[0], xy[1]), CFG.select_xy);
  await p.mouse.click(cx, cy);
  await p.waitForTimeout(700);
  await p.evaluate(() => window.__aruco.idle(45000));
  await p.mouse.move(W - 3, H / 2);
  await p.waitForTimeout(400);
  out.panel_box = await p.evaluate(() => { const e = document.querySelector('[data-testid="extrude-panel"]'); if (!e) return null; const r = e.getBoundingClientRect(); return [r.x, r.y, r.right, r.bottom]; });
  await alpha(p, ONLY_PANEL, `${S}/panel.png`);
  await p.screenshot({ path: `${S}/today-selected.png` });
  await p.keyboard.press("Escape");
  await p.waitForTimeout(400);

  // ---- the storyboard's edit, as the app draws it: B6's label back on Auto (the board opened as a file)
  {
    const q = await b.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: CFG.dpr });
    await q.goto(CFG.site);
    await q.getByTestId("viewport").waitFor();
    await q.waitForFunction(() => window.__aruco && window.__aruco.state().core.state === "ready", null, { timeout: 180000 });
    await q.evaluate(() => window.__aruco.idle(90000));
    await q.getByTestId("menu-main").click();
    await q.getByTestId("menu-file").hover();
    await q.waitForTimeout(300);
    const fc = q.waitForEvent("filechooser", { timeout: 15000 });
    await q.getByTestId("cmd-open").click();
    await (await fc).setFiles(CFG.fixed_doc);
    await q.waitForTimeout(1200);
    await q.evaluate(() => window.__aruco.idle(90000));
    await q.addStyleTag({ content: HIDE_ALWAYS });
    await q.keyboard.press("Escape");
    await q.mouse.move(W - 3, H / 2);
    await q.waitForTimeout(600);
    out.fixed_camera = await q.evaluate(() => window.__aruco.state().camera);
    await alpha(q, ONLY_PRINT, `${S}/print-fixed.png`);
    await q.close();
  }

  // ---- the browser's timings
  const T = await p.evaluate(async (cfg) => {
    const R = window.__arucoRange;
    const res = { runs: {} };
    // the first range of a visit loads OpenCV into the worker: kept apart
    const warm = await R.run(cfg.reqs[cfg.warm], "d435");
    res.first = { key: cfg.warm, wall_ms: Math.round(warm.wall_ms), renders: warm.renders, opencv: warm.result.opencv };
    for (const k of cfg.cold) {
      const r = await R.run(cfg.reqs[k], "d435");
      res.runs[k] = { wall_ms: Math.round(r.wall_ms), renders: r.renders, steps: r.steps, worst_step_ms: Math.round(r.worst_step_ms),
        near_mm: r.result.near_mm, far_mm: r.result.far_mm, opencv: r.result.opencv, bytes: JSON.stringify(r.result).length };
      res.sample = r.result;
    }
    // ---- the cached path as web/src/verify/range.ts has it today: one localStorage array, parsed per lookup
    const median = (xs) => { const s = [...xs].sort((a, b) => a - b); return s[Math.floor(s.length / 2)]; };
    const keys = cfg.order.map((k) => JSON.stringify(["range-ui/1", "0.1.0", "d435", cfg.reqs[k]]));
    const STORE = "vc-proposal.ranges";            // this headless profile's own storage, never Zach's
    const store = [];
    for (let i = 0; i < 240 - keys.length; i++) store.push({ k: `filler-${i}`, r: res.sample, ms: 1000 });
    for (const k of keys) store.push({ k, r: res.sample, ms: 1000 });
    localStorage.setItem(STORE, JSON.stringify(store));
    res.store_bytes = localStorage.getItem(STORE).length;
    const readStore = () => { try { const v = JSON.parse(localStorage.getItem(STORE) ?? "[]"); return Array.isArray(v) ? v.filter((x) => x && typeof x.k === "string" && x.r) : []; } catch { return []; } };
    const ls = [], mem = [];
    for (let rep = 0; rep < 25; rep++) {
      const memory = new Map();
      let t = performance.now();
      for (const k of keys) { const m = memory.get(k); if (m) continue; const s = readStore().find((x) => x.k === k); if (s) memory.set(k, s); }
      ls.push(performance.now() - t);
      t = performance.now();
      let hit = 0;
      for (const k of keys) if (memory.get(k)) hit++;
      mem.push(performance.now() - t);
      if (hit !== keys.length) throw new Error("cache miss in the test");
    }
    localStorage.removeItem(STORE);
    res.localstorage_28_ms = +median(ls).toFixed(2);
    res.memory_28_ms = +median(mem).toFixed(3);
    // ---- IndexedDB, keyed by the verify key (a hash), one transaction for the 28
    const open = () => new Promise((ok, no) => { const q = indexedDB.open("vc-proposal", 1); q.onupgradeneeded = () => q.result.createObjectStore("m"); q.onsuccess = () => ok(q.result); q.onerror = () => no(q.error); });
    const db = await open();
    await new Promise((ok, no) => { const tx = db.transaction("m", "readwrite"); const st = tx.objectStore("m");
      for (let i = 0; i < 240; i++) st.put(res.sample, i < keys.length ? `k${i}` : `f${i}`); tx.oncomplete = ok; tx.onerror = () => no(tx.error); });
    const idb = [];
    for (let rep = 0; rep < 25; rep++) {
      const t = performance.now();
      await new Promise((ok, no) => { const tx = db.transaction("m", "readonly"); const st = tx.objectStore("m"); let n = 0;
        for (let i = 0; i < keys.length; i++) { const q = st.get(`k${i}`); q.onsuccess = () => { if (q.result) n++; }; }
        tx.oncomplete = () => (n === keys.length ? ok() : no(new Error("idb miss"))); tx.onerror = () => no(tx.error); });
      idb.push(performance.now() - t);
    }
    db.close();
    await new Promise((ok) => { const q = indexedDB.deleteDatabase("vc-proposal"); q.onsuccess = ok; q.onerror = ok; q.onblocked = ok; });
    res.indexeddb_28_ms = +median(idb).toFixed(2);
    // ---- the verify key: SHA-256 of each marker's scene (its own frame), the 28
    const enc = new TextEncoder();
    const hs = [];
    for (let rep = 0; rep < 25; rep++) {
      const t = performance.now();
      await Promise.all(cfg.payloads.map((s) => crypto.subtle.digest("SHA-256", enc.encode(s))));
      hs.push(performance.now() - t);
    }
    res.hash_28_ms = +median(hs).toFixed(2);
    res.payload_bytes = cfg.payloads.reduce((a, s) => a + s.length, 0);
    // ---- re-judging 28 cached answers against a changed threshold (no render)
    const js = [];
    for (let rep = 0; rep < 25; rep++) {
      const t = performance.now();
      let fails = 0;
      for (let i = 0; i < 28; i++) { const r = res.sample; const need = 300 + 25 * rep; if (!r.far_mm || r.far_mm < need || (r.near_mm || 0) > 150) fails++; }
      js.push(performance.now() - t);
    }
    res.judge_28_ms = +median(js).toFixed(4);
    // ---- the flash: 28 badges' class set, then two frames
    const svg = document.querySelector(".vp-svg");
    const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
    for (let i = 0; i < 28; i++) { const c = document.createElementNS("http://www.w3.org/2000/svg", "circle"); c.setAttribute("r", "7"); c.setAttribute("cx", String(40 + 20 * i)); c.setAttribute("cy", "60"); g.appendChild(c); }
    svg.appendChild(g);
    const fr = [];
    for (let rep = 0; rep < 15; rep++) {
      const t = performance.now();
      for (const c of g.children) c.setAttribute("class", rep % 2 ? "ok" : "flash");
      await new Promise((ok) => requestAnimationFrame(() => requestAnimationFrame(ok)));
      fr.push(performance.now() - t);
    }
    g.remove();
    res.flash_frames_ms = +median(fr).toFixed(1);
    return res;
  }, CFG);
  out.timing = T;
  await b.close();
  fs.writeFileSync(`${S}/capture.json`, JSON.stringify(out, null, 1));
  console.log("captured; boot", out.boot_ms, "ms; first range", T.first.wall_ms, "ms;", JSON.stringify(T.runs));
})().catch((e) => { console.error(e); process.exit(1); });
"""


def node_env() -> dict:
    """playwright from the app's own node_modules, the script outside the repo."""
    return dict(os.environ, NODE_PATH=str(ROOT / "web" / "node_modules"))


def run_js(name: str, js: str, timeout: int) -> str:
    with tempfile.TemporaryDirectory(prefix="vc-") as tmp:
        path = Path(tmp) / f"{name}.cjs"
        path.write_text(js)
        r = subprocess.run(["node", str(path)], cwd=tmp, env=node_env(), timeout=timeout, capture_output=True, text=True)
        if r.returncode:
            print(r.stdout[-3000:], r.stderr[-3000:], sep="\n", file=sys.stderr)
            raise RuntimeError(f"{name}.cjs failed")
        return r.stdout + r.stderr


def capture(force: bool) -> dict:
    facts = SHOTS / "capture.json"
    if facts.exists() and not force:
        return json.loads(facts.read_text())
    SHOTS.mkdir(parents=True, exist_ok=True)
    doc, cases = board()
    b6 = next(s for s in doc["shapes"] if s["id"] == "lp-B6-r")
    payloads = []
    from aruco_studio import web_verify as V
    for c in cases:
        rq = V.placed(c["req"])
        d = V._plan(rq)
        payloads.append(json.dumps(canon({"layers": d["layers"], "ids": d["ids"], "label": V._label(rq, d)}), sort_keys=True))
    fixed = copy.deepcopy(doc)
    f6 = next(f for f in fixed["features"] if f["id"] == "lp-B6")
    f6["label"]["height_mm"] = 0
    f6["set"] = [s for s in f6.get("set", []) if s != "label.height_mm"]
    fixed_path = SHOTS / "board-b6-auto.arucostudio-web.json"
    fixed_path.write_text(json.dumps(fixed, indent=1))
    cfg = {"view": [1440, 900], "dpr": 2, "site": PREVIEW, "shots": str(SHOTS), "select_xy": [b6["cx"], b6["cy"]],
           "fixed_doc": str(fixed_path),
           "reqs": {c["key"]: c["req"] for c in cases}, "order": [c["key"] for c in cases],
           "warm": "B1", "cold": ["A1", "B6", "E2"], "payloads": payloads}
    hist_file = SHOTS / "timing-runs.json"
    hist = json.loads(hist_file.read_text()) if hist_file.exists() else []
    load0 = os.getloadavg()[0]
    print(run_js("capture", CAPTURE_JS.replace("__CFG__", json.dumps(cfg)), 1500).strip()[-1500:], flush=True)
    cap = json.loads(facts.read_text())
    # WHY a history: peers' lanes share this machine (load 15-85 during these runs), so one run's
    # seconds are one sample; the page prints every run's with its load
    t = cap["timing"]
    hist.append({"at": time.strftime("%Y-%m-%d %H:%M"), "load": [round(load0, 1), round(os.getloadavg()[0], 1)],
                 "runs": t["runs"], "first_ms": t["first"]["wall_ms"],
                 "lookups": {k: t[k] for k in ("localstorage_28_ms", "indexeddb_28_ms", "hash_28_ms", "flash_frames_ms")}})
    hist_file.write_text(json.dumps(hist, indent=1))
    return cap


# ================================================================== 3. the shared contract: pass / fail

# The threshold set Verify judges with ("Verify thresholds v1", proposed). Each
# is a named number Zach can read and change; a marker FAILS when any one says so.
# WHY these defaults: see THRESHOLD_ROWS' `why` (and the sweeps the page prints).
DEFAULTS = {"p_read": 0.95, "label_pts": 3.0, "p_max": 0.05, "easy_share": 0.02, "easy_min": 2,
            "mark_pose": 1.0, "pose_mm": 1.0, "rules": True}
DEMO_NEED = (150.0, 500.0)      # the storyboard's required distance, batch-set on the whole board
ORDER = ["A1", "B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B9", "C1", "C2", "C3", "C4", "D1", "D2", "D3",
         "D4", "D5", "D6", "D7", "E1", "E2", "E3", "E4", "F1", "F2", "F3"]
DETAIL = "B6"                   # the failure the storyboard opens and then fixes
RUN_DONE = 11                   # the running step: this many measured, the next one spinning
FLASH_RECENT = ("B7", "B9")     # ... and these the last passes in, still flashing


def m(mm, digits=2) -> str:
    if mm is None:
        return "—"
    return f"{mm / 1000.0:.{digits}f} m" if mm >= 1000.0 else f"{mm:.0f} mm"


def label_fails(mk: dict, T: dict) -> str | None:
    """web_marks.check's numbers against T: 'easy' / 'cost' / None."""
    e = mk["easy"]
    if e["lost"] >= T["easy_min"] and e["bare"] and e["lost"] >= T["easy_share"] * e["bare"]:
        return "easy"
    if mk["p"] < T["p_max"] and mk["cost_pts"] >= T["label_pts"]:
        return "cost"
    return None


def pose_mark_fails(ps: dict, T: dict) -> bool:
    return bool(ps["judged"] and ps["p"] < T["p_max"] and ps["worse"] > ps["better"] and ps["growth"] >= T["mark_pose"])


def judge_board(data: dict, guide: dict, cv: str = NEWEST, need=DEMO_NEED, T: dict | None = None, fixed=False) -> dict:
    """Every marker's verdict and its reasons, each reason (threshold id, words)."""
    T = dict(DEFAULTS, **(T or {}))
    gc = {c["key"]: c for c in guide["cases"]}
    out = {}
    for c in data["cases"]:
        k = c["key"]
        if fixed and k == DETAIL:
            fx = data["fixed"][cv]
            r, mk, rules = fx["range"], dict(fx["check"], easy=fx["check"]["easy"]), fx["rules"]
            pose_m = fx["check"]["pose"]
        else:
            r = data["ranges"][cv][k]["marked"]
            mk = gc[k]["verify"][cv]["marks"]
            rules = gc[k]["rules"]
            pose_m = mk["pose"]
        why = []
        if r["far_mm"] is None:
            why.append(("reads", f"Reads nowhere on the D435: no distance where every id reads in {T['p_read'] * 100:.0f} % of the Field cameras"))
        elif need:
            if r["far_mm"] < need[1]:
                why.append(("need", f"Reads to {m(r['far_mm'])}, needs {m(need[1])} (short by {m(need[1] - r['far_mm'])})"))
            if (r["near_mm"] or 0) > need[0]:
                why.append(("need", f"Reads from {m(r['near_mm'])}, needs {m(need[0])}"))
        lf = label_fails(mk, T)
        if lf == "easy":
            why.append(("label", f"Label loses {mk['easy']['lost']} of the bare marker's {mk['easy']['bare']} easy reads "
                                 f"(over {T['easy_share'] * 100:.0f} %)"))
        elif lf == "cost":
            why.append(("label", f"Label costs {mk['cost_pts']:.1f} pts of the bare marker's reads (p = {mk['p']:.3f}), over {T['label_pts']:g} pts"))
        if pose_mark_fails(pose_m, T):
            why.append(("markpose", f"Label grows the pose error {pose_m['growth'] * 100:+.0f} % where the bare pose is sharp, over +{T['mark_pose'] * 100:.0f} %"))
        if c["type"] == "charuco" and need and not (fixed and k == DETAIL):
            p = data["pose"][k].get(f"{need[1]:g}")
            if p and p["p90"] is not None and p["p90"] > T["pose_mm"]:
                why.append(("pose", f"Pose error p90 {p['p90']:.1f} mm at {m(need[1])}, over {T['pose_mm']:g} mm"))
        if T["rules"] and rules["verdict"] == "unsafe":
            why.append(("rules", "Print rule: " + rules["hits"][0]))
        out[k] = {"pass": not why, "why": why, "range": r}
    return out


THRESHOLD_ROWS = [
    {"id": "reads", "name": "Reads at all", "value": "95 % of the Field cameras",
     "fails": "no distance at which every id reads in 95 % of the 48 Field cameras (the live engine, reading-range/1)",
     "why": "The engine's own line: the range's ends are where the read rate crosses 95 %. A marker with no such distance has no range to draw."},
    {"id": "need", "name": "Required distance", "value": "none · set per document or marker",
     "fails": "the reading range does not cover it: far end short of the max, or near end past the min (the live judge())",
     "why": "Without one, a range is information, not a verdict. Batch-set it once; the storyboard uses 0.15–0.5 m on all 28."},
    {"id": "label", "name": "Label cost", "value": "3 pts, sign test p < 0.05 · or 2 % of easy reads",
     "fails": "the label (and corner mark) loses ≥ 3 pts of the bare marker's reads over the same views and the loss is not chance, or loses ≥ 2 % (≥ 2) of the reads the bare marker gets in sharp, well-resolved views",
     "why": "The REF study tolerated 0.7 module's −1.5 pts and made a hard rule of 0.5 module's −7 pts; 3 pts sits between with room. Paired views and the sign test do the real work: on this board X = 1…10 pts changes one verdict."},
    {"id": "markpose", "name": "Label's pose cost", "value": "+100 % mean pose error, p < 0.05",
     "fails": "where the bare pose is sharp, the label more than doubles the mean pose error and the sign test says it is not chance",
     "why": "web_marks' unsafe line: a ChArUco label near a chessboard corner doubled the pose error (0.062 → 0.119 mm) while every id still read."},
    {"id": "pose", "name": "Pose accuracy (ChArUco)", "value": "p90 ≤ 1 mm at the required far end",
     "fails": "90 % of the Field cameras at the required max distance see a pose error over 1 mm",
     "why": "At 0.3 m the board's 5 × 4 ChArUco sits at 0.33 mm and a 22 mm single at 1.25 mm: 1 mm keeps the boards built for pose honest about the distance they are asked to work at."},
    {"id": "rules", "name": "Print rules", "value": "on: an unsafe rule fails",
     "fails": "the core's label rules (the REF study's lines) say unsafe: ink in the quiet zone, letters taller than the border row, text longer than it",
     "why": "The simulator prints crisp ink: it cannot see dot spread or grey ink, where the REF study measured up to −40 pts in the quiet ring. A green badge over a rule break would be a lie."},
]


def sweeps(data: dict, guide: dict) -> dict:
    """What each threshold's value does to the 28 (fails per OpenCV)."""
    gc = {c["key"]: c for c in guide["cases"]}
    keys = [c["key"] for c in data["cases"]]
    out = {"label": [], "need": [], "markpose": [], "pose": []}
    for X in (1.0, 2.0, 3.0, 5.0, 10.0):
        row = {"value": f"{X:g} pts"}
        for cv in PYTHONS:
            row[cv] = [k for k in keys if label_fails(gc[k]["verify"][cv]["marks"], dict(DEFAULTS, label_pts=X))]
        out["label"].append(row)
    for mx in (300.0, 400.0, 500.0, 750.0, 1000.0):
        row = {"value": f"0.15 – {m(mx)}"}
        for cv in PYTHONS:
            fails, border = [], []
            for k in keys:
                r = data["ranges"][cv][k]["marked"]
                if r["far_mm"] is None or r["far_mm"] < mx or (r["near_mm"] or 0) > 150.0:
                    fails.append(k)
                if r["band_mm"] and r["band_mm"][0] < mx <= r["band_mm"][1]:
                    border.append(k)
            row[cv] = fails
            row[cv + "_border"] = border
        out["need"].append(row)
    for G in (0.2, 0.5, 1.0, 2.0):
        row = {"value": f"+{G * 100:.0f} %"}
        for cv in PYTHONS:
            row[cv] = [k for k in keys if pose_mark_fails(gc[k]["verify"][cv]["marks"]["pose"], dict(DEFAULTS, mark_pose=G))]
        out["markpose"].append(row)
    boards = [c["key"] for c in data["cases"] if c["type"] == "charuco"]
    for lim in (0.5, 1.0, 2.0):
        row = {"value": f"{lim:g} mm"}
        for dist in POSE_AT:
            row[f"{dist:g}"] = [k for k in boards if (data["pose"][k][f"{dist:g}"]["p90"] or 99) > lim]
        out["pose"].append(row)
    out["rules"] = [k for k in keys if gc[k]["rules"]["verdict"] == "unsafe"]
    out["reads"] = {cv: [k for k in keys if data["ranges"][cv][k]["marked"]["far_mm"] is None] for cv in PYTHONS}
    return out


# ================================================================== 4. drawing

VIEW = (1440.0, 900.0)
OK, BAD, ACC, MUTED, STALE = "#18865a", "#cf3b3b", "#2f6fed", "#6b7480", "#8a94a0"


def webp(path: Path, q: int = 80, crop=None) -> str:
    import cv2
    im = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if crop:
        x0, y0, x1, y1 = (int(round(v)) for v in crop)
        im = im[y0:y1, x0:x1]
    ok, buf = cv2.imencode(".webp", im, [cv2.IMWRITE_WEBP_QUALITY, q])
    assert ok
    return "data:image/webp;base64," + base64.b64encode(buf.tobytes()).decode("ascii")


class Ctx:
    """The capture, the data and the verdicts the variants draw from."""

    def __init__(self, data: dict, cap: dict, guide: dict):
        self.data, self.cap, self.guide = data, cap, guide
        self.boxes = {k[3:]: v["white"] for k, v in cap["geom"]["markers"].items()}
        self.v = judge_board(data, guide)
        self.vfix = judge_board(data, guide, fixed=True)
        self.case = {c["key"]: c for c in data["cases"]}
        self.fans = data["fans_all"]
        self.fails = [k for k in ORDER if not self.v[k]["pass"]]
        self.passes = [k for k in ORDER if self.v[k]["pass"]]
        self.fails_fixed = [k for k in ORDER if not self.vfix[k]["pass"]]
        t = cap["timing"]
        self.flash_ms = t["hash_28_ms"] + t["indexeddb_28_ms"] + t["judge_28_ms"] + t["flash_frames_ms"]
        # every capture run's browser seconds (peer lanes load this machine: one run is one sample)
        hf = SHOTS / "timing-runs.json"
        self.hist = json.loads(hf.read_text()) if hf.exists() else [{"runs": t["runs"], "first_ms": t["first"]["wall_ms"]}]
        self.span = {k: (min(h["runs"][k]["wall_ms"] for h in self.hist), max(h["runs"][k]["wall_ms"] for h in self.hist))
                     for k in ("A1", "B6", "E2")}
        per = [h["runs"]["A1"]["wall_ms"] / h["runs"]["A1"]["renders"] for h in self.hist]
        n6 = data["fixed"]["4.11.0"]["range"]["renders"]
        self.b6fix_txt = f"≈ {min(per) * n6 / 1000:.0f}–{max(per) * n6 / 1000:.0f} s"

    def b(self, k):
        return self.boxes[k]

    def corner(self, k, dx=3.0, dy=-3.0):
        x0, y0, x1, y1 = self.b(k)
        return x1 + dx, y0 + dy

    def centre(self, k):
        x0, y0, x1, y1 = self.b(k)
        return (x0 + x1) / 2.0, (y0 + y1) / 2.0


def g_ok(x, y, r=7.0, cls="") -> str:
    s = r / 7.0
    return (f'<g class="vc-g {cls}"><circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{OK}" stroke="#fff" stroke-width="1.5"/>'
            f'<path d="M{x - 3.2 * s:.1f} {y + 0.2 * s:.1f}l{2.2 * s:.1f} {2.2 * s:.1f}l{4.2 * s:.1f} {-4.6 * s:.1f}" fill="none" stroke="#fff" stroke-width="{1.7 * s:.2f}" stroke-linecap="round" stroke-linejoin="round"/></g>')


def g_bad(x, y, r=7.0, cls="") -> str:
    s = r / 7.0
    return (f'<g class="vc-g {cls}"><circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{BAD}" stroke="#fff" stroke-width="1.5"/>'
            f'<path d="M{x - 2.6 * s:.1f} {y - 2.6 * s:.1f}l{5.2 * s:.1f} {5.2 * s:.1f}M{x + 2.6 * s:.1f} {y - 2.6 * s:.1f}l{-5.2 * s:.1f} {5.2 * s:.1f}" stroke="#fff" stroke-width="{1.7 * s:.2f}" stroke-linecap="round"/></g>')


def g_stale(x, y, r=7.0, cls="") -> str:
    return (f'<g class="vc-g {cls}"><circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="#fff" stroke="{STALE}" stroke-width="1.6" stroke-dasharray="2.4 2"/>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r * 0.28:.1f}" fill="{STALE}"/></g>')


def g_spin(x, y, r=7.0, frac=0.4, cls="") -> str:
    a = 2 * math.pi * frac
    ex, ey = x + r * math.sin(a), y - r * math.cos(a)
    big = 1 if frac > 0.5 else 0
    return (f'<g class="vc-g {cls}"><circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="#fff" stroke="#d6dbe2" stroke-width="2"/>'
            f'<path d="M{x:.1f} {y - r:.1f}A{r} {r} 0 {big} 1 {ex:.1f} {ey:.1f}" fill="none" stroke="{ACC}" stroke-width="2.2" stroke-linecap="round"/>'
            f'<circle class="vc-spin" cx="{x:.1f}" cy="{y:.1f}" r="{r - 3.2:.1f}" fill="none" stroke="{ACC}" stroke-width="1.4" stroke-dasharray="4 20" stroke-linecap="round"/></g>')


def g_queued(x, y, r=7.0, cls="") -> str:
    return f'<g class="vc-g {cls}"><circle cx="{x:.1f}" cy="{y:.1f}" r="{r * 0.42:.1f}" fill="#c3c9d1"/></g>'


def g_dot(x, y, r=4.0, cls="") -> str:
    return f'<circle class="vc-g {cls}" cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{BAD}" stroke="#fff" stroke-width="1.2"/>'


def outline(ctx: Ctx, k, color, cls="", pad=2.5, w=2.0, dash="") -> str:
    x0, y0, x1, y1 = ctx.b(k)
    da = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<rect class="{cls}" x="{x0 - pad:.1f}" y="{y0 - pad:.1f}" width="{x1 - x0 + 2 * pad:.1f}" height="{y1 - y0 + 2 * pad:.1f}" '
            f'rx="3" fill="none" stroke="{color}" stroke-width="{w}"{da}/>')


def flash(ctx: Ctx, k, cls="") -> str:
    """A pass, just in: a green glow round the sticker that fades (CSS: vcflash)."""
    x0, y0, x1, y1 = ctx.b(k)
    return (f'<g class="vc-flash {cls}"><rect x="{x0 - 3:.1f}" y="{y0 - 3:.1f}" width="{x1 - x0 + 6:.1f}" height="{y1 - y0 + 6:.1f}" rx="4" '
            f'fill="none" stroke="{OK}" stroke-width="2.4"/>{g_ok(*ctx.corner(k))}</g>')


# ---- the symmetric reach fan

FAN_D0, FAN_D1 = 40.0, 1500.0
RINGS = [(100.0, "0.1"), (200.0, "0.2"), (500.0, "0.5"), (1000.0, "1 m")]


def fan(rows: list, cx: float, cy: float, R: float, *, axis: float = 0.0, need=None, tone="ok", mini=False,
        rings=True, labels=True, cls="", spokes=True, marker=True) -> str:
    """The reading zone by viewing angle, symmetric about the marker's axis:
    angle exact, distance on a log radius (FAN_D0..FAN_D1). `axis`: the axis's
    direction on screen in degrees (0 = right, -90 = up). rows: the engine's
    answer per yaw angle (near_mm, far_mm, band_mm)."""
    def rad(d):
        return R * min(1.0, max(0.0, math.log(max(d, FAN_D0) / FAN_D0) / math.log(FAN_D1 / FAN_D0)))

    def pt(d, ang):
        a = math.radians(axis + ang)
        r_ = rad(d)
        return cx + r_ * math.cos(a), cy + r_ * math.sin(a)
    col = {"ok": OK, "bad": BAD, "grey": STALE, "acc": ACC}[tone]
    s = [f'<g class="vc-fan {cls}">']
    if rings:
        for d, lab in RINGS:
            r_ = rad(d)
            a0, a1 = math.radians(axis - 80), math.radians(axis + 80)
            s.append(f'<path class="vc-ring" d="M{cx + r_ * math.cos(a0):.1f} {cy + r_ * math.sin(a0):.1f}A{r_:.1f} {r_:.1f} 0 0 1 '
                     f'{cx + r_ * math.cos(a1):.1f} {cy + r_ * math.sin(a1):.1f}"/>')
            if labels:
                lx, ly = pt(d, 0)
                s.append(f'<text class="vc-rl" x="{lx + 2:.1f}" y="{ly + (11 if not mini else 8):.1f}">{lab}</text>')
    if spokes:
        for a in (-45, 45):
            x, y = pt(FAN_D1, a)
            s.append(f'<line class="vc-spoke" x1="{cx:.1f}" y1="{cy:.1f}" x2="{x:.1f}" y2="{y:.1f}"/>')
            if labels:
                s.append(f'<text class="vc-rl" x="{x:.1f}" y="{y:.1f}" text-anchor="middle">{"+" if a > 0 else "−"}45°</text>')
    if need:
        pts = [pt(need[1], a) for a in range(-45, 46, 3)] + [pt(need[0], a) for a in range(45, -46, -3)]
        s.append('<path class="vc-need" d="M' + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + 'Z"/>')
    runs, cur = [], []
    for r in rows:
        if r["far_mm"]:
            cur.append(r)
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    for run in runs:
        if run[0]["band_mm"] and not mini:
            outer = [pt(r["band_mm"][1], r["angle"]) for r in run]
            inner = [pt(r["band_mm"][0], r["angle"]) for r in reversed(run)]
            s.append(f'<path class="vc-band" style="fill:{col}" d="M' + " L".join(f"{x:.1f} {y:.1f}" for x, y in outer + inner) + 'Z"/>')
        far = [pt(r["far_mm"], r["angle"]) for r in run]
        near = [pt(r["near_mm"] or FAN_D0, r["angle"]) for r in reversed(run)]
        s.append(f'<path class="vc-zone" style="fill:{col};stroke:{col}" d="M' + " L".join(f"{x:.1f} {y:.1f}" for x, y in far + near) + 'Z"/>')
        if not mini:
            for r, (x, y) in zip(run, far):
                s.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="1.8" fill="{col}"/>')
    if not runs:
        x, y = pt(320.0 if not mini else 150.0, 0)
        s.append(f'<text class="vc-none" x="{x:.1f}" y="{y + 4:.1f}" text-anchor="middle"'
                 + (' style="font-size:6.5px"' if mini else "") + '>reads nowhere</text>')
    if marker:
        a = math.radians(axis + 90)
        hw = 5.0 if not mini else 3.0
        s.append(f'<line x1="{cx - hw * math.cos(a):.1f}" y1="{cy - hw * math.sin(a):.1f}" x2="{cx + hw * math.cos(a):.1f}" '
                 f'y2="{cy + hw * math.sin(a):.1f}" stroke="#111" stroke-width="{2.6 if not mini else 2}" stroke-linecap="round"/>')
    s.append("</g>")
    return "".join(s)


def fan_rows(ctx: Ctx, k: str, fixed=False) -> list:
    return ctx.fans["B6fix" if (fixed and k == DETAIL) else k]


# ---- the stage: the live canvas's captured layers + this mock's overlays

def stage(canvas: str = "", top: str = "", view=(0.0, 0.0, VIEW[0], VIEW[1]), cls: str = "", fix: str = "",
          extra_style: str = "") -> str:
    """One frame of the canvas: bg (grid, ruler), the printed geometry, V1
    "Turn it down" chrome (the live profile edges, guides and Joint Origins,
    thin and grey), the overlays, the app's chrome, the chrome overlays. `view`
    crops it (x, y, w, h in the capture's px); `fix`: the states (st-…
    classes) in which B6 shows its edited label."""
    x, y, w, h = view
    W_, H_ = VIEW
    if w < W_ - 0.5:
        bs = f"background-size:{W_ / w * 100:.4f}% {H_ / h * 100:.4f}%;background-position:{x / (W_ - w) * 100:.4f}% {y / (H_ - h) * 100:.4f}%"
    else:
        bs = "background-size:100% 100%"
    vb = f"{x:.1f} {y:.1f} {w:.1f} {h:.1f}"
    fixer = f'<use href="#vc-b6fix" class="{fix}"/>' if fix else ""
    return (f'<div class="vc-stage {cls}" style="aspect-ratio:{w:.1f}/{h:.1f};{extra_style}">'
            f'<div class="vc-l vc-bg" style="{bs}"></div><div class="vc-l vc-print" style="{bs}"></div>'
            f'<svg class="vc-l vc-svg" viewBox="{vb}" preserveAspectRatio="none">{fixer}<use href="#vc-geom"/>{canvas}</svg>'
            f'<div class="vc-l vc-chrome" style="{bs}"></div>'
            f'<svg class="vc-l vc-svg vc-top" viewBox="{vb}" preserveAspectRatio="none">{top}</svg></div>')


def defs_svg(ctx: Ctx) -> str:
    """Once per page: the turned-down live chrome and B6's edited print, used by every stage."""
    gm = ctx.cap["geom"]
    tri = "".join(v["triad"] or "" for v in gm["markers"].values())
    outl = "".join(f'<path d="{v["outline_d"]}"/>' for v in gm["markers"].values() if v["outline_d"])
    edges = "".join(f'<path d="{d}"/>' for d in gm["edges"])
    x0, y0, x1, y1 = ctx.b(DETAIL)
    pad = 1.0
    crop = ((x0 - pad) * 2, (y0 - pad) * 2, (x1 + pad) * 2, (y1 + pad) * 2)
    img = webp(SHOTS / "print-fixed.png", 88, crop)
    return (f'<svg class="vc-defs" width="0" height="0" aria-hidden="true"><defs>'
            f'<g id="vc-geom"><g class="vc-edges">{edges}</g><g class="vc-outl">{outl}</g><g class="vc-tri">{tri}</g></g>'
            f'<g id="vc-b6fix"><rect x="{x0 - pad:.2f}" y="{y0 - pad:.2f}" width="{x1 - x0 + 2 * pad:.2f}" height="{y1 - y0 + 2 * pad:.2f}" fill="#e9ecf0"/>'
            f'<image href="{img}" x="{x0 - pad:.2f}" y="{y0 - pad:.2f}" width="{x1 - x0 + 2 * pad:.2f}" height="{y1 - y0 + 2 * pad:.2f}"/></g>'
            f'<pattern id="vc-hatch" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
            f'<line x1="0" y1="0" x2="0" y2="5" stroke="{BAD}" stroke-width="1.4" opacity=".5"/></pattern>'
            f'<filter id="vc-sh" x="-10%" y="-10%" width="120%" height="130%"><feDropShadow dx="0" dy="4" stdDeviation="6" flood-opacity=".16"/></filter>'
            f'</defs></svg>')


def fo(x, y, w, h, inner: str, cls: str = "", attrs: str = "") -> str:
    """HTML in the canvas's frame (cards, panels, menus): scales with the stage."""
    return (f'<foreignObject class="{cls}" x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" {attrs}>'
            f'<div xmlns="http://www.w3.org/1999/xhtml" class="vc-fo">{inner}</div></foreignObject>')


def st(states: str) -> str:
    return "st " + " ".join(f"st-{s}" for s in states.split())


def hit(ctx: Ctx, k: str, to: str, cls: str = "") -> str:
    """A clickable box over a marker that moves the story."""
    x0, y0, x1, y1 = ctx.b(k)
    return (f'<rect class="vc-hit {cls}" data-story-to="{to}" x="{x0 - 4:.1f}" y="{y0 - 4:.1f}" width="{x1 - x0 + 8:.1f}" '
            f'height="{y1 - y0 + 8:.1f}" rx="4"/>')


def verify_btn(ctx: Ctx, inner: str, to: str | None = None, cls: str = "") -> str:
    """An overlay on the live Verify button (its captured box): a status chip at its right."""
    x0, y0, x1, y1 = ctx.cap["geom"]["boxes"]["verify"]
    tgt = f' data-story-to="{to}"' if to else ""
    return (f'<g class="vc-vbtn {cls}"{tgt}><rect class="vc-hit" x="{x0:.1f}" y="{y0:.1f}" width="{x1 - x0:.1f}" height="{y1 - y0:.1f}" rx="7"/>'
            f'{inner}</g>')


def status(ctx: Ctx, items: list, to: str | None = None, cls: str = "") -> str:
    """The Verify button's status (marimo's run button): count pills centred under the live button."""
    x0, y0, x1, y1 = ctx.cap["geom"]["boxes"]["verify"]
    ws = [10 + 6.2 * len(t) for t, _k in items]
    gap = 4.0
    x = (x0 + x1) / 2 - (sum(ws) + gap * (len(ws) - 1)) / 2
    out = []
    for (t, k), w in zip(items, ws):
        out.append(chip(x, y1 + 14, t, k, w, anchor="start"))
        x += w + gap
    return verify_btn(ctx, "".join(out), to, cls)


def chip(x, y, text, kind="grey", w=None, anchor="middle") -> str:
    """A small count pill (SVG)."""
    w = w or (8 + 6.4 * len(text))
    col = {"grey": ("#eef0f3", "#4b5563", "#c9ced6"), "bad": ("#fdecec", BAD, "#f0b4b4"), "ok": ("#e7f5ee", OK, "#a6d8bf"),
           "acc": ("#e9f0fe", "#1d4fb8", "#b5c9f7")}[kind]
    x0 = x - w / 2 if anchor == "middle" else x
    return (f'<g class="vc-chip"><rect x="{x0:.1f}" y="{y - 9:.1f}" width="{w:.1f}" height="18" rx="9" fill="{col[0]}" stroke="{col[2]}"/>'
            f'<text x="{x0 + w / 2:.1f}" y="{y + 4:.1f}" text-anchor="middle" fill="{col[1]}" class="vc-chipt">{E(text)}</text></g>')


# ================================================================== 5. the variants

STATES = ["made", "running", "done", "edited", "again"]


def running_sets(ctx: Ctx):
    done = ORDER[:RUN_DONE]
    cur = ORDER[RUN_DONE]
    queued = ORDER[RUN_DONE + 1:]
    return done, cur, queued


def why_html(ctx: Ctx, k: str, fixed=False, n=4) -> str:
    v = (ctx.vfix if fixed else ctx.v)[k]
    names = {r["id"]: r["name"] for r in THRESHOLD_ROWS}
    if v["pass"]:
        r = v["range"]
        return f'<div class="vc-why ok">Passes all 6 thresholds · reads {m(r["near_mm"])} – {m(r["far_mm"])}</div>'
    return "".join(f'<div class="vc-why"><b>{E(names[t])}</b> {E(w)}</div>' for t, w in v["why"][:n])


def detail_card(ctx: Ctx, k: str, *, fan_r=78, fixed=False, fix_to="edited", title_extra="", foot=True, w=330, tail="") -> str:
    """The marker's detail: its title, the thresholds it fails with numbers, the
    fan, the measured fix and the ways to the strip and the bench (V1's popover,
    V5's walk card)."""
    c = ctx.case[k]
    v = (ctx.vfix if fixed else ctx.v)[k]
    rows = fan_rows(ctx, k, fixed)
    fsvg = (f'<svg viewBox="-6 {-fan_r - 14} {fan_r + 50} {2 * fan_r + 26}" class="vc-cardfan">'
            + fan(rows, 0, 0, fan_r, need=DEMO_NEED, tone="ok" if v["pass"] else "bad", labels=False) + "</svg>")
    head = "PASS" if v["pass"] else f"FAIL · {len(v['why'])} of 6"
    fx = ctx.data["fixed"][NEWEST]
    fixbtn = "" if (fixed or k != DETAIL) else (
        f'<button class="vc-btn pri" data-story-to="{fix_to}">Label height: Auto</button>'
        f'<span class="vc-mut">measured: reads {m(fx["range"]["near_mm"])} – {m(fx["range"]["far_mm"])}, label costs {fx["check"]["cost_pts"]:.1f} pts</span>')
    links = '<span class="vc-link">Range strip ▸</span><span class="vc-link">Bench ▸</span>'
    meta = (f'<div class="vc-meta">D435 colour · OpenCV {NEWEST[:-2]} · Field · key {E((ctx.data["fixed"]["verify_key"] if fixed and k == DETAIL else c["verify_key"])[:8])}</div>') if foot else ""
    return (f'<div class="vc-card" style="width:{w}px"><div class="vc-card-h"><b>#{c["ids"][0] if len(c["ids"]) == 1 else str(c["ids"][0]) + "–" + str(c["ids"][-1])}</b>'
            f'<span>{E(c["title"])}</span><i class="{"ok" if v["pass"] else "bad"}">{head}</i>{title_extra}</div>'
            f'<div class="vc-card-b"><div class="vc-card-w">{why_html(ctx, k, fixed)}<div class="vc-fix">{fixbtn}</div>'
            f'<div class="vc-links">{links}</div></div>{fsvg}</div>{tail}{meta}</div>')


# ---- V1 Marimo badges

def v1(ctx: Ctx) -> dict:
    done, cur, queued = running_sets(ctx)
    C, T = [], []
    # running: done fails badged, recent passes flashing, the current one spinning, the rest queued
    for k in done:
        if not ctx.v[k]["pass"]:
            C.append(f'<g class="{st("running")}">{g_bad(*ctx.corner(k))}</g>')
        elif k in FLASH_RECENT:
            C.append(f'<g class="{st("running")}">{flash(ctx, k)}</g>')
    C.append(f'<g class="{st("running")}">{g_spin(*ctx.corner(cur), frac=0.4)}</g>')
    for k in queued:
        C.append(f'<g class="{st("running")}">{g_queued(*ctx.corner(k))}</g>')
    # done / edited / again: failures persist
    for k in ctx.fails:
        if k == DETAIL:
            C.append(f'<g class="{st("done")} vc-b-{k}">{g_bad(*ctx.corner(k), r=8.5)}</g>')
            C.append(f'<g class="{st("edited")}">{g_stale(*ctx.corner(k))}</g>')
            C.append(f'<g class="{st("again")}">{flash(ctx, k)}</g>')
        else:
            C.append(f'<g class="{st("done edited again")}">{g_bad(*ctx.corner(k))}</g>')
    for k in ctx.passes:
        C.append(f'<g class="{st("again")}">{flash(ctx, k)}</g>')
    C.append(f'<g class="{st("done")}">{hit(ctx, DETAIL, "done", "vc-sel")}</g>')
    x0, y0, x1, y1 = ctx.b(DETAIL)
    T.append(f'<g class="{st("done")}"><path d="M{x1 + 10:.1f} {(y0 + y1) / 2:.1f}l12 -8v16z" fill="#fff" stroke="#dadee4"/>'
             + fo(x1 + 21, y0 - 80, 360, 330, detail_card(ctx, DETAIL, w=354), "vc-pop") + "</g>")
    # the Verify button's status (marimo's run button: what is stale, what failed)
    vx0, vy0, vx1, vy1 = ctx.cap["geom"]["boxes"]["verify"]
    T.append(f'<g class="{st("made")}">' + status(ctx, [("28 new", "grey")], "running", "vc-vb-made") + "</g>")
    T.append(f'<g class="{st("running")}">' + status(ctx, [(f"{RUN_DONE} / 28", "acc")]) + "</g>")
    T.append(f'<g class="{st("done")}">' + status(ctx, [(f"{len(ctx.fails)}", "bad")]) + "</g>")
    T.append(f'<g class="{st("edited")}">' + status(ctx, [("1 stale", "grey"), (f"{len(ctx.fails) - 1}", "bad")], "again", "vc-vb-edited") + "</g>")
    T.append(f'<g class="{st("again")}">' + status(ctx, [(f"{len(ctx.fails_fixed)}", "bad")]) + "</g>")
    preview = stage("".join(C), "".join(T), fix="st st-edited st-again")
    # media: the five states, close up, on real markers
    legend = state_strip(ctx, {
        "unverified": ("A1", "", "nothing drawn; the button counts it"),
        "stale": (DETAIL, g_stale(*ctx.corner(DETAIL)), "edited since: kept, marked, not trusted"),
        "computing": ("C2", g_spin(*ctx.corner("C2"), frac=0.4), "spins; the ring is the engine's own fraction"),
        "passed": ("B9", flash(ctx, "B9", "vc-hold"), "flashes, then fades to nothing (2.4 s)"),
        "failed": ("D4", g_bad(*ctx.corner("D4")), "stays until the marker passes"),
    }, fix_for="stale")
    x0, y0, x1, y1 = ctx.b(DETAIL)
    pop = stage(f'{g_bad(*ctx.corner(DETAIL), r=8.5)}',
                f'<path d="M{x1 + 10:.1f} {(y0 + y1) / 2:.1f}l12 -8v16z" fill="#fff" stroke="#dadee4"/>' + fo(x1 + 21, y0 - 80, 360, 330, detail_card(ctx, DETAIL, w=354), "vc-pop"),
                view=(x0 - 40, y0 - 96, 470, 340))
    media = [
        {"label": "The five states, on real markers", "caption": "Close-ups of the board's own stickers: a badge sits on the sticker's corner, outside its black, so it never covers what prints.", "html": legend},
        {"label": "Click a red badge: the why, the fan, the fix", "caption": f"B6's popover: every threshold it fails, with the measured numbers; its fan (empty: it reads nowhere); the fix re-measured ({m(ctx.data['fixed'][NEWEST]['range']['far_mm'])} after Label Auto); Range strip and Bench one click.", "html": pop},
    ]
    steps = [
        {"label": "Make", "caption": "28 markers, none verified. Nothing on the canvas; the Verify button says 28 new.", "state": "made", "target": ".st-made .vc-vbtn"},
        {"label": "Press Verify", "caption": f"Reading order, one marker at a time: failures get a red badge and keep it; passes flash green and fade. #{ctx.case[cur]['ids'][0]} spins, the rest wait (grey dot).", "state": "running", "target": ".st-running .vc-spin"},
        {"label": "Results in", "caption": f"{len(ctx.passes)} passes are gone; {len(ctx.fails)} red badges stay. Click B6's: why it fails, in numbers, its fan, and the measured fix.", "state": "done", "target": ".vc-pop"},
        {"label": "Edit one", "caption": "Label height: Auto. B6's badge turns hollow grey (stale); moving or turning any marker would not, its key ignores position.", "state": "edited", "target": ".st-edited .vc-vbtn"},
        {"label": "Verify again", "caption": f"The {len(ctx.passes)} cached passes flash at once ({ctx.flash_ms:.0f} ms, measured); only B6 runs ({ctx.b6fix_txt}) and passes; the {len(ctx.fails_fixed)} unchanged failures are not re-rendered.", "state": "again", "target": ".st-again .vc-flash"},
    ]
    return {"preview": preview, "media": media, "steps": steps}


def state_strip(ctx: Ctx, cells: dict, fix_for: str | None = None, below: dict | None = None, pad=(26, 24)) -> str:
    """Five close-up crops of real markers, one state each."""
    out = []
    for name, (k, svg, words) in cells.items():
        x0, y0, x1, y1 = ctx.b(k)
        w = max(x1 - x0, y1 - y0) + 2 * pad[0]
        h = w * 0.9 + (below.get(name, 0) if below else 0)
        cx = (x0 + x1) / 2
        view = (cx - w / 2, y0 - pad[1], w, h)
        fix = "vc-on" if (fix_for == name) else ""
        out.append(f'<figure class="vc-cell">{stage(svg, view=view, fix=fix)}<figcaption><b>{E(name)}</b>{E(words)}</figcaption></figure>')
    return f'<div class="vc-strip">{"".join(out)}</div>'


# ---- V2 Verify layer

def bar(ctx: Ctx, k: str, tone: str, need=DEMO_NEED, cls="", fixed=False, dash=False, frac=None) -> str:
    """The range strip's band, moved under its own marker: near–far on one log axis (0.04–1.5 m)."""
    x0, y0, x1, y1 = ctx.b(k)
    y = y1 + 7.0
    L, Rr = x0, x0 + max(58.0, x1 - x0)

    def X(d):
        return L + (Rr - L) * min(1.0, max(0.0, math.log(max(d, FAN_D0) / FAN_D0) / math.log(FAN_D1 / FAN_D0)))
    v = (ctx.vfix if fixed else ctx.v)[k]["range"]
    col = {"ok": "#9aa3ad", "flash": OK, "bad": BAD, "grey": STALE, "none": "#c3c9d1"}[tone]
    s = [f'<g class="vc-bar {cls}"><line x1="{L:.1f}" x2="{Rr:.1f}" y1="{y:.1f}" y2="{y:.1f}" stroke="#d3d8de" stroke-width="1"/>']
    if need:
        for d in need:
            s.append(f'<line x1="{X(d):.1f}" x2="{X(d):.1f}" y1="{y - 4:.1f}" y2="{y + 4:.1f}" stroke="{ACC}" stroke-width="1" opacity=".7"/>')
    if frac is not None:
        s.append(f'<line class="vc-sweep" x1="{L:.1f}" x2="{L + (Rr - L) * frac:.1f}" y1="{y:.1f}" y2="{y:.1f}" stroke="{ACC}" stroke-width="3" stroke-linecap="round"/>')
    elif tone == "none":
        s.append(f'<line x1="{L:.1f}" x2="{Rr:.1f}" y1="{y:.1f}" y2="{y:.1f}" stroke="#c3c9d1" stroke-width="3" stroke-dasharray="1.5 3" stroke-linecap="round"/>')
    elif v["far_mm"]:
        da = ' stroke-dasharray="3 2.5"' if dash else ""
        s.append(f'<line x1="{X(v["near_mm"] or FAN_D0):.1f}" x2="{X(v["far_mm"]):.1f}" y1="{y:.1f}" y2="{y:.1f}" stroke="{col}" stroke-width="{3.2 if tone in ("bad", "flash") else 2.4}" stroke-linecap="round"{da}/>')
    else:
        s.append(f'<text x="{(L + Rr) / 2:.1f}" y="{y + 3.5:.1f}" text-anchor="middle" class="vc-bart" fill="{col}">reads nowhere</text>')
    if tone == "bad":
        s.append(g_bad(Rr + 6, y, 4.6))
    s.append("</g>")
    return "".join(s)


def layers_menu(ctx: Ctx, on: bool, to: str | None = None) -> str:
    """The calm-canvas lane's Layers menu (web/src/overlays/LayersMenu.tsx, in flight) with one row added."""
    tb = ctx.cap["geom"]["boxes"]["toolbar"]
    rows = [("Sketch dimensions", True), ("Joint Origins", True), ("Profile edges", True), ("Quiet-zone guides", True),
            ("Marker info", False), ("Rulers", True)]
    sw = lambda o: f'<span class="vc-sw{" on" if o else ""}"><i></i></span>'  # noqa: E731
    items = "".join(f'<div class="vc-mrow"><span>{E(n)}</span>{sw(o)}</div>' for n, o in rows)
    tgt = f' data-story-to="{to}"' if to else ""
    vr = (f'<div class="vc-mrow vc-new"{tgt}><span>Verify results <small>badges · reach bars</small></span>{sw(on)}</div>')
    inner = (f'<div class="vc-menu"><div class="vc-mrow"><span>Grid</span><small>Grid ›</small></div><hr/>{items}<hr/>{vr}</div>')
    x = tb[2] + 36 - 130
    return fo(x, tb[1] - 268, 260, 262, inner, "vc-lm")


def layers_btn(ctx: Ctx, active: bool) -> str:
    """The Layers button the calm-canvas lane adds to the dock, drawn over its future slot (after Fit)."""
    tb = ctx.cap["geom"]["boxes"]["toolbar"]
    x, y = tb[2] + 10, tb[1] + 6
    return (f'<g class="vc-lbtn"><rect x="{x - 6:.1f}" y="{y - 6:.1f}" width="52" height="52" rx="12" fill="#fff" stroke="#dadee4"/>'
            f'<rect x="{x:.1f}" y="{y:.1f}" width="40" height="40" rx="9" fill="{"#e9f0fe" if active else "#fff"}"/>'
            f'<path d="M{x + 20} {y + 11}l9 4.5-9 4.5-9-4.5z M{x + 11} {y + 20}l9 4.5 9-4.5 M{x + 11} {y + 24.5}l9 4.5 9-4.5" fill="none" '
            f'stroke="{ACC if active else "#374151"}" stroke-width="1.6" stroke-linejoin="round"/></g>')


def v2(ctx: Ctx) -> dict:
    done, cur, queued = running_sets(ctx)
    C, T = [], []
    for k in ORDER:
        C.append(f'<g class="{st("made")}">{bar(ctx, k, "none")}</g>')
    for k in done:
        tone = "bad" if not ctx.v[k]["pass"] else ("flash" if k in FLASH_RECENT else "ok")
        C.append(f'<g class="{st("running")}">{bar(ctx, k, tone)}</g>')
    C.append(f'<g class="{st("running")}">{bar(ctx, cur, "none", frac=0.4)}</g>')
    for k in queued:
        C.append(f'<g class="{st("running")}">{bar(ctx, k, "none")}</g>')
    for k in ORDER:
        tone = "ok" if ctx.v[k]["pass"] else "bad"
        if k == DETAIL:
            C.append(f'<g class="{st("done")}">{bar(ctx, k, tone)}</g>')
            C.append(f'<g class="{st("edited")}">{bar(ctx, k, "grey", dash=True)}</g>')
            C.append(f'<g class="{st("again")}">{bar(ctx, k, "flash", fixed=True)}</g>')
        else:
            C.append(f'<g class="{st("done edited")}">{bar(ctx, k, tone)}</g>')
            C.append(f'<g class="{st("again")}">{bar(ctx, k, "flash" if tone == "ok" else "bad")}</g>')
    # hover a bar: its fan, for the detail
    hk = "A1"
    x0, y0, x1, y1 = ctx.b(hk)
    hx = x1 + 18
    C.append(f'<g class="{st("done")}">{hit(ctx, hk, "done")}</g>')
    T.append(f'<g class="{st("done")}">' + fo(hx, y0 - 16, 300, 300,
             f'<div class="vc-card" style="width:290px"><div class="vc-card-h"><b>#0</b><span>No label · hover the bar</span><i class="ok">PASS</i></div>'
             f'<svg viewBox="-8 -92 220 186" class="vc-cardfan2">{fan(fan_rows(ctx, hk), 0, 0, 84, need=DEMO_NEED, tone="ok")}</svg>'
             f'<div class="vc-meta">{m(ctx.v[hk]["range"]["near_mm"])} – {m(ctx.v[hk]["range"]["far_mm"])} over the budget · head on {m(next(r["far_mm"] for r in fan_rows(ctx, hk) if r["angle"] == 0))} · ±45°: '
             f'{m(next(r["far_mm"] for r in fan_rows(ctx, hk) if r["angle"] == -45))} / {m(next(r["far_mm"] for r in fan_rows(ctx, hk) if r["angle"] == 45))}</div></div>', "vc-pop") + "</g>")
    T.append(f'<g class="{st("made")}">{layers_btn(ctx, True)}{layers_menu(ctx, True, "running")}' + status(ctx, [("28 new", "grey")], "running") + "</g>")
    T.append(f'<g class="{st("running done edited again")}">{layers_btn(ctx, True)}</g>')
    vx0, vy0, vx1, vy1 = ctx.cap["geom"]["boxes"]["verify"]
    T.append(f'<g class="{st("running")}">' + status(ctx, [(f"{RUN_DONE} / 28", "acc")]) + "</g>")
    T.append(f'<g class="{st("done")}">' + status(ctx, [(f"{len(ctx.fails)}", "bad")]) + "</g>")
    T.append(f'<g class="{st("edited")}">' + status(ctx, [("1 stale", "grey"), (f"{len(ctx.fails) - 1}", "bad")], "again", "vc-vb-edited") + "</g>")
    T.append(f'<g class="{st("again")}">' + status(ctx, [(f"{len(ctx.fails_fixed)}", "bad")]) + "</g>")
    preview = stage("".join(C), "".join(T), fix="st st-edited st-again")
    legend = state_strip(ctx, {
        "unverified": ("A1", bar(ctx, "A1", "none"), "a dotted axis: nothing measured"),
        "stale": (DETAIL, bar(ctx, DETAIL, "grey", dash=True, fixed=True), "the old band, dashed grey"),
        "computing": ("C2", bar(ctx, "C2", "none", frac=0.4), "the axis fills with the engine's fraction"),
        "passed": ("B9", bar(ctx, "B9", "flash"), "green, then thin grey (turned down)"),
        "failed": ("E2", bar(ctx, "E2", "bad"), "red band and ✕, kept; blue ticks: 0.15 / 0.5 m"),
    }, fix_for="stale", below={k: 14 for k in ("unverified", "stale", "computing", "passed", "failed")})
    tb = ctx.cap["geom"]["boxes"]["toolbar"]
    menu = stage("", layers_btn(ctx, True) + layers_menu(ctx, True), view=(tb[0] + 200, tb[1] - 300, 420, 366))
    media = [
        {"label": "The five states, on real markers", "caption": "Each marker's reading range drawn as a band right under it (0.04–1.5 m, log), the requirement's two ends as blue ticks: the range strip, with nothing to associate.", "html": legend},
        {"label": "One more row in the Layers menu", "caption": "The calm-canvas lane's Layers menu (in flight on lane/os-calmcanvas) gains ‘Verify results’; Verify turns it on, the switch hides it. Drawn over the dock; the menu's rows are that lane's.", "html": menu},
    ]
    steps = [
        {"label": "Make", "caption": "Layers › Verify results is on: every marker carries an empty axis under it. Nothing measured yet.", "state": "made", "target": ".vc-new"},
        {"label": "Press Verify", "caption": "The axes fill one by one: a red band and ✕ for a failure, green for a pass that then settles to thin grey, like every other turned-down layer.", "state": "running", "target": ".st-running .vc-sweep"},
        {"label": "Results in", "caption": f"All 28 bands on the canvas, {len(ctx.fails)} red. Comparing reach across markers is a glance along the rows; hover a band for its fan.", "state": "done", "target": ".vc-pop"},
        {"label": "Edit one", "caption": "B6's label to Auto: its band goes dashed grey (stale) until Verify.", "state": "edited", "target": ".st-edited .vc-vbtn"},
        {"label": "Verify again", "caption": f"Cached bands flash green at once ({ctx.flash_ms:.0f} ms); B6 runs ({ctx.b6fix_txt}) and gets its band: {m(ctx.vfix[DETAIL]['range']['near_mm'])} – {m(ctx.vfix[DETAIL]['range']['far_mm'])}.", "state": "again", "target": ".st-again .vc-bar"},
    ]
    return {"preview": preview, "media": media, "steps": steps}


# ---- V3 Verify mode

def mode_toggle(ctx: Ctx, verify: bool, to: str | None = None) -> str:
    d = ctx.cap["geom"]["boxes"]["doc"]
    x, y = d[2] + 14, d[1] + 6
    tgt = f' data-story-to="{to}"' if to else ""
    return (f'<g class="vc-mode"{tgt}><rect x="{x:.1f}" y="{y:.1f}" width="150" height="40" rx="10" fill="#fff" stroke="#dadee4"/>'
            f'<rect x="{x + 4 + (71 if verify else 0):.1f}" y="{y + 4:.1f}" width="71" height="32" rx="7" fill="{"#e9f0fe" if verify else "#f1f3f6"}"/>'
            f'<text x="{x + 39.5:.1f}" y="{y + 25:.1f}" text-anchor="middle" class="vc-modet{"" if verify else " on"}">Edit</text>'
            f'<text x="{x + 110.5:.1f}" y="{y + 25:.1f}" text-anchor="middle" class="vc-modet{" on" if verify else ""}">Verify</text>'
            f'<rect class="vc-hit" x="{x:.1f}" y="{y:.1f}" width="150" height="40" rx="10"/></g>')


def mini_fan(ctx: Ctx, k: str, tone: str, fixed=False, cls="") -> str:
    x0, y0, x1, y1 = ctx.b(k)
    cx = (x0 + x1) / 2
    return fan(fan_rows(ctx, k, fixed), cx, y0 - 2, 25, axis=-90, tone=tone, mini=True, rings=False, labels=False,
               spokes=False, marker=False, cls=cls)


def verify_panel(ctx: Ctx, fixed=False) -> str:
    fails = ctx.fails_fixed if fixed else ctx.fails
    v = ctx.vfix if fixed else ctx.v
    cnt = {}
    for k in fails:
        for t, _w in v[k]["why"]:
            cnt[t] = cnt.get(t, 0) + 1
    trs = "".join(f'<tr><td>{E(r["name"])}</td><td class="val">{E(r["value"].split(" · ")[0] if r["id"] != "need" else "0.15 – 0.5 m")}</td>'
                  f'<td class="n{" bad" if cnt.get(r["id"]) else ""}">{cnt.get(r["id"], 0)}</td></tr>' for r in THRESHOLD_ROWS)
    lst = "".join(f'<div class="vc-li"><i></i><b>{E(ctx.case[k]["title"][:30])}</b><span>{E(dict(v[k]["why"]).get(v[k]["why"][0][0])[:44])}…</span></div>'
                  for k in fails[:7])
    return (f'<div class="vc-panel"><div class="vc-ph">Verify <span>{len(ORDER) - len(fails)} pass · <b>{len(fails)} fail</b></span></div>'
            f'<div class="vc-prow"><span>Camera</span><b>RealSense D435 · colour 1920×1080</b></div>'
            f'<div class="vc-prow"><span>OpenCV</span><b>5.0 (newest) ⌄</b></div>'
            f'<div class="vc-prow"><span>Budget</span><b>Field: tilt ≤ 45° · blur ≤ 1.5 px</b></div>'
            f'<div class="vc-psec">Thresholds <small>fails</small></div><table class="vc-pt">{trs}</table>'
            f'<div class="vc-psec">Failing</div>{lst}<div class="vc-more">+ {max(0, len(fails) - 7)} more</div></div>')


def v3(ctx: Ctx) -> dict:
    done, cur, queued = running_sets(ctx)
    C, T = [], []
    C.append(f'<rect class="{st("running done again")} vc-veil" x="0" y="0" width="1440" height="900"/>')
    for k in done:
        tone = "bad" if not ctx.v[k]["pass"] else "grey"
        fl = f'<g class="vc-flash">{mini_fan(ctx, k, "ok")}</g>' if k in FLASH_RECENT else ""
        C.append(f'<g class="{st("running")}">{mini_fan(ctx, k, tone)}{fl}{g_bad(*ctx.corner(k), r=5.5) if tone == "bad" else ""}</g>')
    C.append(f'<g class="{st("running")}">{g_spin(*ctx.corner(cur), frac=0.4)}</g>')
    for k in ORDER:
        tone = "grey" if ctx.v[k]["pass"] else "bad"
        if k == DETAIL:
            C.append(f'<g class="{st("done")}">{mini_fan(ctx, k, tone)}{g_bad(*ctx.corner(k), r=5.5)}</g>')
            C.append(f'<g class="{st("again")}">{mini_fan(ctx, k, "grey", fixed=True)}<g class="vc-flash">{mini_fan(ctx, k, "ok", fixed=True)}{g_ok(*ctx.corner(k), r=5.5)}</g></g>')
            C.append(f'<g class="{st("edited")}">{g_stale(*ctx.corner(k), r=5)}</g>')
        else:
            C.append(f'<g class="{st("done")}">{mini_fan(ctx, k, tone)}{g_bad(*ctx.corner(k), r=5.5) if tone == "bad" else ""}</g>')
            C.append(f'<g class="{st("again")}">{mini_fan(ctx, k, tone)}' + (f'<g class="vc-flash">{mini_fan(ctx, k, "ok")}</g>' if tone == "grey" else g_bad(*ctx.corner(k), r=5.5)) + "</g>")
            if tone == "bad":
                C.append(f'<g class="{st("edited")}">{g_dot(*ctx.corner(k, 2, -2))}</g>')
    px = 1440 - 12 - 320
    T.append(f'<g class="{st("done")}">' + fo(px, 90, 320, 720, verify_panel(ctx), "vc-pan") + "</g>")
    T.append(f'<g class="{st("again")}">' + fo(px, 90, 320, 720, verify_panel(ctx, True), "vc-pan") + "</g>")
    T.append(f'<g class="{st("running")}">' + fo(px, 90, 320, 120, f'<div class="vc-panel"><div class="vc-ph">Verify <span>{RUN_DONE} of 28 · #{ctx.case[cur]["ids"][0]} 40 %</span></div><div class="vc-prow"><span>Camera</span><b>RealSense D435</b></div><div class="vc-prow"><span>OpenCV</span><b>5.0 (newest)</b></div></div>', "vc-pan") + "</g>")
    T.append(f'<g class="{st("made edited")}">{mode_toggle(ctx, False, "running")}</g>')
    T.append(f'<g class="{st("running done again")}">{mode_toggle(ctx, True, "edited")}</g>')
    vx0, vy0, vx1, vy1 = ctx.cap["geom"]["boxes"]["verify"]
    T.append(f'<g class="{st("edited")}">' + status(ctx, [("1 stale", "grey")], "again", "vc-vb-edited") + "</g>")
    preview = stage("".join(C), "".join(T), fix="st st-edited st-again")
    legend = state_strip(ctx, {
        "unverified": ("A1", "", "Edit mode: nothing; Verify mode runs it"),
        "stale": (DETAIL, g_stale(*ctx.corner(DETAIL), r=5), "back in Edit: grey ring until Verify mode"),
        "computing": ("C2", g_spin(*ctx.corner("C2"), frac=0.4), "spins while its fan is measured"),
        "passed": ("B9", mini_fan(ctx, "B9", "ok", cls="vc-hold"), "fan green, then grey"),
        "failed": ("E2", mini_fan(ctx, "E2", "bad") + g_bad(*ctx.corner("E2"), r=5.5), "red fan + ✕, kept"),
    }, fix_for="stale", pad=(26, 40))
    panel = stage("", fo(px, 90, 320, 720, verify_panel(ctx), "vc-pan"), view=(px - 20, 80, 360, 560))
    media = [
        {"label": "The five states, on real markers", "caption": "In Verify mode every marker grows its own fan above it (±75°, log distance; real per-angle ranges for all 28).", "html": legend},
        {"label": "The Verify panel replaces the Extrude panel", "caption": "Camera, OpenCV (one, the newest by default), the budget, the six thresholds with how many markers each fails, and the failing list: Fusion swaps the browser the same way between workspaces.", "html": panel},
    ]
    steps = [
        {"label": "Make (Edit)", "caption": "Edit mode, as today: nothing about Verify on the canvas.", "state": "made", "target": ".st-made .vc-mode"},
        {"label": "Verify mode", "caption": "Pressing Verify switches the canvas to Verify: edit chrome dims, each marker grows a fan as it is measured, the panel lists progress.", "state": "running", "target": ".st-running .vc-pan"},
        {"label": "Results in", "caption": f"Every fan on the canvas, {len(ctx.fails)} red; the panel holds the thresholds and the failing list.", "state": "done", "target": ".st-done .vc-pan"},
        {"label": "Edit one", "caption": "Back to Edit to fix B6 (label Auto): Edit shows only red dots on failures and a grey ring on what you changed.", "state": "edited", "target": ".st-edited .vc-mode"},
        {"label": "Verify again", "caption": f"Verify mode again: cached fans appear at once ({ctx.flash_ms:.0f} ms) and flash; only B6 runs ({ctx.b6fix_txt}).", "state": "again", "target": ".st-again .vc-pan"},
    ]
    return {"preview": preview, "media": media, "steps": steps}


# ---- V4 Hover fan

def big_fan(ctx: Ctx, k: str, fixed=False, R=210.0, need=DEMO_NEED) -> str:
    """The hovered marker's fan on the canvas: apex at its right edge, the axis laid flat to the right; the rest dimmed."""
    x0, y0, x1, y1 = ctx.b(k)
    cx, cy = x1 + 2, (y0 + y1) / 2
    v = (ctx.vfix if fixed else ctx.v)[k]
    rows = fan_rows(ctx, k, fixed)
    r = v["range"]
    head = next((x["far_mm"] for x in rows if x["angle"] == 0), None)
    words = (f'{m(r["near_mm"])} – {m(r["far_mm"])} over the budget · {m(head)} head on' if r["far_mm"] else "reads nowhere")
    fars = [x["far_mm"] or 0 for x in rows if abs(x["angle"]) <= 45]
    vs_need = ("short of " + m(need[1]) + " at every angle to ±45°" if need and max(fars) < need[1] else
               "covers " + m(need[1]) + " out to ±45°" if need and min(fars) >= need[1] else
               "covers " + m(need[1]) + " at some angles only") if need else ""
    kind = {"single": "", "grid": "Grid · ", "charuco": "ChArUco · "}[ctx.case[k]["type"]]
    tag = (f'<g transform="translate({cx + R + 12:.1f},{cy - 40:.1f})"><rect width="250" height="78" rx="8" fill="#fff" stroke="#dadee4" filter="url(#vc-sh)"/>'
           f'<text x="12" y="22" class="vc-tagt"><tspan class="{"ok" if v["pass"] else "bad"}">{"PASS" if v["pass"] else "FAIL"}</tspan> · {k} {E(kind)}#{ctx.case[k]["ids"][0]}</text>'
           f'<text x="12" y="42" class="vc-tags">{E(words)}</text><text x="12" y="60" class="vc-tags">{E(vs_need)}</text></g>')
    veil = f'<path class="vc-veil2" fill-rule="evenodd" d="M0 0H1440V900H0Z M{x0 - 3:.1f} {y0 - 3:.1f}V{y1 + 3:.1f}H{x1 + 3:.1f}V{y0 - 3:.1f}Z"/>'
    return veil + fan(rows, cx, cy, R, axis=0, need=need, tone="ok" if v["pass"] else "bad", cls="vc-bigfan") + tag


def v4(ctx: Ctx) -> dict:
    done, cur, queued = running_sets(ctx)
    C, T = [], []
    for k in done:
        if not ctx.v[k]["pass"]:
            C.append(f'<g class="{st("running")}">{g_dot(*ctx.corner(k, 2, -2))}</g>')
        elif k in FLASH_RECENT:
            C.append(f'<g class="{st("running")}">{flash(ctx, k)}</g>')
    C.append(f'<g class="{st("running")}">{g_spin(*ctx.corner(cur), r=6, frac=0.4)}</g>')
    for k in ctx.fails:
        if k == DETAIL:
            C.append(f'<g class="{st("done")}">{g_dot(*ctx.corner(k, 2, -2))}</g>')
            C.append(f'<g class="{st("edited")}">{g_stale(*ctx.corner(k, 2, -2), r=5)}</g>')
            C.append(f'<g class="{st("again")}">{flash(ctx, k)}</g>')
        else:
            C.append(f'<g class="{st("done edited again")}">{g_dot(*ctx.corner(k, 2, -2))}</g>')
    for k in ctx.passes:
        C.append(f'<g class="{st("again")}">{flash(ctx, k)}</g>')
    hk = "E2"
    C.append(f'<g class="{st("done")}">{big_fan(ctx, hk)}</g>')
    C.append(f'<g class="{st("done")}">{hit(ctx, hk, "done", "vc-sel")}</g>')
    vx0, vy0, vx1, vy1 = ctx.cap["geom"]["boxes"]["verify"]
    T.append(f'<g class="{st("made")}">' + status(ctx, [("28 new", "grey")], "running", "vc-vb-made") + "</g>")
    T.append(f'<g class="{st("running")}">' + status(ctx, [(f"{RUN_DONE} / 28", "acc")]) + "</g>")
    T.append(f'<g class="{st("done")}">' + status(ctx, [(f"{len(ctx.fails)}", "bad")]) + "</g>")
    T.append(f'<g class="{st("edited")}">' + status(ctx, [("1 stale", "grey"), (f"{len(ctx.fails) - 1}", "bad")], "again", "vc-vb-edited") + "</g>")
    T.append(f'<g class="{st("again")}">' + status(ctx, [(f"{len(ctx.fails_fixed)}", "bad")]) + "</g>")
    preview = stage("".join(C), "".join(T), fix="st st-edited st-again")
    legend = state_strip(ctx, {
        "unverified": ("A1", "", "nothing; the button counts it"),
        "stale": (DETAIL, g_stale(*ctx.corner(DETAIL, 2, -2), r=5), "a small grey ring"),
        "computing": ("C2", g_spin(*ctx.corner("C2"), r=6, frac=0.4), "spins"),
        "passed": ("B9", flash(ctx, "B9", "vc-hold"), "flashes, fades to nothing"),
        "failed": ("D4", g_dot(*ctx.corner("D4", 2, -2)), "a 4 px red dot, kept"),
    }, fix_for="stale")
    x0, y0, x1, y1 = ctx.b("A1")
    hov = stage(big_fan(ctx, "A1", R=210.0), view=(x0 - 30, y0 - 200 + 30, 700, 420))
    media = [
        {"label": "The five states, on real markers", "caption": "The quietest at rest: a failure is a 4 px dot on the sticker's corner; a pass leaves nothing behind.", "html": legend},
        {"label": "Hover any marker: its fan, on the canvas", "caption": "A1 (no label) on the D435 under the Field budget: the reading zone from 42 mm out to the far end at every yaw from −75° to +75°, the pale fringe its 90 % interval; the dashed blue sector is the requirement (0.15–0.5 m over ±45°). Real per-angle ranges.", "html": hov},
    ]
    steps = [
        {"label": "Make", "caption": "Nothing on the canvas; the Verify button says 28 new.", "state": "made", "target": ".st-made .vc-vbtn"},
        {"label": "Press Verify", "caption": "Failures leave a red dot, passes flash and vanish, one marker spins at a time.", "state": "running", "target": ".st-running .vc-spin"},
        {"label": "Hover a marker", "caption": f"Point at E2 (ChArUco 5 × 4): the board dims and its fan opens to the right — {m(next(r['far_mm'] for r in ctx.fans['E2'] if r['angle'] == 0))} head on, short of the 0.5 m sector at every angle. One fan at a time; a click pins it.", "state": "done", "target": ".vc-bigfan"},
        {"label": "Edit one", "caption": "B6's label to Auto: its dot becomes a grey ring.", "state": "edited", "target": ".st-edited .vc-vbtn"},
        {"label": "Verify again", "caption": f"Cached passes flash ({ctx.flash_ms:.0f} ms); B6 runs ({ctx.b6fix_txt}), passes, fades.", "state": "again", "target": ".st-again .vc-flash"},
    ]
    return {"preview": preview, "media": media, "steps": steps}


# ---- V5 Fix-it walk (steelman: not asked for)

def v5(ctx: Ctx) -> dict:
    done, cur, queued = running_sets(ctx)
    C, T = [], []
    for k in done:
        if not ctx.v[k]["pass"]:
            C.append(f'<g class="{st("running")}">{outline(ctx, k, BAD, w=1.6)}</g>')
        elif k in FLASH_RECENT:
            C.append(f'<g class="{st("running")}"><g class="vc-flash">{outline(ctx, k, OK, w=2.4)}</g></g>')
    C.append(f'<g class="{st("running")}">{g_spin(*ctx.corner(cur), r=6, frac=0.4)}</g>')
    for k in ctx.fails:
        if k == DETAIL:
            C.append(f'<g class="{st("done")}">{outline(ctx, k, BAD, w=2.4)}</g>')
            C.append(f'<g class="{st("edited")}">{outline(ctx, k, STALE, w=1.6, dash="3 2.5")}</g>')
            C.append(f'<g class="{st("again")}"><g class="vc-flash">{outline(ctx, k, OK, w=2.4)}</g></g>')
        else:
            C.append(f'<g class="{st("done edited again")}">{outline(ctx, k, BAD, w=1.6)}</g>')
    for k in ctx.passes:
        C.append(f'<g class="{st("again")}"><g class="vc-flash">{outline(ctx, k, OK, w=2.4)}</g></g>')
    vx0, vy0, vx1, vy1 = ctx.cap["geom"]["boxes"]["verify"]
    T.append(f'<g class="{st("made")}">' + status(ctx, [("28 new", "grey")], "running", "vc-vb-made") + "</g>")
    T.append(f'<g class="{st("running")}">' + status(ctx, [(f"{RUN_DONE} / 28", "acc")]) + "</g>")
    T.append(f'<g class="{st("done")}">' + status(ctx, [(f"{len(ctx.fails)} to fix ›", "bad")]) + "</g>")
    T.append(f'<g class="{st("edited")}">' + status(ctx, [(f"{len(ctx.fails) - 1} to fix ›", "bad")], "done", "vc-vb-edited") + "</g>")
    T.append(f'<g class="{st("again")}">' + status(ctx, [(f"{len(ctx.fails_fixed)} to fix ›", "bad")]) + "</g>")
    # the walk: the canvas framed on the failure, one card, Prev / Next
    x0, y0, x1, y1 = ctx.b(DETAIL)
    walk = (f'<g class="{st("done")}"><path class="vc-veil3" fill-rule="evenodd" d="M0 0H1440V900H0Z M{x0 - 4:.1f} {y0 - 4:.1f}V{y1 + 4:.1f}H{x1 + 4:.1f}V{y0 - 4:.1f}Z"/>'
            + outline(ctx, DETAIL, BAD, w=2.4) + f'<path d="M{x1 + 10:.1f} {(y0 + y1) / 2:.1f}l12 -8v16z" fill="#fff" stroke="#dadee4"/>'
            + fo(x1 + 21, y0 - 80, 372, 440, detail_card(ctx, DETAIL, w=366, title_extra=f'<span class="vc-walkn">1 of {len(ctx.fails)}</span>',
                                                   tail='<div class="vc-walk"><span class="vc-btn">‹ Prev</span><span class="vc-btn pri">Next failure › <kbd>F8</kbd></span><span class="vc-mut">Esc ends the walk</span></div>'), "vc-pop")
            + "</g>")
    T.append(walk)
    preview = stage("".join(C), "".join(T), fix="st st-edited st-again")
    legend = state_strip(ctx, {
        "unverified": ("A1", "", "nothing; the button counts it"),
        "stale": (DETAIL, outline(ctx, DETAIL, STALE, w=1.6, dash="3 2.5"), "a dashed grey outline"),
        "computing": ("C2", g_spin(*ctx.corner("C2"), r=6, frac=0.4), "spins"),
        "passed": ("B9", f'<g class="vc-flash vc-hold">{outline(ctx, "B9", OK, w=2.4)}</g>', "green outline, fades"),
        "failed": ("D4", outline(ctx, "D4", BAD, w=1.6), "a thin red outline, kept"),
    }, fix_for="stale")
    zoom = stage(outline(ctx, DETAIL, BAD, w=2.4), f'<path d="M{x1 + 10:.1f} {(y0 + y1) / 2:.1f}l12 -8v16z" fill="#fff" stroke="#dadee4"/>'
                 + fo(x1 + 21, y0 - 80, 372, 440, detail_card(ctx, DETAIL, w=366, title_extra=f'<span class="vc-walkn">1 of {len(ctx.fails)}</span>',
                                  tail='<div class="vc-walk"><span class="vc-btn">‹ Prev</span><span class="vc-btn pri">Next failure › <kbd>F8</kbd></span></div>'), "vc-pop"),
                 view=(x0 - 50, y0 - 100, 500, 430))
    media = [
        {"label": "The five states, on real markers", "caption": "No badges: the sticker's own outline carries the state — red stays, green fades, dashed grey is stale.", "html": legend},
        {"label": "The walk, framed on one failure", "caption": "‘13 to fix ›’ walks the failures in reading order (F8 / Shift+F8, as VS Code's Go to Next Problem): the canvas frames the marker, the card says why in numbers, the fan, the measured fix.", "html": zoom},
    ]
    steps = [
        {"label": "Make", "caption": "Nothing on the canvas; the Verify button says 28 new.", "state": "made", "target": ".st-made .vc-vbtn"},
        {"label": "Press Verify", "caption": "Outlines only: a failure's sticker edge turns red and stays, a pass's flashes green and goes.", "state": "running", "target": ".st-running .vc-spin"},
        {"label": "Walk the failures", "caption": f"‘{len(ctx.fails)} to fix ›’ opens the walk on the first: the board dims, the card says why with numbers, the fix, Next (F8).", "state": "done", "target": ".vc-walk"},
        {"label": "Edit one", "caption": f"Label Auto from the card; the walk moves on. B6's outline dashes grey: ‘{len(ctx.fails) - 1} to fix’.", "state": "edited", "target": ".st-edited .vc-vbtn"},
        {"label": "Verify again", "caption": f"Cached passes flash ({ctx.flash_ms:.0f} ms); B6 runs ({ctx.b6fix_txt}) and joins them: {len(ctx.fails_fixed)} to fix.", "state": "again", "target": ".st-again .vc-vbtn"},
    ]
    return {"preview": preview, "media": media, "steps": steps}


# ================================================================== 6. the contract every variant shares (the page's "read first")

def ids_of(ctx: Ctx, keys: list) -> str:
    return " ".join(keys) if keys else "none"


def contract(ctx: Ctx) -> str:
    d, t = ctx.data, ctx.cap["timing"]
    sw = sweeps(d, ctx.guide)
    v = ctx.v
    rows = []
    v411 = judge_board(d, ctx.guide, cv="4.11.0")
    for r in THRESHOLD_ROWS:
        f5 = [k for k in ORDER if any(t_ == r["id"] for t_, _ in v[k]["why"])]
        f4 = [k for k in ORDER if any(t_ == r["id"] for t_, _ in v411[k]["why"])]
        rows.append(f'<tr><td><b>{E(r["name"])}</b></td><td>{E(r["value"])}</td><td>{E(r["fails"])}</td><td class="mut">{E(r["why"])}</td>'
                    f'<td class="n"><b>{len(f5)}</b><small>{E(ids_of(ctx, f5))}</small></td><td class="n">{len(f4)}<small>{E(ids_of(ctx, f4))}</small></td></tr>')

    def sw_table(key, head, fmt):
        trs = "".join(fmt(row) for row in sw[key])
        return f'<table class="vs-t"><tr>{"".join(f"<th>{h}</th>" for h in head)}</tr>{trs}</table>'
    lab = sw_table("label", ["Label cost X", "Fail · OpenCV 5.0", "Fail · 4.11"],
                   lambda r: f'<tr{" class=on" if r["value"] == "3 pts" else ""}><td>{r["value"]}</td><td>{len(r["5.0.0"])} <small>{" ".join(r["5.0.0"])}</small></td><td>{len(r["4.11.0"])} <small>{" ".join(r["4.11.0"])}</small></td></tr>')
    need = sw_table("need", ["Required", "Fail · 5.0", "of them borderline", "Fail · 4.11"],
                    lambda r: f'<tr{" class=on" if r["value"].endswith("500 mm") else ""}><td>{r["value"]}</td><td>{len(r["5.0.0"])}</td><td>{len(r["5.0.0_border"])} <small>{" ".join(r["5.0.0_border"][:8])}</small></td><td>{len(r["4.11.0"])}</td></tr>')
    mp = sw_table("markpose", ["Label's pose cost", "Fail · 5.0", "Fail · 4.11"],
                  lambda r: f'<tr{" class=on" if r["value"] == "+100 %" else ""}><td>{r["value"]}</td><td>{len(r["5.0.0"])} <small>{" ".join(r["5.0.0"])}</small></td><td>{len(r["4.11.0"])}</td></tr>')
    po = sw_table("pose", ["Pose p90 limit", "ChArUco failing at 0.3 m", "at 0.5 m"],
                  lambda r: f'<tr{" class=on" if r["value"] == "1 mm" else ""}><td>{r["value"]}</td><td>{len(r["300"])} of 4</td><td>{len(r["500"])} of 4 <small>{" ".join(r["500"])}</small></td></tr>')
    pose_line = " · ".join(f'{k} {d["pose"][k]["300"]["p90"]:.2f} / {d["pose"][k]["500"]["p90"]:.2f} mm' for k in ("A1", "E1", "E2", "E3", "E4", "F3"))
    # the verdict map: the default set on the real board
    vm = []
    for k in ORDER:
        if v[k]["pass"]:
            vm.append(g_ok(*ctx.corner(k), r=6))
        else:
            vm.append(outline(ctx, k, BAD, w=1.6) + g_bad(*ctx.corner(k), r=6))
    vmap = stage("".join(vm), view=(420, 66, 640, 760))
    by_reason = {}
    for k in ORDER:
        for t_, _w in v[k]["why"]:
            by_reason.setdefault(t_, []).append(k)
    tn = {r["id"]: r["name"] for r in THRESHOLD_ROWS}
    reasons = "".join(f'<li><b>{E(tn[t_])}</b> {len(ks)}: {E(" ".join(ks))}</li>' for t_, ks in by_reason.items())
    # the fans, real
    fans = []
    for k, words in (("A1", "No label · 22 mm single"), ("E2", "ChArUco 5 × 4 · 12 mm squares"), ("B6", "Letters a whole cell tall")):
        rr = ctx.fans[k]
        vv = v[k]
        fans.append(f'<figure class="vs-fan"><svg class="vs-fanimg" viewBox="-10 -150 330 300">{fan(rr, 0, 0, 280, need=DEMO_NEED, tone="ok" if vv["range"]["far_mm"] and vv["pass"] else "bad")}</svg>'
                    f'<figcaption><b>{k} · {E(words)}</b>{E(m(vv["range"]["near_mm"]))} – {E(m(vv["range"]["far_mm"]))} under the whole budget</figcaption></figure>')
    angles = [r["angle"] for r in ctx.fans["A1"]]
    ftab = ('<table class="vs-t"><tr><th>far end</th>' + "".join(f"<th>{a:+.0f}°</th>" for a in angles) + "</tr>"
            + "".join(f'<tr><td>{k}</td>' + "".join(f'<td>{m(r["far_mm"])}</td>' for r in ctx.fans[k]) + "</tr>" for k in ("A1", "E2", "B6"))
            + "</table>")
    a = {r["angle"]: r for r in ctx.fans["A1"]}
    # the edit table
    etr = "".join(f'<tr><td>{E(e["edit"])}</td><td class="{"bad" if e["request_changed"] else "ok"}">{"re-runs" if e["request_changed"] else "kept"}</td>'
                  f'<td class="{"bad" if e["verify_changed"] else "ok"}">{"stale → re-runs" if e["verify_changed"] else "kept"}</td></tr>' for e in d["edits"])
    seq = d["seq"]
    seq_s = sum(x["ms"] for x in seq["range"].values()) / 1000.0
    ratios = [h["runs"][k]["wall_ms"] / seq["range"][k]["ms"] for h in ctx.hist for k in ("A1", "E2")]
    r_lo, r_hi = min(ratios), max(ratios)
    chk = seq["check"]
    sp = ctx.span

    def secs(k):
        lo, hi = sp[k]
        return f"{lo / 1000:.1f}" if abs(hi - lo) < 50 else f"{lo / 1000:.1f}–{hi / 1000:.1f}"
    firsts = [h["first_ms"] for h in ctx.hist]
    runs_txt = " · ".join(f'{h.get("at", "")}: A1 {h["runs"]["A1"]["wall_ms"] / 1000:.1f} s, E2 {h["runs"]["E2"]["wall_ms"] / 1000:.1f} s'
                          + (f' (load {h["load"][0]})' if h.get("load") and h["load"][0] else "") for h in ctx.hist)
    timing = f'''<table class="vs-t vs-time">
      <tr><th>What</th><th>Measured</th><th>How</th></tr>
      <tr class="on"><td><b>Flash 28 cached results</b></td><td><b>{ctx.flash_ms:.0f} ms</b></td><td>28 verify keys hashed (SHA-256, {t["payload_bytes"] / 1000:.0f} KB of scenes) {t["hash_28_ms"]} ms + 28 IndexedDB reads {t["indexeddb_28_ms"]} ms + re-judge &lt; 0.1 ms + two frames {t["flash_frames_ms"]} ms</td></tr>
      <tr><td>The same 28 from today's store</td><td>{t["localstorage_28_ms"]} ms</td><td>range.ts's localStorage array ({t["store_bytes"] / 1000:.0f} KB, 240 kept) is parsed again for every lookup</td></tr>
      <tr><td>Recompute one marker</td><td>{secs("A1")} s · {secs("E2")} s · {secs("B6")} s</td><td>A1 · E2 (ChArUco) · B6 (reads nowhere, stops early): the browser's own core worker, OpenCV {t["runs"]["A1"]["opencv"]}, in 250 ms slices; {t["runs"]["A1"]["renders"]} / {t["runs"]["E2"]["renders"]} / {t["runs"]["B6"]["renders"]} renders. Runs: {E(runs_txt)}</td></tr>
      <tr><td>Recompute the whole board</td><td>≈ {seq_s * r_lo / 60:.0f}–{seq_s * r_hi / 60:.0f} min</td><td>its 28 ranges one after another in CPython 4.11: {seq_s:.0f} s (load {seq["load"]}), × {r_lo:.1f}–{r_hi:.1f}, the browser / CPython ratio of A1 and E2 over the runs</td></tr>
      <tr><td>+ the label check, per marker</td><td>{chk["A1"]["ms"] / 1000:.1f} – {chk["E2"]["ms"] / 1000:.0f} s CPython</td><td>web_marks.check (320 paired views): A1 {chk["A1"]["ms"] / 1000:.1f} s, B6 {chk["B6"]["ms"] / 1000:.1f} s, D4 {chk["D4"]["ms"] / 1000:.1f} s, E2 {chk["E2"]["ms"] / 1000:.1f} s; camera-independent, so a camera switch never re-runs it</td></tr>
      <tr><td>The first range of a visit</td><td>{min(firsts) / 1000:.1f}–{max(firsts) / 1000:.1f} s</td><td>B1, OpenCV loading into the worker included</td></tr>
    </table>'''
    ratio_flash = sp["A1"][0] / ctx.flash_ms
    stamp = {"key": d["cases"][6]["verify_key"], "camera": "d435", "opencv": "5.0.0", "engine": "reading-range/1+marks/1",
             "budget": "field", "thresholds": "v1", "verdict": "fail", "why": ["reads", "label", "rules"],
             "near_mm": None, "far_mm": None, "fan": [[-75, None, None], ["…"], [75, None, None]], "at": "2026-10-21T17:02Z", "by": "zach"}
    diagram = state_diagram()
    return f'''<section class="vs" aria-labelledby="vs-h">
  <div class="eyebrow">Read first · what every proposal shares</div>
  <h2 id="vs-h">Pass, fail, stale, cached: one contract, five ways to show it</h2>
  <p class="vs-lead"><b>A marker passes when all six thresholds pass.</b> On the 28-marker Label placement board (RealSense D435, OpenCV 5.0, the
  Field budget, a required 0.15–0.5 m): <b>{len(ctx.passes)} pass, {len(ctx.fails)} fail</b>. A cached board shows its results in
  <b>{ctx.flash_ms:.0f} ms</b>; recomputing one marker takes {sp["A1"][0] / 1000:.0f}–{sp["E2"][1] / 1000:.0f} s in the browser
  (the cheapest is ≈ {ratio_flash:,.0f}× the flash), the whole board ≈ {seq_s * r_lo / 60:.0f}–{seq_s * r_hi / 60:.0f} min. Every number here was measured on this board.</p>
  <div class="vs-grid">
   <div class="vs-card vs-wide"><h3>1 · What pass and fail mean: six named thresholds</h3>
    <div class="tw"><table class="vs-t vs-th"><tr><th>Threshold</th><th>Default</th><th>Fails when</th><th>Why this default</th><th>Fails · 5.0</th><th>· 4.11</th></tr>{"".join(rows)}</table></div>
    <div class="vs-two"><div>{vmap}</div><div><p><b>The default set on the real board</b> (the storyboard's state ‘Results in’): red = fails, by threshold:</p><ul class="vs-r">{reasons}</ul>
    <p class="mut">The OpenCV you pick moves more verdicts than any threshold value: 4.11 fails {len([k for k in ORDER if not v411[k]["pass"]])} where 5.0 fails {len(ctx.fails)} (B7, and B5 reads nowhere).
    So the OpenCV is part of the cache key and is named on every result.</p></div></div>
    <details><summary>What each value does to the 28 (the sweeps)</summary><div class="vs-sw">
      <div><h4>Label cost X</h4>{lab}<p class="mut">With the sign test the value hardly matters: under 5.0 only B6 fails anywhere from 1 to 10 pts (by its easy reads). Under 4.11, C4 (2.2 pts, p = 0.03) is the one marker between 1 and 3.</p></div>
      <div><h4>Required distance</h4>{need}<p class="mut">The lever that moves most. ‘Borderline’: the requirement sits inside the far end's 90 % interval, so 48 cases cannot call it: Verify re-runs those at 96 cases (below).</p></div>
      <div><h4>Label's pose cost</h4>{mp}</div>
      <div><h4>Pose accuracy (ChArUco)</h4>{po}<p class="mut">p90 pose error at 0.3 / 0.5 m (24 Field cameras): {E(pose_line)}.</p></div>
      <div><h4>Print rules</h4><p>{len(sw["rules"])} of 28 break one: {E(" ".join(sw["rules"]))}.</p><h4>Reads at all</h4><p>5.0: {E(" ".join(sw["reads"]["5.0.0"]))} · 4.11: {E(" ".join(sw["reads"]["4.11.0"]))}</p>
      <p class="mut">Why the label threshold is paired, not a range difference: the same 22 mm marker, bare, reads to {m(d["ranges"][NEWEST]["A1"]["bare"]["far_mm"])} as #0 and {m(d["ranges"][NEWEST]["B3"]["bare"]["far_mm"])} as #3, and D7's label, beside the marker, ‘gains’ {(d["ranges"][NEWEST]["D7"]["marked"]["far_mm"] / d["ranges"][NEWEST]["D7"]["bare"]["far_mm"] - 1) * 100:+.0f} %: two ranges differ by ±20 % from the draw alone.</p></div>
    </div></details>
   </div>
   <div class="vs-card vs-wide"><h3>2 · The reach fan, symmetric, from the engine</h3>
    <div class="vs-fans">{"".join(fans)}</div>
    <p>Each point is the live engine (reading_range, 48 Field cameras × 6+ distances) with the camera held at that yaw, left (−) or right (+) of the marker's axis;
    the radius is log distance (40 mm – 1.5 m), the pale fringe the far end's 90 % interval, the dashed blue sector the requirement over the budget's ±45°.
    Symmetric within the draw: A1 reads {m(a[-15.0]["far_mm"])} at −15° and {m(a[15.0]["far_mm"])} at +15°; at ±75° {m(a[-75.0]["far_mm"])} / {m(a[75.0]["far_mm"])}.</p>
    <details><summary>The numbers</summary><div class="tw">{ftab}</div></details>
   </div>
   <div class="vs-card"><h3>3 · States, and what makes a result stale</h3>{diagram}
    <ul class="vs-r">
     <li><b>Verify</b> = for every marker: key unchanged and passed → flash (from the cache); key unchanged and failed → stays red, <i>not</i> re-rendered (seeded: the same inputs give the same bytes); <b>borderline</b> → re-run at 96 cases (halves the ±); stale or never run → compute, selected first, then reading order.</li>
     <li><b>Streams in</b> one marker at a time from the one core worker, in 250 ms slices (planning never waits longer than a slice); each result lands as it finishes.</li>
     <li><b>Changing a threshold</b> re-judges every cached result in &lt; 0.1 ms: thresholds key the verdict, not the measurement.</li>
    </ul>
    <h4>Which edits make it stale (measured on B6's neighbour B1)</h4>
    <table class="vs-t"><tr><th>Edit</th><th>Today's key (the request)</th><th>Proposed key (the scene)</th></tr>{etr}</table>
   </div>
   <div class="vs-card"><h3>4 · The cache</h3>
    <table class="vs-t"><tr><th>Key part</th><th>Why</th></tr>
     <tr><td><b>Scene hash</b> <small>SHA-256 of the marker in its own frame: layers, ids, label as drawn</small></td><td>a move or a turn keeps the result; any printed change re-runs</td></tr>
     <tr><td><b>Camera</b> <small>library id, or W × H, HFOV, focus</small></td><td>switching back to a camera is instant</td></tr>
     <tr><td><b>OpenCV version</b> <small>one, selectable, newest by default</small></td><td>4.11 and 5.0 differ by up to 2× near the limits</td></tr>
     <tr><td><b>Engine + budget</b> <small>reading-range/1, marks/1, Field, seed</small></td><td>a method change drops old answers</td></tr>
     <tr><td class="mut"><b>Not the thresholds</b></td><td class="mut">they judge cached numbers; a change re-judges in &lt; 0.1 ms</td></tr></table>
    <p><b>Where it lives:</b> the measurements (range rows, fan, label check) in this browser's <b>IndexedDB</b>, no size limit that matters; a ~400-byte <b>stamp per feature in the file</b> (verdict, why, range ends, the fan's 11 ends, key, who, when). Autosave carries it.</p>
    <pre class="vs-code">"verified": {E(json.dumps(stamp))}</pre>
    <p><b>A teammate opening the file</b> hashes the 28 scenes ({t["hash_28_ms"]} ms) and compares: same key, OpenCV and engine → they see Zach's results (failures red, “verified by zach, 2 h ago” in the detail), no compute; anything different → stale, hollow, until they press Verify.</p>
   </div>
   <div class="vs-card vs-wide"><h3>5 · Cached flash against recompute, measured</h3>{timing}
    <p class="mut">Browser numbers: headless Chrome on the running Preview (main, {E(d["head"])}), the core's own Pyodide worker (OpenCV {t["runs"]["A1"]["opencv"]}), captured {E(d["generated"])}. Lookups are the median of 25 repeats. CPython: this repo's .venv (OpenCV 5.0) and .venv-cv411.</p>
   </div>
  </div>
</section>'''


def state_diagram() -> str:
    """The five states and what moves a marker between them (an SVG, V1's glyphs)."""
    nodes = {"unverified": (16, 90, ""), "computing": (196, 90, g_spin(0, 0, 8, 0.4)), "passed": (420, 18, g_ok(0, 0, 8)),
             "failed": (420, 160, g_bad(0, 0, 8)), "stale": (196, 196, g_stale(0, 0, 8))}
    s = ['<svg class="vs-diag" viewBox="0 0 600 244"><defs><marker id="vs-ar" viewBox="0 0 8 8" refX="7" refY="4" '
         'markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L8 4L0 8z" fill="#6b7480"/></marker></defs>']
    for name, (x, y, glyph) in nodes.items():
        s.append(f'<g transform="translate({x},{y})"><rect width="128" height="40" rx="8" fill="#fff" stroke="#c9ced6"/>'
                 + (f'<g transform="translate(20,20)">{glyph}</g><text x="36" y="25" class="vs-dn">{name}</text>' if glyph
                    else f'<text x="64" y="25" class="vs-dn" text-anchor="middle">{name}</text>') + "</g>")

    def arrow(d, label="", lx=0, ly=0, col="#6b7480", anchor="start"):
        s.append(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="1.2" marker-end="url(#vs-ar)"/>')
        if label:
            s.append(f'<text x="{lx}" y="{ly}" class="vs-dl" fill="{col}" text-anchor="{anchor}">{label}</text>')
    arrow("M144 110L194 110", "Verify", 169, 103, anchor="middle")
    arrow("M324 102L418 42", "pass", 368, 62, anchor="middle")
    arrow("M324 118L418 178", "fail", 368, 160, anchor="middle")
    arrow("M470 58Q440 150 326 206", "edit", 452, 140, anchor="middle")
    arrow("M420 190Q380 210 326 214", "edit", 360, 236, anchor="middle")
    arrow("M240 196L240 132", "Verify", 246, 168)
    arrow("M548 30q34 8 0 18", col="#18865a")
    s.append('<text x="484" y="11" class="vs-dl" fill="#18865a" text-anchor="middle">Verify: flash, from the cache</text>')
    arrow("M548 172q34 8 0 18", col="#cf3b3b")
    s.append('<text x="484" y="214" class="vs-dl" fill="#cf3b3b" text-anchor="middle">Verify: stays (borderline: 96 cases)</text>')
    s.append('<text x="16" y="150" class="vs-dl">a camera or OpenCV switch:</text><text x="16" y="164" class="vs-dl">cached for that one, else stale</text>')
    s.append("</svg>")
    return "".join(s)


# ================================================================== 7. the page

REQUIREMENTS = [
    {"id": "fr1", "name": "No association needed", "weight": 25,
     "why": "Zach: “I like showing the results on the live canvas because then I don't need to do an association between what is on the canvas and the result.”",
     "passCondition": "Each marker's verdict is drawn on or against that marker in the canvas he edits, with no list or second screen to map back.",
     "anchors": {"1": "Results in a dialog or list; he maps names to markers himself.",
                 "3": "On the canvas, but only in a separate mode or after a step that changes what he sees.",
                 "5": "On the marker itself, while editing, every time."}},
    {"id": "fr2", "name": "A quiet board", "weight": 25,
     "why": "“So it doesn't clutter the screen … just the ones with an error show”; “temporarily show success then it can fade away; it's the errors that should remain persistent”; V1 ‘Turn it down’.",
     "passCondition": "At rest after Verify, passes leave nothing (or thin grey) and failures stay, small; on this board, where 13 of 28 fail.",
     "anchors": {"1": "Every marker carries a result glyph or number at rest.",
                 "3": "Passes vanish, but failures (or the whole layer) are loud.",
                 "5": "Passes vanish, failures stay as a small persistent mark, nothing else."}},
    {"id": "fr3", "name": "Angle and length at a glance", "weight": 20,
     "why": "“I really like the reach fan … symmetric around the axis … a very nice way to show angle and length.”",
     "passCondition": "The symmetric fan (real per-angle ranges) is one gesture away for any marker, readable at its size, with the requirement on it.",
     "anchors": {"1": "Distance only, or the fan buried in a dialog.",
                 "3": "The fan one click away but small, or distance-only on the canvas.",
                 "5": "A readable fan, with the requirement, one hover or click away for any marker."}},
    {"id": "fr4", "name": "Lazy and cached", "weight": 15,
     "why": "“If I click the Verify button it will flash all the passing ones already (using the cached result), and will recompute … the ones that need to be recomputed”; “Caching … essential”.",
     "passCondition": "Verify shows cached results at once and computes only stale or unrun markers, with spinners and results streaming in; edits mark stale, not re-run.",
     "anchors": {"1": "Runs everything on every Verify.", "3": "Cached, but the cached results do not appear until the run ends, or a mode switch is needed.",
                 "5": "Cached results flash in tens of ms; only stale ones spin; each lands as it finishes."}},
    {"id": "fr5", "name": "Concrete pass / fail", "weight": 15,
     "why": "“What does it mean to pass or fail? That is what I need to get very concrete … We likely need thresholds.”",
     "passCondition": "From the canvas, a failure names the thresholds it broke with the measured numbers, and the thresholds themselves are one step away to read and change.",
     "anchors": {"1": "Just red.", "3": "The reason in words, without the numbers or the thresholds.",
                 "5": "Every broken threshold with its number, the fix measured, the threshold set one step away."}},
]

GATES = [
    {"id": "g1", "name": "Real detector numbers", "why": "Every badge, band and fan comes from web_verify renders read by OpenCV's detector (the live engine), never a px-per-cell rule."},
    {"id": "g2", "name": "Strip and bench stay", "why": "The range strip (V4, live) and the manual bench stay reachable in two clicks: Zach likes sweeping the marker himself."},
    {"id": "g3", "name": "Prints what it shows", "why": "No overlay covers or recolours the printed black: glyphs sit on the sticker's corner or outside it."},
    {"id": "g4", "name": "One OpenCV, named", "why": "Zach's pick (2026-10-21): one OpenCV, selectable, newest by default; every result names it and the cache never mixes two."},
]


def variants(ctx: Ctx) -> list:
    built = {"v1": v1(ctx), "v2": v2(ctx), "v3": v3(ctx), "v4": v4(ctx), "v5": v5(ctx)}
    fl = f"{ctx.flash_ms:.0f} ms"
    shared_pf = "The shared six thresholds (v1); a failure lists each broken one with its number."
    shared_cache = "Scene-hash key + camera + OpenCV + engine; IndexedDB + a stamp in the file."
    out = [
        {"id": "v1", "name": "Marimo badges", "accent": "#2f7f74",
         "thesis": "Always on and lazy, like marimo's cells: a failing marker wears a red badge until it passes, a pass flashes green and fades, an edit greys its badge, and the Verify button is the run button that says what is stale.",
         "bestWhen": "Zach edits and checks in one place, and the failures are a handful.",
         "losesWhen": f"Many fail at once: on this test board {len(ctx.fails)} red badges stay up; and comparing reach across markers means opening popovers one by one.",
         "decisions": [{"label": "Edit vs Verify", "value": "No mode, no layer: results are always on the canvas; Layers › Verify results hides the badges."},
                       {"label": "States", "value": "unverified: nothing (the button counts) · stale: hollow grey · computing: progress ring · passed: green flash, 2.4 s · failed: red badge, kept."},
                       {"label": "Detail", "value": "Click a badge: a popover with the broken thresholds, the fan, the measured fix, Range strip ▸ and Bench ▸."},
                       {"label": "Pass / fail · cache", "value": f"{shared_pf} {shared_cache}"}],
         "keepParts": ["Verify button as marimo's run button (28 new / 1 stale / 13)", "red badge stays, green flashes", "popover: thresholds with numbers + fan + measured fix"],
         "proof": [f"The badges are the default thresholds' verdicts on the real board: {len(ctx.fails)} fail, {len(ctx.passes)} pass.", f"The flash is the measured cached path ({fl}); B6's fix is measured (passes under both OpenCVs)."],
         "previewLabel": "canvas · badges"},
        {"id": "v2", "name": "Verify layer", "accent": "#7667c6",
         "thesis": "Verify results is a layer in the Layers menu, beside Sketch dimensions and Joint Origins: on, each marker carries its range strip band right under it, turned down to thin grey when it passes and red when it fails; hover a band for the fan.",
         "bestWhen": "Zach wants to compare reach across many markers at a glance while he edits, the way the strip does, without the strip.",
         "losesWhen": "The board must be quiet: with the layer on every marker carries a band; with it off, nothing shows, failures included.",
         "decisions": [{"label": "Edit vs Verify", "value": "A layer: one switch in the calm-canvas lane's Layers menu; Verify turns it on."},
                       {"label": "States", "value": "unverified: dotted axis · stale: dashed grey band · computing: the axis fills · passed: green, then thin grey · failed: red band + ✕."},
                       {"label": "Detail", "value": "Hover a band: the marker's fan in a card. The strip itself becomes these bands; the bench from the card."},
                       {"label": "Pass / fail · cache", "value": f"{shared_pf} {shared_cache}"}],
         "keepParts": ["‘Verify results’ row in the Layers menu", "the strip's band under its own marker", "requirement ticks on every band"],
         "proof": ["Bands are the real reading ranges (5.0, D435, Field) on the shared 0.04–1.5 m log axis.", "The menu's other rows are the calm-canvas lane's (web/src/overlays/LayersMenu.tsx, in flight)."],
         "previewLabel": "canvas · layer"},
        {"id": "v3", "name": "Verify mode", "accent": "#3f6fa8",
         "thesis": "Edit | Verify, like Figma's Design | Prototype or Fusion's workspaces, but the canvas never leaves: Verify mode grows a fan on every marker and swaps the Extrude panel for a Verify panel with the thresholds; Edit mode keeps only red dots.",
         "bestWhen": "Zach does verification as a pass of its own (before Print) and wants every fan and the thresholds in view at once.",
         "losesWhen": "He edits and checks in the same breath: every look is a mode switch, and in Edit the fans are gone.",
         "decisions": [{"label": "Edit vs Verify", "value": "A mode switch in the top bar; Verify enters it. The canvas stays; the panel swaps."},
                       {"label": "States", "value": "unverified: nothing (Edit) · stale: grey ring in Edit · computing: spinner while its fan grows · passed: green fan then grey · failed: red fan + ✕."},
                       {"label": "Detail", "value": "A fan on every marker (mini, ±75°) and the panel: camera, OpenCV, budget, the six thresholds with fail counts, the failing list."},
                       {"label": "Pass / fail · cache", "value": f"{shared_pf} The thresholds live in the panel, editable. {shared_cache}"}],
         "keepParts": ["Verify panel: thresholds with fail counts", "a fan on every marker", "Edit mode's red dots"],
         "proof": ["Every mini fan is that marker's own per-angle ranges (11 angles × 28 markers, the live engine).", "The panel's counts are the default set on the board."],
         "previewLabel": "canvas · mode"},
        {"id": "v4", "name": "Hover fan", "accent": "#a94f78",
         "thesis": "The quietest board: a failure is a 4 px red dot, a pass flashes and leaves nothing; point at any marker and the board dims while its symmetric fan opens on the canvas from that marker, with the requirement drawn as a sector.",
         "bestWhen": "Zach wants a near-empty board and the fan, big and readable, for whichever marker he is looking at.",
         "losesWhen": "He wants to compare fans side by side, or to see why without pointing (a dot alone says nothing).",
         "decisions": [{"label": "Edit vs Verify", "value": "Always on, lazy; the detail is a hover (one at a time), a click pins it. Layers › Verify results hides the dots."},
                       {"label": "States", "value": "unverified: nothing · stale: small grey ring · computing: spinner · passed: green flash · failed: 4 px red dot, kept."},
                       {"label": "Detail", "value": "The fan on the canvas from the marker's edge (210 px, log distance), PASS / FAIL and the range in a tag; Range strip and Bench in the pinned card."},
                       {"label": "Pass / fail · cache", "value": f"{shared_pf} {shared_cache}"}],
         "keepParts": ["fan on the canvas from the hovered marker", "4 px red dot as the only rest mark", "requirement as a sector on the fan"],
         "proof": ["E2's fan is its own per-angle ranges: 0.38 m head on, short of 0.5 m at every angle.", "A1's exhibit fan: 42 mm to ≈ 0.6 m head on, ≈ 0.22 m at ±75°."],
         "previewLabel": "canvas · hover"},
        {"id": "v5", "name": "Fix-it walk", "accent": "#b7791f",
         "thesis": "Steelman of what he did not ask for: no badges at all — a failing sticker's own outline turns red and stays — and Verify ends in ‘13 to fix ›’, a walk that frames each failure in turn with why, the fan and the measured fix (F8, as VS Code's next problem).",
         "bestWhen": f"Many fail at once (this board: {len(ctx.fails)} of 28) and the job is fixing them, not looking at them.",
         "losesWhen": "He wants to glance at the canvas and know: a red outline says ‘fails’ but not why, until he walks.",
         "decisions": [{"label": "Edit vs Verify", "value": "Always on (outlines); the walk is a short review pass Verify offers when anything fails."},
                       {"label": "States", "value": "unverified: nothing · stale: dashed grey outline · computing: spinner · passed: green outline flash · failed: thin red outline, kept."},
                       {"label": "Detail", "value": "The walk card, one failure at a time, the canvas framed on it: thresholds with numbers, fan, fix, Prev / Next."},
                       {"label": "Pass / fail · cache", "value": f"{shared_pf} {shared_cache}"}],
         "keepParts": ["‘13 to fix ›’ on the Verify button", "red sticker outline as the failure mark", "F8 walk with the fix in the card"],
         "proof": ["The walk card is the same measured detail as V1's popover.", "Outlines are the captured stickers' own boxes."],
         "previewLabel": "canvas · walk"},
    ]
    for v in out:
        b = built[v["id"]]
        v["preview"], v["media"] = b["preview"], b["media"]
        v["story"] = {"title": "Make → Verify → edit → Verify", "steps": b["steps"]}
    return out


SCORES = {
    # fr1 association, fr2 quiet, fr3 fan, fr4 lazy+cached, fr5 concrete
    "v1": {"fr1": (5, "The badge sits on the marker's corner in the editing canvas.", "high"),
           "fr2": (4, "Passes vanish; but the 13 failures here keep 9 px badges: quiet for a handful, busy on this board.", "high"),
           "fr3": (3, "The fan is in the popover: one click, 118 px wide, readable but small.", "medium"),
           "fr4": (5, "Cached passes flash in the measured 34 ms; only stale ones spin; the button says what is stale.", "high"),
           "fr5": (5, "The popover lists every broken threshold with its number and the measured fix; the set is one click from it.", "medium")},
    "v2": {"fr1": (5, "Each band sits under its own marker.", "high"),
           "fr2": (3, "Layer on: 28 bands (passes thin grey); layer off: failures vanish too.", "high"),
           "fr3": (3, "Length for every marker at once; the angle only on hover, in a card.", "medium"),
           "fr4": (4, "Cached bands flash; but the layer must be on to see anything.", "medium"),
           "fr5": (3, "A red band says short or nowhere; why in numbers is a hover away, the thresholds a menu away.", "medium")},
    "v3": {"fr1": (4, "On the canvas, but only in Verify mode; in Edit only dots.", "high"),
           "fr2": (3, "Edit is quiet; Verify mode carries 28 fans plus a panel.", "high"),
           "fr3": (4, "Every marker's fan at once, but mini (25 px); the requirement is in the panel, not on the fans.", "medium"),
           "fr4": (4, "Cached fans appear at once, but each look is a mode switch.", "medium"),
           "fr5": (5, "The panel shows the six thresholds, editable, with how many each fails.", "high")},
    "v4": {"fr1": (5, "The dot and the fan both come out of the marker itself.", "high"),
           "fr2": (5, "At rest only 4 px dots on failures; passes leave nothing.", "high"),
           "fr3": (5, "A 210 px fan with rings, the ±45° spokes and the requirement sector, for any marker on hover.", "high"),
           "fr4": (5, "Same lazy run as V1, the same measured flash.", "high"),
           "fr5": (3, "The fan tag says PASS / FAIL and the range; the other broken thresholds need the pinned card.", "medium")},
    "v5": {"fr1": (4, "The outline is on the marker; the why is in the walk, which frames the marker.", "medium"),
           "fr2": (5, "No badges: a thin red sticker outline is the only rest mark.", "high"),
           "fr3": (3, "The fan is in the walk card, one failure at a time; a pass's fan needs another way in.", "medium"),
           "fr4": (4, "Lazy and cached as V1; the walk is extra steps after.", "medium"),
           "fr5": (5, "Each step of the walk: every broken threshold, its number, the measured fix.", "high")},
}


def spec(ctx: Ctx) -> dict:
    vs = variants(ctx)
    for v in vs:
        v["scores"] = {k: {"score": s, "evidence": e, "confidence": c} for k, (s, e, c) in SCORES[v["id"]].items()}
        v["gateResults"] = {"g1": {"pass": True, "evidence": "Ranges, fans and label costs are web_verify / web_marks runs on OpenCV's detector."},
                            "g2": {"pass": True, "evidence": "Range strip ▸ and Bench ▸ sit in the detail (" + {"v1": "popover", "v2": "hover card", "v3": "panel → marker", "v4": "pinned card", "v5": "walk card"}[v["id"]] + ")."},
                            "g3": {"pass": True, "evidence": "Glyphs sit on the sticker's corner, under it, or as its outline; none on the black."},
                            "g4": {"pass": True, "evidence": "OpenCV 5.0 named in the detail and the key."}}
    w = {r["id"]: r["weight"] for r in REQUIREMENTS}

    def totals(wt):
        return {v["id"]: sum(wt[k] * SCORES[v["id"]][k][0] / 5.0 for k in wt) for v in vs}
    tot = totals(w)
    rank = sorted(tot, key=tot.get, reverse=True)
    top, second = rank[0], rank[1]
    names = {v["id"]: v["name"] for v in vs}
    # the hinge: the smallest move of weight (5-point steps) between two criteria that changes the winner
    hinge = None
    for step in range(5, 30, 5):
        for a in w:
            for b_ in w:
                if a == b_ or w[a] - step < 5:
                    continue
                wt = dict(w)
                wt[a] -= step
                wt[b_] += step
                tt = totals(wt)
                win = max(tt, key=tt.get)
                if win != top:
                    hinge = (step, a, b_, win, tt)
                    break
            if hinge:
                break
        if hinge:
            break
    rn = {r["id"]: r["name"] for r in REQUIREMENTS}
    hinge_text = (f"‘{rn[hinge[1]]}’ against ‘{rn[hinge[2]]}’: move {hinge[0]} points from the first to the second and {names[hinge[3]]} "
                  f"takes the lead ({hinge[4][hinge[3]]:.0f} vs {hinge[4][top]:.0f}). " if hinge else "")
    hinge_text += (f"The evidence that would move it most: how many markers fail on a real document. On this test board {len(ctx.fails)} of 28 fail and "
                   f"a 4 px dot per failure is still quiet; if a real board fails one or two, V1's badge carries more (the why) for the same quiet.")
    return {
        "schemaVersion": 3,
        "title": "Verify on the canvas — five takes",
        "kicker": "ArUco Studio · /babble 5 · 2026-10-21",
        "brief": ("Verify's results ON the canvas, marimo-style: a pass flashes green and fades, an error stays, an edit marks it stale, and Verify "
                  "flashes the cached passes and recomputes only what changed, with spinners and results streaming in. The symmetric reach fan for "
                  "angle and length, and pass / fail as named numbers. Shared scenario: the 28-marker Label placement board on a RealSense D435, "
                  "OpenCV 5.0, the Field budget, a required 0.15–0.5 m; the storyboard makes it, verifies it, fixes B6 and verifies again."),
        "count": 5,
        "defaultId": top,
        "defaultWhy": (f"{names[top]} scores {tot[top]:.0f} / 100: the quietest board that still answers on the marker (a 4 px dot), and the fan Zach liked, "
                       f"big and symmetric, wherever he points. {names[second]} is next at {tot[second]:.0f}. Splice to consider: {names[top]}'s dot and "
                       f"hover fan, V1's Verify button as marimo's run button and its popover reasons in the pinned card, V3's threshold panel "
                       f"behind the button's menu."),
        "decisionHinge": hinge_text,
        "invariants": [
            "One board: web/public/examples/label-placement.arucostudio-web.json (28 markers), as the live Preview draws it at 1440 × 900.",
            "One camera (RealSense D435 colour, 1920 × 1080, 69°), one OpenCV (5.0, the newest), one budget (Field), one requirement (0.15–0.5 m, batch-set).",
            "One threshold set (the six above) and one cache (scene-hash key + camera + OpenCV + engine).",
            "One storyboard: make → Verify (spinners, streaming) → results → edit B6's label to Auto → Verify again.",
            "Canvas at rest in V1 ‘Turn it down’: the live edges, guides and Joint Origins, thin and grey.",
        ],
        "boundary": (f"Static mocks over the live canvas: the grid, the printed markers and the app's chrome are the running Preview's pixels "
                     f"(main {ctx.data['head']}); the edges, guides and axes are its SVG, turned down. Every badge, band, fan, verdict and timing is "
                     f"measured. Not built: the glyphs, menus, panels and cards are this page's."),
        "axes": [
            {"name": "Edit vs Verify", "values": ["always on, lazy badges", "a layer in the Layers menu", "a mode", "always on + hover", "always on + a walk"]},
            {"name": "A failure at rest", "values": ["red badge", "red band under it", "red fan (Verify) / dot (Edit)", "4 px red dot", "red sticker outline"]},
            {"name": "Where the fan lives", "values": ["popover on click", "card on hover of the band", "on every marker, mini", "on the canvas, one at a time", "the walk card"]},
            {"name": "A pass at rest", "values": ["nothing", "thin grey band", "grey fan (Verify)", "nothing", "nothing"]},
        ],
        "requirements": REQUIREMENTS,
        "hardGates": GATES,
        "variants": vs,
    }


def images_css() -> str:
    return (f'.vc-bg{{background-image:url({webp(SHOTS / "bg.png", 72)})}}'
            f'.vc-print{{background-image:url({webp(SHOTS / "print.png", 86)})}}'
            f'.vc-chrome{{background-image:url({webp(SHOTS / "chrome.png", 86)})}}')


CSS = r"""
.prototype .st{display:none}
.vc-stage{position:relative;width:100%;overflow:hidden;border-radius:6px;background:#e9ecf0;font-family:Inter,"Segoe UI",system-ui,sans-serif;text-align:left}
.vc-l{position:absolute;inset:0;width:100%;height:100%}
.vc-bg,.vc-print,.vc-chrome{background-repeat:no-repeat;pointer-events:none}
.vc-svg{pointer-events:none;overflow:hidden}
.vc-svg [data-story-to],.vc-svg [data-story-to] *,.vc-fo,.vc-fo *{pointer-events:auto}
.vc-hit{fill:transparent;stroke:none;cursor:pointer;pointer-events:all}
.vc-hit.vc-sel{stroke:#2f6fed;stroke-width:1.6;fill:none}
.vc-defs{position:absolute;width:0;height:0;overflow:hidden}
.vc-edges path{fill:none;stroke:#9aa3ad;stroke-width:.75;opacity:.8}
.vc-outl path{fill:none;stroke:#b6bdc6;stroke-width:.6;stroke-dasharray:2.5 3}
.vc-tri line{stroke-width:.9;opacity:.55} .vc-tri .ax-x{stroke:#c96d6d} .vc-tri .ax-y{stroke:#5fa57f}
.vc-tri circle{fill:none;stroke:#9aa3ad;stroke-width:.8;opacity:.7}
.vc-svg text{font-family:Inter,"Segoe UI",system-ui,sans-serif}
.vc-ring{fill:none;stroke:#c5ccd5;stroke-width:.8} .vc-spoke{stroke:#c5ccd5;stroke-width:.8;stroke-dasharray:3 3}
.vc-rl{font-size:9.5px;fill:#6b7480} .vc-none{font-size:12px;fill:#cf3b3b;font-weight:600}
.vc-zone{fill-opacity:.2;stroke-width:1.4;stroke-linejoin:round} .vc-band{fill-opacity:.13;stroke:none}
.vc-need{fill:rgba(47,111,237,.06);stroke:#2f6fed;stroke-width:1;stroke-dasharray:4 3}
.vc-bigfan .vc-zone{fill-opacity:.24}
.vc-veil{fill:rgba(236,242,255,.32)} .vc-veil2{fill:rgba(233,236,240,.74)} .vc-veil3{fill:rgba(233,236,240,.62)}
.vc-chipt{font-size:10.5px;font-weight:600} .vc-bart{font-size:7.5px;font-weight:600}
.vc-modet{font-size:13px;fill:#6b7480;font-weight:500} .vc-modet.on{fill:#1d4fb8;font-weight:650}
.vc-tagt{font-size:12px;font-weight:650;fill:#1c222b} .vc-tagt .ok{fill:#18865a} .vc-tagt .bad{fill:#cf3b3b} .vc-tags{font-size:11px;fill:#6b7480}
@keyframes vcflash{0%{opacity:0}8%{opacity:1}55%{opacity:1}100%{opacity:0}}
.vc-hold,.vc-hold .vc-flash,.vc-hold .vc-zone{animation:none!important;opacity:1}
.vc-stage .vc-l{width:100%!important;height:100%!important;max-width:none!important}
.vc-fo svg.vc-cardfan{width:118px!important;height:auto!important;flex:none}
.vc-fo svg.vc-cardfan2{width:240px!important;height:auto!important;margin:0 auto}
.vs svg.vs-fanimg,.vs svg.vs-diag{width:100%!important;height:auto!important;display:block}
@keyframes vcspin{to{transform:rotate(360deg)}}
.vc-spin{transform-box:fill-box;transform-origin:center;animation:vcspin 1s linear infinite}
@media (prefers-reduced-motion:reduce){.vc-spin{animation:none}}
.vc-fo{font:12px/1.4 Inter,"Segoe UI",system-ui,sans-serif;color:#1c222b}
.vc-card{background:#fff;border:1px solid #dadee4;border-radius:9px;box-shadow:0 8px 24px rgba(17,24,39,.14);overflow:hidden}
.vc-card-h{display:flex;gap:7px;align-items:baseline;padding:8px 12px;border-bottom:1px solid #eceef2}
.vc-card-h b{font-size:13px} .vc-card-h span{color:#6b7480;flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.vc-card-h i{font-style:normal;font-weight:700;font-size:11px} .vc-card-h i.ok{color:#18865a} .vc-card-h i.bad{color:#cf3b3b}
.vc-card-h .vc-walkn{flex:none;color:#6b7480;font-size:11px}
.vc-card-b{display:flex;gap:4px;padding:8px 10px 8px 12px;align-items:flex-start} .vc-card-w{flex:1;min-width:0}
.vc-why{font-size:11px;line-height:1.32;margin:0 0 5px} .vc-why b{display:block;font-size:9.5px;text-transform:uppercase;letter-spacing:.05em;color:#cf3b3b}
.vc-why.ok{color:#18865a}
.vc-cardfan{width:118px;height:auto;flex:none} .vc-cardfan2{width:100%;height:auto;display:block}
.vc-fix{display:flex;flex-direction:column;gap:3px;margin:6px 0 4px}
.vc-btn{display:inline-flex;align-items:center;gap:6px;height:24px;padding:0 10px;border:1px solid #dadee4;border-radius:6px;background:#fff;font:inherit;font-size:11.5px;font-weight:500;color:#1c222b;cursor:pointer;white-space:nowrap;width:max-content}
.vc-btn.pri{background:#2f6fed;border-color:#2f6fed;color:#fff}
.vc-btn kbd{font:10px ui-monospace,monospace;border:1px solid rgba(255,255,255,.5);border-radius:3px;padding:0 3px}
.vc-mut{color:#6b7480;font-size:10.5px}
.vc-links{display:flex;gap:12px;font-size:11px;color:#2f6fed;margin-top:4px}
.vc-meta{padding:5px 12px;border-top:1px solid #eceef2;background:#f7f8fa;color:#6b7480;font-size:10.5px}
.vc-walk{display:flex;gap:8px;align-items:center;padding:6px 12px 8px;border-top:1px solid #eceef2}
.vc-menu{background:#fff;border:1px solid #dadee4;border-radius:10px;box-shadow:0 8px 24px rgba(17,24,39,.14);padding:5px;font-size:12.5px}
.vc-menu hr{border:0;border-top:1px solid #eceef2;margin:3px 0}
.vc-mrow{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:5px 8px;border-radius:6px}
.vc-mrow small{color:#6b7480;font-size:10.5px}
.vc-new{background:#e9f0fe;cursor:pointer;font-weight:600} .vc-new small{font-weight:400;display:block}
.vc-sw{width:28px;height:16px;border-radius:8px;background:#d1d5db;position:relative;flex:none}
.vc-sw i{position:absolute;left:2px;top:2px;width:12px;height:12px;border-radius:6px;background:#fff}
.vc-sw.on{background:#2f6fed} .vc-sw.on i{left:14px}
.vc-panel{background:#fff;border:1px solid #dadee4;border-radius:10px;box-shadow:0 8px 24px rgba(17,24,39,.12);font-size:12px;overflow:hidden}
.vc-ph{display:flex;justify-content:space-between;align-items:baseline;padding:10px 14px;font-weight:650;font-size:13px;border-bottom:1px solid #eceef2}
.vc-ph span{font-weight:400;color:#6b7480;font-size:11.5px} .vc-ph b{color:#cf3b3b}
.vc-prow{display:flex;justify-content:space-between;padding:5px 14px;gap:10px} .vc-prow span{color:#6b7480}
.vc-psec{padding:9px 14px 3px;font-size:10px;font-weight:700;color:#6b7480;text-transform:uppercase;letter-spacing:.06em;display:flex;justify-content:space-between}
.vc-pt{width:100%;border-collapse:collapse;font-size:11.5px} .vc-pt td{padding:4px 14px;border-top:1px solid #f0f1f4}
.vc-pt td.val{color:#6b7480;font-size:10.5px;padding:4px 4px} .vc-pt td.n{text-align:right;font-weight:650} .vc-pt td.n.bad{color:#cf3b3b}
.vc-li{display:grid;grid-template-columns:8px 1fr;column-gap:8px;padding:3px 14px;font-size:11px}
.vc-li i{grid-row:span 2;width:7px;height:7px;border-radius:4px;background:#cf3b3b;margin-top:5px} .vc-li span{color:#6b7480;font-size:10.5px}
.vc-more{padding:3px 14px 10px;color:#6b7480;font-size:11px}
.vc-strip{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;padding:10px;background:#fff}
.vc-cell{margin:0} .vc-cell figcaption{font:11px/1.3 Inter,system-ui,sans-serif;color:#6b7480;margin-top:5px}
.vc-cell figcaption b{display:block;color:#1c222b;text-transform:capitalize;font-size:12px}
.media-exhibit:has(.vc-strip){grid-column:1/-1}
@media (max-width:700px){.vc-strip{grid-template-columns:repeat(2,minmax(0,1fr))}}
/* the shared contract */
.vs{margin:22px 0 10px;padding:20px 22px;background:var(--panel,#fff);border:1px solid var(--line,#dadee4);border-radius:6px}
.vs h2{margin:2px 0 8px;font-size:22px} .vs h3{margin:0 0 8px;font-size:15px} .vs h4{margin:10px 0 4px;font-size:12.5px}
.vs-lead{font-size:14px;max-width:980px}
.vs-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-top:12px}
.vs-card{border:1px solid var(--line,#dadee4);border-radius:6px;padding:14px 16px;min-width:0;background:var(--soft,#fafbfc)}
.vs-wide{grid-column:1/-1}
.vs .tw{overflow-x:auto}
.vs-t{border-collapse:collapse;width:100%;font-size:12.5px;margin:6px 0}
.vs-t th,.vs-t td{border-bottom:1px solid var(--line,#e3e6ea);padding:5px 7px;text-align:left;vertical-align:top}
.vs-t th{font:700 10px/1.2 var(--mono,ui-monospace,monospace);letter-spacing:.06em;text-transform:uppercase;color:var(--muted,#6b7480)}
.vs-t td small{display:block;color:var(--muted,#6b7480);font-size:11px}
.vs-t tr.on td{background:rgba(47,111,237,.07)}
.vs-t td.ok{color:#18865a;font-weight:600} .vs-t td.bad{color:#cf3b3b;font-weight:600} .vs-t td.n{white-space:nowrap}
.vs-th td:nth-child(3),.vs-th td:nth-child(4){min-width:220px}
.vs .mut{color:var(--muted,#6b7480)}
.vs-two{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.1fr);gap:16px;align-items:start;margin:10px 0}
.vs-r{margin:6px 0;padding-left:18px;font-size:13px} .vs-r li{margin:3px 0}
.vs-sw{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}
.vs-fans{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.vs-fan{margin:0;background:#fff;border:1px solid var(--line,#e3e6ea);border-radius:6px;padding:6px}
.vs-fan svg{width:100%;height:auto;display:block}
.vs-fan figcaption{font-size:12px;color:var(--muted,#6b7480)} .vs-fan figcaption b{display:block;color:var(--text,#1c222b)}
.vs-diag{width:100%;height:auto;display:block;background:#fff;border:1px solid var(--line,#e3e6ea);border-radius:6px}
.vs-dn{font:600 12px Inter,system-ui,sans-serif;fill:#1c222b} .vs-dl{font:11px Inter,system-ui,sans-serif;fill:#6b7480}
.vs-code{font:11px/1.45 var(--mono,ui-monospace,monospace);background:#14181e;color:#d6dde6;padding:10px 12px;border-radius:5px;white-space:pre-wrap;word-break:break-all}
.vs details{margin-top:8px} .vs summary{cursor:pointer;font-weight:600;font-size:13px}
@media (max-width:820px){.vs{padding:14px}.vs-grid,.vs-two{grid-template-columns:1fr}.vs-fans{grid-template-columns:1fr}.vs-wide{grid-column:auto}}
"""


def state_css() -> str:
    rules = []
    for vid in ("v1", "v2", "v3", "v4", "v5"):
        for s in STATES:
            rules.append(f'.variant-card[data-variant="{vid}"] .prototype[data-story-state="{s}"] .st-{s}{{display:inline}}')
            # WHY here and not on .vc-flash itself (measured 2026-10-21): Chrome runs the animations of
            # SVG inside a display:none group from page load, so by the step they were spent; an
            # animation that only exists in the state's selector starts when the state does
            rules.append(f'.variant-card[data-variant="{vid}"] .prototype[data-story-state="{s}"] .st-{s} .vc-flash'
                         f'{{animation:vcflash 3.4s ease-out both}}')
    return "\n".join(rules)


def build(data: dict, cap: dict) -> int:
    guide = json.loads(GUIDE.read_text())
    ctx = Ctx(data, cap, guide)
    sp = spec(ctx)
    with tempfile.TemporaryDirectory() as tmp:
        spath = Path(tmp) / "spec.json"
        spath.write_text(json.dumps(sp, ensure_ascii=False))
        out = Path(tmp) / "g.html"
        r = subprocess.run([sys.executable, str(GALLERY), "build", "--spec", str(spath), "--output", str(out), "--strict"],
                           capture_output=True, text=True)
        print(r.stdout[-2000:], r.stderr[-2000:])
        if r.returncode:
            return r.returncode
        page = out.read_text()
    page = page.replace("<title>Babble &amp; Prune</title>", "<title>Verify on the canvas</title>", 1)
    page = page.replace("</style>", CSS + images_css() + "\n" + state_css() + "\n</style>", 1)
    page = page.replace('<main class="page">', '<main class="page">' + defs_svg(ctx) + contract(ctx), 1)
    OUT.write_text(page)
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.2f} MB)")
    r = subprocess.run([sys.executable, str(GALLERY), "check", "--input", str(OUT), "--strict"], capture_output=True, text=True)
    print(r.stdout[-2000:], r.stderr[-2000:])
    return r.returncode


# ================================================================== 8. review: the built page, headless

REVIEW_JS = r"""
// Generated by docs/build_verify_canvas_proposals.py: the built gallery, headless. Deleted after the run.
const { chromium } = require("@playwright/test");
const CFG = __CFG__;
(async () => {
  const b = await chromium.launch({ channel: "chrome" });
  const errors = [], log = { cards: {} };
  const open = async (w, h) => {
    const p = await b.newPage({ viewport: { width: w, height: h } });
    p.on("pageerror", (e) => errors.push(e.message));
    p.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
    await p.goto("file://" + CFG.out);
    await p.waitForTimeout(800);
    await p.addStyleTag({ content: "#decision-dock{visibility:hidden!important}" });
    return p;
  };
  const p = await open(1280, 860);
  await p.screenshot({ path: `${CFG.dir}/top-1280.png` });
  await p.locator(".vs").screenshot({ path: `${CFG.dir}/contract-1280.png` });
  await p.locator("#variant-grid").scrollIntoViewIfNeeded(); await p.waitForTimeout(250);
  await p.screenshot({ path: `${CFG.dir}/grid-1280.png` });
  for (const id of CFG.ids) {
    const card = p.locator(`#card-${id}`);
    await p.locator('[data-layout="grid"]').click(); await p.waitForTimeout(120);
    await card.locator("[data-grid-focus-target]").click(); await p.waitForTimeout(300);
    const frame = card.locator(".prototype-frame");
    await frame.scrollIntoViewIfNeeded();
    const proto = card.locator(".prototype");
    const n = await card.locator('[data-story-action="jump"]').count();
    const rec = { steps: [], shown: {} };
    for (let i = 0; i < n; i++) {
      await card.locator(`[data-story-action="jump"][data-story-index="${i}"]`).click(); await p.waitForTimeout(450);
      const state = await proto.getAttribute("data-story-state");
      rec.steps.push(state);
      rec.shown[state] = await card.evaluate((c, s) => [...c.querySelectorAll(`.prototype .st-${s}`)].filter((e) => getComputedStyle(e).display !== "none").length, state);
      await frame.screenshot({ path: `${CFG.dir}/${id}-${i + 1}-${state}.png` });
    }
    // direct manipulation: the first step's own control moves the story on
    await card.locator(`[data-story-action="jump"][data-story-index="0"]`).click(); await p.waitForTimeout(200);
    const ctl = card.locator(".prototype .st-made [data-story-to]").first();
    if (await ctl.count()) { await ctl.click({ force: true }); await p.waitForTimeout(200); rec.direct = await proto.getAttribute("data-story-state"); }
    const ex = card.locator(".media-exhibit");
    const ne = await ex.count();
    for (let i = 0; i < ne; i++) { await ex.nth(i).scrollIntoViewIfNeeded(); await ex.nth(i).screenshot({ path: `${CFG.dir}/${id}-media${i + 1}.png` }); }
    log.cards[id] = rec;
  }
  await p.locator("#ai-prune").scrollIntoViewIfNeeded(); await p.waitForTimeout(200);
  await p.screenshot({ path: `${CFG.dir}/prune-1280.png` });
  log.hscroll1280 = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  await p.close();
  const m = await open(390, 844);
  await m.screenshot({ path: `${CFG.dir}/top-390.png` });
  await m.locator(".vs").screenshot({ path: `${CFG.dir}/contract-390.png` });
  await m.locator("#variant-grid").scrollIntoViewIfNeeded(); await m.waitForTimeout(250);
  await m.screenshot({ path: `${CFG.dir}/grid-390.png` });
  await m.locator("#card-v4 .prototype-frame").scrollIntoViewIfNeeded();
  await m.locator("#card-v4 .prototype-frame").screenshot({ path: `${CFG.dir}/card-v4-390.png` });
  log.hscroll390 = await m.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  await m.close();
  await b.close();
  console.log(JSON.stringify({ errors, log }));
})().catch((e) => { console.error(e); process.exit(1); });
"""


def review() -> dict:
    REVIEW.mkdir(parents=True, exist_ok=True)
    cfg = {"out": str(OUT), "dir": str(REVIEW), "ids": ["v1", "v2", "v3", "v4", "v5"]}
    outp = run_js("review", REVIEW_JS.replace("__CFG__", json.dumps(cfg)), 900)
    res = json.loads(outp.strip().splitlines()[-1])
    (REVIEW / "review.json").write_text(json.dumps(res, indent=1))
    return res


# ================================================================== main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--recompute", action="store_true")
    ap.add_argument("--recapture", action="store_true")
    ap.add_argument("--data-only", action="store_true")
    ap.add_argument("--capture-only", action="store_true")
    ap.add_argument("--no-review", action="store_true")
    ap.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    if a.worker:
        return worker_main(a.workers)
    SRC.mkdir(parents=True, exist_ok=True)
    if a.recompute or not DATA.exists():
        data = compute(a.workers)
        DATA.write_text(json.dumps(data, separators=(",", ":")))
        print(f"data: {DATA} in {data['wall_s']} s", flush=True)
    data = json.loads(DATA.read_text())
    if ensure_extras(data):
        DATA.write_text(json.dumps(data, separators=(",", ":")))
        print("data: extras added", flush=True)
    if a.data_only:
        return 0
    cap = capture(a.recapture)
    if a.capture_only:
        return 0
    rc = build(data, cap)
    if rc or a.no_review:
        return rc
    res = review()
    print(f"review: {len(res['errors'])} page errors; h-scroll 1280 {res['log']['hscroll1280']} px, 390 {res['log']['hscroll390']} px; "
          f"renders in {REVIEW}")
    for e in res["errors"][:10]:
        print("  page error:", e)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
