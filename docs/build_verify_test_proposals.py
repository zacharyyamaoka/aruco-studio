"""Verify as a unit test: 5 proposals, a babble gallery (Zach, 2026-10-21).

    .venv/bin/python docs/build_verify_test_proposals.py            # data (cached) + gallery
    .venv/bin/python docs/build_verify_test_proposals.py --recompute
    .venv/bin/python docs/build_verify_test_proposals.py --guide    # the label-placement table only

Every number in the gallery is the shipped core's: aruco_studio.web_verify
(the plan rendered by verify.camera, read by OpenCV's ArucoDetector) under
CPython, on a re-creation of Zach's document of 2026-10-21 (Grid 3x1 #16-18,
#19-21, #22-24 and Grid 2x1 #25-26, DICT_4X4_50, 30 mm, inkjet vinyl). The
engines below (reading_range, ladder, smoke, break_it, reach) are what each
proposal would run; `reading_range` is the one a build would move into
web_verify.py beside `readable`, and `placement_guide` is that same engine
on a board of every label placement and corner mark (the public guide).

Writes reports/media/verify-unit-test-proposals-2026-10-21.html (and its
data cache beside it, -data.json; reports/media/ is git-ignored). Babble
gallery shell: ~/zach_brain/Settings/Skills/babble (scripts/gallery.py).
"""
from __future__ import annotations

import argparse
import base64
import copy
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

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from aruco_studio import web_api as W  # noqa: E402
from aruco_studio import web_verify as V  # noqa: E402
from aruco_studio.verify import camera as C  # noqa: E402

OUT = ROOT / "reports/media/verify-unit-test-proposals-2026-10-21.html"
CACHE = ROOT / "reports/media/verify-unit-test-proposals-2026-10-21-data.json"
SKILL = Path.home() / "zach_brain/Settings/Skills/babble"
SHOTS = Path(os.environ.get("VT_SHOTS", "/tmp"))

# ------------------------------------------------------------------ the fixture

INK = copy.deepcopy(next(p for p in W.presets() if p["name"] == "Inkjet · Letter vinyl"))


def req(cols: int, first_id: int, mm: float = 30.0, label: dict | None = None,
        marker: dict | None = None, single: bool = False) -> dict:
    """A PlanRequest as the Studio sends it (tests/web/test_web_verify.py's shape)."""
    sep = round(mm / 3.0, 1)
    m = {"type": "single" if single else "grid", "dictionary": "DICT_4X4_50",
         "first_id": first_id, "auto": False, "marker_mm": mm, "checker_mm": 0.0,
         "separation_mm": 0.0 if single else sep, "cols": 1 if single else cols, "rows": 1,
         "turn": 0, "flip": False, "quiet_modules": 1.0, "corner_mark": "none"}
    m.update(marker or {})
    lb = {"on": True, "text": "#{ids}", "height_mm": 0.0, "side": "below", "gap_mm": 2.0,
          "offset_mm": [0.0, 0.0], "place": "on_marker"}
    lb.update(label or {})
    outside = lb.get("place") == "outside" and lb.get("on")
    w = (mm + 10.0) if single else (cols * mm + (cols - 1) * sep + 3.5)
    h = mm + (18.0 if outside else 10.0)
    return {"rect": {"cx": 0.0, "cy": 0.0, "w": w, "h": h, "angle_deg": 0.0}, "marker": m,
            "label": lb, "preset": INK, "reference_face": False}


def doc(mm: float, a_label_mm: float) -> list:
    """Zach's document (his 2026-10-21 screenshot): four boards. Board A's
    label is typed 5 mm tall, a whole module, which the core's lint flags
    ("over the 2.50 mm the border row holds") -- the demo's label failure."""
    return [
        {"key": "A", "name": "Grid 3×1 #16–18", "req": req(3, 16, mm, {"height_mm": a_label_mm})},
        {"key": "B", "name": "Grid 3×1 #19–21", "req": req(3, 19, mm)},
        {"key": "C", "name": "Grid 3×1 #22–24", "req": req(3, 22, mm)},
        {"key": "D", "name": "Grid 2×1 #25–26", "req": req(2, 25, mm)},
    ]


DOCS = {"before": doc(30.0, 5.0), "label": doc(30.0, 0.0), "after": doc(40.0, 0.0)}

# The camera library (Zach's addendum 1). Each entry is the colour stream an
# ArUco pipeline reads, from its maker's datasheet (sources in CAMERA_SOURCES;
# filled from the 2026-10-21 lookup). hfov is across the width.
CAMERAS: dict = {}
CAMERA_SOURCES: dict = {}
DEFAULT_CAMERA = "d435"

# The adversarial budget ("Field"): every draw is a camera somewhere inside it.
BUDGET = {"name": "Field", "tilt_max": 45.0, "blur": (0.3, 1.5), "grain": (0.02, 0.2),
          "glare": (0.0, 0.5), "dirt": 0.0}
N_DRAWS = 24          # cases per distance probe
NEED = 23             # ... of which this many must read every id (>= 95 %)
N_NEAR = 8            # cases per probe at the near end (it is about fitting the frame)
REQUIREMENT = (300.0, 2000.0)   # the optional batch requirement in the demo (mm)
DRAW_SEED = 20261021


def draws(n: int = N_DRAWS, seed: int = DRAW_SEED, budget: dict = BUDGET, tilt=None) -> list:
    """n cameras inside the budget, seeded: the same cases at every distance,
    so a run is deterministic and the range is (nearly) monotone."""
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        th = rng.uniform(0.0, budget["tilt_max"]) if tilt is None else float(tilt)
        ph = rng.uniform(0.0, 2.0 * math.pi)
        out.append({"tilt_deg": th * math.cos(ph), "yaw_deg": th * math.sin(ph),
                    "blur_px": float(rng.uniform(*budget["blur"])),
                    "noise": float(rng.uniform(*budget["grain"])),
                    "glare": float(rng.uniform(*budget["glare"])),
                    "occlusion": float(budget["dirt"]), "seed": int(rng.integers(0, 2**31 - 1))})
    return out


class Ctx:
    """One board seen by one camera: the plan, its scene (label as built) and
    a render counter."""

    def __init__(self, r: dict, cam: dict):
        self.req = V.placed(r)
        self.d = V._plan(self.req)
        self.scene = C.scene_of(self.d, V._label(self.req, self.d))
        self.cam = cam
        self.renders = 0
        self.ms = 0.0

    def view(self, dist: float, v: dict, picture: bool = False) -> dict:
        t0 = time.perf_counter()
        o = V._view(self.d, self.scene, C.Cam.of(dict(self.cam, distance_mm=float(dist))), v,
                    picture=picture)
        self.ms += (time.perf_counter() - t0) * 1000.0
        self.renders += 1
        return o

    def probe(self, dist: float, cases: list, need: int) -> dict:
        """Read the board at `dist` under each case; stop as soon as the
        verdict is known (the misses allowed are spent, or enough have read)."""
        ok = 0
        miss = 0
        worst = None
        allowed = len(cases) - need
        per_id = {i: 0 for i in self.d["ids"]}
        for k, v in enumerate(cases):
            o = self.view(dist, v)
            for i in o["found"]:
                per_id[i] += 1
            if o["ok"]:
                ok += 1
            else:
                miss += 1
                if worst is None or len(o["found"]) < worst["found"]:
                    worst = {"case": k, "found": len(o["found"]), "missing": o["missing"]}
                if miss > allowed:
                    break
            if ok >= need:
                break
        return {"d": round(dist, 1), "ok": ok, "miss": miss, "n": ok + miss,
                "pass": ok >= need, "worst": worst, "per_id": per_id}


# ------------------------------------------------------------------ the engines

def bisect_range(r: dict, cam: dict, budget: dict = BUDGET) -> dict:
    """The first engine tried (kept for the calibration): bisection on the
    pass / fail of N_DRAWS cases. Measured 2026-10-21 against 1,536 renders
    of board B: it lands ~12 % past the true 95 % crossing (the farthest
    distance a lucky case set passes wins), so reading_range fits instead."""
    cx = Ctx(r, cam)
    cases = draws(budget=budget)
    lo, hi = 300.0, 420.0
    if not cx.probe(lo, cases, NEED)["pass"]:
        return {"far": None, "renders": cx.renders}
    while hi < 30000.0 and cx.probe(hi, cases, NEED)["pass"]:
        lo, hi = hi, hi * 1.4
    while hi / lo > 1.04:
        mid = math.sqrt(lo * hi)
        if cx.probe(mid, cases, NEED)["pass"]:
            lo = mid
        else:
            hi = mid
    return {"far": round(lo, 1), "renders": cx.renders}


JITTER = 0.04          # each case at distance x U(1 -/+ 4 %): the pixel grid's holes average out
P_READ = 0.95


def logistic(xs: list, ys: list):
    """P(read) = 1 / (1 + exp(-(a + b x))), x = ln(distance mm), by IRLS with
    a whisper of ridge (all-pass or all-fail grids stay finite). -> a, b, cov."""
    X = np.asarray(xs, float)
    Y = np.asarray(ys, float)
    a, b = 10.0, -1.0
    H = np.eye(2)
    for _ in range(60):
        z = np.clip(a + b * X, -30, 30)
        pz = 1.0 / (1.0 + np.exp(-z))
        w = pz * (1.0 - pz) + 1e-9
        g = np.array([np.sum(Y - pz), np.sum((Y - pz) * X)]) - 1e-4 * np.array([a, b])
        H = np.array([[np.sum(w), np.sum(w * X)], [np.sum(w * X), np.sum(w * X * X)]]) + 1e-4 * np.eye(2)
        step = np.linalg.solve(H, g)
        a, b = a + step[0], b + step[1]
        if abs(step).max() < 1e-7:
            break
    return a, b, np.linalg.inv(H)


def pava_down(y: list, w: list) -> list:
    """Pool adjacent violators: the closest non-increasing sequence (weighted)."""
    blocks = [[v, wt, 1] for v, wt in zip(y, w)]
    i = 0
    while i < len(blocks) - 1:
        if blocks[i][0] < blocks[i + 1][0]:
            a, b = blocks[i], blocks[i + 1]
            wt = a[1] + b[1]
            blocks[i] = [(a[0] * a[1] + b[0] * b[1]) / wt, wt, a[2] + b[2]]
            del blocks[i + 1]
            i = max(0, i - 1)
        else:
            i += 1
    out = []
    for v, _, k in blocks:
        out += [v] * k
    return out


def crossing(grid: list, M: np.ndarray, idx) -> float | None:
    """Where the read rate (non-increasing, PAVA) falls through P_READ,
    interpolated in ln(distance); None when even the nearest distance misses."""
    rates = M[:, idx].mean(axis=1)
    iso = pava_down(list(rates), [1.0] * len(rates))
    if iso[0] < P_READ:
        return None
    for i in range(len(iso) - 1):
        if iso[i + 1] < P_READ:
            t = (iso[i] - P_READ) / max(1e-9, iso[i] - iso[i + 1])
            return math.exp(math.log(grid[i]) + t * (math.log(grid[i + 1]) - math.log(grid[i])))
    return grid[-1]


def far_fit(cx: "Ctx", cases: list, js, lo: float, hi: float):
    """6 distances log-spaced over [0.6 lo, 1.5 hi] (more inward while the
    nearest still misses P_READ), every case at each (no early stop), the
    read rate made non-increasing (PAVA) and its P_READ crossing in
    ln(distance); a 90 % interval by resampling the cases (200 draws, no
    new renders). -> far, (lo90, hi90), rows."""
    g0, g1 = 0.6 * lo, 1.5 * hi
    grid = [g0 * (g1 / g0) ** (k / 5.0) for k in range(6)]

    def row(d):
        return [bool(cx.view(d * j, v)["ok"]) for v, j in zip(cases, js)]
    M = [row(d) for d in grid]
    k = 0
    while sum(M[0]) / len(cases) < P_READ and k < 3 and grid[0] > 60.0:
        grid.insert(0, grid[0] * 0.7)
        M.insert(0, row(grid[0]))
        k += 1
    M = np.array(M, bool)
    n = len(cases)
    far = crossing(grid, M, np.arange(n))
    boot = np.random.default_rng(DRAW_SEED + 2)
    fs = [crossing(grid, M, boot.integers(0, n, n)) for _ in range(200)]
    fs = [x if x is not None else grid[0] * 0.7 for x in fs]
    band = (float(np.percentile(fs, 5)), float(np.percentile(fs, 95)))
    rows = [{"d": round(d, 1), "ok": int(M[i].sum()), "n": n} for i, d in enumerate(grid)]
    return far, band, rows


def bracket(cx: "Ctx", cases: list):
    """(lo, hi): the last of x1.4 steps from 300 mm on 12 cases that all read, and the first that does not."""
    lo = 300.0
    if not cx.probe(lo, cases[:12], 12)["pass"]:
        hi, lo = lo, lo / 1.4
        while lo > 60.0 and not cx.probe(lo, cases[:12], 12)["pass"]:
            hi, lo = lo, lo / 1.4
        return (lo, hi) if lo > 60.0 else (None, None)
    hi = lo * 1.4
    while hi < 30000.0 and cx.probe(hi, cases[:12], 12)["pass"]:
        lo, hi = hi, hi * 1.4
    return lo, hi


def reading_range(r: dict, cam: dict, budget: dict = BUDGET, n: int = 48, focus=None) -> dict:
    """THE engine (V4's, the guide's; a build moves it into web_verify.py
    beside readable): the nearest and farthest distance at which every id
    reads in P_READ of the budget's cameras.

    Far: out from 300 mm in x1.4 steps on 12 cases to the first miss (the
    bracket), then 6 distances log-spaced over [0.6 x, 1.5 x] the bracket,
    `n` seeded cases each at +/- JITTER, and a logistic fit of read vs
    ln(distance) over all of them: far is where it crosses P_READ, with a
    +/- from the fit. WHY a fit, not bisection (measured 2026-10-21, board
    B, D435): bisection said 1.48 m; 192 cases at each of 8 distances put
    the crossing at 1.33 m; the fit on 24 cases a distance gave 1.29-1.37 m
    over four seed sets. Near: where the board (label included) fills 90 %
    of the frame head on, stepped out x1.15 until 8 cases read, never under
    the camera's stated minimum focus."""
    cx = Ctx(r, cam)
    rng_ = np.random.default_rng(DRAW_SEED + 1)
    cases = draws(n, budget=budget)
    js = rng_.uniform(1.0 - JITTER, 1.0 + JITTER, n)
    near_label = None
    p300 = cx.probe(300.0, cases[:12], 12)["pass"]
    lo, hi = bracket(cx, cases)
    if not p300:
        # WHY outward too (measured 2026-10-21): a 1-module label knocked out of
        # a single's border row fails at 0.3 m and reads at 1.2 m -- up close the
        # letters resolve and cut the border; farther out blur fills them in
        d, found = 420.0, None
        while d < 6000.0:
            if cx.probe(d, cases[:12], 12)["pass"]:
                found = d
                break
            d *= 1.4
        if found is not None and (lo is None or lo < 150.0):
            a_, b_ = found / 1.4, found
            while b_ / a_ > 1.08:
                mid = math.sqrt(a_ * b_)
                if cx.probe(mid, cases[:N_NEAR], N_NEAR)["pass"]:
                    b_ = mid
                else:
                    a_ = mid
            near_label = b_
            lo, hi = found, found * 1.4
            while hi < 30000.0 and cx.probe(hi, cases[:12], 12)["pass"]:
                lo, hi = hi, hi * 1.4
    if lo is None:
        return {"near": None, "far": None, "pm": None, "grid": [], "renders": cx.renders, "ms": round(cx.ms, 1)}
    far, band, rows = far_fit(cx, cases, js, lo, hi)
    # near
    u0, v0, u1, v1 = cx.scene.bounds
    W_, H_ = cam["resolution"]
    f = C.Cam(1000.0, W_, H_, cam["hfov_deg"]).f_px
    near = max((u1 - u0) * f / (0.9 * W_), (v1 - v0) * f / (0.9 * H_))
    if focus:
        near = max(near, float(focus))
    if near_label is not None:
        near = max(near, near_label)
    for _ in range(6):
        if cx.probe(near, cases[:N_NEAR], N_NEAR)["pass"]:
            break
        near *= 1.15
    if far is not None and near >= far:
        near = far = None
    pm = None if far is None else round((band[1] - band[0]) / (2.0 * far), 3)
    return {"near": None if near is None else round(near, 1), "far": None if far is None else round(far, 1),
            "band": [round(band[0], 1), round(band[1], 1)], "pm": pm, "grid": rows,
            "renders": cx.renders, "ms": round(cx.ms, 1)}


RUNGS = [150.0, 300.0, 450.0, 700.0, 1000.0, 1400.0, 2000.0, 3000.0]


def ladder(r: dict, cam: dict) -> dict:
    """V1's engine: one test per rung, N_DRAWS cases each, NEED to pass."""
    cx = Ctx(r, cam)
    cases = draws()
    rows = [cx.probe(x, cases, NEED) for x in RUNGS]
    return {"rungs": rows, "renders": cx.renders, "ms": round(cx.ms, 1)}


def smoke(r: dict, cam: dict) -> dict:
    """V2's badge: the far limit on 12 cases that must all read (a cheap
    stand-in for >= 95 % of 24), bisected to 8 %; the 24-case range confirms
    it in idle time."""
    cx = Ctx(r, cam)
    cases = draws(12)
    lo, hi = 300.0, 420.0
    if not cx.probe(lo, cases, 12)["pass"]:
        return {"far": None, "renders": cx.renders, "ms": cx.ms}
    while hi < 30000.0 and cx.probe(hi, cases, 12)["pass"]:
        lo, hi = hi, hi * 1.4
    while hi / lo > 1.08:
        mid = math.sqrt(lo * hi)
        if cx.probe(mid, cases, 12)["pass"]:
            lo = mid
        else:
            hi = mid
    return {"far": round(lo, 1), "renders": cx.renders, "ms": round(cx.ms, 1)}


KNOBS = [("dist", None), ("tilt", 0.0), ("blur_px", BUDGET["blur"][0]),
         ("noise", BUDGET["grain"][0]), ("glare", BUDGET["glare"][0])]


