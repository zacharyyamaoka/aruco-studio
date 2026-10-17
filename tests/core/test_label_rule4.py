"""Label rule 4 (the 2026-10-17 audit, FB-13: "ChArUco: the label goes only
in a black checker square"). Under rules 1-3 a ChArUco label on Position
auto falls back to the white beside the board when its square is too small;
from rule 4 it stays in a black square: refused with ONE message under the
Label row (what to change: fewer columns, a bigger checker or Content #id),
its orange preview in the square it was tried in. A new tag stores rule 4;
a stored rule 3 label is planned as it always was.
"""
from __future__ import annotations

import copy

from aruco_studio.core import label as L
from aruco_studio.plan import plan_tag
from aruco_studio.scene import design as DS


def plate_tag(rule):
    """The audit's plate: 80 x 50, a hole near the left, ChArUco Auto, the
    label "#id + name" on Position auto (the Default preset)."""
    doc = {"schema": DS.SCHEMA,
           "sketches": [{"id": "sk", "shapes": [{"id": "plate", "rect": [80, 50],
                                                 "holes": [{"circle": 18, "at": [-25, 0]}]}]}],
           "features": [{"id": "body", "extrude": "plate", "height": 5},
                        {"id": "tag", "aruco": "body.top", "layout": "charuco",
                         "label": "#id + name", "name": "plate"}]}
    sc, issues = DS.compile(doc)
    assert not [i for i in issues if i.level == "error"]
    spec = copy.deepcopy(sc.tags[0].spec)
    if rule is not None:
        spec.settings["label"]["rule"] = rule
    return spec


def test_a_new_tag_stores_rule_4():
    assert L.NEW_RULE == 4 and L.SQUARE_ONLY_RULE == 4
    assert plate_tag(None).settings["label"]["rule"] == 4


def test_rule_3_keeps_its_white_fallback():
    lab = plan_tag(plate_tag(3)).ev["label"]
    assert lab.kind == "white" and lab.parts             # as built before the audit


def test_rule_4_refuses_with_one_message_and_a_preview_in_the_square():
    p = plan_tag(plate_tag(4))
    lab = p.ev["label"]
    assert lab.kind == "none" and not lab.parts
    assert lab.reason.startswith("no room in a ") and "ChArUco square for '#0-" in lab.reason
    pv = lab.preview
    assert pv is not None and pv.kind == "black" and pv.side == "square"
    sq = L.charuco_square(p.ev["spec"])
    cx = (pv.slots[0].rect[0] + pv.slots[0].rect[2]) / 2.0
    cy = (pv.slots[0].rect[1] + pv.slots[0].rect[3]) / 2.0
    assert sq[0] <= cx <= sq[2] and sq[1] <= cy <= sq[3]    # drawn in its square
    label_rows = [i for i in p.data["warnings"] if i["field"].startswith("settings.label")]
    assert len(label_rows) == 1, label_rows
    one = label_rows[0]
    assert one["field"] == "settings.label" and one["level"] == "error"
    assert "Fewer columns (bigger squares), a bigger checker or Content #id" in one["text"]
    assert "nothing printable fits" not in " ".join(i["text"] for i in p.data["warnings"])


def test_rule_4_builds_in_the_square_when_it_fits():
    spec = plate_tag(4)
    spec.settings["label"]["content"] = "id"
    spec.settings["force"] = [3, 2]
    spec.settings["size_auto"] = False
    spec.numbers["square"] = 20.0
    spec.numbers["size"] = 15.0
    lab = plan_tag(spec).ev["label"]
    assert lab.kind == "black" and lab.side == "square" and lab.parts


def test_an_explicit_white_is_still_honoured():
    spec = plate_tag(4)
    spec.settings["label"]["place"] = "white"
    lab = plan_tag(spec).ev["label"]
    assert lab.kind in ("white", "none")
    assert lab.kind == "white" or (lab.preview is not None and lab.preview.kind == "white")
