"""Verify accuracy for the online Studio (CoreApi.verify / readable): the plan
rendered as a camera would see it, read by OpenCV's own ArUco detector.

numpy + OpenCV, which Pyodide loads on the first call (web/src/core/worker.ts);
web_api imports this module only then. The marker is planned exactly as the
Studio plans it (web_api._plan: corner marks, grids, ChArUco as built) and
its label is drawn beside it where the sketch puts it (web_api.placed_label);
verify.camera is the camera, the dirt and the detector.

`readable` MEASURES the distance: it runs `verify` head on, with the blur
and grain of a decent camera (READ_VIEW), outward and then bisected
(max_distance), so its limit is the simulator's, not a rule of thumb (the
old core.markers.suggest's "5 px per module" is not used); `measured` true.

Without numpy / OpenCV (inside a CAD's Python: Fusion) this module still
imports, `readable` gives the analytic answer (readable_analytic, `measured`
false) and `verify` refuses in words.

`reading_range` (V4 "Range strip", 2026-10-21) is each marker's near - far on
a camera from the camera library (core.cameras), through a budget of tilt,
blur, grain and glare: core.reading_range's engine with this module's reader
(the plan rendered, OpenCV's detector), or its pinhole model without OpenCV
(`measured` false). `range_table` is the same for a list of markers (a
script's table; `python -m aruco_studio.web_verify requests.json`) on ONE
OpenCV, the newest installed unless asked (opencv_choice), and
range_start / range_step / range_cancel run one in time slices for the
browser's worker (progress, cancel, the UI never waits on one call).
"""
from __future__ import annotations

import base64
import json
import math
import sys
import time

from . import web_api as _W
from .core import cameras as _CAMS
from .core import dictionary as _D
from .core import reading_range as _RR

try:
    import cv2
    import numpy as np

    from .verify import camera as _C
    from .verify import pnp as _pnp
except ImportError:                                # a CAD's Python: no numpy / OpenCV
    cv2 = np = _C = _pnp = None

PNG_MAX_W = 640
# readable's probe: head on; a decent lens + demosaic (blur sigma 0.8 px) and
# grain of 2 grey levels (noise 0.04 x camera.NOISE_SIGMA); seed 0
READ_VIEW = {"tilt_deg": 0.0, "yaw_deg": 0.0, "blur_px": 0.8, "noise": 0.04, "glare": 0.0,
             "occlusion": 0.0, "seed": 0}
READ_COARSE = 1.15          # the outward scan's step
READ_STEP = 1.01            # then bisect until the bracket's ratio is under this
READ_JITTER = (1.0, 0.99, 1.01, 0.98, 1.02)
# WHY these thresholds (measured with this simulator, 2026-10-18): a field
# view -- tilt 45 deg, blur 1 px, grain 0.1, seeds 0-4 -- still reads every
# id out to this share of the head-on limit. Over 4 cameras (3840x2160/90,
# 1920x1080/70, 1280x720/70, 640x480/60 deg) x 5 markers (4x4 30 mm, 5x5
# 50 mm, 6x6 30 mm singles, a 2x3 grid, a 5x4 ChArUco) the share ran 0.57
# (the 4x4 single at 720p) to 0.85; at 4K it is 0.81-0.85, at 1080p
# 0.62-0.80. So within 0.55 of the limit is "good" (tilt, blur and grain
# still read); out to the limit "marginal" (reads square on, a tilt or a
# blur can lose it); past it "poor". tests/web/test_web_verify.py
# test_good_still_reads_in_the_field holds the 4x4 single to it.
FIELD_SHARE = 0.55
FIELD_VIEW = {"tilt_deg": 45.0, "yaw_deg": 0.0, "blur_px": 1.0, "noise": 0.1, "glare": 0.0,
              "occlusion": 0.0}