def attacks(seed: int = 7) -> list:
    """V3's opening moves: the budget's corners (tilt at its limit on the four
    sides, glare off / on, blur and grain at their worst), then random cases."""
    out = []
    for ph in (0.0, 90.0, 180.0, 270.0):
        for gl in (BUDGET["glare"][0], BUDGET["glare"][1]):
            t = BUDGET["tilt_max"]
            out.append({"tilt_deg": t * math.cos(math.radians(ph)),
                        "yaw_deg": t * math.sin(math.radians(ph)),
                        "blur_px": BUDGET["blur"][1], "noise": BUDGET["grain"][1], "glare": gl,
                        "occlusion": 0.0, "seed": int(ph) + int(gl * 10)})
    return out + draws(40, seed=seed)


def break_it(r: dict, cam: dict) -> dict:
    """V3's engine: the farthest distance no attack breaks (48 attacks per
    probe, a single miss breaks it), then the first counterexample beyond it
    shrunk knob by knob toward the kindest camera (the same seed), so what
    is left is what breaks it."""
    cx = Ctx(r, cam)
    acts = attacks()

    def holds(dist):
        for k, v in enumerate(acts):
            o = cx.view(dist, v)
            if not o["ok"]:
                return False, k, o
        return True, None, None

    lo = 300.0
    ok, k, o = holds(lo)
    if not ok:
        hi = lo
        lo = None
    else:
        hi = lo * 1.4
        while hi < 30000.0:
            ok, k2, o2 = holds(hi)
            if not ok:
                break
            lo, hi = hi, hi * 1.4
        while hi / lo > 1.06:
            mid = math.sqrt(lo * hi)
            ok, _, _ = holds(mid)
            if ok:
                lo = mid
            else:
                hi = mid
    # the counterexample at `hi`: find the first attack that breaks it there
    ce_k, ce = None, None
    for k3, v in enumerate(acts):
        o = cx.view(hi, v)
        if not o["ok"]:
            ce_k, ce = k3, dict(v)
            break
    shrunk = None
    if ce is not None:
        cur = {"dist": hi, **ce}

        def breaks(c):
            v = {k: c[k] for k in ("tilt_deg", "yaw_deg", "blur_px", "noise", "glare",
                                     "occlusion", "seed")}
            return not cx.view(c["dist"], v)["ok"]

        relaxed = {}
        # distance: in toward the hunt's start (0.3 m) while it still breaks
        # (bisection, 5 steps); WHY not nearer: under ~0.2 m a bigger board
        # leaves the frame, which is the near end, not this failure
        a, b = 300.0, cur["dist"]
        c2 = dict(cur, dist=a)
        if b <= a or breaks(c2):
            cur = c2 if b > a else cur
            relaxed["dist"] = "breaks even at 0.3 m"
        else:
            for _ in range(5):
                mid = math.sqrt(a * b)
                if breaks(dict(cur, dist=mid)):
                    b = mid
                else:
                    a = mid
            cur["dist"] = b
        # tilt: scale tilt and yaw toward 0
        def scaled(c, f):
            return dict(c, tilt_deg=c["tilt_deg"] * f, yaw_deg=c["yaw_deg"] * f)
        for name, kind in (("tilt", None), ("blur_px", BUDGET["blur"][0]),
                           ("noise", BUDGET["grain"][0]), ("glare", BUDGET["glare"][0])):
            kindest = scaled(cur, 0.0) if name == "tilt" else dict(cur, **{name: kind})
            if breaks(kindest):
                cur = kindest
                relaxed[name] = "not needed"
                continue
            a, b = 0.0, 1.0
            for _ in range(4):
                mid = (a + b) / 2.0
                trial = scaled(cur, mid) if name == "tilt" else dict(cur, **{name: kind + (cur[name] - kind) * mid})
                if breaks(trial):
                    b = mid
                else:
                    a = mid
            cur = scaled(cur, b) if name == "tilt" else dict(cur, **{name: kind + (cur[name] - kind) * b})
        shrunk = {"case": cur, "relaxed": relaxed}
    return {"holds_to": None if lo is None else round(lo, 1), "breaks_at": round(hi, 1),
            "attack": ce_k, "shrunk": shrunk, "renders": cx.renders, "ms": round(cx.ms, 1)}


ANGLES = [0.0, 15.0, 30.0, 45.0]


def reach(r: dict, cam: dict, n: int = 48) -> dict:
    """V5's engine: reading_range's far fit at each viewing angle (tilt fixed,
    its direction and the other knobs drawn from the budget)."""
    cx = Ctx(r, cam)
    out = []
    for th in ANGLES:
        cases = draws(n, tilt=th, seed=DRAW_SEED + int(th))
        js = np.random.default_rng(DRAW_SEED + 1 + int(th)).uniform(1.0 - JITTER, 1.0 + JITTER, n)
        lo, hi = bracket(cx, cases)
        if lo is None:
            out.append({"angle": th, "far": None})
            continue
        far, band, _ = far_fit(cx, cases, js, lo, hi)
        out.append({"angle": th, "far": None if far is None else round(far, 1),
                    "band": [round(band[0], 1), round(band[1], 1)]})
    return {"reach": out, "renders": cx.renders, "ms": round(cx.ms, 1)}


# ------------------------------------------------------------------ pictures

def webp(img: np.ndarray, max_w: int = 360, q: int = 70) -> str:
    h, w = img.shape[:2]
    if w > max_w:
        img = cv2.resize(img, (max_w, max(1, round(h * max_w / w))), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".webp", img, [cv2.IMWRITE_WEBP_QUALITY, q])
    return "data:image/webp;base64," + base64.b64encode(buf.tobytes()).decode("ascii")


def art(r: dict) -> dict:
    """The board as printed (head on, crisp): the simulator's own top view."""
    cx = Ctx(r, {"resolution": [3840, 2160], "hfov_deg": 60.0})
    f = 1920.0 / math.tan(math.radians(30.0))
    dist = cx.d["marker"]["marker_length_m"] * 1000.0 / 6.0 * f / 15.0   # 15 px per cell
    v = C.simulate(cx.scene, C.Cam.of(dict(cx.cam, distance_mm=dist)),
                   {"tilt_deg": 0, "yaw_deg": 0, "blur_px": 0.35, "noise": 0, "glare": 0,
                    "occlusion": 0, "seed": 0})
    img = v.img[C.CROP_MARGIN_PX - 6:-C.CROP_MARGIN_PX + 6, C.CROP_MARGIN_PX - 6:-C.CROP_MARGIN_PX + 6]
    return {"src": webp(cv2.cvtColor(img, cv2.COLOR_GRAY2BGR), 560, 80), "w": int(img.shape[1]),
            "h": int(img.shape[0])}


def shot(r: dict, cam: dict, dist: float, v: dict, max_w: int = 300) -> dict:
    """A real verify view (detections in green, missing ids' outlines in red)."""
    cx = Ctx(r, cam)
    o = cx.view(dist, v, picture=True)
    raw = base64.b64decode(o["image_png_base64"])
    img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    return {"src": webp(img, max_w, 72), "found": o["found"], "missing": o["missing"],
            "ppc": o["px_per_cell"], "d": round(dist), "view": {k: round(float(x), 2) if k != "seed" else x
                                                               for k, x in v.items()}}


# ------------------------------------------------------------------ the guide

GUIDE = [
    ("No label", {"on": False}, {}),
    ("On the marker · border row · Auto (½ module)", {}, {}),
    ("On the marker · border row · ¾ module typed", {"height_mm": 3.75}, {}),
    ("On the marker · border row · 1 module typed", {"height_mm": 5.0}, {}),
    ("On the marker · border row · above", {"side": "above"}, {}),
    ("On the marker · quiet zone (white) · Auto", {"surface": "white"}, {}),
    ("On the marker · quiet zone (white) · 1 module typed", {"surface": "white", "height_mm": 5.0}, {}),
    ("Outside · below · Auto", {"place": "outside"}, {}),
    ("Outside · right · Auto", {"place": "outside", "side": "right"}, {}),
    ("Corner mark · triangle (+ Auto label)", {}, {"corner_mark": "triangle"}),
    ("Corner mark · cut (+ Auto label)", {}, {"corner_mark": "cut"}),
]


GUIDE_N = 48           # cases per distance for each placement's range
GUIDE_PAIRED = 96      # paired cases at the plain marker's far end


def _guide_job(args):
    name, lab, mk, cam, at = args
    r = req(1, 7, 30.0, lab, mk, single=True)
    p = W.plan(r)
    warns = [w["text"] for w in p.get("warnings", []) if w.get("level") == "warn"]
    rr = reading_range(r, cam, n=GUIDE_N) if at is None else {"near": None, "far": None, "pm": None, "renders": 0}
    out = {"name": name, "label": lab, "marker": mk, "near": rr["near"], "far": rr["far"], "pm": rr["pm"],
           "renders": rr["renders"], "warnings": warns[:2], "art": art(r)}
    if at is not None:
        cx = Ctx(r, cam)
        cases = draws(GUIDE_PAIRED, seed=DRAW_SEED + 7)
        js = np.random.default_rng(DRAW_SEED + 8).uniform(1.0 - JITTER, 1.0 + JITTER, GUIDE_PAIRED)
        out["oks"] = [bool(cx.view(at * j, v)["ok"]) for v, j in zip(cases, js)]
        out["renders"] = cx.renders
    return out


def placement_guide(cam: dict, workers: int = 8) -> list:
    """The public "Label placement" guide: Verify's reading_range on one 30 mm
    DICT_4X4_50 single per placement (a board of every label placement and
    corner mark), then each one read by the SAME 96 cameras at the plain
    marker's far end, where a cost would show (paired: a difference is the
    label's, not the draw's). Pure CPython, no browser."""
    with ProcessPoolExecutor(workers) as ex:
        rows = list(ex.map(_guide_job, [(n, l, m_, cam, None) for n, l, m_ in GUIDE]))
        at = rows[0]["far"]
        paired = list(ex.map(_guide_job, [(n, l, m_, cam, at) for n, l, m_ in GUIDE]))
    base_oks = paired[0]["oks"]
    nb = len(base_oks)
    for row, pr in zip(rows, paired):
        row["at"] = round(at, 1)
        row["renders"] += pr["renders"]
        oks = pr["oks"]
        row["rate_at"] = round(sum(oks) / nb, 3)
        row["lost"] = sum(1 for a, b in zip(base_oks, oks) if a and not b)
        row["gained"] = sum(1 for a, b in zip(base_oks, oks) if b and not a)
        d = [int(b) - int(a) for a, b in zip(base_oks, oks)]
        row["d_rate"] = round(sum(d) / nb, 3)
        sd = float(np.std(d, ddof=1)) if nb > 1 else 0.0
        row["d_ci"] = round(1.96 * sd / math.sqrt(nb), 3)
        row["vs_none"] = None if (row["far"] is None or not rows[0]["far"]) else round(row["far"] / rows[0]["far"] - 1.0, 3)
    return rows


# ------------------------------------------------------------------ compute

def _feature_job(args):
    kind, dkey, fkey, r, cam = args
    if kind == "range":
        return (kind, dkey, fkey, cam["key"], reading_range(r, cam, focus=cam.get("focus")))
    if kind == "ladder":
        return (kind, dkey, fkey, cam["key"], ladder(r, cam))
    if kind == "smoke":
        return (kind, dkey, fkey, cam["key"], smoke(r, cam))
    if kind == "break":
        return (kind, dkey, fkey, cam["key"], break_it(r, cam))
    if kind == "reach":
        return (kind, dkey, fkey, cam["key"], reach(r, cam))
    raise ValueError(kind)


def cam_of(key: str) -> dict:
    c = CAMERAS[key]
    return {"key": key, "resolution": list(c["res"]), "hfov_deg": float(c["hfov"]), "focus": c.get("focus")}


def compute(workers: int = 10) -> dict:
    t0 = time.time()
    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    data = {"generated": time.strftime("%Y-%m-%d %H:%M"), "head": head, "budget": BUDGET,
            "n": N_DRAWS, "need": NEED, "rungs": RUNGS, "angles": ANGLES,
            "requirement": REQUIREMENT, "cameras": CAMERAS, "default_camera": DEFAULT_CAMERA,
            "docs": {}, "range": {}, "ladder": {}, "smoke": {}, "break": {}, "reach": {}}
    dc = cam_of(DEFAULT_CAMERA)
    # the size fix first: the smallest size whose every board reaches the
    # requirement's far end (the "make it >= N mm" a failure suggests is
    # computed, never a rule of thumb); the "after" document uses it
    size_jobs = [("range", f"size{int(mm)}", f["key"], f["req"], dc)
                 for mm in (35.0, 40.0, 45.0, 50.0, 60.0) for f in doc(mm, 0.0)]
    with ProcessPoolExecutor(workers) as ex:
        for kind, dkey, fkey, ck, res in ex.map(_feature_job, size_jobs):
            data[kind].setdefault(dkey, {}).setdefault(fkey, {})[ck] = res
    fix = next((mm for mm in (35, 40, 45, 50, 60)
                if all((data["range"][f"size{mm}"][k][DEFAULT_CAMERA]["far"] or 0) >= REQUIREMENT[1]
                       for k in "ABCD")), 60)
    data["fix_mm"] = fix
    DOCS["after"] = doc(float(fix), 0.0)
    print(f"sizes in {time.time() - t0:.0f} s: fix {fix} mm", flush=True)
    jobs = []
    for dkey, feats in DOCS.items():
        data["docs"][dkey] = []
        for f in feats:
            p = W.plan(f["req"])
            data["docs"][dkey].append({
                "key": f["key"], "name": f["name"], "ids": p["ids"], "cell_mm": p["cell_mm"],
                "outer_mm": p["outer_mm"], "marker_mm": p["marker_mm"],
                "warnings": [w["text"] for w in p.get("warnings", []) if w.get("level") == "warn"],
                "art": art(f["req"])})
            cams = list(CAMERAS) if dkey == "before" else [DEFAULT_CAMERA]
            for ck in cams:
                jobs.append(("range", dkey, f["key"], f["req"], cam_of(ck)))
            for kind in ("ladder", "smoke", "break", "reach"):
                jobs.append((kind, dkey, f["key"], f["req"], dc))
    with ProcessPoolExecutor(workers) as ex:
        for kind, dkey, fkey, ck, res in ex.map(_feature_job, jobs):
            data[kind].setdefault(dkey, {}).setdefault(fkey, {})[ck] = res
    print(f"engines: {len(jobs)} jobs in {time.time() - t0:.0f} s", flush=True)
    data["guide"] = placement_guide(dc, workers)
    print(f"guide in {time.time() - t0:.0f} s", flush=True)
    data["shots"] = shots(data)
    # one render timed alone, single process, for the speed estimates
    data["timing"] = time_renders()
    data["wall_s"] = round(time.time() - t0, 1)
    return data


def shots(data: dict) -> dict:
    """The real camera views the mocks show."""
    dc = cam_of(DEFAULT_CAMERA)
    A = DOCS["before"][0]["req"]
    B = DOCS["before"][1]["req"]
    out = {}
    cases = draws()
    # A at 1 m: the case that loses #17 under the typed 5 mm label
    lad = data["ladder"]["before"]["A"][DEFAULT_CAMERA]["rungs"]
    rung = next((x for x in lad if x["d"] == 1000.0), lad[4])
    k = (rung["worst"] or {"case": 0})["case"]
    out["A_label_1m"] = shot(A, dc, 1000.0, cases[k])
    out["A_fixed_1m"] = shot(DOCS["label"][0]["req"], dc, 1000.0, cases[k])
    # B at its far end and a little past it: the first case that reads at
    # the far end but not at 1.15 x (the edge, seen)
    rr = data["range"]["before"]["B"][DEFAULT_CAMERA]
    far = rr["far"]
    cx = Ctx(B, dc)
    kb = 0
    for k, v in enumerate(cases):
        if cx.view(far, v)["ok"] and not cx.view(far * 1.15, v)["ok"]:
            kb = k
            break
    out["B_at_far"] = shot(B, dc, far, cases[kb])
    out["B_beyond"] = shot(B, dc, far * 1.15, cases[kb])
    out["B_2m"] = shot(B, dc, 2000.0, cases[kb])
    out["Bfix_2m"] = shot(DOCS["after"][1]["req"], dc, 2000.0, cases[kb])
    # V3: the shrunk counterexamples
    for key, dk in (("A", "before"), ("B", "before"), ("B", "after")):
        br = data["break"][dk][key][DEFAULT_CAMERA]
        if br["shrunk"]:
            c = br["shrunk"]["case"]
            v = {x: c[x] for x in ("tilt_deg", "yaw_deg", "blur_px", "noise", "glare", "occlusion", "seed")}
            out[f"break_{key}_{dk}"] = shot(DOCS[dk][["A", "B", "C", "D"].index(key)]["req"], dc,
                                            c["dist"], v)
    # V5: a far, oblique failure for B
    out["B_45deg"] = shot(B, dc, 1600.0, draws(tilt=45.0, seed=DRAW_SEED + 45)[3])
    return out


def time_renders() -> dict:
    """Median ms of one metrics-only render and one with the picture, per
    distance, for board B and the default camera (single process)."""
    cx = Ctx(DOCS["before"][1]["req"], cam_of(DEFAULT_CAMERA))
    cases = draws()
    out = {}
    for x in (150.0, 300.0, 600.0, 1000.0, 1600.0, 2500.0):
        ts, tp = [], []
        for v in cases[:10]:
            t = time.perf_counter()
            cx.view(x, v)
            ts.append((time.perf_counter() - t) * 1000.0)
        for v in cases[:4]:
            t = time.perf_counter()
            cx.view(x, v, picture=True)
            tp.append((time.perf_counter() - t) * 1000.0)
        out[str(int(x))] = {"metrics_ms": round(float(np.median(ts)), 2),
                            "picture_ms": round(float(np.median(tp)), 2)}
    return out


# ------------------------------------------------------------------ main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--recompute", action="store_true")
    ap.add_argument("--data-only", action="store_true")
    ap.add_argument("--guide", action="store_true", help="print the label-placement table only")
    ap.add_argument("--workers", type=int, default=10)
    a = ap.parse_args()
    load_cameras()
    if a.guide:
        t0 = time.time()
        rows = placement_guide(cam_of(DEFAULT_CAMERA), a.workers)
        print(guide_markdown(rows, CAMERAS[DEFAULT_CAMERA]))
        print(f"\n{sum(r['renders'] for r in rows)} renders, {time.time() - t0:.0f} s")
        return 0
    if a.recompute or not CACHE.exists():
        data = compute(a.workers)
        CACHE.write_text(json.dumps(data, separators=(",", ":")))
        print(f"data: {CACHE} ({CACHE.stat().st_size / 1e6:.2f} MB) in {data['wall_s']} s")
    data = json.loads(CACHE.read_text())
    if ensure_extras(data, a.workers) | ("ratio" not in data and bool(pyodide_ratio(data))):
        CACHE.write_text(json.dumps(data, separators=(",", ":")))
    if a.data_only:
        return 0
    return build(data)


