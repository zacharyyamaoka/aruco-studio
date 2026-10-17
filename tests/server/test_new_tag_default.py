"""POST /api/new's default (2026-10-17, CF-13: inkjet on vinyl is the only
way Zach makes tags now): a request naming no preset and no `made_by` is
made under core.presets.NEW_TAG_PRESET ("Inkjet · Letter vinyl": make rule
2, by sticker); a named preset ("Default" for today's 3D tag) or
`made_by` decide exactly as before; GET /api/presets names the new-tag
preset for the Studio's form. A design file's sugar is not a new tag of
this route: it keeps its file's preset. TestClient: no port."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aruco_studio.core import presets as P

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ARUCO_STUDIO_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("ARUCO_STUDIO_SCENES", str(tmp_path / "scenes"))
    monkeypatch.setenv("BAM_ARUCO_PRUSASLICER_DIR", str(ROOT / "goldens" / "prusaslicer"))
    from aruco_studio.server import app as A
    from aruco_studio.scene import Scene
    A.STATE["scene"] = Scene(name="newtag")
    return TestClient(A.app)


def _new(client, **body):
    r = client.post("/api/new", json=dict({"target_key": "box40"}, **body))
    assert r.status_code == 200, r.text
    return r.json()


def test_naming_nothing_makes_an_inkjet_letter_vinyl_sticker(client):
    for layout in ("single", "grid", "charuco"):
        sp = _new(client, layout=layout)
        s = sp["settings"]
        mk = s["make"]
        assert mk["by"] == "sticker" and mk["rule"] == 2, layout
        assert mk["page"] == "letter" and mk["thickness_mm"] == P.VINYL_STOCK_MM
        assert (s["mode"], s["op"], s["pin"]) == ("both", "new", "none") and "trim" not in s
        assert s["cells"] == P.cell_setting(P.new_tag_preset())
        assert s["label"]["nozzle_mm"] == P.STICKER_STROKE_MM
        p = client.post("/api/plan", json=sp).json()
        assert p["ok"], p["errors"]
        assert p["made_by"] == "sticker" and p["parts"] == ["sticker", "pocket", "ink"]
        got = client.post("/api/preset/of", json={"spec": sp}).json()
        assert got["matches"] == P.NEW_TAG_PRESET
    # the same as naming it
    assert _new(client, layout="single") == _new(client, layout="single", preset=P.NEW_TAG_PRESET)


def test_default_and_print3d_still_make_todays_3d_tag(client):
    from aruco_studio.core import origin
    d = _new(client, layout="single", preset="Default")
    s = d["settings"]
    assert s["make"] == {"rule": 1, "by": "print3d"}
    assert s["cells"] == P.cell_setting(P.default_preset())
    assert s["mode"] == "black" and s["pin"] == "triangle"          # Auto on a body, as before
    assert s["origin_v"] == origin.ORIGIN_RULE
    p = client.post("/api/plan", json=d).json()
    assert p["ok"] and p["made_by"] == "print3d"
    assert client.post("/api/preset/of", json={"spec": d}).json()["matches"] == "Default"
    # made_by print3d with no preset: the same 3D tag as naming Default
    for layout in ("single", "grid", "charuco"):
        assert _new(client, layout=layout, made_by="print3d") == \
            _new(client, layout=layout, preset="Default"), layout


def test_a_named_preset_or_made_by_sticker_decide_as_before(client):
    a4 = _new(client, layout="single", preset="Inkjet · A4 vinyl")["settings"]["make"]
    assert a4["rule"] == 2 and a4["page"] == "a4"
    old = _new(client, layout="single", preset="Sticker · Letter · 600 dpi")["settings"]["make"]
    assert old["rule"] == 1 and old["by"] == "sticker"
    by = _new(client, layout="grid", made_by="sticker")["settings"]
    assert by["make"]["by"] == "sticker" and by["make"]["rule"] == 2
    assert by["cells"] == P.cell_setting(P.default_preset())        # Default's cells, as before
    assert client.post("/api/new", json={"preset": "nope"}).status_code == 404


def test_the_presets_route_names_the_new_tag_preset(client):
    r = client.get("/api/presets").json()
    assert r["new_tag"] == P.NEW_TAG_PRESET
    it = next(i for i in r["items"] if i["name"] == r["new_tag"])
    assert it["kind"] == "builtin" and it["made_by"] == "sticker" and not it.get("legacy")


def test_the_design_sugar_keeps_its_files_preset():
    from aruco_studio.plan import newtag as NT
    from aruco_studio.plan import target as TG
    tgt = TG.palette(3.0)[0]["target"]
    sp = NT.new_spec("single", tgt)                    # what a file without a preset compiles
    assert sp["settings"]["make"] == {"rule": 1, "by": "print3d"}
