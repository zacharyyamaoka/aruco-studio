"""Lane speed: plan/region.py and plan/mesh.py got faster, their results
stayed bit-identical.

tests/fixtures/mesh_digests.json holds, for 947 plans (the goldens, the
examples, a fuzz sample), the sha256 of each output as the code BEFORE the
lane gave it (tools/mesh_digests.py --write at 46f2bac): the plan, the
bodies (polygons and trapezoids), the top view, the mesh, the removed
volume and the STL. Every one must come out the same.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import mesh_digests as MD  # noqa: E402

from aruco_studio.plan import mesh as ME  # noqa: E402
from aruco_studio.plan import region as RG  # noqa: E402

CHUNKS = 8
WANT = json.loads(MD.OUT.read_text(encoding="utf-8"))["cases"]
# merge-polish: the plan digests lane polish changed on purpose. Only the
# "plan" digest may differ; the solids, top views and STLs stay 46f2bac's.
MERGE = json.loads(MD.MERGE.read_text(encoding="utf-8"))["plan"]


def _want(cid):
    w = WANT[cid]
    return dict(w, plan=MERGE[cid]) if cid in MERGE else w


def test_the_fixture_was_made_before_the_lane():
    assert json.loads(MD.OUT.read_text(encoding="utf-8"))["made_at"] == "46f2bac"
    assert len(WANT) == 947


# what lane polish changed in a plan, by case: each kind leaves a mark in the plan
_POLISH_MARKS = (
    '"label":5',                      # label rule 5: sugar expands as a new tag
    "1, 2, 3, 4, 5",                  # an unknown rule's warn lists rule 5
    "size -",                         # C2: "Marker size -2 mm: 0 for Auto, ..."
    "it may print poorly —",     # C2: the cell-minimum warn's dash
)


def test_the_merge_overlay_is_only_lane_polish():
    """Every case in mesh_digests_merge.json is a plan lane polish changed on
    purpose, and its plan carries one of the marks above."""
    from aruco_studio.plan import plan_tag
    assert 0 < len(MERGE) <= 60 and set(MERGE) <= set(WANT)
    specs = dict(MD.corpus())
    for cid in MERGE:
        assert MERGE[cid] != WANT[cid]["plan"], cid
        text = json.dumps(plan_tag(specs[cid]).to_dict(), separators=(",", ":"), ensure_ascii=False)
        assert any(m in text for m in _POLISH_MARKS), cid


@pytest.mark.parametrize("chunk", range(CHUNKS))
def test_every_output_is_bit_identical(chunk):
    items = MD.corpus()
    assert {cid for cid, _s in items} == set(WANT)
    bad = []
    for cid, spec in items[chunk::CHUNKS]:
        got = MD._one((cid, spec))[1]
        if got != _want(cid):
            bad.append((cid, sorted(k for k in WANT[cid] if WANT[cid].get(k) != got.get(k))))
    assert not bad, bad[:5]


# ---------------------------------------------------------- the old code, side by side

def _simplify_before(lp):
    """region._simplify as it was at 46f2bac (restart from 0 after a drop)."""
    import math
    EPS = RG.EPS
    pts = []
    for p in lp:
        if not pts or abs(p[0] - pts[-1][0]) > EPS or abs(p[1] - pts[-1][1]) > EPS:
            pts.append(p)
    if len(pts) > 1 and abs(pts[0][0] - pts[-1][0]) <= EPS and abs(pts[0][1] - pts[-1][1]) <= EPS:
        pts.pop()
    changed = True
    while changed and len(pts) > 3:
        changed = False
        for i in range(len(pts)):
            a, b, c = pts[i - 1], pts[i], pts[(i + 1) % len(pts)]
            cr = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
            la = math.hypot(c[0] - a[0], c[1] - a[1]) or 1.0
            if abs(cr) / la <= EPS and ((b[0] - a[0]) * (c[0] - b[0])
                                        + (b[1] - a[1]) * (c[1] - b[1])) >= 0:
                pts.pop(i)
                changed = True
                break
    return pts


def _split_pinches_before(pos, tris):
    """mesh._split_pinches as it was at 46f2bac (union-find at every vertex)."""
    from collections import defaultdict
    inc = defaultdict(list)
    for t, tri in enumerate(tris):
        for v in tri:
            inc[v].append(t)
    tris = [list(t) for t in tris]
    pos = list(pos)
    for v, ts in inc.items():
        if len(ts) < 3:
            continue
        by_w = defaultdict(list)
        for t in ts:
            for w in tris[t]:
                if w != v:
                    by_w[w].append(t)
        parent = {t: t for t in ts}

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a
        for w, tt in by_w.items():
            if len(tt) == 2:
                a, b = find(tt[0]), find(tt[1])
                if a != b:
                    parent[a] = b
        fans = defaultdict(list)
        for t in ts:
            fans[find(t)].append(t)
        if len(fans) < 2:
            continue
        for k, (_root, fan) in enumerate(sorted(fans.items())):
            if k == 0:
                continue
            nv = len(pos)
            pos.append(pos[v])
            for t in fan:
                tris[t] = [nv if x == v else x for x in tris[t]]
    return pos, tris


def test_simplify_drops_the_same_points_in_the_same_order():
    r = random.Random(1017)
    for _ in range(3000):
        n = r.randint(3, 40)
        pts = []
        x, y = 0.0, 0.0
        for _k in range(n):
            mode = r.random()
            if mode < 0.4:                       # straight runs, some a hair off
                x += r.choice([1.0, 0.5, 2.0])
                y += r.choice([0.0, 0.0, 1e-10, -1e-10, 1e-8])
            elif mode < 0.6:
                y += r.choice([1.0, -1.0, 0.25])
            elif mode < 0.7:                     # a repeat, or a step back
                x -= r.choice([0.0, 1.0])
            else:
                x, y = x + r.uniform(-3, 3), y + r.uniform(-3, 3)
            pts.append((round(x, 9), round(y, 9)))
        assert RG._simplify(list(pts)) == _simplify_before(list(pts)), pts


def _checker(n, m, holes=()):
    """A checkerboard's black squares (they touch at corners: pinches)."""
    return [[[(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]] for i in range(n) for j in range(m)
            if (i + j) % 2 == 0 and (i, j) not in holes]


def test_split_pinches_makes_the_same_copies():
    r = random.Random(7)
    cases = [_checker(4, 3), _checker(6, 6), _checker(5, 2, holes={(0, 0)})]
    for _ in range(40):
        cells = [[[(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]]
                 for i in range(5) for j in range(5) if r.random() < 0.5]
        if cells:
            cases.append(cells)
    for polys in cases:
        traps = RG.boolean([polys], lambda f: f[0])
        # prism() without its last step: the raw shell, then both splits
        pos, tris = [], []
        for comp in RG.components(traps):
            index = {}

            def v(p, z):
                key = (p[0], p[1], z)
                i = index.get(key)
                if i is None:
                    i = index[key] = len(pos)
                    pos.append(key)
                return i
            edges, ys_at = RG.boundary(comp)
            for c, a, b in RG.faces(comp, ys_at):
                tris.append((v(c, 1.0), v(a, 1.0), v(b, 1.0)))
                tris.append((v(c, 0.0), v(b, 0.0), v(a, 0.0)))
            for a, b in edges:
                tris.append((v(a, 0.0), v(b, 0.0), v(b, 1.0)))
                tris.append((v(a, 0.0), v(b, 1.0), v(a, 1.0)))
        # one shell for the whole board too: the corners then really pinch
        assert ME._split_pinches(list(pos), list(tris)) == _split_pinches_before(list(pos), list(tris))
        glued = {}
        gpos, gtris = [], []
        for t in tris:
            q = []
            for i in t:
                k = pos[i]
                if k not in glued:
                    glued[k] = len(gpos)
                    gpos.append(k)
                q.append(glued[k])
            gtris.append(tuple(q))
        assert ME._split_pinches(list(gpos), list(gtris)) == _split_pinches_before(list(gpos), list(gtris))


def test_booleans_is_each_boolean_alone():
    r = random.Random(3)
    for _ in range(60):
        groups = []
        for _g in range(r.randint(1, 4)):
            polys = []
            for _p in range(r.randint(1, 3)):
                x, y = r.uniform(-5, 5), r.uniform(-5, 5)
                k = r.randint(3, 6)
                import math
                pts = [(round(x + r.uniform(1, 3) * math.cos(2 * math.pi * i / k), 6),
                        round(y + r.uniform(1, 3) * math.sin(2 * math.pi * i / k), 6)) for i in range(k)]
                polys.append([pts])
            groups.append(polys)
        n = len(groups)
        exprs = [lambda f: f[0], lambda f: any(f), lambda f: sum(f) == 1,
                 lambda f, n=n: f[0] and not f[n - 1]]
        both = RG.booleans(groups, exprs)
        for e, got in zip(exprs, both):
            alone = RG.boolean(groups, e)
            assert [(t.x0, t.x1, t.yb0, t.yb1, t.yt0, t.yt1) for t in got] == \
                [(t.x0, t.x1, t.yb0, t.yb1, t.yt0, t.yt1) for t in alone]
