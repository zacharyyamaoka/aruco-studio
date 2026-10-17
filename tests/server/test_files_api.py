"""The 2026-10-17 audit's server half of the Studio fixes:

* the Open dialog's lists (server/files_api.py): the three examples, the
  recent files, a folder; an example opens as a copy in the scenes folder,
  the repo's file never written;
* the Sticker sheet dialog's Export writes the sheet only (`sheet_only`),
  and Reveal answers the export folder without opening a window.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
EX = ROOT / "examples"


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


def test_the_lists_and_an_example_opened_as_a_copy(client, tmp_path):
    before = {f.name: f.read_bytes() for f in EX.glob("*.arucostudio.json")}
    f = client.get("/api/design/files").json()
    assert [x["name"] for x in f["examples"]] == ["forearm", "plate_charuco", "sticker_sheet"]
    assert f["examples"][0]["title"] == "forearm, 1-DoF arm"
    assert f["recent"] == [] and f["scenes_dir"] == str(tmp_path / "scenes")
    a = client.post("/api/design/open_example", json={"name": "forearm"})
    assert a.status_code == 200, a.text
    p1 = Path(a.json()["path"])
    assert p1.parent == tmp_path / "scenes" and p1.name == "forearm.arucostudio.json"
    b = client.post("/api/design/open_example", json={"name": "forearm"}).json()
    assert Path(b["path"]).name == "forearm-2.arucostudio.json"          # a fresh name when taken
    assert client.post("/api/design/open_example", json={"name": "../x"}).status_code == 404
    assert client.post("/api/design/open_example", json={"name": "nope"}).status_code == 404
    rec = [Path(r["path"]) for r in client.get("/api/design/files").json()["recent"]]
    assert rec[:2] == [Path(b["path"]).resolve(), p1.resolve()]
    assert {f.name: f.read_bytes() for f in EX.glob("*.arucostudio.json")} == before


def test_browse_a_folder(client, tmp_path):
    d = client.get("/api/design/browse").json()                # the scenes folder (made if missing)
    assert d["dir"] == str(tmp_path / "scenes") and d["files"] == []
    work = tmp_path / "work"
    (work / "sub").mkdir(parents=True)
    shutil.copy(EX / "plate_charuco.arucostudio.json", work / "plate.arucostudio.json")
    (work / "notes.txt").write_text("x", encoding="utf-8")
    d = client.get("/api/design/browse", params={"dir": str(work)}).json()
    assert [x["name"] for x in d["files"]] == ["plate"] and [x["name"] for x in d["folders"]] == ["sub"]
    assert d["parent"] == str(tmp_path)
    assert client.get("/api/design/browse", params={"dir": str(work / "none")}).status_code == 404
    home = Path(os.environ["USERPROFILE"]) / "CADExporter"
    assert client.get("/api/design/browse", params={"dir": str(home)}).status_code == 403


def test_the_sheet_dialog_exports_the_sheet_only_and_reveal_says_the_folder(client, tmp_path):
    p = tmp_path / "mix.arucostudio.json"
    shutil.copy(EX / "sticker_sheet.arucostudio.json", p)
    assert client.post("/api/design/open", json={"path": str(p)}).status_code == 200
    sp = client.post("/api/new", json={"layout": "single", "target_key": "box40",
                                       "thickness_mm": 3}).json()             # a 3D tag beside them
    assert client.post("/api/scene/tags", json={"spec": sp, "name": "solid", "x_mm": 200}).status_code == 200
    r = client.post("/api/scene/export/print", json={"sheet_only": True}).json()
    rel = sorted(Path(w).relative_to(r["dir"]).as_posix() for w in r["written"])
    assert {"sheet.pdf", "sheet.svg", "sheet.json", "markers.json"} <= set(rel)
    assert not [x for x in rel if x.startswith("print3d/")]
    full = client.post("/api/scene/export/print", json={}).json()          # the bundle keeps them
    assert [w for w in full["written"] if "print3d" in w]
    rv = client.post("/api/scene/export/reveal", json={"open": False}).json()
    assert rv["dir"] == r["dir"] and rv["opened"] is False and rv["command"]
