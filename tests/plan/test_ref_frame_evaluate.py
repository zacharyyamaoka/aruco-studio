"""REF tests/test_aruco_frame.py, its evaluate() sections (EX-ORIGIN-3,
EX-MIGRATE-2), on plan.evaluate / plan_tag; and REF tests/test_aruco_disc_fit.py.

REF ran evaluate() on a sketch area whose frame sits at (1, 2, 0.5) cm,
turned 30 deg; here that frame is the `base` the plan is given, and the
Joint Origin REF's ensure_joint_origin targets is plan/record.optical_frame_cm.
"""
from __future__ import annotations

import json
import math

import pytest

from aruco_studio.core import markers as AM
from aruco_studio.core import origin as OR
from aruco_studio.core import settings as F
from aruco_studio.plan import evaluate as EV
from aruco_studio.plan import plan_tag
from aruco_studio.plan import record as R
from aruco_studio.plan import target as T
from aruco_studio.plan.spec import TagSpec

SUITE = "tests/test_aruco_frame.py"
A30 = math.radians(30.0)
O = [1.0, 2.0, 0.5]
XB = [math.cos(A30), math.sin(A30), 0.0]
YB = [-math.sin(A30), math.cos(A30), 0.0]
ZB = [0.0, 0.0, 1.0]
CORNER_SIGNS = {"top_left": (-1, 1), "top_right": (1, 1), "bottom_left": (-1, -1),
                "bottom_right": (1, -1), "centre": (0, 0)}


def mm(a, b):
    return max(abs(p - q) for p, q in zip(a, b))


def dot(a, b):
    return sum(p * q for p, q in zip(a, b))


def cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def hand_frame(origin, x, y, z, extent_m, raise_m, corner, zdir, scale=100.0):
    sx, sy = CORNER_SIGNS[corner]
    w, h = extent_m
    o = [origin[i] + (x[i] * sx * w / 2 + y[i] * sy * h / 2 + z[i] * raise_m) * scale
         for i in range(3)]
    s = 1.0 if zdir == "out" else -1.0
    return o, list(x), [c * s for c in y], [c * s for c in z]


def hand_opencv(origin, x, y, z, spec, scale=100.0):
    if spec.layout == "single":
        return hand_frame(origin, x, y, z, spec.extent_m, spec.raise_m, "centre", "out", scale)
    return hand_frame(origin, x, y, z, spec.extent_m, spec.raise_m, "top_left", "in", scale)


def evaluate(layout, mode, op, w_mm, h_mm, turn, numbers=None, force=None, legacy=False,
             rule=None, extra=None):
    t = T.box(w_mm, h_mm, kind="profile")
    t.has_body = op == "join"
    s = F.default_settings()
    s.update(mode=mode, op=op, layout=layout, turn=turn, has_body=(op == "join"),
             source="profile", force=list(force) if force else None, legacy=legacy,
             origin_v=OR.ORIGIN_RULE if rule is None else rule)
    if rule == "old":
        s.pop("origin_v")
    s.update(extra or {})
    n = F.default_numbers(mode)
    n.update(numbers or {})
    return EV.evaluate(t, s, n, base=(O, XB, YB, ZB, w_mm / 10.0, h_mm / 10.0))


CASES = (("single", 40.0, 40.0, {"size": 28.0}, None),
         ("grid", 40.0, 40.0, {"size": 14.0}, (2, 2)),
         ("grid", 60.0, 40.0, {"size": 14.0}, (3, 2)),
         ("charuco", 60.0, 60.0, {"size": 13.5, "square": 18.0}, (3, 3)),
         ("charuco", 110.0, 60.0, {"size": 18.75, "square": 25.0}, (4, 2)),
         ("charuco", 100.0, 80.0, {"size": 13.5, "square": 18.0}, (5, 4)))
MODES = (("black", "join", {}), ("both", "new", {}),
         ("black", "join", {"black_offset": 0.0, "black_height": 0.6}))


@pytest.mark.ref(SUITE, "== the add-in: evaluate() x every Origin -> the Joint Origin IS "
                 "OpenCV's frame")
