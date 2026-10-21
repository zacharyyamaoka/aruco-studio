"""The Print dialog's "Scale bar" option (barrier 12, Zach 2026-10-20 night:
"Hide, show on first page, show on every page"), in the facade
(web_api.sheet, contract.ts SheetRequest.scale_bar): which pages of a
multi-page sheet draw the 100 mm / 4 in bar AND keep its band. "every" is
what every page always had; "first" (the default) gives pages 2+ the band's
area for stickers; "hide" has none and says so."""
from __future__ import annotations

import base64
import hashlib
import json
import re
import zlib

import pytest

from aruco_studio import web_api as W
from aruco_studio.core import sheet as SH

from test_web_api import req
from test_web_layout import LETTER_AREA, placed, squares

DATE = "2026-10-20"
NOTE = "No scale bar: measure a marker to check the print is at 100 %"
BAR_TEXT = "must measure 100 mm"              # the bar's caption, on its page only
# the 100 mm bar itself (not a tick): a 100 x 1.2 mm filled rectangle
BAR_RECT = re.compile(r"h100v1\.2h-100z")


def big(n, side=44.0):
    return [req({"first_id": i, "dictionary": "DICT_4X4_250"}, rect={"w": side, "h": side})
            for i in range(n)]


def tiles(n, **kw):
    """41.5 mm stickers edge to edge: 4 x 5 = 20 to a Letter page under the
    bar's band, 4 x 6 = 24 without it."""
    return run(big(n, 41.5), mode="tight", **kw)


def run(items, **kw):
    return W.sheet({"items": items, "cut_lines": True, **kw}, DATE)


def pdf_pages(got):
    """The text of each PDF page's content stream (the streams are Flate)."""
    raw = base64.b64decode(got["pdf_base64"])
    streams = [zlib.decompress(m.group(1)) for m in
               re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", raw, re.S)
               if m.group(1)[:1] == b"x"]
    return [s.decode("latin-1") for s in streams]


def svg_bars(got):
    return [BAR_TEXT in s for s in got["svg"]]


def per_page(got):
    pages = [0] * got["pages"]
    for p in placed(got):
        pages[p["page"] - 1] += 1
    return pages


def lowest(got, page):
    return max(p["box"][3] for p in placed(got) if p["page"] == page)


# ------------------------------------------------ "every": today's output, byte for byte

# sha256 of json.dumps(web_api.sheet(request, "2026-10-20"), sort_keys=True), taken on
# main @ bca680c before scale_bar existed (the facade answered these for every page)
TODAY = {
    "spaced 30 labelled": "bdc30fa550ca7943ab26107aee63dcfa89a4cba011a87ec61e7fd06650c033e4",
    "tight 30": "b561b2a66eaf72440486d13d912162bbc7aee588bb415ba2469abfd83ecaf668",
    "spaced 26 x 50 mm, fewest cuts": "a894409c0a560aee1d72c701619aa7a9a1ba456d222bc795a0d616e0a83a3785",
    "one page of 6": "8f7e2ca9f55e5d13bc02d302e52663c521aefc94b0054a547a49605812700104",
    "mixed with three grids, gap 6": "5ab759002d8ac5ec5970f8ca866b6b97e9110a14d40794afb6833b7c2b027c00",
}
GRID = req({"type": "grid", "cols": 3, "rows": 2, "first_id": 20}, rect={"w": 120, "h": 90})
CASES = {
    "spaced 30 labelled": {"items": squares(30, label=True), "cut_lines": True},
    "tight 30": {"items": squares(30), "cut_lines": True, "mode": "tight"},
    "spaced 26 x 50 mm, fewest cuts": {"items": squares(26, 50.0), "cut_lines": True,
                                       "objective": "fewest_cuts"},
    "one page of 6": {"items": squares(6, label=True), "cut_lines": True},
    "mixed with three grids, gap 6": {"items": squares(14, 45.0) + [GRID] * 3,
                                      "cut_lines": True, "gap_mm": 6.0},
}


