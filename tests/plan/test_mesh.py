"""plan/region.py and plan/mesh.py: the solids, exactly.

* the 2D boolean against hand-made cases (union, cut, holes, touching);
* every body of every golden case: a closed mesh (every edge in exactly two
  triangles), its volume = its region's area x its height (1e-6), the
  region's polygons and its trapezoids the same area;
* the assembly: the pattern's ink on top equals what verify/render's pixel
  CSG says (tests/verify/test_mesh_raster.py reads both with OpenCV).
"""
from __future__ import annotations

from collections import Counter

import pytest

import _evaluate_golden as G
from aruco_studio.plan import mesh as ME
from aruco_studio.plan import plan_tag
from aruco_studio.plan import region as RG
from aruco_studio.plan.spec import TagSpec


def sq(x0, y0, x1, y1):
    return [[(x0, y0), (x1, y0), (x1, y1), (x0, y1)]]


def test_boolean_hand_cases():
    A = [sq(0, 0, 1, 1), sq(1, 0, 2, 1), sq(0.5, 0.5, 1.5, 2)]
    tri = [[[(0.2, 0.2), (0.8, 0.2), (0.5, 0.8)]]]
    t = RG.boolean([A, tri], lambda f: f[0] and not f[1])
    assert abs(sum(x.area for x in t) - (3.0 - 0.18)) < 1e-12
    ps = RG.polygons(t)
    assert len(ps) == 1 and len(ps[0]) == 2 and abs(RG.area(ps) - 2.82) < 1e-12
    ring = [[[(-3, -3), (3, -3), (3, 3), (-3, 3)], [(-1, -1), (-1, 1), (1, 1), (1, -1)]]]
    ps = RG.polygons(RG.boolean([ring], lambda f: f[0]))
    assert len(ps) == 1 and len(ps[0]) == 2 and abs(RG.area(ps) - 32.0) < 1e-12
    # two squares touching at a corner: two pieces
    t = RG.boolean([[sq(0, 0, 1, 1), sq(1, 1, 2, 2)]], lambda f: f[0])
    assert len(RG.components(t)) == 2 and len(RG.polygons(t)) == 2
    # intersection, xor
    t = RG.boolean([[sq(0, 0, 2, 2)], [sq(1, 1, 3, 3)]], lambda f: f[0] and f[1])
    assert abs(sum(x.area for x in t) - 1.0) < 1e-12
    t = RG.boolean([[sq(0, 0, 2, 2)], [sq(1, 1, 3, 3)]], lambda f: f[0] != f[1])
    assert abs(sum(x.area for x in t) - 6.0) < 1e-12
    # crossing slanted edges
    a = [[[(0, 0), (4, 0), (0, 4)]]]
    b = [[[(0, 0), (4, 4), (4, 0)]]]
    t = RG.boolean([a, b], lambda f: f[0] or f[1])
    assert abs(sum(x.area for x in t) - 12.0) < 1e-9


def _closed(pos, tri):
    e = Counter()
    for a, b, c in tri:
        for u, v in ((a, b), (b, c), (c, a)):
            e[(min(u, v), max(u, v))] += 1
    return sum(1 for v in e.values() if v != 2)


def _check_plan(p):
    bad = []
    for b in ME.bodies(p):
        pos, tri = ME.prism(b["_traps"], *b["z"])
        if _closed(pos, tri):
            bad.append((b["what"], b["z"], "open"))
            continue
        flat = [c for q in pos for c in q]
        vol = ME.volume(flat, [i for t in tri for i in t])
        h = b["z"][1] - b["z"][0]
        want = sum(t.area for t in b["_traps"]) * h
        if abs(vol - want) > 1e-6 * max(1.0, want):
            bad.append((b["what"], b["z"], "volume", vol, want))
        if abs(RG.area(b["polygons"]) * h - want) > 1e-6 * max(1.0, want):
            bad.append((b["what"], b["z"], "polygons", RG.area(b["polygons"]) * h, want))
    return bad


CHUNKS = 8


@pytest.mark.parametrize("chunk", range(CHUNKS))
def test_every_body_is_closed_and_its_volume_is_area_times_height(chunk):
    bad = []
    for c in (G.cases("legacy") + G.cases("matrix"))[chunk::CHUNKS]:
        if "error" in c["out"]:
            continue
        p = plan_tag(TagSpec.from_dict(c["in"]))
        b = _check_plan(p)
        if b:
            bad.append((c["id"], b[:2]))
    assert not bad, bad[:3]


def test_stl_is_its_triangles():
    import struct
    c = next(c for c in G.cases("matrix") if "error" not in c["out"])
    p = plan_tag(TagSpec.from_dict(c["in"]))
    data = ME.stl(p)
    n = struct.unpack("<I", data[80:84])[0]
    assert len(data) == 84 + 50 * n and n > 0
    assert n == sum(len(m["indices"]) // 3 for m in ME.mesh(p))


def test_mesh_json_is_flat_and_per_body():
    c = next(c for c in G.cases("matrix") if "error" not in c["out"])
    p = plan_tag(TagSpec.from_dict(c["in"]))
    ms = ME.mesh(p)
    assert ms and all(len(m["positions"]) % 3 == 0 and len(m["indices"]) % 3 == 0 for m in ms)
    assert {m["colour"] for m in ms} <= {"white", "black", "body"}
    zmax = max(L["z"][1] for L in p.data["layers"] if L["step"] == "add" and L["op"] == "add")
    assert abs(max(m["z"][1] for m in ms) - max(zmax, (p.data["body"] or {"z": [0, 0]})["z"][1])) < 1e-9
