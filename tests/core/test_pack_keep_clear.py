"""Keep-clear rectangles in core.pack (Zach, 2026-11-13: "draw an avoid box
and then you recalculate it ... helpful as I try to reprint on the same page
I have already cut"): a bin's free room starts cut round them, the layout
stays guillotine-cuttable, nothing lands in them, and with none every answer
is today's.

The cuttability checker below is the oracle: plain geometry, sharing nothing
with core.pack."""
from __future__ import annotations

import random
import time

import pytest

from aruco_studio.core import pack as PK

TOL = 1e-6
W, H = 195.9, 230.4                    # Letter inside 10 mm margins, the footer and the bar


def boxes_of(rng, n, sizes=(20.0, 25.0, 30.0, 41.5, 35.0)):
    return [PK.Box(i, rng.choice(sizes), rng.choice(sizes)) for i in range(n)]


def rect(p, gap=0.0):
    return (p.x, p.y, p.x + p.w + gap, p.y + p.h + gap)


def apart(a, b):
    """How far apart two rects are (negative: they overlap)."""
    return max(b[0] - a[2], a[0] - b[2], b[1] - a[3], a[1] - b[3])


def cuttable(rects):
    """Can straight edge-to-edge cuts free every rect? (A cut may run
    through kept-clear room: it is scrap, or already cut away.)"""
    if len(rects) <= 1:
        return True
    for lo, hi in ((0, 2), (1, 3)):
        for r in rects:
            c = r[hi]
            if any(q[lo] + TOL < c < q[hi] - TOL for q in rects):
                continue
            a = [q for q in rects if q[hi] <= c + TOL]
            b = [q for q in rects if q[lo] >= c - TOL]
            if a and b and len(a) + len(b) == len(rects):
                return cuttable(a) and cuttable(b)
    return False


# ------------------------------------------------------------------ carve

@pytest.mark.parametrize("axis", PK.CARVES)
def test_carve_cuts_round_an_obstacle_in_four(axis):
    free = PK._carve([(0.0, 0.0, 100.0, 100.0)], [(20.0, 30.0, 50.0, 60.0)], axis)
    assert len(free) == 4
    assert sum(w * h for _x, _y, w, h in free) == pytest.approx(100 * 100 - 30 * 30)
    hole = (20.0, 30.0, 50.0, 60.0)
    for x, y, w, h in free:
        assert apart((x, y, x + w, y + h), hole) >= -TOL
    if axis == "rows":                             # the bands above and below span the width
        assert (0.0, 0.0, 100.0, 30.0) in free and (0.0, 60.0, 100.0, 40.0) in free
    else:                                          # the bands left and right span the height
        assert (0.0, 0.0, 20.0, 100.0) in free and (50.0, 0.0, 50.0, 100.0) in free


def test_carve_drops_empty_pieces_and_leaves_what_it_misses():
    assert PK._carve([(0.0, 0.0, 10.0, 10.0)], [(20.0, 20.0, 30.0, 30.0)], "rows") == [
        (0.0, 0.0, 10.0, 10.0)]
    # in a corner: two pieces
    assert len(PK._carve([(0.0, 0.0, 10.0, 10.0)], [(0.0, 0.0, 4.0, 4.0)], "cols")) == 2
    assert PK._carve([(0.0, 0.0, 10.0, 10.0)], [(-1.0, -1.0, 11.0, 11.0)], "rows") == []


# ------------------------------------------------------------------ pack

def test_no_obstacle_is_todays_answer():
    rng = random.Random(7)
    bs = boxes_of(rng, 14)
    today = PK.pack(bs, W, H, gap=4.0)
    assert PK.pack(bs, W, H, gap=4.0, keep_clear=None) == today
    assert PK.pack(bs, W, H, gap=4.0, keep_clear={}) == today
    assert PK.pack(bs, W, H, gap=4.0, keep_clear={0: []}) == today
    # one wholly outside the bin is dropped
    assert PK.pack(bs, W, H, gap=4.0, keep_clear={0: [(400.0, 0.0, 500.0, 50.0)]}) == today
    assert "carve" not in today.how


