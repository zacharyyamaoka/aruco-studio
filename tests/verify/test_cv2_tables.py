"""M2b.2: the core against OpenCV ITSELF, not REF's table.

* every id of every dictionary: core.dictionary.marker_grid ==
  cv2.aruco.generateImageMarker (9,596 markers);
* boards: core.board.black_rects_m rasterised == cv2.aruco Board.generateImage
  pixel for pixel, at integer px per module (REF tools/verify_aruco_boards.py
  part a: its spread of grids and ChArUco boards, odd / even, legacy, first
  ids not 0), plus every board of goldens/board.json whose lengths are whole
  pixels at 10 px per module; object points, ChArUco corners and ids ==
  getObjPoints / getChessboardCorners / getIds.
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from aruco_studio.core import board as B
from aruco_studio.core import dictionary as D
from aruco_studio.core.board import BoardSpec

ROOT = Path(__file__).resolve().parents[2]
S = 10000.0              # px per metre: spec lengths = px / S


def cv_dict(name):
    return cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, name))


@pytest.mark.parametrize("name", D.DICTIONARY_NAMES)
def test_every_marker_of_every_dictionary_is_opencvs(name):
    d = cv_dict(name)
    info = D.dictionary_info(name)
    n = info["bits"] + 2
    bad = []
    for mid in range(info["capacity"]):
        img = cv2.aruco.generateImageMarker(d, mid, n * 10, borderBits=1)
        cv = (img.reshape(n, 10, n, 10)[:, 5, :, 5] < 128).astype(int).tolist()
        if D.marker_grid(name, mid) != cv:
            bad.append(mid)
    assert not bad, (name, bad[:10])
    assert info["bits"] == d.markerSize


def test_9596_markers_in_all():
    assert sum(D.dictionary_info(n)["capacity"] for n in D.DICTIONARY_NAMES) == 9596


GRIDS = [(3, 2, "DICT_4X4_50", 10, 5, 10), (2, 3, "DICT_6X6_250", 0, 4, 8),
         (4, 5, "DICT_APRILTAG_36h11", 100, 3, 6), (1, 4, "DICT_5X5_100", 90, 4, 4),
         (5, 5, "DICT_7X7_1000", 975, 3, 9), (3, 3, "DICT_ARUCO_ORIGINAL", 1000, 3, 5)]
CHARUCOS = [(5, 4, "DICT_4X4_50", 0, 5, 40, False), (5, 4, "DICT_4X4_50", 0, 5, 40, True),
            (5, 7, "DICT_5X5_100", 20, 4, 40, False), (5, 7, "DICT_5X5_100", 20, 4, 40, True),
            (4, 5, "DICT_6X6_250", 7, 4, 48, True), (6, 6, "DICT_APRILTAG_36h11", 300, 3, 36, False),
            (6, 6, "DICT_APRILTAG_36h11", 300, 3, 36, True), (3, 3, "DICT_ARUCO_ORIGINAL", 1015, 3, 31, False),
            (3, 4, "DICT_4X4_250", 200, 4, 32, False), (3, 4, "DICT_4X4_250", 200, 4, 32, True),
            (7, 5, "DICT_7X7_100", 50, 3, 37, False)]


def spread():
    out = []
    for cols, rows, name, first, k, sep in GRIDS:
        n = cv_dict(name).markerSize
        out.append(BoardSpec("grid", name, first, (n + 2) * k / S, rows=rows, cols=cols,
                             separation_m=sep / S))
    for cols, rows, name, first, k, sq, legacy in CHARUCOS:
        n = cv_dict(name).markerSize
        out.append(BoardSpec("charuco", name, first, (n + 2) * k / S, rows=rows, cols=cols,
                             square_length_m=sq / S, legacy=legacy))
    return out


def from_golden():
    """The boards of goldens/board.json, scaled so a module is 10 px, when
    every length is then a whole number of pixels."""
    out = []
    data = json.loads((ROOT / "goldens" / "board.json").read_text(encoding="utf-8"))
    for c in data["cases"]:
        i = c["in"]
        if i.get("layout") not in ("grid", "charuco"):
            continue
        try:
            sp = BoardSpec(i["layout"], i["dictionary"], int(i["first_id"]), float(i["marker_length_m"]),
                           rows=int(i["rows"]), cols=int(i["cols"]),
                           separation_m=float(i.get("separation_m") or 0.0),
                           square_length_m=float(i.get("square_length_m") or 0.0),
                           legacy=bool(i.get("legacy")))
            B.check_spec(sp)
        except Exception:                          # noqa: BLE001  (the golden's refusals)
            continue
        n = D.dictionary_info(sp.dictionary)["bits"] + 2
        px_per_m = 10.0 * n / sp.marker_length_m
        lengths = [sp.marker_length_m, sp.separation_m, sp.square_length_m]
        if all(abs(v * px_per_m - round(v * px_per_m)) < 1e-6 for v in lengths):
            out.append((sp, px_per_m))
    return out


def cv_board(spec, unit=1.0):
    d = cv_dict(spec.dictionary)
    ids = np.array(B.ids(spec), np.int32)
    if spec.layout == "grid":
        return cv2.aruco.GridBoard((spec.cols, spec.rows), spec.marker_length_m * unit,
                                   spec.separation_m * unit, d, ids)
    board = cv2.aruco.CharucoBoard((spec.cols, spec.rows), spec.square_length_m * unit,
                                   spec.marker_length_m * unit, d, ids)
    board.setLegacyPattern(bool(spec.legacy))
    return board


def numpy_raster(spec, px_per_m):
    """REF verify_aruco_boards.numpy_raster: black_rects_m sampled at the
    pixel centres (half-open edges as generateImage draws them)."""
    w, h = B.extent_m(spec)
    W, H = int(round(w * px_per_m)), int(round(h * px_per_m))
    xs = (np.arange(W) + 0.5) / px_per_m - w / 2.0
    ys = h / 2.0 - (np.arange(H) + 0.5) / px_per_m
    ink = np.zeros((H, W), bool)
    for x0, y0, x1, y1 in B.black_rects_m(spec):
        cols = (xs >= x0) & (xs < x1)
        rows = (ys > y0) & (ys <= y1)
        ink |= rows[:, None] & cols[None, :]
    return ink


def _check(spec, px_per_m):
    board = cv_board(spec, px_per_m)
    w, h = B.extent_m(spec)
    W, H = int(round(w * px_per_m)), int(round(h * px_per_m))
    ref = board.generateImage((W, H), marginSize=0, borderBits=1) < 128
    mine = numpy_raster(spec, px_per_m)
    assert ref.shape == mine.shape and np.count_nonzero(ref != mine) == 0, spec
    bm = cv_board(spec, 1.0)
    cv_ids = [int(v) for v in np.asarray(bm.getIds()).ravel()]
    assert cv_ids == B.ids(spec)
    ours = B.object_points(spec)
    cv_obj = [np.asarray(o, np.float64).reshape(4, 3) for o in bm.getObjPoints()]
    assert max(float(np.max(np.abs(cv_obj[i] - np.array(ours[m])))) for i, m in
               enumerate(cv_ids)) < 1e-6          # cv2 keeps float32 (REF: 1e-6)
    if spec.layout == "charuco":
        cc = np.asarray(bm.getChessboardCorners(), np.float64).reshape(-1, 3)
        assert float(np.max(np.abs(cc - np.array(B.charuco_corners(spec))))) < 1e-6


@pytest.mark.parametrize("spec", spread(), ids=lambda s: f"{s.layout}-{s.dictionary}-{s.cols}x"
                         f"{s.rows}-{s.first_id}{'-legacy' if s.legacy else ''}")
def test_board_ink_is_generate_image(spec):
    _check(spec, S)


def test_every_board_of_the_golden_table_that_is_whole_pixels():
    cases = from_golden()
    assert len(cases) >= 10, len(cases)
    for spec, px_per_m in cases:
        _check(spec, px_per_m)
