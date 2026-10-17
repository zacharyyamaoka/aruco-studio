"""Make rule 2 (2026-10-17, Zach's CF-7 and the 2D pivot CF-13): an inkjet
sticker is ONE paper body t thick, the black t/2 INTO its top, flush; the
tag frame on the paper's top. New behaviour, no REF: tested by its
properties and by OpenCV.

| Check | Here |
|---|---|
| the parts | sticker / pocket / ink; the pocket cut from the paper; the black [t/2, t]; the paper [0, t] |
| volumes | white + black = the cut outline's area x t; black = the ink's area (top view) x t/2; the white = area x t - ink x t/2 |
| the frame | frames.surface_mm = detector_z_mm = t; plan.sticker.frame_z_mm = t |
| the top view | pixel for pixel rule 1's (the same ink, only its depth moved) |
| OpenCV | every layout x turn x mark x label reads; PnP within 0.1 mm / 0.1 deg |
| the record | fusion.make is rule 2's dict; rules.make = 2 |
| the reading | margin / cut line ignored with an info; a junk page warns; clamped page margins |
| new tags | a vinyl preset stamps rule 2; an older sticker preset (and its frozen copies) rule 1; no preset rule 2 |
| old files | rule 1 plans exactly as before: the three examples' and every golden's digests (tools/mesh_digests.py --check, test_mesh_digests.py) |
"""
from __future__ import annotations

import copy
import math

import numpy as np
import pytest

from aruco_studio.core import faces as FA
from aruco_studio.core import form as F
from aruco_studio.core import make as MK
from aruco_studio.core import presets as P
from aruco_studio.plan import mesh as ME
from aruco_studio.plan import plan_tag
from aruco_studio.plan import target as T

R1 = {"rule": 1, "by": "sticker"}
R2 = {"rule": 2, "by": "sticker", "thickness_mm": 0.1, "perimeter": "marker", "page": "letter",
      "page_margin_mm": 10.0}
LAB = {"on": True, "rule": 3, "place": "black", "content": "id", "nozzle_mm": 0.2}
TARGETS = {"single": (60, 60), "grid": (90, 70), "charuco": (90, 70)}
CASES = [(lay, turn, mark, lab) for lay in ("single", "grid", "charuco")
         for turn in (0, 90, 180, 270) for mark in ("none", "cut", "triangle")
         for lab in (False, True)]


def _area(poly):
    """|area| of an [outer, hole, ...] polygon (mm2)."""
    def a(lp):
        return abs(sum(lp[i - 1][0] * lp[i][1] - lp[i][0] * lp[i - 1][1]
                       for i in range(len(lp)))) / 2.0
    return a(poly[0]) - sum(a(h) for h in poly[1:])


def _vols(p):
    out = {}
    for m in ME.mesh(p):
        out[m["what"]] = out.get(m["what"], 0.0) + ME.volume(m["positions"], m["indices"])
    return out


def _cut_area(d):
    cut = d["guides"]["cut_line"]
    return _area([cut["outer"]] + list(cut.get("holes") or []))


def _ink_area(d):
    return sum(_area(poly) for poly in ME.top(d).get("black", []))


def _pair(lay, turn, mark, lab, t=0.1, per="marker", target=None):
    s = {"layout": lay, "turn": turn, "origin_v": 2, "corner_mark": mark}
    if lab:
        s["label"] = dict(LAB)
    tg = target or T.box(*TARGETS[lay], 0).to_dict()
    a = plan_tag({"settings": dict(s, make=dict(R1, thickness_mm=t, perimeter=per)), "target": tg})
    b = plan_tag({"settings": dict(s, make=dict(R2, thickness_mm=t, perimeter=per)), "target": tg})
    return a, b


@pytest.mark.parametrize("lay,turn,mark,lab", CASES,
                         ids=[f"{a}-{b}-{c}-{'lab' if d else 'nolab'}" for a, b, c, d in CASES])
