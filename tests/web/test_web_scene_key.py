"""web_api.scene_key: what a camera sees of a marker, in its own frame, as the
key Verify's range cache uses (web/src/verify/range.ts). The canvas proposals
measured it on 8 real edits (docs/build_verify_canvas_proposals.py, 2026-10-21):
a move or a turn must keep it (a 6-26 s range is not re-run), every edit that
changes what the camera reads must change it -- and so must one that changes
only how OpenCV reads it (the dictionary). Standard library only, and the same
in Pyodide (web/scripts/parity.d/scene_key.mjs)."""
from __future__ import annotations

import copy
import json
import math

import pytest

from aruco_studio import web_api as W

INK = copy.deepcopy(next(p for p in W.presets() if p["name"] == "Inkjet · Letter vinyl"))
D3 = copy.deepcopy(next(p for p in W.presets() if p["method"] == "print3d"))


def corners(cx, cy, w, h, angle_deg):
    """web/src/model/geom.ts rectCorners: the profile the Studio sends for a rectangle."""
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    return [[cx + u * c - v * s, cy + u * s + v * c] for u, v in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2))]


def req(cx=12.0, cy=-7.0, w=30.0, h=30.0, angle=0.0, marker=None, label=None, preset=None):
    """A rectangle profile with one marker and its label on the marker, as the Studio sends it (B1 of the guide)."""
    m = {"type": "single", "dictionary": "DICT_4X4_50", "first_id": 1, "auto": True, "marker_mm": 30.0, "checker_mm": 0.0,
         "separation_mm": 0.0, "cols": 1, "rows": 1, "turn": 0, "flip": False, "quiet_modules": 1, "corner_mark": "none"}
    m.update(marker or {})
    lb = {"on": True, "text": "#{ids}", "height_mm": 0.0, "side": "below", "gap_mm": 2.0, "offset_mm": [0.0, 0.0],
          "place": "on_marker", "surface": "black"}
    lb.update(label or {})
    return {"trim": "profile", "profile": {"loops": [corners(cx, cy, w, h, angle)]}, "holes": "avoid", "marker": m,
            "label": lb, "preset": preset or INK, "reference_face": False, "extrude": {}}


def request_key(r):
    """Today's key before this change (range.ts rangeKey): the whole request."""
    return json.dumps(r, sort_keys=True)


KEEPS = [
    ("move the marker 10 mm on the page", dict(cx=22.0, cy=-14.0)),
    ("turn the profile 30°", dict(angle=30.0)),
    ("move and turn 135°", dict(cx=-40.5, cy=61.25, angle=135.0)),
]
CHANGES = [
    ("grow the profile 30 -> 36 mm (marker Auto)", dict(w=36.0, h=36.0)),
    ("Re-ID #1 -> #31", dict(marker={"first_id": 31})),
    ("label text #{ids} -> #{ids} {dict}", dict(label={"text": "#{ids} {dict}"})),
    ("label height typed 3.75 mm", dict(label={"height_mm": 3.75})),
    ("corner mark: triangle", dict(marker={"corner_mark": "triangle"})),
    ("label off", dict(label={"on": False})),
    ("label on the quiet zone (white surface)", dict(label={"surface": "white"})),
    ("flip", dict(marker={"flip": True})),
    ("the dictionary only: 4X4_50 -> 4X4_100, the same id and cells", dict(marker={"dictionary": "DICT_4X4_100"})),
    ("a typed size, 25 mm", dict(marker={"auto": False, "marker_mm": 25.0})),
    ("the 3D-print preset", dict(preset=D3)),
]


@pytest.mark.parametrize("what,edit", KEEPS, ids=[k for k, _ in KEEPS])
def test_a_move_or_a_turn_keeps_the_key(what, edit):
    a, b = req(), req(**edit)
    assert request_key(a) != request_key(b), "the ruler can fail: the request itself changed"
    assert W.scene_key(a) == W.scene_key(b), what


@pytest.mark.parametrize("what,edit", CHANGES, ids=[k for k, _ in CHANGES])
def test_what_changes_the_read_changes_the_key(what, edit):
    assert W.scene_key(req()) != W.scene_key(req(**edit)), what


def test_the_same_marker_moved_keeps_any_edit_it_has():
    """A move keeps the key of an edited marker too (a grid with a label and a mark, turned 90° on the page)."""
    g = dict(marker={"type": "grid", "cols": 3, "rows": 1, "first_id": 19, "corner_mark": "triangle"}, w=123.5, h=40.0)
    assert W.scene_key(req(**g)) == W.scene_key(req(cx=-80.0, cy=55.5, angle=90.0, **g))


def test_a_rect_request_and_none_for_nothing_to_plan():
    r = req()
    rect = dict(r, rect={"cx": 5.0, "cy": 6.0, "w": 30.0, "h": 30.0, "angle_deg": 20.0})
    rect.pop("profile")
    moved = dict(rect, rect=dict(rect["rect"], cx=-50.0, angle_deg=-70.0))
    assert W.scene_key(rect) == W.scene_key(moved) and len(W.scene_key(rect)) == 32
    assert W.scene_key(req(w=1.0, h=1.0)) is None                  # nothing fits
    got = json.loads(W.call("scene_keys", json.dumps({"reqs": [req(), {"bad": 1}, req(cx=99.0)]})))["result"]
    assert got[0] == got[2] == W.scene_key(req()) and got[1] is None
