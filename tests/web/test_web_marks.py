"""Verify's label and corner-mark check (aruco_studio/web_marks.py) under
CPython with the real OpenCV: the same plan read marked and bare through
the same views, so what differs is the marks' doing. The guide "Label
placement" (docs/build_guides.py) is this check's output."""
from __future__ import annotations

import copy

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from aruco_studio import opencv_choice as OC              # noqa: E402
from aruco_studio import web_api as W                      # noqa: E402
from aruco_studio import web_marks as M                    # noqa: E402
from aruco_studio import web_verify as V                   # noqa: E402

# the default detector (docs/peps/0003 decision 3): the newest OpenCV installed here
DEFAULT_CV = OC.choose()

INK = copy.deepcopy(next(p for p in W.presets() if p["name"] == "Inkjet · Letter vinyl"))
CELL = 22.0 / 6.0                    # the 4x4 single's module in a 30 mm square (22 mm marker)


def req(marker=None, label=None, w=30.0, h=30.0):
    """A rectangle profile with one marker, as the Studio sends it."""
    m = {"type": "single", "dictionary": "DICT_4X4_50", "first_id": 7, "auto": True,
         "marker_mm": 30.0, "checker_mm": 0.0, "separation_mm": 0.0, "cols": 1, "rows": 1,
         "turn": 0, "flip": False, "quiet_modules": 1, "corner_mark": "none"}
    m.update(marker or {})
    lb = {"on": False, "text": "#{ids}", "height_mm": 0.0, "side": "below", "gap_mm": 2.0,
          "offset_mm": [0.0, 0.0]}
    lb.update(label or {})
    loop = [[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2], [-w / 2, h / 2]]
    return {"trim": "profile", "profile": {"loops": [loop]}, "holes": "avoid", "marker": m,
            "label": lb, "preset": INK, "reference_face": False, "extrude": {}}


ON_BLACK = {"on": True, "place": "on_marker", "surface": "black"}
# a quick grid for the cheap cases: sharp (8 px per cell and up, blur 1 px and under) and not
QUICK = {"px_per_cell": [4.0, 8.0, 13.0, 16.0], "blur_px": [0.5, 1.0, 2.0], "seeds": 2}


def test_the_sign_test():
    assert M.sign_p(0, 0) == 1.0
    assert M.sign_p(5, 0) == pytest.approx(0.0625)
    assert M.sign_p(0, 6) == pytest.approx(0.03125)
    assert M.sign_p(3, 3) == 1.0


def test_the_verdict_lines():
    assert M.verdict_of(12.0, 0.001, 0, 64) == "unsafe"
    assert M.verdict_of(3.0, 0.01, 0, 64) == "marginal"
    assert M.verdict_of(3.0, 0.2, 0, 64) == "safe"        # could be chance
    assert M.verdict_of(0.5, 0.001, 0, 64) == "safe"      # too small to matter
    assert M.verdict_of(0.4, 1.0, 2, 64) == "unsafe"      # two of 64 easy reads lost: 3 %
    assert M.verdict_of(0.4, 1.0, 1, 64) == "safe"        # one is not a pattern
    assert M.verdict_of(0.4, 1.0, 2, 640) == "safe"       # two of a board's 640 easy reads: 0.3 %
    assert M.pose_verdict(0.6, 0.002, 75, 41) == "marginal"
    assert M.pose_verdict(1.7, 0.0002, 13, 0) == "unsafe"
    assert M.pose_verdict(0.6, 0.002, 41, 75) == "safe"   # a better pose never counts against it
    assert M.worst("safe", "marginal") == "marginal"


def test_nothing_to_cost_without_a_label_or_a_corner_mark():
    o = M.check(req(), grid=QUICK)
    assert (o["label"], o["corner_mark"]) == (False, False)
    assert o["views"] == 4 * 3 * 2 * 2
    assert o["lost"] == o["gained"] == 0 and o["reads"]["marked"] == o["reads"]["bare"]
    assert o["verdict"] == "safe" and "nothing to cost" in o["text"]