def test_the_paper_and_the_black_inside_it(lay, turn, mark, lab):
    r1, r2 = _pair(lay, turn, mark, lab)
    assert r1.ok and r2.ok, (r1.data["errors"], r2.data["errors"])
    d = r2.data
    assert d["made_by"] == "sticker" and d["rules"]["make"] == 2
    assert d["parts"] == ["sticker", "pocket", "ink"]
    assert d["combines"] == [{"part": "sticker", "op": "new", "into": None},
                             {"part": "pocket", "op": "cut", "into": "sticker"},
                             {"part": "ink", "op": "new", "into": None}]
    zs = {(L["part"], L["step"]): L["z"] for L in d["layers"] if L["name"] in ("sticker", "pocket", "ink")}
    assert zs[("sticker", "add")] == [0.0, 0.1]
    assert zs[("pocket", "add")] == [0.05, 0.1] and zs[("ink", "add")] == [0.05, 0.1]
    assert max(z for L in d["layers"] if L["op"] == "add" and L["step"] == "add"
               for z in L["z"]) == pytest.approx(0.1)               # nothing on top of the paper
    # the frame on the paper's top, t over the face
    assert d["frames"]["surface_mm"] == pytest.approx(0.1)
    assert d["frames"]["detector_z_mm"] == pytest.approx(0.1)
    assert d["frames"]["opencv"][11] == pytest.approx(0.1)            # its origin's z (pattern frame)
    assert d["sticker"]["frame_z_mm"] == pytest.approx(0.1)
    assert d["sticker"]["paper_z_mm"] == [0.0, 0.1] and d["sticker"]["ink_z_mm"] == [0.05, 0.1]
    assert d["marker"]["depth_m"] == pytest.approx(5e-5)
    assert d["record"]["fusion"]["make"] == dict(R2)
    assert d["writes"]["settings"]["parts"] == ["sticker", "pocket", "ink"]
    assert d["ids"] == r1.data["ids"] and d["marker"]["marker_length_m"] == \
        r1.data["marker"]["marker_length_m"]
    # the volumes: the paper is the cut outline x t, the black the ink x t/2
    v = _vols(r2)
    A, ink = _cut_area(d), _ink_area(d)
    assert v["white"] + v["pattern"] == pytest.approx(A * 0.1, rel=1e-6)
    assert v["pattern"] == pytest.approx(ink * 0.05, rel=1e-6)
    assert v["white"] == pytest.approx(A * 0.1 - ink * 0.05, rel=1e-6)
    # the top view: the same ink as rule 1, every polygon
    assert ME.top(r2) == ME.top(r1)


@pytest.mark.parametrize("t", [0.05, 0.1, 0.18, 2.0])
@pytest.mark.parametrize("per", ["marker", "profile"])
def test_the_volumes_on_every_thickness_and_perimeter(t, per):
    tgt = T.from_face("disc4").to_dict() if per == "profile" else None
    _r1, r2 = _pair("single", 0, "triangle", True, t=t, per=per, target=tgt)
    d = r2.data
    assert r2.ok and d["guides"]["cut_line"]["kind"] == per
    v = _vols(r2)
    A, ink = _cut_area(d), _ink_area(d)
    assert v["white"] + v["pattern"] == pytest.approx(A * t, rel=1e-6)
    assert v["pattern"] == pytest.approx(ink * t / 2.0, rel=1e-6)
    assert d["frames"]["surface_mm"] == pytest.approx(t)
    zmax = max(m["z"][1] for m in ME.mesh(r2))
    assert zmax == pytest.approx(t)
    if per == "profile":
        assert len(d["guides"]["cut_line"]["holes"]) == 4


def test_the_mesh_is_closed_and_the_black_is_flush():
    _r1, r2 = _pair("charuco", 90, "triangle", True, t=2.0)
    for m in ME.mesh(r2):
        idx = m["indices"]
        edges = {}
        for k in range(0, len(idx), 3):
            a, b, c = idx[k:k + 3]
            for e in ((a, b), (b, c), (c, a)):
                edges[e] = edges.get(e, 0) + 1
        assert all(edges.get((b, a), 0) == n for (a, b), n in edges.items()), m["what"]
    black = [m for m in ME.mesh(r2) if m["what"] == "pattern"]
    assert black and all(m["z"] == [1.0, 2.0] for m in black)


@pytest.mark.parametrize("lay,turn,mark,lab", CASES[::3],
                         ids=[f"{a}-{b}-{c}-{'lab' if d else 'nolab'}" for a, b, c, d in CASES[::3]])
def test_opencv_reads_every_rule2_sticker_and_its_frame(lay, turn, mark, lab):
    from aruco_studio.verify.report import verify_plan
    _r1, r2 = _pair(lay, turn, mark, lab)
    rep = verify_plan(r2, px_per_mm=20.0, pose=True)
    assert rep["ok"], {k: rep.get(k) for k in ("missing", "extra", "pnp_err_mm", "pnp_err_deg")}
    assert rep["pnp_err_mm"] <= 0.1 and rep["pnp_err_deg"] <= 0.1


