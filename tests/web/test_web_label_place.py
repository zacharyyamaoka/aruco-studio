"""Where the label goes (contract barrier 7, Zach 2026-10-20: "So for label
position you can choose On Marker, Outside marker, and then for both of those
you could choose top or bottom, left or right"): ON the marker, knocked out of
its black border row (a ChArUco board: a black chessboard square) or black on
its white quiet zone, or OUTSIDE it in the band; a driven height of one cell
("way too big" before); the knock-out absent from the ink on the plan, the
svg, the sheet and its PDF; and OpenCV still reading a marker with its border
row lettered. Every place is measured on the plan's own black and outline,
not on core.rect_fill's helpers."""
from __future__ import annotations

import base64
import copy
import math
import re
import zlib

import pytest

from aruco_studio import web_api as W


def preset(name, **kw):
    p = copy.deepcopy(next(x for x in W.presets() if x["name"] == name))
    p.update(kw)
    return p


INK = preset("Inkjet · Letter vinyl")
D3 = preset("Default")
TOL = 1e-5


def req(marker=None, rect=None, label=None, pre=None):
    m = {"type": "single", "dictionary": "DICT_4X4_50", "first_id": 0, "auto": True,
         "marker_mm": 0.0, "checker_mm": 0.0, "separation_mm": 0.0, "cols": 1, "rows": 1,
         "turn": 0, "flip": False, "quiet_modules": 1.0, "corner_mark": "none"}
    m.update(marker or {})
    lb = {"on": True, "text": "#{ids}", "height_mm": 0.0, "side": "below", "gap_mm": 2.0,
          "offset_mm": [0.0, 0.0]}
    lb.update(label or {})
    return {"rect": dict({"cx": 0.0, "cy": 0.0, "w": 40.0, "h": 40.0, "angle_deg": 0.0},
                         **(rect or {})),
            "marker": m, "label": lb, "preset": pre or INK, "reference_face": False}


# the rectangle sits at the sketch's origin unturned: the sketch frame IS the
# rectangle's, so the plan's black / outer / label are measured directly
TYPES = {"single": ({}, {"w": 40.0, "h": 40.0}),
         "grid": ({"type": "grid", "cols": 3, "rows": 2}, {"w": 60.0, "h": 40.0}),
         "charuco": ({"type": "charuco", "cols": 5, "rows": 4, "first_id": 35}, {"w": 80.0, "h": 60.0})}
BIG = {"single": {"w": 100.0, "h": 100.0}, "grid": {"w": 150.0, "h": 100.0},
       "charuco": {"w": 200.0, "h": 150.0}}            # 3D: room for printable pixel letters
SIDES = ("below", "above", "left", "right")


def box(loops):
    xs = [p[0] for lp in loops for p in lp]
    ys = [p[1] for lp in loops for p in lp]
    return min(xs), min(ys), max(xs), max(ys)


def inside(a, b, tol=TOL):
    return a[0] >= b[0] - tol and a[1] >= b[1] - tol and a[2] <= b[2] + tol and a[3] <= b[3] + tol


def overlaps(a, b, tol=TOL):
    return a[0] < b[2] - tol and b[0] < a[2] - tol and a[1] < b[3] - tol and b[1] < a[3] - tol


def squares(p, side_mm):
    """The black polygons whose box is a side_mm square (markers / checker squares)."""
    out = []
    for poly in p["black"]:
        b = box([poly["outer"]])
        if abs(b[2] - b[0] - side_mm) < TOL and abs(b[3] - b[1] - side_mm) < TOL:
            out.append(b)
    return out


def on_edge(b, edge_box, side, tol=TOL):
    k = {"below": 1, "above": 3, "left": 0, "right": 2}[side]
    return abs(b[k] - edge_box[k]) < tol


def text_box(lab):
    """The text block's box: Helvetica's widths (the page's) or the pixel ink."""
    if lab["font"] == "pixel":
        return box([q["outer"] for q in lab["polygons"]])
    lines = lab["lines"]
    cap = lab["height_mm"]
    along = max(W.text_width(t, cap) for t in lines)
    across = len(lines) * cap + (len(lines) - 1) * 0.4 * cap
    if abs(lab["angle_deg"]) == 90.0:
        along, across = across, along
    u, v = lab["at"]
    return u - along / 2.0, v - across / 2.0, u + along / 2.0, v + across / 2.0