def load_cameras():
    """Filled below (the camera library section)."""
    CAMERAS.update(CAMERA_LIBRARY)
    CAMERA_SOURCES.update(SOURCES)


# The camera library (Zach's addendum, 2026-10-21): the colour stream an ArUco
# pipeline reads, per its maker (looked up 2026-10-21; `src` numbers SOURCES).
# `note` says what is computed rather than stated. `focus` is the colour
# camera's stated minimum focus (mm) where the maker gives one.
CAMERA_LIBRARY: dict = {
    "d405": {"name": "RealSense D405", "stream": "colour 1280×720", "res": (1280, 720), "hfov": 87.0,
             "src": [1, 4], "focus": None, "shutter": "global",
             "note": "colour comes from the left depth imager; 87° is Intel's store figure (the datasheet has no D405 colour-FOV row)"},
    "d415": {"name": "RealSense D415", "stream": "colour 1920×1080", "res": (1920, 1080), "hfov": 69.4,
             "src": [1], "focus": None, "shutter": "rolling", "note": ""},
    "d435": {"name": "RealSense D435", "stream": "colour 1920×1080", "res": (1920, 1080), "hfov": 69.0,
             "src": [1], "focus": None, "shutter": "rolling", "note": "the one BAM owns"},
    "d455": {"name": "RealSense D455", "stream": "colour 1280×800", "res": (1280, 800), "hfov": 90.0,
             "src": [1], "focus": None, "shutter": "global", "note": ""},
    "oakd": {"name": "Luxonis OAK-D", "stream": "colour 1080p", "res": (1920, 1080), "hfov": 69.0,
             "src": [2, 3], "focus": 80.0, "shutter": "rolling", "note": "the ISP's 1080p of the 12 MP IMX378"},
    "oakd12": {"name": "Luxonis OAK-D", "stream": "colour 12 MP", "res": (4056, 3040), "hfov": 69.0,
               "src": [2, 3], "focus": 80.0, "shutter": "rolling", "note": ""},
    "zed2": {"name": "Stereolabs ZED 2", "stream": "left eye 1080p", "res": (1920, 1080), "hfov": 84.8,
             "src": [5], "focus": None, "shutter": "rolling",
             "note": "HFOV computed for the 1080p crop (110° is the full sensor)"},
    "zed2k": {"name": "Stereolabs ZED 2", "stream": "left eye 2.2K", "res": (2208, 1242), "hfov": 92.2,
              "src": [5], "focus": None, "shutter": "rolling", "note": "HFOV computed for the 2.2K crop"},
    "c920": {"name": "Logitech C920", "stream": "1080p", "res": (1920, 1080), "hfov": 70.4,
             "src": [6], "focus": None, "shutter": "rolling", "note": "HFOV computed from the stated 78° diagonal"},
    "picam3": {"name": "Raspberry Pi Camera Module 3", "stream": "full sensor", "res": (4608, 2592), "hfov": 66.0,
               "src": [7], "focus": 100.0, "shutter": "rolling", "note": ""},
    "picam3w": {"name": "Raspberry Pi Camera Module 3 Wide", "stream": "full sensor", "res": (4608, 2592), "hfov": 102.0,
                "src": [7], "focus": 50.0, "shutter": "rolling", "note": ""},
    "iphone": {"name": "iPhone 16 Pro · Main", "stream": "4K video", "res": (3840, 2160), "hfov": 71.6,
               "src": [8], "focus": None, "shutter": "rolling",
               "note": "HFOV computed from 24 mm (35 mm equiv.), assuming 16:9 crops the height only"},
    "iphone12": {"name": "iPhone 16 Pro · Main", "stream": "12 MP photo", "res": (4032, 3024), "hfov": 71.6,
                 "src": [8], "focus": None, "shutter": "rolling", "note": "HFOV computed from 24 mm (35 mm equiv.)"},
}
SOURCES: dict = {
    1: ("RealSense D400 Series datasheet, Mar 2026 (tables 3-18, 3-19, 4-4)",
        "https://www.realsenseai.com/wp-content/uploads/2026/03/RealSense-D400-Series-Datasheet-Mar-2026.pdf"),
    2: ("Luxonis docs: OAK-D", "https://docs.luxonis.com/hardware/products/OAK-D"),
    3: ("OAK-D datasheet (Luxonis depthai-hardware)",
        "https://raw.githubusercontent.com/luxonis/depthai-hardware/master/BW1098OAK_USB3C/Datasheet/OAK-D_Datasheet.pdf"),
    4: ("Intel store: RealSense D405 (search snippet; page did not load)",
        "https://store.intelrealsense.com/buy-intel-realsense-depth-camera-d405.html"),
    5: ("Stereolabs ZED 2 datasheet (reseller copy; the official PDF 404'd)",
        "https://docs.clearpathrobotics.com/assets/files/clearpath_robotics_023611-TDS1-4397f62e823823822ebb46c234e19834.pdf"),
    6: ("Logitech C920 product page", "https://logitech.com/en-gb/product/hd-pro-webcam-c920?crid=34"),
    7: ("Raspberry Pi camera documentation", "https://www.raspberrypi.com/documentation/accessories/camera.html"),
    8: ("Apple Support: iPhone 16 Pro Max tech specs", "https://support.apple.com/en-us/121032"),
}


def guide_markdown(rows: list, cam: dict) -> str:
    at = rows[0]["at"]
    lines = [f"Camera: {cam['name']} {cam['stream']} ({cam['res'][0]}×{cam['res'][1]}, {cam['hfov']:g}°) · budget Field · "
             f"paired reads at {fmt_m(at)}, the plain marker's far end, {GUIDE_PAIRED} cameras", "",
             "| Placement | Reads from | Reads to (± 90 %) | Reads at the edge | vs no label (paired) | Verdict |",
             "|---|---|---|---|---|---|"]
    for r in rows:
        pm = "" if r["pm"] is None else f" ± {r['pm'] * 100:.0f} %"
        lines.append(f"| {r['name']} | {fmt_m(r['near'])} | {fmt_m(r['far'])}{pm} | {r['rate_at'] * 100:.0f} % | "
                     f"{r['d_rate'] * 100:+.0f} ± {r['d_ci'] * 100:.0f} pts ({r['lost']} lost, {r['gained']} gained) | {guide_verdict(r)} |")
    return "\n".join(lines)


def guide_verdict(r: dict) -> str:
    """Paired, at the plain marker's far end: unsafe when no range, no read
    nearer than 0.3 m, or 10+ points fewer reads; costs range when 3+ points fewer and the losses
    clearly outnumber the gains (lost - gained >= 3); else safe (no cost
    this run can see: the +/- says how small a cost could hide)."""
    if r["far"] is None or r["d_rate"] <= -0.10:
        return "unsafe"
    if r["near"] is not None and r["near"] > 300.0:
        return "unsafe"            # it stops reading up close (a big label's letters resolve)
    if r["d_rate"] <= -0.03 and r["lost"] - r["gained"] >= 3:
        return "costs range"
    return "safe"


def fmt_m(mm) -> str:
    if mm is None:
        return "—"
    return f"{mm / 1000.0:.2f} m" if mm >= 1000.0 else f"{mm:.0f} mm"


# ------------------------------------------------------------------ extras (cached, added lazily)

def ensure_extras(data: dict, workers: int = 10) -> bool:
    """Keys added after the first compute: computed only when missing."""
    changed = False
    dc = cam_of(DEFAULT_CAMERA)
    DOCS["after"] = doc(float(data["fix_mm"]), 0.0)
    if data.get("rungs") != RUNGS:
        jobs = [("ladder", dk, f["key"], f["req"], dc) for dk, feats in DOCS.items() for f in feats]
        with ProcessPoolExecutor(workers) as ex:
            for kind, dkey, fkey, ck, res in ex.map(_feature_job, jobs):
                data["ladder"].setdefault(dkey, {}).setdefault(fkey, {})[ck] = res
        data["rungs"] = RUNGS
        lad = data["ladder"]["before"]["A"][DEFAULT_CAMERA]["rungs"]
        rung = next((x for x in lad if x["d"] == 700.0), lad[3])
        k = (rung["worst"] or {"case": 0})["case"]
        data["shots"]["A_label_1m"] = shot(DOCS["before"][0]["req"], dc, rung["d"], draws()[k])
        data["shots"]["A_fixed_1m"] = shot(DOCS["label"][0]["req"], dc, rung["d"], draws()[k])
        changed = True
    if data.get("break_v") != 2:
        jobs = [("break", dk, f["key"], f["req"], dc) for dk, feats in DOCS.items() for f in feats]
        with ProcessPoolExecutor(workers) as ex:
            for kind, dkey, fkey, ck, res in ex.map(_feature_job, jobs):
                data["break"].setdefault(dkey, {}).setdefault(fkey, {})[ck] = res
        for key, dk in (("A", "before"), ("B", "before"), ("B", "after")):
            br = data["break"][dk][key][DEFAULT_CAMERA]
            if br["shrunk"]:
                c = br["shrunk"]["case"]
                v = {x: c[x] for x in ("tilt_deg", "yaw_deg", "blur_px", "noise", "glare", "occlusion", "seed")}
                data["shots"][f"break_{key}_{dk}"] = shot(DOCS[dk]["ABCD".index(key)]["req"], dc, c["dist"], v)
        data["break_v"] = 2
        changed = True
    if data.get("guide_v") != 2:
        data["guide"] = placement_guide(dc, workers)
        data["guide_v"] = 2
        data["art_v"] = 0
        changed = True
    if data.get("shots_v") != 2:
        # V5's picture: a 45° camera that loses an id just past B's 45° reach
        r45 = data["reach"]["before"]["B"][DEFAULT_CAMERA]["reach"][-1]["far"] or 1000.0
        cs = draws(48, tilt=45.0, seed=DRAW_SEED + 45)
        cx = Ctx(DOCS["before"][1]["req"], dc)
        k45 = next((k for k, v in enumerate(cs) if not cx.view(r45 * 1.12, v)["ok"]), 0)
        data["shots"]["B_45deg"] = shot(DOCS["before"][1]["req"], dc, r45 * 1.12, cs[k45])
        data["shots_v"] = 2
        changed = True
    if "dirt" not in data:
        # the dirt model: board B at 0.5 m, a kind camera, a little dirt
        cx = Ctx(DOCS["before"][1]["req"], dc)
        out = {}
        for occ in (0.0, 0.005, 0.02):
            oks = [cx.view(500.0, {"tilt_deg": 0.0, "yaw_deg": 0.0, "blur_px": 0.5, "noise": 0.03, "glare": 0.0,
                                   "occlusion": occ, "seed": k})["ok"] for k in range(40)]
            out[str(occ)] = round(sum(oks) / len(oks), 3)
        data["dirt"] = out
        changed = True
    if data.get("art_v") != 2:
        for dk, feats in DOCS.items():
            for f, rec in zip(feats, data["docs"][dk]):
                rec["art"] = art(f["req"])
        for (n_, l_, m_), row in zip(GUIDE, data["guide"]):
            row["art"] = art(req(1, 7, 30.0, l_, m_, single=True))
        data["art_v"] = 2
        changed = True
    if "calc" not in data:
        # Zach's screenshot: the calculator's camera (1920 px, 70°, 16:9) on board B
        cam70 = {"key": "calc", "resolution": [1920, 1080], "hfov_deg": 70.0}
        B = DOCS["before"][1]["req"]
        data["calc"] = {"readable": V.readable(B, dict(cam70, distance_mm=1500.0)),
                        "range": reading_range(B, cam70)}
        changed = True
    if "clean" not in data:
        # one-engine speed, single process, no other job running from here
        out = {}
        for name, fn in (("range", reading_range), ("ladder", ladder), ("smoke", smoke),
                         ("break", break_it), ("reach", reach)):
            t = time.perf_counter()
            n = sum(fn(f["req"], dc)["renders"] for f in DOCS["before"])
            out[name] = {"renders": n, "s": round(time.perf_counter() - t, 2)}
        data["clean"] = out
        changed = True
    return changed


# Pyodide's speed, measured 2026-10-21 on the running Stable build (127.0.0.1:5382) by a
# temporary Playwright script (window.__arucoVerify.readable on the plate's single
# 37 mm DICT_4X4_50 marker, 1920 px / 70°, OpenCV warm), against CPython's readable
# on the same marker in this process: see pyodide_ratio().
PYODIDE = {"readable_ms": [301, 303, 300], "sweep_18_ms": 3432, "first_image_ms": 846,
           "core_ready_ms": 1850, "readable_cold_ms": 1359,
           "note": "2026-10-21 11:18, load avg 7.9; a first run at load avg ~30 took 468-788 ms"}


def pyodide_ratio(data: dict) -> dict:
    """Browser ms per render: the browser's readable time over the renders
    CPython's readable makes on the same marker and camera."""
    if "ratio" in data:
        return data["ratio"]
    r = req(1, 0, 37.0, {"on": False}, single=True)
    r["rect"] = {"cx": 0.0, "cy": 0.0, "w": 49.33, "h": 49.33, "angle_deg": 0.0}
    n = [0]
    orig = V._view

    def counted(*a, **k):
        n[0] += 1
        return orig(*a, **k)
    V._view = counted
    ts = []
    try:
        for d in (1000.0, 2000.0, 1500.0):
            n[0] = 0
            t = time.perf_counter()
            res = V.readable(r, {"distance_mm": d, "resolution": [1920, 1080], "hfov_deg": 70.0})
            ts.append((time.perf_counter() - t) * 1000.0)
    finally:
        V._view = orig
    renders = n[0]
    b = float(np.median(PYODIDE["readable_ms"]))
    data["ratio"] = {"renders": renders, "cpython_ms": round(float(np.median(ts)), 1),
                     "browser_ms": b, "limit_mm": res["max_distance_mm"],
                     "ms_per_render": round(b / renders, 2),
                     "x": round(b / float(np.median(ts)), 2)}
    return data["ratio"]


# ------------------------------------------------------------------ the page

def pm_txt(pm) -> str:
    return "" if pm is None else f" <small>± {pm * 100:.0f} %</small>"


def pct(x) -> str:
    return "—" if x is None else f"{x * 100:+.0f} %"


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def m(mm, digits=2) -> str:
    if mm is None:
        return "—"
    return f"{mm / 1000.0:.{digits}f} m" if mm >= 1000.0 else f"{mm:.0f} mm"


LO, HI = 80.0, 8000.0
TICKS = [(100, "0.1"), (200, "0.2"), (500, "0.5"), (1000, "1"), (2000, "2"), (5000, "5 m")]


def ax(mm: float, w: float, pad: float = 8.0) -> float:
    mm = min(max(mm, LO), HI)
    return pad + (w - 2 * pad) * math.log(mm / LO) / math.log(HI / LO)


def band_svg(near, far, w=196, req=None, tone="ok", ticks=True, cls="", marks=(), fz=None) -> str:
    """One board's reading band on the shared log axis (0.08-8 m)."""
    h = 40 if ticks else 22
    s = [f'<svg class="as-band {cls}" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" '
         f'aria-label="reads {esc(m(near))} to {esc(m(far))}">']
    if req:
        x0, x1 = ax(req[0], w), ax(req[1], w)
        s.append(f'<rect class="req" x="{x0:.1f}" y="3" width="{x1 - x0:.1f}" height="16" rx="2"/>')
    s.append(f'<line class="axl" x1="8" x2="{w - 8}" y1="11" y2="11"/>')
    if far and fz:
        s.append(f'<line class="fz {tone}" x1="{ax(fz[0], w):.1f}" x2="{ax(fz[1], w):.1f}" y1="11" y2="11"/>')
    if far:
        x0, x1 = ax(near or LO, w), ax(far, w)
        s.append(f'<line class="bd {tone}" x1="{x0:.1f}" x2="{x1:.1f}" y1="11" y2="11"/>')
        s.append(f'<circle class="cap {tone}" cx="{x0:.1f}" cy="11" r="3.2"/>'
                 f'<circle class="cap {tone}" cx="{x1:.1f}" cy="11" r="3.2"/>')
    for mm_, lab, kind in marks:
        x = ax(mm_, w)
        s.append(f'<line class="mk {kind}" x1="{x:.1f}" x2="{x:.1f}" y1="2" y2="20"/>')
    if ticks:
        for t, lab in TICKS:
            x = ax(t, w)
            s.append(f'<line class="tk" x1="{x:.1f}" x2="{x:.1f}" y1="22" y2="25"/>'
                     f'<text class="tl" x="{x:.1f}" y="35" text-anchor="middle">{lab}</text>')
    s.append("</svg>")
    return "".join(s)


GLYPH = {
    "eye": '<svg width="14" height="14" viewBox="0 0 16 16"><path d="M1.5 8s2.4-4.5 6.5-4.5S14.5 8 14.5 8 12.1 12.5 8 12.5 1.5 8 1.5 8z" fill="none" stroke="currentColor" stroke-width="1.2"/><circle cx="8" cy="8" r="2.2" fill="currentColor"/></svg>',
    "cam": '<svg width="14" height="14" viewBox="0 0 16 16"><rect x="1.5" y="4" width="13" height="9" rx="1.6" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M5.5 4l1-1.6h3L10.5 4" fill="none" stroke="currentColor" stroke-width="1.2"/><circle cx="8" cy="8.5" r="2.4" fill="none" stroke="currentColor" stroke-width="1.2"/></svg>',
    "x": '<svg width="12" height="12" viewBox="0 0 12 12"><path d="M2.5 2.5l7 7M9.5 2.5l-7 7" stroke="currentColor" stroke-width="1.3"/></svg>',
    "play": '<svg width="10" height="10" viewBox="0 0 10 10"><path d="M2 1.2v7.6L8.6 5z" fill="currentColor"/></svg>',
    "search": '<svg width="12" height="12" viewBox="0 0 12 12"><circle cx="5" cy="5" r="3.6" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M7.7 7.7l3 3" stroke="currentColor" stroke-width="1.3"/></svg>',
    "ok": '<svg width="12" height="12" viewBox="0 0 12 12"><circle cx="6" cy="6" r="5.4" fill="currentColor"/><path d="M3.4 6.2l1.8 1.8 3.4-3.6" fill="none" stroke="#fff" stroke-width="1.4"/></svg>',
    "bad": '<svg width="12" height="12" viewBox="0 0 12 12"><circle cx="6" cy="6" r="5.4" fill="currentColor"/><path d="M4 4l4 4M8 4l-4 4" stroke="#fff" stroke-width="1.4"/></svg>',
    "warn": '<svg width="12" height="12" viewBox="0 0 12 12"><path d="M6 .9l5.3 9.6H.7z" fill="currentColor"/><path d="M6 4.4v3M6 8.6v.4" stroke="#fff" stroke-width="1.3"/></svg>',
    "spin": '<svg class="as-spin" width="12" height="12" viewBox="0 0 12 12"><circle cx="6" cy="6" r="4.6" fill="none" stroke="currentColor" stroke-opacity=".25" stroke-width="1.6"/><path d="M6 1.4a4.6 4.6 0 0 1 4.6 4.6" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>',
}


