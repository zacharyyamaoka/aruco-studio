"""What a CAD shell needs from the facade, round 2 (contract barrier 6, the
Fusion adapter's N-8 report, 2026-10-19): `into` on every cut / keep layer,
the corner mark in the layers (a ChArUco board's notch, the tile's corner
cut), the 3D label's ink as a layer, SheetRequest.print_dialog,
IdRequest.reserved per family, and pattern_to_sketch at full precision.
Every geometric claim is checked against the plan's own `black` / `cells` /
label and the corner mark's sizes in core.chamfer, not against the code
that made the layers."""
from __future__ import annotations

import base64
import json
import math
import re

import pytest

from aruco_studio import web_api as W
from aruco_studio.core import chamfer as CH
from aruco_studio.core import sheet as SH
from aruco_studio.plan import region as RG

from test_web_cad import (D3, INK, area, assign, in_cells, in_polys, item, layer, poly_area, req,
                          round_tol, samples)

PRESETS = {"inkjet": (INK, False), "3D free": (D3, False), "3D on a face": (D3, True)}
TYPES = {"single": {}, "grid": {"type": "grid", "cols": 2, "rows": 2},
         "charuco": {"type": "charuco", "cols": 4, "rows": 3}}
RECT = {"cx": 3.0, "cy": -2.0, "w": 80.0, "h": 60.0, "angle_deg": 21.0}


def plan(kind, where, mark="none", **kw):
    pre, face = PRESETS[where]
    return W.plan(req(dict(TYPES[kind], corner_mark=mark, **kw), rect=RECT, pre=pre, face=face))


def black_layers(p):
    return [poly for L in p["layers"] if L["colour"] == "black" for poly in L["polygons"]]


def ink_area(p) -> float:
    return poly_area(black_layers(p))


# ------------------------------------------------------------------ 1. into

def every_plan():
    for where in PRESETS:
        for kind in TYPES:
            for mark in ("none", "triangle", "cut"):
                yield (where, kind, mark), plan(kind, where, mark)
    for where in PRESETS:
        pre, face = PRESETS[where]
        yield (where, "label"), W.plan(req(rect={"w": 40.0, "h": 50.0}, pre=pre, face=face,
                                           label={"on": True, "text": "#{id}\n{dict}"}))


def test_every_cut_or_keep_layer_names_what_it_cuts_into():
    for case, p in every_plan():
        names = [L["name"] for L in p["layers"]]
        for i, L in enumerate(p["layers"]):
            if L["op"] == "add":
                assert "into" not in L, (case, L["name"])
                continue
            assert L["op"] in ("cut", "keep") and L["colour"] == "none", (case, L["name"])
            # the paper's / the tile's own add layer, built before it, or the host body
            assert L["into"] == "face" or L["into"] in names[:i], (case, L["name"], L["into"])
            if L["into"] != "face":
                host = layer(p, L["into"])
                assert host["op"] == "add" and host["colour"] == "white", (case, L["into"])


def test_into_says_paper_tile_or_face():
    want = {"inkjet": "sticker", "3D free": "tile", "3D on a face": "face"}
    for where, host in want.items():
        for mark in ("none", "triangle"):
            p = plan("single", where, mark)
            cuts = [L for L in p["layers"] if L["op"] == "cut"]
            assert cuts and {L["into"] for L in cuts} == {host}, (where, mark)
    # a face has no paper or tile: nothing white is built, the recess goes into the body
    face = plan("grid", "3D on a face", "triangle")
    assert not [L for L in face["layers"] if L["colour"] == "white"]


# ------------------------------------------------------------------ 2. the corner mark

def notch(p) -> float:
    """A ChArUco board's corner cut (core.chamfer): legs 2 modules, at most
    a quarter of the square."""
    leg = min(CH.CHARUCO_LEG * p["cell_mm"], CH.CHARUCO_LEG_SQUARE * p["checker_mm"])
    return leg * leg / 2.0


