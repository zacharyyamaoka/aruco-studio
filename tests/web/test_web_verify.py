"""Verify accuracy (aruco_studio/web_verify.py) under CPython with the real
OpenCV: the plan as a camera sees it, read back by OpenCV's own detector,
posed against the plan's OpenCV frame; and `readable`'s measured limit
against `verify` itself. The same calls run in Pyodide (opencv-python from
Pyodide's CDN) in the lane's browser proof."""
from __future__ import annotations

import base64
import copy
import json
import math

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from aruco_studio import web_api as W                      # noqa: E402
from aruco_studio import web_verify as V                   # noqa: E402

# the inkjet preset without the cell snap: typed sizes exactly as typed
INK_NO_SNAP = dict(copy.deepcopy(next(p for p in W.presets()
                                     if p["name"] == "Inkjet · Letter vinyl")), cell_step_mm=0.0)


def req(marker=None, rect=None, label=None, pre=None, face=False):
    """A PlanRequest (tests/web/test_web_api.py's)."""
    m = {"type": "single", "dictionary": "DICT_4X4_50", "first_id": 0, "auto": True,
         "marker_mm": 0.0, "checker_mm": 0.0, "separation_mm": 0.0, "cols": 1, "rows": 1,
         "turn": 0, "flip": False, "quiet_modules": 1.0, "corner_mark": "none"}
    m.update(marker or {})
    lb = {"on": False, "text": "", "height_mm": 0.0, "side": "below", "gap_mm": 2.0,
          "offset_mm": [0.0, 0.0]}
    lb.update(label or {})
    return {"rect": dict({"cx": 0.0, "cy": 0.0, "w": 20.0, "h": 20.0, "angle_deg": 0.0},
                         **(rect or {})),
            "marker": m, "label": lb, "preset": pre or INK_NO_SNAP, "reference_face": face}


CAM = {"distance_mm": 300.0, "resolution": [1920, 1080], "hfov_deg": 70.0}


def view(camera=None, **kw):
    v = {"camera": dict(CAM, **(camera or {})), "tilt_deg": 0.0, "yaw_deg": 0.0, "blur_px": 0.0,
         "noise": 0.0, "glare": 0.0, "occlusion": 0.0, "seed": 1}
    v.update(kw)
    return v


def single(mm=30.0, **m):
    return req(dict({"auto": False, "marker_mm": mm}, **m), rect={"w": mm + 10.0, "h": mm + 10.0},
               pre=INK_NO_SNAP)


GRID = req({"type": "grid", "cols": 2, "rows": 3}, rect={"w": 60.0, "h": 90.0}, pre=INK_NO_SNAP)
CHARUCO = req({"type": "charuco", "cols": 5, "rows": 4}, rect={"w": 100.0, "h": 80.0},
              pre=INK_NO_SNAP)


def png(out):
    raw = base64.b64decode(out["image_png_base64"])
    img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    assert img is not None
    return img


# ------------------------------------------------------------------ verify: clean views

def test_a_clean_single_reads_with_its_pose():
    out = V.verify(single(first_id=7), view())
    assert out["found"] == [7] and out["missing"] == [] and out["wrong"] == []
    assert out["ok"]
    assert out["pose_error_mm"] < 2.0 and out["pose_error_deg"] < 2.0, out
    # 5 mm cells (30 mm / 6 modules) x f 1371 px / 300 mm
    f = 960.0 / math.tan(math.radians(35.0))
    assert out["px_per_cell"] == pytest.approx(5.0 * f / 300.0, abs=1e-3)
    assert png(out).shape[1] <= V.PNG_MAX_W


def test_a_2x3_grid_reads_all_six():
    out = V.verify(GRID, view())
    assert out["found"] == [0, 1, 2, 3, 4, 5] and out["missing"] == [] and out["wrong"] == []
    assert out["ok"] and out["pose_error_mm"] is not None


def test_a_charuco_5x4_reads_its_markers_and_poses():
    out = V.verify(CHARUCO, view())
    assert out["found"] == list(range(10)) and out["wrong"] == []
    assert out["pose_error_mm"] is not None and out["pose_error_deg"] is not None
    assert out["pose_error_mm"] < 2.0 and out["pose_error_deg"] < 2.0, out


@pytest.mark.parametrize("side", ["below", "above", "left", "right"])
def test_label_and_corner_mark_do_not_read_as_markers(side):
    """The label beside the marker and the corner triangle (Zach's 'where
    should the label / black corner go') never read as an id."""
    r = single(corner_mark="triangle")
    r["label"].update(on=True, text="{type} #{id}", side=side, height_mm=5.0)
    out = V.verify(r, view(tilt_deg=20.0, yaw_deg=-15.0))
    assert out["found"] == [0] and out["wrong"] == [], out


def test_a_60_degree_tilt_still_reads_the_single():
    out = V.verify(single(), view(tilt_deg=60.0))
    assert out["found"] == [0] and out["wrong"] == []


def test_yaw_and_turned_rect_read():
    r = single()
    r["rect"]["angle_deg"] = 30.0
    r["marker"]["turn"] = 90
    out = V.verify(r, view(yaw_deg=40.0))
    assert out["found"] == [0] and out["wrong"] == []


# ------------------------------------------------------------------ verify: degraded views