def where_it_should_be(p, kind, surface, side):
    """The rooms a label ON the marker may sit in, from the plan's own geometry."""
    m, L, S = p["cell_mm"], p["marker_mm"], p["checker_mm"]
    out = box([p["outer"]])
    marks = squares(p, L)
    assert marks
    if kind == "charuco" and surface == "black":
        cands = [b for b in squares(p, S) if on_edge(b, out, side)]
        assert cands
        return cands
    if kind == "charuco":                              # the edge row's white square, outside its marker
        rows = []
        for mk in marks:
            c = ((mk[0] + mk[2]) / 2.0, (mk[1] + mk[3]) / 2.0)
            white = (c[0] - S / 2.0, c[1] - S / 2.0, c[0] + S / 2.0, c[1] + S / 2.0)
            if on_edge(white, out, side):
                rows.append({"below": (mk[0], white[1], mk[2], mk[1]),
                             "above": (mk[0], mk[3], mk[2], white[3]),
                             "left": (white[0], mk[1], mk[0], mk[3]),
                             "right": (mk[2], mk[1], white[2], mk[3])}[side])
        assert rows
        return rows
    if surface == "black":                             # a marker on the board's edge: its border row
        rows = []
        ext = box([[(b[0], b[1]), (b[2], b[3])] for b in marks])
        for b in marks:
            if not on_edge(b, ext, side):
                continue
            rows.append({"below": (b[0] + m, b[1], b[2] - m, b[1] + m),
                         "above": (b[0] + m, b[3] - m, b[2] - m, b[3]),
                         "left": (b[0], b[1] + m, b[0] + m, b[3] - m),
                         "right": (b[2] - m, b[1] + m, b[2], b[3] - m)}[side])
        return rows
    ext = box([[(b[0], b[1]), (b[2], b[3])] for b in marks])     # the quiet zone on that side
    return [{"below": (ext[0], out[1], ext[2], ext[1]), "above": (ext[0], ext[3], ext[2], out[3]),
             "left": (out[0], ext[1], ext[0], ext[3]), "right": (ext[2], ext[1], out[2], ext[3])}[side]]


@pytest.mark.parametrize("kind", TYPES)
@pytest.mark.parametrize("where", ["black", "white", "outside"])
@pytest.mark.parametrize("side", SIDES)
@pytest.mark.parametrize("pre", ["inkjet", "3d"])
def test_each_place_puts_the_text_where_it_should(kind, where, side, pre):
    marker, rect = TYPES[kind]
    place = "outside" if where == "outside" else "on_marker"
    label = {"side": side, "place": place} if place == "outside" else {"side": side, "surface": where}
    if where == "black":
        del label["surface"]                           # black is the default surface ...
    if place == "on_marker" and where == "black" and side == "below":
        label = {}                                     # ... and on the marker below the default place
    r = req(marker, BIG[kind] if pre == "3d" else rect, label, D3 if pre == "3d" else INK)
    p = W.plan(r)
    assert p["ok"]
    lab = p["label"]
    lb, tb = box([lab["box"]]), text_box(lab)
    if place == "outside":
        R = (-r["rect"]["w"] / 2.0, -r["rect"]["h"] / 2.0, r["rect"]["w"] / 2.0, r["rect"]["h"] / 2.0)
        assert inside(lb, R) and not overlaps(lb, box([p["outer"]]))
        assert lab["angle_deg"] == 0.0
        k = {"below": 1, "above": 3, "left": 0, "right": 2}[side]
        assert lb[k] == pytest.approx(R[k], abs=TOL)
        return
    rooms = where_it_should_be(p, kind, where, side)
    room = next((q for q in rooms if inside(lb, q)), None)
    assert room is not None, (lb, rooms)               # the label's box is in that row / square / zone
    assert inside(tb, lb), (tb, lb)                    # and the text in its box
    # the knock-out is all on the black; black text on the white touches no black
    if where == "white":
        assert not any(overlaps(tb, box([poly["outer"]])) for poly in p["black"])
    assert lab["angle_deg"] == {"below": 0.0, "above": 0.0, "left": 90.0, "right": -90.0}[side]
    # the marker keeps the whole rectangle: on the marker nothing is reserved
    off = W.plan(dict(r, label=dict(r["label"], on=False)))
    assert (p["marker_mm"], p["outer"]) == (off["marker_mm"], off["outer"])


