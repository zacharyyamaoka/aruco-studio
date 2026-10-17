"""M6a: a printed sticker's plan (manufacturing_intent.md 3, M6 note d).

| Check | Here |
|---|---|
| M6.1 | legacy = 3D: plan_tag(spec) equals plan_tag(spec + make print3d) but for rules.make, on all 824 goldens |
| M6.2 | a sticker: parts sticker / ink, the layers' z, the frame on the ink top, the twin's ids, the ink's top view equal to the 3D twin's pattern pixel for pixel at 20 px / mm (every layout x 4 turns x 3 marks x label off / on) |
| M6.3 | OpenCV reads every case of M6.2; PnP within 0.1 mm / 0.1 deg |
| M6.4 | junk make plans as 3D / clamped with a warn; plan_tag never raises (2,000 specs) |
| M6a.4 | Perimeter: Marker a rectangle, Profile the loops with every hole, the sticker layer = cut_line; the no-white label rule; margin 6 builds on the white |
| M6a.10 | a 96-point disc with 3 holes plans under 50 ms |
| ST-T-TARGET-1 | the loop checks; CHORD_MM; loops normalised |
"""
from __future__ import annotations

import copy
import json
import math
import random
import time

import numpy as np
import pytest

import _evaluate_golden as G
from aruco_studio.core import faces as FA
from aruco_studio.core import make as MK
from aruco_studio.plan import plan_tag
from aruco_studio.plan import target as T
from aruco_studio.plan.spec import TagSpec

STK = {"rule": 1, "by": "sticker"}
CASES = G.cases("legacy") + G.cases("matrix")
CHUNKS = 16


# ------------------------------------------------------------ M6.1

@pytest.mark.parametrize("chunk", range(CHUNKS))
def test_legacy_is_3d_both_ways(chunk):
    bad = []
    for c in CASES[chunk::CHUNKS]:
        spec = TagSpec.from_dict(c["in"])
        a = plan_tag(spec).to_dict()
        sp = copy.deepcopy(spec)
        sp.settings["make"] = {"rule": 1, "by": "print3d"}
        b = plan_tag(sp).to_dict()
        if not a["ok"]:
            if a != dict(b, rules=a["rules"]):
                bad.append((c["id"], "refused differs"))
            continue
        assert a["rules"]["make"] is None and b["rules"]["make"] == 1
        assert a["made_by"] == b["made_by"] == "print3d"
        b["rules"]["make"] = None
        if a != b:
            bad.append(c["id"])
    assert not bad, bad[:5]


# ------------------------------------------------------------ M6.2 / M6.3

LAB = {"on": True, "rule": 3, "place": "black", "content": "id", "nozzle_mm": 0.2}
TARGETS = {"single": (60, 60), "grid": (90, 70), "charuco": (90, 70)}
M62 = [(lay, turn, mark, lab) for lay in ("single", "grid", "charuco")
       for turn in (0, 90, 180, 270) for mark in ("none", "cut", "triangle")
       for lab in (False, True)]


def _pair(lay, turn, mark, lab):
    s = {"layout": lay, "mode": "both", "op": "new", "turn": turn, "origin_v": 2,
         "corner_mark": mark}
    if lab:
        s["label"] = dict(LAB)
    t = T.box(*TARGETS[lay], 0).to_dict()
    twin = plan_tag({"settings": s, "target": t})
    stk = plan_tag({"settings": dict(s, make=dict(STK)), "target": t})
    return twin, stk


def _black(plan, grid):
    from aruco_studio.verify.render import top_view
    return top_view(plan, px_per_mm=20.0, ss=1, grid=grid).img < 128


@pytest.mark.parametrize("lay,turn,mark,lab", M62,
                         ids=[f"{a}-{b}-{c}-{'lab' if d else 'nolab'}" for a, b, c, d in M62])
