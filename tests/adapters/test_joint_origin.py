"""adapters/fusion/joint_origin.py on the stand-in (PLAN M4.5).

* 200 random frames: core.geometry.jo_decompose's three numbers -> the
  stand-in's Joint Origin (Fusion's measured composition, written there
  independently) -> read back: 1e-6 mm and 1e-6 degree;
* when Fusion composes differently (the stand-in switched to the old,
  wrong convention) the read-back fallback still lands it;
* ONE Joint Origin per tag after REF test_aruco_jo_one_per_tag's 12-edit
  run, also when an old Joint Origin refuses deleteMe() (a joint uses it),
  and with two tags in one component;
* every probe and every Joint Origin a failed call made is gone.
"""
from __future__ import annotations

import math
import random
import types

import pytest

import fake_adsk as FK
from aruco_studio.adapters.fusion import feature as FT
from aruco_studio.adapters.fusion import joint_origin as JO
from aruco_studio.core import geometry as G
from aruco_studio.core import settings as S


def _unit(v):
    n = math.sqrt(sum(c * c for c in v))
    return [c / n for c in v]


def _rand_frame(rnd):
    x = _unit([rnd.gauss(0, 1) for _ in range(3)])
    t = _unit([rnd.gauss(0, 1) for _ in range(3)])
    z = _unit(G._cross(x, t))
    y = G._cross(z, x)
    o = [rnd.uniform(-20, 20) for _ in range(3)]
    return o, x, y, z


def _err(a, b):
    """(mm, degrees) between two frames (cm); the angle by atan2, which
    keeps its precision near 0 (acos does not: ~1e-6 degree of noise)."""
    d = G._sub(a[0], b[0])
    pos = math.sqrt(G._dot(d, d)) * 10.0
    ang = 0.0
    for i in (1, 2, 3):
        c = G._cross(a[i], b[i])
        ang = max(ang, math.degrees(math.atan2(math.sqrt(G._dot(c, c)), G._dot(a[i], b[i]))))
    return pos, ang


def _face(frame):
    """A planar face as the stand-in's JointGeometry reads it: its frame."""
    return types.SimpleNamespace(frame=frame, name="face")


def _target_on(base, rnd):
    """A frame a Joint Origin on `base` can be: turned about its z, maybe
    flipped (half a turn about the new x), offset anywhere (cm)."""
    o, x, y, z = base
    a = rnd.uniform(-math.pi, math.pi)
    x1 = [math.cos(a) * x[i] + math.sin(a) * y[i] for i in range(3)]
    y1 = G._cross(z, x1)
    z1 = list(z)
    if rnd.random() < 0.5:
        y1, z1 = [-c for c in y1], [-c for c in z1]
    o1 = [o[i] + rnd.uniform(-8, 8) for i in range(3)]
    return o1, x1, y1, z1


@pytest.mark.parametrize("convention", ["measured", "flipped_z"])
def test_200_random_frames_read_back(convention):
    FK.JointOrigin.CONVENTION = convention
    try:
        rnd = random.Random(20261016)
        comp = FK.design().rootComponent
        worst = [0.0, 0.0]
        for k in range(200):
            base = _rand_frame(rnd)
            target = _target_on(base, rnd)
            out = JO.ensure(comp, f"k{k}", FK.JointGeometry.createByPlanarFace(_face(base), None, 0),
                            target)
            jo = JO.find(comp, f"k{k}", out["token"])
            pos, ang = _err(JO.frame_of(jo), target)
            worst = [max(worst[0], pos), max(worst[1], ang)]
        assert worst[0] < 1e-6 and worst[1] < 1e-6, worst
        assert comp.jointOrigins.count == 200          # every probe deleted
    finally:
        FK.JointOrigin.CONVENTION = "measured"


def test_the_first_solve_is_core_geometrys():
    rnd = random.Random(7)
    comp = FK.design().rootComponent
    for _k in range(20):
        base = _rand_frame(rnd)
        target = _target_on(base, rnd)
        geo = FK.JointGeometry.createByPlanarFace(_face(base), None, 0)
        FK.LOG.clear()
        jo, err, params = JO.place(comp, geo, target)
        assert sum(1 for x in FK.LOG if x.startswith("jointOrigins.add")) == 2   # probe + it
        assert params == G.jo_decompose(JO.probe(comp, geo), target)
        JO.delete_quietly(jo)