# readable_analytic (no OpenCV): the pinhole model at the limits the simulator
# measured. WHY 3.1 px per cell (measured 2026-10-18, max_distance over the
# cameras and markers FIELD_SHARE's comment names): at the head-on limit a
# cell spans 1.61 px (6x6) to 3.08 px (5x5; a 4x4 2.27 single, 2.80 grid
# and ChArUco) wherever OpenCV's minimum outline does not bind; at 4K it
# binds first (the outline at the limit is 115-119 px against 115.2). So the
# limit is the nearer of 3.1 px per cell and OpenCV's minimum outline: never
# farther than the simulator measured (up to ~2x nearer for a 6x6).
READ_PX_PER_CELL = 3.1
PERIMETER_RATE = 0.03       # OpenCV's default minMarkerPerimeterRate (verify.camera's)


def placed(req: dict) -> dict:
    """The request with the box its marker goes in (web_api.placed_in: its
    rect, else the box fitted in its profile); refused in words when nothing
    fits."""
    req, pre = _W.placed_in(req)
    if req["rect"] is None:
        raise ValueError("nothing to verify: " + pre[0]["text"])
    return req


def _plan(req: dict):
    d, _issues = _W._plan(req)
    if not d["ok"]:
        raise ValueError("nothing to verify: " + "; ".join(d["errors"]))
    return d


def _label(req: dict, d: dict):
    """The sketch's label in the pattern frame (verify.camera.scene_of), or
    None (off, or Flip: the marker then faces away from its sketch text).
    On the marker's black (Zach, 2026-10-20) it is white: the letters are
    paper knocked out of the border row, which is what the detector must
    still read past; the pixel font (3D) as its own boxes."""
    flip = _W.flip_of(req)                         # on a reference face too (barrier 10)
    fl = _W._planned(req)[2]
    lab = _W.placed_label(req, d["layout"]["kind"], d["marker"]["dictionary"], d["ids"], fl)
    if lab is None or flip:
        return None
    # WHY the plan's own pattern -> sketch matrix (2026-10-18): with the label
    # inside the rectangle the marker sits in the box the label leaves, not at
    # the rectangle's centre; the rectangle's matrix put the label over it
    M = np.array(_W.plan(req)["pattern_to_sketch"], np.float64).reshape(4, 4)
    Mi = np.linalg.inv(M)
    at = Mi @ np.array([lab["at"][0], lab["at"][1], 0.0, 1.0])
    a = math.radians(lab["angle_deg"])
    dr = Mi[:3, :3] @ np.array([math.cos(a), math.sin(a), 0.0])
    out = {"text": lab["text"], "at": (float(at[0]), float(at[1])),
           "height_mm": float(lab["height_mm"]), "dir": (float(dr[0]), float(dr[1])),
           "width_mm": max(_W.text_width(t, lab["height_mm"]) for t in lab["text"].split("\n"))}
    if fl.place == "on_marker":
        # on the marker the letters must cover what the print covers (Helvetica's
        # widths), and the 3D font is its own boxes; beside it, today's text
        out["widths"] = [_W.text_width(t, lab["height_mm"]) for t in lab["text"].split("\n")]
        if fl.knockout:
            out["colour"] = "white"
        if lab["font"] == "pixel" and lab["polygons"]:
            def back(q):
                return [[float((Mi @ np.array([u, v, 0.0, 1.0]))[k]) for k in (0, 1)] for u, v in q]
            out["polygons"] = [{"outer": back(p["outer"]), "holes": [back(hl) for hl in p["holes"]]}
                               for p in lab["polygons"]]
    return out


def cell_mm(d: dict) -> float:
    return d["marker"]["marker_length_m"] * 1000.0 / _D.dictionary_info(
        d["marker"]["dictionary"])["modules"]


def _px_per_cell(d: dict, cam: _C.Cam) -> float:
    return cell_mm(d) * cam.px_per_mm


