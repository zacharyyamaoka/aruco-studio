"""What a CAD shell needs from the facade (contract barrier 4, the Fusion
adapter's N-6 report, 2026-10-18): MarkerPlan.layers / cells /
pattern_to_sketch / origin_z_mm, PlacedLabel.lines_at, the sheet's print
flags and placements, IdRequest.reserved, the driven values a shell shows,
the cell-multiple note, an exact inscribe of a plain rectangle, and
`readable` without OpenCV. Every geometric claim is checked against the
plan's own `black` / `outer` / label, not against the code that made it."""
from __future__ import annotations

import base64
import copy
import json
import math
import os
import re
import subprocess
import sys

import pytest

from aruco_studio import web_api as W
from aruco_studio.core import label as AL
from aruco_studio.core import rect_fill as RF
from aruco_studio.core import sheet as SH

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def preset(name="Inkjet · Letter vinyl", **kw):
    p = copy.deepcopy(next(x for x in W.presets() if x["name"] == name))
    if "cell_step_mm" in kw:
        p.pop("size_step", None)            # made by its cell step (barrier 11)
    p.update(kw)
    return p


INK = preset()
D3 = preset("Default")
INK_DOTS = preset(cell_step_mm=0.042333)        # the inkjet built-ins before cells rule 2


def req(marker=None, rect=None, label=None, pre=None, face=False):
    m = {"type": "single", "dictionary": "DICT_4X4_50", "first_id": 0, "auto": True,
         "marker_mm": 0.0, "checker_mm": 0.0, "separation_mm": 0.0, "cols": 1, "rows": 1,
         "turn": 0, "flip": False, "quiet_modules": 1.0, "corner_mark": "none"}
    m.update(marker or {})
    lb = {"on": False, "text": "", "height_mm": 0.0, "side": "below", "gap_mm": 2.0,
          "offset_mm": [0.0, 0.0]}
    lb.update(label or {})
    return {"rect": dict({"cx": 0.0, "cy": 0.0, "w": 30.0, "h": 40.0, "angle_deg": 0.0},
                         **(rect or {})),
            "marker": m, "label": lb, "preset": pre or INK, "reference_face": face}


# ------------------------------------------------------------------ geometry helpers

def area(lp) -> float:
    return sum(lp[i - 1][0] * lp[i][1] - lp[i][0] * lp[i - 1][1] for i in range(len(lp))) / 2.0


def poly_area(polys) -> float:
    return sum(area(p["outer"]) + sum(area(h) for h in p["holes"]) for p in polys)


def round_tol(polys) -> float:
    """What rounding every vertex to 1e-6 mm (the facade's JSON) can move an
    area by: half a micron of each edge's length, both sides of a box."""
    per = sum(math.dist(lp[i - 1], lp[i]) for p in polys for lp in [p["outer"]] + p["holes"]
              for i in range(len(lp)))
    return per * 1e-6


def inside(lp, x, y) -> bool:
    c = False
    for i in range(len(lp)):
        (x0, y0), (x1, y1) = lp[i - 1], lp[i]
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            c = not c
    return c


def in_polys(polys, x, y) -> bool:
    """Even-odd over every loop: the polygons are disjoint, holes inside."""
    n = sum(inside(p["outer"], x, y) + sum(inside(h, x, y) for h in p["holes"]) for p in polys)
    return n % 2 == 1


def to_pattern(M, x, y):
    """Sketch -> pattern by the inverse of M's (orthonormal) placement."""
    dx, dy = x - M[3], y - M[7]
    return M[0] * dx + M[4] * dy, M[1] * dx + M[5] * dy


def in_cells(cells, M, x, y) -> bool:
    u, v = to_pattern(M, x, y)
    return any(u0 < u < u1 and v0 < v < v1 for u0, v0, u1, v1 in cells)


def samples(polys, n=60):
    """An n x n grid over the polygons' box, offset by irrational steps so
    no sample sits on an edge."""
    xs = [q[0] for p in polys for q in p["outer"]]
    ys = [q[1] for p in polys for q in p["outer"]]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    for i in range(n):
        for j in range(n):
            yield (x0 + (x1 - x0) * (i + 0.5 + 0.1 * math.sqrt(2)) / n,
                   y0 + (y1 - y0) * (j + 0.5 + 0.1 * math.sqrt(3)) / n)


