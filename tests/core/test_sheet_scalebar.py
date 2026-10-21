"""The "scale bar" option (SheetSettings.scale_bar: "hide" | "first" | "every";
Zach 2026-10-20 night) on every path that draws a page, not only
layout_stickers: core.sheet.layout_sheet (the shelf layout), and the ArUco
Export path that sits on it, core.markers.sheet_layout / sheet_check /
sidecar_files. "first" draws the 100 mm / 4 in bar on page 1 only and gives
the band it would take to pages 2+; "hide" draws none; "every" (and an
absent setting) is what these paths drew before the option existed, byte for
byte (pinned below: the digests were taken on main @ 65164e4)."""
from __future__ import annotations

import datetime
import hashlib
import json
import re
import types
import zlib

import pytest

from aruco_studio.core import markers as M
from aruco_studio.core import sheet as SH

DATE = "2026-10-20"
BAR_TEXT = "must measure 100 mm"              # the bar's caption, on its page only
IN_BAR = "(4 in)"


def make_res(n, length=0.04, grid_copies=0):
    """n singles (one component, n occurrences), then `grid_copies` 3 x 2 grids."""
    tags = [M.TagDef(key="t", component="P", name="Tag",
                     spec=M.TagSpec(dictionary="DICT_4X4_250", marker_id=0,
                                    marker_length_m=length))]
    occs = [M.OccurrenceRef(f"P:{i}", "P") for i in range(1, n + 1)]
    if grid_copies:
        tags.append(M.TagDef(key="g", component="G", name="Grid",
                             spec=M.TagSpec(dictionary="DICT_4X4_250", marker_id=100,
                                            marker_length_m=0.03, layout="grid", rows=2,
                                            cols=3, separation_m=0.006)))
        occs += [M.OccurrenceRef(f"G:{i}", "G") for i in range(1, grid_copies + 1)]
    return M.resolve(tags, [], occs)


def items_of(n):
    return M.print_items(make_res(n))


def pdf_pages(raw):
    """The text of each PDF page's content stream (the streams are Flate)."""
    streams = [zlib.decompress(m.group(1)) for m in
               re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", raw, re.S)
               if m.group(1)[:1] == b"x"]
    return [s.decode("latin-1") for s in streams]


def bars(raw):
    """Per page: does it draw the 100 mm bar (its caption) / the 4 in bar?"""
    pages = pdf_pages(raw)
    assert [(BAR_TEXT in p) for p in pages] == [(IN_BAR in p) for p in pages]
    return [BAR_TEXT in p for p in pages]


def sha(data) -> str:
    if not isinstance(data, bytes):
        data = json.dumps(data, sort_keys=True).encode()
    return hashlib.sha256(data).hexdigest()


class FakeDate(datetime.date):
    @classmethod
    def today(cls):
        return cls(2026, 10, 20)


@pytest.fixture
def fixed_today(monkeypatch):
    """sidecar_files dates its PDF with today's date; pin it."""
    monkeypatch.setattr(SH, "datetime", types.SimpleNamespace(date=FakeDate))


def bottom(placed):
    return max(p.cell[1] + p.cell[3] for p in placed)


# ------------------------------------------------ "every" / absent: byte for byte

CASES = {
    "40 singles, letter": dict(n=40),
    "40 singles, a4 landscape, margin 5": dict(n=40, page="a4", landscape=True, margin_mm=5.0),
    "3 singles": dict(n=3),
    "12 singles and 3 grids, a4": dict(n=12, grid=3, page="a4"),
}
# sha256 of sha(layout_sheet path), sha(markers.sheet_layout path), sha(sidecar_files) per
# case, taken with the code of main @ 65164e4 (before scale_bar was read here)
TODAY = {
    "40 singles, letter": "ff6c02bf8c8ad5de5710385a80a2f0e38f182c534ce1326d85affedb5d46ebf2",
    "40 singles, a4 landscape, margin 5": "8fde664340cd6bd84ca26930f9936f1eac42a06dd7df9c987411487811d8ab1a",
    "3 singles": "94615ef51478867eef2baf97dd243e8d5a193cfbcab13e8b7cb877b7f82d9346",
    "12 singles and 3 grids, a4": "22635accbbe020118bcd5a7f1b682ce260f6fb0ebde19e43f92c4217c0ae93d9",
}