def st(states: str, body: str, tag: str = "div", cls: str = "", d: str = "block", extra: str = "") -> str:
    """An element shown only in these story states."""
    sts = " ".join(f"st-{x}" for x in states.split())
    return f'<{tag} class="st {sts} {cls}" style="--d:{d}" {extra}>{body}</{tag}>'


def chrome(title: str, body: str, w: int = 940, h: int = 572, dim: bool = True) -> str:
    """The Studio window: the canvas, the top-right pill (context, dimmed
    behind the modal), the dialog."""
    return (f'<div class="as"><div class="as-win">'
            f'<div class="as-docpill">ArUco Studio <b>·</b> robot-cell markers</div>'
            f'<div class="as-pill"><span>Download for CAD ⌄</span><span>{GLYPH["eye"]} Verify</span>'
            f'<span class="pri">Print</span></div>'
            + ('<div class="as-dim"></div>' if dim else "")
            + f'<div class="as-dlg" style="width:{w}px;height:{h}px">'
            f'<div class="as-dlg-t">{GLYPH["eye"]}<span>{title}</span><i class="as-x">{GLYPH["x"]}</i></div>'
            f'{body}</div></div></div>')


def cam_chip(data: dict, key: str = DEFAULT_CAMERA, to: str | None = None, label: str = "") -> str:
    c = data["cameras"][key]
    attr = f' data-story-to="{to}"' if to else ""
    tag = "button" if to else "span"
    return (f'<{tag} class="as-chip cam"{attr}>{GLYPH["cam"]}<b>{esc(c["name"])}</b>'
            f'<span>{esc(c["stream"])} · {c["hfov"]:g}°</span>{label}</{tag}>')


def budget_chip(data) -> str:
    b = data["budget"]
    return (f'<span class="as-chip">Field: tilt ≤ {b["tilt_max"]:g}° · blur ≤ {b["blur"][1]:g} px · '
            f'grain ≤ {b["grain"][1]:g} · glare ≤ {b["glare"][1]:g}</span>')


def req_chip(data, on: bool = True) -> str:
    r = data["requirement"]
    if not on:
        return '<span class="as-chip ghost">Requirement: none (optional)</span>'
    return f'<span class="as-chip req">Requirement: {m(r[0])} – {m(r[1])} · all 4 boards</span>'


def rng(data, dk, f, cam=DEFAULT_CAMERA):
    return data["range"][dk][f][cam]


def tone_of(r, req=None, warned=False):
    if not r["far"]:
        return "bad"
    if warned and not req:
        return "warn"
    if req and (r["far"] < req[1] or (r["near"] or 0) > req[0]):
        return "bad"
    return "ok"


def img(sh: dict, cls: str = "", w: int | None = None) -> str:
    # WHY a style, not width=: the gallery shell sets .prototype img {width: auto}
    ww = f' style="width:{w}px;height:auto"' if w else ""
    return f'<img class="as-img {cls}" src="{sh["src"]}"{ww} alt="the simulated camera view at {sh["d"]} mm">'


def view_words(v: dict) -> str:
    th = math.hypot(v.get("tilt_deg", 0.0), v.get("yaw_deg", 0.0))
    return (f'{th:.0f}° off axis · blur {v.get("blur_px", 0):.2f} px · grain {v.get("noise", 0):.2f} · '
            f'glare {v.get("glare", 0):.2f}')


def renders_of(data, kind, dk="before"):
    return data["clean"][kind]["renders"]


def est(data, kind, share: float = 1.0) -> float:
    """Seconds in one Pyodide worker: this engine's CPython time on the 4
    boards (single process, data["clean"]) x the measured Pyodide factor."""
    return data["clean"][kind]["s"] * share * pyodide_ratio(data)["x"]


# ---- V1 Test suite

def v1(data) -> dict:
    req_ = data["requirement"]
    lad = {dk: {f: data["ladder"][dk][f][DEFAULT_CAMERA]["rungs"] for f in "ABCD"} for dk in ("before", "after")}
    feats = {dk: data["docs"][dk] for dk in ("before", "after")}

    def table(dk):
        rows = []
        n_pass = n_fail = 0
        for f in feats[dk]:
            cells = []
            for x in lad[dk][f["key"]]:
                inreq = req_[0] <= x["d"] <= req_[1]
                ok = x["pass"]
                if inreq:
                    n_pass += ok
                    n_fail += not ok
                cls = ("ok" if ok else "bad") + (" in" if inreq else " out")
                sel = ' sel' if (dk == "before" and f["key"] == "A" and x["d"] == 700.0) else ""
                cells.append(f'<td class="rg {cls}{sel}" title="{x["ok"]} of {x["n"]} cases read every id">'
                             f'{GLYPH["ok"] if ok else GLYPH["bad"]}<small>{x["ok"]}/{x["n"]}</small></td>')
            reads = [x["d"] for x in lad[dk][f["key"]] if x["pass"]]
            rr = f'{m(min(reads))} – {m(max(reads))}' if reads else "none"
            rows.append(f'<tr><th><b>{esc(f["name"])}</b><small>{f["marker_mm"]:g} mm · reads {rr}</small></th>{"".join(cells)}</tr>')
        head = "".join(f'<td class="rh{" in" if req_[0] <= x <= req_[1] else ""}">{m(x, 1)}</td>' for x in data["rungs"])
        return (f'<table class="v1t"><thead><tr><th></th>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table>',
                n_pass, n_fail)

    tb, pb, fb = table("before")
    ta, pa, fa = table("after")
    sh = data["shots"]["A_label_1m"]
    shf = data["shots"]["A_fixed_1m"]
    a7 = next(x for x in lad["before"]["A"] if x["d"] == 700.0)
    b20 = next(x for x in lad["before"]["B"] if x["d"] == 2000.0)
    fix = data["fix_mm"]
    rb = renders_of(data, "ladder")
    est_b = est(data, "ladder")
    warn = feats["before"][0]["warnings"][0]
    head = (f'<div class="v1-head">{cam_chip(data)}{req_chip(data)}{budget_chip(data)}'
            f'<button class="as-btn pri st st-idle" style="--d:inline-flex" data-story-to="run">{GLYPH["play"]} Run {len(feats["before"]) * 6} tests</button>'
            f'<button class="as-btn st st-run st-fixed st-print" style="--d:inline-flex" data-story-to="idle">Edit fixtures</button></div>')
    idle = st("idle", f'''<div class="v1-idle">
        <div class="as-h">What Run checks</div>
        <p>One test per board × distance rung inside the requirement: <b>every id reads in ≥ {data["need"]} of {data["n"]}</b> seeded
        cameras drawn from the Field budget. Rungs outside the requirement run too and only inform the range.</p>
        <pre class="as-code">test_reads[Grid 3×1 #16–18 @ 0.30 m]
test_reads[Grid 3×1 #16–18 @ 0.45 m]
…
test_reads[Grid 2×1 #25–26 @ 2.00 m]      # {len(feats["before"]) * 6} tests · {rb} renders</pre>
        <p class="muted">The same file runs before Print and from a script: <code>verify --tests doc.arucostudio</code>.</p></div>''')
    run = st("run", f'''<div class="v1-body">{tb}
        <div class="v1-fail">
          <div class="as-h bad">FAIL · test_reads[Grid 3×1 #16–18 @ 0.70 m]</div>
          <div class="v1-assert">AssertionError: every id in ≥ {data["need"]} of {data["n"]} cases · #17 read in {a7["per_id"].get("17", a7["per_id"].get(17, "?")) if isinstance(a7["per_id"], dict) else "?"} (stopped after {a7["n"]})</div>
          <div class="v1-shot">{img(sh, w=300)}<div><b>Why</b><p>The label is 5.0 mm in #17's border row, which holds 2.5 mm. The lint already said
          <i>“{esc(warn[:70])}…”</i>; the test measures it.</p>
          <button class="as-btn pri" data-story-to="fixed">Label height: Auto</button></div></div>
          <div class="as-h bad" style="margin-top:10px">FAIL · test_reads[Grid 3×1 #19–21 @ 2.00 m] <span class="muted">(+ C, D)</span></div>
          <div class="v1-assert">AssertionError: {b20["ok"]} of {b20["n"]} read · 30 mm boards read to {m(rng(data, "before", "B")["far"])} under Field</div>
          <p>Smallest size that passes every rung to 2.0 m, re-run: <b>{fix} mm</b>.
          <button class="as-btn" data-story-to="fixed">Make all 4 boards {fix} mm</button></p>
          <p class="muted">Open on the bench: the failing case loads into Tilt / Blur / Glare.</p>
        </div></div>''', d="flex")
    fixed = st("fixed", f'''<div class="v1-body">{ta}<div class="v1-fail">
          <div class="as-h ok">{GLYPH["ok"]} All {pa} tests in the requirement pass</div>
          <p>Label Auto on #16–18 and every board {fix} mm. Re-run on the same {data["n"]} seeded cameras per rung.</p>
          <div class="v1-shot">{img(shf, w=300)}<div><b>#17 at 0.70 m</b><p>The same camera that lost it now reads all three.</p></div></div>
          <button class="as-btn" data-story-to="print">Print…</button></div></div>''', d="flex")
    printst = st("print", f'''<div class="v1-print"><div class="as-h">Print · runs the tests first, like CI</div>
        <div class="v1-gate bad">{GLYPH["bad"]}<div><b>{fb} of {pb + fb} tests fail.</b> Grid 3×1 #16–18 loses #17 from {m(next((x["d"] for x in lad["before"]["A"] if not x["pass"]), None))}; the 30 mm boards stop at
        {m(rng(data, "before", "B")["far"])}.<br><span class="muted">Print anyway writes the failing tests onto the sheet's footer.</span></div></div>
        <div class="v1-gate ok">{GLYPH["ok"]}<div><b>After the fixes: {pa} of {pa} pass.</b> The sheet's footer reads
        “Verified: D435 colour, 0.3–2.0 m, Field budget, {data["n"]} cases / rung”.</div></div>
        <button class="as-btn" data-story-to="fixed">Back to the results</button></div>''')
    foot = (f'<div class="as-foot"><span class="st st-run" style="--d:inline">{pb} passed · <b class="bad">{fb} failed</b></span>'
            f'<span class="st st-fixed st-print" style="--d:inline">{pa} passed · 0 failed</span>'
            f'<span class="st st-idle" style="--d:inline">Not run yet</span>'
            f'<span class="muted">{rb} renders · ≈ {est_b:.0f} s in the browser (measured renders × Pyodide speed)</span></div>')
    preview = chrome("Verify · tests", head + '<div class="as-dlg-b col">' + idle + run + fixed + printst + "</div>" + foot)
    text = ["$ verify --tests robot-cell.arucostudio --camera d435",
            "collected 24 tests (4 boards × 6 rungs in 0.30–2.00 m)", ""]
    for f in feats["before"]:
        line = "".join("." if x["pass"] else "F" for x in lad["before"][f["key"]] if req_[0] <= x["d"] <= req_[1])
        text.append(f'{f["name"]:<18} {line}')
    text += ["", f"FAILED test_reads[Grid 3×1 #16–18 @ 0.70 m] - #17 read in fewer than {data['need']} of {data['n']}",
             f"FAILED test_reads[Grid 3×1 #19–21 @ 2.00 m] - {b20['ok']} of {b20['n']} read every id",
             f"== {fb} failed, {pb} passed · {rb} renders =="]
    media = [{"label": "The same run from a script",
              "caption": "What V1 prints in a terminal or CI: the dots are the real rung results on the D435, and the guide could run the same file.",
              "html": f'<pre class="as-term">{esc(chr(10).join(text))}</pre>'}]
    a_fail = next((x["d"] for x in lad["before"]["A"] if not x["pass"]), None)
    b_fail = next((x["d"] for x in lad["before"]["B"] if not x["pass"]), None)
    steps = [
        {"label": "Fixtures", "caption": "A camera from the library, an optional requirement and the Field budget are the test's fixtures; Run lists what it will check.", "state": "idle", "target": ".v1-head [data-story-to=\"run\"]"},
        {"label": "Run", "caption": f"Every board × rung: green reads in ≥ {data['need']}/{data['n']} cases. #16–18 fails from {m(a_fail)} (its label); the 30 mm boards fail from {m(b_fail)}.", "state": "run", "target": ".st-run .v1-fail"},
        {"label": "Fix and re-run", "caption": f"Label Auto and {fix} mm, re-run on the same seeded cameras: all {pa} tests pass.", "state": "fixed", "target": ".st-fixed [data-story-to=\"print\"]"},
        {"label": "Print gates", "caption": "Print runs the suite first and puts the result on the sheet's footer, like CI before a release.", "state": "print", "target": ".st-print .v1-gate"},
    ]
    return {"preview": preview, "media": media, "steps": steps, "renders": rb, "est": est_b,
            "pass": pb, "fail": fb}


# ---- V2 Live badges

def v2(data) -> dict:
    req_ = data["requirement"]
    feats = data["docs"]["before"]
    after = data["docs"]["after"]
    sm = {f: data["smoke"]["before"][f][DEFAULT_CAMERA] for f in "ABCD"}
    rb = renders_of(data, "smoke")
    est_one = est(data, "smoke", 0.25)
    est_conf = est(data, "range", 0.25)
    pos = [(50, 150), (530, 150), (50, 370), (530, 370)]
    scale = 2.3  # canvas px per mm

    def boards(dk, state_tone):
        out = []
        for (x, y), f in zip(pos, data["docs"][dk]):
            r = rng(data, dk, f["key"])
            tone = tone_of(r, req_) if state_tone else "pend"
            w = f["outer_mm"][0] * scale * (0.75 if dk == "after" else 1.0)
            label = (f'{GLYPH["spin"]} measuring…' if tone == "pend" else
                     f'{GLYPH["ok"] if tone == "ok" else GLYPH["bad"]} {m(r["near"], 2)} – {m(r["far"])}')
            to = ' data-story-to="why"' if (f["key"] == "A" and dk == "before" and state_tone) else ""
            tag = "button" if to else "span"
            out.append(f'<div class="v2-board" style="left:{x}px;top:{y}px">'
                       f'<img src="{f["art"]["src"]}" style="width:{w:.0f}px;height:auto" alt="{esc(f["name"])} as printed">'
                       f'<{tag} class="v2-badge {tone}"{to}>{label}</{tag}>'
                       f'<small>{esc(f["name"])} · {f["marker_mm"]:g} mm</small></div>')
        return "".join(out)

    A = rng(data, "before", "A")
    Al = rng(data, "label", "A")
    sh = data["shots"]["A_label_1m"]
    warn = feats[0]["warnings"][0]
    top = (f'<div class="v2-top">{cam_chip(data)}<span class="as-chip req">Needs {m(req_[0])} – {m(req_[1])}</span>'
           f'<span class="st st-edit" style="--d:inline-flex"><span class="as-chip">{GLYPH["spin"]} re-measuring 4 boards…</span></span>'
           f'<span class="st st-badges st-why" style="--d:inline-flex"><span class="as-chip badc">{GLYPH["bad"]} {sum(tone_of(rng(data, "before", f), req_) == "bad" for f in "ABCD")} of 4 boards miss the requirement</span></span>'
           f'<span class="st st-fixed" style="--d:inline-flex"><span class="as-chip okc">{GLYPH["ok"]} 4 of 4 read {m(req_[0])} – {m(req_[1])}</span></span></div>')
    pop = st("why", f'''<div class="v2-pop"><div class="as-h bad">{GLYPH["bad"]} Grid 3×1 #16–18 reads only to {m(A["far"])}</div>
        <p><b>#17 drops out.</b> Its label is 5.0 mm tall in a border row that holds 2.5 mm; the lint said
        <i>“{esc(warn[:58])}…”</i>, and the badge measured it.</p>
        <div class="v2-popimg">{img(sh, w=200)}<small>{esc(view_words(sh["view"]))} at {m(sh["d"])}: #17 outlined red, not found</small></div>
        <div class="v2-fixes"><button class="as-btn pri" data-story-to="fixed">Label height: Auto → reads to {m(Al["far"])}</button>
        <span class="muted">then {data["fix_mm"]} mm for 2.0 m · Open on the bench</span></div></div>''')
    canvas = (st("edit", boards("before", False)) + st("badges why", boards("before", True)) + st("fixed", boards("after", True)))
    preview = (f'<div class="as"><div class="as-win">'
               f'<div class="as-docpill">ArUco Studio <b>·</b> robot-cell markers</div>'
               f'<div class="as-pill"><span>Download for CAD ⌄</span><span>{GLYPH["eye"]} Verify</span><span class="pri">Print</span></div>'
               f'{top}{canvas}{pop}'
               f'<div class="v2-legend">Badge = the range under the Field budget on the camera above · hollow while 12 cases are in, solid once 24 confirm</div>'
               f'</div></div>')
    media = [{"label": "Badge close-ups (real numbers)",
              "caption": f"The 12-case badge (provisional) next to the 24-case range that confirms it in idle time; they disagree by up to {max(abs((sm[f]['far'] or 0) - (rng(data, 'before', f)['far'] or 0)) for f in 'ABCD') / 10:.0f} cm here.",
              "html": '<table class="as-mini"><tr><th>Board</th><th>12 cases (badge first)</th><th>24 cases (confirmed)</th></tr>' + "".join(
                  f'<tr><td>{esc(f["name"])}</td><td>to {m(sm[f["key"]]["far"])}</td><td>to {m(rng(data, "before", f["key"])["far"])}</td></tr>' for f in feats) + "</table>"}]
    steps = [
        {"label": "Edit a board", "caption": f"Every edit re-measures in the background: the badge spins for ≈ {est_one:.1f} s (12 cases), no click.", "state": "edit", "target": ".st-edit .as-chip"},
        {"label": "Badges land", "caption": "Each board carries its near–far range; red where it misses the requirement band.", "state": "badges", "target": ".st-badges .v2-badge.bad"},
        {"label": "Why + fix", "caption": "Click the red badge: the id that drops, the cause, a re-verified fix, and the bench.", "state": "why", "target": ".v2-pop"},
        {"label": "Fixed", "caption": f"Label Auto, then {data['fix_mm']} mm: all four badges green across 0.3–2.0 m.", "state": "fixed", "target": ".st-fixed .v2-board"},
    ]
    return {"preview": preview, "media": media, "steps": steps, "renders": rb, "est": est_one,
            "est_one": est_one, "est_conf": est_conf}


