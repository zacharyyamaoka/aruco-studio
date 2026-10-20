"""ArUco Extrude's heights through the facade (contract barrier 10, Zach
2026-10-20 night: "for inkjet you just get to set paper thickness (but its
autofilled from the preset). For 3D printer you get to set the white height
and black height. Black height is always measured from the outer face of the
white ... in all cases you get the option to just flip it"): PlanRequest.extrude
-> the core's settings.mode / numbers / make (aruco_studio/web_extrude.py),
the driven heights rule (core.presets.driven_heights), MarkerPlan.extrude,
Flip on a reference face, and White only's label in `layers`. A request
without `extrude` plans byte for byte as main did."""
from __future__ import annotations

import copy
import hashlib
import json

import pytest

from aruco_studio import web_api as W
from aruco_studio.core import presets as P

from test_web_api import req
from test_web_profile_first import parity_cases

D3 = next(p for p in W.presets() if p["method"] == "print3d")
INK = next(p for p in W.presets() if p["name"] == "Inkjet · Letter vinyl")
# Zach's PrusaSlicer profile "0.32mm SPEED @MK4IS 0.6 - Aruco" as a flat preset
ARUCO = dict(copy.deepcopy(D3), id="aruco", name="Aruco", builtin=False, nozzle_mm=0.6,
             line_mm=0.68, layer_mm=0.32, first_layer_mm=0.2)


def ex_req(extrude=None, pre=ARUCO, face=False, marker=None, label=None, rect=None):
    r = req(marker, rect=rect or {"w": 30.0, "h": 36.0}, label=label, pre=pre, face=face)
    if extrude is not None:
        r["extrude"] = extrude
    return r


def layer(p, name):
    got = [L for L in p["layers"] if L["name"] == name]
    assert len(got) == 1, (name, [L["name"] for L in p["layers"]])
    return got[0]


def said(p, field, level=None):
    return [w for w in p["warnings"] if w["field"] == field and (level is None or w["level"] == level)]


# ------------------------------------------------------------------ the driven rule

def test_the_driven_heights_rule():
    got = P.driven_heights(0.32, 0.2)
    assert got == {"rule": P.HEIGHTS_RULE, "black_mm": 0.52, "white_mm": 1.8, "layers": True}
    assert P.HEIGHTS_RULE == 1
    # whole layers face down: layer_note has nothing to say about either
    assert P.layer_note(got["black_mm"], 0.32, 0.2, "black") is None
    assert P.layer_note(got["white_mm"], 0.32, 0.2, "white") is None
    # without a layer height AND a first layer: the heights before the rule
    for lay, first in ((0.0, 0.0), (0.32, 0.0), (0.0, 0.2), (None, None)):
        assert P.driven_heights(lay, first) == {"rule": 1, "black_mm": 0.6, "white_mm": 2.0,
                                                "layers": False}
    # the fewest layers that reach the minimum: a thick first layer is enough on its own
    assert P.driven_heights(0.2, 0.6)["black_mm"] == 0.6
    assert P.driven_heights(0.1, 0.1) == {"rule": 1, "black_mm": 0.5, "white_mm": 1.8, "layers": True}


def test_driven_heights_reach_the_plan():
    p = W.plan(ex_req({}))
    assert p["extrude"] == {"method": "print3d", "mode": "both", "white_mm": 1.8, "black_mm": 0.52,
                            "paper_mm": 0.0, "flipped": False,
                            "driven": ["mode", "white_mm", "black_mm", "paper_mm"]}
    assert layer(p, "tile")["z"] == [0.0, 1.8]
    assert layer(p, "pattern")["z"] == [1.28, 1.8]          # flush: 0.52 down from the white's top
    assert layer(p, "pocket")["z"] == [1.28, 1.8]
    assert p["origin_z_mm"] == p["origin"][11] == 1.8       # the Joint Origin on the outer face
    assert not [w for w in p["warnings"] if w["field"].startswith("extrude")]
    # the built-in Default has no layers: 2.0 / 0.6 as before
    d = W.plan(ex_req({}, pre=D3))
    assert (d["extrude"]["white_mm"], d["extrude"]["black_mm"]) == (2.0, 0.6)
    assert layer(d, "pattern")["z"] == [1.4, 2.0]


def test_a_3d_print_without_extrude_follows_the_rule_too():
    """The one way a 3D plan without `extrude` changes: its heights are the
    preset's driven ones (a preset with layers), and no `extrude` key."""
    p = W.plan(ex_req(None))
    assert "extrude" not in p
    assert layer(p, "pattern")["z"] == [1.28, 1.8] and p["origin_z_mm"] == 1.8