def test_every_origin_the_joint_origin_is_opencvs_frame():
    n_cases = 0
    for layout, wmm, hmm, size, force in CASES:
        for legacy in ((False, True) if layout == "charuco" and force == (5, 4) else (False,)):
            for mode, op, heights in MODES:
                nums = dict(size, **heights)
                ev0 = evaluate(layout, mode, op, wmm, hmm, 0, nums, force, legacy)
                sp0 = ev0["spec"]
                for turn in OR.TURNS_CW:
                    ev = evaluate(layout, mode, op, wmm, hmm, turn, nums, force, legacy)
                    n_cases += 1
                    c, x, y, zt = ev["tag"]
                    sp = ev["spec"]
                    tt = math.radians(turn)
                    xt = [math.cos(tt) * XB[i] + math.sin(tt) * YB[i] for i in range(3)]
                    yt = cross(ZB, xt)
                    rec = AM.TagDef(key="k", component="", spec=sp, origin=list(c),
                                    x_axis=list(x), y_axis=list(y), z_axis=list(zt)).to_dict()
                    tag = AM.TagDef.from_dict(json.loads(json.dumps(rec)), print)
                    jo = R.optical_frame_cm(tag)
                    want = hand_opencv(c, xt, yt, ZB, sp)
                    W, H = (v * 1000.0 for v in sp0.extent_m)
                    (ou, ov), xd, yd, zs = OR.opencv_in_layout(layout, turn, W, H)
                    lift = sp.raise_m * 100.0
                    named = ([c[i] + (XB[i] * ou + YB[i] * ov) / 10.0 + ZB[i] * lift
                              for i in range(3)],
                             [XB[i] * xd[0] + YB[i] * xd[1] for i in range(3)],
                             [XB[i] * yd[0] + YB[i] * yd[1] for i in range(3)],
                             [ZB[i] * zs for i in range(3)])
                    assert mm(x, xt) < 1e-12 and mm(zt, ZB) < 1e-12
                    assert (sp.cols, sp.rows) == OR.built(layout, turn, sp0.cols, sp0.rows)
                    assert sp.ids == sp0.ids
                    assert all(mm(a, b) < 1e-12 for a, b in zip(jo, want))
                    assert all(mm(a, b) < 1e-12 for a, b in zip(jo, named))
                    assert all(mm(a, b) < 1e-15 for a, b in zip(R.optical_of_ev(ev, ""), jo))
                    assert abs(dot(cross(jo[1], jo[2]), jo[3]) - 1.0) < 1e-12
                    assert not {"frame", "frame_offset"} & set(rec)
                    tw, th = (v * 1000.0 for v in sp.tile_size_m)
                    if turn % 180:
                        tw, th = th, tw
                    tw0, th0 = (v * 1000.0 for v in sp0.tile_size_m)
                    assert abs(tw - tw0) < 1e-9 and abs(th - th0) < 1e-9
    assert n_cases >= 84


def test_the_tagplan_frame_is_the_joint_origin_in_mm():
    """TagPlan.frames.opencv_target is optical_frame_cm in the target's mm."""
    for layout, wmm, hmm, size, force in CASES:
        for turn in OR.TURNS_CW:
            t = T.box(wmm, hmm, kind="profile")
            spec = TagSpec(settings={"layout": layout, "mode": "black", "op": "join",
                                     "turn": turn, "force": list(force) if force else None,
                                     "origin_v": 2},
                           numbers=dict(size), target=t, key="k")
            p = plan_tag(spec)
            assert p.ok, p.data["errors"]
            o, x, y, z = R.optical_of_ev(p.ev, "k")
            m = p.data["frames"]["opencv_target"]
            assert mm([m[3], m[7], m[11]], [v * 10.0 for v in o]) < 1e-6
            assert mm([m[0], m[4], m[8]], x) < 1e-9 and mm([m[2], m[6], m[10]], z) < 1e-9


