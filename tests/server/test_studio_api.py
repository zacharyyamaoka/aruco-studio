"""M3: the routes the Studio web app added to the server (additive).

/api/new (a fresh tag as today's dialog makes it), /api/preset/apply and
/api/preset/of (a preset on a tag and back), the Library's state, Select
and Edit (REF aruco_preset_library.Library on the Studio's store), the top
view (?top=1), the verify raster (image) and inline scene exports."""
from __future__ import annotations

import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ARUCO_STUDIO_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("ARUCO_STUDIO_SCENES", str(tmp_path / "scenes"))
    monkeypatch.setenv("BAM_ARUCO_PRUSASLICER_DIR", str(ROOT / "goldens" / "prusaslicer"))
    from aruco_studio.server import app as A
    from aruco_studio.scene import Scene
    A.STATE["scene"] = Scene(name="untitled")
    return TestClient(A.app)


def test_new_tag_is_what_todays_dialog_stores(client):
    from aruco_studio.core import autosize, label, origin, presets
    for layout in ("single", "grid", "charuco"):
        sp = client.post("/api/new", json={"layout": layout, "target_key": "box40"}).json()
        s, n = sp["settings"], sp["numbers"]
        assert s["layout"] == layout and s["v"] == 2
        assert s["origin_v"] == origin.ORIGIN_RULE
        assert s["label"]["rule"] == label.NEW_RULE           # M6a: rule 3 beside 2
        assert s["cells"] == presets.cell_setting(presets.default_preset())
        assert s["cells"]["rule"] == autosize.CELL_RULE
        assert s["mode"] == "black"                         # Auto on a body (resolve_mode)
        for k in ("jo_v", "host_xform", "key", "has_body"):
            assert k not in s
        p = client.post("/api/plan", json=sp).json()
        assert p["ok"], p["errors"]
        assert not any(w["level"] == "error" for w in p["warnings"])
    no_body = client.post("/api/new", json={"layout": "single", "target_key": "box40",
                                            "thickness_mm": 0.0}).json()
    assert no_body["settings"]["mode"] == "both"            # Auto without a body
    typed = client.post("/api/new", json={"layout": "grid", "target": {
        "kind": "face", "w_mm": 90.0, "h_mm": 60.0, "has_body": False}}).json()
    assert typed["target"]["w_mm"] == 90.0
    assert client.post("/api/new", json={"target_key": "nope"}).status_code == 404
    assert client.post("/api/new", json={"preset": "nope"}).status_code == 404
    assert client.post("/api/new", json={"layout": "hexagon"}).status_code == 422


def test_preset_apply_and_back(client):
    from aruco_studio.core import presets as P
    sp = client.post("/api/new", json={"layout": "grid", "target_key": "plate_hole",
                                       "marker_id": 7}).json()
    sp["settings"]["turn"] = 90
    sp["numbers"]["size"] = 12.0
    cat = client.get("/api/presets").json()["items"]
    aruco = next(i for i in cat if "Aruco" in i["name"] and "0.6" in i["name"])
    got = client.post("/api/preset/apply", json={"spec": sp, "name": aruco["name"]}).json()
    # kept: the layout, ids, size, Origin, target
    assert got["settings"]["layout"] == "grid" and got["settings"]["turn"] == 90
    assert got["numbers"]["marker_id"] == 7 and got["numbers"]["size"] == 12.0
    assert got["target"] == sp["target"]
    assert got["settings"]["cells"] == P.cell_setting(aruco["preset"])
    back = client.post("/api/preset/of", json={"spec": got}).json()
    assert P.same_print(back["preset"], aruco["preset"])
    assert back["matches"] == aruco["name"]
    d = client.post("/api/preset/of", json={"spec": sp}).json()
    assert d["matches"] == "Default"
    assert client.post("/api/preset/apply", json={"spec": sp, "name": "nope"}).status_code == 404


