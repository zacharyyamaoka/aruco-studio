"""Trim (contract barrier 5, Zach 2026-10-18): the sticker is cut to the
profile, the marker rectangle (default) or the marker, everything inside the
cut is white, and every export carries that white -- web_api.plan's cut /
cut_shape, svg, sheet and the inkjet paper layer."""
from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET

import pytest

from aruco_studio import web_api as W

from test_web_api import box, req

TOL = 1e-6
SVG = "{http://www.w3.org/2000/svg}"


def disc(cx, cy, r, n=72):
    """A clockwise circle (a hole)."""
    return [[cx + r * math.cos(-2 * math.pi * k / n), cy + r * math.sin(-2 * math.pi * k / n)]
            for k in range(n)]


PLATE = {"loops": [[[-60.0, -40.0], [60.0, -40.0], [60.0, 40.0], [-60.0, 40.0]],
                   disc(-35.0, 0.0, 10.0), disc(35.0, 0.0, 10.0)]}
CLEAR = {"cx": 0.0, "cy": 0.0, "w": 40.0, "h": 40.0, "angle_deg": 0.0}     # clear of the holes
TURNED = {"cx": 5.0, "cy": 3.0, "w": 30.0, "h": 20.0, "angle_deg": 30.0}


def trimmed(trim, rect=None, label=None, marker=None, profile=PLATE, pre=None):
    r = req(marker, rect=rect or CLEAR, label=label, pre=pre)
    r["trim"] = trim
    if profile is not None:
        r["profile"] = profile
    return r


def same_loop(a, b, tol=TOL):
    return len(a) == len(b) and all(abs(p[0] - q[0]) <= tol and abs(p[1] - q[1]) <= tol
                                    for p, q in zip(a, b))


def corners(rect):
    """The rectangle's 4 corners in the sketch, counter-clockwise from (-w/2, -h/2)."""
    c, s = math.cos(math.radians(rect["angle_deg"])), math.sin(math.radians(rect["angle_deg"]))
    out = []
    for u, v in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        u, v = u * rect["w"] / 2.0, v * rect["h"] / 2.0
        out.append([rect["cx"] + c * u - s * v, rect["cy"] + s * u + c * v])
    return out


def issues(p, field, level):
    return [w for w in p["warnings"] if w["field"] == field and w["level"] == level]


# ------------------------------------------------------------------ cut / cut_shape

@pytest.mark.parametrize("rect", [CLEAR, TURNED], ids=["square", "turned"])
def test_cut_shape_per_trim(rect):
    for label in ({"on": False}, {"on": True, "text": "#{id}"}):
        rp = W.plan(trimmed("rectangle", rect, label))
        assert rp["cut_shape"]["holes"] == [] and same_loop(rp["cut_shape"]["outer"], corners(rect))
        assert rp["cut"] == rp["cut_shape"]["outer"]
        pp = W.plan(trimmed("profile", rect, label))
        assert same_loop(pp["cut_shape"]["outer"], PLATE["loops"][0])
        assert len(pp["cut_shape"]["holes"]) == 2
        assert all(same_loop(h, lp) for h, lp in zip(pp["cut_shape"]["holes"], PLATE["loops"][1:]))
        assert pp["cut"] == pp["cut_shape"]["outer"]
        mp = W.plan(trimmed("marker", rect, label))
        assert mp["cut_shape"]["holes"] == [] and same_loop(mp["cut_shape"]["outer"], mp["outer"])
        assert mp["cut"] == mp["cut_shape"]["outer"]
        # the trim moves the cut only: the marker and its label are the same in all three
        for p in (pp, mp):
            assert (p["black"], p["outer"], p["label"]) == (rp["black"], rp["outer"], rp["label"])
        assert not issues(pp, "rect", "warn")
        assert not [w for w in issues(pp, "tag", "info") if "profile" in w["text"]]


def test_the_default_trim_is_the_rectangle():
    for label in ({"on": False}, {"on": True, "text": "#{id}"}):
        r = req(rect=CLEAR, label=label)
        assert "trim" not in r
        assert W.plan(r) == W.plan(dict(r, trim="rectangle"))
        assert W.svg(r) == W.svg(dict(r, trim="rectangle"))


