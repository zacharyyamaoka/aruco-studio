"""The marker rectangle is the whole sticker (Zach's review of the live app,
2026-10-18; contract 56235bd): the label in a band INSIDE the rectangle
(core.rect_fill), its font by the making method, multi-line text, a
ChArUco origin in a square, the dimensions the canvas draws, the cut line.
Measured on the plan's own geometry; the same calls run in Pyodide in
web/scripts/parity.d/plan2.mjs."""
from __future__ import annotations

import copy
import hashlib
import json
import math

import pytest

from aruco_studio import web_api as W
from aruco_studio.core import rect_fill as RF


def preset(name):
    return copy.deepcopy(next(x for x in W.presets() if x["name"] == name))


INK = preset("Inkjet · Letter vinyl")
P3D = preset("Default")
INK_DOTS = dict(INK, cell_step_mm=0.042333)     # the inkjet built-ins before cells rule 2


def req(marker=None, rect=None, label=None, pre=None, face=False):
    m = {"type": "single", "dictionary": "DICT_4X4_50", "first_id": 0, "auto": True,
         "marker_mm": 0.0, "checker_mm": 0.0, "separation_mm": 0.0, "cols": 1, "rows": 1,
         "turn": 0, "flip": False, "quiet_modules": 1.0, "corner_mark": "none"}
    m.update(marker or {})
    # WHY "outside" (barrier 7, 2026-10-20): this file is about the band the
    # label takes INSIDE the rectangle beside the marker, the default before
    # "on_marker" (tests/web/test_web_label_place.py has the label on it)
    lb = {"on": False, "text": "", "height_mm": 0.0, "side": "below", "gap_mm": 2.0,
          "offset_mm": [0.0, 0.0], "place": "outside"}
    lb.update(label or {})
    return {"rect": dict({"cx": 0.0, "cy": 0.0, "w": 50.0, "h": 80.0, "angle_deg": 0.0},
                         **(rect or {})),
            "marker": m, "label": lb, "preset": pre or INK, "reference_face": face}


def box(loops):
    xs = [p[0] for lp in loops for p in lp]
    ys = [p[1] for lp in loops for p in lp]
    return min(xs), min(ys), max(xs), max(ys)


def inside(inner, outer, tol=1e-6):
    return (inner[0] >= outer[0] - tol and inner[1] >= outer[1] - tol
            and inner[2] <= outer[2] + tol and inner[3] <= outer[3] + tol)


def apart(a, b, tol=1e-6):
    """Two boxes that do not overlap (touching is apart)."""
    return a[2] <= b[0] + tol or b[2] <= a[0] + tol or a[3] <= b[1] + tol or b[3] <= a[1] + tol


def rect_box(r):
    return (r["cx"] - r["w"] / 2.0, r["cy"] - r["h"] / 2.0, r["cx"] + r["w"] / 2.0,
            r["cy"] + r["h"] / 2.0)


def turn(pt, deg, about=(0.0, 0.0)):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    u, v = pt[0] - about[0], pt[1] - about[1]
    return about[0] + c * u - s * v, about[1] + s * u + c * v


# rectangles where either side limits the marker, so any band shrinks it
TYPES = [({"type": "single"}, {"w": 40.0, "h": 40.0}),
         ({"type": "grid", "cols": 4, "rows": 4}, {"w": 60.0, "h": 60.0}),
         ({"type": "charuco", "cols": 5, "rows": 4}, {"w": 80.0, "h": 60.0})]


# ------------------------------------------------------------------ the label inside

@pytest.mark.parametrize("marker,rect", TYPES)
@pytest.mark.parametrize("pre", [INK, P3D], ids=["inkjet", "3d"])
@pytest.mark.parametrize("side", RF.SIDES)
def test_the_label_and_the_marker_share_the_rectangle(marker, rect, pre, side):
    r = req(marker, rect, {"on": True, "text": "#{ids}", "side": side}, pre)
    on, off = W.plan(r), W.plan(req(marker, rect, pre=pre))
    assert on["ok"] and off["ok"]
    R = rect_box(r["rect"])
    lab, outline = box([on["label"]["box"]]), box([on["outer"]])
    assert inside(lab, R) and inside(outline, R) and apart(lab, outline)
    assert on["overflow_mm"] == 0.0
    assert on["marker_mm"] < off["marker_mm"]                  # auto saw the smaller box
    assert inside(box([p["outer"] for p in on["black"]]), R)