def layer(plan, name):
    return next(L for L in plan["layers"] if L["name"] == name)


# ------------------------------------------------------------------ 1. layers

def test_inkjet_layers_are_rule_2_paper_with_the_ink_pocketed_into_its_top_half():
    p = W.plan(req())
    t = INK["thickness_mm"]
    got = [(L["name"], L["part"], L["colour"], L["op"], L["z"]) for L in p["layers"]]
    assert got == [("sticker", "sticker", "white", "add", [0.0, t]),
                   ("pocket", "pocket", "none", "cut", [t / 2.0, t]),
                   ("ink", "ink", "black", "add", [t / 2.0, t])]
    # the paper is the sticker as it is cut (cut_shape: the rectangle by default,
    # trim 2026-10-18; it was the marker's outline); the ink (and its pocket) is
    # exactly the black
    paper = layer(p, "sticker")["polygons"]
    assert len(paper) == 1 and paper[0]["holes"] == []
    assert sorted(map(tuple, paper[0]["outer"])) == sorted(map(tuple, p["cut_shape"]["outer"]))
    for name in ("ink", "pocket"):
        assert poly_area(layer(p, name)["polygons"]) == pytest.approx(poly_area(p["black"]), abs=1e-6)
    for L in p["layers"]:
        for poly in L["polygons"]:
            assert area(poly["outer"]) > 0 and all(area(h) < 0 for h in poly["holes"])


@pytest.mark.parametrize("pre", [INK, D3], ids=["inkjet", "3d"])
@pytest.mark.parametrize("marker", [{"corner_mark": "triangle"}, {"type": "charuco", "cols": 3, "rows": 5}],
                         ids=["corner-mark", "charuco"])
def test_every_ink_polygon_has_its_pocket_in_the_white(pre, marker):
    """The 3D view and CAD take the black out of the white it sits in
    (2026-10-21, the inkjet sheet's slivers): every black add layer --
    the cells, the corner triangle, a ChArUco's squares out to the
    sticker's edge -- has a cut layer of the same polygons over the same z,
    into the white body's layer."""
    p = W.plan(req(marker, pre=pre, rect={"w": 40.0, "h": 60.0}))
    white = next(L for L in p["layers"] if L["op"] == "add" and L["colour"] == "white")
    cuts = [L for L in p["layers"] if L["op"] == "cut" and L.get("into") == white["name"]]
    for ink in (L for L in p["layers"] if L["op"] == "add" and L["colour"] == "black"):
        assert any(c["z"] == ink["z"] and c["polygons"] == ink["polygons"] for c in cuts), ink["name"]


def test_3d_layers_free_and_on_a_face():
    free = W.plan(req(pre=D3))
    assert [(L["name"], L["op"], L["colour"]) for L in free["layers"]] == \
        [("tile", "add", "white"), ("pocket", "cut", "none"), ("pattern", "add", "black")]
    assert layer(free, "tile")["z"][0] == 0.0
    top = layer(free, "tile")["z"][1]
    assert layer(free, "pattern")["z"][1] == top and layer(free, "pocket")["z"] == layer(free, "pattern")["z"]
    face = W.plan(req(pre=D3, face=True))
    assert [(L["name"], L["part"], L["op"]) for L in face["layers"]] == \
        [("pattern", "pattern", "add"), ("recess_pattern", "recess", "cut")]
    lo, hi = layer(face, "pattern")["z"]
    assert hi == 0.0 and lo < 0.0                       # the recess: flush with the face, into it
    assert poly_area(layer(face, "pattern")["polygons"]) == pytest.approx(poly_area(face["black"]), abs=1e-6)


def test_layers_follow_the_rectangle_turn_and_flip():
    r = req({"type": "grid", "cols": 3, "rows": 2, "turn": 90, "flip": True},
            rect={"cx": 15.0, "cy": -8.0, "w": 60.0, "h": 40.0, "angle_deg": 30.0})
    p = W.plan(r)
    t = INK["thickness_mm"]
    # Flip turns the marker over: the paper is below the sketch plane
    assert layer(p, "sticker")["z"] == [-t, 0.0] and layer(p, "ink")["z"] == [-t, -t / 2.0]
    ink = layer(p, "ink")["polygons"]
    assert poly_area(ink) == pytest.approx(poly_area(p["black"]), abs=round_tol(p["black"]))
    bad = [s for s in samples(p["black"]) if in_polys(ink, *s) != in_polys(p["black"], *s)]
    assert bad == []


