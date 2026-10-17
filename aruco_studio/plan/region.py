"""2D booleans on polygons with holes, standard library only.

The plan's layers are REF's temporary bodies step by step (boxes and
prisms united and cut). Every step is a straight prism along the face
normal, so a part is, per slab of z, a 2D boolean of polygons. This module
does that boolean exactly (no grid): a vertical slab sweep.

    regions = boolean(groups, expr)
      groups  [[polygon, ...], ...]   a polygon = [outer, hole, ...] loops
                                      (even-odd inside each group)
      expr    f(inside: tuple of bool per group) -> bool
      -> [Trapezoid]                   the result, as vertical-sided pieces
    polygons(traps) -> [[outer, hole, ...]]   merged: outer CCW, holes CW
    triangulate(outer, holes) -> [(a, b, c)]   ear clipping (holes bridged)

Between two consecutive vertex x's (and the x's where edges cross) every
edge is a straight piece across the whole slab; ordered by height, the
inside state of each group flips at its own edges, and runs where `expr`
holds become trapezoids. Points shared by two slabs are computed by the
same expression, so they are bit-identical and the merge is exact.
"""
from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from typing import Callable, Dict, List, Sequence, Tuple

Pt = Tuple[float, float]
EPS = 1e-9
ND = 9                  # every coordinate out is rounded to 1e-9: two edges a hair
                        # apart give one corner, so neighbours meet exactly


def _q(v: float) -> float:
    return round(v, ND) + 0.0


class Edge:
    __slots__ = ("x0", "y0", "x1", "y1", "g", "p", "k")

    def __init__(self, a: Pt, b: Pt, g: int, p: int):
        if a[0] > b[0]:
            a, b = b, a
        self.x0, self.y0, self.x1, self.y1 = a[0], a[1], b[0], b[1]
        self.g, self.p = g, p
        self.k = (b[1] - a[1]) / (b[0] - a[0])

    def y(self, x: float) -> float:
        if x <= self.x0:
            return self.y0
        if x >= self.x1:
            return self.y1
        return self.y0 + (x - self.x0) * self.k


class Trapezoid:
    """x0..x1, its bottom from yb0 (at x0) to yb1 (at x1), its top yt0..yt1."""
    __slots__ = ("x0", "x1", "yb0", "yb1", "yt0", "yt1")

    def __init__(self, x0, x1, yb0, yb1, yt0, yt1):
        self.x0, self.x1, self.yb0, self.yb1, self.yt0, self.yt1 = x0, x1, yb0, yb1, yt0, yt1

    @property
    def area(self) -> float:
        return (self.x1 - self.x0) * ((self.yt0 - self.yb0) + (self.yt1 - self.yb1)) / 2.0

    def pts(self) -> List[Pt]:
        """Counter-clockwise."""
        return [(self.x0, self.yb0), (self.x1, self.yb1), (self.x1, self.yt1),
                (self.x0, self.yt0)]


def _edges(groups):
    """Every non-vertical edge, tagged with its group and its polygon (a
    group is the UNION of its polygons; a polygon is even-odd over its
    loops)."""
    out, xs = [], set()
    pid = 0
    for g, polys in enumerate(groups):
        for poly in polys:
            for lp in poly:
                n = len(lp)
                if n < 3:
                    continue
                for i in range(n):
                    a, b = lp[i - 1], lp[i]
                    a = (_q(a[0]), _q(a[1]))
                    b = (_q(b[0]), _q(b[1]))
                    xs.add(a[0])
                    if abs(a[0] - b[0]) > EPS:
                        out.append(Edge(a, b, g, pid))
            pid += 1
    return out, sorted(xs), pid


def boolean(groups: Sequence[Sequence[Sequence[Sequence[Pt]]]],
            expr: Callable[[Tuple[bool, ...]], bool]) -> List[Trapezoid]:
    return booleans(groups, [expr])[0]


def _memo(expr):
    """`expr` kept by its flags: it is a pure function of them, and a sweep
    asks the same few combinations thousands of times (lane speed)."""
    seen: Dict[Tuple[bool, ...], bool] = {}

    def f(flags):
        v = seen.get(flags)
        if v is None:
            v = seen[flags] = expr(flags)
        return v
    return f