# ------------------------------------------------------------------ set values

def test_black_is_measured_from_the_whites_outer_face():
    p = W.plan(ex_req({"white_mm": 3.0, "black_mm": 1.0}, pre=D3))
    assert layer(p, "tile")["z"] == [0.0, 3.0]
    assert layer(p, "pattern")["z"] == [2.0, 3.0]
    assert p["origin_z_mm"] == 3.0
    assert p["extrude"]["driven"] == ["mode", "paper_mm"]


def test_black_only_is_measured_from_the_face_into_the_body():
    p = W.plan(ex_req({"black_mm": 0.84}, face=True))
    assert p["extrude"]["mode"] == "black"                  # auto on a reference face
    assert layer(p, "pattern")["z"] == [-0.84, 0.0]
    assert layer(p, "recess_pattern")["z"] == [-0.84, 0.0]
    assert layer(p, "recess_pattern")["into"] == "face"
    assert p["origin_z_mm"] == 0.0
    # in open space, asked for
    q = W.plan(ex_req({"mode": "black"}))
    assert q["extrude"]["mode"] == "black" and q["extrude"]["driven"] == ["white_mm", "black_mm", "paper_mm"]
    assert [L["name"] for L in q["layers"]] == ["pattern"] and layer(q, "pattern")["z"] == [-0.52, 0.0]


def test_mode_both_on_a_reference_face_when_asked():
    p = W.plan(ex_req({"mode": "both"}, face=True))
    assert p["extrude"]["mode"] == "both" and "mode" not in p["extrude"]["driven"]
    assert layer(p, "tile")["z"] == [0.0, 1.8] and layer(p, "pattern")["z"] == [1.28, 1.8]


@pytest.mark.parametrize("ex, field, words", [
    ({"white_mm": 1.0}, "extrude.white_mm", "under the 1.8 mm"),
    ({"black_mm": 0.3}, "extrude.black_mm", "under the 0.5 mm"),
    ({"black_mm": -0.3}, "extrude.black_mm", "proud of the white's outer face"),
    ({"white_mm": -1.0}, "extrude.white_mm", "below the face"),
    ({"white_mm": 1.0, "black_mm": 1.4}, "extrude.black_mm", "pokes 0.40 mm out under the tile"),
    ({"mode": "black", "black_mm": -0.5}, "extrude.black_mm", "out of the face, not flush"),
])
def test_a_set_height_is_honoured_exactly_and_said(ex, field, words):
    p = W.plan(ex_req(ex))
    assert p["ok"]
    for k in ("white_mm", "black_mm"):
        if k in ex:
            assert p["extrude"][k] == ex[k]                  # never clamped
    assert any(words in w["text"] and w["level"] == "warn" for w in said(p, field)), p["warnings"]
    W_, B = p["extrude"]["white_mm"], p["extrude"]["black_mm"]
    if p["extrude"]["mode"] == "both":
        assert layer(p, "tile")["z"] == sorted([0.0, W_])
        assert layer(p, "pattern")["z"] == pytest.approx(sorted([W_ - B, W_]), abs=1e-6)
    else:
        assert layer(p, "pattern")["z"] == sorted([-B, 0.0])


def test_a_black_taller_than_the_white_is_drawn():
    p = W.plan(ex_req({"white_mm": 1.0, "black_mm": 1.4}))
    assert layer(p, "pattern")["z"] == [-0.4, 1.0]           # through the tile and out under it


@pytest.mark.parametrize("k", ["white_mm", "black_mm"])
def test_a_zero_height_is_passed_on_and_the_core_refuses_it(k):
    """Honoured as typed, never clamped: the core has no body of height 0
    (core.slabs.layers / plan.spec.check), so the plan is refused with the
    core's words on the field."""
    p = W.plan(ex_req({k: 0.0}))
    assert not p["ok"]
    assert any("has no height" in w["text"] for w in said(p, f"extrude.{k}", "error")), p["warnings"]


def test_layer_note_is_an_info_on_the_height():
    p = W.plan(ex_req({"black_mm": 0.6}))
    got = said(p, "extrude.black_mm", "info")
    assert len(got) == 1 and "0.52 mm or 0.84 mm prints whole layers" in got[0]["text"]
    q = W.plan(ex_req({"white_mm": 2.0}))
    assert any("prints whole layers" in w["text"] for w in said(q, "extrude.white_mm", "info"))
    # whole layers: nothing
    assert not said(W.plan(ex_req({"black_mm": 0.84, "white_mm": 2.12})), "extrude.black_mm")