def triangle(p) -> float:
    leg = CH.TRI_LEG * p["cell_mm"]
    return leg * leg / 2.0


@pytest.mark.parametrize("where", list(PRESETS))
@pytest.mark.parametrize("kind", list(TYPES))
@pytest.mark.parametrize("mark", ["triangle", "cut"])
def test_the_ink_with_a_corner_mark_is_the_ink_without_it_less_the_notch(where, kind, mark):
    bare, p = plan(kind, where), plan(kind, where, mark)
    assert (p["marker_mm"], p["cell_mm"], p["checker_mm"]) == (bare["marker_mm"], bare["cell_mm"],
                                                              bare["checker_mm"])
    tol = round_tol(black_layers(p)) + round_tol(black_layers(bare))
    if kind == "charuco":
        # either form on a board whose top-left square is black: that square's
        # outer corner, cut out of the ink
        assert ink_area(p) == pytest.approx(ink_area(bare) - notch(p), abs=tol)
    elif mark == "triangle" or where == "3D on a face":
        # no tile of its own to cut (a face): the black triangle, added to the ink
        assert ink_area(p) == pytest.approx(ink_area(bare) + triangle(p), abs=tol)
    elif where == "inkjet":
        # the core cuts the sticker's own outline (its tile_cut); the facade's
        # paper is the trim (cut_shape), as its svg and sheet print it: the
        # mark changes nothing it builds
        assert ink_area(p) == pytest.approx(ink_area(bare), abs=tol)
        assert [L["name"] for L in p["layers"]] == ["sticker", "pocket", "ink"]
        assert layer(p, "sticker")["polygons"] == [p["cut_shape"]]
    else:
        # 3D free "cut": the white tile's corner, a cut layer into the tile; the ink as it was
        assert ink_area(p) == pytest.approx(ink_area(bare), abs=tol)
        cut = layer(p, "mark_cut")
        assert (cut["op"], cut["into"], cut["colour"]) == ("cut", "tile", "none")
        tile = layer(p, "tile")
        lo, hi = tile["z"]
        assert cut["z"][0] < lo and cut["z"][1] > hi                  # through the whole tile
        took = RG.area(RG.polygons(RG.boolean(
            [[[q["outer"]] + q["holes"] for q in tile["polygons"]],
             [[q["outer"]] + q["holes"] for q in cut["polygons"]]], lambda f: f[0] and f[1])))
        leg = CH.TILE_LEG * p["cell_mm"]
        assert took == pytest.approx(leg * leg / 2.0, abs=1e-5)


@pytest.mark.parametrize("where", list(PRESETS))
@pytest.mark.parametrize("kind", list(TYPES))
@pytest.mark.parametrize("mark", ["none", "triangle", "cut"])
def test_black_and_the_ink_layers_are_one_shape(where, kind, mark):
    """`black` (the plan's own top view) = the black layers, point for
    point; the pocket / recess is the same footprint as the ink."""
    p = plan(kind, where, mark)
    ink = black_layers(p)
    assert ink_area(p) == pytest.approx(poly_area(p["black"]), abs=round_tol(p["black"]) + round_tol(ink))
    bad = [s for s in samples(p["black"]) if in_polys(ink, *s) != in_polys(p["black"], *s)]
    assert bad == [], (len(bad), bad[:3])
    foot = [poly for L in p["layers"] if L["op"] == "cut" and L["name"] != "mark_cut"
            for poly in L["polygons"]]
    assert poly_area(foot) == pytest.approx(ink_area(p), abs=round_tol(foot) + round_tol(ink))
    bad = [s for s in samples(p["black"]) if in_polys(foot, *s) != in_polys(ink, *s)]
    assert bad == []
    for L in p["layers"]:
        for poly in L["polygons"]:
            assert area(poly["outer"]) > 0 and all(area(h) < 0 for h in poly["holes"])