@pytest.mark.parametrize("name", list(CASES))
def test_every_reproduces_todays_sheet_byte_for_byte(name):
    got = W.sheet(dict(CASES[name], scale_bar="every"), DATE)
    digest = hashlib.sha256(json.dumps(got, sort_keys=True).encode()).hexdigest()
    assert digest == TODAY[name]


def test_core_default_is_every_so_other_callers_keep_their_bytes():
    assert SH.SheetSettings().scale_bar == "every"


def test_a_one_page_sheet_is_the_same_under_first_and_every():
    one = {"items": squares(6, label=True), "cut_lines": True}
    assert W.sheet(dict(one, scale_bar="first"), DATE) == W.sheet(dict(one, scale_bar="every"), DATE)
    assert W.sheet(one, DATE) == W.sheet(dict(one, scale_bar="every"), DATE)       # first is the default


# ------------------------------------------------ which pages carry the bar

def test_every_has_the_bar_on_each_page_in_the_pdf_and_the_svg():
    got = run(big(40), scale_bar="every")
    assert got["pages"] == 3
    assert svg_bars(got) == [True, True, True]
    assert all(BAR_RECT.search(s) for s in got["svg"])
    pages = pdf_pages(got)
    assert len(pages) == 3 and all("(" + "Print at 100%" in p and BAR_TEXT in p for p in pages)
    assert [p.count("(4 in)") for p in pages] == [1, 1, 1]
    assert not [w for w in got["warnings"] if w["text"] == NOTE]


def test_first_has_the_bar_on_page_1_only_in_the_pdf_and_the_svg():
    got = run(big(40), scale_bar="first")
    assert got["pages"] == 3
    assert svg_bars(got) == [True, False, False]
    assert [bool(BAR_RECT.search(s)) for s in got["svg"]] == [True, False, False]
    assert [">4 in<" in s for s in got["svg"]] == [True, False, False]
    pages = pdf_pages(got)
    assert len(pages) == 3
    assert [BAR_TEXT in p for p in pages] == [True, False, False]
    assert [p.count("(4 in)") for p in pages] == [1, 0, 0]
    assert not [w for w in got["warnings"] if w["text"] == NOTE]


def test_first_is_the_default():
    items = big(40)
    assert run(items) == run(items, scale_bar="first")
    assert run(items) != run(items, scale_bar="every")


def test_hide_has_no_bar_anywhere_and_an_info_issue():
    got = run(big(40), scale_bar="hide")
    assert svg_bars(got) == [False] * got["pages"]
    assert not any(BAR_RECT.search(s) or ">4 in<" in s or ">100 mm<" in s for s in got["svg"])
    assert all(BAR_TEXT not in p and "(4 in)" not in p for p in pdf_pages(got))
    assert {"field": "tag", "level": "info", "text": NOTE} in got["warnings"]
    for other in ("first", "every"):
        assert NOTE not in [w["text"] for w in run(big(40), scale_bar=other)["warnings"]]


def test_the_footer_stays_on_every_page_whatever_the_bar():
    for sb in ("hide", "first", "every"):
        got = run(big(40), scale_bar=sb)
        assert all(f"page {i + 1}/3" in s for i, s in enumerate(got["svg"]))


# ------------------------------------------------ the band's area goes to stickers

def test_a_page_without_the_bar_fits_more_stickers():
    every, first, hide = (tiles(66, scale_bar=sb) for sb in ("every", "first", "hide"))
    pe, pf, ph = per_page(every), per_page(first), per_page(hide)
    assert sum(pe) == sum(pf) == sum(ph) == 66          # nobody is dropped
    assert pe == [20, 20, 20, 6]
    assert pf[0] == pe[0] == 20                         # page 1 keeps its band
    assert pf[1:3] == [24, 22]                          # pages 2+ fit at least as many
    assert all(f >= e for f, e in zip(pf[1:], pe[1:]))
    assert ph[0] == 24                                  # hide: page 1 has the band too
    assert every["pages"] == 4 and first["pages"] == 3 and hide["pages"] == 3   # a sheet saved


