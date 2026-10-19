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
"""
from __future__ import annotations

import base64
import math

from . import web_api as _W
from .core import dictionary as _D

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


def _plan(req: dict):
    d, _issues = _W._plan(req)
    if not d["ok"]:
        raise ValueError("nothing to verify: " + "; ".join(d["errors"]))
    return d


def _label(req: dict, d: dict):
    """The sketch's label in the pattern frame (verify.camera.scene_of), or
    None (off, or Flip: the marker then faces away from its sketch text)."""
    m = req["marker"]
    flip = bool(m.get("flip")) and not req.get("reference_face")
    lab = _W.placed_label(req, d["layout"]["kind"], d["marker"]["dictionary"], d["ids"])
    if lab is None or flip:
        return None
    M = np.array(_W.sketch_of_pattern(req["rect"], d, False), np.float64).reshape(4, 4)
    Mi = np.linalg.inv(M)
    at = Mi @ np.array([lab["at"][0], lab["at"][1], 0.0, 1.0])
    a = math.radians(lab["angle_deg"])
    dr = Mi[:3, :3] @ np.array([math.cos(a), math.sin(a), 0.0])
    return {"text": lab["text"], "at": (float(at[0]), float(at[1])),
            "height_mm": float(lab["height_mm"]), "dir": (float(dr[0]), float(dr[1])),
            "width_mm": _W.text_width(lab["text"], lab["height_mm"])}


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
           "image_png_base64": "", "notes": notes}
    if picture:
        ok, png = cv2.imencode(".png", _C.picture(v, d, got, missing, PNG_MAX_W))
        out["image_png_base64"] = base64.b64encode(png.tobytes()).decode("ascii") if ok else ""
    return out


def _need_cv(what: str) -> None:
    if cv2 is None:
        raise ImportError(f"{what} needs numpy and OpenCV, which this Python does not have")


def verify(req: dict, view: dict) -> dict:
    _need_cv("verify")
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
            "text": text, "measured": measured}


def readable_analytic(req: dict, camera: dict) -> dict:
    """`readable` without OpenCV: a pinhole camera (verify.camera's f_px)
    head on; the limit the nearer of READ_PX_PER_CELL and OpenCV's minimum
    outline (PERIMETER_RATE x the image's longest side). Standard library."""
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
    d = _plan(req)
    cam = _C.Cam.of(camera)
    # the label is beside the marker, not on it: the limit is the marker's own
    lim = max_distance(d, _C.scene_of(d), cam)
    return _readability(_px_per_cell(d, cam), cam.distance_mm, lim, True)