def _view(d: dict, scene, cam: _C.Cam, view: dict, picture: bool = True) -> dict:
    v = _C.simulate(scene, cam, view)
    got = _C.read(v, d)
    want = list(d["ids"])
    found = sorted(i for i in got["ids"] if i in want)
    missing = sorted(set(want) - set(found))
    wrong = sorted(i for i in got["ids"] if i not in want)
    err_mm = err_deg = None
    if got["pose"] is not None:
        err_mm, err_deg = _pnp.err(_C.truth_m(v, d), got["pose"])
    notes = []
    ppc = _px_per_cell(d, cam)
    notes.append(f"{cam.width}×{cam.height} px, {cam.hfov_deg:g}° across: "
                 f"{cam.px_per_mm:.2f} px per mm at {cam.distance_mm:.0f} mm head on, "
                 f"{ppc:.1f} px per cell")
    tilt = abs(float(view.get("tilt_deg") or 0.0))
    yaw = abs(float(view.get("yaw_deg") or 0.0))
    if tilt or yaw:
        short = ppc * math.cos(math.radians(min(_C.MAX_TILT, max(tilt, yaw))))
        notes.append(f"tilted: about {short:.1f} px per cell across the tilt")
    side_px = d["marker"]["marker_length_m"] * 1000.0 * cam.px_per_mm
    min_perim = _C.PERIMETER_RATE * max(cam.width, cam.height)
    if 4.0 * side_px < min_perim * 1.15:
        notes.append(f"a marker's outline is about {4.0 * side_px:.0f} px; OpenCV's default "
                     f"skips outlines under {min_perim:.0f} px "
                     f"(3% of {max(cam.width, cam.height)} px)")
    if v.clipped:
        notes.append("the marker runs off the sensor at this distance")
    if v.occluded > 0:
        notes.append(f"dirt covers {v.occluded * 100:.0f} % of the marker area")
    if got["pose"] is None:
        notes.append("no pose: too few corners read")
    if wrong:
        notes.append("read ids the marker does not print: " + ", ".join(map(str, wrong)))
    out = {"ok": not missing and not wrong, "found": found, "missing": missing, "wrong": wrong,
           "px_per_cell": round(ppc, 3),
           "pose_error_mm": None if err_mm is None else round(float(err_mm), 3),
           "pose_error_deg": None if err_deg is None else round(float(err_deg), 3),
           "image_png_base64": "", "notes": notes,
           # WHY named (docs/peps/0003 decision 3): every result says which OpenCV drew and read it
           "opencv": cv2.__version__}
    if picture:
        ok, png = cv2.imencode(".png", _C.picture(v, d, got, missing, PNG_MAX_W))
        out["image_png_base64"] = base64.b64encode(png.tobytes()).decode("ascii") if ok else ""
    return out


def _need_cv(what: str) -> None:
    if cv2 is None:
        raise ImportError(f"{what} needs numpy and OpenCV, which this Python does not have")


def verify(req: dict, view: dict) -> dict:
    _need_cv("verify")
    req = placed(req)
    d = _plan(req)
    cam = _C.Cam.of(view["camera"])
    return _view(d, _C.scene_of(d, _label(req, d)), cam, view)


def _reads(d, scene, cam0: _C.Cam, distance: float) -> bool:
    """At least half of READ_JITTER's views round the distance read every id.
    WHY a vote, not one view: where a cell edge lands on the pixel grid
    makes the odd distance miss one marker well inside the limit (a ChArUco
    5x4 at 720p: 12 holes, each about 0.4 % wide, in 500-890 mm), and near
    the limit reading is a coin toss over a band (a 2x3 grid at 720p: from
    the first miss to the last read is x1.3). One view in a hole, or a lucky
    one past the band, would set the limit there."""
    votes, n = 0, len(READ_JITTER)
    for k, f in enumerate(READ_JITTER):
        cam = _C.Cam(distance * f, cam0.width, cam0.height, cam0.hfov_deg)
        votes += bool(_view(d, scene, cam, READ_VIEW, picture=False)["ok"])
        if 2 * votes >= n or 2 * (votes + n - 1 - k) < n:
            break
    return 2 * votes >= n


def max_distance(d: dict, scene, cam: _C.Cam) -> float:
    """The farthest READ_VIEW still reads every id (mm), head on: from 4 px
    per cell (in to the sticker filling 60 % of the frame when even that
    fails) out in x READ_COARSE steps to the first distance that does not
    read, then bisected to READ_STEP. The first failure, not the last read:
    past it reading is luck. 0 when it does not read even filling the frame."""
    u0, v0, u1, v1 = d["guides"]["sticker"]
    near = max(u1 - u0, v1 - v0) * cam.f_px / (0.6 * min(cam.width, cam.height))
    lo = max(near, cell_mm(d) * cam.f_px / 4.0)
    while not _reads(d, scene, cam, lo):
        if lo <= near:
            return 0.0
        lo = max(near, lo / READ_COARSE)
    hi = lo * READ_COARSE
    for _ in range(40):
        if not _reads(d, scene, cam, hi):
            break
        lo, hi = hi, hi * READ_COARSE
    while hi / lo > READ_STEP:
        mid = math.sqrt(lo * hi)
        if _reads(d, scene, cam, mid):
            lo = mid
        else:
            hi = mid
    return lo


