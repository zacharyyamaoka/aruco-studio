"""Print margins and keep-clear boxes (Zach, 2026-11-13), in the facade
(web_api.sheet, contract.ts SheetRequest.margins_mm / keep_clear).

Zach: "make it so I can add custom spacing margins, top bottom left right
when I go to print ... helpful if I manually want to offset where it starts
to print from ... whenever I set a new edge then it should recalculate. Or
perhaps I can just draw boxes on the pages that you need to keep clear ...
helpful as I try to reprint on the same page I have already cut ... it's on
a per page basis."

* `margins_mm` {top?, right?, bottom?, left?}: each side given replaces the
  preset's margin_mm on that side (a side left out keeps the preset's). The
  printable area, the footer and the scale bar move with them.
* `keep_clear` [{page, x_mm, y_mm, w_mm, h_mm}]: boxes on one page (0-based,
  mm from the page's top-left, y down -- placements' frame) that no sticker
  (nor its caption) may land in; spaced mode keeps the gap from them too. A
  page whose clear room cannot take a sticker sends it to the next page.

ACCEPTANCE: written before the build (2026-11-13) and not edited by it."""
from __future__ import annotations

import random
import re

import pytest

from aruco_studio import web_api as W
from aruco_studio.core import sheet as SH

from test_web_layout import squares

DATE = "2026-11-13"
PAGE_W, PAGE_H = 215.9, 279.4                 # the Letter vinyl preset (10 mm margins)
EPS = 1e-3


def run(items, **kw):
    return W.sheet({"items": items, "cut_lines": True, **kw}, DATE)


def boxes(got, page=None):
    """Each placed sticker as (page, x0, y0, x1, y1), page 0-based."""
    return [(p["page"], p["x_mm"], p["y_mm"], p["x_mm"] + p["w_mm"], p["y_mm"] + p["h_mm"])
            for p in got["placements"] if page is None or p["page"] == page]


def apart(a, b):
    """How far apart two boxes (x0, y0, x1, y1) are: < 0 when they overlap."""
    return max(b[0] - a[2], a[0] - b[2], b[1] - a[3], a[1] - b[3])


def clear_box(k):
    return (k["x_mm"], k["y_mm"], k["x_mm"] + k["w_mm"], k["y_mm"] + k["h_mm"])


def text_at(svg, words):
    """(x, y) of the <text> that reads `words`."""
    m = re.search(r'<text x="([-\d.]+)" y="([-\d.]+)"[^>]*>' + re.escape(words) + "</text>", svg)
    assert m, f"no text {words!r}"
    return float(m.group(1)), float(m.group(2))


# ------------------------------------------------------------------ margins

def test_no_margins_and_no_keep_clear_are_todays_answer():
    its = squares(10, label=True)
    today = run(its)
    assert run(its, margins_mm={}) == today
    assert run(its, keep_clear=[]) == today
    # every side given as the preset's own 10 mm is the same answer too
    assert run(its, margins_mm={"top": 10, "right": 10, "bottom": 10, "left": 10}) == today


@pytest.mark.parametrize("mode", ["spaced", "tight"])
def test_each_margin_moves_its_own_edge(mode):
    margins = {"top": 50.0, "left": 70.0, "right": 15.0, "bottom": 30.0}
    got = run(squares(8), mode=mode, margins_mm=margins)
    bs = boxes(got)
    assert len(bs) == 8 and not [w for w in got["warnings"] if w["level"] == "error"]
    # it starts printing at the top-left margins' corner ...
    assert min(b[1] for b in bs) == pytest.approx(70.0, abs=EPS)
    assert min(b[2] for b in bs) == pytest.approx(50.0, abs=EPS)
    # ... and stays inside the right and bottom ones
    assert max(b[3] for b in bs) <= PAGE_W - 15.0 + EPS
    assert max(b[4] for b in bs) <= PAGE_H - 30.0 + EPS


def test_a_side_left_out_keeps_the_presets_margin():
    got = run(squares(4), margins_mm={"left": 40})
    bs = boxes(got)
    assert min(b[1] for b in bs) == pytest.approx(40.0, abs=EPS)
    assert min(b[2] for b in bs) == pytest.approx(10.0, abs=EPS)   # top: the preset's 10 mm


