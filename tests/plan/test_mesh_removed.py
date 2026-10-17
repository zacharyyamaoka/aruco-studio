"""M8c: plan/mesh.removed -- the material a tag removes from the body under
it, per slab: Send to PrusaSlicer's negative volumes (scene/print3d.py).

On the golden cases (every 5th, legacy and matrix) with a body:
* what is removed lies inside the body's loops and its z;
* it overlaps no body, white or pattern that remains in the same slab, so
  a negative volume never cuts a colour;
* its prisms are closed (every directed edge once, its reverse once).
And by hand: an inset black (recess = pattern) removes nothing; a
New-body tile's pins leave their sockets' clearance.
"""
from __future__ import annotations

from collections import Counter

import pytest

import _evaluate_golden as G
from aruco_studio.plan import mesh as ME
from aruco_studio.plan import plan_tag
from aruco_studio.plan import region as RG
from aruco_studio.plan import target as T
from aruco_studio.plan.spec import TagSpec

CASES = [c for c in (G.cases("legacy") + G.cases("matrix"))[::5] if "error" not in c["out"]]


def _overlap(a, b):
    return a[0] < b[1] - 1e-9 and b[0] < a[1] - 1e-9


def _area_and(pa, pb):
    t = RG.boolean([pa, pb], lambda f: f[0] and f[1])
    return sum(x.area for x in t)


def _check(p):
    d = p.data
    rem = ME.removed(d)
    if not d.get("body"):
        return ["a removal without a body"] if rem else []
    bad = []
    body0 = [d["body"]["loops"]]
    kept = ME.bodies(d)
    for r in rem:
        a = sum(x.area for x in r["_traps"])
        if abs(_area_and(r["polygons"], body0) - a) > 1e-6 * max(1.0, a):
            bad.append(("outside the body", r["z"]))
        if not (d["body"]["z"][0] - 1e-9 <= r["z"][0] and r["z"][1] <= d["body"]["z"][1] + 1e-9):
            bad.append(("outside the body's z", r["z"]))
        for b in kept:
            if _overlap(r["z"], b["z"]) and _area_and(r["polygons"], b["polygons"]) > 1e-9:
                bad.append((f"overlaps {b['what']}", r["z"], b["z"]))
    for m in ME.removed_mesh(d):
        tris = [m["indices"][i:i + 3] for i in range(0, len(m["indices"]), 3)]
        e = Counter((t[k], t[(k + 1) % 3]) for t in tris for k in range(3))
        if not all(n == 1 and e.get((b, a)) == 1 for (a, b), n in e.items()):
            bad.append(("not closed", m["z"]))
    return bad


@pytest.mark.parametrize("chunk", range(4))
def test_removed_is_inside_the_body_and_cuts_no_colour(chunk):
    bad = []
    n = 0
    for c in CASES[chunk::4]:
        p = plan_tag(TagSpec.from_dict(c["in"]))
        if not p.ok:
            continue
        n += 1
        b = _check(p)
        if b:
            bad.append((c["id"], b[:2]))
    assert n and not bad, bad[:3]


def _box_tag(settings):
    t = T.box(60.0, 40.0, 5.0)
    s = {"layout": "single", "dictionary": "DICT_4X4_50"}
    s.update(settings)
    return plan_tag(TagSpec(target=t, settings=s, numbers={}, name="t", key="t"))


def test_an_inset_black_removes_nothing_new_body_pins_leave_sockets():
    inset = _box_tag({"mode": "black", "op": "join"})
    assert inset.ok and ME.removed(inset.data) == []
    pins = _box_tag({"mode": "both", "op": "new", "pin": "triangle"})
    assert pins.ok
    rem = ME.removed(pins.data)
    assert rem and not _check(pins)
    assert min(r["z"][0] for r in rem) < -1.0          # the sockets go into the body
    assert ME.removed({"layers": [], "combines": [], "parts": [], "body": None}) == []