def digest_case(name, extra=None, fixed_date=FakeDate):
    """The three paths' outputs for a case, as one digest. `extra`: kwargs the
    paths take besides the old ones (empty: the call as it was at 65164e4)."""
    c = dict(CASES[name])
    extra = extra or {}
    res = make_res(c["n"], grid_copies=c.get("grid", 0))
    page, landscape = c.get("page", "letter"), c.get("landscape", False)
    margin = c.get("margin_mm", 10.0)
    settings = SH.SheetSettings(page=page, landscape=landscape, margin_mm=margin,
                                title="Design — ArUco tags", **extra)
    lay_a = SH.layout_sheet(M.print_items(res), settings)
    part_a = [sha(SH.layout_summary(lay_a)), sha(SH.render_layout_pdf(lay_a, date=DATE))]
    lay_b = M.sheet_layout(res, page=page, landscape=landscape, margin_mm=margin, **extra)
    part_b = [sha(SH.layout_summary(lay_b)), sha(SH.render_layout_pdf(lay_b, date=DATE)),
              sha(M.sheet_check(res, page=page, landscape=landscape, margin_mm=margin, **extra))]
    old = SH.datetime
    SH.datetime = types.SimpleNamespace(date=fixed_date)
    try:
        files = M.sidecar_files(res, page=page, landscape=landscape, exported_at=DATE,
                                margin_mm=margin, **extra)
    finally:
        SH.datetime = old
    part_c = [(k, sha(v)) for k, v in sorted(files.items())]
    return sha([part_a, part_b, part_c])


@pytest.mark.parametrize("name", list(CASES))
def test_every_and_absent_reproduce_todays_bytes(name):
    assert digest_case(name) == TODAY[name]
    assert digest_case(name, dict(scale_bar="every")) == TODAY[name]


def test_core_default_is_every():
    assert SH.SheetSettings().scale_bar == "every"
    lay = SH.layout_sheet(items_of(40))
    assert lay.scale_bar == "every" and lay.rest_h_mm == 0.0
    assert "scale_bar" not in SH.layout_summary(lay)


def test_a_one_page_sheet_is_the_same_under_first_and_every():
    its = items_of(3)
    a = SH.layout_sheet(its, SH.SheetSettings(scale_bar="first"))
    b = SH.layout_sheet(its, SH.SheetSettings(scale_bar="every"))
    assert SH.render_layout_pdf(a, date=DATE) == SH.render_layout_pdf(b, date=DATE)
    assert a.page_count == 1 and bars(SH.render_layout_pdf(a, date=DATE)) == [True]


def test_an_unknown_mode_is_refused():
    with pytest.raises(ValueError, match="scale_bar is one of"):
        SH.layout_sheet(items_of(3), SH.SheetSettings(scale_bar="sometimes"))


# ------------------------------------------------ layout_sheet: which pages carry the bar

@pytest.mark.parametrize("mode,expect_pages,expect_bars", [
    ("every", 5, [True] * 5),
    ("first", 4, [True, False, False, False]),
    ("hide", 4, [False] * 4),
])
def test_layout_sheet_draws_the_bar_on_the_right_pages(mode, expect_pages, expect_bars):
    lay = SH.layout_sheet(items_of(40), SH.SheetSettings(scale_bar=mode))
    pdf = SH.render_layout_pdf(lay, date=DATE)
    assert lay.page_count == expect_pages
    assert bars(pdf) == expect_bars
    assert [p.count(IN_BAR) for p in pdf_pages(pdf)] == [int(b) for b in expect_bars]
    assert (lay.ruler is None) == (mode == "hide")


def test_layout_sheet_gives_the_band_to_pages_without_the_bar():
    x0, y0, w, h = SH.layout_sheet(items_of(40), SH.SheetSettings(scale_bar="every")).printable_mm
    y1 = y0 + h
    every = SH.layout_sheet(items_of(40), SH.SheetSettings(scale_bar="every"))
    first = SH.layout_sheet(items_of(40), SH.SheetSettings(scale_bar="first"))
    hide = SH.layout_sheet(items_of(40), SH.SheetSettings(scale_bar="hide"))
    assert [len(p) for p in every.pages] == [9, 9, 9, 9, 4]
    assert [len(p) for p in first.pages] == [9, 12, 12, 7]
    assert [len(p) for p in hide.pages] == [12, 12, 12, 4]
    # page 1 stays above its bar; pages 2+ reach into the band, and no further
    assert bottom(first.pages[0]) <= y1 + 1e-6
    assert y1 + 1.0 < bottom(first.pages[1]) <= y1 + SH.RULER_H_MM + 1e-6
    assert all(bottom(p) <= y1 + 1e-6 for p in every.pages)
    assert hide.printable_mm[3] == pytest.approx(h + SH.RULER_H_MM)
    assert all(bottom(p) <= hide.printable_mm[1] + hide.printable_mm[3] + 1e-6
               for p in hide.pages)
    assert sum(len(p) for p in first.pages) == sum(len(p) for p in hide.pages) == 40