def test_page_1_stays_above_the_bar_and_pages_2_plus_use_its_band():
    x0, y0, x1, y1 = LETTER_AREA
    first = tiles(66, scale_bar="first")
    assert lowest(first, 1) <= y1 + 1e-3
    assert lowest(first, 2) > y1 + 1.0                  # into the band's 19 mm
    assert lowest(first, 2) <= y1 + SH.RULER_H_MM + 1e-3
    area = sum((p["box"][2] - p["box"][0]) * (p["box"][3] - p["box"][1]) for p in placed(first))
    capacity = (x1 - x0) * ((y1 - y0) + (first["pages"] - 1) * (y1 - y0 + SH.RULER_H_MM))
    assert first["fill"] == pytest.approx(area / capacity, abs=2e-3)
    every = tiles(66, scale_bar="every")
    assert all(lowest(every, k) <= y1 + 1e-3 for k in range(1, every["pages"] + 1))
    hide = tiles(66, scale_bar="hide")
    assert all(lowest(hide, k) <= y1 + SH.RULER_H_MM + 1e-3 for k in range(1, hide["pages"] + 1))


@pytest.mark.parametrize("mode", ["spaced", "tight"])
@pytest.mark.parametrize("objective", ["fewest_sheets", "fewest_cuts"])
def test_every_mode_and_objective_respects_the_pages_areas(mode, objective):
    x0, y0, x1, y1 = LETTER_AREA
    got = run(big(52), scale_bar="first", mode=mode, objective=objective)
    ps = placed(got)
    assert len(ps) == 52
    for p in ps:
        limit = y1 if p["page"] == 1 else y1 + SH.RULER_H_MM
        assert p["box"][3] <= limit + 1e-3 and p["box"][1] >= y0 - 1e-3


def test_the_shelf_packer_follows_the_option_too():
    its = [SH.PrintItem(key=f"k{i}", dictionary="DICT_4X4_50", marker_id=i,
                        marker_length_m=0.030) for i in range(60)]
    base = SH.SheetSettings(page="letter", margin_mm=10.0)
    import dataclasses
    lays = {sb: SH.layout_stickers(its, dataclasses.replace(base, scale_bar=sb))
            for sb in ("every", "first", "hide")}
    count = {sb: [len(p) for p in lay.pages] for sb, lay in lays.items()}
    assert all(c1 >= c0 for c0, c1 in zip(count["every"][1:], count["first"][1:]))
    assert lays["first"].ruler is not None and lays["hide"].ruler is None
    ops = lambda lay, i: [o for o in SH.sticker_page_ops(lay, i, DATE).ops if o[0] == "text"]
    has = lambda lay, i: any(BAR_TEXT in o[3] for o in ops(lay, i))
    assert [has(lays["first"], i) for i in range(lays["first"].page_count)] == \
        [True] + [False] * (lays["first"].page_count - 1)
    assert all(has(lays["every"], i) for i in range(lays["every"].page_count))
    assert not any(has(lays["hide"], i) for i in range(lays["hide"].page_count))


# ------------------------------------------------ guards

def test_an_unknown_scale_bar_is_an_error_not_a_guess():
    with pytest.raises(ValueError, match="scale_bar is one of hide, first, every"):
        run(big(2), scale_bar="sometimes")
    out = json.loads(W.call("sheet", json.dumps({"items": big(2), "scale_bar": "sometimes"})))
    assert "scale_bar is one of" in out["error"]


def test_a_sticker_too_tall_for_page_1_is_refused_under_first_as_under_every():
    tall = [req({"first_id": 0}, rect={"w": 40.0, "h": 240.0})]    # fits a bare Letter page only
    assert [w["level"] for w in run(tall, scale_bar="every")["warnings"]].count("error") == 1
    assert [w["level"] for w in run(tall, scale_bar="first")["warnings"]].count("error") == 1
    assert [w["level"] for w in run(tall, scale_bar="hide")["warnings"]].count("error") == 0