@pytest.mark.parametrize("side", RF.SIDES)
def test_side_puts_the_band_on_that_side(side):
    r = req({"type": "grid", "cols": 3, "rows": 3}, {"cx": 10.0, "cy": -5.0, "w": 60.0, "h": 70.0},
            {"on": True, "text": "#{ids}", "side": side, "gap_mm": 3.0})
    p = W.plan(r)
    x0, y0, x1, y1 = rect_box(r["rect"])
    b0, c0, b1, c1 = box([p["label"]["box"]])
    o0, p0, o1, p1 = box([p["outer"]])
    edge = {"below": (c0, y0), "above": (c1, y1), "left": (b0, x0), "right": (b1, x1)}[side]
    assert edge[0] == pytest.approx(edge[1], abs=1e-6)          # flush with its edge
    if side in ("below", "above"):                              # the whole width
        assert (b0, b1) == (pytest.approx(x0), pytest.approx(x1))
        assert (p0 >= c1 + 3.0 - 1e-6) if side == "below" else (p1 <= c0 - 3.0 + 1e-6)
    else:
        assert (c0, c1) == (pytest.approx(y0), pytest.approx(y1))
        assert (o0 >= b1 + 3.0 - 1e-6) if side == "left" else (o1 <= b0 - 3.0 + 1e-6)
    # the text sits in the band, EDGE x cap of white from the cut line, and a
    # sans label below keeps DESCENT x cap under its baseline (2026-10-18: a
    # label flush with the cut line lost its descenders to the knife)
    cap = p["label"]["height_mm"]
    ax, ay = p["label"]["at"]
    assert b0 - 1e-6 <= ax <= b1 + 1e-6 and c0 - 1e-6 <= ay - cap / 2.0 and ay + cap / 2.0 <= c1 + 1e-6
    pad, desc = RF.EDGE * cap, RF.DESCENT * cap
    if side == "below":
        assert ay - cap / 2.0 == pytest.approx(y0 + pad + desc, abs=1e-6)
    elif side == "above":
        assert ay + cap / 2.0 == pytest.approx(y1 - pad, abs=1e-6)
    else:
        assert (ax - b0 if side == "left" else b1 - ax) > pad


@pytest.mark.parametrize("pre", [INK, P3D], ids=["inkjet", "3d"])
def test_offset_moves_the_label_by_exactly_that(pre):
    base = {"on": True, "text": "{type} #{id}", "side": "above"}
    a = W.plan(req(label=base, pre=pre))["label"]
    b = W.plan(req(label=dict(base, offset_mm=[3.5, -1.25]), pre=pre))["label"]
    assert b["at"][0] - a["at"][0] == pytest.approx(3.5, abs=1e-6)
    assert b["at"][1] - a["at"][1] == pytest.approx(-1.25, abs=1e-6)
    assert b["box"] == a["box"]                                  # the preset band stays
    if pre is P3D:                                               # the ink moves with it
        assert box([q["outer"] for q in b["polygons"]]) == pytest.approx(
            [v + d for v, d in zip(box([q["outer"] for q in a["polygons"]]), (3.5, -1.25, 3.5, -1.25))],
            abs=1e-6)


def test_multi_line_labels():
    one = W.plan(req(label={"on": True, "text": "#{ids}"}))["label"]
    two = W.plan(req(label={"on": True, "text": "#{ids}\n{dict}"}))["label"]
    assert two["lines"] == ["#0", "4X4_50"] and two["text"] == "#0\n4X4_50"
    assert one["lines"] == ["#0"]
    h1 = box([one["box"]])[3] - box([one["box"]])[1]
    h2 = box([two["box"]])[3] - box([two["box"]])[1]
    assert h2 > h1
    cap2 = two["height_mm"]
    assert h2 == pytest.approx((2 + RF.LINE_GAP + RF.EDGE + RF.DESCENT) * cap2, abs=1e-6)
    p3 = W.plan(req(label={"on": True, "text": "AB\nC\nD"}, pre=P3D))["label"]
    assert p3["lines"] == ["AB", "C", "D"]
    ys = sorted({round(q["outer"][0][1], 6) for q in p3["polygons"]})
    assert ys[-1] - ys[0] > 2 * p3["height_mm"]                 # three rows of ink