def test_layout_sheet_summary_says_which_pages_when_not_every():
    s = SH.layout_summary(SH.layout_sheet(items_of(40), SH.SheetSettings(scale_bar="first")))
    assert s["scale_bar"] == "first" and s["rest_h_mm"] > s["printable_mm"]["h"]
    h = SH.layout_summary(SH.layout_sheet(items_of(40), SH.SheetSettings(scale_bar="hide")))
    assert h["ruler"] is None and "scale_bar" not in h


def test_ruler_false_is_still_none_under_every_mode():
    for mode in ("hide", "first", "every"):
        lay = SH.layout_sheet(items_of(40), SH.SheetSettings(ruler=False, scale_bar=mode))
        assert lay.ruler is None and lay.scale_bar == "every"
        assert not any(bars(SH.render_layout_pdf(lay, date=DATE)))


def test_a_page_too_narrow_for_the_bar_still_warns_unless_hidden():
    narrow = dict(custom_page_mm=(100, 150))
    every = SH.layout_sheet([], SH.SheetSettings(scale_bar="first", **narrow))
    assert every.ruler is None and every.warnings
    hide = SH.layout_sheet([], SH.SheetSettings(scale_bar="hide", **narrow))
    assert hide.ruler is None and not hide.warnings


# ------------------------------------------------ markers.sheet_layout / sheet_check / sidecar_files

@pytest.mark.parametrize("mode,expect_bars", [
    ("every", [True] * 5),
    ("first", [True, False, False, False]),
    ("hide", [False] * 4),
])
def test_markers_sheet_layout_follows_the_setting(mode, expect_bars):
    res = make_res(40)
    lay = M.sheet_layout(res, scale_bar=mode)
    assert bars(SH.render_layout_pdf(lay, date=DATE)) == expect_bars
    assert [len(p) for p in lay.pages] == {"every": [9, 9, 9, 9, 4], "first": [9, 12, 12, 7],
                                          "hide": [12, 12, 12, 4]}[mode]
    assert M.sheet_check(res, scale_bar=mode)["pages"] == len(expect_bars)


@pytest.mark.parametrize("mode,expect_bars", [
    ("every", [True] * 5),
    ("first", [True, False, False, False]),
    ("hide", [False] * 4),
])
def test_sidecar_files_pdf_and_json_follow_the_setting(mode, expect_bars, fixed_today):
    files = M.sidecar_files(make_res(40), exported_at=DATE, scale_bar=mode)
    assert bars(files["aruco/print_letter.pdf"]) == expect_bars
    doc = json.loads(files["aruco/markers.json"])["print_sheet"]
    assert doc["pages"] == len(expect_bars)
    assert (doc["ruler"] is None) == (mode == "hide")
    assert doc.get("scale_bar") == ("first" if mode == "first" else None)


def test_sidecar_files_default_is_every(fixed_today):
    res = make_res(40)
    assert bars(M.sidecar_files(res)["aruco/print_letter.pdf"]) == [True] * 5
    assert M.sidecar_files(res) == M.sidecar_files(res, scale_bar="every")


# ------------------------------------------------ the sticker sheet still honours it

def test_layout_stickers_unchanged_by_this_lane():
    its = [SH.PrintItem(key="a%d" % i, dictionary="DICT_4X4_50", marker_id=i,
                        marker_length_m=0.045) for i in range(40)]
    pdfs = {mode: SH.render_sticker_pdf(SH.layout_stickers(its, SH.SheetSettings(scale_bar=mode)),
                                        date=DATE) for mode in ("every", "first", "hide")}
    assert bars(pdfs["first"])[0] is True and not any(bars(pdfs["first"])[1:])
    assert not any(bars(pdfs["hide"]))
    assert all(bars(pdfs["every"])) and len(bars(pdfs["every"])) > 1
