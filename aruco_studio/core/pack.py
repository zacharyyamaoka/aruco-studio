"""Auto layout: rectangles onto as few bins (pages, beds) as possible, every
layout cut free with straight edge-to-edge cuts. Standard library only (it
runs in the browser, Pyodide).

Zach, 2026-10-18: "tightly packs rectangular shapes to ensure the fewest
number of cuts and fit onto a4 paper ... doing it with spacing between them
is almost like running the same algorithm but just adding like manual
padding. The same layout algorithm can be used for 2d and even 3D printing".

### Prior art (ported, not invented)

* Jukka Jylänki, "A Thousand Ways to Pack the Bin -- A Practical Approach
  to Two-Dimensional Rectangle Bin Packing" (2010), section 3, GUILLOTINE:
  a list of free rectangles, starting with the empty bin; each box goes into
  the free rectangle a CHOICE rule picks (BSSF best short side fit, BLSF
  best long side fit, BAF best area fit; here also "tl", the top-left-most
  free rectangle, his Bottom-Left with y down), at its corner, and the rest of that
  rectangle is SPLIT in two by one straight line (SAS / LAS shorter / longer
  axis, SLAS / LLAS shorter / longer leftover axis, MINAS / MAXAS min / max
  area). Offline (boxes sorted first, -DESC), 90 degree turns, several bins
  first-fit. His conclusion: no single variant wins, so try several and keep
  the best -- which is what `pack` does.
* rectpack 0.2.2 (Python, Apache-2.0, github.com/secnot/rectpack),
  guillotine.py: the same rules, read for this port (the split geometry and
  the fitness keys are rectpack's). Its free-rectangle MERGE is left out:
  joining two free rectangles across a split line lets a later box straddle
  that line, and the layout stops being guillotine-cuttable.
* Gilmore & Gomory (1965), guillotine cutting stock: a cut runs from edge
  to edge of the piece it is made in, as a paper trimmer (or scissors along
  a straight line) does.

### Why guillotine

Every box sits at the corner of a free rectangle and the rest is split by a
straight line, so the free rectangles form a cutting tree: every layout this
module returns can be freed by straight edge-to-edge cuts. With gap 0
neighbours share a cut line (a sticker sheet's "tight" mode); a gap is the
same packing with every box and the bin grown by the gap (the box keeps its
corner, the gap is the right / lower strip): "spaced".

Two more split rules make shelves of it: "rows" always splits across (the
remainder under a box spans the free rectangle's width: a shelf), "cols"
always along. Sort orders x choice rules x split rules are tried and the
winner has the fewest bins, then the fewest cuts (`count_cuts`), then the
most area on the earliest bins, then the fewest turned boxes, then the most
compact boxes per bin; the
candidate's index breaks the last tie, so the result is deterministic.

That is objective "fewest_sheets" (the default). Zach, 2026-10-18: "there
are two things to optimize for btw: one is fewest cut lines, one is most
compact (fewest number of sheets)". Objective "fewest_cuts" ranks the cuts
first, then the bins (it may take more). Both also try the variants that
line cuts up (`_variants`): they sometimes fit a bin fewer as well.

### The API

    pack(boxes, bin_w, bin_h, gap=0.0, stock=None,
         objective="fewest_sheets") -> Packing

`Box(key, w, h, turn=True, turned=None, cut=None)`: `turned` is the box's
size turned 90 degrees when that is not (h, w) (a sticker's caption stays
under it, so its cell turns differently); `cut` what is cut out of the box,
as given and turned ("fewest_cuts" counts the cuts on it). Coordinates: the bin's min corner is (0, 0) and
a Place's (x, y) is the box's min corner (a page: top-left, y down; a bed:
front-left). `stock` is the piece the bin sits on, in the bin's frame (a
page inside its margins: (-margin, -margin, page_w - margin, ...)); its
edges need no cut. Default: the bin itself.

### A 3D bed (core.beds, unchanged)

beds.pack_rectangles is MaxRects (denser, not guillotine: a bed needs no
cuts) with a wipe-tower hole kept on every bed. `pack` fits the same call:
bin = BedSettings.usable(), gap = spacing_mm (the same grow-by-the-gap
trick beds uses), Box(index, w, d, turn=allow_rotate), Place.bin = the bed,
x + margin_mm / y + margin_mm its corner. The wipe tower would be a box
pinned to each bin before the parts, which `pack` does not do yet: so beds
keeps its own packer.

Not here: true nesting of odd outlines (no-fit polygons, as SVGnest and
Deepnest do). A caller packs an odd shape by its box.
"""
from __future__ import annotations

from typing import List, NamedTuple, Optional, Sequence, Tuple