def test_the_web_settings_build_only_add_steps():
    """cad_layers leaves "sub" steps out (the contract has no step): none of
    the facade's requests -- mode auto, corner mark none / triangle -- make
    one, so nothing is left out."""
    for pre in (INK, D3):
        for face in (False, True):
            for m in ({}, {"corner_mark": "triangle"}, {"type": "grid", "cols": 2, "rows": 2},
                      {"type": "charuco", "cols": 4, "rows": 3}):
                d, _i, _f = W._planned(req(m, rect={"w": 80.0, "h": 60.0}, pre=pre, face=face))
                assert d["ok"]
                assert {L["step"] for L in d["layers"]} == {"add"}, (pre["name"], face, m)
                assert len(W.plan(req(m, rect={"w": 80.0, "h": 60.0}, pre=pre, face=face))["layers"]) \
                    == len(d["layers"])


# ------------------------------------------------------------------ 2. cells + pattern_to_sketch

CELL_CASES = {
    "single": req(),
    "single 3D on a face": req(pre=D3, face=True),
    "grid turned 90, rotated rect, flipped": req({"type": "grid", "cols": 3, "rows": 2, "turn": 90, "flip": True},
                                                 rect={"cx": 15.0, "cy": -8.0, "w": 60.0, "h": 40.0,
                                                       "angle_deg": 30.0}),
    "grid manual, separation 5": req({"type": "grid", "cols": 2, "rows": 1, "auto": False, "marker_mm": 10.0,
                                      "separation_mm": 5.0}, rect={"w": 40.0, "h": 20.0}),
    "charuco 5x4 turned 270": req({"type": "charuco", "cols": 5, "rows": 4, "turn": 270},
                                  rect={"w": 80.0, "h": 60.0, "angle_deg": -12.5}),
    "single with a label, turned 180": req({"turn": 180, "first_id": 7}, rect={"w": 60.0, "angle_deg": 45.0},
                                           label={"on": True, "text": "#{id}\n{dict}", "side": "right"}),
    "6x6 single, 3D": req({"dictionary": "DICT_6X6_50"}, pre=D3),
}


@pytest.mark.parametrize("name", list(CELL_CASES))
def test_cells_through_pattern_to_sketch_reproduce_black(name):
    p = W.plan(CELL_CASES[name])
    M, cells = p["pattern_to_sketch"], p["cells"]
    assert len(M) == 16 and M[12:] == [0.0, 0.0, 0.0, 1.0] and cells
    assert all(u0 < u1 and v0 < v1 for u0, v0, u1, v1 in cells)
    # the placement is rigid (det +-1): a box's area is its area in the sketch
    assert abs(M[0] * M[5] - M[1] * M[4]) == pytest.approx(1.0, abs=1e-6)
    cell_area = sum((u1 - u0) * (v1 - v0) for u0, v0, u1, v1 in cells)
    assert cell_area == pytest.approx(poly_area(p["black"]), abs=round_tol(p["black"]))
    bad = [s for s in samples(p["black"]) if in_cells(cells, M, *s) != in_polys(p["black"], *s)]
    assert bad == [], (name, len(bad))


def test_pattern_to_sketch_is_the_frame_black_is_placed_with():
    r = CELL_CASES["grid turned 90, rotated rect, flipped"]
    d, _i = W._plan(r)
    # full precision since barrier 6 (N-8): the matrix itself, not rounded to ND
    assert W.plan(r)["pattern_to_sketch"] == W.sketch_of_pattern(r["rect"], d, True)