def booleans(groups: Sequence[Sequence[Sequence[Sequence[Pt]]]],
             exprs: Sequence[Callable[[Tuple[bool, ...]], bool]]) -> List[List[Trapezoid]]:
    """boolean(groups, e) for each e of `exprs`, from one sweep: the slabs,
    the edges' order and their crossings do not depend on the expression,
    so each result is exactly what boolean(groups, e) alone gives."""
    edges, xs, npoly = _edges(groups)
    ng = len(groups)
    edges.sort(key=lambda e: e.x0)
    fs = [_memo(e) for e in exprs]
    outs: List[List[Trapezoid]] = [[] for _ in fs]
    active: List[Edge] = []
    j = 0
    for xa, xb in zip(xs, xs[1:]):
        if xb - xa <= EPS:
            continue
        xm = (xa + xb) / 2.0
        while j < len(edges) and edges[j].x0 < xm:
            active.append(edges[j])
            j += 1
        active = [e for e in active if e.x1 > xm]
        if active:
            _slab(active, xa, xb, ng, npoly, fs, outs, 0)
    return [_snap(out) for out in outs]


SNAP = 1e-7             # corners on one slab line closer than this are one corner


def _snap(traps: List["Trapezoid"]) -> List["Trapezoid"]:
    """Corners on one slab line that two neighbours computed from two
    edges a hair apart (1e-12) become one: the first of each cluster."""
    ys: Dict[float, list] = {}
    for t in traps:
        ys.setdefault(t.x0, []).extend((t.yb0, t.yt0))
        ys.setdefault(t.x1, []).extend((t.yb1, t.yt1))
    rep: Dict[float, Dict[float, float]] = {}
    for x, vals in ys.items():
        m = {}
        cur = None
        for v in sorted(set(vals)):
            if cur is None or v - cur > SNAP:
                cur = v
            m[v] = cur
        rep[x] = m
    out = []
    for t in traps:
        a, b = rep[t.x0], rep[t.x1]
        u = Trapezoid(t.x0, t.x1, a[t.yb0], b[t.yb1], a[t.yt0], b[t.yt1])
        if (u.yt0 - u.yb0) > EPS or (u.yt1 - u.yb1) > EPS:
            out.append(u)
    return out


def _slab(active, xa, xb, ng, npoly, exprs, outs, depth):
    """The runs of each expression in exprs between xa and xb, appended to
    the matching list of outs. Each edge's heights at xa, xm and xb are
    computed once (the same Edge.y calls as before, so the same floats)."""
    xm = (xa + xb) / 2.0
    ya = [e.y(xa) for e in active]
    yb = [e.y(xb) for e in active]
    ymid = [e.y(xm) for e in active]
    order = sorted(range(len(active)), key=lambda k: (ymid[k], ya[k] + yb[k]))
    # edges that cross inside the slab: split it where they do
    if depth < 30:
        cuts = set()
        for p, q in zip(order, order[1:]):
            da, db = ya[q] - ya[p], yb[q] - yb[p]
            if (da < -EPS and db > EPS) or (da > EPS and db < -EPS):
                t = da / (da - db)
                xc = _q(xa + t * (xb - xa))
                if xa + EPS < xc < xb - EPS:
                    cuts.add(xc)
        if cuts:
            pts = [xa] + sorted(cuts) + [xb]
            for a, b in zip(pts, pts[1:]):
                if b - a > EPS:
                    _slab(active, a, b, ng, npoly, exprs, outs, depth + 1)
            return
    es = [active[k] for k in order]
    eya = [ya[k] for k in order]
    eyb = [yb[k] for k in order]
    eym = [ymid[k] for k in order]
    parity = [False] * npoly
    count = [0] * ng
    inside = [False] * ng                      # count[g] > 0, kept as the counts change
    ne = len(exprs)
    flags = tuple(inside)
    states = [f(flags) for f in exprs]
    starts: List = [None] * ne
    i, n = 0, len(es)
    while i < n:
        # every edge at this height at once: no zero-height gaps
        j = i
        ym = eym[i]
        while j < n and eym[j] - ym <= EPS:
            j += 1
        for k in range(i, j):
            e = es[k]
            parity[e.p] = not parity[e.p]
            count[e.g] += 1 if parity[e.p] else -1
            inside[e.g] = count[e.g] > 0
        flags = tuple(inside)
        for x in range(ne):
            before = states[x]
            after = states[x] = exprs[x](flags)
            if not before and after:
                starts[x] = i
            elif before and not after and starts[x] is not None:
                s, k = starts[x], j - 1
                t = Trapezoid(xa, xb, _q(eya[s]), _q(eyb[s]), _q(eya[k]), _q(eyb[k]))
                if (t.yt0 - t.yb0) > EPS or (t.yt1 - t.yb1) > EPS:
                    outs[x].append(t)
                starts[x] = None
        i = j


# ---------------------------------------------------------------- merging

def _area2(pts):
    return sum(pts[i - 1][0] * pts[i][1] - pts[i][0] * pts[i - 1][1] for i in range(len(pts)))