_EPS = 1e-9
_TOL = 1e-6                         # cut lines: coordinates within this are the same line
ND = 6                              # keys are rounded to 1e-6 (deterministic everywhere)

CHOICES = ("bssf", "baf", "blsf", "tl")
SPLITS = ("rows", "slas", "llas", "sas", "las", "minas", "maxas", "cols")
ORDERS = (
    ("height", lambda w, h: (-h, -w)),
    ("area", lambda w, h: (-(w * h), -max(w, h))),
    ("long side", lambda w, h: (-max(w, h), -min(w, h))),
    ("short side", lambda w, h: (-min(w, h), -max(w, h))),
    ("width", lambda w, h: (-w, -h)),
    ("perimeter", lambda w, h: (-(w + h), -max(w, h))),
)


class Box(NamedTuple):
    key: object                     # the caller's id: returned on its Place
    w: float
    h: float
    turn: bool = True               # may it turn 90 degrees
    turned: Optional[Tuple[float, float]] = None   # its size turned; None = (h, w)
    # what is cut out of the box (x0, y0, x1, y1 in the box from its min
    # corner), as given and turned; None = the box. Objective "fewest_cuts"
    # counts these (a sticker in its caption's cell)
    cut: Optional[Tuple[Tuple[float, float, float, float],
                        Tuple[float, float, float, float]]] = None


class Place(NamedTuple):
    key: object
    bin: int                        # 0-based
    x: float                        # the box's min corner in the bin
    y: float
    w: float                        # the box as placed (after a turn)
    h: float
    turned: bool


class Packing(NamedTuple):
    places: List[Place]             # in the order the boxes were given
    rejected: List[Tuple[object, str]]
    bins: int
    cuts: int                       # count_cuts over every bin (stock edges free)
    fill: float                     # box area / (bins x bin area)
    how: str                        # the winning variant, e.g. "height, bssf, rows"


def _sizes(b: Box) -> List[Tuple[float, float, bool]]:
    """The ways a box can go: (w, h, turned)."""
    out = [(float(b.w), float(b.h), False)]
    if b.turn:
        tw, th = b.turned if b.turned is not None else (b.h, b.w)
        tw, th = float(tw), float(th)
        if abs(tw - out[0][0]) > _EPS or abs(th - out[0][1]) > _EPS:
            out.append((tw, th, True))
    return out


def _choose(free, sizes, rule):
    """(key, free index, w, h, turned) of the best spot, or None."""
    best = None
    for fi, (fx, fy, fw, fh) in enumerate(free):
        for w, h, turned in sizes:
            if w > fw + _EPS or h > fh + _EPS:
                continue
            lw, lh = fw - w, fh - h
            if rule == "bssf":
                k = (min(lw, lh), max(lw, lh))
            elif rule == "blsf":
                k = (max(lw, lh), min(lw, lh))
            elif rule == "baf":
                k = (fw * fh - w * h, min(lw, lh))
            else:                                   # "tl": the top-left-most spot
                k = (fy, fx)
            k = tuple(round(v, ND) for v in k) + (round(fy, ND), round(fx, ND), turned)
            if best is None or k < best[0]:
                best = (k, fi, w, h, turned)
    return best


def _split(f, w, h, rule):
    """The free rectangles left of `f` once a w x h box sits at its corner:
    one straight line splits the rest in two (Jylanki 3.2; rectpack's
    _split_horizontal / _split_vertical)."""
    fx, fy, fw, fh = f
    lw, lh = fw - w, fh - h
    if rule == "rows":
        across = True
    elif rule == "cols":
        across = False
    elif rule == "sas":
        across = fw < fh
    elif rule == "las":
        across = fw >= fh
    elif rule == "slas":
        across = lw < lh
    elif rule == "llas":
        across = lw >= lh
    elif rule == "maxas":
        across = w * lh <= h * lw
    else:                                           # "minas"
        across = w * lh >= h * lw
    if across:                                      # the line runs along the box's far side
        parts = [(fx, fy + h, fw, lh), (fx + w, fy, lw, h)]
    else:
        parts = [(fx, fy + h, w, lh), (fx + w, fy, lw, fh)]
    return [p for p in parts if p[2] > _EPS and p[3] > _EPS]


def guillotine(boxes: Sequence[Box], bin_w: float, bin_h: float, order: int = 0,
               choice: str = "bssf", split: str = "rows") -> List[Optional[Place]]:
    """One guillotine variant (ORDERS[order], a CHOICES rule, a SPLITS rule),
    bins first-fit. Boxes that fit no empty bin get None. Sizes are as given
    (pack grows them by the gap)."""
    keyf = ORDERS[order][1]
    seq = sorted(range(len(boxes)), key=lambda i: (tuple(round(v, ND) for v in
                                                         keyf(boxes[i].w, boxes[i].h)), i))
    return _run(boxes, bin_w, bin_h, seq, choice, split)