def test_the_footer_and_the_scale_bar_move_with_the_margins():
    base = run(squares(2))["svg"][0]
    moved = run(squares(2), margins_mm={"left": 30, "right": 25, "bottom": 40})["svg"][0]
    title = "ArUco Studio · spaced · " + DATE
    bx, by = text_at(base, title)
    mx, my = text_at(moved, title)
    assert (bx, mx) == (pytest.approx(10.0), pytest.approx(30.0))
    assert my == pytest.approx(by - 30.0, abs=EPS)                  # bottom 10 -> 40 mm
    px, _py = text_at(moved, "page 1/1")
    assert px == pytest.approx(PAGE_W - 25.0, abs=EPS)
    # the scale bar's 100 mm rule starts at the left margin, 30 mm higher
    bar = re.compile(r"M([-\d.]+) ([-\d.]+)h100v1\.2h-100z")
    (bx0, by0), (mx0, my0) = (tuple(map(float, bar.search(s).groups())) for s in (base, moved))
    assert (bx0, mx0) == (pytest.approx(10.0), pytest.approx(30.0))
    assert my0 == pytest.approx(by0 - 30.0, abs=EPS)


def test_a_bigger_margin_can_push_stickers_onto_another_page():
    # 4 x 5 = 20 tiles of 41.5 mm fill a Letter page under the bar's band
    # (test_web_scalebar.tiles); a 60 mm top margin takes a row of them away
    # (FIXED 2026-11-13 after the build: the first version asked 24 on one
    # page, which today's layout never fitted -- the ruler's error, not the build's)
    its = squares(20, side=41.5)
    assert run(its, mode="tight")["pages"] == 1
    got = run(its, mode="tight", margins_mm={"top": 60})
    assert got["pages"] == 2 and len(boxes(got)) == 20
    assert len(boxes(got, 0)) < 20


@pytest.mark.parametrize("bad", [{"top": -1}, {"left": "a"}, {"bottom": None, "right": -0.5}])
def test_a_bad_margin_is_answered_in_words(bad):
    import json
    out = json.loads(W.call("sheet", json.dumps({"items": squares(1), "cut_lines": True,
                                                    "margins_mm": bad})))
    assert "error" in out and "margin" in out["error"]


def test_margins_that_leave_no_room_are_an_error():
    import json
    out = json.loads(W.call("sheet", json.dumps({"items": squares(1), "cut_lines": True,
                                                    "margins_mm": {"left": 120, "right": 120}})))
    assert "error" in out


# ------------------------------------------------------------------ keep clear

@pytest.mark.parametrize("mode", ["spaced", "tight"])
def test_no_sticker_lands_in_a_keep_clear_box(mode):
    keep = {"page": 0, "x_mm": 10.0, "y_mm": 10.0, "w_mm": 95.0, "h_mm": 130.0}
    got = run(squares(12), mode=mode, keep_clear=[keep])
    bs = boxes(got)
    assert len(bs) == 12
    gap = 0.0 if mode == "tight" else SH.SheetSettings().gap_mm
    for b in boxes(got, 0):
        assert apart(b[1:], clear_box(keep)) >= gap - EPS, b
    # and the clear room was used: page 1 still holds stickers
    assert boxes(got, 0)


def test_a_keep_clear_box_is_on_its_own_page_only():
    its = squares(30, side=41.5)
    plain = run(its, mode="tight")
    assert plain["pages"] >= 2
    keep = {"page": 1, "x_mm": 10.0, "y_mm": 10.0, "w_mm": 90.0, "h_mm": 90.0}
    got = run(its, mode="tight", keep_clear=[keep])
    for b in boxes(got, 1):
        assert apart(b[1:], clear_box(keep)) >= -EPS
    # page 0 still uses that corner
    assert any(apart(b[1:], clear_box(keep)) < 0 for b in boxes(got, 0))


