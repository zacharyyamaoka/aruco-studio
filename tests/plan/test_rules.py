"""Every versioned rule, as the plan carries it (TagPlan.rules) and as it
builds: an old tag keeps the rule it was made under, a new one gets today's.

| Rule | Stored as | Absent / unknown means |
|---|---|---|
| SPEC_VERSION 2 | settings.v | (normalise maps older shapes) |
| ORIGIN_RULE 2 | settings.origin_v | the pre-2026-10-09 rule: a rectangular board keeps 90 / 270 as laid out |
| CELL_RULE 1 | settings.cells | the legacy 0.5 mm steps |
| label RULES {1, 2} | settings.label.rule | rule 1 (2-module gap) |
| trim RULE 1 | settings.trim | off |
| legacy numbers | numbers.height / thickness / above | mapped to Offset / Height pairs |
| font 1 | (the plan only) | |
"""
from __future__ import annotations

import pytest

from aruco_studio.core import label as L
from aruco_studio.core import slabs as SL
from aruco_studio.plan import TagSpec, plan_tag
from aruco_studio.plan import target as T


def P(settings, numbers=None, w=100.0, h=60.0, thickness=0.0):
    return plan_tag(TagSpec(settings=settings, numbers=numbers or {},
                            target=T.box(w, h, thickness), key="k"))


@pytest.mark.parametrize("layout", ["single", "grid", "charuco"])
def test_todays_rules_on_a_new_tag(layout):
    p = P({"layout": layout, "mode": "both", "origin_v": 2,
           "cells": {"rule": 1, "of": "cell", "mm": 0.68, "min_mm": 2.0},
           "label": {"on": True, "place": "white", "rule": 2},     # the form writes it
           "trim": {"rule": 1, "axes": "both"}}, thickness=3.0)
    assert p.ok, p.data["errors"]
    r = p.data["rules"]
    assert r["spec"] == 2 and r["origin"] == 2 and r["cells"]["rule"] == 1
    assert r["label"] == L.RULE == 2 and r["trim"] == 1 and r["font"] == 1
    assert not r["legacy_numbers"]
    assert p.data["writes"]["settings"]["v"] == 2


@pytest.mark.parametrize("layout", ["single", "grid", "charuco"])
def test_an_old_tag_keeps_its_rules(layout):
    p = P({"layout": layout, "mode": "both", "label": {"on": True, "place": "white"},
           "trim": {"rule": 9, "axes": "both"}})
    assert p.ok
    r = p.data["rules"]
    assert r["origin"] is None and r["cells"] is None and r["trim"] is None
    assert r["label"] == 1                                # no "rule": rule 1, as it was
    assert "trim" not in p.data["parts"]
    assert p.data["writes"]["settings"].get("trim", "absent") is None    # settle drops junk


def test_the_origin_rule_changes_only_a_rectangular_boards_quarter_turn():
    for layout, force, w, h, nums in (("grid", [3, 2], 60.0, 40.0, {"size": 14.0}),
                                      ("charuco", [5, 4], 100.0, 80.0,
                                       {"size": 13.5, "square": 18.0})):
        old = P({"layout": layout, "mode": "black", "turn": 90, "force": force}, nums, w, h)
        new = P({"layout": layout, "mode": "black", "turn": 90, "force": force, "origin_v": 2},
                nums, w, h)
        assert old.data["placement"]["turn_deg"] == 0 and new.data["placement"]["turn_deg"] == 90
        assert (old.data["marker"]["cols"], old.data["marker"]["rows"]) == tuple(force)
        assert (new.data["marker"]["cols"], new.data["marker"]["rows"]) == tuple(force[::-1])


def test_the_cell_rule_changes_the_size_grid():
    legacy = P({"layout": "single", "mode": "black"}, {"size": 27.3}, 60, 60)
    cells = P({"layout": "single", "mode": "black",
               "cells": {"rule": 1, "of": "cell", "mm": 0.68, "min_mm": 2.0}}, {"size": 27.3},
              60, 60)
    assert legacy.data["marker"]["marker_length_m"] != cells.data["marker"]["marker_length_m"]
    # legacy: a typed size as typed (0.5 mm steps only for Auto)
    assert abs(legacy.data["marker"]["marker_length_m"] - 0.0273) < 1e-12


def test_the_label_rule_moves_a_label_on_the_white():
    one = P({"layout": "single", "mode": "both", "label": {"on": True, "place": "white",
                                                           "side": "below", "rule": 1}},
            w=60, h=70)
    two = P({"layout": "single", "mode": "both", "label": {"on": True, "place": "white",
                                                           "side": "below", "rule": 2}},
            w=60, h=70)
    assert one.ok and two.ok
    assert one.data["rules"]["label"] == 1 and two.data["rules"]["label"] == 2
    assert one.data["guides"]["clear_hard"] != two.data["guides"]["clear_hard"]


def test_legacy_numbers_build_as_their_offset_height_pairs():
    for mode in ("both", "black", "white"):
        old = P({"layout": "single", "mode": mode}, {"height": 3.0, "thickness": 1.0,
                                                     "above": 0.4})
        pairs = dict(SL.from_legacy(mode, 3.0, 1.0, 0.4))
        new = P({"layout": "single", "mode": mode}, pairs)
        assert old.data["rules"]["legacy_numbers"] and not new.data["rules"]["legacy_numbers"]
        assert old.data["layers"] == new.data["layers"]
        assert old.data["record"] == new.data["record"]