def _run(boxes, bin_w, bin_h, seq, choice, split):
    """guillotine() in the order `seq` (box indices)."""
    bins: List[list] = []
    out: List[Optional[Place]] = [None] * len(boxes)
    for i in seq:
        sizes = _sizes(boxes[i])
        spot = None
        for b, free in enumerate(bins):
            got = _choose(free, sizes, choice)
            if got is not None:
                spot = (b, got)
                break
        if spot is None:
            got = _choose([(0.0, 0.0, float(bin_w), float(bin_h))], sizes, choice)
            if got is None:
                continue
            bins.append([(0.0, 0.0, float(bin_w), float(bin_h))])
            spot = (len(bins) - 1, got)
        b, (_k, fi, w, h, turned) = spot
        f = bins[b].pop(fi)
        bins[b].extend(_split(f, w, h, split))
        out[i] = Place(boxes[i].key, b, f[0], f[1], w, h, turned)
    return out


# ------------------------------------------------------------------ cuts

def _segments(rects, region, axis, out):
    """The guillotine cuts that free every rect (x0, y0, x1, y1) from
    `region`, as segments (axis, at, lo, hi) appended to `out`: axis 0 a
    line y = at from x = lo to hi, axis 1 a line x = at. Along `axis` every
    rect edge that crosses no rect cuts the whole region; each piece is then
    cut along the other axis. Rects that interlock (no straight cut at all)
    each take their four sides."""
    if not rects:
        return
    for ax in (axis, 1 - axis):
        lo_i, hi_i = (1, 3) if ax == 0 else (0, 2)          # the coordinate a cut sits at
        a_i, b_i = (0, 2) if ax == 0 else (1, 3)            # the cut's extent
        # the rects' spans along the cut's normal, overlapping ones joined: a
        # cut can only sit at the ends of a joined span (anywhere else it
        # crosses a rect)
        order = sorted(rects, key=lambda r: (r[lo_i], r[hi_i]))
        groups = [[order[0]]]
        top = order[0][hi_i]
        for r in order[1:]:
            if r[lo_i] < top - _TOL:
                groups[-1].append(r)
                top = max(top, r[hi_i])
            else:
                groups.append([r])
                top = r[hi_i]
        ends = []
        for g in groups:
            ends += [g[0][lo_i], max(r[hi_i] for r in g)]
        cs = []
        for c in ends:
            if region[lo_i] + _TOL < c < region[hi_i] - _TOL and not (cs and c - cs[-1] <= _TOL):
                cs.append(c)
        if not cs:
            continue
        for c in cs:
            out.append((ax, c, region[a_i], region[b_i]))
        for g, (a, b) in zip(groups, zip(ends[::2], ends[1::2])):
            a = a if a > region[lo_i] + _TOL else region[lo_i]      # its piece: the cuts
            b = b if b < region[hi_i] - _TOL else region[hi_i]      # at its ends, or the edge
            piece = list(region)
            piece[lo_i], piece[hi_i] = a, b
            if len(g) == 1 and all(abs(p - q) <= _TOL for p, q in zip(g[0], piece)):
                continue                                    # the piece IS the rect
            _segments(g, tuple(piece), 1 - ax, out)
        return
    if len(rects) == 1:                                     # can only be on the region's edges
        return
    for x0, y0, x1, y1 in rects:
        out += [(0, y0, x0, x1), (0, y1, x0, x1), (1, x0, y0, y1), (1, x1, y0, y1)]


def _clear(rects, ax, at, a, b) -> bool:
    """Does the line (axis `ax` at `at`) from a to b cross no rect's inside?"""
    for r in rects:
        c0, c1 = (r[1], r[3]) if ax == 0 else (r[0], r[2])
        e0, e1 = (r[0], r[2]) if ax == 0 else (r[1], r[3])
        if c0 + _TOL < at < c1 - _TOL and e0 < b - _TOL and a < e1 - _TOL:
            return False
    return True


