"""Auto layout in the online Studio's facade (web_api.sheet, contract.ts
SheetRequest.mode / gap_mm, Sheet.cuts / fill): core.pack's guillotine
packer behind core.sheet (Zach, 2026-10-18). The placements are read back
from the page SVG's data-sticker boxes."""
from __future__ import annotations

import re

import pytest

from aruco_studio import web_api as W
from aruco_studio.core import sheet as SH

from test_web_api import req

LETTER_AREA = (10.0, 10.0, 215.9 - 10.0, 279.4 - 10.0 - SH.FOOTER_H_MM - SH.RULER_H_MM
               - SH.BAND_GAP_MM)              # the Letter vinyl preset: 10 mm margins
_BOX = re.compile(r'<rect data-sticker="([^"]*)"[^>]* data-page="(\d+)" data-x="([-\d.]+)" '
                  r'data-y="([-\d.]+)" data-w="([-\d.]+)" data-h="([-\d.]+)" '
                  r'data-rotation="(\d+)"')


def placed(got):
    out = []
    for svg in got["svg"]:
        for key, page, x, y, w, h, rot in _BOX.findall(svg):
            x, y, w, h = float(x), float(y), float(w), float(h)
            out.append({"key": key, "page": int(page), "box": (x, y, x + w, y + h),
                        "rotation": int(rot)})
    return out


def apart(a, b):
    return max(b[0] - a[2], a[0] - b[2], b[1] - a[3], a[1] - b[3])


def min_apart(ps):
    return min(apart(a["box"], b["box"]) for i, a in enumerate(ps) for b in ps[i + 1:]
               if a["page"] == b["page"])


def inside(ps, area=LETTER_AREA):
    x0, y0, x1, y1 = area
    return all(p["box"][0] >= x0 - 1e-3 and p["box"][1] >= y0 - 1e-3 and
               p["box"][2] <= x1 + 1e-3 and p["box"][3] <= y1 + 1e-3 for p in ps)


def squares(n, side=40.0, label=False):
    return [req({"first_id": i}, rect={"w": side, "h": side},
                label={"on": label, "text": "part {id}"}) for i in range(n)]


def test_sheet_says_cuts_and_fill_and_defaults_to_spaced():
    its = squares(6, label=True)
    got = W.sheet({"items": its, "cut_lines": True}, "2026-10-18")
    ps = placed(got)
    assert got["pages"] == 1 and len(ps) == 6 and inside(ps)
    assert ">part 3</text>" in got["svg"][0]                    # spaced keeps the captions
    assert min_apart(ps) >= SH.SheetSettings().gap_mm - 1e-3     # the core's gap
    assert isinstance(got["cuts"], int) and got["cuts"] > 0
    x0, y0, x1, y1 = LETTER_AREA
    area = sum((p["box"][2] - p["box"][0]) * (p["box"][3] - p["box"][1]) for p in ps)
    assert got["fill"] == pytest.approx(area / ((x1 - x0) * (y1 - y0)), abs=1e-4)
    assert 0.0 < got["fill"] <= 1.0
    same = W.sheet({"items": its, "cut_lines": True, "mode": "spaced", "gap_mm": 4.0},
                   "2026-10-18")
    assert same == got


def test_twelve_40_mm_stickers_tight_on_letter_are_one_page_cut_as_a_grid():
    got = W.sheet({"items": squares(12, label=True), "cut_lines": True, "mode": "tight"},
                  "2026-10-18")
    ps = placed(got)
    assert got["pages"] == 1 and len(ps) == 12 and inside(ps)
    # The label is part of the sticker now (Zach, 2026-10-18: "the label should
    # go inside of the marker rectangle"): printed in tight mode too, inside it
    m = re.search(r'<text[^>]* x="([\d.]+)" y="([\d.]+)"[^>]*>part 3</text>', got["svg"][0])
    assert m, "part 3's label is on the page"
    tx, ty = float(m.group(1)), float(m.group(2))
    assert any(p["box"][0] < tx < p["box"][2] and p["box"][1] < ty < p["box"][3] for p in ps)
    xs = sorted({round(p["box"][0], 3) for p in ps})
    ys = sorted({round(p["box"][1], 3) for p in ps})
    assert len(xs) * len(ys) == 12                              # a full grid
    assert min_apart(ps) == pytest.approx(0.0, abs=1e-3)        # edge to edge: shared cuts
    assert got["cuts"] == (len(xs) + 1) + (len(ys) + 1)
    assert not [w for w in got["warnings"] if w["level"] == "error"]