def test_the_font_follows_the_method():
    ink = W.plan(req(label={"on": True, "text": "#{ids}"}, pre=INK))["label"]
    assert ink["font"] == "sans" and ink["polygons"] == []
    p3 = W.plan(req(label={"on": True, "text": "#{ids}"}, pre=P3D))["label"]
    assert p3["font"] == "pixel" and p3["polygons"]
    band = box([p3["box"]])
    for q in p3["polygons"]:
        assert inside(box([q["outer"]]), band) and q["holes"] == []
        assert W._area2(q["outer"]) > 0
    # strokes suit the preset's line: one pixel = a whole number of 0.675 mm lines
    px = p3["height_mm"] / 5.0
    assert px >= 0.675 - 1e-9 and px / 0.675 == pytest.approx(round(px / 0.675), abs=1e-6)
    widths = {round(min(b[2] - b[0], b[3] - b[1]), 6) for b in (box([q["outer"]]) for q in p3["polygons"])}
    assert min(widths) == pytest.approx(px, abs=1e-6)
    # a typed cap thinner than the line is drawn as typed and said
    thin = W.plan(req(label={"on": True, "text": "#1", "height_mm": 2.0}, pre=P3D))
    assert thin["label"]["height_mm"] == 2.0
    assert any(w["field"] == "label.height_mm" and w["level"] == "warn" for w in thin["warnings"])


def test_a_typed_marker_too_big_for_the_box_is_flagged_against_the_rectangle():
    """30 mm (outline 40 mm) in 40 x 40 with a 5 mm label and a 1 mm gap: the
    band is 5 + its edge margin 2 + descender room 1.5 = 8.5 mm, so the marker
    is centred on the 40 x 30.5 box the label leaves, and its outline pokes
    4.75 mm past the rectangle's top; the words name that box."""
    loose = preset("Inkjet · Letter vinyl") | {"cell_step_mm": 0.0}
    p = W.plan(req({"auto": False, "marker_mm": 30.0}, {"w": 40.0, "h": 40.0},
                   {"on": True, "text": "#{id}", "height_mm": 5.0, "gap_mm": 1.0}, loose))
    assert p["marker_mm"] == 30.0 and p["outer_mm"] == [40.0, 40.0]
    o = box([p["outer"]])
    assert o[3] == pytest.approx(24.75, abs=1e-6)
    assert p["overflow_mm"] == pytest.approx(4.75, abs=1e-6)
    red = [w for w in p["warnings"] if w["field"] == "marker.marker_mm" and w["level"] == "error"]
    assert red and "9.5 mm taller than the 40 × 30.5 mm beside the label" in red[0]["text"]
    big = W.plan(req({"auto": False, "marker_mm": 45.0}, {"w": 40.0, "h": 40.0},
                     {"on": True, "height_mm": 5.0, "gap_mm": 1.0, "side": "left"}, loose))
    o = box([big["outer"]])                                     # measured against the rectangle
    assert big["overflow_mm"] == pytest.approx(max(o[2] - 20.0, -20.0 - o[0], o[3] - 20.0,
                                                   -20.0 - o[1]), abs=1e-6) and big["overflow_mm"] > 0
    ok = W.plan(req({"auto": False, "marker_mm": 15.0}, {"w": 40.0, "h": 40.0},
                    {"on": True, "height_mm": 5.0, "gap_mm": 1.0}, loose))
    assert ok["overflow_mm"] == 0.0 and not [w for w in ok["warnings"] if w["level"] == "error"]


def test_a_label_that_leaves_no_room_is_an_error():
    p = W.plan(req(rect={"w": 20.0, "h": 20.0}, label={"on": True, "height_mm": 12.0,
                                                       "text": "A\nB", "gap_mm": 2.0}))
    assert any(w["field"] == "label.height_mm" and w["level"] == "error" for w in p["warnings"])