def test_a_grid_label_is_in_the_middle_markers_row_and_a_board_square_on_its_edge():
    p = W.plan(req({"type": "grid", "cols": 3, "rows": 2}, {"w": 60.0, "h": 40.0}))
    lb = box([p["label"]["box"]])
    mid = [b for b in squares(p, p["marker_mm"]) if abs((b[0] + b[2]) / 2.0) < TOL]
    assert len(mid) == 2 and inside(lb, min(mid, key=lambda b: b[1]))     # the bottom middle marker
    c = W.plan(req({"type": "charuco", "cols": 5, "rows": 4}, {"w": 80.0, "h": 60.0},
                   {"side": "above"}))
    lb = box([c["label"]["box"]])
    top = [b for b in squares(c, c["checker_mm"]) if on_edge(b, box([c["outer"]]), "above")]
    near = min(top, key=lambda b: abs((b[0] + b[2]) / 2.0))
    assert inside(lb, near)


# ------------------------------------------------------------------ the driven height

@pytest.mark.parametrize("kind", TYPES)
def test_the_driven_height_is_one_cell(kind):
    """Inkjet (sans): on the black, one module less a quarter module of black
    above and below the letters (core.label's border-row rule: half a
    module); in a ChArUco square, one module; on the white, the quiet zone's
    module less the same quarter-module margins; outside, one module."""
    marker, rect = TYPES[kind]
    got = {}
    for name, lab in (("black", {}), ("white", {"surface": "white"}), ("outside", {"place": "outside"})):
        p = W.plan(req(marker, rect, lab))
        got[name] = (p["label"]["height_mm"], p["cell_mm"], p)
    cap, m, _p = got["black"]
    assert cap == pytest.approx(m if kind == "charuco" else m - 2 * 0.25 * m, abs=1e-6)
    cap, m, p = got["white"]
    depth = (p["checker_mm"] - p["marker_mm"]) / 2.0 if kind == "charuco" else 1.0 * m
    assert cap == pytest.approx(depth - 2 * 0.25 * m, abs=1e-6)
    cap, m, _p = got["outside"]
    assert cap == pytest.approx(m, abs=1e-6)


@pytest.mark.parametrize("pre", ["inkjet", "3d"])
@pytest.mark.parametrize("side", SIDES)
def test_outside_the_driven_height_is_the_drawn_markers_cell(pre, side):
    """The band's depth changes the marker Auto draws; the driven cap is one
    cell of the marker as drawn (3D: whole lines of the preset under it)."""
    for marker, rect in TYPES.values():
        p = W.plan(req(marker, rect, {"place": "outside", "side": side}, INK if pre == "inkjet" else D3))
        cap, m = p["label"]["height_mm"], p["cell_mm"]
        if pre == "inkjet":
            assert cap == pytest.approx(m, abs=1e-6)
        else:
            unit = 5 * 0.675                         # the pixel font's 5 rows of whole lines
            assert cap <= m + 1e-6 or cap == pytest.approx(unit)
            assert (cap / unit) == pytest.approx(round(cap / unit), abs=1e-6)


def test_a_typed_height_is_drawn_as_typed_and_flagged_over_the_row():
    p = W.plan(req(label={"height_mm": 6.0}))
    assert p["label"]["height_mm"] == 6.0
    assert any(w["field"] == "label.height_mm" and w["level"] == "warn" for w in p["warnings"])
    ok = W.plan(req())
    assert not [w for w in ok["warnings"] if w["field"].startswith("label")]


def test_two_lines_stack_and_are_flagged_when_the_row_cannot_hold_them():
    p = W.plan(req(label={"text": "#{ids}\n{dict}"}))
    lab = p["label"]
    assert lab["lines"] == ["#0", "4X4_50"] and len(lab["lines_at"]) == 2
    assert lab["lines_at"][0][1] - lab["lines_at"][1][1] == pytest.approx(1.4 * lab["height_mm"], abs=1e-6)
    assert any(w["field"] == "label.text" and w["level"] == "warn" and "runs out" in w["text"]
               for w in p["warnings"])
    left = W.plan(req(label={"text": "A\nB", "side": "left"}))["label"]
    (u0, v0), (u1, v1) = left["lines_at"]
    assert v0 == pytest.approx(v1) and u1 - u0 == pytest.approx(1.4 * left["height_mm"], abs=1e-6)


