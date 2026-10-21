"""A SET value is always honoured, Auto or not (contract barrier 7, Zach
2026-10-20: "We should always have complete control if we want, and it
should always display what we want even if it wouldn't print properly or
would go outside the rectangle"). His screenshot: a ChArUco checker typed
as 20 mm with Auto on was dropped and the board drew 15.41 mm. Measured on
the plan the facade returns; the same requests run in Pyodide in
web/scripts/parity.d/label_place.mjs."""
from __future__ import annotations

import copy

import pytest

from aruco_studio import web_api as W


def preset(name, **kw):
    p = copy.deepcopy(next(x for x in W.presets() if x["name"] == name))
    p.update(kw)
    return p


INK = preset("Inkjet · Letter vinyl")
INK_NO_SNAP = preset("Inkjet · Letter vinyl", cell_step_mm=0.0)
INK_DOTS = preset("Inkjet · Letter vinyl", cell_step_mm=0.042333)   # before cells rule 2
D3 = preset("Default")


def req(marker=None, rect=None, pre=None):
    m = {"type": "single", "dictionary": "DICT_4X4_50", "first_id": 0, "auto": True,
         "marker_mm": 30.0, "checker_mm": 0.0, "separation_mm": 0.0, "cols": 1, "rows": 1,
         "turn": 0, "flip": False, "quiet_modules": 1.0, "corner_mark": "none"}
    m.update(marker or {})
    return {"rect": dict({"cx": 0.0, "cy": 0.0, "w": 61.6, "h": 77.0, "angle_deg": 0.0}, **(rect or {})),
            "marker": m, "label": {"on": False, "text": "", "height_mm": 0.0, "side": "below",
                                   "gap_mm": 2.0, "offset_mm": [0.0, 0.0]},
            "preset": pre or INK, "reference_face": False}


def red(p, field="marker.marker_mm"):
    return [w for w in p["warnings"] if w["field"] == field and w["level"] == "error"]


CHARUCO = {"type": "charuco", "cols": 5, "rows": 4, "first_id": 35, "turn": 90}


@pytest.mark.parametrize("pre", [D3, INK_NO_SNAP], ids=["3d", "inkjet-no-snap"])
def test_a_typed_checker_with_auto_is_drawn_as_typed(pre):
    """Zach's board: 5 x 4 ChArUco in the 61.6 x 77 mm rectangle, Auto on,
    checker typed 20 mm: drawn at 20 mm, the marker the core's ratio for it
    (the largest that leaves a module of white in the square), the overhang
    flagged red; the rectangle is left as it is."""
    p = W.plan(req(dict(CHARUCO, checker_mm=20.0), pre=pre))
    assert p["ok"] and p["auto"]
    assert p["checker_mm"] == 20.0
    assert p["marker_mm"] == 15.0                     # 4x4: 6 modules + 2 of white = 20 mm, 0.5 mm steps
    assert sorted(p["outer_mm"]) == [80.0, 100.0]      # 5 x 4 squares of 20
    assert p["overflow_mm"] > 0 and red(p)
    fields = {d["field"]: d["value_mm"] for d in p["dims"]}
    assert fields["marker.checker_mm"] == 20.0         # the canvas shows what is drawn
    # a checker that fits is drawn as typed with nothing red
    fit = W.plan(req(dict(CHARUCO, checker_mm=12.0), pre=pre))
    assert fit["checker_mm"] == 12.0 and fit["overflow_mm"] == 0.0 and not red(fit)
    # and Auto alone still fills the rectangle
    auto = W.plan(req(CHARUCO, pre=pre))
    assert auto["checker_mm"] != 20.0 and auto["overflow_mm"] == 0.0