@pytest.mark.ref(SUITE, "== a node made before 2026-10-09 keeps its orientation (no origin_v)")
def test_an_old_node_keeps_its_orientation():
    ev = evaluate("grid", "black", "join", 60.0, 40.0, 90, {"size": 14.0}, (3, 2), rule="old")
    note = next((t for t in ev["notes"] if t.startswith("origin ")), None)
    assert ev["turn"] == 0 and (ev["spec"].cols, ev["spec"].rows) == (3, 2) and note \
        and F.is_info(note)
    assert evaluate("grid", "black", "join", 40.0, 40.0, 90, {"size": 14.0}, (2, 2),
                    rule="old")["turn"] == 90
    assert evaluate("single", "black", "join", 40.0, 40.0, 270, {"size": 28.0},
                    rule="old")["turn"] == 270
    assert "origin_v" not in F.default_settings() and OR.ORIGIN_RULE == 2
    # the plan says so on the Origin's field, as info
    spec = TagSpec(settings={"layout": "grid", "mode": "black", "turn": 90, "force": [3, 2]},
                   numbers={"size": 14.0}, target=T.box(60, 40, kind="profile"))
    p = plan_tag(spec)
    assert p.data["rules"]["origin"] is None
    assert any(w["field"] == "settings.turn" and w["level"] == "info"
               and w["text"].startswith("origin ") for w in p.data["warnings"])


@pytest.mark.ref(SUITE, "== the removed Frame: settings and records that still carry one")
def test_the_removed_frame():
    s_old = dict(F.default_settings(), frame={"corner": "top_left", "z": "out"}, chamfer=True)
    s = F.normalise(s_old)
    assert "frame" not in s and "chamfer" not in s and s["corner_mark"] == "cut"
    assert F.normalise({"chamfer": True, "corner_mark": "triangle"})["corner_mark"] == "triangle"
    assert F.normalise({"chamfer": False})["corner_mark"] == "none"
    assert F.normalise({"chamfer": True}, partial=True) == {"corner_mark": "cut"}
    ev = evaluate("charuco", "black", "join", 110.0, 60.0, 0, {"size": 18.75, "square": 25.0},
                  (4, 2), extra={"frame": {"corner": "top_left", "z": "out"}})
    tag = AM.TagDef(key="k", component="", spec=ev["spec"], origin=list(ev["tag"][0]),
                    x_axis=list(ev["tag"][1]), y_axis=list(ev["tag"][2]),
                    z_axis=list(ev["tag"][3]))
    assert "frame" not in ev and R.optical_of_ev(ev, "") == R.optical_frame_cm(tag)
    rec = dict(tag.to_dict(), frame={"corner": "top_left", "z": "out"},
               frame_offset=[1.0, 0, 0, 0, 0, -1.0, 0, 0, 0, 0, -1.0, 0, 0, 0, 0, 1.0])
    assert not R.record_same(rec, ev)
    w = []
    back = AM.TagDef.from_dict(rec, w.append)
    assert back.record_optical() == tag.record_optical() and w \
        and "Frame chosen on 2026-10-08" in w[0] and "frame" not in back.to_dict()


# ----------------------------------------------------- REF test_aruco_disc_fit

HOLES = [(23.75, 0, 1.425), (-23.75, 0, 1.425), (0, 23.75, 1.425), (0, -23.75, 1.425)]


def _disc(radius_mm, holes, size):
    loops = [T.circle_pts(0, 0, radius_mm, 96)] + [T.circle_pts(hx, hy, hr, 24, cw=True)
                                                   for hx, hy, hr in holes]
    t = T.Target(kind="face", w_mm=2 * radius_mm, h_mm=2 * radius_mm, loops_mm=loops)
    spec = TagSpec(settings={"layout": "single", "mode": "black"},
                   numbers={"size": size, "marker_id": 0, "black_height": -1.0}, target=t,
                   key="gim")
    p = plan_tag(spec)
    assert p.ok, p.data["errors"]
    return round(p.ev["spec"].marker_length_m * 1000.0, 3), p.data["notes"]


@pytest.mark.ref("tests/test_aruco_disc_fit.py", "== the GIM43 discs")
def test_disc_fit__the_gim43_discs():
    """ST-T-SIZE-1: an unchanged tag never changes size by itself."""
    m, notes = _disc(23.75, [], 28.0)
    assert m == 25.0 and any("clamped: 28.0 mm does not fit" in t for t in notes), (m, notes)
    m, notes = _disc(23.75, [], 0.0)
    assert m == 25.0
    m, notes = _disc(26.5, HOLES, 28.0)
    assert m == 28.0 and not any("clamped" in t for t in notes)
    m, notes = _disc(26.5, HOLES, 0.0)
    assert m == 28.0