# ---- V3 Break it

def v3(data) -> dict:
    br = {dk: {f: data["break"][dk][f][DEFAULT_CAMERA] for f in "ABCD"} for dk in ("before", "after")}
    rb = renders_of(data, "break")
    sA = data["shots"].get("break_A_before")
    sB = data["shots"].get("break_B_before")
    sBa = data["shots"].get("break_B_after")

    def case_line(b):
        if not b or not b.get("shrunk"):
            return "no counterexample"
        c = b["shrunk"]["case"]
        need = [k for k in ("tilt", "blur_px", "noise", "glare") if k not in b["shrunk"]["relaxed"]]
        names = {"tilt": "tilt", "blur_px": "blur", "noise": "grain", "glare": "glare"}
        return (f'{m(c["dist"])} · {view_words(c)} · needs: distance'
                + ("".join(f", {names[k]}" for k in need)))

    def card(b, f, sh, dk):
        holds = b["holds_to"]
        r95 = rng(data, dk, f["key"])
        return (f'<div class="v3-card"><div class="v3-left">{img(sh, w=300) if sh else ""}'
                f'<small>the smallest camera that breaks it</small></div><div class="v3-right">'
                f'<div class="as-h">{esc(f["name"])} · {f["marker_mm"]:g} mm</div>'
                f'<div class="v3-big bad">Holds to {m(holds) if holds else "—"}</div>'
                + "".join(f'<div class="v3-verdict {"ok" if (holds or 0) >= hi_ else "bad"}">{GLYPH["ok"] if (holds or 0) >= hi_ else GLYPH["bad"]} '
                          f'{"PASS" if (holds or 0) >= hi_ else "FAIL"} against {m(data["requirement"][0])} – {m(hi_)}</div>'
                          for hi_ in (1200.0, data["requirement"][1]))
                + f'<p>Broken at {m(b["breaks_at"])} by attack #{b["attack"]}. Shrunk toward the kindest camera, it still breaks at:</p>'
                f'<div class="v3-case">{esc(case_line(b))}</div>'
                f'<p class="muted">For scale: the ≥ 95 % range on the same budget is {m(r95["near"])} – {m(r95["far"])}. '
                f'One miss in 48 attacks fails the hunt, so its edge sits where the first unlucky pixel grid lands.</p>'
                f'</div></div>')

    fA, fB = data["docs"]["before"][0], data["docs"]["before"][1]
    fBa = data["docs"]["after"][1]
    log = st("hunt", f'''<div class="v3-hunt"><div class="as-h">Attack log · Grid 3×1 #19–21</div><ol class="v3-log">
        <li class="ok">8 corner attacks at 0.30 m (tilt 45° on four sides, blur 1.5, grain 0.2, glare 0 / 0.5): held</li>
        <li class="ok">+ 40 random cameras, outward from 0.30 m in ×1.4 steps, then bisected: held to {m(br["before"]["B"]["holds_to"])} (48 / 48)</li>
        <li class="bad">{m(br["before"]["B"]["breaks_at"])}: attack #{br["before"]["B"]["attack"]} loses an id</li>
        <li>shrinking: distance in, then tilt, blur, grain, glare toward kind, keeping it broken</li></ol>
        <button class="as-btn pri" data-story-to="brokenB">Show the counterexample</button></div>''')
    body = (log + st("brokenA", card(br["before"]["A"], fA, sA, "before"))
            + st("brokenB", card(br["before"]["B"], fB, sB, "before"))
            + st("after", card(br["after"]["B"], fBa, sBa, "after")))
    tabs = ('<div class="v3-tabs"><button class="as-tab" data-story-to="hunt">Hunt</button>'
            '<button class="as-tab" data-story-to="brokenA">#16–18</button>'
            '<button class="as-tab" data-story-to="brokenB">#19–21</button>'
            f'<button class="as-tab" data-story-to="after">#19–21 at {data["fix_mm"]} mm</button></div>')
    head = f'<div class="v1-head">{cam_chip(data)}{budget_chip(data)}<span class="as-chip">48 attacks per distance · one miss breaks it</span></div>'
    preview = chrome("Verify · try to break it", head + tabs + f'<div class="as-dlg-b col">{body}</div>'
                     + f'<div class="as-foot"><span class="muted">{rb} renders for 4 boards · ≈ {est(data, "break"):.0f} s in the browser</span></div>')
    rows = "".join(
        f'<tr><td>{esc(f["name"])}</td><td>{m(br["before"][f["key"]]["holds_to"]) if br["before"][f["key"]]["holds_to"] else "breaks at 0.30 m"}</td>'
        f'<td>{m(rng(data, "before", f["key"])["far"])}</td><td>{m(br["after"][f["key"]]["holds_to"])}</td><td>{m(rng(data, "after", f["key"])["far"])}</td></tr>'
        for f in data["docs"]["before"])
    media = [{"label": "Strict vs statistical, same cameras",
              "caption": "'Holds to' (no attack in 48 breaks it) against the ≥ 95 % range, before and after the fix: the hunt is roughly half as far and moves with pixel-grid luck.",
              "html": f'<table class="as-mini"><tr><th>Board</th><th>Holds to (30 mm)</th><th>95 % range</th><th>Holds to ({data["fix_mm"]} mm)</th><th>95 % range</th></tr>{rows}</table>'}]
    steps = [
        {"label": "Hunt", "caption": "Corner attacks first, then random cameras, outward until one loses an id.", "state": "hunt", "target": ".v3-log"},
        {"label": "#19–21 breaks", "caption": "The counterexample, shrunk: what is left is what breaks it. Every knob was needed here.", "state": "brokenB", "target": ".st-brokenB .v3-case"},
        {"label": "#16–18 breaks", "caption": "The typed label breaks it at the first distance tried.", "state": "brokenA", "target": ".st-brokenA .v3-case"},
        {"label": f"After {data['fix_mm']} mm", "caption": "Bigger boards hold farther, but the strict edge still sits well inside the 95 % range.", "state": "after", "target": ".st-after .v3-big"},
    ]
    return {"preview": preview, "media": media, "steps": steps, "renders": rb, "est": est(data, "break")}


# ---- V4 Range strip

def v4(data) -> dict:
    req_ = data["requirement"]
    fix = data["fix_mm"]
    cams = data["cameras"]
    rb = renders_of(data, "range")

    def strip(dk, cam, req=None, cls=""):
        cols = []
        for f in data["docs"][dk]:
            r = rng(data, dk, f["key"], cam)
            tone = tone_of(r, req, bool(f["warnings"]))
            note = ""
            if tone == "bad" and req:
                short = req[1] - (r["far"] or 0)
                note = f'<div class="v4-note bad">{GLYPH["bad"]} short by {m(short)}</div>'
            elif tone == "bad":
                note = f'<div class="v4-note bad">{GLYPH["bad"]} reads nowhere</div>'
            if f["key"] == "A" and dk == "before":
                note += f'<div class="v4-note warn">{GLYPH["warn"]} label 5 mm in a 2.5 mm row: #17 drops first</div>'
            w = max(40, f["outer_mm"][0] * (1.25 if dk != "after" else 0.95))
            cols.append(f'<div class="v4-col"><div class="v4-art"><img src="{f["art"]["src"]}" style="width:{w:.0f}px;height:auto" alt="{esc(f["name"])}"></div>'
                        f'<div class="v4-name"><b>{esc(f["name"])}</b> · {f["marker_mm"]:g} mm</div>'
                        f'{band_svg(r["near"], r["far"], 200, req, tone, fz=r.get("band"))}'
                        f'<div class="v4-num {tone}">{m(r["near"])} – <b>{m(r["far"])}</b> <small>± {(r.get("pm") or 0) * 100:.0f} %</small></div>{note}</div>')
        return f'<div class="v4-strip {cls}">{"".join(cols)}</div>'

    def rows_view(dk, cam):
        out = []
        for f in data["docs"][dk]:
            r = rng(data, dk, f["key"], cam)
            out.append(f'<div class="v4-row"><img src="{f["art"]["src"]}" style="width:64px;height:auto" alt=""><span>{esc(f["name"])}</span>'
                       f'{band_svg(r["near"], r["far"], 520, None, tone_of(r), ticks=False)}<b>{m(r["near"])} – {m(r["far"])}</b></div>')
        axis = band_svg(None, None, 520, None, "ok", ticks=True, cls="axonly")
        return f'<div class="v4-rows">{"".join(out)}<div class="v4-row axis"><span></span><span></span>{axis}<b></b></div></div>'

    # the library: one row per camera, with the document's shortest far end on it
    lib = []
    for k, c in cams.items():
        fars = [rng(data, "before", f, k)["far"] or 0 for f in "BCD"]
        to = ' data-story-to="oak"' if k == "oakd12" else (' data-story-to="range"' if k == DEFAULT_CAMERA else "")
        tag = "button" if to else "div"
        lib.append(f'<{tag} class="v4-lib-row{" on" if k == DEFAULT_CAMERA else ""}"{to}><b>{esc(c["name"])}</b>'
                   f'<span>{esc(c["stream"])}</span><span>{c["res"][0]}×{c["res"][1]}</span><span>{c["hfov"]:g}°</span>'
                   f'<span class="muted">{"".join(f"[{s}]" for s in c["src"])}</span><span class="ok">to {m(min(fars))}</span></{tag}>')
    library = st("library", f'''<div class="v4-lib"><div class="v4-search">{GLYPH["search"]}<span>Search cameras</span><i>13 presets · click to pick</i></div>
        <div class="v4-lib-head"><span>Camera</span><span>Stream</span><span>Pixels</span><span>HFOV</span><span>Source</span><span>30 mm boards</span></div>
        {"".join(lib)}<div class="muted v4-lib-foot">Sources are the makers' datasheets (numbered in the Source Index below the gallery). “30 mm boards” is this
        document's shortest far end on that camera, measured.</div></div>''')
    tl = f'''<div class="v4-top">{cam_chip(data, DEFAULT_CAMERA, "library", "<i>⌄</i>")}
        <span class="st st-range st-rows st-library" style="--d:inline-flex"><button class="as-chip ghost" data-story-to="need">+ Requirement (optional)</button></span>
        <span class="st st-need st-fixed" style="--d:inline-flex"><span class="as-chip req">Requirement {m(req_[0])} – {m(req_[1])} · all 4</span></span>
        {budget_chip(data)}
        <span class="v4-seg"><button data-story-to="range">Strip</button><button data-story-to="rows">Rows</button></span></div>'''
    oak = cams["oakd12"]
    body = (st("range", strip("before", DEFAULT_CAMERA) + f'''<div class="v4-edge"><div>{img(data["shots"]["B_at_far"], w=210)}<small>#19–21 at {m(data["shots"]["B_at_far"]["d"])}: reads</small></div>
              <div>{img(data["shots"]["B_beyond"], w=210)}<small>at {m(data["shots"]["B_beyond"]["d"])}: {", ".join("#" + str(i) for i in data["shots"]["B_beyond"]["missing"]) or "an id"} lost</small></div>
              <p>Each band runs to where every id reads in 95 % of the Field cameras (48 a distance, fitted; the pale end is its 90 % band). Hover an end to see that view; click it to open the bench there.</p></div>''')
            + st("rows", rows_view("before", DEFAULT_CAMERA))
            + library
            + st("oak", strip("before", "oakd12") + f'<p class="v4-cap">Same boards on the <b>{esc(oak["name"])} · {esc(oak["stream"])}</b>: more pixels across the same 69°, so every band reaches farther.</p>')
            + st("need", strip("before", DEFAULT_CAMERA, req_) + f'''<div class="v4-fix"><b class="bad">{sum(tone_of(rng(data, "before", f), req_) == "bad" for f in "ABCD")} of 4 boards miss {m(req_[0])} – {m(req_[1])}.</b>
                 <button class="as-btn" data-story-to="fixed">Label Auto on #16–18 + every board {fix} mm</button>
                 <span class="muted">{fix} mm is the smallest size whose band reaches {m(req_[1])}, measured (35 / 40 / 45 / 50 / 60 mm tried).</span></div>''')
            + st("fixed", strip("after", DEFAULT_CAMERA, req_) + f'<div class="v4-fix"><b class="ok">{GLYPH["ok"]} All 4 boards read {m(req_[0])} – {m(req_[1])}.</b> <span class="muted">Stored on each ArUco Extrude: the Fusion panel shows “Reads {m(rng(data, "after", "B")["near"])}–{m(rng(data, "after", "B")["far"])} · D435 colour · Field”.</span></div>'))
    preview = chrome("Verify · reading range", tl + f'<div class="as-dlg-b col v4">{body}</div>'
                     + f'<div class="as-foot"><span class="muted">{rb} renders for 4 boards · ≈ {est(data, "range"):.0f} s in the browser, in one Pyodide worker; cached per board + camera; 48 cases × 6+ distances, the 95 % crossing ± its 90 % band</span></div>')
    g = data["guide"]
    grow = "".join(
        f'<tr class="{guide_verdict(r).replace(" ", "-")}"><td><img src="{r["art"]["src"]}" style="width:60px;height:auto" alt=""></td><td>{esc(r["name"])}</td><td>{m(r["near"])}</td>'
        f'<td>{m(r["far"])}{pm_txt(r["pm"])}</td><td>{r["rate_at"] * 100:.0f} %</td>'
        f'<td>{r["d_rate"] * 100:+.0f} ± {r["d_ci"] * 100:.0f} pts <small>({r["lost"]} lost · {r["gained"]} gained)</small></td>'
        f'<td><b>{guide_verdict(r)}</b></td></tr>' for r in g)
    media = [
        {"label": "Label placement guide · the same engine, from a script",
         "caption": f"`docs/build_verify_test_proposals.py --guide` runs this engine on one 30 mm 4×4 single per placement in CPython, no browser: its range, then the same {GUIDE_PAIRED} cameras at the plain marker's far end ({m(g[0]['at'])}), paired. This table is its output. One gap before it goes public: this simulator prints crisp black ink, while the core's 2026-10-13 study lost ~11 points to grey ink and dot spread in the quiet zone, so the quiet-zone rows need that ink model first.",
         "html": f'<table class="as-mini guide"><tr><th></th><th>Placement</th><th>From</th><th>To (± 90 %)</th><th>Reads at {m(g[0]["at"])}</th><th>vs no label, paired</th><th>Verdict</th></tr>{grow}</table>'},
        {"label": "In the Fusion panel",
         "caption": "The range is a stored value on the feature, so the add-in shows it without OpenCV, greyed with “edited since” when a dimension changes.",
         "html": f'''<div class="as"><div class="v4-fusion"><div class="fz-h">ARUCO EXTRUDE</div>
           <div class="fz-row"><span>Marker</span><b>Grid 3×1 · {fix} mm</b></div>
           <div class="fz-row"><span>Reads</span><b class="ok">{m(rng(data, "after", "B")["near"])} – {m(rng(data, "after", "B")["far"])}</b></div>
           <div class="fz-row"><span></span><small>D435 colour · Field · verified in Studio</small></div>
           <div class="fz-row"><span>Was</span><b class="muted">{m(rng(data, "before", "B")["near"])} – {m(rng(data, "before", "B")["far"])} at 30 mm · edited since</b></div></div></div>'''},
    ]
    steps = [
        {"label": "The range", "caption": f"Pick a camera; every board shows the near–far it reads at, on one shared axis. #16–18 stops at {m(rng(data, 'before', 'A')['far'])}: its label.", "state": "range", "target": ".st-range .v4-strip"},
        {"label": "Camera library", "caption": "13 presets from the makers' datasheets; each row already shows how far this document's boards reach on it.", "state": "library", "target": ".v4-lib"},
        {"label": "Another camera", "caption": "One click: the OAK-D at 12 MP. Same 69°, 2× the pixels: the bands stretch.", "state": "oak", "target": ".st-oak .v4-strip"},
        {"label": "Requirement (optional)", "caption": "Batch-set 0.3–2.0 m: shaded on every axis; the misses say by how much and offer the measured fix.", "state": "need", "target": ".st-need .v4-fix .as-btn"},
        {"label": "Fixed", "caption": f"Label Auto + {fix} mm: every band covers the requirement.", "state": "fixed", "target": ".st-fixed .v4-strip"},
    ]
    return {"preview": preview, "media": media, "steps": steps, "renders": rb, "est": est(data, "range")}


# ---- V5 Reach fan

