"""The gallery (Zach's N-3, 2026-10-17; server/gallery_api.py):

* GET /api/gallery lists examples/gallery/gallery.json, every item with its
  file's text; every example file is listed and every listed file exists;
* every example compiles and plans with no error-level message (the
  compile's issues, each tag's plan errors and its error-level warnings);
* POST /api/gallery/open copies the example to <home>/gallery/ and opens
  it; a second open starts from the example again; examples/ is never
  written; an unknown name is 404.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
GAL = ROOT / "examples" / "gallery"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ARUCO_STUDIO_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("ARUCO_STUDIO_SCENES", str(tmp_path / "scenes"))
    monkeypatch.setenv("BAM_ARUCO_PRUSASLICER_DIR", str(ROOT / "tests" / "fixtures" / "prusaslicer_m8c"))
    from aruco_studio.scene import Scene
    from aruco_studio.server import app as A
    from aruco_studio.server import design_api as DA
    A.STATE["scene"] = Scene(name="untitled")
    c = TestClient(A.app)
    yield c
    DA.D.unbind()


def _items(doc):
    return [it for g in doc["groups"] for it in g["items"]]


def _files():
    return {f.name: f.read_bytes() for f in GAL.iterdir()}


def test_the_list_and_every_file(client, tmp_path):
    doc = client.get("/api/gallery").json()
    assert doc["schema"] == "arucostudio.gallery/1"
    assert doc["dir"] == str(tmp_path / "home" / "gallery")
    items = _items(doc)
    assert len(items) >= 15
    assert doc["groups"][0]["id"] == "basics"                       # markers first
    names = [it["name"] for it in items]
    assert len(set(names)) == len(names)
    listed = {it["file"] for it in items}
    on_disk = {f.name for f in GAL.glob("*.arucostudio.json")}
    assert listed == on_disk
    for it in items:
        assert it["text"] == (GAL / it["file"]).read_text(encoding="utf-8"), it["name"]
        assert it["title"] and it["line"] and it["look"], it["name"]
        assert set(it.get("actions") or []) <= {"3d", "sheet", "send", "ids"}, it["name"]


def test_every_example_plans_with_no_error(client):
    from aruco_studio.plan import plan_tag
    from aruco_studio.scene import design, loads_design
    from aruco_studio.server.design_api import resolver
    for it in _items(client.get("/api/gallery").json()):
        sc, issues = design.compile(loads_design(it["text"]), resolver())
        bad = [f"{i.field}: {i.text}" for i in issues if i.level == "error"]
        assert sc.tags, it["name"]
        for t in sc.tags:
            p = plan_tag(t.spec).to_dict()
            assert p["ok"], (it["name"], t.name, p["errors"])
            bad += [f"{t.name} {w['field']}: {w['text']}" for w in p["warnings"] if w["level"] == "error"]
        assert bad == [], it["name"]


def test_open_a_copy_afresh(client, tmp_path):
    before = _files()
    a = client.post("/api/gallery/open", json={"name": "basics_single"})
    assert a.status_code == 200, a.text
    got = a.json()
    p = Path(got["path"])
    assert p == tmp_path / "home" / "gallery" / "basics_single.arucostudio.json"
    assert got["state"] == "ok" and got["item"]["name"] == "basics_single" and got["item"]["group"] == "basics"
    assert client.get("/api/design?text=0").json()["path"] == str(p)
    # the copy is the example, its sugar's presets frozen in at the end (FILE_FORMAT 2)
    fresh = p.read_text(encoding="utf-8")
    example = json.loads((GAL / "basics_single.arucostudio.json").read_text(encoding="utf-8"))
    copied = json.loads(fresh)
    assert set(copied.pop("frozen_presets", {})) <= {example.get("preset")}
    assert copied == example
    # a change goes to the copy; opening the card again starts from the example
    doc = json.loads(client.get("/api/design").json()["text"])
    doc["name"] = "changed"
    h = client.get("/api/design?text=0").json()["hash"]
    assert client.put("/api/design", json={"text": json.dumps(doc), "hash": h}).status_code == 200
    assert json.loads(p.read_text(encoding="utf-8"))["name"] == "changed"
    client.post("/api/gallery/open", json={"name": "basics_single"})
    assert p.read_text(encoding="utf-8") == fresh
    for bad in ("nope", "../forearm", "gallery"):
        assert client.post("/api/gallery/open", json={"name": bad}).status_code == 404, bad
    assert _files() == before