def test_library_state_select_edit_recent(client):
    sp = client.post("/api/new", json={"layout": "single"}).json()
    client.post("/api/scene/tags", json={"spec": sp, "x_mm": 0.0, "y_mm": 0.0})
    st = client.get("/api/library", params={"tag": "tag1"}).json()
    ids = {c["id"]: c for c in st["cards"]}
    assert "builtin:Default" in ids and st["dialog"] is True
    assert {c["id"] for c in st["collections"]} == {"recent", "document", "mine", "prusa",
                                                     "builtin"}
    assert ids["builtin:Default"]["used"] == 1 and "document" in ids["builtin:Default"]["in"]
    assert ids["builtin:Default"]["thumb"].startswith("<svg")
    assert ids["builtin:Default"]["differs"] == ""          # the tag is Default's
    prusa = [c for c in st["cards"] if c["kind"] == "prusa"]
    assert prusa and all(c["subtitle"] for c in prusa)
    # Select a PrusaSlicer profile: imported as mine, recent
    pc = next(c for c in prusa if not c.get("unreadable"))
    r = client.post("/api/library/select", json={"id": pc["id"]}).json()
    assert r["name"] == pc["name"]
    st = client.get("/api/library").json()
    mine = [c for c in st["cards"] if c["kind"] == "user"]
    assert [c["name"] for c in mine] == [pc["name"]]
    assert client.get("/api/library/recent").json()["recent"][0] == pc["name"]
    # Edit -> Save; rename
    r = client.post("/api/library/save", json={"id": mine[0]["id"], "name": "Mine 0.6",
                                               "values": {"tag.quiet_modules": "1.5"}}).json()
    assert r["name"] == "Mine 0.6"
    st = client.get("/api/library").json()
    c = next(c for c in st["cards"] if c["name"] == "Mine 0.6")
    assert c["preset"]["tag"]["quiet_modules"] == 1.5
    assert pc["name"] not in client.get("/api/library/recent").json()["recent"]
    assert client.post("/api/library/save", json={"id": "builtin:Default",
                                                  "values": {}}).status_code == 400
    assert client.post("/api/library/select", json={"id": "nope"}).status_code == 404
    client.post("/api/library/recent", json={"name": "Mine 0.6"})
    assert client.delete("/api/presets/Mine 0.6").status_code == 200
    assert "Mine 0.6" not in client.get("/api/library/recent").json()["recent"]


def test_top_view_verify_image_inline_export(client):
    sp = client.post("/api/new", json={"layout": "single"}).json()
    p = client.post("/api/plan?top=1", json=sp).json()
    assert set(p["top"]) >= {"black", "body"}
    client.post("/api/scene/tags", json={"spec": sp, "x_mm": 0.0, "y_mm": 0.0})
    sc = client.get("/api/scene?plans=1&top=1").json()
    assert "top" in sc["tags"][0]["plan"]
    v = client.post("/api/verify", json={"spec": sp, "px_per_mm": 10.0, "pose": False,
                                         "image": True}).json()
    assert v["ok"] and base64.b64decode(v["image_png"])[:8] == b"\x89PNG\r\n\x1a\n"
    e = client.post("/api/scene/export/svg?save=1&inline=1").json()
    assert e["files"] and Path(e["files"][0]).exists()
    assert base64.b64decode(e["inline"]["sheet.svg"]).startswith(b"<svg")


def test_target_editor(client):
    b = client.post("/api/target", json={"shape": "box", "w_mm": 60.0, "h_mm": 30.0,
                                          "thickness_mm": 2.0}).json()
    assert b["w_mm"] == 60.0 and b["h_mm"] == 30.0 and b["has_body"]
    assert b["body_mm"]["z0"] == -2.0
    h = client.post("/api/target", json={"shape": "box", "w_mm": 60.0, "h_mm": 40.0,
                                          "holes": [[20.0, 0.0, 6.0]], "thickness_mm": 0.0}).json()
    assert len(h["loops_mm"]) == 2 and not h["has_body"]
    d = client.post("/api/target", json={"shape": "disc", "r_mm": 25.0}).json()
    assert abs(d["w_mm"] - 50.0) < 0.1
    f = client.post("/api/target", json={"shape": "face", "key": "ring"}).json()
    assert len(f["loops_mm"]) == 2
    assert client.post("/api/target", json={"shape": "face", "key": "nope"}).status_code == 404
    r = client.post("/api/target", json={"shape": "box", "w_mm": -1.0})
    assert r.status_code == 422 and r.json()["detail"][0]["path"] == "w_mm"
    for t in (b, h, d, f):
        sp = client.post("/api/new", json={"layout": "single", "target": t}).json()
        assert client.post("/api/plan", json=sp).json()["ok"]


def test_options_carry_the_origin_words(client):
    from aruco_studio.core import origin
    o = client.get("/api/options").json()["origin"]
    assert [x["value"] for x in o["single"]] == list(origin.TURNS_CW)
    assert o["grid"][0]["label"] == origin.label("grid", 0)