def cut_lines(rects, region, axis: int = 0) -> List[Tuple[int, float, float, float]]:
    """The straight cuts that free every rect from `region` (both x0, y0,
    x1, y1), merged: cuts on one line count once when the stretch between
    them crosses no rect (a shared edge, or stickers in line, is one stroke
    of the trimmer). -> [(axis, at, lo, hi)], sorted."""
    segs: list = []
    _segments([tuple(map(float, r)) for r in rects], tuple(map(float, region)), axis, segs)
    by: dict = {}
    for ax, at, lo, hi in segs:
        by.setdefault((ax, round(at / _TOL) * _TOL), []).append((min(lo, hi), max(lo, hi), at))
    out = []
    for (ax, _k), lst in sorted(by.items()):
        lst.sort()
        at = lst[0][2]
        cur = [lst[0][0], lst[0][1]]

        for lo, hi, _at in lst[1:]:
            if lo <= cur[1] + _TOL or _clear(rects, ax, at, cur[1], lo):
                cur[1] = max(cur[1], hi)
            else:
                out.append((ax, at, cur[0], cur[1]))
                cur = [lo, hi]
        out.append((ax, at, cur[0], cur[1]))
    return out


def count_cuts(rects, region) -> int:
    """The fewest straight cuts (cut_lines, either axis first) that free
    every rect from `region`. Four 30 mm stickers in a row, edge to edge:
    2 long + 5 short = 7; a grid of c x r: (c + 1) + (r + 1)."""
    if not rects:
        return 0
    return min(len(cut_lines(rects, region, 0)), len(cut_lines(rects, region, 1)))


# ------------------------------------------------------------------ pack

def _size_key(b: Box):
    """Boxes that are the same size (either way round, if they turn) share
    this key."""
    return tuple(sorted(tuple(round(v, ND) for v in s[:2]) for s in _sizes(b)))


def _turned_all(boxes: Sequence[Box], flat: bool, bin_w: float, bin_h: float):
    """Every box that may turn turned the same way (its long side across
    when `flat`, else along) where that way fits the bin, none left free to
    turn: equal boxes line up. -> (boxes, turned flags)."""
    out, flags = [], []
    for b in boxes:
        sizes = [s for s in _sizes(b) if s[0] <= bin_w + _EPS and s[1] <= bin_h + _EPS]
        w, h, t = sizes[0]
        for sw, sh, st in sizes[1:]:
            if (sw > sh + _EPS if flat else sh > sw + _EPS) and not (
                    w > h + _EPS if flat else h > w + _EPS):
                w, h, t = sw, sh, st
        out.append(Box(b.key, w, h, False, None,
                       None if b.cut is None else (b.cut[t],) * 2))
        flags.append(t)
    return out, flags


def _variants(boxes: Sequence[Box], bin_w: float, bin_h: float):
    """(how, places) of every variant pack tries: ORDERS x CHOICES x SPLITS,
    then the ones that line cuts up -- every box turned the same way (the
    long side across, or along), and equal boxes packed together, the most
    numerous size first. Measured (2026-10-18, 400 sets with repeated
    sizes): each family wins some; each size on bins of its own never did
    (every bin adds its edge cuts), so it is not tried."""
    for oi, (oname, _f) in enumerate(ORDERS):
        for choice in CHOICES:
            for split in SPLITS:
                yield ("%s, %s, %s" % (oname, choice, split),
                       guillotine(boxes, bin_w, bin_h, oi, choice, split))
    for flat in (True, False):
        if not any(b.turn for b in boxes):
            break                                   # nothing turns: the variants above
        turned, flags = _turned_all(boxes, flat, bin_w, bin_h)
        for oi, (oname, _f) in enumerate(ORDERS):
            for choice in CHOICES:
                for split in SPLITS:
                    got = guillotine(turned, bin_w, bin_h, oi, choice, split)
                    yield ("%s turned %s, %s, %s" % ("flat" if flat else "upright", oname,
                                                     choice, split),
                           [p if p is None else p._replace(turned=flags[k])
                            for k, p in enumerate(got)])
    groups: dict = {}
    for k, b in enumerate(boxes):
        groups.setdefault(_size_key(b), []).append(k)
    if len(groups) == len(boxes):
        return                                      # no two boxes the same size
    by = sorted(groups.items(), key=lambda kv: (-len(kv[1]), tuple(-v for s in kv[0] for v in s),
                                                kv[1][0]))
    seq = [k for _key, ks in by for k in ks]
    for choice in CHOICES:
        for split in SPLITS:
            yield ("same size, %s, %s" % (choice, split),
                   _run(boxes, bin_w, bin_h, seq, choice, split))


OBJECTIVES = ("fewest_sheets", "fewest_cuts")


def _cut_rect(p: Place, cut):
    """What is cut out of a placed box, in the bin (rounded as pack's keys)."""
    if cut is None:
        return (round(p.x, ND), round(p.y, ND), round(p.x + p.w, ND), round(p.y + p.h, ND))
    x0, y0, x1, y1 = cut[1 if p.turned else 0]
    return (round(p.x + x0, ND), round(p.y + y0, ND), round(p.x + x1, ND),
            round(p.y + y1, ND))