@pytest.mark.parametrize("where", list(PRESETS))
@pytest.mark.parametrize("kind", list(TYPES))
def test_cells_and_mark_triangle_agree_with_the_layers(where, kind):
    p = plan(kind, where, "triangle")
    M, cells = p["pattern_to_sketch"], p["cells"]
    cell_area = sum((u1 - u0) * (v1 - v0) for u0, v0, u1, v1 in cells)
    tol = round_tol(p["black"])
    if kind != "charuco":
        # black = the cells + the "mark_triangle" add layer
        tri = [poly for L in p["layers"] if L["name"] == "mark_triangle" and L["op"] == "add"
               for poly in L["polygons"]]
        assert cell_area + poly_area(tri) == pytest.approx(ink_area(p), abs=tol)
        for s in samples(p["black"]):
            assert in_polys(black_layers(p), *s) == (in_cells(cells, M, *s) or in_polys(tri, *s))
        return
    # a ChArUco board: no triangle; the cells are its squares before the cut,
    # and what they cover that the ink does not is the notch at the board's
    # top-left corner (the pattern frame's -u, +v)
    assert not [L for L in p["layers"] if L["name"].startswith("mark_")]
    assert cell_area - notch(p) == pytest.approx(ink_area(p), abs=tol)
    u0 = min(c[0] for c in cells)
    v1 = max(c[3] for c in cells)
    leg = math.sqrt(2.0 * notch(p))
    for s in samples(p["black"], 90):
        ink, cell = in_polys(black_layers(p), *s), in_cells(cells, M, *s)
        if ink:
            assert cell, s
        elif cell:
            dx, dy = s[0] - M[3], s[1] - M[7]
            u, v = M[0] * dx + M[4] * dy, M[1] * dx + M[5] * dy
            assert (u - u0) + (v1 - v) <= leg + 1e-6, (s, u, v)


def test_the_notch_is_in_every_footprint_layer_a_board_builds():
    """Today's bug (N-8): the ink had no notch. Each footprint layer -- the
    ink, its pocket, the recess -- now holds the cut corner."""
    for where in PRESETS:
        p, bare = plan("charuco", where, "triangle"), plan("charuco", where)
        for L, B in zip(p["layers"], bare["layers"]):
            assert (L["name"], L["op"], L["z"]) == (B["name"], B["op"], B["z"])
            if L["colour"] == "white":
                assert poly_area(L["polygons"]) == pytest.approx(poly_area(B["polygons"]), abs=1e-9)
            else:
                assert poly_area(L["polygons"]) == pytest.approx(
                    poly_area(B["polygons"]) - notch(p), abs=round_tol(L["polygons"]) + round_tol(B["polygons"]))


# ------------------------------------------------------------------ 3. the 3D label

LABEL = {"on": True, "text": "#{id}\n{dict}", "place": "outside"}   # ink, not knocked out (barrier 7)


@pytest.mark.parametrize("face,flip", [(False, False), (False, True), (True, False)])
def test_the_pixel_label_is_a_black_layer_at_the_inks_z(face, flip):
    p = W.plan(req({"flip": flip, "first_id": 9}, rect={"cx": 15.0, "cy": -8.0, "w": 40.0, "h": 50.0,
                                                        "angle_deg": 30.0}, pre=D3, face=face, label=LABEL))
    lab = p["label"]
    assert lab["font"] == "pixel" and lab["polygons"]
    got = [L for L in p["layers"] if L["name"] == "label_ink"]
    assert len(got) == 1
    L = got[0]
    assert (L["colour"], L["op"]) == ("black", "add") and "into" not in L
    assert L["polygons"] == lab["polygons"]
    ink = next(B for B in p["layers"] if B["colour"] == "black" and B["name"] != "label_ink")
    assert L["z"] == ink["z"]
    if flip:
        assert L["z"][1] <= 0.0