def test_the_corner_triangle_is_black_but_not_a_cell():
    """The triangle is not a box: black = the cells + the "mark_triangle" layer."""
    p = W.plan(req({"corner_mark": "triangle"}))
    M, cells = p["pattern_to_sketch"], p["cells"]
    tri = next(L for L in p["layers"] if L["name"] == "mark_triangle" and L["part"] == "ink")
    assert tri["colour"] == "black" and len(tri["polygons"][0]["outer"]) == 3
    cell_area = sum((u1 - u0) * (v1 - v0) for u0, v0, u1, v1 in cells)
    assert cell_area + poly_area(tri["polygons"]) == pytest.approx(poly_area(p["black"]),
                                                                    abs=round_tol(p["black"]))
    for s in samples(p["black"]):
        assert in_polys(p["black"], *s) == (in_cells(cells, M, *s) or in_polys(tri["polygons"], *s))


# ------------------------------------------------------------------ 3. lines_at

def _up(angle_deg):
    a = math.radians(angle_deg)
    return -math.sin(a), math.cos(a)


def test_sans_lines_at_are_each_lines_centre():
    r = req(rect={"cx": 5.0, "cy": 2.0, "angle_deg": 30.0},
            label={"on": True, "text": "#{id}\n{dict}\nthird", "side": "below"}, pre=INK_DOTS)
    lab = W.plan(r)["label"]
    la = lab["lines_at"]
    assert lab["font"] == "sans" and len(la) == len(lab["lines"]) == 3
    # the block's centre is the middle line's; the lines step down the label's up axis
    assert la[1] == pytest.approx(lab["at"], abs=1e-6)
    ux, uy = _up(lab["angle_deg"])
    pitch = lab["height_mm"] * (1.0 + RF.LINE_GAP)
    for a, b in zip(la, la[1:]):
        assert (a[0] - b[0]) * ux + (a[1] - b[1]) * uy == pytest.approx(pitch, abs=1e-5)
        assert (a[0] - b[0]) * uy - (a[1] - b[1]) * ux == pytest.approx(0.0, abs=1e-5)
    # the same centres sticker_parts gives the page (its texts, the rectangle's frame)
    R = W.rect_matrix(r["rect"])
    assert la == [W._pt(R, *t["at"]) for t in W.sticker_parts(r)["texts"]]


def test_pixel_lines_at_centre_each_lines_ink():
    r = req(pre=D3, label={"on": True, "text": "#{id}\n{dict}", "side": "below"})
    lab = W.plan(r)["label"]
    la = lab["lines_at"]
    assert lab["font"] == "pixel" and len(la) == 2
    assert ((la[0][1] + la[1][1]) / 2.0) == pytest.approx(lab["at"][1], abs=1e-6)
    cap = lab["height_mm"]
    stroke = cap / AL.GLYPH_ROWS
    assert la[0][1] - la[1][1] == pytest.approx(cap + AL.LINE_GAP_PX * stroke, abs=1e-6)
    # every stroke of the pixel ink sits in its line's cap band, about its centre
    for poly in lab["polygons"]:
        ys = [q[1] for q in poly["outer"]]
        assert any(min(ys) >= c[1] - cap / 2.0 - 1e-6 and max(ys) <= c[1] + cap / 2.0 + 1e-6 for c in la)
    for c in la:
        band = [q for poly in lab["polygons"] for q in poly["outer"]
                if c[1] - cap / 2.0 - 1e-6 <= q[1] <= c[1] + cap / 2.0 + 1e-6]
        xs = [q[0] for q in band]
        assert (min(xs) + max(xs)) / 2.0 == pytest.approx(c[0], abs=stroke)


# ------------------------------------------------------------------ 4. the PDF's print flags

def _catalog(pdf: bytes) -> bytes:
    m = re.search(rb"1 0 obj\n(.*?)\nendobj", pdf, re.S)
    return m.group(1)


def _body(pdf: bytes) -> bytes:
    """Every object after the catalog, up to the xref (offsets differ)."""
    return pdf[pdf.index(b"2 0 obj"):pdf.index(b"xref\n")]


def test_the_sheet_pdf_asks_for_actual_size():
    out = W.sheet({"items": [req(), req({"type": "grid", "cols": 2, "rows": 2})], "cut_lines": True},
                  "2026-10-18")
    pdf = base64.b64decode(out["pdf_base64"])
    assert _catalog(pdf) == (b"<< /Type /Catalog /Version /1.6 /Pages 2 0 R "
                             b"/ViewerPreferences << /PrintScaling /None >> >>")
    # the same catalog REF's writer (render_layout_pdf) gives its sheets
    ref = SH.render_layout_pdf(SH.layout_sheet([]), date="2026-10-18")
    assert b"/Version /1.6" in _catalog(ref) and b"/ViewerPreferences << /PrintScaling /None >>" in _catalog(ref)


