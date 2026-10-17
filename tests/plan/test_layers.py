"""M2.4: the layers are where they belong, on every golden case.

* every material layer (an "add" step of a part that adds material) lies
  inside the union of the tile and the target's outer loop (1e-6 mm);
* the pattern's ink is core.markers.cell_boxes, cell for cell;
* guides.quiet_ring contains guides.sticker;
* each part's z range is the slab core.slabs planned for it;
* the plan is JSON, deterministic and schema-versioned."""
from __future__ import annotations

import json

import pytest

import _evaluate_golden as G
from aruco_studio.core import markers as M
from aruco_studio.plan import plan_tag
from aruco_studio.plan.spec import TagSpec

TOL = 1e-6


def _inside_poly(loop, p, tol=TOL):
    u, v = p
    inside = False
    n = len(loop)
    for i in range(n):
        (x0, y0), (x1, y1) = loop[i - 1], loop[i]
        # on the edge (within tol) counts
        dx, dy = x1 - x0, y1 - y0
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((u - x0) * dx + (v - y0) * dy) / L2))
        if (u - x0 - t * dx) ** 2 + (v - y0 - t * dy) ** 2 <= tol * tol:
            return True
        if (y0 > v) != (y1 > v) and u < x0 + (v - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside


def _in_rect(r, p, tol=TOL):
    return r is not None and r[0] - tol <= p[0] <= r[2] + tol and r[1] - tol <= p[1] <= r[3] + tol


def _plans(group):
    for c in G.cases(group):
        if "error" in c["out"]:
            continue
        p = plan_tag(TagSpec.from_dict(c["in"]))
        assert p.ok, (c["id"], p.data["errors"])
        yield c, p


@pytest.mark.parametrize("group", ["legacy", "matrix"])
def test_material_lies_on_the_tile_or_the_target(group):
    bad = []
    for c, p in _plans(group):
        d = p.data
        tile = d["guides"]["tile"]
        outer = d["guides"]["target"][0] if d["guides"]["target"] else None
        forced = bool((d.get("label") or {}).get("forced"))
        for L in d["layers"]:
            if L["op"] != "add" or L["step"] != "add":
                continue
            if forced and L["name"].startswith("label"):
                continue                    # Build anyway: it may hang off the face (warned)
            for poly in L["polygons"]:
                for q in poly["outer"]:
                    if not (_in_rect(tile, q) or (outer and _inside_poly(outer, q))):
                        bad.append((c["id"], L["name"], q))
                        break
    assert not bad, bad[:5]


@pytest.mark.parametrize("group", ["legacy", "matrix"])
def test_pattern_ink_is_cell_boxes_cell_for_cell(group):
    for c, p in _plans(group):
        ev = p.ev
        want = [[[x0 * 1000.0, y0 * 1000.0], [x1 * 1000.0, y0 * 1000.0],
                 [x1 * 1000.0, y1 * 1000.0], [x0 * 1000.0, y1 * 1000.0]]
                for (x0, y0, x1, y1) in M.cell_boxes(ev["spec"])]
        name = "cells" if ev["mode"] == "white" else "pattern"
        cells = [L for L in p.data["layers"] if L["part"] == "pattern" and L["name"] == name]
        assert len(cells) == 1, (c["id"], [L["name"] for L in p.data["layers"]])
        got = [pp["outer"] for pp in cells[0]["polygons"]]
        assert len(got) == len(want), c["id"]
        for g, w in zip(got, want):
            assert all(abs(a - b) <= 1e-9 for gp, wp in zip(g, w) for a, b in zip(gp, wp)), c["id"]


@pytest.mark.parametrize("group", ["legacy", "matrix"])
def test_quiet_ring_contains_the_sticker(group):
    for c, p in _plans(group):
        g = p.data["guides"]
        s, q = g["sticker"], g["quiet_ring"]
        assert q[0] <= s[0] + TOL and q[1] <= s[1] + TOL and q[2] >= s[2] - TOL \
            and q[3] >= s[3] - TOL, (c["id"], s, q)
        h, pr = g["clear_hard"], g["clear_preferred"]
        assert pr[0] <= h[0] + TOL and pr[2] >= h[2] - TOL


@pytest.mark.parametrize("group", ["legacy", "matrix"])
def test_each_part_sits_in_its_slab(group):
    for c, p in _plans(group):
        sl = p.data["slabs"]
        for L in p.data["layers"]:
            if L["step"] != "add":
                continue
            lo, hi = L["z"]
            if L["part"] == "tile":
                assert [lo, hi] == [round(v, 9) + 0.0 for v in sl["white"]], c["id"]
            elif L["part"] == "pattern":
                assert [lo, hi] == [round(v, 9) + 0.0 for v in sl["pattern"]], c["id"]
            elif L["part"] == "pocket":
                assert [lo, hi] == [round(v, 9) + 0.0 for v in sl["pocket"]], c["id"]


def test_plan_json_is_deterministic_and_versioned():
    c = next(c for c in G.cases("matrix") if "error" not in c["out"])
    a = plan_tag(TagSpec.from_dict(c["in"])).to_json()
    b = plan_tag(TagSpec.from_dict(json.loads(json.dumps(c["in"])))).to_json()
    assert a == b
    d = json.loads(a)
    assert d["schema"] == "arucostudio.tagplan/1"
    assert d["rules"]["spec"] == 2 and d["rules"]["font"] == 1