def _dist_words(mm: float) -> str:
    return f"{mm / 1000.0:.1f} m" if mm >= 1000.0 else f"{mm:.0f} mm"


def verdict_of(distance: float, limit: float) -> str:
    if limit <= 0 or distance > limit:
        return "poor"
    return "good" if distance <= FIELD_SHARE * limit else "marginal"


def _readability(ppc: float, distance: float, lim: float, measured: bool) -> dict:
    verdict = verdict_of(distance, lim)
    why = {"good": "reads reliably",
           "marginal": "reads head on, but a tilt, blur or dirt can lose it",
           "poor": "too far: it will not read"}[verdict]
    text = (f"{ppc:.1f} px per cell at {distance:.0f} mm: {why}; "
            + (f"limit ≈ {_dist_words(lim)}" if lim > 0 else "it does not read at any distance")
            + ("" if measured else " (estimated: no OpenCV here)"))
    return {"px_per_cell": round(ppc, 3), "max_distance_mm": round(lim, 1), "verdict": verdict,
            "text": text, "measured": measured, "opencv": cv2.__version__ if measured else None}


def readable_analytic(req: dict, camera: dict) -> dict:
    """`readable` without OpenCV: a pinhole camera (verify.camera's f_px)
    head on; the limit the nearer of READ_PX_PER_CELL and OpenCV's minimum
    outline (PERIMETER_RATE x the image's longest side). Standard library."""
    req = placed(req)
    d = _plan(req)
    w, h = (int(v) for v in camera["resolution"])
    distance = float(camera["distance_mm"])
    f_px = (w / 2.0) / math.tan(math.radians(float(camera["hfov_deg"])) / 2.0)
    cell = cell_mm(d)
    side = d["marker"]["marker_length_m"] * 1000.0
    lim = min(cell * f_px / READ_PX_PER_CELL, 4.0 * side * f_px / (PERIMETER_RATE * max(w, h)))
    return _readability(cell * f_px / distance, distance, lim, False)


def readable(req: dict, camera: dict) -> dict:
    if cv2 is None:
        return readable_analytic(req, camera)
    req = placed(req)
    d = _plan(req)
    cam = _C.Cam.of(camera)
    # a label beside the marker leaves the limit the marker's own; one ON it
    # (the default since 2026-10-20) is part of what the detector reads past
    on = _W.place_of(req.get("label") or {}) == "on_marker"
    lim = max_distance(d, _C.scene_of(d, _label(req, d) if on else None), cam)
    return _readability(_px_per_cell(d, cam), cam.distance_mm, lim, True)


# ------------------------------------------------------------ the reading range (V4, 2026-10-21)
#
# WHY its own reader, not _view: the engine needs only "did every id read",
# and _view also solves the pose (a second detectMarkers inside pnp.solve, and
# solvePnP), draws its notes and could draw the picture -- about a third of a
# far view's time for nothing. The ids are the same: detect.detect on the same
# simulated image with the same parameters (tests/web/test_web_verify_range.py
# holds the two to the same answer on every case).

def _geometry(d: dict, bounds) -> dict:
    return {"bounds_mm": [float(x) for x in bounds], "cell_mm": cell_mm(d),
            "marker_mm": d["marker"]["marker_length_m"] * 1000.0, "ids": list(d["ids"])}