def v5(data) -> dict:
    req_ = data["requirement"]
    rb = renders_of(data, "reach")

    def fan(dk, req=None, w=560, h=330):
        cx, cy = 40, h - 30
        R = w - 80
        lo, hi = 100.0, 4000.0

        def rad(mm):
            mm = min(max(mm, lo), hi)
            return R * math.log(mm / lo) / math.log(hi / lo)

        def pt(mm, deg):
            a = math.radians(deg)
            r_ = rad(mm)
            return cx + r_ * math.cos(a), cy - r_ * math.sin(a)
        s = [f'<svg class="v5-fan" width="{w}" height="{h}" viewBox="0 0 {w} {h}">']
        for t in (100, 200, 500, 1000, 2000, 4000):
            r_ = rad(t)
            s.append(f'<path class="ring" d="M{cx + r_:.1f} {cy} A{r_:.1f} {r_:.1f} 0 0 0 {cx + r_ * math.cos(math.radians(50)):.1f} {cy - r_ * math.sin(math.radians(50)):.1f}"/>'
                     f'<text class="tl" x="{cx + r_:.1f}" y="{cy + 14}" text-anchor="middle">{m(t, 1)}</text>')
        for a in data["angles"]:
            x, y = pt(hi, a)
            s.append(f'<line class="ray" x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}"/><text class="tl" x="{x + 4:.1f}" y="{y:.1f}">{a:g}°</text>')
        if req:
            a0, a1 = 0, data["angles"][-1]
            p = [pt(req[0], a) for a in range(a0, int(a1) + 1, 3)] + [pt(req[1], a) for a in range(int(a1), a0 - 1, -3)]
            s.append('<path class="reqz" d="M' + " L".join(f"{x:.1f} {y:.1f}" for x, y in p) + 'Z"/>')
        colors = {"A": "#cf3b3b", "B": "#2a78d6", "C": "#1baf7a", "D": "#eb6834"}
        for f in "ABCD":
            rr = data["reach"][dk][f][DEFAULT_CAMERA]["reach"]
            p = [pt(x["far"] or lo, x["angle"]) for x in rr]
            s.append(f'<path class="reach" style="stroke:{colors[f]}" d="M{cx} {cy} L' + " L".join(f"{x:.1f} {y:.1f}" for x, y in p) + 'Z"/>')
            for (x, y), q in zip(p, rr):
                s.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" style="fill:{colors[f]}"/>')
        s.append(f'<g transform="translate({cx - 26},{cy - 12})"><rect width="22" height="16" rx="3" class="camb"/><circle cx="11" cy="8" r="4" class="camc"/></g>')
        s.append("</svg>")
        legend = "".join(
            f'<span><i style="background:{colors[f["key"]]}"></i>{esc(f["name"])}: '
            + " / ".join(m(x["far"], 1) for x in data["reach"][dk][f["key"]][DEFAULT_CAMERA]["reach"]) + "</span>"
            for f in data["docs"][dk])
        return "".join(s) + f'<div class="v5-leg">{legend}<small>far end at 0° / 15° / 30° / 45°</small></div>'

    sh = data["shots"]["B_45deg"]
    rB = data["reach"]["before"]["B"][DEFAULT_CAMERA]["reach"]
    side = st("fan need", f'''<div class="v5-side"><div class="as-h">Grid 3×1 #19–21</div>
        <p>Head on it reads to <b>{m(rB[0]["far"])}</b>; at 45° only <b>{m(rB[-1]["far"])}</b>. A 1-D range hides that the edge is a curve.</p>
        <div>{img(sh, w=200)}<small>45° at {m(sh["d"])}: {", ".join("#" + str(i) for i in sh["missing"]) or "reads"} {"lost" if sh["missing"] else ""}</small></div>
        <button class="as-btn" data-story-to="need">Overlay the requirement</button></div>''')
    ra = {f: data["reach"]["after"][f][DEFAULT_CAMERA]["reach"] for f in "ABCD"}
    short45 = [f for f in "ABCD" if (ra[f][-1]["far"] or 0) < req_[1]]
    covered = [a for a in data["angles"] if all((next(x for x in ra[f] if x["angle"] == a)["far"] or 0) >= req_[1] for f in "ABCD")]
    lo45 = min(ra[f][-1]["far"] or 0 for f in "ABCD")
    fixed_words = (f"Every board's fan covers {m(req_[0])} – {m(req_[1])} out to 45°." if not short45 else
                   f"The fans cover {m(req_[1])} out to {max(covered) if covered else 0:g}°; at 45° {len(short45)} of 4 boards stop at "
                   f"{m(lo45)}–{m(max(ra[f][-1]['far'] or 0 for f in short45))}. The strip, which averages tilt over the budget, called this a pass.")
    side2 = st("fixed", f'''<div class="v5-side"><div class="as-h {"ok" if not short45 else "bad"}">{GLYPH["ok"] if not short45 else GLYPH["warn"]} {data["fix_mm"]} mm, label Auto</div>
        <p>{fixed_words}</p></div>''')
    body = (st("fan", f'<div class="v5-main">{fan("before")}</div>', d="block")
            + st("need", f'<div class="v5-main">{fan("before", req_)}<div class="v5-fix"><b class="bad">The shaded zone (0.3–2.0 m, 0–45°) pokes past every fan.</b> <button class="as-btn pri" data-story-to="fixed">Label Auto + {data["fix_mm"]} mm</button></div></div>')
            + st("fixed", f'<div class="v5-main">{fan("after", req_)}</div>') + side + side2)
    head = f'<div class="v1-head">{cam_chip(data)}{budget_chip(data)}<span class="as-chip">reach at 0°, 15°, 30°, 45°</span></div>'
    preview = chrome("Verify · reach from the camera", head + f'<div class="as-dlg-b">{body}</div>'
                     + f'<div class="as-foot"><span class="muted">{rb} renders for 4 boards (4 angles each) · ≈ {est(data, "reach"):.0f} s in the browser</span></div>')
    rows = "".join(
        f'<tr><td>{esc(f["name"])}</td>' + "".join(f'<td>{m(x["far"])}</td>' for x in data["reach"]["before"][f["key"]][DEFAULT_CAMERA]["reach"]) + "</tr>"
        for f in data["docs"]["before"])
    media = [{"label": "Reach by angle (real)", "caption": "Far end of each board at each viewing angle, D435 colour, the other knobs drawn from the Field budget.",
              "html": f'<table class="as-mini"><tr><th>Board</th>{"".join(f"<th>{a:g}°</th>" for a in data["angles"])}</tr>{rows}</table>'}]
    steps = [
        {"label": "The fan", "caption": "Each board's reach drawn from the camera: far at head-on, shrinking with angle.", "state": "fan", "target": ".st-fan .v5-fan"},
        {"label": "Requirement", "caption": "The requirement becomes a zone (distance × angle); where it pokes past a fan is where it fails.", "state": "need", "target": ".st-need .v5-fix"},
        {"label": "After the fix", "caption": f"{data['fix_mm']} mm and label Auto. " + fixed_words, "state": "fixed", "target": ".st-fixed .v5-fan"},
    ]
    return {"preview": preview, "media": media, "steps": steps, "renders": rb, "est": est(data, "reach"), "short45": short45, "fixed_words": fixed_words}


CSS = r"""
.as{--bg:#f3f4f6;--panel:#fff;--panel-2:#f7f8fa;--line:#dadee4;--line-soft:#eceef2;--text:#1c222b;--muted:#6b7480;
 --accent:#2f6fed;--accent-soft:rgba(47,111,237,.12);--ok:#18865a;--warn:#a8650e;--bad:#cf3b3b;--canvas:#e9ecf0;
 --grid:rgba(25,35,50,.06);--grid-major:rgba(25,35,50,.13);--shadow:0 10px 32px rgba(17,24,39,.14),0 1px 3px rgba(17,24,39,.08);
 --f:Inter,"Segoe UI Variable Text","Segoe UI",system-ui,-apple-system,sans-serif;--mono:"Cascadia Mono",Consolas,ui-monospace,monospace;
 font:12px/1.42 var(--f);color:var(--text);text-align:left}
.prototype .st{display:none}
.as .muted{color:var(--muted)} .as .ok{color:var(--ok)} .as .bad{color:var(--bad)} .as .warn{color:var(--warn)}
.as p{margin:6px 0} .as small{font-size:10.5px;color:var(--muted)}
.as code,.as .as-code{font-family:var(--mono);font-size:11px}
.as-win{position:relative;width:1000px;height:640px;overflow:hidden;border-radius:8px;background-color:var(--canvas);
 background-image:linear-gradient(var(--grid-major) 1px,transparent 1px),linear-gradient(90deg,var(--grid-major) 1px,transparent 1px),linear-gradient(var(--grid) 1px,transparent 1px),linear-gradient(90deg,var(--grid) 1px,transparent 1px);
 background-size:50px 50px,50px 50px,10px 10px,10px 10px;box-shadow:inset 0 0 0 1px var(--line)}
.as-docpill{position:absolute;left:10px;top:10px;height:28px;display:flex;align-items:center;gap:6px;padding:0 12px;background:var(--panel);border:1px solid var(--line);border-radius:7px;font-weight:600}
.as-docpill b{color:var(--muted);font-weight:400}
.as-pill{position:absolute;right:10px;top:10px;display:flex;gap:6px}
.as-pill span{height:28px;display:inline-flex;align-items:center;gap:5px;padding:0 12px;border-radius:7px;background:var(--panel);border:1px solid var(--line);font-weight:500}
.as-pill .pri{background:var(--accent);border-color:var(--accent);color:#fff}
.as-dim{position:absolute;inset:0;background:rgba(17,24,39,.28)}
.as-dlg{position:absolute;left:50%;top:48px;transform:translateX(-50%);background:var(--panel);border-radius:8px;box-shadow:var(--shadow);display:flex;flex-direction:column;overflow:hidden}
.as-dlg-t{height:38px;flex:none;display:flex;align-items:center;gap:8px;padding:0 10px 0 14px;font-size:13px;font-weight:600;border-bottom:1px solid var(--line-soft)}
.as-dlg-t .as-x{margin-left:auto;color:var(--muted);display:flex}
.as-dlg-b{flex:1;min-height:0;display:flex;overflow:hidden;position:relative}
.as-dlg-b.col{flex-direction:column}
.as-foot{flex:none;display:flex;gap:14px;align-items:center;padding:7px 14px;border-top:1px solid var(--line-soft);background:var(--panel-2);font-size:11px}
.as-btn{height:24px;padding:0 10px;border-radius:5px;border:1px solid var(--line);background:var(--panel);font:inherit;font-weight:500;color:var(--text);cursor:pointer;display:inline-flex;align-items:center;gap:6px;white-space:nowrap}
.as-btn:hover{background:#f1f3f6}
.as-btn.pri{background:var(--accent);border-color:var(--accent);color:#fff}
.as-chip{height:24px;display:inline-flex;align-items:center;gap:6px;padding:0 9px;border-radius:12px;border:1px solid var(--line);background:var(--panel-2);font:inherit;font-size:11.5px;color:var(--text);white-space:nowrap}
button.as-chip{cursor:pointer} button.as-chip:hover{border-color:var(--accent)}
.as-chip.cam b{font-weight:600} .as-chip.cam span{color:var(--muted)} .as-chip.cam i{font-style:normal;color:var(--muted)}
.as-chip.req{background:rgba(47,111,237,.08);border-color:rgba(47,111,237,.35);color:#1d4fb8}
.as-chip.ghost{background:transparent;border-style:dashed;color:var(--muted)}
.as-chip.badc{color:var(--bad);border-color:rgba(207,59,59,.4);background:rgba(207,59,59,.06)}
.as-chip.okc{color:var(--ok);border-color:rgba(24,134,90,.4);background:rgba(24,134,90,.06)}
.as-h{font-size:10.5px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;display:flex;gap:6px;align-items:center}
.as-h.bad{color:var(--bad)} .as-h.ok{color:var(--ok)}
.as-img{border-radius:4px;background:#888;image-rendering:pixelated;display:block}
.as-spin{animation:asspin 1s linear infinite}
@keyframes asspin{to{transform:rotate(360deg)}}
.as-term{margin:0;padding:12px 14px;background:#14181e;color:#d6dde6;font:11.5px/1.5 var(--mono);white-space:pre;min-width:560px}
.as-mini{border-collapse:collapse;font:12px/1.4 Inter,system-ui,sans-serif;margin:10px;background:#fff}
.as-mini th,.as-mini td{border-bottom:1px solid #eceef2;padding:4px 10px;text-align:left;white-space:nowrap}
.as-mini th{font-size:10.5px;color:#6b7480;text-transform:uppercase;letter-spacing:.04em}
.as-mini.guide tr.unsafe td{color:#cf3b3b} .as-mini.guide tr.costs-range td b{color:#a8650e} .as-mini.guide tr.safe td b{color:#18865a}
.v1-head,.v2-top,.v4-top{display:flex;flex-wrap:wrap;gap:6px;align-items:center;padding:8px 12px;border-bottom:1px solid var(--line-soft)}
.v1-head .as-btn.pri{margin-left:auto}
.v1-idle{padding:16px 22px;max-width:640px}
.v1-idle pre{background:var(--panel-2);border:1px solid var(--line-soft);border-radius:6px;padding:10px 12px;margin:10px 0}
.v1-body{flex:1;min-height:0;display:flex;gap:14px;padding:12px}
.v1t{border-collapse:separate;border-spacing:0;font-size:11px;align-self:flex-start}
.v1t th{text-align:left;padding:6px 8px 6px 0;font-weight:400;white-space:nowrap}
.v1t th b{display:block;font-size:12px} .v1t th small{display:block}
.v1t td.rh{font-size:10px;color:var(--muted);text-align:center;padding:0 3px 4px}
.v1t td.rh.in{color:#1d4fb8;font-weight:600;background:rgba(47,111,237,.07)}
.v1t td.rg{width:38px;text-align:center;padding:6px 2px;border-top:1px solid var(--line-soft)}
.v1t td.rg.in{background:rgba(47,111,237,.05)}
.v1t td.rg.ok{color:var(--ok)} .v1t td.rg.bad{color:var(--bad)}
.v1t td.rg.out{opacity:.5}
.v1t td.rg small{display:block;font-size:9.5px}
.v1t td.rg.sel{outline:2px solid var(--bad);outline-offset:-2px;border-radius:4px}
.v1-fail{flex:1;min-width:300px;border-left:1px solid var(--line-soft);padding-left:14px;overflow:auto}
.v1-assert{font-family:var(--mono);font-size:11px;background:rgba(207,59,59,.06);border:1px solid rgba(207,59,59,.25);border-radius:5px;padding:6px 8px;margin:6px 0}
.v1-shot{display:flex;flex-direction:column;gap:6px;align-items:flex-start;margin:8px 0}
.v1-shot b{display:block}
.v1-print{padding:18px 22px;display:flex;flex-direction:column;gap:12px;max-width:700px}
.v1-gate{display:flex;gap:10px;align-items:flex-start;padding:10px 12px;border-radius:6px;border:1px solid var(--line)}
.v1-gate.bad{background:rgba(207,59,59,.05);border-color:rgba(207,59,59,.3);color:var(--bad)}
.v1-gate.ok{background:rgba(24,134,90,.05);border-color:rgba(24,134,90,.3);color:var(--ok)}
.v1-gate div{color:var(--text)}
.v2-top{position:absolute;left:10px;top:46px;border:0;padding:0}
.v2-board{position:absolute;display:flex;flex-direction:column;gap:4px}
.v2-board img{display:block;box-shadow:0 1px 3px rgba(0,0,0,.18)}
.v2-badge{position:absolute;right:-8px;top:-12px;height:22px;display:inline-flex;align-items:center;gap:5px;padding:0 9px;border-radius:11px;font:600 11px/1 var(--f);border:1.5px solid;background:#fff;cursor:default}
button.v2-badge{cursor:pointer}
.v2-badge.ok{color:var(--ok);border-color:var(--ok)} .v2-badge.bad{color:var(--bad);border-color:var(--bad)}
.v2-badge.pend{color:var(--muted);border-color:var(--line);border-style:dashed}
.v2-pop{position:absolute;left:470px;top:118px;width:470px;background:#fff;border-radius:8px;box-shadow:var(--shadow);padding:12px 14px;border:1px solid var(--line)}
.v2-popimg{display:flex;gap:10px;align-items:flex-end;margin:6px 0}
.v2-fixes{display:flex;flex-direction:column;gap:6px;align-items:flex-start}
.v2-legend{position:absolute;left:10px;bottom:10px;font-size:11px;color:var(--muted);background:rgba(255,255,255,.8);padding:3px 8px;border-radius:5px}
.v3-tabs{display:flex;gap:2px;padding:6px 12px 0;border-bottom:1px solid var(--line-soft)}
.as-tab{border:0;background:none;font:inherit;padding:6px 10px;border-bottom:2px solid transparent;cursor:pointer;color:var(--muted)}
.prototype[data-story-state="hunt"] .as-tab[data-story-to="hunt"],.prototype[data-story-state="brokenA"] .as-tab[data-story-to="brokenA"],
.prototype[data-story-state="brokenB"] .as-tab[data-story-to="brokenB"],.prototype[data-story-state="after"] .as-tab[data-story-to="after"]{color:var(--text);border-bottom-color:var(--accent);font-weight:600}
.v3-hunt{padding:14px 20px}
.v3-log{margin:8px 0 12px;padding-left:18px;font-family:var(--mono);font-size:11px;line-height:1.8}
.v3-log li.ok{color:var(--ok)} .v3-log li.bad{color:var(--bad);font-weight:600}
.v3-card{display:flex;gap:18px;padding:14px 18px}
.v3-left{flex:none;display:flex;flex-direction:column;gap:4px}
.v3-right{flex:1;min-width:0}
.v3-big{font-size:22px;font-weight:700;margin:4px 0}
.v3-verdict{display:flex;gap:6px;align-items:center;font-weight:600;margin:2px 0}
.v3-verdict.ok{color:var(--ok)} .v3-verdict.bad{color:var(--bad)}
.v3-case{font-family:var(--mono);font-size:11.5px;background:rgba(207,59,59,.06);border:1px solid rgba(207,59,59,.25);border-radius:5px;padding:8px 10px}
.v4{padding:10px 14px;overflow:auto}
.media-exhibit:has(.guide){grid-column:1/-1}
.v4-seg{margin-left:auto;display:inline-flex;border:1px solid var(--line);border-radius:6px;overflow:hidden}
.v4-seg button{border:0;background:var(--panel);font:inherit;padding:3px 10px;cursor:pointer}
.prototype[data-story-state="rows"] .v4-seg button[data-story-to="rows"],.prototype:not([data-story-state="rows"]) .v4-seg button[data-story-to="range"]{background:var(--accent-soft);color:#1d4fb8;font-weight:600}
.v4-strip{display:flex;gap:14px;align-items:flex-start}
.v4-col{width:212px;flex:none;display:flex;flex-direction:column;gap:4px}
.v4-art{height:84px;display:flex;align-items:flex-end}
.v4-art img{display:block;max-width:206px;box-shadow:0 1px 3px rgba(0,0,0,.2)}
.v4-name{font-size:11.5px}
.v4-num{font-size:12px} .v4-num.bad b{color:var(--bad)}
.v4-note{font-size:11px;display:flex;gap:5px;align-items:center}
.as-band .axl{stroke:var(--line);stroke-width:2}
.as-band .bd{stroke-width:6;stroke-linecap:round}
.as-band .fz{stroke-width:10;stroke-linecap:round;opacity:.22}
.as-band .fz.ok{stroke:var(--ok)} .as-band .fz.bad{stroke:var(--bad)}
.as-band .bd.ok,.as-band .cap.ok{stroke:var(--ok);fill:var(--ok)}
.as-band .bd.bad,.as-band .cap.bad{stroke:var(--bad);fill:var(--bad)}
.as-band .bd.warn,.as-band .cap.warn{stroke:var(--warn);fill:var(--warn)} .as-band .fz.warn{stroke:var(--warn)}
.v4-num.warn b{color:var(--warn)}
.as-band .cap{stroke:#fff;stroke-width:1.5}
.as-band .req{fill:rgba(47,111,237,.13);stroke:rgba(47,111,237,.45);stroke-dasharray:3 2}
.as-band .tk{stroke:var(--muted)} .as-band .tl{fill:var(--muted);font:10px var(--f)}
.v4-edge{display:flex;gap:12px;align-items:flex-end;margin-top:14px;padding-top:10px;border-top:1px solid var(--line-soft)}
.v4-edge>div{display:flex;flex-direction:column;gap:3px}
.v4-edge p{max-width:330px;color:var(--muted)}
.v4-rows{display:flex;flex-direction:column;gap:6px}
.v4-row{display:grid;grid-template-columns:70px 130px 520px 130px;align-items:center;gap:8px}
.v4-row img{box-shadow:0 1px 2px rgba(0,0,0,.2)}
.v4-lib{position:absolute;left:12px;top:6px;width:880px;background:#fff;border:1px solid var(--line);border-radius:8px;box-shadow:var(--shadow);padding:8px;z-index:3}
.v4-search{display:flex;gap:8px;align-items:center;height:30px;padding:0 10px;border:1px solid var(--accent);border-radius:6px;color:var(--muted)}
.v4-search i{margin-left:auto;font-style:normal;font-size:11px}
.v4-lib-head,.v4-lib-row{display:grid;grid-template-columns:230px 130px 90px 50px 70px 1fr;gap:8px;padding:4px 8px;align-items:center;text-align:left}
.v4-lib-head{font-size:10.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;margin-top:6px}
.v4-lib-row{border:0;background:none;font:inherit;color:inherit;border-radius:5px;width:100%}
button.v4-lib-row{cursor:pointer} button.v4-lib-row:hover{background:var(--accent-soft)}
.v4-lib-row.on{background:var(--accent-soft)}
.v4-lib-foot{padding:6px 8px 2px;font-size:11px}
.v4-cap{color:var(--muted);margin-top:12px}
.v4-fix{margin-top:14px;display:flex;flex-wrap:wrap;gap:10px;align-items:center}
.v4-fusion{width:300px;margin:12px;background:#f0f0f0;border:1px solid #c8c8c8;font:12px/1.5 "Segoe UI",system-ui,sans-serif;color:#222}
.fz-h{background:#e2e2e2;padding:4px 8px;font-weight:700;font-size:11px;letter-spacing:.04em}
.fz-row{display:grid;grid-template-columns:70px 1fr;gap:8px;padding:3px 8px}
.v5-main{flex:1;padding:8px 10px}
.v5-fan .ring{fill:none;stroke:var(--line);stroke-width:1}
.v5-fan .ray{stroke:var(--line);stroke-dasharray:3 3}
.v5-fan .tl{fill:var(--muted);font:10px var(--f)}
.v5-fan .reach{fill:none;stroke-width:2;opacity:.9}
.v5-fan .reqz{fill:rgba(47,111,237,.12);stroke:rgba(47,111,237,.5);stroke-dasharray:4 3}
.v5-fan .camb{fill:#1c222b} .v5-fan .camc{fill:#fff}
.v5-leg{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:11px}
.v5-leg i{display:inline-block;width:12px;height:3px;border-radius:2px;margin-right:5px;vertical-align:middle}
.v5-side{width:250px;flex:none;border-left:1px solid var(--line-soft);padding:12px 14px;background:var(--panel-2)}
.v5-fix{display:flex;gap:10px;align-items:center;margin-top:6px}
/* the history section */
.hist{margin:22px 0 8px;padding:20px 22px;background:var(--panel);border:1px solid var(--line);border-radius:6px}
.hist h2{margin:2px 0 6px;font-size:22px}
.hist .tw{overflow-x:auto}
.hist table{border-collapse:collapse;width:100%;font-size:13px;margin:8px 0}
.hist th,.hist td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
.hist th{font:700 10px/1.2 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.hist .y{color:var(--green);font-weight:700} .hist .n{color:var(--red);font-weight:700} .hist .p{color:#a8650e;font-weight:700}
.hist .find{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:10px;margin:12px 0}
.hist .find div{border:1px solid var(--line);border-radius:5px;padding:10px 12px;background:var(--soft);font-size:13px}
.hist .find b{display:block;font-size:20px}
.hist sup{font-size:10px} .hist sup a{color:var(--blue);text-decoration:none}
.hist .srcs{font-size:12px;color:var(--muted);columns:2 420px;margin:10px 0 0;padding-left:20px}
.hist .srcs li{break-inside:avoid;margin-bottom:3px}
@media (max-width:700px){.hist{padding:14px}.hist table{font-size:12px}.hist th:nth-child(3),.hist td:nth-child(3){display:none}}
"""


