"""Auto layout (Zach, 2026-10-18): core.pack's guillotine packer, and the
sticker sheet with SheetSettings.packer = "guillotine" (core.sheet), tight
and spaced, measured against the shelves on 200 seeded random sets.

The validity checker below is the oracle: plain geometry on the placed
stickers, written here and sharing nothing with core.pack."""
from __future__ import annotations

import dataclasses
import math
import random
import statistics

import pytest

from aruco_studio.core import pack as PK
from aruco_studio.core import sheet as SH

PAGES_MM = {"letter": (215.9, 279.4), "a4": (210.0, 297.0)}
MARGIN = 10.0
TOL = 1e-6


def item(key, w, h, holes=()):
    a, b = w / 2.0, h / 2.0
    return SH.PrintItem(key=key, dictionary="DICT_4X4_50", marker_id=0, marker_length_m=0.02,
                        cut_mm={"outer": [[-a, -b], [a, -b], [a, b], [-a, b]],
                                "holes": [list(hh) for hh in holes]},
                        ink_mm=[], ids=[0], name=key, made_by="sticker")


def lay(items, mode, page="letter", packer="guillotine", **kw):
    return SH.layout_stickers(items, SH.SheetSettings(page=page, mode=mode, packer=packer, **kw))


# ------------------------------------------------------------ the oracle

def printable(page):
    """The sticker area of a page, from the sheet's spec (margins, then the
    footer, the scale bars and the gaps above them at the bottom)."""
    w, h = PAGES_MM[page]
    bottom = h - MARGIN - SH.FOOTER_H_MM - SH.RULER_H_MM - SH.BAND_GAP_MM
    return MARGIN, MARGIN, w - MARGIN, bottom


def caption_box(p):
    """The caption under a placed sticker (x0, y0, x1, y1), or None."""
    if not p.caption_lines:
        return None
    wd = max(SH.text_width_mm(t, p.caption_pt) for t in p.caption_lines)
    hh = p.caption_gap_mm + len(p.caption_lines) * p.caption_pt * SH.LABEL_LEADING / SH.MM_TO_PT
    cx = p.x_mm + p.w_mm / 2.0
    return cx - wd / 2.0, p.y_mm + p.h_mm, cx + wd / 2.0, p.y_mm + p.h_mm + hh


def apart(a, b):
    """How far apart two boxes are (negative: they overlap)."""
    return max(b[0] - a[2], a[0] - b[2], b[1] - a[3], a[1] - b[3])


def problems(L, items, page, gap):
    """Everything wrong with a sticker layout: overlaps (spaced: closer than
    gap), outside the printable area, scaled, placed twice or never."""
    bad = []
    x0, y0, x1, y1 = printable(page)
    keys = [p.item.key for p in L.placed] + [r.item.key for r in L.rejected]
    for it in items:
        if keys.count(it.key) != 1:
            bad.append(f"{it.key} placed / rejected {keys.count(it.key)} times")
    bad += [f"{r.item.key} rejected without a reason" for r in L.rejected if not r.reason]
    by_page = {}
    for p in L.placed:
        o = p.item.cut_mm["outer"]
        bw = max(q[0] for q in o) - min(q[0] for q in o)
        bh = max(q[1] for q in o) - min(q[1] for q in o)
        want = (bh, bw) if p.rotation == 90 else (bw, bh)
        if p.rotation not in (0, 90) or abs(p.w_mm - want[0]) > TOL or abs(p.h_mm - want[1]) > TOL:
            bad.append(f"{p.item.key}: {p.w_mm} x {p.h_mm} turned {p.rotation} is not its {bw} x {bh}")
        st = (p.x_mm, p.y_mm, p.x_mm + p.w_mm, p.y_mm + p.h_mm)
        cap = caption_box(p)
        cell = st if cap is None else (min(st[0], cap[0]), st[1], max(st[2], cap[2]), cap[3])
        if cell[0] < x0 - TOL or cell[1] < y0 - TOL or cell[2] > x1 + TOL or cell[3] > y1 + TOL:
            bad.append(f"{p.item.key}: {cell} is outside the printable area {(x0, y0, x1, y1)}")
        by_page.setdefault(p.page, []).append((p.item.key, st, cell))
    for pg in by_page.values():
        for i, (ka, sa, ca) in enumerate(pg):
            for kb, sb, cb in pg[i + 1:]:
                if apart(sa, sb) < gap - TOL:
                    bad.append(f"{ka} and {kb} are {apart(sa, sb):.3f} mm apart (gap {gap})")
                elif apart(ca, cb) < gap - TOL:
                    bad.append(f"{ka} and {kb}: captions {apart(ca, cb):.3f} mm apart (gap {gap})")
    return bad