def pack(boxes: Sequence[Box], bin_w: float, bin_h: float, gap: float = 0.0,
         stock: Optional[Tuple[float, float, float, float]] = None,
         objective: str = "fewest_sheets") -> Packing:
    """Every box on as few bins as possible, at least `gap` apart, never
    scaled: the best of the guillotine variants (ORDERS x CHOICES x SPLITS,
    see the module's docstring). A box no empty bin holds (either way
    round, if it may turn) is rejected with the reason.

    `objective` (Zach, 2026-10-18: "two things to optimize for ... one is
    fewest cut lines, one is most compact (fewest number of sheets)"):
    "fewest_sheets" ranks the variants by bins, then cuts; "fewest_cuts" by
    cuts (on each box's `cut`), then bins. Both rank the same variants, so
    fewest_cuts never cuts more and fewest_sheets never takes more bins."""
    if objective not in OBJECTIVES:
        raise ValueError("objective is one of %s (got %r)" % (", ".join(OBJECTIVES), objective))
    cuts_first = objective == "fewest_cuts"
    gap = float(gap)
    if not (bin_w > 0 and bin_h > 0) or gap < 0:
        raise ValueError("a bin is a positive w x h and the gap >= 0 (got %r x %r, gap %r)"
                         % (bin_w, bin_h, gap))
    stock = tuple(map(float, stock)) if stock is not None else (0.0, 0.0, float(bin_w),
                                                                 float(bin_h))
    rejected: List[Tuple[object, str]] = []
    grown: List[Box] = []
    for i, b in enumerate(boxes):
        sizes = _sizes(b)
        if not all(w > 0 and h > 0 for w, h, _t in sizes):
            rejected.append((b.key, "%r x %r is not a size" % (b.w, b.h)))
            continue
        if not any(w <= bin_w + _EPS and h <= bin_h + _EPS for w, h, _t in sizes):
            rejected.append((b.key, "%.1f x %.1f is bigger than the %.1f x %.1f bin%s"
                             % (b.w, b.h, bin_w, bin_h,
                                " either way round" if b.turn else "")))
            continue
        t = None if b.turned is None else (b.turned[0] + gap, b.turned[1] + gap)
        grown.append(Box(i, b.w + gap, b.h + gap, b.turn, t, b.cut))
    best = None
    seen: dict = {}                     # a bin's rects -> its cuts (variants often agree)
    k = 0
    for how, got in _variants(grown, bin_w + gap, bin_h + gap):
        places = [p._replace(w=p.w - gap, h=p.h - gap) for p in got]
        nb = 1 + max((p.bin for p in places), default=-1)
        k += 1
        if best is not None and not cuts_first and nb > best[0][0]:
            continue                    # more bins never wins: skip counting its cuts
        cuts = 0
        spread = 0.0
        compact = 0.0
        for b in range(nb):
            mine = tuple(sorted((round(p.x, ND), round(p.y, ND), round(p.x + p.w, ND),
                                 round(p.y + p.h, ND)) for p in places if p.bin == b))
            cut = mine
            if cuts_first:
                cut = tuple(sorted(_cut_rect(p, boxes[p.key].cut) for p in places
                                   if p.bin == b))
            if cut not in seen:
                seen[cut] = count_cuts(cut, stock)
            cuts += seen[cut]
            if best is not None and (cuts > best[0][0] if cuts_first else
                                     nb == best[0][0] and cuts > best[0][1]):
                break                   # more cuts already: it cannot win
            spread += b * sum((r[2] - r[0]) * (r[3] - r[1]) for r in mine)
            compact += ((max(r[2] for r in mine) - min(r[0] for r in mine))
                        * (max(r[3] for r in mine) - min(r[1] for r in mine)))
        else:
            turns = sum(1 for p in places if p.turned)
            first = (cuts, nb) if cuts_first else (nb, cuts)
            score = first + (round(spread, 3), turns, round(compact, 3), k)
            if best is None or score < best[0]:
                best = (score, places, how)
    places: List[Place] = []
    nb = cuts = 0
    how = ""
    if best is not None:
        (a, b, _s, _t, _c, _k), got, how = best
        nb, cuts = (b, a) if cuts_first else (a, b)
        places = [p._replace(key=boxes[p.key].key) for p in got]
    area = sum(p.w * p.h for p in places)
    fill = area / (nb * bin_w * bin_h) if nb else 0.0
    return Packing(places=places, rejected=rejected, bins=nb, cuts=cuts, fill=fill, how=how)