# ------------------------------------------------------------------ the cut line

def test_cut_is_the_rectangle():
    r = req({"type": "grid", "cols": 2, "rows": 2}, {"cx": 3.0, "cy": 4.0, "w": 30.0, "h": 50.0,
                                                    "angle_deg": 30.0}, {"on": True})
    p = W.plan(r)
    want = [turn((u, v), 30.0) for u, v in ((-15, -25), (15, -25), (15, 25), (-15, 25))]
    assert [tuple(q) for q in p["cut"]] == [pytest.approx((u + 3.0, v + 4.0), abs=1e-6)
                                           for u, v in want]
    assert W._area2(p["cut"]) > 0
    assert W.plan(req())["cut"] == [[-25.0, -40.0], [25.0, -40.0], [25.0, 40.0], [-25.0, 40.0]]


def test_label_off_plans_are_todays():
    """Every number a label-off plan had at 56235bd (sha256 of its JSON then,
    tools: the facade at that commit), with only cut and dims added -- and
    contract barrier 4's CAD fields (tests/web/test_web_cad.py), barrier
    5's cut_shape (tests/web/test_web_trim.py), and barrier 9's fit_rect (the
    request's rect: tests/web/test_web_profile_first.py)."""
    # the inkjet cases under the dots they were pinned with (cells rule 2 is
    # tests/web/test_web_round.py's)
    cases = {"45d745cfb9e6f365165f5c0bd683e49ca3e92ce73c36bc70e1ecd36fba350684":
             req({}, {"w": 20, "h": 20}, pre=INK_DOTS),
             "ac8aa1c5edb27b8ab778aa1bfdd6da0f94c885ae28ff885f19e8cae6b0ce6ce7":
             req({"type": "grid", "cols": 3, "rows": 2, "turn": 90, "flip": True},
                 {"cx": 15, "cy": -8, "angle_deg": 30, "w": 60, "h": 40}, pre=INK_DOTS),
             "7adcc5ce7f65c97b70dbd82367dabcd59a353ed661bfb771217b7ee537d81bc9":
             req({"type": "charuco", "cols": 5, "rows": 4}, {"w": 80, "h": 60}, pre=P3D)}
    for sha, r in cases.items():
        p = W.plan(r)
        new = {"cut", "cut_shape", "dims", "layers", "cells", "pattern_to_sketch", "origin_z_mm",
               "fit_rect"}
        assert new <= set(p)
        assert p["fit_rect"] == {k: float(r["rect"][k]) for k in ("cx", "cy", "w", "h", "angle_deg")}
        old = {k: v for k, v in p.items() if k not in new}
        assert hashlib.sha256(json.dumps(old, sort_keys=True).encode()).hexdigest() == sha


# ------------------------------------------------------------------ ChArUco origin

def _centres(p, side):
    """The centres of the drawn black squares of a side (any angle)."""
    out = []
    for q in p["black"]:
        lp = q["outer"]
        if len(lp) == 4 and all(abs(math.dist(lp[i - 1], lp[i]) - side) < 1e-5 for i in range(4)):
            out.append((sum(x for x, _y in lp) / 4.0, sum(y for _x, y in lp) / 4.0))
    return out


def test_origin_square_puts_the_joint_origin_at_that_squares_centre():
    m = {"type": "charuco", "cols": 5, "rows": 4}
    corner = W.plan(req(m, {"w": 80.0, "h": 60.0}))
    p = W.plan(req(dict(m, origin_square=[2, 1]), {"w": 80.0, "h": 60.0}))
    S = p["checker_mm"]
    # the drawn board: its top-left corner is OpenCV's origin (turn 0), x right, y down
    squares = _centres(p, S)
    bx0 = min(c[0] for c in squares) - S / 2.0
    by1 = max(c[1] for c in squares) + S / 2.0
    want = (bx0 + 2.5 * S, by1 - 1.5 * S)
    assert (p["origin"][3], p["origin"][7]) == (pytest.approx(want[0], abs=0.01),
                                                pytest.approx(want[1], abs=0.01))
    # (2, 1) is a white square: the marker it holds is centred there
    assert any(math.dist(c, want) < 0.01 for c in _centres(p, p["marker_mm"]))
    # the axes are OpenCV's, unchanged; only the translation moved
    assert [p["origin"][i] for i in (0, 1, 2, 4, 5, 6, 8, 9, 10)] == \
        [corner["origin"][i] for i in (0, 1, 2, 4, 5, 6, 8, 9, 10)]
    assert not [w for w in p["warnings"] if w["field"] == "marker.origin_square"]