# ------------------------------------------------------------------ the knock-out

def even_odd(loops, x, y):
    c = False
    for lp in loops:
        for i in range(len(lp)):
            (x0, y0), (x1, y1) = lp[i - 1], lp[i]
            if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
                c = not c
    return c


def in_black(polys, x, y):
    return any(even_odd([q["outer"]] + q["holes"], x, y) for q in polys)


def area(lp):
    return sum(lp[i - 1][0] * lp[i][1] - lp[i][0] * lp[i - 1][1] for i in range(len(lp))) / 2.0


def poly_area(polys):
    return sum(area(q["outer"]) + sum(area(h) for h in q["holes"]) for q in polys)


@pytest.mark.parametrize("kind", TYPES)
@pytest.mark.parametrize("side", ["below", "left"])
def test_knocked_out_letters_are_absent_from_the_ink(kind, side):
    marker, _rect = TYPES[kind]
    r = req(marker, BIG[kind], {"side": side}, D3)
    p, off = W.plan(r), W.plan(dict(r, label=dict(r["label"], on=False)))
    lab = p["label"]
    assert lab["font"] == "pixel" and lab["polygons"]
    letters = sum(area(q["outer"]) for q in lab["polygons"])
    for q in lab["polygons"]:
        cx, cy = (sum(x for x, _ in q["outer"]) / 4.0, sum(y for _, y in q["outer"]) / 4.0)
        assert in_black(off["black"], cx, cy)          # it was black there ...
        assert not in_black(p["black"], cx, cy)        # ... and is paper now
    assert poly_area(off["black"]) - poly_area(p["black"]) == pytest.approx(letters, rel=1e-6)
    # the CAD layers: the footprint carries the letters as holes; no ink layer for them
    assert not [L for L in p["layers"] if L["part"] == "label"]
    blk = lambda plan: [q for L in plan["layers"] if L["colour"] == "black" for q in L["polygons"]]
    assert poly_area(blk(off)) - poly_area(blk(p)) == pytest.approx(letters, rel=1e-6)
    # the sticker as printed: the same holes, no label ink
    sp = W.sticker_parts(r)
    assert sp["label_ink"] == []
    ink = [{"outer": q[0], "holes": q[1:]} for q in sp["ink"]]
    assert poly_area(ink) == pytest.approx(poly_area(p["black"]), rel=1e-6)
    # on the white the letters are ink: a black layer of their own, the marker untouched
    w = W.plan(dict(r, label=dict(r["label"], surface="white")))
    assert [L["name"] for L in w["layers"] if L["part"] == "label"] == ["label_ink"]
    assert poly_area(w["black"]) == pytest.approx(poly_area(off["black"]), rel=1e-9)


def svg_texts(svg):
    return re.findall(r'<text([^>]*)>([^<]*)</text>', svg)


def test_the_svg_shows_the_knockout_white_over_the_black():
    for side, turn in (("below", None), ("left", "-90"), ("right", "90")):
        out = W.svg(req(label={"side": side}))
        (attrs, text), = [t for t in svg_texts(out) if 'data-label="1"' in t[0]]
        assert text == "#0" and 'fill="#ffffff"' in attrs
        assert out.index('data-layer="black"') < out.index('data-label="1"')    # on top of the black
        if turn:
            assert f'transform="rotate({turn} ' in attrs
        else:
            assert "transform" not in attrs
    white = W.svg(req(label={"surface": "white"}))
    (attrs, _t), = [t for t in svg_texts(white) if 'data-label="1"' in t[0]]
    assert 'fill="#000000"' in attrs
    # 3D: the black path itself has the letters' holes
    r = req(rect=BIG["single"], pre=D3)
    out, lab = W.svg(r), W.plan(r)["label"]
    d = re.search(r'data-layer="black"[^>]* d="([^"]*)"', out).group(1)
    loops = [[(float(a), -float(b)) for a, b in re.findall(r"(-?[\d.]+) (-?[\d.]+)", part)]
             for part in d.split("Z") if part.strip()]
    for q in lab["polygons"]:
        cx, cy = (sum(x for x, _ in q["outer"]) / 4.0, sum(y for _, y in q["outer"]) / 4.0)
        assert not even_odd(loops, cx, cy)
    assert 'data-label="1"' not in out                 # no ink drawn for it


