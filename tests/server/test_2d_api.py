"""The 2D model over HTTP (2026-10-17, Zach's 2D pivot): the inkjet rows of
/api/form, /api/new under the vinyl presets (make rule 2) and the older
ones (rule 1), the preset match, the Library's Inkjet printers (their own
Edit form), the sheet's Sticker margin and Cut lines on every sheet
route, and the design sugar (`shift`, `paper_mm`). TestClient: no port."""
from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
VINYL = "Inkjet · Letter vinyl"
OLD = "Sticker · Letter · 600 dpi"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ARUCO_STUDIO_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("ARUCO_STUDIO_SCENES", str(tmp_path / "scenes"))
    monkeypatch.setenv("BAM_ARUCO_PRUSASLICER_DIR", str(ROOT / "goldens" / "prusaslicer"))
    from aruco_studio.server import app as A
    from aruco_studio.server import design_api as DA
    from aruco_studio.server import sheet_api  # noqa: F401  (installs the routes)
    from aruco_studio.scene import Scene
    A.STATE["scene"] = Scene(name="twod")
    c = TestClient(A.app)
    yield c
    DA.D.unbind()


def test_the_form_has_the_inkjet_rows(client):
    f = client.get("/api/form").json()
    rows = {r["path"]: r for r in f["fields"]}
    th = rows["settings.make.thickness_mm"]
    assert th["label"] == "Paper thickness" and th["intent"] == "2d" and th["tab"] == "print"
    assert [s["value"] for s in th["suggestions"]][0] == 0.1 and "measure" in th["hint"]
    pg = rows["settings.make.page"]
    assert [c["value"] for c in pg["choices"]][:2] == ["letter", "a4"]
    assert pg["show_when"] == {"made_by": ["sticker"], "values": {"settings.make.rule": [2]}}
    assert rows["settings.make.page_margin_mm"]["show_when"]["values"] == {"settings.make.rule": [2]}
    for p in ("settings.make.margin_mm", "settings.make.cut_line"):   # rule 1's own (Q7)
        assert rows[p]["show_when"]["values"] == {"settings.make.rule": [1]}
    sh = rows["settings.shift"]
    assert sh["type"] == "shift" and sh["tab"] == "marker" and sh["drag"] == "shift-xy"
    assert sh["show_when"]["made_by"] == ["sticker"] and sh["anchor"] == "numbers.size"
    tabs = {t["id"]: t for t in f["tabs"]}
    assert tabs["print"]["name"] == "Print" and tabs["print"]["name_2d"] == "Inkjet"
    assert f["rules"]["make"] == 1 and f["rules"]["make_new_2d"] == 2 and f["rules"]["shift"] == 1
    made = rows["settings.make.by"]
    assert [c["label"] for c in made["choices"]] == ["3D printed", "Inkjet printer"]


def test_new_tags_under_each_inkjet_preset(client):
    for preset, rule in ((VINYL, 2), ("Inkjet · A4 vinyl", 2), (OLD, 1)):
        sp = client.post("/api/new", json={"layout": "single", "target_key": "box40",
                                           "thickness_mm": 0, "preset": preset}).json()
        mk = sp["settings"]["make"]
        assert mk["rule"] == rule and mk["by"] == "sticker", preset
        p = client.post("/api/plan", json=sp).json()
        assert p["ok"] and p["frames"]["detector_z_mm"] == pytest.approx(0.1 if rule == 2 else 0.11)
        if rule == 2:
            assert mk["page"] == ("a4" if "A4" in preset else "letter")
            assert p["parts"] == ["sticker", "pocket", "ink"] and p["sticker"]["frame_z_mm"] == 0.1
        else:
            assert p["parts"] == ["sticker", "ink"] and "sticker" not in p
        # the Preset row finds the preset the tag was made with
        got = client.post("/api/preset/of", json={"spec": sp}).json()
        assert got["matches"] == preset, (preset, got["matches"])
    # made_by sticker with no sticker preset: rule 2
    o = client.post("/api/new", json={"layout": "single", "target_key": "box40",
                                      "made_by": "sticker"}).json()
    assert o["settings"]["make"]["rule"] == 2