def random_set(seed):
    rng = random.Random(seed)
    n = rng.randint(1, 40)
    page = rng.choice(["letter", "a4"])
    its = [item(f"s{seed}-{i}", round(rng.uniform(10, 120), 1), round(rng.uniform(10, 120), 1))
           for i in range(n)]
    return page, its


def page_cuts(L):
    """One ruler for both packers: core.pack.count_cuts on every page."""
    return sum(PK.count_cuts([(p.x_mm, p.y_mm, p.x_mm + p.w_mm, p.y_mm + p.h_mm) for p in pg],
                             (0.0, 0.0) + tuple(L.page_mm)) for pg in L.pages)


GAP = SH.SheetSettings().gap_mm


# ------------------------------------------------------------ count_cuts

def test_count_cuts_counts_a_shared_line_once():
    page = (-10.0, -10.0, 300.0, 300.0)
    assert PK.count_cuts([(30 * i, 0, 30 * i + 30, 30) for i in range(4)], page) == 7
    grid = [(40 * c, 40 * r, 40 * c + 40, 40 * r + 40) for c in range(4) for r in range(3)]
    assert PK.count_cuts(grid, page) == (4 + 1) + (3 + 1)
    spaced = [(44 * c, 44 * r, 44 * c + 40, 44 * r + 40) for c in range(4) for r in range(3)]
    assert PK.count_cuts(spaced, page) == 2 * 4 + 2 * 3
    assert PK.count_cuts([(0, 0, 10, 10)], (0, 0, 100, 100)) == 2      # two sides on the edge
    assert PK.count_cuts([], page) == 0


# ------------------------------------------------------------ pack()

def test_pack_keeps_the_gap_and_the_bin():
    got = PK.pack([PK.Box(i, 30, 20) for i in range(9)], 100, 70, gap=5)
    assert got.bins == 1 and not got.rejected and len(got.places) == 9
    for i, a in enumerate(got.places):
        assert a.x >= -TOL and a.y >= -TOL and a.x + a.w <= 100 + TOL and a.y + a.h <= 70 + TOL
        for b in got.places[i + 1:]:
            assert apart((a.x, a.y, a.x + a.w, a.y + a.h), (b.x, b.y, b.x + b.w, b.y + b.h)) >= 5 - TOL


def test_pack_rejects_what_no_bin_holds_and_respects_turn():
    got = PK.pack([PK.Box("long", 120, 30), PK.Box("stiff", 120, 30, turn=False),
                   PK.Box("huge", 200, 200)], 100, 150)
    assert [p.key for p in got.places] == ["long"] and got.places[0].turned
    assert dict(got.rejected).keys() == {"stiff", "huge"}
    assert "either way round" in dict(got.rejected)["huge"]
    # a turned size of its own (a caption stays under the sticker)
    got = PK.pack([PK.Box("c", 120, 40, turned=(45, 125))], 100, 150)
    assert got.places[0][4:] == (45, 125, True)


def test_pack_is_deterministic_and_fills_bins():
    boxes = [PK.Box(i, 10 + (7 * i) % 50, 12 + (11 * i) % 40) for i in range(30)]
    a, b = PK.pack(boxes, 190, 230, gap=2), PK.pack(boxes, 190, 230, gap=2)
    assert a == b
    area = sum(p.w * p.h for p in a.places)
    assert a.fill == pytest.approx(area / (a.bins * 190 * 230))


# ------------------------------------------------------------ the sheet