def pdf_text(b64):
    pdf = base64.b64decode(b64)
    out = []
    for m in re.finditer(rb"stream\n(.*?)\nendstream", pdf, re.S):
        try:
            out.append(zlib.decompress(m.group(1)).decode("latin-1"))
        except zlib.error:
            continue
    return "\n".join(out)


def test_the_sheet_and_its_pdf_print_the_knockout_white():
    items = [req(label={"side": "below"}), req({"first_id": 1}, label={"side": "left"}),
             req({"first_id": 2}, label={"side": "right"}),
             req({"first_id": 3}, label={"surface": "white"})]
    got = W.sheet({"items": items, "cut_lines": True}, "2026-10-20")
    page = "".join(got["svg"])
    by = {t: a for a, t in svg_texts(page) if t in ("#0", "#1", "#2", "#3")}
    assert set(by) == {"#0", "#1", "#2", "#3"}
    assert all('fill="#ffffff"' in by[t] for t in ("#0", "#1", "#2"))
    assert 'fill="#000000"' in by["#3"]
    assert 'rotate(-90 ' in by["#1"] and 'rotate(90 ' in by["#2"] and "rotate" not in by["#0"]
    text = pdf_text(got["pdf_base64"])
    assert re.search(r"1 g [\d.]+ [\d.]+ Td \(#0\) Tj", text)
    assert re.search(r"1 g 0 1 -1 0 [\d.]+ [\d.]+ Tm \(#1\) Tj", text)
    assert re.search(r"1 g 0 -1 1 0 [\d.]+ [\d.]+ Tm \(#2\) Tj", text)
    assert re.search(r"0 g [\d.]+ [\d.]+ Td \(#3\) Tj", text)
    # the ink is drawn before the white letters over it (painted in order)
    ink = text.find("f*")
    assert -1 < ink < text.find("(#0) Tj")


def test_a_turned_label_is_centred_on_its_row_on_the_page():
    """The left label's letters on the page sit where the sketch has them:
    its baseline start half a cap right of the centre line, half its width
    below the centre (it reads upward)."""
    r = req(label={"side": "left"})
    sp = W.sticker_parts(r)
    (t,) = sp["texts"]
    assert t["rot"] == 90 and t["grey"] == 1.0
    lab = W.plan(r)["label"]
    assert t["at"] == pytest.approx(lab["at"], abs=1e-6)


# ------------------------------------------------------------------ the trim and verify

def test_a_label_on_the_marker_stays_inside_a_marker_trim():
    r = dict(req(), trim="marker")
    p = W.plan(r)
    assert not [w for w in p["warnings"] if w["field"] == "label.on"]
    assert inside(box([p["label"]["box"]]), box([p["cut"]]))
    assert W.sticker_parts(r)["texts"] and 'data-label="1"' in W.svg(r)


def test_place_and_surface_out_of_range_are_said():
    p = W.plan(req(label={"place": "inside", "surface": "grey"}))
    fields = {w["field"] for w in p["warnings"] if w["level"] == "warn"}
    assert {"label.place", "label.surface"} <= fields and p["label"] is not None


# ------------------------------------------------------------------ OpenCV still reads it

def bench(p):
    """The Verify dialog's bench camera (web/src/verify/bench.ts benchCamera):
    16 px per cell at 1280 x 960 / 60 deg, set back to fit the outline."""
    f = 640.0 / math.tan(math.radians(30.0))
    d = max(p["cell_mm"] * f / 16.0, max(p["outer_mm"]) * f / (0.8 * 960.0))
    return {"distance_mm": d, "resolution": [1280, 960], "hfov_deg": 60.0}


