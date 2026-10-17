"""The scene fixes through the API (lane/scene-fixes, 2026-10-17: the
gallery's two findings, docs/status/gallery.md):

* POST /api/scene/renumber (the IDs table's Renumber all) on the sticker
  sheet keeps its typed ids 0, 1, 2, 8: the scene, the file it wrote and the
  file opened again plan them, with no duplicate; a move of one tag after
  keeps the others' ids (each used to plan as #0);
* the gallery's 3D Trim examples type `perimeter` (they carried exact
  settings while the sugar had no trim): Marker plans with the trim (the
  Inspector's {rule 1, axes both, margin 0, force false}), Profile without;
  each plans as the exact settings they replaced (`force` absent = false).
"""
from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aruco_studio.plan import plan_tag

ROOT = Path(__file__).resolve().parents[2]
TYPED = {"t1": 0, "t2": 1, "t3": 2, "t4": 8}
TRIM_BOTH = {"rule": 1, "axes": "both", "margin_mm": 0.0, "force": False}


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


def _ids(client):
    tags = client.get("/api/scene?plans=1").json()["tags"]
    assert all(t["plan"]["ok"] for t in tags)
    return {t["name"]: t["plan"]["ids"] for t in tags}


def test_renumber_all_keeps_the_typed_ids_in_the_scene_and_the_file(client, tmp_path):
    p = tmp_path / "stickers.arucostudio.json"
    shutil.copy(ROOT / "examples" / "sticker_sheet.arucostudio.json", p)
    assert client.post("/api/design/open", json={"path": str(p)}).status_code == 200
    before = _ids(client)
    assert {k: v[0] for k, v in before.items()} == TYPED
    rep = client.post("/api/scene/renumber").json()
    assert rep["ok"] and rep["changed"] == [] and rep["duplicates"] == {}
    sc = client.get("/api/scene").json()
    assert sc["overrides"] == TYPED
    assert _ids(client) == before
    doc = json.loads(p.read_text(encoding="utf-8"))                 # the file it wrote
    assert doc["overrides"] == TYPED
    assert [f["numbers"]["marker_id"] for f in doc["features"] if "aruco" in f] == [0, 1, 2, 8]
    assert not any("first_id" in f for f in doc["features"])
    assert client.post("/api/design/open", json={"path": str(p)}).status_code == 200
    assert _ids(client) == before                                   # opened again
    flat = [i for v in before.values() for i in v]
    assert len(flat) == len(set(flat))
    assert client.post("/api/scene/renumber").json()["changed"] == []   # a second: nothing


def test_a_move_on_the_typed_sheet_keeps_the_other_tags_ids(client, tmp_path):
    p = tmp_path / "stickers.arucostudio.json"
    shutil.copy(ROOT / "examples" / "sticker_sheet.arucostudio.json", p)
    client.post("/api/design/open", json={"path": str(p)})
    before = _ids(client)
    assert client.patch("/api/scene/tags/t2", json={"x_mm": 45.0}).status_code == 200
    assert _ids(client) == before
    assert client.get("/api/scene").json()["overrides"] == TYPED


@pytest.mark.parametrize("name,tag,perimeter", [
    ("basics_single", "tag", "marker"), ("basics_grid", "tag", "marker"),
    ("basics_charuco", "tag", "marker"), ("trim", "marker3d", "marker"),
    ("trim", "profile3d", "profile")])
def test_the_gallerys_trim_examples_type_perimeter(client, name, tag, perimeter):
    from aruco_studio.scene import design, loads_design
    from aruco_studio.server.design_api import resolver
    doc = loads_design((ROOT / "examples" / "gallery" / f"{name}.arucostudio.json")
                       .read_text(encoding="utf-8"))
    f = next(f for f in doc["features"] if f.get("id") == tag)
    assert f["perimeter"] == perimeter and "settings" not in f and "numbers" not in f
    sc, issues = design.compile(doc, resolver())
    assert not [i for i in issues if i.level == "error"]
    t = sc.get(tag)
    assert t.spec.settings["make"]["by"] == "print3d" and t.spec.target.has_body
    p = plan_tag(t.spec)
    assert p.ok
    if perimeter == "marker":
        assert t.spec.settings["trim"] == TRIM_BOTH
        assert p.data["parts"][-1] == "trim" and p.data["guides"]["trim"]["outline"]
        # the exact settings the example carried (no `force`) plan the same
        exact = copy.deepcopy(t.spec.to_dict())
        exact["settings"]["trim"].pop("force")
        assert plan_tag(exact).to_dict() == p.to_dict()
    else:
        assert "trim" not in t.spec.settings and "trim" not in p.data["parts"]
