"""M6a.6, M6a.7, M6a.9: the sticker sheet, spaced or tight
(core.sheet.layout_stickers), odd shapes by their boxes, and the SVG beside
the PDF with the same numbers as sheet.json."""
from __future__ import annotations

import json
import re
import zlib

import pytest

from aruco_studio.core import sheet as SH
from aruco_studio.plan import target as T
from aruco_studio.plan.spec import TagSpec
from aruco_studio.scene import Scene, renumber
from aruco_studio.scene import sheet as SS

STK = {"rule": 1, "by": "sticker"}


def item(key, w, h, holes=(), marker_m=0.02, ids=(0,), name=""):
    a, b = w / 2.0, h / 2.0
    return SH.PrintItem(key=key, dictionary="DICT_4X4_50", marker_id=ids[0],
                        marker_length_m=marker_m,
                        outline_mm={"outer": [[-a, -b], [a, -b], [a, b], [-a, b]],
                                    "holes": [list(hh) for hh in holes]},
                        ink_mm=[], ids=list(ids), name=name or key, made_by="sticker")


def lay(items, mode, page="letter", **kw):
    return SH.layout_stickers(items, SH.SheetSettings(page=page, mode=mode, **kw))


# ------------------------------------------------------------ M6a.6

def test_four_identical_30_mm_stickers_tight_one_shelf_7_cuts():
    L = lay([item(f"t{i}", 30, 30, ids=(i,)) for i in range(4)], "tight")
    assert not L.rejected and L.page_count == 1
    assert len(L.shelves) == 1 and len(L.shelves[0]["keys"]) == 4
    xs = sorted(p.x_mm for p in L.placed)
    assert [round(b - a, 9) for a, b in zip(xs, xs[1:])] == [30.0, 30.0, 30.0]  # shared cuts
    assert len({p.y_mm for p in L.placed}) == 1
    assert L.cuts() == 7                     # 2 long + 5 short (16 for four rectangles)
    assert lay([item(f"t{i}", 30, 30, ids=(i,)) for i in range(4)], "spaced").cuts() == 16


def _crosses(L):
    """(shelf line y, sticker) pairs where a sticker straddles a shelf's line."""
    bad = []
    for sh in L.shelves:
        for y in (sh["y"], sh["y"] + sh["h"]):
            for p in L.pages[sh["page"]]:
                if p.y_mm + 1e-9 < y < p.y_mm + p.h_mm - 1e-9:
                    bad.append((y, p.item.key))
    return bad


def test_three_sizes_tight_one_shelf_per_height_straight_full_width_cuts():
    its = ([item(f"a{i}", 30, 30, ids=(i,)) for i in range(5)]
           + [item(f"b{i}", 45, 20, ids=(10 + i,)) for i in range(3)]
           + [item(f"c{i}", 25, 40, ids=(20 + i,)) for i in range(4)])
    L = lay(its, "tight")
    assert not L.rejected
    heights = sorted({round(sh["h"], 6) for sh in L.shelves}, reverse=True)
    assert heights == [40.0, 30.0, 20.0] and len(L.shelves) == 3
    for sh in L.shelves:
        hs = {round(p.h_mm, 6) for p in L.placed if p.shelf == sh["index"]}
        assert hs == {round(sh["h"], 6)}
    # the shelves are stacked with no gap and no sticker crosses a shelf line
    ys = sorted((sh["y"], sh["h"]) for sh in L.shelves)
    for (y0, h0), (y1, _h1) in zip(ys, ys[1:]):
        assert y1 == pytest.approx(y0 + h0)
    assert not _crosses(L)
    # identical sizes side by side
    for sh in L.shelves:
        keys = sh["keys"]
        assert keys == sorted(keys, key=lambda k: (k[0], int(k[1:])))
    assert L.cuts() == (3 + 1) + (5 + 1) + (3 + 1) + (4 + 1)