def test_a_sticker_plans_as_its_3d_twin_on_a_thin_stock(lay, turn, mark, lab):
    twin, stk = _pair(lay, turn, mark, lab)
    assert twin.ok and stk.ok, (twin.data["errors"], stk.data["errors"])
    d = stk.data
    assert d["made_by"] == "sticker" and d["parts"] == ["sticker", "ink"]
    assert d["rules"]["make"] == 1
    zs = {L["part"]: L["z"] for L in d["layers"] if L["step"] == "add"}
    assert zs["sticker"] == [0.0, 0.1] and zs["ink"] == [0.1, 0.11]
    assert d["frames"]["detector_z_mm"] == pytest.approx(0.11)
    assert d["frames"]["surface_mm"] == pytest.approx(0.11)
    assert d["marker"]["depth_m"] == pytest.approx(1e-5) and not d["marker"].get("raise_m")
    assert d["combines"] == [{"part": "sticker", "op": "new", "into": None},
                             {"part": "ink", "op": "new", "into": None}]
    assert d["record"]["fusion"]["make"]["by"] == "sticker"
    assert "make" not in (twin.data["record"]["fusion"] or {})
    assert d["ids"] == twin.data["ids"]
    assert d["writes"]["settings"]["parts"] == ["sticker", "ink"]
    # the ink seen from above = the twin's pattern seen from above
    u0, v0, u1, v1 = twin.data["guides"]["sticker"]
    grid = (u0 - 3.0, v1 + 3.0, int((u1 - u0 + 6.0) * 20), int((v1 - v0 + 6.0) * 20))
    a, b = _black(twin.data, grid), _black(stk.data, grid)
    assert int(np.count_nonzero(a ^ b)) == 0, int(np.count_nonzero(a ^ b))
    if lab:
        assert d["label"]["kind"] == twin.data["label"]["kind"] == "black"


@pytest.mark.parametrize("lay,turn,mark,lab", M62,
                         ids=[f"{a}-{b}-{c}-{'lab' if d else 'nolab'}" for a, b, c, d in M62])
def test_opencv_reads_every_sticker_and_its_frame(lay, turn, mark, lab):
    from aruco_studio.verify.report import verify_plan
    _twin, stk = _pair(lay, turn, mark, lab)
    rep = verify_plan(stk, px_per_mm=20.0, pose=True)
    assert rep["ok"], {k: rep.get(k) for k in ("missing", "extra", "pnp_err_mm", "pnp_err_deg")}
    assert rep["pnp_err_mm"] <= 0.1 and rep["pnp_err_deg"] <= 0.1


# ------------------------------------------------------------ M6.4

@pytest.mark.parametrize("make,field", [({"rule": 9, "by": "sticker"}, "settings.make"),
                                        ({"rule": 1, "by": "laser"}, "settings.make.by")])
def test_junk_make_plans_as_3d_with_a_warn(make, field):
    t = T.box(40, 40, 0).to_dict()
    p = plan_tag({"settings": {"layout": "single", "make": make}, "target": t})
    base = plan_tag({"settings": {"layout": "single"}, "target": t})
    assert p.ok and p.data["made_by"] == "print3d" and p.data["parts"] == base.data["parts"]
    assert any(w["field"] == field and w["level"] == "warn" for w in p.data["warnings"])


def test_a_thickness_out_of_range_is_clamped():
    p = plan_tag({"settings": {"layout": "single", "make": dict(STK, thickness_mm=-1.0)},
                  "target": T.box(40, 40, 0).to_dict()})
    assert p.ok and p.data["made_by"] == "sticker"
    assert p.data["frames"]["detector_z_mm"] == pytest.approx(MK.THICKNESS_MM[0] + MK.INK_MM)
    assert any(w["field"] == "settings.make.thickness_mm" and w["level"] == "warn"
               for w in p.data["warnings"])


def _random_spec(rng):
    junk = [None, {}, "sticker", 3, [1], {"rule": rng.choice([0, 1, 2, "1", None, True])},
            {"rule": 1, "by": rng.choice(["sticker", "print3d", "laser", 7, None])},
            {"rule": 1, "by": "sticker", "thickness_mm": rng.choice([-1, 0, 0.1, 3, "x", None,
                                                                     float("nan")]),
             "margin_mm": rng.choice([-5, 0, 6, 80, "y", None]),
             "perimeter": rng.choice(["marker", "profile", "round", 1]),
             "cut_line": rng.choice([True, False, "no"])}]
    s = {"layout": rng.choice(["single", "grid", "charuco", "hex"]),
         "make": rng.choice(junk), "holes": rng.choice([None, "avoid", "ignore", "maybe", 4]),
         "corner_mark": rng.choice(["none", "cut", "triangle"]),
         "label": rng.choice([None, {"on": True, "place": rng.choice(["black", "white", "auto"]),
                                     "rule": rng.choice([1, 2, 3, 9])}])}
    key = rng.choice([f["key"] for f in FA.PALETTE])
    return {"settings": s, "numbers": {"size": rng.choice([0.0, 0.0, 12.0, 300.0, -1.0])},
            "target": T.from_face(key, rng.choice([0.0, 3.0])).to_dict()}