def test_gap_mm_spaces_the_stickers_and_tight_ignores_it():
    its = squares(10, side=30.0)
    wide = placed(W.sheet({"items": its, "cut_lines": True, "mode": "spaced", "gap_mm": 10.0},
                          "2026-10-18"))
    assert min_apart(wide) >= 10.0 - 1e-3 and inside(wide)
    t1 = W.sheet({"items": its, "cut_lines": True, "mode": "tight", "gap_mm": 10.0}, "2026-10-18")
    t2 = W.sheet({"items": its, "cut_lines": True, "mode": "tight"}, "2026-10-18")
    assert t1 == t2 and min_apart(placed(t1)) == pytest.approx(0.0, abs=1e-3)


def test_a_sticker_longer_than_the_page_is_wide_turns():
    long = req({"type": "grid", "cols": 8, "rows": 1}, rect={"w": 220.0, "h": 30.0})
    got = W.sheet({"items": [long] + squares(4), "cut_lines": True, "mode": "tight"},
                  "2026-10-18")
    ps = placed(got)
    turned = [p for p in ps if p["key"] == "m1"]
    assert turned and turned[0]["rotation"] == 90 and inside(ps)
    assert not [w for w in got["warnings"] if w["level"] == "error"]


def test_rectangular_stickers_carry_no_bounding_box_note():
    got = W.sheet({"items": squares(3), "cut_lines": True}, "2026-10-18")
    assert not [w for w in got["warnings"] if "bounding box" in w["text"]]


MIXED = [(40, 40), (40, 40), (30, 30), (30, 30), (50, 25), (25, 50), (90, 35), (35, 90), (70, 22),
         (22, 70)]


@pytest.mark.parametrize("mode", ["tight", "spaced"])
def test_objective_fewest_cuts_never_cuts_more_and_never_takes_fewer_pages(mode):
    # contract.ts SheetRequest.objective (Zach, 2026-10-18: "fewest cut lines"
    # or "most compact (fewest number of sheets)"), default "fewest_sheets"
    its = [req({"first_id": i}, rect={"w": w, "h": h}) for i, (w, h) in enumerate(MIXED)]
    its += squares(6, side=30.0)
    base = {"items": its, "cut_lines": True, "mode": mode}
    default = W.sheet(base, "2026-10-18")
    assert W.sheet({**base, "objective": "fewest_sheets"}, "2026-10-18") == default
    cuts = W.sheet({**base, "objective": "fewest_cuts"}, "2026-10-18")
    assert cuts["cuts"] <= default["cuts"] and cuts["pages"] >= default["pages"]
    if mode == "spaced":            # a page more saves cuts here; tight: the same layout
        assert cuts["cuts"] < default["cuts"] and cuts["pages"] > default["pages"]
    ps = placed(cuts)
    assert len(ps) == len(its) and inside(ps)
    gap = 0.0 if mode == "tight" else SH.SheetSettings().gap_mm
    assert min_apart(ps) >= gap - 1e-3
    assert not [w for w in cuts["warnings"] if w["level"] == "error"]


def test_an_unknown_objective_is_an_error():
    with pytest.raises(ValueError, match="objective"):
        W.sheet({"items": squares(2), "cut_lines": True, "objective": "cheapest"}, "2026-10-18")