def test_a_sans_label_stays_text():
    p = W.plan(req(rect={"w": 40.0, "h": 50.0}, pre=INK, label=LABEL))
    assert p["label"]["font"] == "sans" and p["label"]["polygons"] == []
    assert [L["name"] for L in p["layers"]] == ["sticker", "pocket", "ink"]
    off = W.plan(req(rect={"w": 40.0, "h": 50.0}, pre=D3))
    assert not [L for L in off["layers"] if L["name"] == "label_ink"]


# ------------------------------------------------------------------ 4. print_dialog

OPEN = b"/OpenAction << /S /Named /N /Print >>"
ITEMS = [req(rect={"w": 20.0, "h": 20.0}, label={"on": True, "text": "a"}),
         req({"type": "grid", "cols": 3, "rows": 2}, rect={"w": 120.0, "h": 60.0})]


def pdf_of(**kw) -> bytes:
    return base64.b64decode(W.sheet(dict({"items": ITEMS, "cut_lines": True}, **kw), "2026-10-19")["pdf_base64"])


def structure(pdf: bytes) -> dict:
    """A stdlib check of the file: every xref offset is its object's
    header, startxref is the xref, the trailer's /Size and /Root hold; ->
    {object number: body}."""
    assert pdf.startswith(b"%PDF-1.4\n") and pdf.endswith(b"%%EOF\n")
    sx = int(re.search(rb"startxref\n(\d+)\n%%EOF\n$", pdf).group(1))
    assert pdf[sx:sx + 5] == b"xref\n"
    m = re.match(rb"xref\n0 (\d+)\n0000000000 65535 f \n", pdf[sx:])
    n = int(m.group(1))
    rows = pdf[sx + m.end():].split(b"\n")[:n - 1]
    objs = {}
    for k, row in enumerate(rows, start=1):
        off = int(row[:10])
        assert row.endswith(b" 00000 n ") and pdf[off:].startswith(b"%d 0 obj\n" % k), k
        objs[k] = pdf[off + len(b"%d 0 obj\n" % k):pdf.index(b"\nendobj\n", off)]
    trailer = pdf[pdf.index(b"trailer\n", sx):]
    assert re.search(rb"/Size %d /Root 1 0 R" % n, trailer)
    assert objs[1].startswith(b"<< /Type /Catalog ")
    return objs


def test_the_print_dialog_opens_only_when_asked():
    plain, asked, no = pdf_of(), pdf_of(print_dialog=True), pdf_of(print_dialog=False)
    assert plain == no and OPEN not in plain and b"OpenAction" not in plain
    a, b = structure(plain), structure(asked)
    assert b[1] == (b"<< /Type /Catalog /Version /1.6 /Pages 2 0 R "
                    b"/ViewerPreferences << /PrintScaling /None >> " + OPEN + b" >>")
    assert asked.count(b"OpenAction") == 1
    assert {k: v for k, v in a.items() if k != 1} == {k: v for k, v in b.items() if k != 1}


def test_the_print_dialog_pdf_still_parses():
    pdfium = pytest.importorskip("pypdfium2")
    out = W.sheet({"items": ITEMS, "cut_lines": True, "print_dialog": True}, "2026-10-19")
    doc = pdfium.PdfDocument(base64.b64decode(out["pdf_base64"]))
    try:
        assert len(doc) == out["pages"]
        page_w, page_h = INK["page_mm"]
        w, h = doc[0].get_size()
        assert (w, h) == pytest.approx((page_w * 72.0 / 25.4, page_h * 72.0 / 25.4), abs=0.01)
    finally:
        doc.close()


def test_older_sticker_pdfs_keep_their_bytes():
    from types import SimpleNamespace
    from aruco_studio.scene import sheet as SS
    d, _i = W._plan(req({"type": "grid", "cols": 2, "rows": 2}))
    lay = SH.layout_stickers([SS.sticker_item(SimpleNamespace(name=""), d)], SH.SheetSettings())
    old = SH.render_sticker_pdf(lay, date="2026-10-19")
    assert SH.render_sticker_pdf(lay, date="2026-10-19", print_dialog=False) == old
    assert SH.render_sticker_pdf(lay, date="2026-10-19", print_scaling=True) == \
        SH.render_sticker_pdf(lay, date="2026-10-19", print_scaling=True, print_dialog=False)
    asked = structure(SH.render_sticker_pdf(lay, date="2026-10-19", print_dialog=True))
    assert asked[1] == b"<< /Type /Catalog /Pages 2 0 R " + OPEN + b" >>"