def _bounds_stdlib(req: dict, d: dict) -> list:
    """The board's box in its pattern frame, label included, without numpy
    (scene_of's, near enough for the near end): the sticker, grown to the
    label's band (PlacedLabel.box, mapped back through pattern_to_sketch, a
    rotation or a reflection, so its inverse is its transpose)."""
    u0, v0, u1, v1 = (float(x) for x in d["guides"]["sticker"])
    if _W.flip_of(req):
        return [u0, v0, u1, v1]
    p = _W.plan(req)
    lab = p.get("label")
    if lab and lab.get("box"):
        M = p["pattern_to_sketch"]
        for x, y in lab["box"]:
            q = (x - M[3], y - M[7], -M[11])
            u = M[0] * q[0] + M[4] * q[1] + M[8] * q[2]
            v = M[1] * q[0] + M[5] * q[1] + M[9] * q[2]
            u0, v0, u1, v1 = min(u0, u), min(v0, v), max(u1, u), max(v1, v)
    return [u0, v0, u1, v1]


def _cv_reader(d: dict, scene, camera: dict):
    """read(distance_mm, view) -> (every id read, the ids missed): the plan
    rendered by verify.camera on this camera and read by OpenCV."""
    w, h = (int(v) for v in camera["resolution"])
    hfov = float(camera["hfov_deg"])
    want = set(int(i) for i in d["ids"])
    rasters = {}                                   # simulate's top views of this scene

    def read(distance_mm, view):
        v = _C.simulate(scene, _C.Cam(float(distance_mm), w, h, hfov), view, cache=rasters)
        got = set(int(i) for i in _C._det.detect(v.img, d, params=_C.parameters_for(v))["ids"])
        missing = sorted(want - got)
        return (not missing and not (got - want)), missing
    return read


def _range_setup(req: dict, camera, reader=None):
    """(geometry, camera, read, measured) for the engine. `reader`: "opencv",
    "analytic", or None (OpenCV when this Python has it, as readable does)."""
    if reader not in (None, "opencv", "analytic"):
        raise ValueError(f"reader {reader!r}: one of opencv, analytic")
    cam = _CAMS.camera_of(camera)
    req = placed(req)
    d = _plan(req)
    if reader == "opencv":
        _need_cv("the measured reading range")
    if reader != "analytic" and cv2 is not None:
        scene = _C.scene_of(d, _label(req, d))
        return _geometry(d, scene.bounds), cam, _cv_reader(d, scene, cam), True
    geo = _geometry(d, _bounds_stdlib(req, d))
    return geo, cam, _RR.analytic_reader(geo, cam), False


def _finish(out: dict, cam: dict, measured: bool) -> dict:
    out["measured"] = measured
    # WHY the version (measured 2026-10-21): the renderer's warps and blur
    # differ between OpenCV releases (5.0 in the repo's .venv, 4.11 in Pyodide
    # 314), and near the limits that moves a range up to 2x; with 4.11 in
    # CPython the browser's four ranges came out identical. A table says
    # which OpenCV drew it.
    out["opencv"] = cv2.__version__ if measured else None
    out["camera"]["id"] = cam["id"]
    out["camera"]["name"] = cam["name"]
    return out


def reading_range(req: dict, camera="d435", budget=None, cases=None, seed=None, reader=None) -> dict:
    """THE per-marker reading range (CPython or Pyodide, one call): `camera` a
    library id (core.cameras: "d435", "oakd12", ...) or {resolution, hfov_deg,
    focus_mm}; `budget` a name in reading_range.BUDGETS ("field"); `cases`
    per distance (48); `seed` the cases' (reading_range.SEED). -> the engine's
    answer (reading_range.result: near_mm, far_mm, band_mm, pm, near_by,
    far_limit, weakest_id, rows, renders, ...) + `measured` (OpenCV, or the
    pinhole model). The same bytes for the same inputs, every run."""
    geo, cam, read, measured = _range_setup(req, camera, reader)
    seed = _RR.SEED if seed is None else int(seed)
    out = _RR.run(_RR.sweep(geo, cam, budget or _RR.DEFAULT_BUDGET, int(cases or _RR.N_CASES), seed), read)
    return _finish(out, cam, measured)