def test_old_sticker_sheets_keep_their_bytes_unless_asked():
    d, _i = W._plan(req({"type": "grid", "cols": 2, "rows": 2}))
    from types import SimpleNamespace
    from aruco_studio.scene import sheet as SS
    lay = SH.layout_stickers([SS.sticker_item(SimpleNamespace(name=""), d)], SH.SheetSettings())
    old = SH.render_sticker_pdf(lay, date="2026-10-18")
    new = SH.render_sticker_pdf(lay, date="2026-10-18", print_scaling=True)
    assert _catalog(old) == b"<< /Type /Catalog /Pages 2 0 R >>" and b"PrintScaling" not in old
    assert _body(old) == _body(new) and old != new                  # only the catalog differs


# ------------------------------------------------------------------ 5. placements

def test_placements_say_where_each_item_landed():
    items = [req(rect={"w": 20.0, "h": 20.0}, label={"on": True, "text": "part {id}"}),
             req({"auto": False, "marker_mm": 300.0}, rect={"w": 300.0, "h": 300.0}),       # too big
             req({"type": "grid", "cols": 3, "rows": 2, "first_id": 10}, rect={"w": 120.0, "h": 60.0})]
    out = W.sheet({"items": items, "cut_lines": True}, "2026-10-18")
    pl = out["placements"]
    assert [q["item"] for q in pl] == [0, 2]                         # the rejected item is not placed
    page_w, page_h = INK["page_mm"]
    for q in pl:
        assert set(q) == {"item", "page", "x_mm", "y_mm", "w_mm", "h_mm", "rotation"}
        assert q["rotation"] in (0, 90) and 0 <= q["page"] < out["pages"]
        assert 0.0 <= q["x_mm"] and q["x_mm"] + q["w_mm"] <= page_w + 1e-6
        assert 0.0 <= q["y_mm"] and q["y_mm"] + q["h_mm"] <= page_h + 1e-6
        # the page's own invisible sticker box (core.sheet's data-sticker rect)
        page = out["svg"][q["page"]]
        m = re.search(r'<rect data-sticker="m%d"[^>]*data-x="([\d.]+)" data-y="([\d.]+)" '
                      r'data-w="([\d.]+)" data-h="([\d.]+)" data-rotation="(\d+)"' % (q["item"] + 1), page)
        assert m, q
        assert [float(v) for v in m.groups()[:4]] == pytest.approx(
            [q["x_mm"], q["y_mm"], q["w_mm"], q["h_mm"]], abs=1e-4)
        assert int(m.group(5)) == q["rotation"]
    # a labelled sticker is the whole marker rectangle (WYSIWYG)
    first = next(q for q in pl if q["item"] == 0)
    assert sorted([first["w_mm"], first["h_mm"]]) == pytest.approx([20.0, 20.0], abs=1e-6)


def test_a_turned_sticker_says_so():
    tall = req(rect={"w": 40.0, "h": 200.0}, label={"on": True, "text": "x"})
    wide = req(rect={"w": 190.0, "h": 40.0}, label={"on": True, "text": "y"})
    out = W.sheet({"items": [tall, tall, tall, tall, wide], "cut_lines": True, "mode": "tight"},
                  "2026-10-18")
    pl = out["placements"]
    assert len(pl) == 5
    for q in pl:
        w, h = (190.0, 40.0) if q["item"] == 4 else (40.0, 200.0)
        assert (q["w_mm"], q["h_mm"]) == pytest.approx((w, h) if q["rotation"] == 0 else (h, w), abs=1e-6)


# ------------------------------------------------------------------ 6. reserved ids

def item(key, kind="single", dictionary="DICT_4X4_50", count=1, first_id=None):
    return {"key": key, "type": kind, "dictionary": dictionary, "count": count, "first_id": first_id}


def assign(payload):
    return json.loads(W.call("assign_ids", json.dumps(payload)))