def test_the_rule2_reading():
    mk, notes = MK.make_of({"make": dict(R2, margin_mm=4.0, cut_line=False)})
    assert mk.inset and mk.margin_mm == 0.0 and mk.cut_line is True
    assert {(f, lv) for f, lv, _t in notes} == {("settings.make.margin_mm", "info"),
                                               ("settings.make.cut_line", "info")}
    mk, notes = MK.make_of({"make": dict(R2, page="napkin", page_margin_mm=80)})
    assert mk.page == "letter" and mk.page_margin_mm == 50.0
    assert {f for f, _lv, _t in notes} == {"settings.make.page", "settings.make.page_margin_mm"}
    assert MK.make_of({"make": dict(R2, page="A4")})[0].page == "a4"
    # rule 2 on a 3D tag changes nothing (the rule is the sticker's)
    mk3, _n = MK.make_of({"make": {"rule": 2, "by": "print3d"}})
    assert not mk3.sticker and not mk3.inset
    t = T.box(40, 40, 3).to_dict()
    a = plan_tag({"settings": {"layout": "single", "make": {"rule": 1, "by": "print3d"}}, "target": t})
    b = plan_tag({"settings": {"layout": "single", "make": {"rule": 2, "by": "print3d"}}, "target": t})
    da, db = a.to_dict(), b.to_dict()
    da["rules"]["make"] = db["rules"]["make"] = None
    da["record"]["fusion"] = db["record"]["fusion"] = None
    assert da == db
    # rule 3 is not a rule: read as 3D printed with a warn (as before)
    j = plan_tag({"settings": {"layout": "single", "make": {"rule": 3, "by": "sticker"}},
                  "target": T.box(40, 40, 0).to_dict()})
    assert j.ok and j.data["made_by"] == "print3d"
    assert any(w["field"] == "settings.make" and w["level"] == "warn" for w in j.data["warnings"])


def test_a_rule2_label_and_its_white():
    """No margin on a rule-2 sticker: Marker has no white for a label (the
    black only); Profile does."""
    s = {"layout": "single", "label": {"on": True, "rule": 3, "place": "white", "content": "id",
                                       "nozzle_mm": 0.2}}
    m = plan_tag({"settings": dict(s, make=dict(R2)), "numbers": {"size": 30},
                  "target": T.box(60, 60, 0).to_dict()})
    assert any(w["field"] == "settings.label.place" and w["level"] == "warn"
               for w in m.data["warnings"])
    p = plan_tag({"settings": dict(s, make=dict(R2, perimeter="profile")), "numbers": {"size": 30},
                  "target": T.box(60, 60, 0).to_dict()})
    assert p.data["label"]["kind"] == "white"


# ------------------------------------------------------------ new tags: which rule

def test_new_tags_get_rule2_from_the_vinyl_presets():
    from aruco_studio.core import settings as S
    s = S.default_settings()
    for p in (P.vinyl_preset("letter"), P.vinyl_preset("a4")):
        st = F.new_tag_settings(s, False, preset=p)
        assert st["make"] == {"rule": 2, "by": "sticker", "thickness_mm": 0.1,
                              "perimeter": "marker", "page": p["profile"]["page"],
                              "page_margin_mm": 10.0}
        assert "margin_mm" not in st["make"] and "cut_line" not in st["make"]
    # the older sticker presets (and a frozen copy without the key): rule 1, as before
    for p in (P.sticker_preset("letter"), P.sticker_preset("a4")):
        st = F.new_tag_settings(s, False, preset=p)
        assert st["make"] == {"rule": 1, "by": "sticker", "thickness_mm": 0.1, "margin_mm": 0.0,
                              "cut_line": True, "perimeter": "marker"}
    old = copy.deepcopy(P.vinyl_preset("letter"))
    old["profile"].pop("make_rule")
    assert F.new_tag_settings(s, False, preset=old)["make"]["rule"] == 1
    # no preset, made_by sticker (a script): rule 2 with the vinyl paper
    st = F.new_tag_settings(s, False, preset=P.default_preset(), made_by="sticker")
    assert st["make"]["rule"] == 2 and st["make"]["thickness_mm"] == MK.VINYL_MM
    # a 3D tag stores rule 1, as before (3D is a placeholder)
    assert F.new_tag_settings(s, True)["make"] == {"rule": 1, "by": "print3d"}