def state_css(variants) -> str:
    rules = []
    for v in variants:
        for s in {x["state"] for x in v["story"]["steps"]}:
            rules.append(f'.variant-card[data-variant="{v["id"]}"] .prototype[data-story-state="{s}"] .st-{s}{{display:var(--d,block)}}')
    return "\n".join(rules)


def sup(*ns) -> str:
    return "<sup>" + ",".join(f'<a href="#src-{n}">{n}</a>' for n in ns) + "</sup>"


def history(data) -> str:
    calc = data["calc"]
    B = rng(data, "before", "B")
    A = rng(data, "before", "A")
    srcs = [
        ("Zach, PROJECT - Aruco Studio.md § Verify Accuracy (2026-10-18): test at different angles; enter camera distance and resolution, say whether to expect errors", "~/zach_brain/PROJECT - Aruco Studio.md"),
        ("PROJECT - Aruco Studio.md, AI callout 2026-10-18: Verify built (tilt/yaw/blur/noise/glare/dirt, ~0.2 s a view, Tilt as the manual sweep, the measured camera calculator)", "~/zach_brain/PROJECT - Aruco Studio.md"),
        ("Zach, 2026-10-18 chat (bb066f35, line 3967): “single button click… yes ok these markers are ok”, distance should shrink or expand the marker, define success, 5 proposals", "~/zach_brain/Sources/Chats/Claude Code/2026-10-18 — bb066f35 (CHAT).md"),
        ("The 2026-10-18 Verify gallery: V1 Test plan 80, V2 Pass envelope 84, V3 Worst case first 91 (AI pick), V4 Guided check 69, V5 Camera rig 69; 7,740 real runs", "reports/media/verify-proposals-2026-10-18.html"),
        ("Same chat, lines 4529–4978: “Reply with a pick or a splice” and five later “Still yours: pick or splice the Verify proposal”; no Oct 19–21 chat mentions the gallery (grep)", "~/zach_brain/Sources/Chats/Claude Code/2026-10-18 — bb066f35 (CHAT).md"),
        ("git: 8771524 Merge lane/os-verifyui (live sliders, Tilt as the manual sweep, automatic angle sweep, camera calculator); 3b5fc0f label drawn where the plan puts it; 1521cb8 label ON the marker", "git log -i --grep=verify"),
        ("web/src/verify/VerifyDialog.tsx + bench.ts: bench at 16 px per cell (1280×960, 60°); sweep 0–85° in 5° steps, clean; calculator 1500 mm / 1920 px / 70°", "web/src/verify/"),
        ("aruco_studio/web_verify.py: readable() measures a head-on limit (READ_VIEW: blur 0.8, grain 0.04); good / marginal / poor by FIELD_SHARE 0.55", "aruco_studio/web_verify.py"),
        ("Zach's screenshot of 2026-10-21: “Reads all 3”, “marginal 4.6 px per cell … limit ≈ 2.7 m”", "verify-now.webp (scratchpad)"),
        ("Zach, 2026-10-21 brief and addendum: unit-test feel, adversarial budget, label placement; camera library, range-first, range strip, label guide", "this request"),
        ("core/label.py: BLACK_CAP 0.5 module “measured to cost the detector nothing”; the 2026-10-13 white-gap study, n = 3000", "aruco_studio/core/label.py"),
    ]
    rows = [
        ("Test at different angles", "10-18", "Angle sweep, 0–85° per marker, on a clean bench camera", "y", "done", 1, 6, 7),
        ("Enter camera distance + resolution, say if errors are expected", "10-18", "Camera calculator: typed fields; head-on limit, good / marginal / poor", "p", "head-on only", 1, 8),
        ("Sweep the marker myself", "10-18", "Tilt slider re-renders live", "y", "kept", 2, 7),
        ("One click: yes, these markers are ok", "10-18", "5 proposals built (AI pick: Worst case first); never picked, never built", "n", "open", 3, 4, 5),
        ("Distance shrinks or grows the marker in the view", "10-18", "Not built: the bench is fixed at 16 px per cell", "n", "open", 3, 7),
        ("Define what success is", "10-18", "Not built: the verdict is “reads at this one view”", "n", "open", 3, 7),
        ("Feels like a unit test; adversarial glare etc.; label placement", "10-21", "Not built", "n", "new", 10),
        ("Camera library, range-first, range strip, label-placement guide", "10-21", "Not built; the calculator takes typed specs", "n", "new", 10, 7),
    ]
    trs = "".join(f'<tr><td>{esc(a)}</td><td>{d}</td><td>{esc(e)}</td><td class="{k}">{esc(s)}</td><td>{sup(*ns)}</td></tr>'
                  for a, d, e, k, s, *ns in rows)
    li = "".join(f'<li id="src-{i}">{esc(t)} — <code>{esc(p)}</code></li>' for i, (t, p) in enumerate(srcs, 1))
    cam_srcs = "".join(f'<li id="cam-{k}">[{k}] {esc(t)} — <a href="{esc(u)}">{esc(u)}</a></li>' for k, (t, u) in SOURCES.items())
    return f'''<section class="hist" aria-labelledby="hist-h">
  <div class="eyebrow">Read first · history</div>
  <h2 id="hist-h">What exists today vs what was asked</h2>
  <p>You asked for this on 2026-10-18 and an agent did answer: five Verify proposals, real data, a provisional pick.{sup(4)} You never picked one,{sup(5)}
  so the app still has the first Verify: a bench, a sweep and a calculator, no verdict.{sup(6, 7)}</p>
  <div class="tw"><table><tr><th>Asked</th><th>When</th><th>What exists</th><th>State</th><th>Src</th></tr>{trs}</table></div>
  <div class="find">
    <div><b>{m(calc["readable"]["max_distance_mm"], 1)} → {m(calc["range"]["far"], 2)}</b>Your calculator's camera (1920 px, 70°) on a 30 mm 3×1 grid: today's limit is head-on and clean,{sup(8, 9)} under the Field budget it reads to {m(calc["range"]["far"], 2)}.</div>
    <div><b>{m(A["far"], 2)}</b>Board #16–18 here has its label typed 5 mm (a whole module) in a 2.5 mm border row. The lint warns;{sup(11)} the range shows it costs {100 - 100 * A["far"] / B["far"]:.0f} % of the reach. (Injected for the demo; your labels are Auto.)</div>
    <div><b>dirt ≠ distance</b>The simulator sizes its first dirt blob from the whole board, so any dirt above 0 hides a whole 30 mm marker in most draws (board #19–21 at 0.5 m reads all 3 ids in {data["dirt"]["0.0"] * 100:.0f} % of 40 views clean, {data["dirt"]["0.005"] * 100:.0f} % with 0.5 % dirt). Dirt stays out of the default budget; it belongs to a “k of n markers for pose” rule.</div>
  </div>
  <p class="muted">Every number on this page is the shipped core's (<code>web_verify</code> under CPython, OpenCV's detector) at {esc(data["head"])}, computed {esc(data["generated"])}; Pyodide speed measured on the running Stable build.</p>
  <details><summary>Sources</summary><ol class="srcs">{li}</ol><p class="muted">Camera library sources (accessed 2026-10-21):</p><ul class="srcs">{cam_srcs}</ul></details>
</section>'''


def build(data: dict) -> int:
    ratio = pyodide_ratio(data)
    vs = {"v1": v1(data), "v2": v2(data), "v3": v3(data), "v4": v4(data), "v5": v5(data)}
    spec = project(data, vs, ratio)
    with tempfile.TemporaryDirectory() as tmp:
        sp = Path(tmp) / "spec.json"
        sp.write_text(json.dumps(spec, ensure_ascii=False))
        out = Path(tmp) / "g.html"
        r = subprocess.run([sys.executable, str(SKILL / "scripts/gallery.py"), "build", "--spec", str(sp),
                            "--output", str(out), "--strict"], capture_output=True, text=True)
        print(r.stdout, r.stderr)
        if r.returncode:
            return r.returncode
        page = out.read_text()
    page = page.replace("<title>Babble &amp; Prune</title>", "<title>Verify as a unit test</title>", 1)
    page = page.replace("</style>", CSS + "\n" + state_css(spec["variants"]) + "\n</style>", 1)
    page = page.replace('<main class="page">', '<main class="page">' + history(data), 1)
    OUT.write_text(page)
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.2f} MB)")
    r = subprocess.run([sys.executable, str(SKILL / "scripts/gallery.py"), "check", "--input", str(OUT),
                        "--strict"], capture_output=True, text=True)
    print(r.stdout, r.stderr)
    return r.returncode


REQUIREMENTS = [
    {"id": "fr1", "name": "Trust in the answer", "weight": 25,
     "why": "Zach sense-checks one answer and moves on. An optimistic range sends markers to the robot that miss in the field; a flaky one gets ignored.",
     "passCondition": "The answer comes from the real detector across the whole budget and distance span, is the same every run, has enough cases per distance to bound the miss rate, and says what it assumed.",
     "anchors": {"1": "One view or a rule of thumb; can say 'reads' where a budget case fails.",
                 "3": "Samples budget × distance, seeded, but coarse (rungs) or statistically loose (24 cases, no interval).",
                 "5": "A continuous range from enough cases, with its uncertainty shown, the same every run."}},
    {"id": "fr2", "name": "Range-first, at a glance", "weight": 20,
     "why": "Zach's addendum (2026-10-21): pick a camera, Verify answers each marker's min–max distance, he sense-checks it; a typed requirement is optional.",
     "passCondition": "One look shows every board's near–far on a shared distance axis for a camera picked from the library; a requirement band is an optional overlay.",
     "anchors": {"1": "A verdict only; no distances.",
                 "3": "Distances per board, but not on one shared axis, or only a far limit.",
                 "5": "Every board's near–far on one shared axis, camera one click away, requirement optional."}},
    {"id": "fr3", "name": "A failure says what to change", "weight": 20,
     "why": "The brief's own examples: 'label covers 2 border cells — move outside', 'too small at 2 m — make it ≥ 32 mm'.",
     "passCondition": "A failure names the board, the id, the condition and the cause, offers a fix that was re-measured, and opens the bench there.",
     "anchors": {"1": "Just FAIL.", "3": "Board and condition.",
                 "5": "Board, id, cause, a re-measured fix in one click, and the bench."}},
    {"id": "fr4", "name": "Speed", "weight": 15,
     "why": "'I click it, it should run an automated sweep' — seconds, in the browser's Pyodide, on a document of several boards.",
     "passCondition": "The browser time, estimated from this engine's measured CPython time × the measured Pyodide factor, is a few seconds, or the answer is already there when he looks.",
     "anchors": {"1": "Over a minute, nothing until it ends.", "3": "10–60 s, or arrives progressively / cached.",
                 "5": "Under 5 s, or already computed before he looks."}},
    {"id": "fr5", "name": "Fits the Fusion add-in", "weight": 10,
     "why": "The add-in runs this core in Fusion's Python, which has no OpenCV; ArUco Extrude is the CAD feature.",
     "passCondition": "The answer is a value stored on the feature that the add-in's panel shows as-is and marks stale after an edit.",
     "anchors": {"1": "Needs the Studio dialog and OpenCV.", "3": "A stored verdict without its numbers.",
                 "5": "A per-feature value shown as a panel row, stale-aware."}},
    {"id": "fr6", "name": "Implementation cost", "weight": 10,
     "why": "Everything here reuses web_verify's render; what differs is the engine around it and the surface.",
     "passCondition": "An engine function in web_verify.py plus a view on existing pieces.",
     "anchors": {"1": "New simulator capability plus a new surface (weeks).", "3": "A new surface plus orchestration (several days).",
                 "5": "One engine function and a small view (two days or less)."}},
]

GATES = [
    {"id": "g1", "name": "Real detector", "why": "Ranges and verdicts come from web_verify renders read by OpenCV's ArucoDetector, never a px-per-cell rule of thumb."},
    {"id": "g2", "name": "The manual bench stays", "why": "Zach, 2026-10-18: 'I like how I sweep the verify marker myself'. Every answer opens the bench at that camera in one click."},
    {"id": "g3", "name": "Same answer every run", "why": "A unit test must not be flaky: cases are seeded, so the same document, camera and budget give the same answer."},
    {"id": "g4", "name": "Runs from a script", "why": "Zach's addendum: the public Label placement guide must be Verify's own output — CPython, no browser."},
]