def test_a_preset_pick_turns_a_tag_into_that_sticker(client):
    sp = client.post("/api/new", json={"layout": "single", "target_key": "box40",
                                       "thickness_mm": 0, "preset": OLD}).json()
    got = client.post("/api/preset/apply", json={"spec": sp, "name": "Inkjet · A4 vinyl"}).json()
    assert got["settings"]["make"]["rule"] == 2 and got["settings"]["make"]["page"] == "a4"
    assert client.post("/api/preset/of", json={"spec": got}).json()["matches"] == "Inkjet · A4 vinyl"


def test_the_library_lists_the_inkjet_printers_with_their_own_form(client):
    lib = client.get("/api/library").json()
    cols = {c["id"]: c for c in lib["collections"]}
    assert cols["stickers"]["name"] == "Inkjet printers"
    cards = {c["name"]: c for c in lib["cards"]}
    assert "stickers" in cards[VINYL]["in"] and "stickers" not in cards[OLD]["in"]
    assert cards[VINYL]["edit"] == "2d" and cards["Default"]["edit"] == "3d"
    assert cards[VINYL]["subtitle"] == "Letter · paper 0.1 mm · 600 dpi"
    info = dict(cards[VINYL]["info"])
    rows = dict(info["Inkjet printer"])
    assert rows["Paper thickness"].startswith("0.1 mm") and rows["Make rule"].startswith("2")
    paths = [r[0] for r in lib["schema_2d"]]
    assert paths[:5] == ["profile.name", "profile.page", "profile.stock_mm", "profile.margin_mm",
                         "profile.dpi"]
    assert "profile.nozzle_mm" not in paths and "tag.pin" not in paths
    # an inkjet preset of mine: Edit -> Save with 1200 dpi re-derives the dot
    from aruco_studio.core import presets as P
    p = P.vinyl_preset("letter")
    p["name"] = "my vinyl"
    assert client.post("/api/presets", json={"name": "my vinyl", "preset": p}).status_code == 200
    r = client.post("/api/library/save", json={"id": "user:my vinyl", "name": "my vinyl",
                                               "values": {"profile.dpi": 1200,
                                                          "profile.stock_mm": 0.12,
                                                          "profile.page": "a4"}})
    assert r.status_code == 200, r.text
    mine = {i["name"]: i for i in client.get("/api/presets").json()["items"]}["my vinyl"]["preset"]
    assert mine["profile"]["dpi"] == 1200 and mine["profile"]["line_mm"] == round(25.4 / 1200, 6)
    assert mine["profile"]["stock_mm"] == 0.12 and mine["profile"]["page"] == "a4"
    assert mine["profile"]["make_rule"] == 2
    bad = client.post("/api/library/save", json={"id": "user:my vinyl", "name": "my vinyl",
                                                 "values": {"profile.stock_mm": 9}})
    assert bad.status_code == 422


def test_the_inkjet_limits_are_what_a_sticker_preset_keeps():
    """As audit F16 for LIMITS: inside kept, outside dropped (the default)."""
    from aruco_studio.core import presets as P
    from aruco_studio.server import library as L
    for path, (lo, hi) in L.LIMITS_2D.items():
        for v, kept in ((lo, True), (hi, True), (lo - 0.01, False), (hi + 0.01, False)):
            p = P.vinyl_preset("letter")
            P.set_path(p, path, int(v) if path == "profile.dpi" and float(v).is_integer() else v)
            got = P.normalise(p)
            a, b = path.split(".")
            assert (got[a][b] == v) == kept, (path, v, got[a][b])
    assert set(L.LIMITS_2D) == {p for p, _l, k, _o in P.inkjet_schema() if k == "number"
                                and p.startswith("profile.")}