def test_origin_square_on_a_turned_rotated_board():
    """turn 90 on a 30 degree rectangle: still a square's centre, (0, 0) is
    the square at OpenCV's corner (a black one)."""
    m = {"type": "charuco", "cols": 5, "rows": 4, "turn": 90}
    r = {"cx": 5.0, "cy": -3.0, "w": 80.0, "h": 60.0, "angle_deg": 30.0}
    corner = W.plan(req(m, r))
    p = W.plan(req(dict(m, origin_square=[0, 0]), r))
    S = p["checker_mm"]
    o = (p["origin"][3], p["origin"][7])
    x, y = (corner["origin"][0], corner["origin"][4]), (corner["origin"][1], corner["origin"][5])
    want = (corner["origin"][3] + 0.5 * S * (x[0] + y[0]), corner["origin"][7] + 0.5 * S * (x[1] + y[1]))
    assert o == (pytest.approx(want[0], abs=0.01), pytest.approx(want[1], abs=0.01))
    assert any(math.dist(c, o) < 0.01 for c in _centres(p, S))   # a drawn black square


@pytest.mark.parametrize("bad", [[5, 0], [0, 4], [-1, 0], [1.5, 0], [1], "a1"])
def test_origin_square_out_of_range_is_an_error_on_its_row(bad):
    m = {"type": "charuco", "cols": 5, "rows": 4}
    p = W.plan(req(dict(m, origin_square=bad), {"w": 80.0, "h": 60.0}))
    corner = W.plan(req(m, {"w": 80.0, "h": 60.0}))
    assert p["ok"] and p["origin"] == corner["origin"]
    red = [w for w in p["warnings"] if w["field"] == "marker.origin_square"]
    assert len(red) == 1 and red[0]["level"] == "error" and "5 × 4" in red[0]["text"]


def test_origin_square_is_ignored_off_charuco():
    p = W.plan(req({"type": "grid", "cols": 2, "rows": 2, "origin_square": [1, 1]}))
    assert p["origin"] == W.plan(req({"type": "grid", "cols": 2, "rows": 2}))["origin"]
    assert [w["level"] for w in p["warnings"] if w["field"] == "marker.origin_square"] == ["info"]
    assert W.plan(req({"type": "charuco", "cols": 5, "rows": 4, "origin_square": None},
                      {"w": 80.0, "h": 60.0}))["origin"] == \
        W.plan(req({"type": "charuco", "cols": 5, "rows": 4}, {"w": 80.0, "h": 60.0}))["origin"]


# ------------------------------------------------------------------ dimensions

DIM_CASES = [
    ("single", req({"auto": False, "marker_mm": 15.0}, {"w": 30.0, "h": 30.0})),
    ("single 3D, label + offset", req({}, {"w": 40.0, "h": 50.0},
                                      {"on": True, "text": "#{id}", "offset_mm": [2.0, 1.0]}, P3D)),
    ("grid 3x2", req({"type": "grid", "cols": 3, "rows": 2, "separation_mm": 4.0},
                     {"w": 70.0, "h": 50.0}, {"on": True, "side": "left"})),
    ("grid 1x3 (vertical gap)", req({"type": "grid", "cols": 1, "rows": 3}, {"w": 30.0, "h": 90.0})),
    ("grid turned 90", req({"type": "grid", "cols": 3, "rows": 2, "turn": 90}, {"w": 50.0, "h": 70.0})),
    ("charuco 5x4", req({"type": "charuco", "cols": 5, "rows": 4}, {"w": 80.0, "h": 60.0},
                        {"on": True, "side": "above"})),
]