def test_reserved_ids_are_never_handed_out():
    keys = [f"k{i:02d}" for i in range(45)]
    reserved = [0, 1, 2, 3, 4]
    res = assign({"items": [item(k) for k in keys], "reserved": reserved})["result"]
    got = [i for a in res["items"] for i in a["ids"]]
    assert len(got) == 45 and not set(got) & set(reserved) and len(set(got)) == 45
    assert res["warnings"] == []
    # one more fills DICT_4X4_50 (50 ids, 5 reserved): it is refused, not given a reserved id
    full = assign({"items": [item(k) for k in keys + ["k45"]], "reserved": reserved})["result"]
    last = next(a for a in full["items"] if a["ids"] == [])
    assert any(w["level"] == "error" and "is full" in w["text"] and w["key"] == last["key"]
               for w in full["warnings"])


def test_reserved_is_per_family_and_blocks_whole_boards():
    res = assign({"items": [item("g", "grid", "DICT_5X5_50", 4), item("s", "single", "DICT_6X6_1000")],
                  "reserved": list(range(0, 1000, 2))})["result"]
    for a in res["items"]:
        assert all(i % 2 == 1 for i in a["ids"]) or a["ids"] == []
    g = next(a for a in res["items"] if a["key"] == "g")
    assert g["ids"] == [] and any(w["key"] == "g" and w["level"] == "error" for w in res["warnings"])
    s = next(a for a in res["items"] if a["key"] == "s")
    assert len(s["ids"]) == 1 and s["ids"][0] % 2 == 1


def test_a_typed_id_on_a_reserved_id_keeps_it_and_is_an_error():
    res = assign({"items": [item("lid", first_id=3), item("base", "grid", count=4, first_id=10)],
                  "reserved": [3, 12]})["result"]
    assert [a["ids"] for a in res["items"]] == [[3], [10, 11, 12, 13]]
    errs = {w["key"]: w["text"] for w in res["warnings"] if w["level"] == "error"}
    assert set(errs) == {"lid", "base"}
    assert "reserved id 3" in errs["lid"] and "reserved id 12" in errs["base"]
    assert all(w["field"] == "marker.first_id" for w in res["warnings"])


def test_a_ledger_id_that_became_reserved_moves_with_a_warning():
    res = assign({"items": [item("a")], "ledger": {"a": 7}, "reserved": [7]})["result"]
    a = res["items"][0]
    assert a["ids"] != [7] and len(a["ids"]) == 1 and a["driven"]
    assert any(w["level"] == "warn" and "reserved id 7" in w["text"] for w in res["warnings"])
    assert res["ledger"]["a"] == a["first_id"]


def test_bad_reserved_is_answered_in_words():
    for bad in ("3", [1.5], [-1], [True]):
        out = assign({"items": [item("a")], "reserved": bad})
        assert set(out) == {"error"} and out["error"].startswith("ValueError: "), (bad, out)


# ------------------------------------------------------------------ 7. driven values come back

def test_every_driven_value_a_shell_shows_is_in_the_plan():
    g = W.plan(req({"type": "grid", "cols": 3, "rows": 2, "first_id": 5}, rect={"w": 60.0, "h": 40.0},
                   label={"on": True, "text": "#{ids}", "height_mm": 0.0, "place": "outside"}))
    assert g["auto"] and g["marker_mm"] > 0 and g["separation_mm"] > 0
    assert (g["cols"], g["rows"]) == (3, 2) and g["ids"][0] == 5 and len(g["ids"]) == 6
    # barrier 7 (2026-10-20): driven = one module of the marker drawn, was
    # RF.auto_cap (0.12 x the short side, "way too big")
    assert g["label"]["height_mm"] == pytest.approx(g["cell_mm"], abs=1e-6)
    c = W.plan(req({"type": "charuco", "cols": 5, "rows": 4}, rect={"w": 80.0, "h": 60.0}))
    assert c["checker_mm"] > c["marker_mm"] > 0 and c["cell_mm"] > 0
    # a dimension carries each driven size
    fields = {dm["field"]: dm["value_mm"] for dm in c["dims"]}
    assert fields["marker.marker_mm"] == c["marker_mm"] and fields["marker.checker_mm"] == c["checker_mm"]


