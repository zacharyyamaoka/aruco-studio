"""The 2026-10-17 audit (B9): Auto on a ChArUco board can pick a layout
whose cells are under the preset's minimum, and warns at once. The layout
Auto picks is the versioned rule's (unchanged); the warn now says the fix:
the Checker size that passes, and the board it gives on a plain face."""
from __future__ import annotations

from aruco_studio.plan import plan_tag
from aruco_studio.plan.plan import cell_min_fix
from aruco_studio.scene import design as DS


def _cellmin(doc):
    sc, _ = DS.compile(doc)
    p = plan_tag(sc.tags[0].spec)
    return p, [w for w in p.data["warnings"] if w["text"].startswith("cell minimum")]


def _plate(holes):
    shape = {"id": "plate", "rect": [80, 50]}
    if holes:
        shape["holes"] = [{"circle": 18}]
    return {"schema": DS.SCHEMA, "sketches": [{"id": "sk", "shapes": [shape]}],
            "features": [{"id": "body", "extrude": "plate", "height": 5},
                         {"id": "tag", "aruco": "body.top", "layout": "charuco"}]}


def _side():
    """The forearm's 40 x 40 side face (Auto: 3 x 3 under the minimum)."""
    return {"schema": DS.SCHEMA, "sketches": [{"id": "sk", "shapes": [{"id": "o", "rect": [120, 40]}]}],
            "features": [{"id": "body", "extrude": "o", "height": 40},
                         {"id": "tag", "aruco": "body.right", "layout": "charuco"}]}


def test_the_warn_names_the_checker_that_passes_and_it_does():
    p, ws = _cellmin(_side())
    assert len(ws) == 1 and ws[0]["level"] == "warn" and ws[0]["field"] == "numbers.size"
    text = ws[0]["text"]
    assert "; a Checker size of " in text and "mm passes (" in text and "on this face)" in text
    sq = float(text.split("a Checker size of ")[1].split(" mm")[0])
    # typed, that checker clears the minimum
    sc, _ = DS.compile(_side())
    spec = sc.tags[0].spec
    spec.settings["size_auto"] = False
    spec.numbers["square"] = sq
    spec.numbers["size"] = 0.0
    p2 = plan_tag(spec)
    assert p2.ok and not [w for w in p2.data["warnings"] if w["text"].startswith("cell minimum")]


def test_with_a_hole_no_count_is_claimed():
    _p, ws = _cellmin(_plate(holes=True))
    assert len(ws) == 1 and ws[0]["text"].endswith("mm or more passes")


def test_other_notes_pass_through():
    assert cell_min_fix("module 1.0 mm < 1.2 mm", {}, None) == "module 1.0 mm < 1.2 mm"