def _number(p, r, d):
    f = d["field"]
    if f.startswith("marker."):
        return p[f.split(".", 1)[1]]
    if f == "rect.w":
        return r["rect"]["w"]
    if f == "rect.h":
        return r["rect"]["h"]
    if f == "label.offset_mm":
        return math.hypot(*r["label"]["offset_mm"])
    assert f == "outer", f
    return min(p["outer_mm"], key=lambda v: abs(v - d["value_mm"]))


@pytest.mark.parametrize("name,r", DIM_CASES, ids=[c[0] for c in DIM_CASES])
@pytest.mark.parametrize("angle", [0.0, 30.0])
def test_each_dimension_measures_its_field(name, r, angle):
    r = copy.deepcopy(r)
    r["rect"]["angle_deg"] = angle
    p = W.plan(r)
    fields = [d["field"] for d in p["dims"]]
    want = {"marker.marker_mm", "outer", "rect.w", "rect.h"}
    want |= {"marker.checker_mm"} if p["checker_mm"] else set()
    want |= {"marker.separation_mm"} if p["separation_mm"] else set()
    want |= {"label.offset_mm"} if any(r["label"]["offset_mm"]) and r["label"]["on"] else set()
    assert set(fields) == want and fields.count("outer") == 2
    for d in p["dims"]:
        assert math.dist(d["a"], d["b"]) == pytest.approx(d["value_mm"], abs=1e-6), d
        assert d["value_mm"] == pytest.approx(_number(p, r, d), abs=1e-6), d
    outer = sorted(d["value_mm"] for d in p["dims"] if d["field"] == "outer")
    assert outer == pytest.approx(sorted(p["outer_mm"]), abs=1e-6)


@pytest.mark.parametrize("name,r", DIM_CASES, ids=[c[0] for c in DIM_CASES])
def test_dimension_endpoints_are_on_the_drawing_and_the_lines_stay_off_the_marker(name, r):
    p = W.plan(r)
    corners = {(round(x, 5), round(y, 5)) for q in p["black"] for x, y in q["outer"]}
    o = box([p["outer"]])
    oc = {(round(x, 5), round(y, 5)) for x, y in p["outer"]}
    rc = {(round(x, 5), round(y, 5)) for x, y in p["cut"]}
    for d in p["dims"]:
        a, b = d["a"], d["b"]
        if d["field"] in ("marker.marker_mm", "marker.checker_mm"):
            assert {(round(a[0], 5), round(a[1], 5)), (round(b[0], 5), round(b[1], 5))} <= corners
        elif d["field"] == "marker.separation_mm":          # on two markers' edges
            assert any(abs(a[0] - x) < 1e-5 or abs(a[1] - y) < 1e-5 for x, y in corners)
        elif d["field"] == "outer":
            assert {(round(a[0], 5), round(a[1], 5)), (round(b[0], 5), round(b[1], 5))} <= oc
        elif d["field"] in ("rect.w", "rect.h"):
            assert {(round(a[0], 5), round(a[1], 5)), (round(b[0], 5), round(b[1], 5))} <= rc
        if d["field"] == "label.offset_mm":
            assert d["a"] != d["b"]
            continue
        # the drawn line: offset_mm to the left of a -> b, clear of the outline
        dx, dy = (b[0] - a[0]) / d["value_mm"], (b[1] - a[1]) / d["value_mm"]
        n = (-dy * d["offset_mm"], dx * d["offset_mm"])
        line = box([[(a[0] + n[0], a[1] + n[1]), (b[0] + n[0], b[1] + n[1])]])
        assert apart(line, o), (d, o)