# ------------------------------------------------------------------ 5. reserved per family

def ids_of(res, key):
    return next(a["ids"] for a in res["items"] if a["key"] == key)


def test_a_list_reserves_in_every_family_a_map_only_in_its_own():
    items = [item("four"), item("five", "single", "DICT_5X5_50")]
    free = assign({"items": items})["result"]
    every = list(range(49))                                  # leaves only 49 in each
    lst = assign({"items": items, "reserved": every})["result"]
    assert ids_of(lst, "four") == [49] and ids_of(lst, "five") == [49]
    for key in ("aruco4x4", "4x4", "4X4"):
        mp = assign({"items": items, "reserved": {key: every}})["result"]
        assert ids_of(mp, "four") == [49], key
        assert ids_of(mp, "five") == ids_of(free, "five"), key      # 5x5: as if nothing were reserved
        assert mp["warnings"] == []
    both = assign({"items": items, "reserved": {"aruco4x4": every, "5x5": every}})["result"]
    assert ids_of(both, "four") == [49] and ids_of(both, "five") == [49]


def test_a_map_flags_typed_ids_and_moves_ledger_ids_in_its_family_only():
    items = [item("t4", first_id=3), item("t5", "single", "DICT_5X5_50", first_id=3),
             item("l4"), item("l5", "single", "DICT_5X5_100")]
    res = assign({"items": items, "ledger": {"l4": 7, "l5": 7}, "reserved": {"aruco4x4": [3, 7]}})["result"]
    assert ids_of(res, "t4") == [3] and ids_of(res, "t5") == [3]       # typed: kept as typed
    errs = [w for w in res["warnings"] if w["level"] == "error"]
    assert [w["key"] for w in errs] == ["t4"] and "reserved id 3" in errs[0]["text"]
    assert ids_of(res, "l5") == [7] and ids_of(res, "l4") not in ([7], [3])
    warns = [w for w in res["warnings"] if w["level"] == "warn"]
    assert [w["key"] for w in warns] == ["l4"] and "reserved id 7" in warns[0]["text"]
    assert res["ledger"]["l5"] == 7 and res["ledger"]["l4"] == ids_of(res, "l4")[0]
    # the same as a list: both families
    lst = assign({"items": items, "ledger": {"l4": 7, "l5": 7}, "reserved": [3, 7]})["result"]
    assert sorted(w["key"] for w in lst["warnings"]) == ["l4", "l5", "t4", "t5"]


def test_a_board_is_blocked_whole_in_its_family():
    res = assign({"items": [item("g", "grid", "DICT_5X5_50", 4), item("s")],
                  "reserved": {"aruco5x5": list(range(0, 50, 2))}})["result"]
    assert ids_of(res, "g") == [] and any(w["key"] == "g" and w["level"] == "error" for w in res["warnings"])
    assert len(ids_of(res, "s")) == 1


def test_bad_maps_are_answered_in_words():
    for bad in ({"9x9": [1]}, {"aruco4x4": 3}, {"aruco4x4": [-1]}, {"aruco4x4": [1.5]}, {"DICT_4X4_50": [1]}):
        out = assign({"items": [item("a")], "reserved": bad})
        assert set(out) == {"error"} and out["error"].startswith("ValueError: reserved"), (bad, out)
    ok = assign({"items": [item("a", "single", "DICT_APRILTAG_36h11")],
                 "reserved": {"DICT_APRILTAG_36h11": [0]}})
    assert ok["result"]["items"][0]["ids"] != [0]