READS = [("single", {}, {"w": 40.0, "h": 40.0}),
         ("grid", {"type": "grid", "cols": 2, "rows": 3}, {"w": 60.0, "h": 90.0}),
         ("charuco", {"type": "charuco", "cols": 5, "rows": 4}, {"w": 100.0, "h": 80.0}),
         ("single 6x6", {"dictionary": "DICT_6X6_250"}, {"w": 40.0, "h": 40.0})]


@pytest.mark.parametrize("name,marker,rect", READS, ids=[r[0] for r in READS])
@pytest.mark.parametrize("side", SIDES)
def test_opencv_reads_a_marker_with_its_border_row_knocked_out(name, marker, rect, side):
    """The real-world gate (Zach, 2026-10-20): the white letters in the black
    border row must leave it black enough for the detector -- head on and in
    a field view (tilt 45, blur, grain), seeds 0-2, at the Verify dialog's
    default distance. The label is drawn where it is (white, its page
    widths), so the test is not vacuous: the row is lighter with it."""
    pytest.importorskip("cv2")
    from aruco_studio import web_verify as V
    from aruco_studio.verify import camera as C
    from aruco_studio.verify.render import top_view
    r = req(marker, rect, {"side": side})
    p = W.plan(r)
    d = V._plan(r)
    lab = V._label(r, d)
    assert lab["colour"] == "white" and lab["widths"]
    # the letters are on the top view the camera looks at: the row gets lighter
    rv = top_view(d, px_per_mm=40.0, ss=1)
    before = rv.img.copy()
    C._draw_label(rv, lab)
    hb = [lab["height_mm"] / 2.0] * 2
    x0, y0 = rv.to_px(lab["at"][0] - hb[0], lab["at"][1] + hb[1])
    x1, y1 = rv.to_px(lab["at"][0] + hb[0], lab["at"][1] - hb[1])
    win = (slice(int(y0), int(y1) + 1), slice(int(x0), int(x1) + 1))
    assert rv.img[win].mean() > before[win].mean() + 20.0
    cam = bench(p)
    for v in ({"tilt_deg": 0.0, "blur_px": 0.0, "noise": 0.0},
              {"tilt_deg": 45.0, "blur_px": 1.0, "noise": 0.1}):
        for seed in (0, 1, 2):
            got = V.verify(r, dict(v, camera=cam, yaw_deg=0.0, glare=0.0, occlusion=0.0, seed=seed))
            assert got["ok"] and got["found"] == p["ids"], (v, seed, got["notes"])


def test_the_knockout_costs_no_reading_distance():
    """readable's measured limit (head on, a decent camera's blur and grain)
    with the border row lettered is the plain marker's: 2771 mm for a 30 mm
    4x4 at 1080p / 70 deg on 2026-10-20, both ways."""
    pytest.importorskip("cv2")
    from aruco_studio import web_verify as V
    nosnap = dict(INK, cell_step_mm=0.0)
    r = req({"auto": False, "marker_mm": 30.0}, {"w": 40.0, "h": 40.0}, {}, nosnap)
    cam = {"distance_mm": 500.0, "resolution": [1920, 1080], "hfov_deg": 70.0}
    on = V.readable(r, cam)["max_distance_mm"]
    off = V.readable(dict(r, label=dict(r["label"], on=False)), cam)["max_distance_mm"]
    assert on >= 0.95 * off, (on, off)


@pytest.mark.parametrize("kind", TYPES)
def test_opencv_reads_a_3d_marker_with_knocked_out_pixel_letters(kind):
    """3D: the letters are holes in the black (the pixel font's boxes, drawn
    as boxes on the camera's top view, white)."""
    pytest.importorskip("cv2")
    from aruco_studio import web_verify as V
    marker, _rect = TYPES[kind]
    r = req(marker, BIG[kind], {}, D3)
    p = W.plan(r)
    lab = V._label(r, V._plan(r))
    assert lab["colour"] == "white" and len(lab["polygons"]) == len(p["label"]["polygons"])
    cam = bench(p)
    for v in ({"tilt_deg": 0.0, "blur_px": 0.0, "noise": 0.0},
              {"tilt_deg": 45.0, "blur_px": 1.0, "noise": 0.1}):
        got = V.verify(r, dict(v, camera=cam, yaw_deg=0.0, glare=0.0, occlusion=0.0, seed=0))
        assert got["ok"] and got["found"] == p["ids"], (v, got["notes"])