def test_a_typed_checker_with_auto_on_the_dot_grid_is_snapped_and_said():
    """The inkjet preset's cells are whole printer dots (cell_step_mm, the
    contract's "cells snap to multiples of this"): a typed checker off that
    grid is drawn on it and SAID (a note on the checker's row), never dropped;
    one on the grid is drawn exactly."""
    p = W.plan(req(dict(CHARUCO, checker_mm=20.0), pre=INK_DOTS))
    assert abs(p["checker_mm"] - 20.0) < 0.05 and p["checker_mm"] != 15.41
    assert any(w["field"] == "marker.checker_mm" and "20.0 mm →" in w["text"] for w in p["warnings"])
    on_grid = W.plan(req(dict(CHARUCO, checker_mm=p["checker_mm"]), pre=INK_DOTS))
    assert on_grid["checker_mm"] == p["checker_mm"]


@pytest.mark.parametrize("pre", [D3, INK], ids=["3d", "inkjet"])
def test_a_typed_separation_with_auto_is_drawn_as_typed(pre):
    grid = {"type": "grid", "cols": 3, "rows": 2}
    p = W.plan(req(dict(grid, separation_mm=5.0), {"w": 60.0, "h": 40.0}, pre))
    assert p["ok"] and p["auto"] and p["separation_mm"] == 5.0 and p["overflow_mm"] == 0.0
    marks = sorted(round(min(q[0] for q in poly["outer"]), 6) for poly in p["black"]
                   if abs(max(q[1] for q in poly["outer"]) - max(q[1] for poly2 in p["black"]
                                                              for q in poly2["outer"])) < 1e-6)
    gaps = {round(b - a - p["marker_mm"], 5) for a, b in zip(marks, marks[1:])}
    assert gaps == {5.0}                                # measured on the black, not the field
    # a separation that leaves no room for any marker: still drawn as typed,
    # with the smallest marker the preset prints well, overhang flagged red
    big = W.plan(req(dict(grid, separation_mm=30.0), {"w": 60.0, "h": 40.0}, pre))
    assert big["ok"] and big["separation_mm"] == 30.0
    assert big["overflow_mm"] > 0 and red(big)
    assert big["cell_mm"] >= {"inkjet": 1.0, "print3d": 2.0}[pre["method"]] - 1e-9
    assert any(w["field"] == "marker.separation_mm" for w in big["warnings"])


def test_a_typed_quiet_zone_of_zero_reaches_the_core():
    """It was read as 1 module without a word (`or 1.0`); now the core's own
    rule answers it, in words, on its row."""
    p = W.plan(req({"quiet_modules": 0.0}, {"w": 40.0, "h": 40.0}))
    assert not p["ok"]
    assert any(w["field"] == "marker.quiet_modules" and w["level"] == "error" for w in p["warnings"])
    one = W.plan(req({"quiet_modules": 1.0}, {"w": 40.0, "h": 40.0}))
    absent = req({}, {"w": 40.0, "h": 40.0})
    del absent["marker"]["quiet_modules"]
    assert W.plan(absent)["outer"] == one["outer"]


def test_a_negative_gap_is_kept_and_said():
    r = req({}, {"w": 40.0, "h": 60.0})
    r["label"] = {"on": True, "text": "#{id}", "height_mm": 0.0, "side": "below", "gap_mm": -2.0,
                  "offset_mm": [0.0, 0.0], "place": "outside"}
    p = W.plan(r)
    zero = W.plan(dict(r, label=dict(r["label"], gap_mm=0.0)))
    # the 40 mm width sets the marker; its box reaches 2 mm into the band, so
    # the marker (centred in the box) sits 1 mm lower than with no gap
    assert p["marker_mm"] == zero["marker_mm"] and p["label"]["box"] == zero["label"]["box"]
    assert min(q[1] for q in p["outer"]) == pytest.approx(min(q[1] for q in zero["outer"]) - 1.0, abs=1e-6)
    assert any(w["field"] == "label.gap_mm" and w["level"] == "warn" for w in p["warnings"])


def test_a_typed_marker_size_is_still_drawn_as_typed():
    p = W.plan(req({"auto": False, "marker_mm": 11.4299, "type": "charuco", "cols": 5, "rows": 4}))
    assert p["marker_mm"] == 11.4299 and p["overflow_mm"] > 0 and red(p)