# ------------------------------------------------------------------ 6. pattern_to_sketch, full precision

ROUND_TRIP = {             # name: (request, its cells on the 1e-6 grid)
    "single turned 21": (req(rect=RECT), False),
    "grid turned 90, rotated -33, flipped": (req({"type": "grid", "cols": 3, "rows": 2, "turn": 90, "flip": True},
                                                 rect={"cx": 15.0, "cy": -8.0, "w": 60.0, "h": 40.0,
                                                       "angle_deg": -33.0}), True),
    "charuco 5x4 turned 270, 3D, far from the origin": (req({"type": "charuco", "cols": 5, "rows": 4, "turn": 270},
                                                rect={"cx": 401.0, "cy": 357.0, "w": 80.0, "h": 60.0,
                                                      "angle_deg": 12.5}, pre=D3), False),
    "single with a label, 3D, turned 45, far from the origin": (req({"first_id": 7}, rect={"cx": -250.0, "cy": 300.0,
                                                                                "w": 60.0, "h": 40.0,
                                                                                "angle_deg": 45.0},
                                                        pre=D3, label={"on": True, "text": "#{id}",
                                                                       "side": "right",
                                                                       "place": "outside"}), False),
}
# black's vertices and the cells are each rounded to 1e-6 mm (ND): two
# roundings of half a micron per axis, whatever M is
TWO_ROUNDINGS = 2.0 * 5e-7 * math.sqrt(2.0) + 1e-12


def worst(M, cells, verts) -> float:
    """How far M x the cells' corners (unrounded) are from black's vertices."""
    exact = [(M[0] * u + M[1] * v + M[3], M[4] * u + M[5] * v + M[7]) for u0, v0, u1, v1 in cells
             for u, v in ((u0, v0), (u1, v0), (u1, v1), (u0, v1))]
    return max(min(math.hypot(x - a, y - b) for a, b in exact) for x, y in verts)


@pytest.mark.parametrize("name", list(ROUND_TRIP))
def test_pattern_to_sketch_times_the_cells_gives_black_exactly(name):
    r, on_grid = ROUND_TRIP[name]
    p = W.plan(r)
    M, cells = p["pattern_to_sketch"], p["cells"]
    # full precision: the rotation block is orthonormal to the last bits
    for a, b in ((0, 1), (4, 5)):
        assert M[a] * M[a] + M[b] * M[b] == pytest.approx(1.0, abs=1e-15)
    assert M[0] * M[1] + M[4] * M[5] == pytest.approx(0.0, abs=1e-15)
    verts = {tuple(q) for poly in p["black"] for lp in [poly["outer"]] + poly["holes"] for q in lp}
    if on_grid:
        # the cells lost nothing to their rounding: every vertex of black is
        # a cell corner placed by M, bit for bit
        corners = {tuple(W._pt(M, u, v)) for u0, v0, u1, v1 in cells
                   for u, v in ((u0, v0), (u1, v0), (u1, v1), (u0, v1))}
        assert verts <= corners, sorted(verts - corners)[:5]
    # no drift: far from the origin as near it, only the two roundings
    assert worst(M, cells, verts) <= TWO_ROUNDINGS, name
    # the matrix rounded to 1e-6 (as it was) is off by more: its rotation's
    # error grows with every cell's distance from the pattern's centre
    assert worst([W._r(v) for v in M], cells, verts) > TWO_ROUNDINGS, name


def test_only_pattern_to_sketch_is_full_precision():
    p = W.plan(ROUND_TRIP["single turned 21"][0])
    assert any(v != W._r(v) for v in p["pattern_to_sketch"])
    for key in ("origin", "outer_mm"):
        assert all(v == W._r(v) for v in p[key]), key
    assert all(q == [W._r(q[0]), W._r(q[1])] for poly in p["black"] for q in poly["outer"])
    assert p["origin_z_mm"] == W._r(p["origin_z_mm"])