def test_profile_without_a_profile_is_the_rectangle_said_on_tag():
    for prof in (None, {"loops": []}):
        p = W.plan(trimmed("profile", profile=prof))
        assert same_loop(p["cut_shape"]["outer"], corners(CLEAR)) and p["cut_shape"]["holes"] == []
        assert issues(p, "tag", "info") and "profile" in issues(p, "tag", "info")[0]["text"]


def test_a_rectangle_poking_out_of_the_profile_is_a_warning():
    wide = dict(CLEAR, w=100.0)                    # over both holes
    p = W.plan(trimmed("profile", wide))
    assert issues(p, "rect", "warn") and "outside the profile" in issues(p, "rect", "warn")[0]["text"]
    out = dict(CLEAR, cx=50.0, w=30.0, h=20.0)     # past the outer edge
    assert issues(W.plan(trimmed("profile", out)), "rect", "warn")
    # a rectangle that IS the profile touches it all round: inside
    tight = {"loops": [corners(CLEAR)]}
    assert not issues(W.plan(trimmed("profile", CLEAR, profile=tight)), "rect", "warn")


def test_a_label_outside_a_marker_trimmed_sticker_is_a_warning():
    p = W.plan(trimmed("marker", label={"on": True, "text": "#{id}"}))
    got = issues(p, "label.on", "warn")
    assert got and "the label is outside a marker-trimmed sticker" in got[0]["text"]
    assert p["label"] is not None                  # not silently dropped from the sketch
    sp = W.sticker_parts(trimmed("marker", label={"on": True, "text": "#{id}"}))
    assert sp["texts"] == [] and sp["label_ink"] == []
    assert not issues(W.plan(trimmed("marker")), "label.on", "warn")
    assert not issues(W.plan(trimmed("rectangle", label={"on": True})), "label.on", "warn")


# ------------------------------------------------------------------ svg

def svg_parts(out):
    root = ET.fromstring(out)
    white = [e for e in root.iter(SVG + "path") if e.get("data-layer") == "white"]
    assert len(white) == 1
    return root, white[0], loops_of(white[0].get("d"))


def loops_of(d):
    return [[(float(x), float(y)) for x, y in re.findall(r"([-\d.]+) ([-\d.]+)", sub)]
            for sub in d.split("M")[1:]]


def even_odd(loops, x, y):
    c = False
    for lp in loops:
        for i in range(len(lp)):
            (x0, y0), (x1, y1) = lp[i - 1], lp[i]
            if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
                c = not c
    return c


@pytest.mark.parametrize("trim", ["rectangle", "profile", "marker"])
@pytest.mark.parametrize("label", [False, True])
def test_svg_is_white_inside_the_cut(trim, label):
    r = trimmed(trim, label={"on": label, "text": "#{id}"})
    out = W.svg(r)
    root, white, loops = svg_parts(out)
    assert white.get("fill") == "#ffffff" and white.get("fill-rule") == "evenodd"
    # the white path's box is the cut's (the rectangle's own frame, y down); the
    # rectangle sits at the sketch origin unturned, so that is the plan's cut
    cut = W.plan(r)["cut_shape"]
    x0, y0, x1, y1 = box([cut["outer"]])
    got = box([loops[0]])
    assert got == pytest.approx((x0, -y1, x1, -y0), abs=TOL)
    vb = [float(v) for v in root.get("viewBox").split()]
    assert vb == pytest.approx([x0, -y1, x1 - x0, y1 - y0], abs=TOL)
    assert root.get("width") == W._f(x1 - x0) + "mm" and root.get("height") == W._f(y1 - y0) + "mm"
    # the ink is drawn on top of the white
    paths = [e.get("data-layer") for e in root.iter(SVG + "path") if e.get("data-layer")]
    assert paths[:2] == ["white", "black"]
    assert len(loops) == 1 + len(cut["holes"])
    if trim == "profile":
        assert not even_odd(loops, -35.0, 0.0) and not even_odd(loops, 35.0, 0.0)  # the holes
        assert even_odd(loops, 0.0, -30.0) and even_odd(loops, 50.0, 30.0)         # the plate
    has_label = 'data-label="1"' in out
    assert has_label == (label and trim != "marker")