def test_spaced_has_a_caption_and_crop_marks_per_sticker():
    its = [item(f"s{i}", 30, 30, ids=(i,), name=f"arm{i}") for i in range(3)]
    for it in its:
        it.caption = f"#{it.ids[0]} · {it.name} · 4X4_50 · 20.0 mm"
    L = lay(its, "spaced")
    xs = sorted(p.x_mm for p in L.placed)
    assert [round(b - a, 6) for a, b in zip(xs, xs[1:])] == [34.0, 34.0]   # gap_mm 4
    ops = SH.sticker_page_ops(L, 0, "2026-10-16").ops
    lines = [o for o in ops if o[0] == "line"]
    assert len(lines) == 8 * 3                        # two short lines at each corner
    for o in lines:                                   # outside the sticker, never inside
        for p in L.placed:
            x0, y0, x1, y1 = p.x_mm, p.y_mm, p.x_mm + p.w_mm, p.y_mm + p.h_mm
            for x, y in ((o[1], o[2]), (o[3], o[4])):
                assert not (x0 + 1e-6 < x < x1 - 1e-6 and y0 + 1e-6 < y < y1 - 1e-6)
    texts = [o[3] for o in ops if o[0] == "text"]
    for it in its:
        assert it.caption in texts
    tight = SH.sticker_page_ops(lay(its, "tight"), 0, "2026-10-16").ops
    assert not [o for o in tight if o[0] == "line"]
    assert not [o for o in tight if o[0] == "text" and o[3].startswith("#")]
    assert [o for o in tight if o[0] == "text" and o[3].startswith("row 1: #0-2")]


def test_spaced_packs_as_todays_first_fit_decreasing_shelves():
    """The same items, no captions: layout_stickers (spaced) puts every
    sticker where REF's layout_sheet puts it."""
    its = [SH.PrintItem(key=f"k{i}", dictionary="DICT_4X4_50", marker_id=i,
                        marker_length_m=m) for i, m in enumerate((0.03, 0.02, 0.045, 0.02, 0.06))]
    st = SH.SheetSettings(page="letter", labels=False, id_mark="off", orient_mark="off")
    ref = SH.layout_sheet(its, st)
    mine = SH.layout_stickers(its, SH.SheetSettings(page="letter", labels=False))
    a = {p.item.key: (round(p.x_mm, 6), round(p.y_mm, 6)) for p in ref.placed}
    b = {p.item.key: (round(p.x_mm, 6), round(p.y_mm, 6)) for p in mine.placed}
    assert a == b


@pytest.mark.parametrize("mode", ["spaced", "tight"])
def test_a_400_mm_sticker_is_rejected_with_a_reason(mode):
    L = lay([item("big", 400, 30), item("ok", 30, 30)], mode)
    assert [r.item.key for r in L.rejected] == ["big"]
    assert "never scaled" in L.rejected[0].reason and "400.0 x 30.0 mm" in L.rejected[0].reason
    assert [p.item.key for p in L.placed] == ["ok"]


def test_a_sticker_longer_than_the_page_turns():
    L = lay([item("long", 210, 25)], "spaced")
    p = L.placed[0]
    assert p.rotation == 90 and (p.w_mm, p.h_mm) == pytest.approx((25.0, 210.0))
    # never mirrored: the frame's +u lands on the page's -y (up), +v on -x
    x0, y0 = p.to_page(0, 0)
    x1, y1 = p.to_page(1, 0)
    x2, y2 = p.to_page(0, 1)
    assert (x1 - x0, y1 - y0) == pytest.approx((0, -1)) and (x2 - x0, y2 - y0) == \
        pytest.approx((-1, 0))


# ------------------------------------------------------------ M6a.7 odd shapes

def odd_scene():
    sc = Scene(name="odd")
    for k, key in enumerate(("disc4", "dshape", "lshape", "plate_hole")):
        sc.add(TagSpec(settings={"layout": "single", "make": dict(STK, perimeter="profile")},
                       target=T.from_face(key)), x_mm=90 * k)
    long = T.from_loops([[(0, 0), (210, 0), (210, 20), (0, 20)]], name="strip 210")
    sc.add(TagSpec(settings={"layout": "single", "make": dict(STK, perimeter="profile")},
                   target=long), y_mm=100)
    renumber(sc)
    return sc