def test_on_the_frame_sketch_no_angle_no_offset():
    rnd = random.Random(3)
    comp = FK.design().rootComponent
    for k in range(50):
        target = _rand_frame(rnd)
        sk = comp.sketches.add(comp.xYConstructionPlane)
        o, x, _y, z = target
        lx = sk.sketchCurves.sketchLines.addByTwoPoints(
            FK.Point3D(*o), FK.Point3D(*[o[i] + 0.5 * x[i] for i in range(3)]))
        sk.sketchCurves.sketchLines.addByTwoPoints(
            lx.startSketchPoint, FK.Point3D(*[o[i] + 0.5 * z[i] for i in range(3)]))
        out = JO.ensure(comp, f"s{k}", None, target, sketch=sk)
        assert out["how"] == "point_axes"
        jo = JO.find(comp, f"s{k}", out["token"])
        assert jo.angle == 0.0 and jo.offsets == (0.0, 0.0, 0.0) and not jo.isFlipped
        pos, ang = _err(JO.frame_of(jo), target)
        assert pos < 1e-6 and ang < 1e-6


EDITS = [({}, {"size": 25.0}), ({"turn": 90}, {}), ({}, {"size": 0.0}),
         ({"turn": 180}, {}), ({"corner_mark": "triangle"}, {}), ({}, {"marker_id": 3.0}),
         ({"dictionary": "DICT_5X5_100"}, {}), ({"turn": 0}, {}), ({}, {"size": 20.0}),
         ({"quiet_modules": 1.5}, {}), ({"turn": 270}, {}), ({}, {"size": 0.0})]


def _tag(key, at=(0.0, 0.0), w=6.0):
    _body, face = FK.plate(w_cm=w, at=at)
    s = {"layout": "single", "dictionary": "DICT_4X4_50", "mode": "both", "op": "join"}
    return FT.create(face, s, S.default_numbers("both"), key=key)


def _jo_names(comp):
    return sorted(j.name for j in comp.jointOrigins)


def test_one_joint_origin_per_tag_through_12_edits():
    FT.register()
    out = _tag("t1")
    comp = FK.design().rootComponent
    cf = out["node"]
    for i, (s, n) in enumerate(EDITS):
        res = FT.edit(cf, dict(s), dict(n))
        cf = res["node"]
        assert _jo_names(comp) == ["aruco t1"], (i, _jo_names(comp))
        rec = res["record"]
        if rec is not None:
            jo = JO.find(comp, "t1", rec["fusion"].get("joint_origin"))
            want = tuple(tuple(v) for v in FT.RC.recipe(
                FT.plan_for(cf.dependencies.itemById("target").entity, FT.REC.settings_of(cf),
                            FT.REC.numbers_of(cf), "t1")[0],
                FT.plan_for(cf.dependencies.itemById("target").entity, FT.REC.settings_of(cf),
                            FT.REC.numbers_of(cf), "t1")[2][:4])["frames"]["opencv_cm"])
            pos, ang = _err(JO.frame_of(jo), want)
            assert pos < 1e-6 and ang < 1e-6, (i, pos, ang)


def test_a_joint_origin_that_refuses_to_go_stays_the_only_one():
    FT.register()
    out = _tag("t1")
    comp = FK.design().rootComponent
    cf = out["node"]
    held = JO.find(comp, "t1")
    held.refuse_delete = True                     # a joint uses it
    for s, n in EDITS[:6]:
        res = FT.edit(cf, dict(s), dict(n))
        cf = res["node"]
        assert _jo_names(comp) == ["aruco t1"]
        assert JO.find(comp, "t1") is held
        if res["record"] is not None:
            assert "could not be deleted" in res["record"]["fusion"]["joint_origin_problem"]


def test_two_tags_in_one_component_keep_one_each():
    FT.register()
    a = _tag("ta", at=(0.0, 0.0))
    b = _tag("tb", at=(10.0, 0.0))
    comp = FK.design().rootComponent
    cfs = {"ta": a["node"], "tb": b["node"]}
    for i, (s, n) in enumerate(EDITS[:8]):
        k = "ta" if i % 2 == 0 else "tb"
        cfs[k] = FT.edit(cfs[k], dict(s), dict(n))["node"]
        assert _jo_names(comp) == ["aruco ta", "aruco tb"], i


def test_a_failed_placement_leaves_no_joint_origin():
    comp = FK.design().rootComponent
    base = _rand_frame(random.Random(1))
    bad = (["nan", 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1])
    with pytest.raises(Exception):
        JO.ensure(comp, "x", FK.JointGeometry.createByPlanarFace(_face(base), None, 0), bad)
    assert comp.jointOrigins.count == 0