def test_the_default_packer_is_still_the_shelves():
    its = [item(f"t{i}", 30, 30) for i in range(4)]
    L = SH.layout_stickers(its, SH.SheetSettings(mode="tight"))
    assert L.settings.packer == "shelf" and len(L.shelves) == 1 and L.cuts() == 7
    assert "packer" not in SH.sticker_summary(L)
    assert SH.sticker_summary(lay(its, "tight"))["packer"] == "guillotine"


def test_twelve_40_mm_stickers_tight_make_one_page_cut_as_a_grid():
    its = [item(f"q{i}", 40, 40) for i in range(12)]
    L = lay(its, "tight")
    assert L.page_count == 1 and not L.rejected and not problems(L, its, "letter", 0.0)
    xs = sorted({round(p.x_mm, 6) for p in L.placed})
    ys = sorted({round(p.y_mm, 6) for p in L.placed})
    assert len(xs) * len(ys) == 12                       # a full grid, edge to edge
    assert [round(b - a, 6) for a, b in zip(xs, xs[1:])] == [40.0] * (len(xs) - 1)
    assert [round(b - a, 6) for a, b in zip(ys, ys[1:])] == [40.0] * (len(ys) - 1)
    assert L.cuts() == (len(xs) + 1) + (len(ys) + 1)
    shelf = lay([item(f"q{i}", 40, 40) for i in range(12)], "tight", packer="shelf")
    assert L.cuts() < shelf.cuts()                       # 9 against the shelves' 19


MIXED = ([(40, 40)] * 4 + [(30, 30)] * 4 + [(50, 25)] * 3 + [(25, 50)] * 3
         + [(90, 35), (35, 90), (70, 22), (22, 70)])


@pytest.mark.parametrize("mode", ["tight", "spaced"])
def test_mixed_sizes_the_shelves_split_over_two_pages_fit_on_one(mode):
    its = [item(f"m{i}", w, h) for i, (w, h) in enumerate(MIXED)]
    shelf, new = lay(its, mode, packer="shelf"), lay(its, mode)
    assert shelf.page_count == 2 and new.page_count == 1
    assert not problems(new, its, "letter", 0.0 if mode == "tight" else GAP)
    assert new.fill() == pytest.approx(2 * shelf.fill())


def test_a_turned_sticker_carries_its_ink_and_outline():
    # a 1 x 8 grid board is longer than Letter is wide: it turns, ink and all
    board = SH.PrintItem(key="board", dictionary="DICT_4X4_50", marker_id=0,
                         marker_length_m=0.022, layout="grid", rows=1, cols=8,
                         separation_m=0.004)
    small = [item(f"s{i}", 30, 30) for i in range(5)]
    L = lay([board] + small, "spaced")
    p = next(q for q in L.placed if q.item.key == "board")
    assert p.rotation == 90 and p.h_mm > p.w_mm
    ink = [p.to_page(u, v) for poly in SH.ink_of(board) for lp in poly for u, v in lp]
    assert ink
    assert all(p.x_mm - TOL <= x <= p.x_mm + p.w_mm + TOL and
               p.y_mm - TOL <= y <= p.y_mm + p.h_mm + TOL for x, y in ink)
    cut = [p.to_page(u, v) for u, v in SH.outline_of(board)["outer"]]
    assert min(x for x, _ in cut) == pytest.approx(p.x_mm)
    assert max(y for _, y in cut) == pytest.approx(p.y_mm + p.h_mm)
    svg = SH.render_sticker_svg(L, date="2026-10-18")
    assert 'data-cut="board"' in svg


def test_an_odd_shape_is_packed_by_its_box():
    disc = [[25 * math.cos(k / 36 * 2 * math.pi), 25 * math.sin(k / 36 * 2 * math.pi)]
            for k in range(36)]
    odd = dataclasses.replace(item("disc", 50, 50), cut_mm={"outer": disc, "holes": []})
    L = lay([odd] + [item(f"s{i}", 50, 50) for i in range(3)], "tight")
    p = next(q for q in L.placed if q.item.key == "disc")
    assert (round(p.w_mm, 6), round(p.h_mm, 6)) == (50.0, 50.0)
    assert L.fill() < 4 * 50 * 50 / (L.printable_mm[2] * L.printable_mm[3])   # the disc's area


# ------------------------------------------------------------ the checker fails when it should

