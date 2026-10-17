"""M6.8 / M6a.2 and the sheet routes (server/sheet_api.py), on FastAPI's
TestClient (no port is bound).

* /api/form: every row says where it applies (`intent`);
* /api/new: the preset is the machine (a sticker preset makes a sticker);
  `made_by` overrides it; a sticker has `make` and no trim;
* /api/presets: both kinds, two collections, `?made_by=sticker` lists no
  PrusaSlicer profile;
* PUT /api/remembered round-trips `made_by`;
* a locked tag's PATCH of settings.make is a 409;
* the sheet: sheet.svg, sheet.json, print.pdf (inline; the bytes export/print
  writes), export/print (the bundle on disk, the ledger), verify/sheet.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
STICKER = "Sticker · Letter · 600 dpi"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ARUCO_STUDIO_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("ARUCO_STUDIO_SCENES", str(tmp_path / "scenes"))
    monkeypatch.setenv("BAM_ARUCO_PRUSASLICER_DIR", str(ROOT / "goldens" / "prusaslicer"))
    from aruco_studio.server import app as A
    from aruco_studio.server import sheet_api  # noqa: F401  (installs the routes)
    from aruco_studio.scene import Scene
    A.STATE["scene"] = Scene(name="m6a")
    return TestClient(A.app)


def test_every_form_row_says_where_it_applies(client):
    f = client.get("/api/form").json()
    assert all(r.get("intent") in ("3d", "2d", "both") for r in f["fields"])
    rows = {r["path"]: r for r in f["fields"]}
    assert rows["settings.mode"]["intent"] == "3d" and rows["numbers.white_height"]["intent"] == "3d"
    assert rows["settings.make.thickness_mm"]["intent"] == "2d"
    assert rows["settings.holes"]["intent"] == "both"
    assert rows["settings.make.by"]["read_only"] and rows["settings.label.nozzle_mm"][
        "label_2d"] == "Stroke"
    assert f["rules"]["make"] == 1 and f["rules"]["label_new"] == 3


def test_a_sticker_preset_makes_a_sticker(client):
    sp = client.post("/api/new", json={"layout": "single", "target_key": "box40",
                                       "thickness_mm": 0, "preset": STICKER}).json()
    s = sp["settings"]
    assert s["make"] == {"rule": 1, "by": "sticker", "thickness_mm": 0.1, "margin_mm": 0.0,
                         "cut_line": True, "perimeter": "marker"}
    assert "trim" not in s and s["holes"] == "avoid" and s["label"]["rule"] == 3
    assert s["cells"] == {"rule": 1, "of": "cell", "mm": 0.042333, "min_mm": 1.0}
    assert s["label"]["nozzle_mm"] == 0.2
    p = client.post("/api/plan", json=sp).json()
    assert p["ok"] and p["made_by"] == "sticker" and p["parts"] == ["sticker", "ink"]
    assert p["frames"]["detector_z_mm"] == pytest.approx(0.11)
    # Default: a 3D tag that says so
    d = client.post("/api/new", json={"layout": "single", "target_key": "box40"}).json()
    assert d["settings"]["make"] == {"rule": 1, "by": "print3d"}
    # made_by overrides the preset (scripts)
    o = client.post("/api/new", json={"layout": "grid", "target_key": "box40",
                                      "made_by": "sticker"}).json()
    assert o["settings"]["make"]["by"] == "sticker" and "trim" not in o["settings"]
    bad = client.post("/api/new", json={"layout": "single", "made_by": "laser"})
    assert bad.status_code == 422


def test_presets_both_kinds_two_collections(client):
    r = client.get("/api/presets").json()
    names = [i["name"] for i in r["items"]]
    assert names[0] == "Default" and STICKER in names and "Sticker · A4 · 600 dpi" in names
    by = {i["name"]: i for i in r["items"]}
    assert by[STICKER]["made_by"] == "sticker" and by["Default"]["made_by"] == "print3d"
    cols = {c["id"]: c for c in r["collections"]}
    assert cols["print3d"]["title"] == "3D printers" and cols["sticker"]["title"] == \
        "Sticker printers"
    assert "Default" in cols["print3d"]["names"] and STICKER in cols["sticker"]["names"]
    prusa = [i["name"] for i in r["items"] if i["preset"]["profile"].get("source") == "prusaslicer"]
    assert prusa, "the fixture's Aruco profiles"
    assert set(prusa) <= set(cols["print3d"]["names"])
    st = client.get("/api/presets?made_by=sticker").json()
    assert [i["name"] for i in st["items"]] == [STICKER, "Sticker · A4 · 600 dpi"]
    assert not [i for i in st["items"] if i["preset"]["profile"].get("source") == "prusaslicer"]


def test_remembered_round_trips_made_by(client):
    got = client.put("/api/remembered/aruco_extrude", json={"made_by": "sticker"}).json()
    assert got.get("made_by") == "sticker"
    assert client.get("/api/remembered").json()


def _add(client, settings, target=None, **kw):
    from aruco_studio.plan import target as T
    spec = {"settings": settings, "target": target or T.box(40, 40, 0).to_dict()}
    r = client.post("/api/scene/tags", json=dict({"spec": spec, "number": True}, **kw))
    assert r.status_code == 200, r.text
    return r.json()


def test_a_locked_tag_refuses_a_change_of_make(client):
    t = _add(client, {"layout": "single", "mode": "both", "op": "new"}, locked=True)
    r = client.patch(f"/api/scene/tags/{t['name']}",
                     json={"settings": {"make": {"rule": 1, "by": "sticker"}}})
    assert r.status_code == 409
    assert r.json()["issues"][0]["field"].startswith("settings")


def _sheet_scene(client):
    from aruco_studio.plan import target as T
    stk = {"rule": 1, "by": "sticker"}
    _add(client, {"layout": "single", "make": stk,
                  "label": {"on": True, "rule": 3, "place": "black", "content": "id",
                            "nozzle_mm": 0.2}})
    _add(client, {"layout": "grid", "make": stk}, T.box(80, 50, 0).to_dict(), x_mm=100)
    _add(client, {"layout": "single", "make": dict(stk, perimeter="profile")},
         T.from_face("disc4").to_dict(), y_mm=100)
    _add(client, {"layout": "single", "mode": "both", "op": "new"}, T.box(40, 40, 3).to_dict(),
         x_mm=200)


def test_the_sheet_routes(client):
    _sheet_scene(client)
    svg = client.get("/api/scene/sheet.svg?mode=tight")
    assert svg.status_code == 200 and svg.headers["content-type"].startswith("image/svg+xml")
    assert svg.text.count("data-sticker=") == 3 and 'data-mode="tight"' in svg.text
    js = client.get("/api/scene/sheet.json?mode=spaced&page=a4").json()
    assert js["schema"] == "arucostudio.sheet/1" and js["page"] == "a4"
    assert len(js["stickers"]) == 3 and {s["made_by"] for s in js["stickers"]} == {"sticker"}
    assert len(client.get("/api/scene/sheet.json?proofs=true").json()["stickers"]) == 4
    pdf = client.get("/api/scene/print.pdf")
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    assert pdf.headers["content-disposition"].startswith("inline")
    ex = client.post("/api/scene/export/print", json={"inline": True}).json()
    assert base64.b64decode(ex["inline"]["sheet.pdf"]) == pdf.content     # the same bytes
    out = Path(ex["dir"])
    for rel in ("sheet.pdf", "sheet.svg", "sheet.json", "markers.json", "print3d/parts.json",
                "print3d/aruco_tags.3mf"):
        assert (out / rel).is_file(), rel
    assert ex["stickers"] == 3 and ex["parts"] == 1
    sc = client.get("/api/scene").json()
    assert sc["ledger"] and sc["ledger"]["printed"]
    # 100 mm is 100 mm in the print route's bytes
    from aruco_studio.verify import sheet_check as SC
    page = SC.rasterise(pdf.content)[0]
    js = client.get("/api/scene/sheet.json").json()
    assert abs(SC.bar_mm(page, js["ruler"]["mm_bar"], 600 / 25.4) - 100.0) <= 0.1
    assert client.get("/api/scene/sheet.svg?mode=loose").status_code == 422


def test_verify_sheet(client):
    _sheet_scene(client)
    rep = client.post("/api/scene/verify/sheet", json={"mode": "tight"}).json()
    assert rep["ok"], json.dumps(rep)[:1500]
    assert len(rep["stickers"]) == 3 and rep["worst"]["ink_xor"] <= 0.02
    assert rep["mode"] == "tight"


def test_the_routes_come_before_the_web_app():
    from starlette.routing import Mount
    from aruco_studio.server import app as A
    from aruco_studio.server import sheet_api
    sheet_api.install(A.app)                       # idempotent
    routes = A.app.router.routes
    paths = [getattr(r, "path", "") for r in routes]
    assert paths.count("/api/scene/print.pdf") == 1
    mounts = [i for i, r in enumerate(routes) if isinstance(r, Mount)]
    assert all(i > paths.index("/api/scene/print.pdf") for i in mounts)