def test_heavy_occlusion_loses_an_id_on_a_grid():
    out = V.verify(GRID, view(occlusion=0.6))
    assert out["missing"], out
    assert not out["ok"]
    assert out["wrong"] == []


def test_glare_blur_and_noise_are_applied():
    clean = V.verify(single(), view())
    rough = V.verify(single(), view(glare=0.8, blur_px=2.0, noise=0.5))
    assert rough["image_png_base64"] != clean["image_png_base64"]


def test_the_same_seed_gives_the_same_view_another_seed_another():
    v = view(tilt_deg=35.0, blur_px=1.0, noise=0.3, glare=0.5, occlusion=0.3, seed=11)
    a, b = V.verify(GRID, v), V.verify(GRID, v)
    assert a == b
    c = V.verify(GRID, dict(v, seed=12))
    assert c["image_png_base64"] != a["image_png_base64"]


def test_too_far_says_why():
    out = V.verify(single(), view(camera={"distance_mm": 6000.0}))
    assert out["missing"] == [0] and not out["ok"]
    assert out["pose_error_mm"] is None
    assert any("OpenCV's default skips outlines" in n for n in out["notes"]), out["notes"]


def test_through_the_worker_entry():
    got = json.loads(W.call("verify", json.dumps({"req": single(), "view": view()})))
    assert got["result"]["found"] == [0]
    got = json.loads(W.call("readable", json.dumps({"req": single(), "camera": CAM})))
    assert set(got["result"]) == {"px_per_cell", "max_distance_mm", "verdict", "text", "measured"}
    assert got["result"]["measured"] is True
    assert "error" in json.loads(W.call("verify", json.dumps({"req": {}, "view": view()})))


# ------------------------------------------------------------------ readable

@pytest.fixture(scope="module")
def limits():
    return {mm: V.readable(single(mm), CAM) for mm in (30.0, 60.0)}


def test_readable_is_measured_and_monotone_in_size(limits):
    small, big = limits[30.0]["max_distance_mm"], limits[60.0]["max_distance_mm"]
    assert small > 300.0
    assert big >= 1.8 * small, (small, big)


@pytest.mark.parametrize("mm", [30.0, 60.0])
def test_readable_agrees_with_verify(limits, mm):
    lim = limits[mm]["max_distance_mm"]
    near = V.verify(single(mm), dict(V.READ_VIEW, camera=dict(CAM, distance_mm=0.9 * lim)))
    far = V.verify(single(mm), dict(V.READ_VIEW, camera=dict(CAM, distance_mm=1.3 * lim)))
    assert near["found"] == [0], (lim, near)
    assert far["missing"] == [0], (lim, far)


def test_readable_text_and_verdicts(limits):
    r = limits[30.0]
    assert r["verdict"] == "good"
    assert r["px_per_cell"] == pytest.approx(V.verify(single(), view())["px_per_cell"])
    assert r["text"].startswith(f"{r['px_per_cell']:.1f} px per cell at 300 mm: reads reliably")
    lim = r["max_distance_mm"]
    assert V.readable(single(), dict(CAM, distance_mm=0.8 * lim))["verdict"] == "marginal"
    poor = V.readable(single(), dict(CAM, distance_mm=1.2 * lim))
    assert poor["verdict"] == "poor" and "will not read" in poor["text"]
    assert V.verdict_of(V.FIELD_SHARE * lim, lim) == "good"


def test_good_still_reads_in_the_field(limits):
    """FIELD_SHARE's claim for the 4x4 single at 1080p: at that share of the
    head-on limit a 45 deg tilt, 1 px blur and grain still read it."""
    lim = limits[30.0]["max_distance_mm"]
    for seed in range(5):
        v = dict(V.FIELD_VIEW, seed=seed, camera=dict(CAM, distance_mm=V.FIELD_SHARE * lim))
        out = V.verify(single(), v)
        assert out["found"] == [0] and out["wrong"] == [], (seed, out)


def test_a_two_line_label_sits_in_its_band_below_the_marker_and_is_all_in_view():
    # 2026-10-18: Verify drew a two-line label as one line with "?" (Hershey's
    # "\n") and over the marker (it planned the marker in the whole rectangle
    # while the label sat in its band inside it).
    r = single(mm=0.0, auto=True)
    r = dict(r, rect={"cx": 0.0, "cy": 0.0, "w": 60.0, "h": 70.0, "angle_deg": 0.0},
             label={"on": True, "text": "PLATE\n#{ids}", "height_mm": 6.0, "side": "below",
                    "gap_mm": 2.0, "offset_mm": [0.0, 0.0]})
    d = V._plan(r)
    lab = V._label(r, d)
    u0, v0, u1, v1 = d["guides"]["sticker"]                     # the marker's outline, pattern frame
    lines = lab["text"].split("\n")
    assert len(lines) == 2
    top_of_text = lab["at"][1] + (len(lines) - 1) * 0.7 * lab["height_mm"] + lab["height_mm"] / 2.0
    assert top_of_text <= v0 + 1e-6, "the label block clears the marker's outline"
    corners = __import__("aruco_studio.verify.camera", fromlist=["x"]).label_corners(lab)
    assert min(c[1] for c in corners) < lab["at"][1] - 1.4 * lab["height_mm"] / 2.0   # both lines in the crop
    got = V.verify(r, view())
    assert got["found"] == W.plan(r)["ids"] and not got["wrong"]
