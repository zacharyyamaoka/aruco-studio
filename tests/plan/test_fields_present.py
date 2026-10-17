"""M8b2 (ST-FIELDS-PRESENT): plan/fields.py carries what a renderer needs,
so the Studio's form (and later the Fusion dialog, M7.5) holds no second
copy: tab, icon, show_when, anchor, unit, step, drag, preset.

These pin the presentation keys to the old hand-written tables they replace
(the Studio's layout.ts, deleted in M8b2) and check that every anchor ends
at a row that is always drawn."""
from __future__ import annotations

from aruco_studio.core import board as _B
from aruco_studio.plan.fields import ROWS_OUTSIDE, TABS, fields, form

ROWS = {r["path"]: r for r in fields()}
TAB_IDS = {t["id"] for t in TABS}
PLACES = TAB_IDS | {"root", "header", "none"}
SHOW_KEYS = {"layouts", "made_by", "target", "values", "truthy", "any_truthy"}


def test_every_row_has_a_tab_and_a_show_when():
    for p, r in ROWS.items():
        assert r["tab"] in PLACES, p
        assert isinstance(r["show_when"], dict), p
        assert set(r["show_when"]) <= SHOW_KEYS, p
        assert isinstance(r["preset"], bool), p


def test_the_tabs_of_layout_ts():
    # the old BY_GROUP / BY_PATH of studio/src/inspector/layout.ts, verbatim
    want = {"settings.layout": "marker", "settings.dictionary": "marker", "numbers.marker_id": "marker",
            "numbers.size": "marker", "numbers.square": "marker", "settings.force": "marker",
            "settings.turn": "marker", "settings.corner_mark": "marker",
            "settings.quiet_modules": "print", "settings.grow": "print", "settings.cells": "print",
            "settings.mode": "heights", "settings.op": "heights", "numbers.white_height": "heights",
            "settings.pin": "heights", "numbers.pin_size": "heights",
            "settings.label.on": "label", "settings.label.place": "label",
            "settings.label.rule": "advanced", "settings.origin_v": "advanced",
            "target.kind": "advanced", "target.z_sign": "advanced",
            "settings.trim": "advanced", "settings.trim.margin_mm": "advanced", "key": "advanced",
            "name": "header", "target.loops_mm": "none", "target.w_mm": "none"}
    for p, t in want.items():
        assert ROWS[p]["tab"] == t, (p, ROWS[p]["tab"], t)


def test_the_m6_rows_have_their_place():
    # the sticker's rows on the Print tab, Holes and Perimeter on Marker,
    # Made by under the Preset (a read-only line), the Make rule in Advanced
    assert ROWS["settings.make.thickness_mm"]["tab"] == "print"
    assert ROWS["settings.make.margin_mm"]["tab"] == "print"
    assert ROWS["settings.make.cut_line"]["tab"] == "print"
    assert ROWS["settings.holes"]["tab"] == "marker"
    assert ROWS["settings.make.perimeter"]["tab"] == "marker"
    assert ROWS["settings.make.by"]["tab"] == "root" and ROWS["settings.make.by"]["read_only"]
    assert ROWS["settings.make"]["tab"] == "advanced"


def test_show_when_follows_intent_and_layouts():
    for p, r in ROWS.items():
        sw = r["show_when"]
        if r["intent"] == "3d":
            assert sw.get("made_by") == ["print3d"], p
        elif r["intent"] == "2d" and p != "settings.make.perimeter":
            assert sw.get("made_by") == ["sticker"], p
        else:
            assert "made_by" not in sw, p
        if r.get("layouts"):
            assert sw["layouts"] == r["layouts"], p
        if r.get("hidden_layouts"):
            assert set(sw["layouts"]) == set(_B.LAYOUTS) - set(r["hidden_layouts"]), p
    # on a 3D tag the Perimeter row IS Trim excess: shown for both kinds
    assert ROWS["settings.make.perimeter"]["on_3d"] == "settings.trim"
    assert "made_by" not in ROWS["settings.make.perimeter"]["show_when"]
    assert ROWS["settings.holes"]["show_when"]["target"] == ["holes"]
    assert ROWS["settings.label.text"]["show_when"] == {"truthy": ["settings.label.on"],
                                                        "values": {"settings.label.content": ["custom"]}}
    assert ROWS["numbers.pin_size"]["show_when"]["values"] == {"settings.pin": ["triangle", "round"]}
    assert ROWS["settings.op"]["show_when"]["values"] == {"settings.mode": ["both"]}
    assert ROWS["settings.force"]["show_when"]["truthy"] == ["numbers.size"]
    assert ROWS["settings.label.offset_x_mm"]["show_when"]["any_truthy"] == [
        "settings.label.offset_x_mm", "settings.label.offset_y_mm"]


def _always_drawn(p: str) -> bool:
    if p in ROWS_OUTSIDE:
        return True
    r = ROWS[p]
    return r["tab"] in PLACES - {"none"} and not r["show_when"]


def test_every_anchor_ends_at_a_row_always_drawn():
    for p, r in ROWS.items():
        seen = [p]
        q = r.get("anchor")
        while q is not None and not _always_drawn(q):
            assert q in ROWS, (p, q)
            assert q not in seen, ("anchor loop", seen + [q])
            seen.append(q)
            q = ROWS[q].get("anchor")
        if r["show_when"] or r["tab"] == "none":
            # a row that can be hidden says where its messages go
            assert q is not None and _always_drawn(q), (p, seen)


def test_icons_of_choices():
    lay = {c["value"]: c["icon"] for c in ROWS["settings.layout"]["choices"]}
    assert lay == {"single": "single", "grid": "grid", "charuco": "charuco"}
    mark = {c["value"]: c["icon"] for c in ROWS["settings.corner_mark"]["choices"]}
    assert mark == {"none": "cm-none", "cut": "cm-cut", "triangle": "cm-tri"}
    assert ROWS["settings.turn"]["icons_by_layout"]["single"]["0"] == "up-t"
    assert set(ROWS["settings.turn"]["icons_by_layout"]) == set(_B.LAYOUTS)


def test_units_steps_drag_preset():
    assert ROWS["numbers.size"]["unit"] == "mm" and ROWS["numbers.size"]["drag"] == "size-arrow"
    assert ROWS["numbers.black_height"]["drag"] == "height-arrow"
    assert ROWS["settings.label.x_mm"]["drag"] == "label-xy"
    assert ROWS["settings.quiet_modules"]["unit"] == "modules"
    for p, r in ROWS.items():
        if r["type"] == "mm":
            assert r["unit"] == "mm" and r["step"] > 0, p
    assert ROWS["settings.dictionary"]["preset"] and ROWS["settings.label.nozzle_mm"]["preset"]
    assert not ROWS["numbers.size"]["preset"] and not ROWS["settings.layout"]["preset"]


def test_the_form_doc():
    f = form()
    assert f["schema"] == "arucostudio.form/1" and f["contract"] == "bam.form/1"
    assert [t["id"] for t in f["tabs"]] == ["marker", "heights", "print", "label", "advanced"]
    assert f["outside"] == ["target", "preset", "name"]
    # the presentation keys change no value: every row keeps its old keys
    for r in f["fields"]:
        assert {"path", "group", "type", "label", "default", "intent"} <= set(r)
