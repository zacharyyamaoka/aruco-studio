"""The sheet's own options (2026-10-17, Zach's Q7: "Only in export sheet"):
a white Sticker margin round each sticker (its cut outline grown, the
holes as they are) and the cut lines on / off. 0 / on = the sheet exactly
as before. New behaviour, no REF: tested by its properties (the WYSIWYG
raster check is tests/verify/test_sheet_rule2.py)."""
from __future__ import annotations

import dataclasses
import json

import pytest

from aruco_studio.core import sheet as SH


def item(key, w, h, holes=(), ink=True):
    out = {"outer": [[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2], [-w / 2, h / 2]],
           "holes": [list(map(list, hl)) for hl in holes]}
    black = [[[[-w / 4, -h / 4], [w / 4, -h / 4], [w / 4, h / 4], [-w / 4, h / 4]]]] if ink else []
    return SH.PrintItem(key=key, dictionary="DICT_4X4_50", marker_id=0, marker_length_m=w / 2000.0,
                        cut_mm=out, ink_mm=black, made_by="sticker", name=key)


HOLE = [(-2, 5), (2, 5), (2, 9), (-2, 9)]
ITEMS = [item("a", 30, 30), item("b", 40, 25, [HOLE]), item("c", 60, 40)]


def _box(lp):
    us = [p[0] for p in lp]
    vs = [p[1] for p in lp]
    return (min(us), min(vs), max(us), max(vs))


@pytest.mark.parametrize("mode", ["spaced", "tight"])
def test_no_margin_and_cut_lines_on_is_the_sheet_as_before(mode):
    a = SH.layout_stickers(ITEMS, SH.SheetSettings(mode=mode))
    b = SH.layout_stickers(ITEMS, SH.SheetSettings(mode=mode, sticker_margin_mm=0.0, cut_marks=True))
    assert SH.sticker_summary(a) == SH.sticker_summary(b)
    assert SH.render_sticker_pdf(a, date="2026-10-17") == SH.render_sticker_pdf(b, date="2026-10-17")
    assert "sticker_margin_mm" not in SH.sticker_summary(a) and "cut_lines" not in SH.sticker_summary(a)


@pytest.mark.parametrize("mode", ["spaced", "tight"])
@pytest.mark.parametrize("m", [1.0, 3.0, 6.5])
def test_a_sticker_margin_grows_every_outline_and_keeps_the_holes(mode, m):
    lay = SH.layout_stickers(ITEMS, SH.SheetSettings(mode=mode, sticker_margin_mm=m))
    s = SH.sticker_summary(lay)
    assert s["sticker_margin_mm"] == m and len(s["stickers"]) == 3
    by = {x.key: x for x in ITEMS}
    for st in s["stickers"]:
        u0, v0, u1, v1 = _box(st["outline_mm"]["outer"])
        b0 = _box(by[st["key"]].cut_mm["outer"])
        assert (u0, v0, u1, v1) == pytest.approx((b0[0] - m, b0[1] - m, b0[2] + m, b0[3] + m))
        assert st["outline_mm"]["holes"] == by[st["key"]].cut_mm["holes"]
        w, h = (st["w_mm"], st["h_mm"]) if st["rotation"] == 0 else (st["h_mm"], st["w_mm"])
        assert (w, h) == pytest.approx((b0[2] - b0[0] + 2 * m, b0[3] - b0[1] + 2 * m))
        # the page outline is the grown one too (what the WYSIWYG check traces)
        pu = _box(st["outline_page_mm"]["outer"])
        assert pu[2] - pu[0] == pytest.approx(st["w_mm"], abs=1e-3)
    # the ink is not moved or grown: each sticker's black stays where the plan has it
    for p in lay.placed:
        assert p.item.ink_mm == by[p.item.key].ink_mm


def test_grown_outline_of_a_polygon_and_a_disc():
    import math
    disc = {"outer": [[20 * math.cos(2 * math.pi * k / 96), 20 * math.sin(2 * math.pi * k / 96)]
                      for k in range(96)], "holes": [HOLE]}
    g = SH.grown_outline(disc, 2.0)
    r = [math.hypot(*p) for p in g["outer"]]
    assert min(r) == pytest.approx(22.0, abs=0.01) and max(r) == pytest.approx(22.0, abs=0.02)
    assert g["holes"] == [list(map(list, HOLE))]
    assert SH.grown_outline(disc, 0.0) is disc


@pytest.mark.parametrize("mode", ["spaced", "tight"])
def test_cut_lines_off_draw_no_cut_line(mode):
    on = SH.layout_stickers(ITEMS, SH.SheetSettings(mode=mode))
    off = SH.layout_stickers(ITEMS, SH.SheetSettings(mode=mode, cut_marks=False))
    ops_on = SH.sticker_page_ops(on, 0, "2026-10-17").ops
    ops_off = SH.sticker_page_ops(off, 0, "2026-10-17").ops
    assert any(o[0] == "loops" for o in ops_on)
    assert not any(o[0] == "loops" for o in ops_off)
    if mode == "spaced":
        assert not any(o[0] == "line" and abs(o[5] - SH.CUT_GREY) < 1e-9 for o in ops_off)
    # the same places, the same ink
    assert [(p.x_mm, p.y_mm) for p in on.placed] == [(p.x_mm, p.y_mm) for p in off.placed]
    assert [o for o in ops_on if o[0] == "fill"] == [o for o in ops_off if o[0] == "fill"]
    assert SH.sticker_summary(off)["cut_lines"] is False
    svg = SH.render_sticker_svg(off, date="2026-10-17")
    assert "data-cut=" not in svg


def test_a_margin_can_push_a_sticker_off_the_page():
    big = item("big", 190, 40)
    lay0 = SH.layout_stickers([big], SH.SheetSettings())
    assert lay0.placed and lay0.placed[0].rotation == 0
    lay = SH.layout_stickers([big], SH.SheetSettings(sticker_margin_mm=5.0))
    assert lay.placed and lay.placed[0].rotation == 90          # 200 mm wide now: it turns
    lay2 = SH.layout_stickers([item("long", 230, 200)], SH.SheetSettings(sticker_margin_mm=5.0))
    assert lay2.rejected and "printable area" in lay2.rejected[0].reason
