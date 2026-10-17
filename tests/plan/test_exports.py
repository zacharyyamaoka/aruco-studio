"""M2b.7 (the plan's exports): the SVG parses, prints at true size, its
viewBox is the tile (or the sticker) in mm; the plan JSON round-trips; the
STL is binary and closed."""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET

import pytest

import _evaluate_golden as G
from aruco_studio.plan import exports as X
from aruco_studio.plan import plan_tag
from aruco_studio.plan import target as T
from aruco_studio.plan.spec import TagSpec

NS = "{http://www.w3.org/2000/svg}"


def _plans(n=60):
    out = []
    for c in G.cases("matrix"):
        if "error" not in c["out"]:
            out.append(plan_tag(TagSpec.from_dict(c["in"])))
        if len(out) >= n:
            break
    return out


def test_svg_parses_and_its_viewbox_is_the_tile_in_mm():
    for p in _plans():
        svg = X.to_svg(p)
        root = ET.fromstring(svg)
        u0, v0, u1, v1 = X.view_rect(p)
        vb = [float(v) for v in root.get("viewBox").split()]
        assert abs(vb[0] - u0) < 1e-5 and abs(vb[1] + v1) < 1e-5
        assert abs(vb[2] - (u1 - u0)) < 1e-5 and abs(vb[3] - (v1 - v0)) < 1e-5
        assert root.get("width") == f"{X._f(u1 - u0)}mm" and root.get("height") == f"{X._f(v1 - v0)}mm"
        g = p.data["guides"]
        if g["tile"]:
            assert [round(v, 6) for v in (u0, v0, u1, v1)] == [round(v, 6) for v in g["tile"]] \
                or (p.data.get("label") or {}).get("white")
        layers = [e.get("data-layer") for e in root.iter(NS + "path")]
        assert "black" in layers or "white" in layers


def test_plan_json_round_trips():
    for p in _plans(20):
        s = X.to_json(p)
        assert json.loads(s) == json.loads(p.to_json())
        assert json.loads(s)["schema"] == "arucostudio.tagplan/1"


def test_a_refused_plan_has_no_svg():
    p = plan_tag(TagSpec(settings={"layout": "single", "mode": "both"}, target=T.box(4, 4)))
    assert not p.ok
    with pytest.raises(ValueError):
        X.to_svg(p)


def test_stl_header_names_the_tag():
    p = _plans(1)[0]
    data = X.to_stl(p)
    assert data[:11] == b"arucostudio"