@pytest.mark.parametrize("chunk", range(10))
def test_plan_tag_never_raises_on_2000_specs_with_make(chunk):
    rng = random.Random(1000 + chunk)
    for _ in range(200):
        sp = _random_spec(rng)
        p = plan_tag(sp)                    # never raises
        json.dumps(p.to_dict(), allow_nan=False)
        if p.ok:
            assert p.data["made_by"] in ("print3d", "sticker")


# ------------------------------------------------------------ M6a.4 perimeter

FACES = [f["key"] for f in FA.PALETTE]


def _sticker(key, per, **kw):
    s = {"layout": "single", "make": dict(STK, perimeter=per, **kw.pop("make", {})), **kw}
    return plan_tag({"settings": s, "target": T.from_face(key).to_dict()})


@pytest.mark.parametrize("key", FACES)
@pytest.mark.parametrize("per", ["marker", "profile"])
@pytest.mark.parametrize("lab", ["off", "black", "white"])
def test_the_perimeter_on_every_palette_face(key, per, lab):
    kw = {}
    if lab != "off":
        kw["label"] = {"on": True, "rule": 3, "place": lab, "content": "id", "nozzle_mm": 0.2}
    p = _sticker(key, per, **kw)
    assert p.ok, p.data["errors"]
    d = p.data
    cut = d["guides"]["cut_line"]
    sticker = [L for L in d["layers"] if L["name"] == "sticker"]
    assert len(sticker) == 1 and len(sticker[0]["polygons"]) == 1
    poly = sticker[0]["polygons"][0]
    if per == "marker":
        u0, v0, u1, v1 = cut["rect"]
        assert cut["kind"] == "marker" and cut["holes"] == []
        assert sorted(map(tuple, cut["outer"])) == sorted([(u0, v0), (u1, v0), (u1, v1),
                                                           (u0, v1)])
        assert cut["rect"] == pytest.approx(d["guides"]["sticker"])        # margin 0
    else:
        tgt = d["guides"]["target"]
        assert cut["kind"] == "profile"
        assert cut["outer"] == tgt[0] and cut["holes"] == tgt[1:]
        assert len(cut["holes"]) == len(T.from_face(key).loops_mm) - 1
    assert poly["outer"] == cut["outer"] or sorted(map(tuple, poly["outer"])) == \
        sorted(map(tuple, cut["outer"]))
    assert len(poly["holes"]) == len(cut["holes"])
    w = [x for x in d["warnings"] if x["field"] == "settings.label.place"]
    if lab == "white" and per == "marker":
        assert w and w[0]["level"] == "warn" and "no white outside the quiet zone" in w[0]["text"]
        assert d["label"] is None or d["label"]["kind"] in ("black", "none")
    else:
        assert not [x for x in w if "quiet zone" in x["text"]]


def test_a_marker_corner_cut_cuts_the_cut_line():
    p = _sticker("box40", "marker", corner_mark="cut")
    cut = p.data["guides"]["cut_line"]
    assert len(cut["outer"]) == 5                       # a rectangle less one corner
    assert p.data["mark"]["kind"] == "tile_cut"


def test_a_margin_makes_white_for_a_label():
    lab = {"on": True, "rule": 3, "place": "white", "content": "id_name", "nozzle_mm": 0.2}
    p = plan_tag({"settings": {"layout": "single", "label": lab,
                               "make": dict(STK, margin_mm=6.0)},
                  "target": T.box(60, 60, 0).to_dict(), "name": "arm"})
    assert p.ok and p.data["label"]["kind"] == "white", p.data["warnings"]
    r = p.data["guides"]["cut_line"]["rect"]
    s = p.data["guides"]["sticker"]
    assert r == pytest.approx([s[0] - 6, s[1] - 6, s[2] + 6, s[3] + 6])
    for part in p.data["label"]["parts"]:
        x0, y0, x1, y1 = part["rect"]
        assert r[0] <= x0 and x1 <= r[2] and r[1] <= y0 and y1 <= r[3]


