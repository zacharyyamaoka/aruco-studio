"""The Fusion calls a new tag makes, for each type (single marker, grid
board, ChArUco board) and the other structures (Black only, White only, New
body with pins, a label and a corner mark, Trim excess), on the stand-in.

Each sequence is kept, at feature level, in tests/adapters/sequences/<name>.txt
(the TemporaryBRepManager calls between two feature calls folded into one
line of counts) and compared exactly; ARUCO_UPDATE_SEQUENCES=1 rewrites
them. The tests also check the order REF's create() measured right:

* the frame sketch first (jo_v 2), then per part its base feature, its body
  named for its role, then its combine (join / cut / intersect, into the
  plate or the tile, as `TagPlan.combines`);
* the node wraps the first to the last feature; its spec is written right
  after `customFeatures.add`;
* the colours LAST (after add(), which resets them); the Joint Origin after
  the node, on the frame sketch's point and lines; the record last.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

import fake_adsk as FK
from aruco_studio.adapters.fusion import feature as FT
from aruco_studio.core import settings as S

SEQ = Path(__file__).resolve().parent / "sequences"
LABEL = {"on": True, "content": "id", "rule": 2}

CASES = {
    "single_join": ({"layout": "single", "dictionary": "DICT_4X4_50", "mode": "both",
                     "op": "join"}, {}),
    "grid_new": ({"layout": "grid", "dictionary": "DICT_4X4_50", "mode": "both", "op": "new"},
                 {}),
    "charuco_join": ({"layout": "charuco", "dictionary": "DICT_4X4_50", "mode": "both",
                      "op": "join"}, {}),
    "single_black_only": ({"layout": "single", "dictionary": "DICT_5X5_100", "mode": "black",
                           "op": "join"}, {"black_offset": 0.0, "black_height": -0.6}),
    "grid_white_only": ({"layout": "grid", "dictionary": "DICT_4X4_50", "mode": "white",
                         "op": "join"}, {"white_offset": 0.0, "white_height": 0.6}),
    "single_new_pins_label_mark": ({"layout": "single", "dictionary": "DICT_4X4_50",
                                    "mode": "both", "op": "new", "pin": "triangle",
                                    "corner_mark": "triangle", "label": LABEL},
                                   {"white_offset": 0.0, "white_height": 2.0}),
    "single_black_trim": ({"layout": "single", "dictionary": "DICT_4X4_50", "mode": "black",
                           "op": "join", "trim": {"rule": 1, "axes": "both", "margin_mm": 1.0,
                                                  "force": False}},
                          {"black_offset": 0.0, "black_height": -0.6}),
}


def _make(name):
    s, n_over = CASES[name]
    FT.register()
    _body, face = FK.plate()
    n = dict(S.default_numbers(s.get("mode", "both")), **n_over)
    FK.LOG.clear()
    out = FT.create(face, dict(s), n, key="t1")
    return out, FK.summary()


@pytest.mark.parametrize("name", sorted(CASES))
def test_sequence_is_kept(name):
    out, seq = _make(name)
    assert out["node"] is not None, out["record"]["fusion"].get("live_error")
    text = "\n".join(seq) + "\n"
    path = SEQ / f"{name}.txt"
    if os.environ.get("ARUCO_UPDATE_SEQUENCES") == "1" or not path.exists():
        path.write_text(text, encoding="utf-8", newline="\n")
    assert path.read_text(encoding="utf-8") == text


@pytest.mark.parametrize("name", sorted(CASES))
def test_order_is_create_s(name):
    out, seq = _make(name)
    rec = out["recipe"]
    heads = [x.split("(")[0] for x in seq]
    roles = [p["role"] for p in rec["parts"]]
    # the frame sketch leads
    assert heads[0] == "sketches.add"
    # per part: base feature, its body named, then its combine when it has one
    bases = [i for i, h in enumerate(heads) if h == "baseFeatures.add"]
    assert len(bases) == len(roles)
    names = [x for x in seq if x.startswith("BRepBody.name=")]
    assert [n.split("'")[1] for n in names[:len(roles)]] == [p["name"] for p in rec["parts"]]
    cbs = [x for x in seq if x.startswith("combineFeatures.add")]
    want = [c for c in rec["combines"] if c["op"] != "new"]
    assert [c.split("'")[1] for c in cbs] == [c["op"] for c in want]
    for c, w in zip(cbs, want):
        tool = c.split("[")[1]
        assert rec["parts"][roles.index(w["part"])]["name"] in tool
        into = c.split("'")[3]
        assert into == ("Plate" if w["into"] == "body" else f"tag tile t1")
    # the node: wraps first..last, spec right after add
    add = heads.index("customFeatures.add")
    assert heads[add + 1] == "customNamedValues.addOrSetValue"
    rng = next(x for x in seq if x.startswith("CustomFeatureInput.setStartAndEndFeatures"))
    assert "'aruco frame t1'" in rng
    # colours after the node; the Joint Origin after that; the record last
    paint_after = [i for i, h in enumerate(heads) if h == "BRepBody.appearance=" and i > add]
    jo = [i for i, h in enumerate(heads) if h == "jointOrigins.add"]
    assert paint_after and jo and min(jo) > min(paint_after)
    # on the frame sketch: its point and two lines, no angle, no offset, no probe
    assert len(jo) == 1 and seq[jo[0]] == "jointOrigins.add(0, [0,0,0], False)"
    assert heads[-1] == "attributes.add"


@pytest.mark.parametrize("name", sorted(CASES))
def test_colours_and_bodies_in_the_document(name):
    out, _seq = _make(name)
    des = FK.design()
    rec = out["recipe"]
    made = out["made"]
    pat = made["pattern"].bodies.item(0)
    want = "Plastic - Matte (White)" if rec["pattern_white"] else "Plastic - Matte (Black)"
    assert pat.appearance is not None and pat.appearance.name == want
    if "tile" in made and not rec["joined"]:
        tile = made["tile"].bodies.item(0)
        assert tile.appearance.name == "Plastic - Matte (White)"
        assert all(f.appearance.name == "Plastic - Matte (White)" for f in tile.faces)
    # the document's solids: cut tools consumed, the pattern a body of its own
    solids = des.solids()
    for r in ("pocket", "recess", "trim"):
        if r in made:
            assert made[r].bodies.item(0) not in solids, r
    assert pat in solids
    # one Joint Origin, named for the tag; the record says so
    jos = list(des.rootComponent.jointOrigins)
    assert [j.name for j in jos] == ["aruco t1"]
    assert out["record"]["fusion"]["joint_origin_name"] == "aruco t1"


def test_three_types_differ_where_they_should():
    seqs = {n: _make(n)[1] for n in ("single_join", "grid_new", "charuco_join")}
    for n, seq in seqs.items():
        assert sum(1 for x in seq if x.startswith("baseFeatures.add")) >= 2, n
    # a New body tile has no join; a joined one does
    assert not any("'join'" in x for x in seqs["grid_new"] if x.startswith("combineFeatures"))
    assert any("'join'" in x for x in seqs["single_join"] if x.startswith("combineFeatures"))