def test_a_page_kept_clear_all_over_sends_every_sticker_to_the_next():
    keep = {"page": 0, "x_mm": 0.0, "y_mm": 0.0, "w_mm": PAGE_W, "h_mm": PAGE_H}
    got = run(squares(5), keep_clear=[keep])
    assert got["pages"] == 2
    assert boxes(got, 0) == [] and len(boxes(got, 1)) == 5
    assert not [w for w in got["warnings"] if w["level"] == "error" and "not printed" in w["text"]]


def test_reprinting_on_a_sheet_already_cut():
    """Print 6, cut them out; put the sheet back, keep their area clear, print 6 more:
    none of the new stickers is where an old one was."""
    first = run(squares(6, side=50.0))
    assert first["pages"] == 1
    cut = [{"page": 0, "x_mm": x0, "y_mm": y0, "w_mm": x1 - x0, "h_mm": y1 - y0}
           for _p, x0, y0, x1, y1 in boxes(first)]
    again = run(squares(6, side=50.0), keep_clear=cut)
    assert len(boxes(again)) == 6
    for b in boxes(again, 0):
        for k in cut:
            assert apart(b[1:], clear_box(k)) >= SH.SheetSettings().gap_mm - EPS


def test_keep_clear_over_the_footer_says_it_still_prints_there():
    keep = {"page": 0, "x_mm": 0.0, "y_mm": PAGE_H - 30.0, "w_mm": PAGE_W, "h_mm": 30.0}
    got = run(squares(3), keep_clear=[keep])
    assert any(w["level"] in ("info", "warn") and "keep" in w["text"].lower()
               for w in got["warnings"])


@pytest.mark.parametrize("bad", [
    [{"page": 0, "x_mm": 0, "y_mm": 0, "w_mm": -5, "h_mm": 10}],
    [{"page": -1, "x_mm": 0, "y_mm": 0, "w_mm": 5, "h_mm": 10}],
    [{"page": 0, "x_mm": "a", "y_mm": 0, "w_mm": 5, "h_mm": 10}],
    [{"x_mm": 0, "y_mm": 0, "w_mm": 5, "h_mm": 10}],
    {"page": 0},
])
def test_a_bad_keep_clear_box_is_answered_in_words(bad):
    import json
    out = json.loads(W.call("sheet", json.dumps({"items": squares(1), "cut_lines": True,
                                                    "keep_clear": bad})))
    assert "error" in out and "keep_clear" in out["error"]


@pytest.mark.parametrize("seed", range(40))
def test_property_random_keep_clear_boxes_are_never_printed_on(seed):
    rng = random.Random(seed)
    n = rng.randint(1, 18)
    its = [squares(1, side=rng.choice([20.0, 30.0, 41.5, 60.0]))[0] for _ in range(n)]
    for k, it in enumerate(its):
        it["marker"]["first_id"] = k
    keep = []
    for page in range(2):
        for _ in range(rng.randint(0, 3)):
            w, h = rng.uniform(10, 120), rng.uniform(10, 160)
            keep.append({"page": page, "x_mm": rng.uniform(0, PAGE_W - w),
                         "y_mm": rng.uniform(0, PAGE_H - h), "w_mm": w, "h_mm": h})
    margins = rng.choice([{}, {"top": rng.uniform(5, 40), "left": rng.uniform(5, 40)}])
    mode = rng.choice(["spaced", "tight"])
    got = run(its, mode=mode, keep_clear=keep, margins_mm=margins)
    gap = 0.0 if mode == "tight" else SH.SheetSettings().gap_mm
    assert len(boxes(got)) == n, (seed, got["warnings"])
    left, top = margins.get("left", 10.0), margins.get("top", 10.0)
    for p, *b in boxes(got):
        assert b[0] >= left - EPS and b[1] >= top - EPS, (seed, b)
        for k in keep:
            if k["page"] == p:
                assert apart(b, clear_box(k)) >= gap - EPS, (seed, p, b, k)
    # stickers never overlap one another either
    bs = boxes(got)
    for i, a in enumerate(bs):
        for c in bs[i + 1:]:
            if a[0] == c[0]:
                assert apart(a[1:], c[1:]) >= gap - EPS, (seed, a, c)