def test_a_profile_corner_cut_is_not_made():
    p = _sticker("disc4", "profile", corner_mark="cut")
    assert p.ok and p.data["mark"] is None
    assert any(w["field"] == "settings.corner_mark" and "keeps its outline" in w["text"]
               for w in p.data["warnings"])


def test_a_3d_tag_is_untouched_by_the_label_rule():
    lab = {"on": True, "rule": 3, "place": "white", "content": "id", "nozzle_mm": 0.4}
    p = plan_tag({"settings": {"layout": "single", "mode": "both", "op": "new", "label": lab},
                  "target": T.box(60, 60, 0).to_dict()})
    assert not [w for w in p.data["warnings"] if "quiet zone (Perimeter" in w["text"]]


# ------------------------------------------------------------ M6a.10, the target checks

def test_a_96_point_disc_with_3_holes_plans_under_50_ms():
    t = T.disc(30.0, [(15.0, 0.0, 3.0), (-8.0, 13.0, 3.0), (-8.0, -13.0, 3.0)], n=96)
    assert len(t.loops_mm[0]) == 96 and len(t.loops_mm) == 4
    spec = TagSpec.from_dict({"settings": {"layout": "single", "holes": "avoid"},
                              "target": t.to_dict()})
    assert plan_tag(spec).ok
    best = math.inf
    # the best of twenty, in up to six rounds: the other test workers share
    # the machine (Merge 1: one round under the full check's load read 64 ms,
    # 22 ms alone)
    for _round in range(6):
        for _ in range(20):
            t0 = time.perf_counter()
            plan_tag(spec)
            best = min(best, time.perf_counter() - t0)
        if best < 0.050:
            break
        time.sleep(0.5)
    print(f"\nM6a.10: plan_tag of a 96-point disc with 3 holes: {best * 1000:.1f} ms")
    assert best < 0.050, best


def test_one_chord_tolerance():
    assert T.CHORD_MM == FA.CHORD_TOL_MM == 0.05
    n = T.chord_segments(25.0)
    assert 25.0 * (1 - math.cos(math.pi / n)) <= T.CHORD_MM
    assert 25.0 * (1 - math.cos(math.pi / (n - 1))) > T.CHORD_MM


def test_loops_are_normalised_on_reading():
    sq = [[-10, -10], [10, -10], [10, 10], [-10, 10]]
    hole = [[-2, -2], [2, -2], [2, 2], [-2, 2]]                # counter-clockwise: wrong
    t = T.Target.from_dict({"w_mm": 20, "h_mm": 20, "loops_mm": [sq[::-1], hole]})
    assert T._area2(t.loops_mm[0]) > 0 and T._area2(t.loops_mm[1]) < 0
    good = T.Target.from_dict({"w_mm": 20, "h_mm": 20, "loops_mm": [sq, hole[::-1]]})
    assert good.loops_mm == [[tuple(map(float, p)) for p in sq],
                             [tuple(map(float, p)) for p in hole[::-1]]]


def test_a_loop_outside_the_outline_is_an_error():
    sq = [[-10, -10], [10, -10], [10, 10], [-10, 10]]
    far = [[30, 0], [32, 0], [32, 2], [30, 2]]
    p = plan_tag({"settings": {"layout": "single"},
                  "target": {"w_mm": 20, "h_mm": 20, "loops_mm": [sq, far]}})
    assert not p.ok
    w = [x for x in p.data["warnings"] if x["field"] == "target.loops_mm"]
    assert w and w[0]["level"] == "error" and "loop 2 lies outside the outline" in w[0]["text"]


def test_an_island_in_a_hole_is_an_error():
    sq = [[-20, -20], [20, -20], [20, 20], [-20, 20]]
    hole = [[-10, -10], [10, -10], [10, 10], [-10, 10]]
    island = [[-2, -2], [2, -2], [2, 2], [-2, 2]]
    p = plan_tag({"settings": {"layout": "single"},
                  "target": {"w_mm": 40, "h_mm": 40, "loops_mm": [sq, hole, island]}})
    assert not p.ok
    assert any("lies inside hole 1" in w["text"] for w in p.data["warnings"])