def test_svg_of_a_turned_profile_is_in_the_rectangles_frame():
    r = trimmed("profile", TURNED)
    _root, _white, loops = svg_parts(W.svg(r))
    sp = W.sticker_parts(r)
    x0, y0, x1, y1 = box([sp["cut"]["outer"]])
    assert box([loops[0]]) == pytest.approx((x0, -y1, x1, -y0), abs=TOL)
    # the hole centres, turned into the rectangle's frame, are not white
    for hx in (-35.0, 35.0):
        u, v = W.to_rect(TURNED, [[(hx, 0.0)]])[0][0]
        assert not even_odd(loops, u, -v)


# ------------------------------------------------------------------ sheet

def test_every_sheet_sticker_is_its_cut():
    items = [trimmed("rectangle", dict(CLEAR, w=30.0, h=24.0)),
             trimmed("rectangle", dict(CLEAR, w=30.0, h=40.0), {"on": True, "text": "#{id}"}),
             trimmed("profile"),
             trimmed("profile", TURNED, {"on": True, "text": "lid"}),
             trimmed("marker", dict(CLEAR, w=30.0, h=40.0)),
             trimmed("marker", dict(CLEAR, w=30.0, h=40.0), {"on": True, "text": "#{id}"})]
    for mode in ("spaced", "tight"):
        got = W.sheet({"items": items, "cut_lines": True, "mode": mode}, "2026-10-18")
        assert not [w for w in got["warnings"] if w["level"] == "error"]
        assert [q["item"] for q in got["placements"]] == list(range(len(items)))
        for q in got["placements"]:
            sp = W.sticker_parts(items[q["item"]])
            x0, y0, x1, y1 = box([sp["cut"]["outer"]])
            w, h = (y1 - y0, x1 - x0) if q["rotation"] == 90 else (x1 - x0, y1 - y0)
            assert (q["w_mm"], q["h_mm"]) == pytest.approx((w, h), abs=TOL), q
            # the page's cut line runs along the cut: its outer loop is the box,
            # every hole of the profile is cut too
            page = got["svg"][q["page"]]
            d = re.search(r'<path data-cut="m%d"[^>]* d="([^"]*)"' % (q["item"] + 1), page).group(1)
            loops = loops_of(d)
            assert len(loops) == 1 + len(sp["cut"]["holes"])
            assert box([loops[0]]) == pytest.approx(
                (q["x_mm"], q["y_mm"], q["x_mm"] + q["w_mm"], q["y_mm"] + q["h_mm"]), abs=1e-3)
        warned = [w for w in got["warnings"] if w["field"] == "label.on" and w["level"] == "warn"]
        assert len(warned) == 1 and "the label is outside a marker-trimmed sticker" in warned[0]["text"]
        boxed = [w["text"] for w in got["warnings"] if "bounding box" in w["text"]]
        assert boxed == [f"item {k} is packed by its bounding box: its outline is not a rectangle"
                         for k in (3, 4)]


def test_a_label_off_sheet_sticker_is_the_whole_rectangle():
    r = req(rect={"w": 30.0, "h": 40.0})
    got = W.sheet({"items": [r], "cut_lines": True}, "2026-10-18")
    (q,) = got["placements"]
    assert (q["w_mm"], q["h_mm"]) in ((30.0, 40.0), (40.0, 30.0))


# ------------------------------------------------------------------ layers

@pytest.mark.parametrize("trim", ["rectangle", "profile", "marker"])
@pytest.mark.parametrize("rect", [CLEAR, TURNED], ids=["square", "turned"])
def test_the_inkjet_paper_is_the_cut_shape(trim, rect):
    for flip in (False, True):
        p = W.plan(trimmed(trim, rect, marker={"flip": flip}))
        (paper,) = [L for L in p["layers"] if L["part"] == "sticker"]
        assert paper["colour"] == "white"
        (poly,) = paper["polygons"]
        cut = p["cut_shape"]
        assert same_loop(poly["outer"], cut["outer"])
        assert len(poly["holes"]) == len(cut["holes"])
        assert all(same_loop(a, b) for a, b in zip(poly["holes"], cut["holes"]))
