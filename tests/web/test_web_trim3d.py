"""The 3D white is the sticker as it is cut (Zach, 2026-10-21; the printdims
lane found it): with Trim = Marker the canvas fills the quiet-zone box white
and the sheet cuts it (112 x 40 for a 123.5 x 40 profile holding a 3 x 1
grid of 30 mm markers), but a 3D-printed preset's white tile stayed the
core's rectangle -- 123.5 wide -- and, under Trim Profile, stopped short of
an outside label's band.

One geometry: `cut_shape`, the polygon the canvas fills and the sheet cuts.
The plan's white layer of the base the marker sits on (the 3D print's tile,
the inkjet's sticker) is that polygon, whatever the trim, the marker, the
label or the profile. A request with no profile (Fusion, old callers) keeps
the core's tile byte for byte."""
from __future__ import annotations

import copy

import pytest

from aruco_studio import web_api as W

from test_web_printdims import LABELS, MARKERS, PRESETS, PROFILES, request

PRINT3D = next(p for p in W.presets() if p["method"] == "print3d")
BASES = ("tile", "sticker")


def box(polys):
    xs = [p[0] for q in polys for p in q["outer"]]
    ys = [p[1] for q in polys for p in q["outer"]]
    return [min(xs), min(ys), max(xs), max(ys)]


def planned(profile, marker, label, trim, preset, mode=None):
    r = request(profile, MARKERS[marker], label, trim, 0, "letter")
    r["preset"] = copy.deepcopy(preset)
    if mode:
        r["extrude"] = {"mode": mode}
    return r, W.plan(r)


def whites(p):
    return [L for L in p["layers"] if L["op"] == "add" and L["colour"] == "white" and L["part"] in BASES]


CASES = [(prof, mk, trim, label) for prof in PROFILES for mk in MARKERS for trim in ("profile", "marker")
         for label in LABELS]


@pytest.mark.parametrize("preset", [PRINT3D, PRESETS["letter"]], ids=["print3d", "inkjet"])
@pytest.mark.parametrize("prof,mk,trim,label", CASES, ids=["-".join(c) for c in CASES])
def test_the_white_base_is_the_cut(prof, mk, trim, label, preset):
    _r, p = planned(prof, mk, label, trim, preset)
    if not p["ok"]:
        pytest.skip("not planned")
    got = whites(p)
    if not got:
        # a 3D print on a face (a plate's profile) has no tile: the plate is the body, the black is let into it
        assert preset is PRINT3D and prof.startswith("face"), [(L["name"], L["part"]) for L in p["layers"]]
        return
    assert len(got) == 1, [(L["name"], L["part"]) for L in p["layers"]]
    assert got[0]["polygons"] == [p["cut_shape"]], "the white base is the cut, polygon for polygon"


def test_zachs_grid_trimmed_to_the_marker_is_112_wide_in_3d_too():
    _r, p = planned("rect-123.5x40", "grid-3x1", "off", "marker", PRINT3D)
    x0, y0, x1, y1 = box(whites(p)[0]["polygons"])
    assert (round(x1 - x0, 3), round(y1 - y0, 3)) == (112.0, 40.0)
    _r, q = planned("rect-123.5x40", "grid-3x1", "off", "profile", PRINT3D)
    x0, y0, x1, y1 = box(whites(q)[0]["polygons"])
    assert (round(x1 - x0, 3), round(y1 - y0, 3)) == (123.5, 40.0)


def test_the_tile_keeps_its_height_and_its_pockets():
    """Only the polygon is the cut's: z, the pocket and the black are the core's."""
    _r, p = planned("rect-123.5x40", "grid-3x1", "off", "marker", PRINT3D)
    names = {L["name"]: L for L in p["layers"]}
    assert names["tile"]["z"][0] == 0.0 and names["tile"]["z"][1] > 0.0
    assert names["pocket"]["op"] == "cut" and names["pocket"]["into"] == "tile"
    assert names["pattern"]["colour"] == "black"


@pytest.mark.parametrize("mk", list(MARKERS))
def test_a_rect_only_request_keeps_the_cores_tile(mk, monkeypatch):
    """Fusion and old callers send a rect and no profile: their layers are what
    cad_layers answered before (cut_tile off), byte for byte."""
    r = request("rect-123.5x40", MARKERS[mk], "off", "profile")
    r["preset"] = copy.deepcopy(PRINT3D)
    del r["profile"]
    r["rect"] = {"cx": 0.0, "cy": 0.0, "w": 123.5, "h": 40.0, "angle_deg": 0.0}
    now = W.plan(r)["layers"]
    real = W.cad_layers
    monkeypatch.setattr(W, "cad_layers", lambda *a, **k: real(*a, **{**k, "cut_tile": False}))
    assert W.plan(r)["layers"] == now
    assert any(L["part"] == "tile" for L in now)