def range_table(items: list, camera="d435", need=None, opencv=None, **kw) -> list:
    """The reading range of every marker in `items` -- PlanRequests, or
    {name, req, need} -- on one camera, judged against its requirement
    ({min_mm, max_mm}: the item's, else `need`): one row each, {name, ids,
    near_mm, far_mm, band_mm, pm, verdict, hints, range}. table_text()
    prints it.

    `opencv`: the ONE OpenCV that draws and reads every view -- a version
    ("5.0", "4.11") or a Python; None is the newest installed
    (opencv_choice.choose). Run here when it is this Python's, else in that
    Python. WHY one (Zach, 2026-10-21: "Let's only run one, but you can
    choose, and by default it should be the most recent one"; docs/peps/0003
    decision 3): two OpenCVs draw the same view differently and disagree near
    the limits, so a table is one OpenCV's, and says which. With
    reader="analytic" (the pinhole model) no OpenCV runs; nor when no Python
    here has one (the pinhole model, `measured` false, as reading_range)."""
    try:
        from . import opencv_choice as _OC
    except ImportError:                                    # the browser's zip: its worker's one OpenCV, here
        _OC = None
    if kw.get("reader") != "analytic" and _OC is not None:
        try:
            choice = _OC.choose(opencv)
        except ValueError:
            if opencv is not None:
                raise
            choice = None                                  # no OpenCV anywhere: the pinhole model
        if choice is not None and not _OC.is_here(choice):
            return _OC.call(choice, "aruco_studio.web_verify", "range_table", items, camera, need, choice["python"], **kw)
    rows = []
    for k, it in enumerate(items):
        req = it["req"] if isinstance(it, dict) and "req" in it else it
        name = (it.get("name") if isinstance(it, dict) and "req" in it else None) or f"Marker {k + 1}"
        want = (it.get("need") if isinstance(it, dict) and "req" in it else None) or need
        rr = reading_range(req, camera, **kw)
        j = _RR.judge(rr, want)
        rows.append({"name": name, "ids": rr["geometry"]["ids"], "near_mm": rr["near_mm"], "far_mm": rr["far_mm"],
                     "band_mm": rr["band_mm"], "pm": rr["pm"], "need": want, "verdict": j["verdict"],
                     "hints": j["hints"], "range": rr})
    return rows


def _m(mm) -> str:
    if mm is None:
        return "—"
    return f"{mm / 1000.0:.2f} m" if mm >= 1000.0 else f"{mm:.0f} mm"


def table_text(rows: list) -> str:
    """range_table's rows as a Markdown table; its first line names the camera
    and the one OpenCV that drew and read the views."""
    if not rows:
        return "(no markers)"
    cam = rows[0]["range"]["camera"]
    cv = rows[0]["range"].get("opencv")
    cvs = f"OpenCV {cv}" if cv else "the pinhole model (no OpenCV)"
    lines = [f"Camera: {cam.get('name')} ({cam['resolution'][0]}×{cam['resolution'][1]}, {cam['hfov_deg']:g}°)"
             f" · budget {rows[0]['range']['budget']['name']} · {rows[0]['range']['cases']} cases a distance"
             f" · {_RR.VERSION} · {cvs}", "",
             "| Marker | Ids | Reads from | Reads to (± 90 %) | Required | Verdict |", "|---|---|---|---|---|---|"]
    for r in rows:
        ids = r["ids"]
        idw = f"#{ids[0]}" if len(ids) == 1 else f"#{ids[0]}–{ids[-1]}"
        pm = "" if r["pm"] is None else f" ± {r['pm'] * 100:.0f} %"
        nd = r["need"] or {}
        req = "—" if not nd else f"{_m(nd.get('min_mm'))} – {_m(nd.get('max_mm'))}"
        verdict = (r["verdict"] or "—").upper() + ("" if not r["hints"] else ": " + " ".join(r["hints"]))
        lines.append(f"| {r['name']} | {idw} | {_m(r['near_mm'])} | {_m(r['far_mm']) + pm} | {req} | {verdict} |")
    return "\n".join(lines)


# the browser's worker runs a range in time slices: range_start, then
# range_step until done (each returns after about budget_ms, so a plan call
# waiting behind it waits one slice at most), or range_cancel
_JOBS: dict = {}
_SEQ = [0]
JOB_MAX = 16                # jobs kept at once; the oldest is dropped past it
STEP_MS = 250.0