# ------------------------------------------------------------------ 8. the cell-multiple note

def test_a_snapped_size_states_both_numbers():
    p = W.plan(req({"auto": False, "marker_mm": 20.0}, rect={"w": 40.0, "h": 40.0}, pre=INK_DOTS))
    note = next(w for w in p["warnings"] if w["text"].startswith("cell multiple:"))
    assert note["field"] == "marker.marker_mm" and note["level"] == "info"
    assert f"20.0 mm → {p['marker_mm']:.3f} mm" in note["text"], note
    assert p["marker_mm"] != 20.0


# ------------------------------------------------------------------ 9. inscribe

def test_a_plain_rectangle_inscribes_as_itself():
    for loop in ([[0, 0], [50, 0], [50, 80], [0, 80]],                      # CCW
                 [[0, 0], [0, 80], [50, 80], [50, 0]],                      # CW
                 [[0, 0], [25, 0], [50, 0], [50, 80], [0, 80], [0, 0]],     # a point mid-edge, closed
                 [[12.34, -7.5], [62.34, -7.5], [62.34, 72.5], [12.34, 72.5]]):
        x0, y0 = min(p[0] for p in loop), min(p[1] for p in loop)
        for holes in ("avoid", "ignore"):
            r = W.inscribe({"loops": [loop]}, holes)
            assert r == {"cx": W._r(x0 + 25.0), "cy": W._r(y0 + 40.0), "w": 50.0, "h": 80.0,
                         "angle_deg": 0.0}, (loop, r)
    # what the search alone gave (the N-6 report): 0.1 mm short
    raw = W._A.largest_clear_rect([[(u / 1000.0, v / 1000.0) for u, v in [[0, 0], [50, 0], [50, 80], [0, 80]]]])
    assert raw["h"] * 1000.0 < 80.0


def test_a_hole_in_the_way_still_avoids_it():
    plate = [[0, 0], [50, 0], [50, 80], [0, 80]]
    hole = [[20, 30], [20, 50], [30, 50], [30, 30]]                         # CW
    r = W.inscribe({"loops": [plate, hole]}, "avoid")
    assert r["w"] * r["h"] < 50.0 * 80.0
    x0, x1, y0, y1 = r["cx"] - r["w"] / 2, r["cx"] + r["w"] / 2, r["cy"] - r["h"] / 2, r["cy"] + r["h"] / 2
    assert x1 <= 20.0 + 1e-9 or x0 >= 30.0 - 1e-9 or y1 <= 30.0 + 1e-9 or y0 >= 50.0 - 1e-9
    assert W.inscribe({"loops": [plate, hole]}, "ignore")["h"] == 80.0
    # not a rectangle: an L is searched, not taken as its box
    ell = [[0, 0], [50, 0], [50, 30], [20, 30], [20, 80], [0, 80]]
    assert W.inscribe({"loops": [ell]}, "avoid")["w"] * W.inscribe({"loops": [ell]}, "avoid")["h"] < 50.0 * 80.0


def test_an_edge_within_a_micron_of_the_grid_stays_on_it(monkeypatch):
    # the search's edges at 10.0000004 / 59.9999996 mm and 5.0000009 / 44.9999991 mm
    got = {"cx": 0.035, "cy": 0.025, "w": 0.0499999992, "h": 0.0399999982, "angle_deg": 0.0}
    monkeypatch.setattr(W._A, "largest_clear_rect", lambda loops: dict(got))
    r = W.inscribe({"loops": [[[0, 0], [70, 0], [70, 50], [35, 60], [0, 50]]]}, "avoid")
    assert (r["w"], r["h"], r["cx"], r["cy"]) == (50.0, 40.0, 35.0, 25.0), r
    # 2 microns in is in: the next line in, as before
    got.update(w=0.049996, h=0.039996)
    r = W.inscribe({"loops": [[[0, 0], [70, 0], [70, 50], [35, 60], [0, 50]]]}, "avoid")
    assert (r["w"], r["h"]) == (49.8, 39.8), r


# ------------------------------------------------------------------ 10. readable without OpenCV