def _mutated(L, page_index, key, dx, dy):
    pages = [[dataclasses.replace(p, x_mm=p.x_mm + dx, y_mm=p.y_mm + dy)
              if p.item.key == key else p for p in pg] for pg in L.pages]
    return dataclasses.replace(L, pages=pages)


@pytest.mark.parametrize("mode", ["tight", "spaced"])
def test_the_checker_catches_a_sticker_pushed_1_mm_into_its_neighbour(mode):
    gap = 0.0 if mode == "tight" else GAP
    tried = 0
    for seed in range(30):
        page, its = random_set(seed)
        L = lay(its, mode, page)
        assert not problems(L, its, page, gap)
        for pi, pg in enumerate(L.pages):
            if len(pg) < 2:
                continue
            # neighbours: side by side (overlapping across), the closest pair
            near = []
            for i, a in enumerate(pg):
                for b in pg[i + 1:]:
                    ra = (a.x_mm, a.y_mm, a.x_mm + a.w_mm, a.y_mm + a.h_mm)
                    rb = (b.x_mm, b.y_mm, b.x_mm + b.w_mm, b.y_mm + b.h_mm)
                    d = [rb[0] - ra[2], ra[0] - rb[2], rb[1] - ra[3], ra[1] - rb[3]]
                    if sorted(d)[-2] < -TOL:
                        near.append((max(d) - gap, a, d.index(max(d))))
            if not near:
                continue
            _, a, k = min(near, key=lambda n: n[0])
            dx, dy = ((1, 0), (-1, 0), (0, 1), (0, -1))[k]
            assert problems(_mutated(L, pi, a.item.key, dx, dy), its, page, gap), (seed, mode)
            tried += 1
            break
    assert tried >= 20
    # and the rest of what it checks
    page, its = random_set(3)
    L = lay(its, mode, page)
    first = L.placed[0]
    assert problems(_mutated(L, 0, first.item.key, -(first.x_mm - MARGIN) - 1, 0), its, page, gap)
    gone = dataclasses.replace(L, pages=[[p for p in pg if p is not first] for pg in L.pages])
    assert problems(gone, its, page, gap)
    twice = dataclasses.replace(L, pages=[L.pages[0] + [first]] + L.pages[1:])
    assert problems(twice, its, page, gap)
    big = dataclasses.replace(L, pages=[[dataclasses.replace(first, w_mm=first.w_mm * 1.01)]
                                        + L.pages[0][1:]] + L.pages[1:])
    assert problems(big, its, page, gap)


# ------------------------------------------------------------ 200 random sets

def test_200_random_sets_are_valid_and_beat_the_shelves(capsys):
    rows = {m: {"shelf": [], "guillotine": []} for m in ("tight", "spaced")}
    for seed in range(200):
        page, its = random_set(seed)
        for mode in ("tight", "spaced"):
            gap = 0.0 if mode == "tight" else GAP
            shelf, new = lay(its, mode, page, packer="shelf"), lay(its, mode, page)
            assert not problems(new, its, page, gap), (seed, mode, problems(new, its, page, gap))
            assert new.cuts() == page_cuts(new)
            assert new.page_count <= shelf.page_count, (seed, mode)
            for name, L in (("shelf", shelf), ("guillotine", new)):
                rows[mode][name].append((L.page_count, page_cuts(L), L.fill(), L.cuts()))
    table = ["| mode | packer | pages (sum) | median cuts | mean fill | median cuts() |",
             "|---|---|---|---|---|---|"]
    for mode, by in rows.items():
        for name, r in by.items():
            table.append(f"| {mode} | {name} | {sum(x[0] for x in r)} | "
                         f"{statistics.median(x[1] for x in r):g} | "
                         f"{statistics.mean(x[2] for x in r):.4f} | "
                         f"{statistics.median(x[3] for x in r):g} |")
    with capsys.disabled():
        print("\n" + "\n".join(table))
    t = rows["tight"]
    assert statistics.median(x[1] for x in t["guillotine"]) <= statistics.median(
        x[1] for x in t["shelf"])
    for mode in rows:
        assert statistics.mean(x[2] for x in rows[mode]["guillotine"]) >= statistics.mean(
            x[2] for x in rows[mode]["shelf"])