def test_junk_reads_as_driven_and_is_said():
    p = W.plan(ex_req({"mode": "grey", "white_mm": "tall", "black_mm": True}))
    assert p["ok"] and p["extrude"]["mode"] == "both"
    assert p["extrude"]["driven"] == ["mode", "white_mm", "black_mm", "paper_mm"]
    assert (p["extrude"]["white_mm"], p["extrude"]["black_mm"]) == (1.8, 0.52)
    for f in ("extrude.mode", "extrude.white_mm", "extrude.black_mm"):
        assert said(p, f, "warn"), f
    q = W.plan(ex_req([1, 2]))
    assert q["extrude"]["driven"] == ["mode", "white_mm", "black_mm", "paper_mm"] and said(q, "extrude", "warn")


def test_the_other_methods_fields_are_said_not_used():
    p = W.plan(ex_req({"paper_mm": 0.3}))
    assert p["extrude"]["paper_mm"] == 0.3 and said(p, "extrude.paper_mm", "info")
    assert layer(p, "tile")["z"] == [0.0, 1.8]
    q = W.plan(ex_req({"white_mm": 3.0, "black_mm": 1.0, "mode": "white"}, pre=INK))
    for f in ("extrude.white_mm", "extrude.black_mm", "extrude.mode"):
        assert said(q, f, "info"), f
    assert layer(q, "sticker")["z"] == [0.0, 0.1]


# ------------------------------------------------------------------ inkjet

def test_inkjet_paper_is_driven_by_the_preset_and_can_be_set():
    p = W.plan(ex_req({}, pre=INK))
    assert p["extrude"] == {"method": "inkjet", "mode": "both", "white_mm": 0.1, "black_mm": 0.05,
                            "paper_mm": 0.1, "flipped": False,
                            "driven": ["mode", "white_mm", "black_mm", "paper_mm"]}
    t = W.plan(ex_req({}, pre=dict(INK, thickness_mm=0.15)))
    assert t["extrude"]["paper_mm"] == 0.15 and layer(t, "sticker")["z"] == [0.0, 0.15]
    q = W.plan(ex_req({"paper_mm": 0.2}, pre=INK))
    assert layer(q, "sticker")["z"] == [0.0, 0.2] and layer(q, "ink")["z"] == [0.1, 0.2]
    assert q["origin_z_mm"] == 0.2
    assert (q["extrude"]["paper_mm"], q["extrude"]["white_mm"], q["extrude"]["black_mm"]) == (0.2, 0.2, 0.1)
    assert q["extrude"]["driven"] == ["mode", "white_mm", "black_mm"]
    # what the core says of the paper is said on the paper's field once it is set
    t2 = "the black is printed 0.1 mm into the 0.2 mm paper"
    assert any(w["text"].startswith(t2) for w in said(q, "extrude.paper_mm", "info"))
    assert not [w for w in q["warnings"] if w["field"] == "preset" and "into the" in w["text"]]
    assert [w for w in p["warnings"] if w["field"] == "preset" and "into the 0.1 mm paper" in w["text"]]


def test_a_paper_the_core_clamps_is_said_never_silent():
    """core.make keeps the paper in 0.05..2 mm (core.make.THICKNESS_MM): a
    set paper outside it reaches the core as typed, which clamps it and says
    so on extrude.paper_mm; the plan reports the paper it built."""
    p = W.plan(ex_req({"paper_mm": 0.01}, pre=INK))
    assert any("0.01 mm" in w["text"] for w in said(p, "extrude.paper_mm", "warn")), p["warnings"]
    assert p["extrude"]["paper_mm"] == layer(p, "sticker")["z"][1] == 0.05