def project(data, vs, ratio) -> dict:
    req_ = data["requirement"]
    fix = data["fix_mm"]
    x = ratio["x"]
    cl = data["clean"]

    def secs(kind, share=1.0):
        return cl[kind]["s"] * share * x

    def speed(t, background=False):
        """FR4's anchors on the estimated browser seconds; +1 when the answer
        is computed in the background before he looks."""
        sc = 5 if t <= 5 else 4 if t <= 10 else 3 if t <= 60 else 2 if t <= 180 else 1
        return min(5, sc + (1 if background else 0))
    B = rng(data, "before", "B")
    A = rng(data, "before", "A")
    g = {r["name"]: r for r in data["guide"]}
    unsafe = [r["name"] for r in data["guide"] if guide_verdict(r) == "unsafe"]
    gate = lambda e1, e2, e3, e4: {"g1": {"pass": True, "evidence": e1}, "g2": {"pass": True, "evidence": e2},  # noqa: E731
                                   "g3": {"pass": True, "evidence": e3}, "g4": {"pass": True, "evidence": e4}}
    seeded = "Its cases come from draws(seed=20261021): two builds of this page gave the same numbers."
    rB5 = data["reach"]["before"]["B"][DEFAULT_CAMERA]["reach"]
    variants = [
        {"id": "v1", "name": "Test suite",
         "thesis": "Verify is a test file: the camera and an optional requirement are its fixtures, Run prints one pass / fail per board × distance rung, and Print runs it first like CI.",
         "accent": "#3f6fa8",
         "bestWhen": "Markers ship to a fixed cell with a known requirement, and a release step (Print) should refuse a failing sheet.",
         "losesWhen": "There is no requirement yet: then it is a coarse range on 8 rungs, and a gap between rungs (1.4 → 2.0 m) is untested.",
         "decisions": [{"label": "Primary object", "value": "Test cases: board × distance rung, each 'every id in ≥ 23 of 24 cameras'."},
                       {"label": "Trigger", "value": "Run in the dialog; Print runs it first and writes the result on the sheet's footer."},
                       {"label": "Scope", "value": "The whole document, grouped by board."}],
         "keepParts": ["Print runs the tests first (CI)", "the run as text for scripts", "rung dots per board"],
         "proof": [f"Ladder computed on the 4 boards: {vs['v1']['pass']} rung tests pass and {vs['v1']['fail']} fail inside 0.3–2.0 m (D435 colour, Field).",
                   f"The #16–18 failure image is the real 0.70 m case that loses #17; after Label Auto the same camera reads all three."],
         "scores": {
             "fr1": {"score": 3, "evidence": f"24 seeded cases per rung, 23 to pass: one rung's verdict moves with a single case, and between rungs (1.4 → 2.0 m) is unknown.", "confidence": "high"},
             "fr2": {"score": 3, "evidence": "The range is read off rung dots per board on shared columns; no continuous band, no near end.", "confidence": "high"},
             "fr3": {"score": 4, "evidence": "The assertion names board, id, rung and cause (the lint, now measured), with re-run fixes; size advice is only as fine as the rungs.", "confidence": "medium"},
             "fr4": {"score": speed(secs('ladder')), "evidence": f"{cl['ladder']['renders']} renders, ≈ {secs('ladder'):.0f} s in one Pyodide worker (CPython {cl['ladder']['s']:.1f} s × {x:.1f}); rows fill in as they finish.", "confidence": "medium"},
             "fr5": {"score": 3, "evidence": "A stored '24 passed' fits a panel row, but rung dots and the assertion text need the Studio.", "confidence": "medium"},
             "fr6": {"score": 3, "evidence": "A ladder function, a results table, the assertion pane and a Print gate: several days.", "confidence": "medium"}},
         "gateResults": gate("Every rung is web_verify._view on the plan (OpenCV's detector).", "'Open on the bench' loads the failing case into the sliders.", seeded, "ladder() is plain CPython; the terminal exhibit is its output."),
         "previewLabel": "Verify dialog · tests"},
        {"id": "v2", "name": "Live badges",
         "thesis": "No Verify click at all: every board carries its reading range as a badge on the canvas, re-measured in the background after each edit, red when it misses the requirement.",
         "accent": "#2f7f74",
         "bestWhen": "Zach is designing and wants to see the consequence of each edit without opening anything.",
         "losesWhen": "Many boards are edited at once, or the core's one Pyodide worker is busy planning: badges queue behind the plan calls.",
         "decisions": [{"label": "Primary object", "value": "The board on the canvas, with its range as a badge."},
                       {"label": "Trigger", "value": "Every edit, debounced; 12 cases first (hollow), 48 confirm in idle time (solid)."},
                       {"label": "Scope", "value": "Per board; the top bar counts the misses."}],
         "keepParts": ["range badge on each board", "popover: id, cause, fix, bench", "re-measure after edit"],
         "proof": [f"12-case badges (bisection) vs the 48-case range on the same boards: B {m(data['smoke']['before']['B'][DEFAULT_CAMERA]['far'])} vs {m(B['far'])}.",
                   "The popover's picture is the real case that loses #17 under the typed label."],
         "scores": {
             "fr1": {"score": 3, "evidence": f"The first number is a 12-case bisection (optimistic; B {m(data['smoke']['before']['B'][DEFAULT_CAMERA]['far'])} vs {m(B['far'])} confirmed); trust arrives only when the 48-case run lands.", "confidence": "high"},
             "fr2": {"score": 3, "evidence": "Every board shows near–far with no click, but as numbers on badges, not on one shared axis.", "confidence": "high"},
             "fr3": {"score": 5, "evidence": "The red badge opens id, cause, a re-measured fix and the bench, right on the board.", "confidence": "medium"},
             "fr4": {"score": speed(secs('smoke', 0.25), True), "evidence": f"Already there when he looks: one board's badge ≈ {secs('smoke', 0.25):.1f} s after an edit, its confirmation ≈ {secs('range', 0.25):.0f} s, in the background.", "confidence": "medium"},
             "fr5": {"score": 4, "evidence": "The badge is a stored per-feature range: the panel can show it and grey it after an edit, but cannot re-measure.", "confidence": "medium"},
             "fr6": {"score": 2, "evidence": "A background scheduler, a second Pyodide worker (so badges don't block planning), canvas badges, popovers and a cache: the most new machinery.", "confidence": "medium"}},
         "gateResults": gate("Badges and confirmations are web_verify._view renders.", "The popover has 'Open on the bench'.", seeded, "smoke() and reading_range() are CPython."),
         "previewLabel": "canvas · badges"},
        {"id": "v3", "name": "Break it",
         "thesis": "Verify plays adversary: it hunts for the camera inside the budget that loses an id, shrinks it to the smallest failing case, and the range is how far no attack breaks it.",
         "accent": "#b7791f",
         "bestWhen": "Safety-flavoured work where one miss matters more than the average, and 'what exactly breaks it' is the question.",
         "losesWhen": "Zach wants the typical reach: the strict edge sits at roughly half the 95 % range and moves with pixel-grid luck.",
         "decisions": [{"label": "Primary object", "value": "The counterexample: the smallest camera that loses an id, as a picture."},
                       {"label": "Rule", "value": "No miss in 48 attacks (8 budget corners + 40 random) at a distance."},
                       {"label": "Trigger", "value": "On click, per board."}],
         "keepParts": ["shrunk counterexample image", "attack log", "corner attacks"],
         "proof": [f"B holds to {m(data['break']['before']['B'][DEFAULT_CAMERA]['holds_to'])} against a 95 % range of {m(B['far'])}.",
                   "Shrinking kept every knob for B: on this budget no single knob is 'the' cause."],
         "scores": {
             "fr1": {"score": 2, "evidence": f"Strict and deterministic, but its edge is set by the unluckiest pixel grid: B's shrunk case breaks at {m(data['break']['before']['B'][DEFAULT_CAMERA]['shrunk']['case']['dist'])}, inside the {m(data['break']['before']['B'][DEFAULT_CAMERA]['holds_to'])} it 'holds' to.", "confidence": "high"},
             "fr2": {"score": 2, "evidence": "One 'holds to' number per board; no near end, no shared axis.", "confidence": "high"},
             "fr3": {"score": 3, "evidence": "It shows exactly the camera that breaks it, but shrinking kept every knob here, so the fix is still 'bigger'.", "confidence": "medium"},
             "fr4": {"score": speed(secs('break')), "evidence": f"{cl['break']['renders']} renders, ≈ {secs('break'):.0f} s in one worker; stops at the first break.", "confidence": "medium"},
             "fr5": {"score": 3, "evidence": "'Holds to' can be stored; the counterexample needs the Studio.", "confidence": "medium"},
             "fr6": {"score": 3, "evidence": "Search, shrink and the counterexample view: several days.", "confidence": "medium"}},
         "gateResults": gate("Every attack is a web_verify._view render.", "The counterexample opens on the bench with its knobs set.", "Attacks are seeded (corners fixed, 40 from draws(seed=7)).", "break_it() is CPython."),
         "previewLabel": "Verify dialog · adversary"},
        {"id": "v4", "name": "Range strip",
         "thesis": "Verify answers with a range: pick a camera from the library and every board shows the near–far distance it reads at on one shared axis; set a requirement only if you have one.",
         "accent": "#7667c6",
         "bestWhen": "Zach knows his camera and wants to sense-check distances, and the same engine should publish the label guide.",
         "losesWhen": "The camera looks from steep angles: the band averages tilt over the budget, so a 45°-only shortfall (V5 found one at the fix size) can hide in it; or he wants the answer while editing without opening anything (V2).",
         "decisions": [{"label": "Primary object", "value": "Each board's reading band: near–far where every id reads in 95 % of the budget, with its 90 % band."},
                       {"label": "Trigger", "value": "Opening Verify or picking a camera; cached per board + camera, so only edited boards re-run."},
                       {"label": "Requirement", "value": "Optional overlay, batch-set for all boards; misses say by how much and offer the measured fix."}],
         "keepParts": ["range strip on one shared axis", "camera library with reach per row", "range stored on the feature (Fusion row)", "the guide is a script over the same engine"],
         "proof": [f"Ranges on all 13 cameras computed for the 4 boards; B on the D435 reads {m(B['near'])} – {m(B['far'])} (90 % band {m(B['band'][0])} – {m(B['band'][1])}).",
                   f"The fix ({fix} mm, label Auto) is the smallest size of 35–60 mm whose every band reaches {m(req_[1])}, measured.",
                   f"The guide table below its hero is `--guide` output: {len(data['guide'])} placements, {sum(r['renders'] for r in data['guide'])} renders."],
         "scores": {
             "fr1": {"score": 4, "evidence": f"48 cases × 6+ distances, a monotone fit and a 90 % band drawn on the strip (B ± {B['pm'] * 100:.0f} %). Not 5: other 48-case sets moved B by ~10 % (1.28–1.38 m in the calibration vs {m(B['far'])} here).", "confidence": "high"},
             "fr2": {"score": 5, "evidence": "Zach's strip: boards in a row, a band under each on one log axis, the library one click, the requirement an optional overlay.", "confidence": "high"},
             "fr3": {"score": 5, "evidence": f"'short by …', the id that drops first, the re-measured fix ({fix} mm / Label Auto), the edge pictures, and the bench from a band's end.", "confidence": "medium"},
             "fr4": {"score": speed(secs('range')), "evidence": f"{cl['range']['renders']} renders, ≈ {secs('range'):.0f} s for 4 boards in one Pyodide worker (CPython {cl['range']['s']:.1f} s × {x:.1f}); bands draw as they land and are cached, so an edit re-runs one board (≈ {secs('range', 0.25):.0f} s).", "confidence": "medium"},
             "fr5": {"score": 5, "evidence": "A range is two numbers on the feature: the add-in shows 'Reads 0.15–2.1 m · D435' and greys it after an edit, no OpenCV needed.", "confidence": "medium"},
             "fr6": {"score": 4, "evidence": "reading_range() moves into web_verify.py beside readable(); the strip replaces the calculator; the library is a data file.", "confidence": "medium"}},
         "gateResults": gate("reading_range() calls web_verify._view for every case.", "Clicking a band's end opens the bench at that distance and camera.", seeded, f"`--guide` runs it in CPython: {len(data['guide'])} placements."),
         "previewLabel": "Verify dialog · range strip"},
        {"id": "v5", "name": "Reach fan",
         "thesis": "The range depends on the angle you look from, so Verify draws each board's reach as a fan from the camera: how far it reads head on, at 15°, 30° and 45°.",
         "accent": "#a94f78",
         "bestWhen": "The camera's pose varies a lot (a wrist camera sweeping past the part) and the angle, not the distance, is the open question.",
         "losesWhen": "Many boards overlap into a tangle of curves, and it costs four ranges per board.",
         "decisions": [{"label": "Primary object", "value": "Reach by viewing angle, drawn as a fan from the camera."},
                       {"label": "Requirement", "value": "A zone (distance × angle) instead of a band."},
                       {"label": "Trigger", "value": "On click."}],
         "keepParts": ["reach fan", "requirement as a distance × angle zone"],
         "proof": ["Reach measured at 0°, 15°, 30°, 45° for each board (48 cases per distance per angle).",
                   "The 45° picture is a real render past B's 45° reach."],
         "scores": {
             "fr1": {"score": 4, "evidence": f"The same fit per angle, but each angle has its own 48 cases, so the curve wobbles: B reads to {m(rB5[0]['far'])} head on and {m(rB5[1]['far'])} at 15°.", "confidence": "medium"},
             "fr2": {"score": 3, "evidence": "Ranges by angle, overlaid; no near end and no per-board strip.", "confidence": "high"},
             "fr3": {"score": 4, "evidence": "Shows the angle where it fails: " + vs["v5"]["fixed_words"] + " The id that drops is one click deeper.", "confidence": "medium"},
             "fr4": {"score": speed(secs('reach')), "evidence": f"{cl['reach']['renders']} renders, ≈ {secs('reach'):.0f} s in one worker: four ranges per board.", "confidence": "medium"},
             "fr5": {"score": 3, "evidence": "Four numbers per board can be stored; the fan needs the Studio.", "confidence": "medium"},
             "fr6": {"score": 3, "evidence": "Per-angle engine plus a polar view: several days.", "confidence": "medium"}},
         "gateResults": gate("Every point is web_verify._view.", "A point on the fan opens the bench at that angle and distance.", seeded, "reach() is CPython."),
         "previewLabel": "Verify dialog · reach"},
    ]
    for v in variants:
        built = vs[v["id"]]
        v["preview"] = built["preview"]
        v["media"] = built["media"]
        v["story"] = {"title": "Walk the verdict", "steps": built["steps"]}
    def totals_with(shift=0):
        w = {r["id"]: r["weight"] for r in REQUIREMENTS}
        w["fr2"] -= shift
        w["fr4"] += shift
        return {v["id"]: sum(w[k] * v["scores"][k]["score"] / 5.0 for k in w) for v in variants}
    totals = totals_with(0)
    flip = next((k for k in range(5, 21, 5) if totals_with(k)["v2"] >= max(totals_with(k).values()) - 0.5), None)
    rank = sorted(totals, key=totals.get, reverse=True)
    top, second = rank[0], rank[1]
    names = {v["id"]: v["name"] for v in variants}
    return {
        "schemaVersion": 3,
        "title": "Verify as a unit test — five takes",
        "kicker": "ArUco Studio · /babble 5 · 2026-10-21",
        "brief": ("Click Verify and get a straight answer: does this marker read at the distances I'll look from, through some glare, blur and tilt? "
                  "Since the addendum, the answer leads with a range: pick a camera from the library, read each board's near–far distance, "
                  "and set a requirement only if you have one. Shared scenario: your document's four boards on a RealSense D435's colour stream "
                  "under the Field budget, with board #16–18's label typed 5 mm tall to make a real failure."),
        "count": 5,
        "defaultId": top,
        "defaultWhy": (f"{names[top]} scores {totals[top]:.0f} / 100: it is the addendum's answer (camera → each board's near–far on one axis), "
                       f"its engine is the one that publishes the label guide from a script, and the range lives on the feature for Fusion. "
                       f"{names[second]} is next at {totals[second]:.0f}: it wins on speed and loses on trust and cost. "
                       f"Splice to consider: {names[top]}'s engine and strip, with {names['v2']}'s badge showing the same cached range on the canvas, "
                       f"and {names['v1']}'s Print gate when a requirement is set."),
        "decisionHinge": ((f"Speed against the shared axis: move {flip} points of weight from 'Range-first' to 'Speed' and "
                           f"Live badges {'ties' if abs(totals_with(flip)['v2'] - totals_with(flip)[top]) < 0.5 else 'takes the lead'} "
                           f"({totals_with(flip)['v2']:.0f} vs {totals_with(flip)[top]:.0f}): it answers after every edit with no click. " if flip else
                           "Speed against the shared axis: even moving all 20 points of 'Range-first' onto 'Speed' leaves the order unchanged. ")
                          + f"The engine's own hinge is cases per distance: 48 gives about ± 10 % on the far end in ≈ {secs('range', 0.25):.0f} s a board "
                          f"in one Pyodide worker; 96 halves the ± and doubles the time."),
        "invariants": [
            "One document: four boards (Grid 3×1 #16–18, #19–21, #22–24, Grid 2×1 #25–26), DICT_4X4_50, 30 mm, inkjet vinyl.",
            "One camera library (13 presets with sources); the default pick is the RealSense D435 colour stream, 1920×1080, 69°.",
            "One adversarial budget, 'Field': tilt ≤ 45° in any direction, blur 0.3–1.5 px, grain 0.02–0.2, glare 0–0.5, no dirt.",
            "Requirement mode is optional everywhere: 0.3–2.0 m batch-set for all four boards.",
            "Every number is the shipped core's web_verify under CPython; browser times are CPython × the Pyodide factor measured on Stable.",
        ],
        "boundary": (f"Static HTML mocks over real data: every range, test, badge, counterexample, picture and guide row was computed by "
                     f"aruco_studio.web_verify at {data['head']} ({data['generated']}); the clicks walk precomputed states. Not built in the app. "
                     f"Browser times are estimates: CPython × {x:.1f} (readable, measured on Stable)."),
        "axes": [
            {"name": "What the answer is", "values": ["pass/fail per rung", "a range on a badge", "a strict 'holds to'", "a near–far band", "reach by angle"]},
            {"name": "Where it lives", "values": ["dialog + Print gate", "the canvas", "dialog", "dialog strip + the feature", "dialog fan"]},
            {"name": "When it runs", "values": ["Run / Print", "every edit", "on click", "open / camera pick, cached", "on click"]},
            {"name": "Statistics", "values": ["24 cases per rung", "12 then 48", "worst of 48 attacks", "48 cases × 6 distances, fitted", "48 × 6 per angle"]},
        ],
        "requirements": REQUIREMENTS,
        "hardGates": GATES,
        "variants": variants,
    }


if __name__ == "__main__":
    raise SystemExit(main())