def _open(client, tmp_path, name):
    p = tmp_path / f"{name}.arucostudio.json"
    p.write_text((ROOT / "examples" / "gallery" / f"{name}.arucostudio.json").read_text(
        encoding="utf-8"), encoding="utf-8")
    r = client.post("/api/design/open", json={"path": str(p)})
    assert r.status_code == 200 and r.json()["state"] == "ok", r.text
    return p


def test_the_sheet_routes_take_the_margin_and_the_cut_lines(client, tmp_path):
    _open(client, tmp_path, "sheet_options")
    q = "page=letter&mode=spaced"
    plain = client.get(f"/api/scene/sheet.json?{q}").json()
    grown = client.get(f"/api/scene/sheet.json?{q}&sticker_margin_mm=3").json()
    assert "sticker_margin_mm" not in plain and grown["sticker_margin_mm"] == 3.0
    a = {s["key"]: s for s in plain["stickers"]}
    for s in grown["stickers"]:
        w0, h0 = a[s["key"]]["w_mm"], a[s["key"]]["h_mm"]
        if s["rotation"] == a[s["key"]]["rotation"]:
            assert (s["w_mm"], s["h_mm"]) == pytest.approx((w0 + 6, h0 + 6), abs=0.02)
    off = client.get(f"/api/scene/sheet.json?{q}&cut_lines=false").json()
    assert off["cut_lines"] is False
    svg = client.get(f"/api/scene/sheet.svg?{q}&cut_lines=false").text
    assert "data-cut=" not in svg and "data-cut=" in client.get(f"/api/scene/sheet.svg?{q}").text
    pdf = client.get(f"/api/scene/print.pdf?{q}&sticker_margin_mm=3").content
    assert pdf.startswith(b"%PDF")
    r = client.post("/api/scene/export/print", json={"page": "letter", "mode": "spaced",
                                                    "sticker_margin_mm": 3, "cut_lines": True,
                                                    "inline": True, "sheet_only": True}).json()
    sheet = json.loads(base64.b64decode(r["inline"]["sheet.json"]))
    assert sheet["sticker_margin_mm"] == 3.0
    v = client.post("/api/scene/verify/sheet", json={"page": "letter", "mode": "tight",
                                                     "sticker_margin_mm": 3, "cut_lines": False,
                                                     "dpi": 300}).json()
    assert all(s["outline"].get("off") for s in v["stickers"])
    assert client.get(f"/api/scene/sheet.json?{q}&sticker_margin_mm=30").status_code == 422


def test_the_design_sugar_shift_and_paper(client, tmp_path):
    _open(client, tmp_path, "shift")
    tags = {t["name"]: t for t in client.get("/api/scene?plans=1").json()["tags"]}
    moved = tags["moved"]
    assert moved["spec"]["settings"]["shift"] == {"rule": 1, "x_mm": 20.0, "y_mm": 8.0}
    assert moved["plan"]["placement"]["shift_mm"] == [20.0, 8.0]
    _open(client, tmp_path, "inkjet_paper")
    tags = {t["name"]: t for t in client.get("/api/scene?plans=1").json()["tags"]}
    assert tags["real"]["spec"]["settings"]["make"]["thickness_mm"] == 0.1
    assert tags["shown"]["spec"]["settings"]["make"]["thickness_mm"] == 2.0
    assert tags["shown"]["plan"]["sticker"]["ink_z_mm"] == [1.0, 2.0]
    # junk sugar is an error on its path
    from aruco_studio.scene import design as DS
    from aruco_studio.scene import loads_design
    doc = json.loads((ROOT / "examples" / "gallery" / "shift.arucostudio.json").read_text(
        encoding="utf-8"))
    doc["features"][1]["shift"] = [1, "far"]
    _sc, issues = DS.compile(loads_design(json.dumps(doc)), None)
    assert any(i.field == "features[1].shift" and i.level == "error" for i in issues)