def test_an_obstacle_runs_every_variant_per_carve_way():
    bs = boxes_of(random.Random(3), 6)
    got = PK.pack(bs, W, H, keep_clear={0: [(0.0, 0.0, 50.0, 50.0)]})
    assert got.how.endswith(("carve rows", "carve cols"))


def test_a_bin_kept_clear_all_over_is_left_empty():
    bs = [PK.Box(i, 30.0, 30.0) for i in range(5)]
    got = PK.pack(bs, W, H, gap=4.0, keep_clear={0: [(0.0, 0.0, W, H)]})
    assert got.bins == 2 and not got.rejected
    assert {p.bin for p in got.places} == {1}
    # bins 0 and 2 kept clear, 1 free: bin 0 empty, all on 1
    got = PK.pack(bs, W, H, keep_clear={0: [(0.0, 0.0, W, H)], 2: [(0.0, 0.0, 10.0, 10.0)]})
    assert got.bins == 2 and {p.bin for p in got.places} == {1}


def test_fill_leaves_the_kept_clear_area_out():
    bs = [PK.Box(0, 50.0, 50.0)]
    plain = PK.pack(bs, 100.0, 100.0)
    kept = PK.pack(bs, 100.0, 100.0, keep_clear={0: [(60.0, 0.0, 100.0, 50.0),
                                                     (60.0, 25.0, 100.0, 50.0)]})
    assert plain.fill == pytest.approx(0.25)
    assert kept.fill == pytest.approx(2500.0 / (10000.0 - 40.0 * 50.0))   # overlap once


@pytest.mark.parametrize("seed", range(60))
def test_property_obstacles_are_never_covered_and_the_layout_still_cuts(seed):
    rng = random.Random(seed)
    gap = rng.choice([0.0, 0.0, 4.0])
    bs = boxes_of(rng, rng.randint(1, 30))
    keep = {}
    for b in range(rng.randint(1, 3)):
        for _ in range(rng.randint(0, 3)):
            w, h = rng.uniform(5, 120), rng.uniform(5, 160)
            x, y = rng.uniform(-10, W - w + 10), rng.uniform(-10, H - h + 10)
            keep.setdefault(b, []).append((x, y, x + w, y + h))
    first_h = rng.choice([None, H - 22.0])
    got = PK.pack(bs, W, H, gap=gap, keep_clear=keep, first_h=first_h)
    assert not got.rejected and len(got.places) == len(bs)
    assert got.bins == 1 + max(p.bin for p in got.places)
    for p in got.places:
        hb = first_h if (first_h is not None and p.bin == 0) else H
        assert p.x >= -TOL and p.y >= -TOL and p.x + p.w <= W + TOL and p.y + p.h <= hb + TOL
        for k in keep.get(p.bin, []):
            assert apart(rect(p), k) >= gap - TOL, (seed, p, k)
    for b in range(got.bins):
        mine = [p for p in got.places if p.bin == b]
        for i, p in enumerate(mine):
            for q in mine[i + 1:]:
                assert apart(rect(p), rect(q)) >= gap - TOL
        assert cuttable([rect(p, gap) for p in mine]), (seed, b)     # grown, as pack sees them


def test_timing_with_three_obstacles_stays_under_three_times(capsys):
    rng = random.Random(1)
    bs = boxes_of(rng, 30)
    keep = {0: [(10.0, 10.0, 60.0, 80.0), (120.0, 100.0, 180.0, 150.0)],
            1: [(0.0, 0.0, 90.0, 90.0)]}

    def best(**kw):
        t = []
        for _ in range(3):
            a = time.perf_counter()
            PK.pack(bs, W, H, gap=4.0, **kw)
            t.append(time.perf_counter() - a)
        return min(t)

    plain, kept = best(), best(keep_clear=keep)
    with capsys.disabled():
        print("\npack, 30 stickers: %.3f s plain, %.3f s with 3 keep-clear boxes (%.2fx)"
              % (plain, kept, kept / plain))
    assert kept < 3.0 * plain


def test_the_checker_catches_a_pinwheel():
    wheel = [(0, 0, 60, 40), (60, 0, 100, 60), (40, 60, 100, 100), (0, 40, 40, 100),
             (40, 40, 60, 60)]
    assert not cuttable(wheel)
    assert cuttable([(0, 0, 50, 50), (50, 0, 100, 50), (0, 50, 100, 100)])