def _intervals_minus(a, b):
    """Intervals of `a` not covered by `b` (both lists of (lo, hi))."""
    out = []
    for lo, hi in a:
        cur = [(lo, hi)]
        for blo, bhi in b:
            nxt = []
            for clo, chi in cur:
                if bhi <= clo or blo >= chi:
                    nxt.append((clo, chi))
                    continue
                if blo > clo:
                    nxt.append((clo, blo))
                if bhi < chi:
                    nxt.append((bhi, chi))
            cur = nxt
        out += [(x, y) for x, y in cur if y - x > EPS]
    return out


def _merge_intervals(iv):
    iv = sorted(iv)
    out = []
    for lo, hi in iv:
        if out and lo <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], hi))
        else:
            out.append((lo, hi))
    return out


def boundary(traps: Sequence[Trapezoid]):
    """The region's boundary as directed edges (the region on their left):
    every trapezoid's bottom (left -> right) and top (right -> left), and on
    each slab line the vertical pieces where only one side is inside, split
    at every trapezoid corner on that line. -> (edges, {x: sorted ys})."""
    edges: List[Tuple[Pt, Pt]] = []
    left: Dict[float, list] = {}
    right: Dict[float, list] = {}
    pts_at: Dict[float, set] = {}
    for t in traps:
        if (t.x1 - t.x0) > EPS:
            edges.append(((t.x0, t.yb0), (t.x1, t.yb1)))
            edges.append(((t.x1, t.yt1), (t.x0, t.yt0)))
        right.setdefault(t.x1, []).append((t.yb1, t.yt1))       # its right side at x1
        left.setdefault(t.x0, []).append((t.yb0, t.yt0))        # its left side at x0
        pts_at.setdefault(t.x0, set()).update((t.yb0, t.yt0))
        pts_at.setdefault(t.x1, set()).update((t.yb1, t.yt1))
    ys_at = {x: sorted(v) for x, v in pts_at.items()}
    for x in set(left) | set(right):
        L = _merge_intervals(right.get(x, []))       # inside, to the left of x
        R = _merge_intervals(left.get(x, []))        # inside, to the right of x
        ys = ys_at.get(x, [])
        # ys is sorted: the ys strictly between lo and hi are one slice of it
        for lo, hi in _intervals_minus(L, R):         # inside on the left: going up
            seq = [lo] + ys[bisect_right(ys, lo):bisect_left(ys, hi)] + [hi]
            for a, b in zip(seq, seq[1:]):
                edges.append(((x, a), (x, b)))
        for lo, hi in _intervals_minus(R, L):         # inside on the right: going down
            seq = [hi] + ys[bisect_right(ys, lo):bisect_left(ys, hi)][::-1] + [lo]
            for a, b in zip(seq, seq[1:]):
                edges.append(((x, a), (x, b)))
    return edges, ys_at


def polygons(traps: Sequence[Trapezoid]) -> List[List[List[Pt]]]:
    """Trapezoids -> polygons with holes ([outer CCW, holes CW]),
    collinear points removed."""
    if not traps:
        return []
    edges, _ys = boundary(traps)
    loops = _chain(edges)
    loops = [_simplify(lp) for lp in loops]
    loops = [lp for lp in loops if len(lp) >= 3 and abs(_area2(lp)) > EPS]
    outers = [lp for lp in loops if _area2(lp) > 0]
    holes = [lp for lp in loops if _area2(lp) < 0]
    out = [[o] for o in outers]
    for h in holes:
        p = _inner_point(h)
        best, best_a = None, None
        for k, o in enumerate(outers):
            if _inside(o, p):
                a = abs(_area2(o))
                if best is None or a < best_a:
                    best, best_a = k, a
        if best is not None:
            out[best].append(h)
    return out


def faces(traps: Sequence[Trapezoid], ys_at: Dict[float, list]):
    """A watertight triangulation of the region (for a mesh's top and
    bottom): each trapezoid fanned from its centre, its vertical sides
    split at every corner on that line (so neighbours share edges).
    `ys_at` as boundary() gives it: each line's ys sorted."""
    tris = []
    for t in traps:
        ring = [(t.x0, t.yb0), (t.x1, t.yb1)]
        ys = ys_at.get(t.x1, [])                       # sorted: one slice of it
        ring += [(t.x1, y) for y in ys[bisect_right(ys, t.yb1):bisect_left(ys, t.yt1)]]
        ring += [(t.x1, t.yt1), (t.x0, t.yt0)]
        ys = ys_at.get(t.x0, [])
        ring += [(t.x0, y) for y in ys[bisect_right(ys, t.yb0):bisect_left(ys, t.yt0)][::-1]]
        pts = []
        for p in ring:
            if not pts or p != pts[-1]:
                pts.append(p)
        if len(pts) > 1 and pts[0] == pts[-1]:
            pts.pop()
        if len(pts) < 3:
            continue
        c = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            if a != b:
                tris.append((c, a, b))
    return tris