def range_start(req: dict, camera="d435", budget=None, cases=None, seed=None, reader=None) -> dict:
    """A reading range to run in slices: -> {job, done false, phase, fraction, renders 0}."""
    geo, cam, read, measured = _range_setup(req, camera, reader)
    seed = _RR.SEED if seed is None else int(seed)
    gen = _RR.sweep(geo, cam, budget or _RR.DEFAULT_BUDGET, int(cases or _RR.N_CASES), seed)
    ask = next(gen)
    _SEQ[0] += 1
    job = f"range-{_SEQ[0]}"
    while len(_JOBS) >= JOB_MAX:
        _JOBS.pop(next(iter(_JOBS)))
    _JOBS[job] = {"gen": gen, "ask": ask, "read": read, "cam": cam, "measured": measured, "renders": 0, "ms": 0.0}
    return {"job": job, "done": False, "phase": ask["phase"], "fraction": round(ask["done"], 3), "renders": 0}


def range_step(job: str, budget_ms=STEP_MS) -> dict:
    """Read views for about `budget_ms` (one at least): -> {job, done, phase,
    fraction, renders, ms} or, at the end, {job, done true, result, renders,
    ms}. `ms` is this job's rendering time so far."""
    j = _JOBS.get(job)
    if j is None:
        raise ValueError(f"no reading-range job {job!r}: finished, cancelled or dropped")
    t0 = time.perf_counter()
    stop = t0 + max(0.0, float(budget_ms)) / 1000.0
    ask = j["ask"]
    try:
        while True:
            got = j["read"](ask["distance_mm"], ask["view"])
            j["renders"] += 1
            ask = j["gen"].send(got)
            if time.perf_counter() >= stop:
                break
    except StopIteration as fin:
        _JOBS.pop(job, None)
        ms = round(j["ms"] + (time.perf_counter() - t0) * 1000.0, 1)
        return {"job": job, "done": True, "result": _finish(fin.value, j["cam"], j["measured"]),
                "renders": j["renders"], "ms": ms}
    except Exception:
        _JOBS.pop(job, None)
        raise
    j["ask"] = ask
    j["ms"] += (time.perf_counter() - t0) * 1000.0
    return {"job": job, "done": False, "phase": ask["phase"], "fraction": round(ask["done"], 3),
            "renders": j["renders"], "ms": round(j["ms"], 1)}


def range_cancel(job: str) -> dict:
    return {"job": job, "cancelled": _JOBS.pop(job, None) is not None}


def main(argv=None) -> int:
    """python -m aruco_studio.web_verify requests.json [--camera d435] [--need 300:2000] [--opencv 5.0] [--analytic] [--json]:
    the reading range of each marker in the file (a list of PlanRequests, or of
    {name, req, need}) as a table, on one OpenCV (the newest installed unless --opencv)."""
    import argparse
    ap = argparse.ArgumentParser(prog="python -m aruco_studio.web_verify", description=main.__doc__.split("\n")[0])
    ap.add_argument("requests", help="a JSON file: [PlanRequest, ...] or [{name, req, need}, ...]")
    ap.add_argument("--camera", default=_CAMS.DEFAULT, help="a library id (" + ", ".join(c["id"] for c in _CAMS.CAMERAS) + ")")
    ap.add_argument("--need", help="the required distance for every marker without its own, min:max in mm (either may be empty)")
    ap.add_argument("--opencv", metavar="VERSION|PYTHON",
                    help="the one OpenCV that draws and reads the views: a version (5.0, 4.11: the browser's, "
                         "tools/requirements-browser-opencv.txt) or a Python; default: the newest installed "
                         "(python -m aruco_studio.opencv_choice lists them)")
    ap.add_argument("--analytic", action="store_true", help="the pinhole model instead of OpenCV")
    ap.add_argument("--json", action="store_true", help="print the rows as JSON")
    a = ap.parse_args(argv)
    with open(a.requests, encoding="utf-8") as f:
        items = json.load(f)
    need = None
    if a.need:
        lo, _, hi = a.need.partition(":")
        need = {"min_mm": float(lo) if lo else None, "max_mm": float(hi) if hi else None}
    try:
        rows = range_table(items, a.camera, need, opencv=a.opencv, reader="analytic" if a.analytic else None)
    except ValueError as e:
        sys.stderr.write(f"{e}\n")
        return 2
    sys.stdout.write((json.dumps(rows, indent=1) if a.json else table_text(rows)) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
