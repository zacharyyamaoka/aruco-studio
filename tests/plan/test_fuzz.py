"""M2.3: plan_tag never raises. 2,000 random TagSpecs, every field of
ARCHITECTURE 5.6 driven in and out of range; every refusal (ok false) has
an `errors` entry AND an `error` Issue whose field is a 5.6 key path."""
from __future__ import annotations

import random

import pytest

from aruco_studio.plan import plan_tag
from aruco_studio.plan.fields import fields
from aruco_studio.plan import target as T

PATHS = {r["path"] for r in fields()}
N, CHUNKS = 2000, 8


def _rnd_target(r):
    k = r.random()
    if k < 0.35 * (1 - BAD) + BAD * 0:
        t = T.box(_pick(r, [4.0, 8.0, 25.0, 40.0, 60.0, 100.0, 150.0], [0.0, -10.0]),
                  r.choice([4.0, 20.0, 40.0, 60.0, 90.0]), r.choice([0.0, 3.0, 5.0]),
                  kind=r.choice(["face", "profile", "free"]))
    elif k < 0.55:
        t = T.disc(r.choice([3.0, 15.0, 26.5, 40.0]),
                   r.choice([(), ((20.0, 0.0, 2.0),), ((0.0, 0.0, 6.0),)]),
                   r.choice([0.0, 3.0]))
    elif k < 0.8:
        t = T.from_face(r.choice(["disc4", "dshape", "lshape", "plate_hole", "ring", "hexagon",
                                  "stadium", "notch", "strip", "triangle", "box40", "disc40"]),
                        r.choice([0.0, 4.0]))
    elif k < 1.0 - BAD:
        t = T.box(r.choice([40.0, 60.0, 100.0]), r.choice([40.0, 60.0]), r.choice([0.0, 3.0]))
    else:
        t = T.box(60, 40, 3)
        bad = r.choice(["loops2", "hole_out", "body", "kind", "zsign"])
        if bad == "loops2":
            t.loops_mm = [[(0.0, 0.0), (1.0, 1.0)]]
        elif bad == "hole_out":
            t.loops_mm = [T.box_loop() if hasattr(T, "box_loop") else
                          [(-30.0, -20.0), (30.0, -20.0), (30.0, 20.0), (-30.0, 20.0)],
                          [(40.0, 40.0), (41.0, 40.0), (41.0, 41.0)]]
        elif bad == "body":
            t.body_mm = {"u0": -1.0, "v0": -1.0, "u1": 1.0, "v1": 1.0, "z0": 0.0, "z1": -1.0,
                         "measured": True}
        elif bad == "kind":
            t.kind = "cloud"
        else:
            t.z_sign = 3
    return t.to_dict()


BAD = 0.06          # each field out of range this often


def _pick(r, good, bad):
    return r.choice(bad) if bad and r.random() < BAD else r.choice(good)


def _rnd_spec(r):
    s = {"layout": _pick(r, ["single", "grid", "charuco"], ["hexagon"]),
         "dictionary": _pick(r, ["DICT_4X4_50", "DICT_5X5_100", "dict_6x6_250",
                                 "DICT_APRILTAG_36h11"], ["DICT_NOPE"]),
         "mode": _pick(r, ["both", "black", "white", "auto"], ["purple"]),
         "op": _pick(r, ["join", "new"], ["glue"]),
         "quiet_modules": _pick(r, [1.0, 0.5, 2.0, 1.0], [0.0, 4.0, -1.0]),
         "turn": _pick(r, [0, 90, 180, 270], [45, 360]),
         "corner_mark": _pick(r, ["none", "cut", "triangle"], ["star"]),
         "pin": _pick(r, ["none", "triangle", "round"], ["hexagon"]),
         "grow": r.random() < 0.2}
    if r.random() < 0.3:
        s["cells"] = r.choice([{"rule": 1, "of": "cell", "mm": 0.68, "min_mm": 2.0},
                               {"rule": 1, "of": "marker", "mm": 0.5}, {"rule": 4},
                               {"rule": 1, "of": "cell", "mm": 90.0}])
    if r.random() < 0.4:
        s["label"] = {"on": True, "place": r.choice(["auto", "black", "white", "moon"]),
                      "side": r.choice(["auto", "below", "left", "inside"]),
                      "cap_mm": r.choice([0.0, 2.5, -1.0, 9.0]),
                      "content": r.choice(["id", "id_name", "custom", "poem"]),
                      "text": r.choice(["", "{key}|{dict}", "HELLO"]),
                      "rule": r.choice([1, 2, 7]), "build_anyway": r.random() < 0.3}
    if r.random() < 0.3:
        s["trim"] = r.choice([{"rule": 1, "axes": "both", "margin_mm": 1.0},
                              {"rule": 1, "axes": "x", "force": True}, {"rule": 2},
                              {"rule": 1, "axes": "both", "margin_mm": 99.0}])
    if r.random() < 0.15:
        s["force"] = r.choice([[3, 2], [0, 2], [1, 1], [2, 2]])
    if r.random() < 0.1:
        s["chamfer"] = True
        s.pop("corner_mark")
    if r.random() < 0.1:
        s["origin_v"] = r.choice([2, 1])
    n = {}
    for k, good, bad in (("marker_id", [0, 3, 12], [49, 60, 999, -1]),
                         ("size", [0.0, 0.0, 6.0, 20.0, 45.0], [-2.0, 400.0]),
                         ("square", [0.0, 9.0, 30.0], [-1.0]),
                         ("white_height", [2.0, -0.6, 1.0], [0.0, 0.05, 70.0]),
                         ("black_height", [-0.6, 0.6, -0.4], [0.0, 0.01, -60.0]),
                         ("white_offset", [0.0, -1.0], [60.0]), ("black_offset", [2.0, 0.0], [-70.0]),
                         ("pin_size", [3.0, 2.0], [0.1, 15.0, 25.0]),
                         ("pin_length", [2.0, 3.0], [0.1, 30.0]), ("pin_tol", [0.15, 0.0], [2.0])):
        if r.random() < 0.5:
            n[k] = _pick(r, good, bad)
    if r.random() < 0.05:
        n.update(height=r.choice([2.0, 0.0]), thickness=0.6, above=0.0)
    return {"schema": "arucostudio.tagspec/1", "settings": s, "numbers": n,
            "target": _rnd_target(r), "name": r.choice(["", "Arm", "Gripper:2"]),
            "key": r.choice(["", "k", "tg"])}


@pytest.mark.parametrize("chunk", range(CHUNKS))
def test_fuzz_never_raises_and_refusals_say_where(chunk):
    r = random.Random(1016 + chunk)
    seen = {"ok": 0, "refused": 0}
    for _ in range(N // CHUNKS):
        d = _rnd_spec(r)
        p = plan_tag(d)                       # must not raise
        data = p.data
        assert data["schema"] == "arucostudio.tagplan/1"
        if data["ok"]:
            seen["ok"] += 1
            continue
        seen["refused"] += 1
        assert data["errors"], d
        errs = [w for w in data["warnings"] if w["level"] == "error"]
        assert errs, (d, data["warnings"])
        assert any(w["field"] in PATHS for w in errs), (d, errs)
    assert seen["ok"] > 20 and seen["refused"] > 20, seen