def _chain(edges):
    from collections import defaultdict
    out_of = defaultdict(list)
    for e in edges:
        out_of[e[0]].append(e)
    used = set()
    loops = []
    for e in edges:
        if id(e) in used:
            continue
        loop = [e[0]]
        cur = e
        used.add(id(e))
        guard = 0
        while True:
            guard += 1
            if guard > 10 * len(edges) + 10:
                break
            b = cur[1]
            if b == loop[0]:
                break
            loop.append(b)
            cands = [c for c in out_of.get(b, []) if id(c) not in used]
            if not cands:
                break
            if len(cands) == 1:
                nxt = cands[0]
            else:
                dx, dy = b[0] - cur[0][0], b[1] - cur[0][1]

                def turn(c):
                    ex, ey = c[1][0] - b[0], c[1][1] - b[1]
                    return math.atan2(dx * ey - dy * ex, dx * ex + dy * ey)
                nxt = max(cands, key=turn)          # the sharpest LEFT turn: touching
                                                    # regions stay loops of their own
            used.add(id(nxt))
            cur = nxt
        loops.append(loop)
    return loops


def _simplify(lp):
    """Drop repeated and collinear points."""
    pts = []
    for p in lp:
        if not pts or abs(p[0] - pts[-1][0]) > EPS or abs(p[1] - pts[-1][1]) > EPS:
            pts.append(p)
    if len(pts) > 1 and abs(pts[0][0] - pts[-1][0]) <= EPS and abs(pts[0][1] - pts[-1][1]) <= EPS:
        pts.pop()
    # the first collinear point dropped, again and again, until none is left
    # (or three points). After a drop at i only i - 1 and i see new
    # neighbours (and 0, when the last point went), so the scan goes on
    # from there instead of from 0: the same drops in the same order, in
    # linear time (lane speed; it was quadratic on long straight runs).
    i = 0
    while len(pts) > 3 and i < len(pts):
        n = len(pts)
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
        cr = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        la = math.hypot(c[0] - a[0], c[1] - a[1]) or 1.0
        if abs(cr) / la <= EPS and ((b[0] - a[0]) * (c[0] - b[0])
                                    + (b[1] - a[1]) * (c[1] - b[1])) >= 0:
            pts.pop(i)
            i = 0 if i == n - 1 else max(i - 1, 0)
            continue
        i += 1
    return pts