def test_turning_the_rectangle_turns_the_dims_and_the_label():
    base = req({"type": "grid", "cols": 3, "rows": 2}, {"cx": 7.0, "cy": -4.0, "w": 70.0, "h": 50.0},
               {"on": True, "text": "#{ids}\n{dict}", "side": "right", "offset_mm": [1.0, 2.0]}, P3D)
    flat = W.plan(base)
    turned_r = copy.deepcopy(base)
    turned_r["rect"]["angle_deg"] = 30.0
    turned = W.plan(turned_r)
    c = (7.0, -4.0)
    assert [d["field"] for d in turned["dims"]] == [d["field"] for d in flat["dims"]]
    for d0, d1 in zip(flat["dims"], turned["dims"]):
        assert d1["value_mm"] == d0["value_mm"] and d1["offset_mm"] == d0["offset_mm"]
        for k in ("a", "b"):
            assert tuple(d1[k]) == pytest.approx(turn(d0[k], 30.0, c), abs=1e-6)
    l0, l1 = flat["label"], turned["label"]
    assert l1["angle_deg"] == 30.0 and l0["angle_deg"] == 0.0
    assert tuple(l1["at"]) == pytest.approx(turn(l0["at"], 30.0, c), abs=1e-6)   # the offset turns too
    for p0, p1 in zip(l0["box"], l1["box"]):
        assert tuple(p1) == pytest.approx(turn(p0, 30.0, c), abs=1e-6)
    for q0, q1 in zip(l0["polygons"], l1["polygons"]):
        for p0, p1 in zip(q0["outer"], q1["outer"]):
            assert tuple(p1) == pytest.approx(turn(p0, 30.0, c), abs=1e-6)


# ------------------------------------------------------------------ the page, the svg

def test_sticker_parts_are_the_rectangle_with_its_label_inside():
    r = req({"type": "grid", "cols": 2, "rows": 2, "turn": 90}, {"w": 40.0, "h": 60.0, "angle_deg": 20.0},
            {"on": True, "text": "#{ids}\nlid", "side": "below"}, pre=INK_DOTS)
    sp = W.sticker_parts(r)
    assert sp["cut"]["outer"] == [[-20.0, -30.0], [20.0, -30.0], [20.0, 30.0], [-20.0, 30.0]]
    assert sp["font"] == "sans" and sp["label_ink"] == []
    assert [t["text"] for t in sp["texts"]] == ["#0-3", "lid"]
    p = W.plan(r)
    cap = p["label"]["height_mm"]
    band = (-20.0, -30.0, 20.0, -30.0 + (2 + RF.LINE_GAP + RF.EDGE + RF.DESCENT) * cap)
    for t in sp["texts"]:
        assert t["cap_mm"] == cap
        assert band[1] - 1e-6 <= t["at"][1] - cap / 2.0 and t["at"][1] + cap / 2.0 <= band[3] + 1e-6
    ink = box([poly[0] for poly in sp["ink"]])
    assert inside(ink, (-20.0, band[3] + 2.0, 20.0, 30.0))
    p3 = W.sticker_parts(dict(r, preset=P3D))
    assert p3["font"] == "pixel" and p3["texts"] == [] and p3["label_ink"]
    assert box([poly[0] for poly in p3["label_ink"]])[1] >= -30.0 - 1e-6
    assert W.sticker_parts(req()) is not None and W.sticker_parts(req())["texts"] == []


def test_svg_with_a_label_is_the_whole_sticker():
    out = W.svg(req({"auto": False, "marker_mm": 15.0}, {"w": 30.0, "h": 40.0},
                    {"on": True, "text": "#{id}\n{dict}"}))
    assert out.startswith('<svg xmlns="http://www.w3.org/2000/svg" width="30mm" height="40mm" '
                          'viewBox="-15 -20 30 40">')
    assert ">#0</text>" in out and ">4X4_50</text>" in out
    p3 = W.svg(req({}, {"w": 30.0, "h": 40.0}, {"on": True}, P3D))
    assert '<path data-label="1"' in p3 and "<text" not in p3


def test_call_carries_the_new_fields():
    r = req({"type": "charuco", "cols": 5, "rows": 4, "origin_square": [2, 1]}, {"w": 80.0, "h": 60.0},
            {"on": True, "text": "#{ids}\ncal"}, P3D)
    got = json.loads(W.call("plan", json.dumps(r)))["result"]
    assert got == json.loads(json.dumps(W.plan(r)))
    assert {"cut", "dims"} <= set(got) and {"lines", "font", "polygons", "box"} <= set(got["label"])