@pytest.mark.parametrize("mode", ["spaced", "tight"])
def test_odd_shapes_are_packed_by_their_boxes_with_every_cut_line(mode):
    sc = odd_scene()
    got = SS.sticker_files(sc, mode=mode, date="2026-10-16")
    L = got["layout"]
    assert not L.rejected and len(L.placed) == 5
    summ = json.loads(got["sheet.json"])
    plans = sc.plans()
    for st in summ["stickers"]:
        cut = plans[st["key"]].data["guides"]["cut_line"]
        b = st["box_mm"]
        us = [q[0] for q in cut["outer"]]
        vs = [q[1] for q in cut["outer"]]
        assert b == pytest.approx([min(us), min(vs), max(us), max(vs)], abs=1e-4)
        w, h = b[2] - b[0], b[3] - b[1]
        assert (st["w_mm"], st["h_mm"]) == pytest.approx((h, w) if st["rotation"] else (w, h),
                                                        abs=1e-4)
        for k in ("page", "x_mm", "y_mm", "rotation", "outline_mm", "outline_page_mm"):
            assert k in st
        assert len(st["outline_mm"]["holes"]) == len(cut["holes"])
    strip = next(s for s in summ["stickers"] if s["key"] == sc.tags[4].name)
    assert strip["rotation"] == 90                   # 210 mm: only fits turned
    # the PDF strokes every outline and hole as a grey hairline
    ops = [o for i in range(L.page_count) for o in SH.sticker_page_ops(L, i, "x").ops]
    loops = [o for o in ops if o[0] == "loops"]
    assert len(loops) == 5
    for o in loops:
        key = o[4]
        cut = plans[key].data["guides"]["cut_line"]
        assert len(o[1]) == 1 + len(cut["holes"])
        assert (o[2], o[3]) == (SH.CUT_GREY, SH.CUT_LINE_MM)
    assert sum(len(o[1]) - 1 for o in loops) == 4 + 1          # disc4's 4, the plate's 1
    pdf = got["sheet.pdf"]
    streams = re.findall(rb"stream\n(.*?)\nendstream", pdf, re.S)
    body = b"".join(zlib.decompress(s) for s in streams)
    assert body.count(b"0.55 G 0.2835 w" + b"\n") == 5 and b"f*" in body  # a stroked path each
    if mode == "tight":
        # the box edges are not drawn: only outlines are cut lines
        assert not [o for o in ops if o[0] == "line" and o[5] == SH.CUT_GREY
                    and abs(o[1] - o[3]) > 3.0]


# ------------------------------------------------------------ M6a.9 the SVG

@pytest.mark.parametrize("mode", ["spaced", "tight"])
@pytest.mark.parametrize("page", ["letter", "a4"])
def test_the_svg_and_sheet_json_agree(mode, page):
    sc = odd_scene()
    for k in range(4):
        sc.add(TagSpec(settings={"layout": ("single", "grid", "charuco", "single")[k],
                                 "make": dict(STK)}, target=T.box(40 + 10 * k, 40, 0)),
               y_mm=200)
    renumber(sc)
    got = SS.sticker_files(sc, page=page, mode=mode, date="2026-10-16")
    summ = json.loads(got["sheet.json"])
    svg = got["sheet.svg"].decode("utf-8")
    rects = {}
    for m in re.finditer(r'<rect data-sticker="([^"]+)"[^>]*?data-page="(\d+)" '
                         r'data-x="([-\d.]+)" data-y="([-\d.]+)" data-w="([-\d.]+)" '
                         r'data-h="([-\d.]+)" data-rotation="(\d+)"', svg):
        rects[m.group(1)] = (int(m.group(2)),) + tuple(float(m.group(i)) for i in range(3, 7)) \
            + (int(m.group(7)),)
    assert len(rects) == len(summ["stickers"]) == 9
    for st in summ["stickers"]:
        pg, x, y, w, h, rot = rects[st["key"]]
        assert pg == st["page"] and rot == st["rotation"]
        for a, b in ((x, st["x_mm"]), (y, st["y_mm"]), (w, st["w_mm"]), (h, st["h_mm"])):
            assert abs(a - b) <= 0.01
    assert f'data-pages="{summ["pages"]}"' in svg and f'data-mode="{mode}"' in svg
    W, H = SH.PAGE_SIZES_MM[page]
    assert f'width="{W:g}mm"' in svg