def _inside(loop, p):
    inside = False
    for i in range(len(loop)):
        (x0, y0), (x1, y1) = loop[i - 1], loop[i]
        if (y0 > p[1]) != (y1 > p[1]) and p[0] < x0 + (p[1] - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside


def _inner_point(h):
    """A point inside a hole (a CW loop): an edge's midpoint, a hair to the
    right of the edge (the hole's side)."""
    best = None
    for i in range(len(h)):
        a, b = h[i - 1], h[i]
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if best is None or L > best[0]:
            best = (L, a, b)
    L, a, b = best
    nx, ny = (b[1] - a[1]) / L, -(b[0] - a[0]) / L       # right of a -> b
    d = min(1e-6, L * 1e-3)
    return ((a[0] + b[0]) / 2.0 + nx * d, (a[1] + b[1]) / 2.0 + ny * d)


def area(polys) -> float:
    return sum(_area2(lp) for poly in polys for lp in poly) / 2.0


# ---------------------------------------------------------------- triangles

def _bridge(outer: List[Pt], holes: List[List[Pt]]) -> List[Pt]:
    """One loop: every hole joined to the outer by a seam (David Eberly's
    method: the hole's rightmost point to a visible outer vertex)."""
    poly = list(outer)
    for h in sorted(holes, key=lambda lp: -max(p[0] for p in lp)):
        k = max(range(len(h)), key=lambda i: (h[i][0], h[i][1]))
        m = h[k]
        # the nearest outer point straight to the right that sees m
        best, best_d = None, None
        for i in range(len(poly)):
            a, b = poly[i], poly[(i + 1) % len(poly)]
            if (a[1] - m[1]) * (b[1] - m[1]) > 0 or a[1] == b[1]:
                continue
            x = a[0] + (m[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if x < m[0] - EPS:
                continue
            d = x - m[0]
            if best is None or d < best_d:
                # the edge's endpoint further right
                cand = i if a[0] > b[0] else (i + 1) % len(poly)
                best, best_d = cand, d
        if best is None:
            best = min(range(len(poly)), key=lambda i: (poly[i][0] - m[0]) ** 2
                       + (poly[i][1] - m[1]) ** 2)
        else:
            # a vertex inside the triangle (m, hit, poly[best]) would block it:
            # take the one with the smallest angle to the ray
            p = poly[best]
            hit = (m[0] + best_d, m[1])
            tri = [m, hit, p]
            inside = [i for i in range(len(poly)) if i != best and _in_tri(poly[i], tri)
                      and poly[i][0] >= m[0]]
            if inside:
                best = min(inside, key=lambda i: (abs(math.atan2(poly[i][1] - m[1],
                                                                 poly[i][0] - m[0])),
                                                  (poly[i][0] - m[0]) ** 2))
        hole = h[k:] + h[:k]
        poly = poly[:best + 1] + hole + [hole[0], poly[best]] + poly[best + 1:]
    return poly


def _in_tri(p, t, eps=0.0):
    (ax, ay), (bx, by), (cx, cy) = t
    d1 = (p[0] - bx) * (ay - by) - (ax - bx) * (p[1] - by)
    d2 = (p[0] - cx) * (by - cy) - (bx - cx) * (p[1] - cy)
    d3 = (p[0] - ax) * (cy - ay) - (cx - ax) * (p[1] - ay)
    neg = d1 < -eps or d2 < -eps or d3 < -eps
    pos = d1 > eps or d2 > eps or d3 > eps
    return not (neg and pos)


def triangulate(outer: Sequence[Pt], holes: Sequence[Sequence[Pt]] = ()) -> List[Tuple[Pt, Pt, Pt]]:
    """Ear clipping of a polygon with holes (outer CCW, holes CW)."""
    out = [tuple(p) for p in outer]
    if _area2(out) < 0:
        out.reverse()
    hs = []
    for h in holes:
        h = [tuple(p) for p in h]
        if _area2(h) > 0:
            h.reverse()
        hs.append(h)
    poly = _bridge(out, hs) if hs else out
    tris = []
    idx = list(range(len(poly)))
    guard = 0
    while len(idx) > 3 and guard < 10 * len(poly) * len(poly) + 100:
        guard += 1
        n = len(idx)
        cut = False
        for i in range(n):
            ia, ib, ic = idx[i - 1], idx[i], idx[(i + 1) % n]
            a, b, c = poly[ia], poly[ib], poly[ic]
            cr = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            if cr <= EPS * EPS:
                if abs(cr) <= EPS * EPS:
                    idx.pop(i)                      # a spike / a collinear point
                    cut = True
                    break
                continue
            ok = True
            for j in idx:
                if j in (ia, ib, ic):
                    continue
                p = poly[j]
                if p in (a, b, c):
                    continue
                if _in_tri_strict(p, (a, b, c)):
                    ok = False
                    break
            if ok:
                tris.append((a, b, c))
                idx.pop(i)
                cut = True
                break
        if not cut:
            break
    if len(idx) == 3:
        a, b, c = (poly[i] for i in idx)
        if abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) > EPS * EPS:
            tris.append((a, b, c))
    return tris


def _in_tri_strict(p, t):
    """Inside the triangle, or on its edges away from its corners."""
    (ax, ay), (bx, by), (cx, cy) = t
    e = EPS * EPS
    d1 = (bx - ax) * (p[1] - ay) - (by - ay) * (p[0] - ax)
    d2 = (cx - bx) * (p[1] - by) - (cy - by) * (p[0] - bx)
    d3 = (ax - cx) * (p[1] - cy) - (ay - cy) * (p[0] - cx)
    return d1 >= -e and d2 >= -e and d3 >= -e


def components(traps: Sequence[Trapezoid]) -> List[List[Trapezoid]]:
    """The trapezoids grouped into connected pieces: two are connected when
    they share a stretch of a slab line (not a single point: regions that
    touch at a corner are two pieces, so each becomes its own closed shell)."""
    n = len(traps)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    by_x0: Dict[float, list] = {}
    for i, t in enumerate(traps):
        by_x0.setdefault(t.x0, []).append(i)
    for i, t in enumerate(traps):
        for j in by_x0.get(t.x1, []):
            u = traps[j]
            if min(t.yt1, u.yt0) - max(t.yb1, u.yb0) > EPS:
                a, b = find(i), find(j)
                if a != b:
                    parent[a] = b
    groups: Dict[int, list] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(traps[i])
    return list(groups.values())