def test_a_vinyl_preset_picked_for_a_sticker_and_back():
    from aruco_studio.plan import newtag as N
    sp = N.new_spec("single", T.box(40, 40, 0).to_dict(), P.sticker_preset("letter"))
    sp["settings"] = F.new_tag_settings(sp["settings"], False, preset=P.sticker_preset("letter"))
    sp["settings"]["make"] = dict(sp["settings"]["make"], perimeter="profile", margin_mm=3.0)
    got = N.apply_preset(sp, P.vinyl_preset("a4"))
    assert got["settings"]["make"] == {"rule": 2, "by": "sticker", "thickness_mm": 0.1,
                                       "perimeter": "profile", "page": "a4",
                                       "page_margin_mm": 10.0}
    back = N.apply_preset(got, P.sticker_preset("letter"))
    assert back["settings"]["make"]["rule"] == 1 and back["settings"]["make"]["perimeter"] == "profile"
    three = N.apply_preset(got, P.default_preset())
    assert three["settings"]["make"] == {"rule": 1, "by": "print3d"}
    # a 3D preset on a 3D tag leaves `make` alone (absent stays absent)
    sp3 = N.new_spec("single", T.box(40, 40, 3).to_dict(), None)
    sp3["settings"].pop("make", None)
    assert "make" not in N.apply_preset(sp3, P.default_preset())["settings"]
    # the preset row matches the vinyl preset, not the older one
    p2 = P.preset_of(got["settings"], got["numbers"])
    assert P.same_print(p2, P.vinyl_preset("a4")) and P.same_machine(p2, P.vinyl_preset("a4"))
    assert not P.same_machine(p2, P.vinyl_preset("letter"))
    assert not P.same_machine(p2, P.sticker_preset("a4"))
    p1 = P.preset_of(back["settings"], back["numbers"])
    assert P.same_machine(p1, P.sticker_preset("letter"))


def test_the_older_examples_plan_rule1():
    """The three examples (and every file naming an older sticker preset)
    plan as before: their stickers are rule 1 (the digests prove the bits)."""
    import json
    import os
    import tempfile
    from pathlib import Path
    from aruco_studio.scene import design as DS
    from aruco_studio.server import design_api as DA
    root = Path(__file__).resolve().parents[2]
    keep = os.environ.get("ARUCO_STUDIO_HOME")
    os.environ["ARUCO_STUDIO_HOME"] = os.path.join(tempfile.mkdtemp(prefix="r2_"), "studio")
    try:
        text = (root / "examples" / "sticker_sheet.arucostudio.json").read_text(encoding="utf-8")
        sc, _issues = DS.compile(DA.loads_design(text), DA.resolver())
    finally:
        if keep is None:
            os.environ.pop("ARUCO_STUDIO_HOME", None)
        else:
            os.environ["ARUCO_STUDIO_HOME"] = keep
    rules = {t.name: plan_tag(t.spec).data["rules"]["make"] for t in sc.tags}
    assert rules and set(rules.values()) == {1}, rules
    assert json.loads(text)["preset"] == "Sticker · Letter · 600 dpi"


# ------------------------------------------------------------ plan_sticker: what a CAD node builds

def test_plan_sticker_gives_the_bodies_in_build_order():
    from aruco_studio.plan import plan_sticker
    s = {"layout": "single", "corner_mark": "triangle", "label": dict(LAB)}
    tg = T.box(60, 60, 0).to_dict()
    spec = {"settings": dict(s, make=dict(R2)), "target": tg}
    got = plan_sticker(spec)
    assert got["rule"] == 2 and got["thickness_mm"] == 0.1
    assert [(b["part"], b["role"], b["op"], b["into"], b["colour"], b["z_mm"]) for b in got["bodies"]] == [
        ("sticker", "paper", "new", None, "white", [0.0, 0.1]),
        ("pocket", "pocket", "cut", "sticker", "none", [0.05, 0.1]),
        ("ink", "black", "new", None, "black", [0.05, 0.1])]
    ink = got["bodies"][2]["steps"]
    assert ink[0]["name"] == "ink" and ink[0]["step"] == "add"
    assert {x["name"] for x in ink} >= {"ink", "mark_triangle", "label_join"} or \
        {x["name"] for x in ink} >= {"ink", "mark_triangle", "label_cut"}
    assert got["frame"]["z_mm"] == 0.1 and got["frame"]["opencv"][11] == pytest.approx(0.1)
    assert got["page"]["fits"] and got["lint"] == [] and got["record_make"] == dict(R2)
    assert got["cut_line"]["kind"] == "marker"
    # the same from the plan; a 3D tag and a refused one: None; rule 1: two bodies
    p = plan_tag(spec)
    assert plan_sticker(p) == got == plan_sticker(p.to_dict())
    assert plan_sticker({"settings": dict(s), "target": T.box(60, 60, 3).to_dict()}) is None
    r1 = plan_sticker({"settings": dict(s, make=dict(R1)), "target": tg})
    assert [(b["part"], b["z_mm"]) for b in r1["bodies"]] == [("sticker", [0.0, 0.1]),
                                                             ("ink", [0.1, 0.11])]
    big = plan_sticker({"settings": {"layout": "single", "make": dict(R2)}, "numbers": {"size": 200},
                        "target": T.box(280, 280, 0).to_dict()})
    assert big["page"]["fits"] is False and big["lint"][0]["field"] == "numbers.size"