def test_inkjet_without_extrude_is_main_byte_for_byte():
    """Every parity case (web/scripts/parity.mjs) as main bef3fe6 answered
    it: sha256 of its call() JSON."""
    got = {}
    for name, call, payload in parity_cases():
        out = json.loads(W.call(call, json.dumps(payload)))
        text = json.dumps(out, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        got[name] = hashlib.sha256(text.encode()).hexdigest()
    assert got == MAIN


def test_an_empty_extrude_only_adds_the_report():
    for name, call, payload in parity_cases():
        if call != "plan" or not payload.get("marker"):
            continue
        a = W.plan(payload)
        b = W.plan(dict(payload, extrude={}))
        if not a["ok"]:
            assert b == a, name
            continue
        b.pop("extrude")
        assert b == a, name


# sha256 of each case's call() JSON at main bef3fe6 (contract barrier 10, before this lane)
MAIN = {
    "presets": "dd7c0cf29534e61a5aa1f26c082b7d9b875ddf88254679680400e7734209496d",
    "plan single auto": "2bee334b8e9a4e04df945c92a3aac4e470ba694d5404e65a4d37c17a0ab3acb4",
    "plan overflow": "ef0ecd16f4cdef3516ead2ddaa7efed0c221e2ebc9340a89a31e94f7a8386eee",
    "plan grid 3x2 auto": "20a2e38c51ab2595c2ef74e4ba2165aef0f933a471eb26e68303ffe139948074",
    "plan grid 2x1 manual": "1f3ef486a7ae970f43a97d75a30ca77a37230be98c9247f4e83296288ae90162",
    "plan grid turn 90": "005885f5cb6b749fece20775e8fd04ca28687a14123cada54e19bb257a69c3da",
    "plan charuco 5x4 auto": "bd871f821092ad1365fdfe9eef0dbebab2e0ec6a15e85ef6c676ea9d5d246afb",
    "plan charuco 9 / 13": "880a81e94fa8c325dc51fada3cd8f46292652eba5aa2aac3645ed252f2863453",
    "plan charuco 10 / 13 refused": "3399dd2e2ecb823f3060315b6e6113db448228ae14c260629dd8833d422c8977",
    "plan flip + corner + label": "06d73944f8235e2b4ec99a11b0562a075ca50e26ff6482b11de47888e7a65156",
    "plan grid on a face, 3D": "e60ae04543d247e241cb3faa42dc7682f419879178a174ca952bfe12213ce776",
    "plan refused 100 markers": "0a754321cd2aba05c63bde26569fa442b11a3fd4f69ab01c1b01452be52661d0",
    "inscribe avoid": "2872b929d055d95952d5f503de788e119cca0fe677322d876892bcdacff2045d",
    "inscribe ignore": "ff05193f6b0015b86548896b5f9e5ca00c4aa9dd122a7fcca1844220f3c1085c",
    "suggest grid": "6502143650f8ff288fd1fc62c564ee5eca7276a4bcf08ab1aa9761d6d9310915",
    "suggest charuco, 3D lines": "8a3128d3b753215543840bf9839ceaefc26a5394911ff53f0dabdb3034bca626",
    "svg single with label": "27f0e68bd705d93f1b50174eee1c65d898c58936fb63f55de2b4fc9d699a8eb4",
    "sheet letter, 3 items": "629e237732d3dec62b9addb1b696c6c0f7056442203f25c3ce7024e520051a91",
    "bad request": "8e6d901213f7b7338b700624b3727ea41595064d9871a074889a7cb3f6be97f3",
}


# ------------------------------------------------------------------ flip

@pytest.mark.parametrize("pre", [ARUCO, INK], ids=["3D", "inkjet"])
def test_flip_applies_on_a_reference_face(pre):
    a = W.plan(ex_req({}, pre=pre, face=True))
    f = W.plan(ex_req({}, pre=pre, face=True, marker={"flip": True}))
    assert f["extrude"]["flipped"] and not a["extrude"]["flipped"]
    assert not said(f, "marker.flip")
    assert len(f["layers"]) == len(a["layers"])
    for La, Lf in zip(a["layers"], f["layers"]):             # turned over: [lo, hi] -> [-hi, -lo]
        assert Lf["name"] == La["name"] and Lf["z"] == [-La["z"][1] + 0.0, -La["z"][0] + 0.0]
    assert f["origin"][10] == -a["origin"][10] and f["origin_z_mm"] == -a["origin_z_mm"] + 0.0
    mirrored = sorted(tuple(sorted((x, -y + 0.0) for x, y in poly["outer"])) for poly in a["black"])
    assert sorted(tuple(sorted(map(tuple, poly["outer"]))) for poly in f["black"]) == pytest.approx(mirrored)
    # the same flip as in open space
    free = W.plan(ex_req({}, pre=pre, marker={"flip": True}))
    assert f["black"] == free["black"]


def test_flip_on_a_face_turns_black_only_over():
    f = W.plan(ex_req({}, face=True, marker={"flip": True}))
    assert layer(f, "pattern")["z"] == [0.0, 0.52] and layer(f, "recess_pattern")["z"] == [0.0, 0.52]
    assert f["origin_z_mm"] == 0.0


# ------------------------------------------------------------------ White only's label

def test_white_only_puts_the_label_in_layers_white():
    p = W.plan(ex_req({"mode": "white"}, face=True,
                      label={"on": True, "text": "#{id}", "place": "outside"}))
    pat = layer(p, "pattern")
    assert pat["colour"] == "white" and pat["z"] == [-0.52, 0.0]   # driven as the pattern (0.52)
    ink = layer(p, "label_ink")
    assert ink["colour"] == "white" and ink["op"] == "add" and ink["z"] == pat["z"]
    assert ink["polygons"] == p["label"]["polygons"] and ink["polygons"]
    rec = layer(p, "recess_label")                           # cut into the face as the pattern is
    assert (rec["op"], rec["into"], rec["z"]) == ("cut", "face", layer(p, "recess_pattern")["z"])
    assert rec["polygons"] == ink["polygons"]
    # no body under it: no recess
    q = W.plan(ex_req({"mode": "white"}, label={"on": True, "text": "#{id}", "place": "outside"}))
    assert layer(q, "label_ink")["colour"] == "white"
    assert not [L for L in q["layers"] if L["name"] == "recess_label"]


def test_white_only_label_on_the_marker():
    # knocked out of the black border row: the row is the body, the letters white ink
    k = W.plan(ex_req({"mode": "white"}, face=True, label={"on": True, "text": "#{id}"}))
    assert layer(k, "label_ink")["colour"] == "white"
    # black text on the white quiet zone: cut out of the white pattern (the body shows)
    lab = {"on": True, "text": "#{id}", "surface": "white"}
    w = W.plan(ex_req({"mode": "white"}, face=True, label=lab))
    off = W.plan(ex_req({"mode": "white"}, face=True))
    assert not [L for L in w["layers"] if L["part"] == "label"]
    assert len(layer(w, "pattern")["polygons"]) > len(layer(off, "pattern")["polygons"])
    # White + black keeps its black label ink at the black's z
    b = W.plan(ex_req({}, label={"on": True, "text": "#{id}", "place": "outside"}))
    assert layer(b, "label_ink")["colour"] == "black" and layer(b, "label_ink")["z"] == [1.28, 1.8]


# ------------------------------------------------------------------ the other calls

def test_svg_sheet_and_call_carry_extrude():
    r = ex_req({"paper_mm": 0.2, "black_mm": 1.0}, pre=INK, label={"on": True, "text": "#{id}"})
    assert W.svg(r) == W.svg(ex_req(None, pre=INK, label={"on": True, "text": "#{id}"}))   # 2D: the same
    sh = W.sheet({"items": [r], "cut_lines": True}, "2026-10-20")
    assert sh["pages"] == 1 and [w for w in sh["warnings"] if w["field"] == "extrude.black_mm"]
    out = json.loads(W.call("plan", json.dumps(ex_req({"black_mm": 0.84}))))["result"]
    assert out["extrude"]["black_mm"] == 0.84 and out["extrude"]["driven"] == ["mode", "white_mm", "paper_mm"]
    s3 = W.sheet({"items": [ex_req({"white_mm": 1.0})]}, "2026-10-20")
    assert [w for w in s3["warnings"] if w["field"] == "extrude.white_mm"]


def test_verify_plans_with_extrude_and_flip_on_a_face():
    V = pytest.importorskip("aruco_studio.web_verify")
    pytest.importorskip("cv2")
    cam = {"distance_mm": 300.0, "resolution": [1920, 1080], "hfov_deg": 70.0}
    view = {"camera": cam, "tilt_deg": 0.0, "yaw_deg": 0.0, "blur_px": 0.0, "noise": 0.0,
            "glare": 0.0, "occlusion": 0.0, "seed": 1}
    r = ex_req({"white_mm": 3.0, "black_mm": 1.0}, marker={"first_id": 5}, rect={"w": 40.0, "h": 40.0})
    out = V.verify(r, view)
    assert out["found"] == [5] and out["ok"]
    lab = {"on": True, "text": "#{id}", "place": "outside"}
    assert V._label(ex_req({}, face=True, label=lab, rect={"w": 40.0, "h": 50.0}),
                    W._plan(ex_req({}, face=True, label=lab, rect={"w": 40.0, "h": 50.0}))[0]) is not None
    # Flip on a face turns the marker away from its sketch text, as in open space
    fr = ex_req({}, face=True, label=lab, marker={"flip": True}, rect={"w": 40.0, "h": 50.0})
    assert V._label(fr, W._plan(fr)[0]) is None