CAM = {"distance_mm": 300.0, "resolution": [1920, 1080], "hfov_deg": 70.0}
SINGLE = req({"auto": False, "marker_mm": 30.0}, rect={"w": 40.0, "h": 40.0}, pre=preset(cell_step_mm=0.0))


def test_the_analytic_answer_is_the_pinhole_at_the_measured_limits():
    from aruco_studio import web_verify as V
    a = V.readable_analytic(SINGLE, CAM)
    f = 960.0 / math.tan(math.radians(35.0))
    assert a["measured"] is False and set(a) == {"px_per_cell", "max_distance_mm", "verdict", "text",
                                                 "measured"}
    assert a["px_per_cell"] == pytest.approx(5.0 * f / 300.0, abs=1e-3)
    lim = min(5.0 * f / V.READ_PX_PER_CELL, 4.0 * 30.0 * f / (V.PERIMETER_RATE * 1920))
    assert a["max_distance_mm"] == pytest.approx(lim, abs=0.05)
    assert a["verdict"] == "good" and "estimated" in a["text"]
    far = V.readable_analytic(SINGLE, dict(CAM, distance_mm=1.2 * lim))
    assert far["verdict"] == "poor" and far["measured"] is False
    # 4K: OpenCV's minimum outline binds before the px per cell
    k4 = V.readable_analytic(SINGLE, {"distance_mm": 300.0, "resolution": [3840, 2160], "hfov_deg": 90.0})
    assert k4["max_distance_mm"] == pytest.approx(4.0 * 30.0 * 1920.0 / (0.03 * 3840), abs=0.05)


def test_the_simulator_says_measured_and_the_estimate_is_never_farther():
    cv2 = pytest.importorskip("cv2")                           # noqa: F841
    from aruco_studio import web_verify as V
    from aruco_studio.verify import camera as C
    assert V.PERIMETER_RATE == C.PERIMETER_RATE
    m = V.readable(SINGLE, CAM)
    a = V.readable_analytic(SINGLE, CAM)
    assert m["measured"] is True and a["measured"] is False
    assert a["px_per_cell"] == m["px_per_cell"]
    assert 0.5 * m["max_distance_mm"] <= a["max_distance_mm"] <= m["max_distance_mm"]


def test_without_numpy_and_opencv_readable_still_answers():
    code = "\n".join([
        "import json, sys",
        "sys.modules['cv2'] = None; sys.modules['numpy'] = None",     # imports of these fail
        "from aruco_studio import web_api",
        "req = json.loads(sys.argv[1]); cam = json.loads(sys.argv[2])",
        "print(web_api.call('readable', json.dumps({'req': req, 'camera': cam})))",
        "print(web_api.call('verify', json.dumps({'req': req, 'view': {'camera': cam}})))",
    ])
    env = dict(os.environ, PYTHONPATH=ROOT, PYTHONDONTWRITEBYTECODE="1")
    out = subprocess.run([sys.executable, "-c", code, json.dumps(SINGLE), json.dumps(CAM)],
                         capture_output=True, text=True, env=env, cwd=ROOT, check=True).stdout.splitlines()
    readable, verify = json.loads(out[0]), json.loads(out[1])
    assert readable["result"]["measured"] is False and readable["result"]["max_distance_mm"] > 0
    assert verify["error"].startswith("ImportError: verify needs numpy and OpenCV")


# ------------------------------------------------------------------ 11. origin_z_mm

def test_origin_z_is_the_printed_surface():
    t = INK["thickness_mm"]
    cases = {"inkjet": (req(), t), "inkjet flipped": (req({"flip": True}), -t),
             "3D free": (req(pre=D3), None), "3D on a face": (req(pre=D3, face=True), 0.0)}
    for name, (r, want) in cases.items():
        p = W.plan(r)
        assert p["origin_z_mm"] == p["origin"][11], name
        if want is None:                               # the tile's top: where the pattern ends
            want = max(L["z"][1] for L in p["layers"])
        assert p["origin_z_mm"] == pytest.approx(want, abs=1e-9), (name, p["origin_z_mm"])
        # the detector's plane is where the black's top is
        black_top = max(L["z"][1] if want >= 0 else -L["z"][0] for L in p["layers"] if L["colour"] == "black")
        assert abs(p["origin_z_mm"]) == pytest.approx(black_top, abs=1e-9), name