def test_the_pair_differs_only_where_the_label_is():
    """The bare scene keeps the marked one's crop and grain: outside the
    label's own box the two sensor images are the same pixel for pixel."""
    r = V.placed(req(label=dict(ON_BLACK, side="left")))
    d = V._plan(r)
    lab = V._label(r, d)
    marked = V._C.scene_of(d, lab)
    bare = V._C.Scene(M.bare_plan(d), marked.bounds, marked.centre, marked.area, None)
    view = {"camera": {"distance_mm": 400.0, "resolution": [1920, 1080], "hfov_deg": 70.0},
            "tilt_deg": 30.0, "yaw_deg": 0.0, "blur_px": 1.0, "noise": 0.1, "glare": 0.0,
            "occlusion": 0.0, "seed": 3}
    cam = V._C.Cam.of(view["camera"])
    a, b = V._C.simulate(marked, cam, view), V._C.simulate(bare, cam, view)
    assert a.img.shape == b.img.shape and a.offset == b.offset
    diff = a.img != b.img
    assert diff.any(), "the label is drawn"
    box = V._C._project(a.H, V._C.label_corners(lab))
    x0, y0 = np.floor(box.min(axis=0)).astype(int) - 4
    x1, y1 = np.ceil(box.max(axis=0)).astype(int) + 4
    diff[max(0, y0):y1, max(0, x0):x1] = False
    assert not diff.any(), "the images differ only round the label"


def test_letters_a_cell_tall_in_the_border_row_are_unsafe_half_a_cell_safe():
    """The gate can fail: the Studio's own cap (half a module) costs nothing,
    a cap of a whole module knocks the border row out and loses sharp views."""
    tall = M.check(req(label=dict(ON_BLACK, height_mm=CELL)), grid=QUICK)
    assert tall["verdict"] == "unsafe" and tall["easy"]["lost"] >= M.EASY_MIN
    assert tall["lost"] > tall["gained"]
    assert all(set(v) >= {"camera", "tilt_deg", "blur_px", "seed"} for v in tall["views_lost"])
    ok = M.check(req(label=ON_BLACK), grid=QUICK)
    assert ok["label"] and ok["verdict"] == "safe" and ok["easy"]["lost"] == 0


def test_a_lost_view_is_one_verify_shows_lost():
    o = M.check(req(label=dict(ON_BLACK, height_mm=CELL)), grid=QUICK)
    v = o["views_lost"][0]
    assert not V.verify(req(label=dict(ON_BLACK, height_mm=CELL)), v)["ok"]


def test_the_corner_triangle_costs_nothing():
    o = M.check(req(marker={"corner_mark": "triangle"}))
    assert (o["label"], o["corner_mark"]) == (False, True)
    assert o["verdict"] == "safe"


def test_a_label_run_into_the_corner_cells_moves_the_pose():
    """Knocked out of the black past the border row's end, the letters move
    the marker's corners: the pose is worse wherever it was sharp.

    VERSION-SPECIFIC, so it runs on the default detector (DEFAULT_CV): on
    OpenCV 5.0 the pose is worse in 13 of 14 sharp views (unsafe); on 4.11
    (the browser's) worse in 9 and better in 5 of 15, which a sign test cannot
    tell from chance, so it calls the label safe (measured 2026-10-21; the
    two disagree near the limits, docs/peps/0003)."""
    o = OC.call(DEFAULT_CV, "aruco_studio.web_marks", "check", req(label=dict(ON_BLACK, text="#{ids} {dict} {type}")))
    assert o["opencv"] == DEFAULT_CV["opencv"]
    assert o["pose"]["judged"] and o["pose"]["worse"] > o["pose"]["better"]
    assert o["verdict"] in ("marginal", "unsafe")


def test_a_board_counts_each_of_its_markers():
    """A read is an id in a view: a 2 x 2 grid has four in every view."""
    o = M.check(req(marker={"type": "grid", "cols": 2, "rows": 2}, label=ON_BLACK, w=60.0, h=60.0), grid=QUICK)
    assert o["ids"] == 4
    assert o["reads"]["bare"] <= 4 * o["views"] and o["reads"]["bare"] > o["views"]
    assert all(c[2] == 4 * 2 * 2 for row in o["map"] for c in row)


def test_the_result_is_versioned_and_says_its_grid():
    o = M.check(req(label=ON_BLACK), grid=QUICK)
    assert o["version"] == M.VERSION
    assert o["grid"]["px_per_cell"] == QUICK["px_per_cell"]
    assert len(o["map"]) == 4 and len(o["map"][0]) == 3
    assert sum(c[0] for row in o["map"] for c in row) == o["reads"]["marked"]
    assert sum(c[1] for row in o["map"] for c in row) == o["reads"]["bare"]
