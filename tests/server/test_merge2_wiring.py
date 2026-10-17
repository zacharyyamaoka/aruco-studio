"""Merge 2 (M8c + M8b1): the wiring the merge added.

- app.py serves M8c's PrusaSlicer routes (the include line), and they come
  before the web app's static mount.
- /api/preset/apply and /api/preset/of read catalog_all, so a sticker
  printer is found by name, as /api/new and the Library already do.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "tests" / "fixtures" / "prusaslicer_m8c"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ARUCO_STUDIO_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("ARUCO_STUDIO_SCENES", str(tmp_path / "scenes"))
    monkeypatch.setenv("BAM_ARUCO_PRUSASLICER_DIR", str(FIX))
    from aruco_studio.server import app as A
    from aruco_studio.scene import Scene
    A.STATE["scene"] = Scene(name="untitled")
    return TestClient(A.app)              # not `with`: the folder's watcher is not started


def test_app_serves_the_prusa_routes_first():
    from aruco_studio.server import app as A
    paths = [getattr(r, "path", "") for r in A.app.router.routes]
    for p in ("/api/prusa/printers", "/api/prusa/stale", "/api/prusa/watch",
              "/api/scene/send/prusaslicer"):
        assert p in paths, p
    if "" in paths or "/" in paths:               # the static mount, when studio/dist exists
        mount = next(i for i, r in enumerate(A.app.router.routes)
                     if type(r).__name__ == "Mount")
        assert paths.index("/api/prusa/printers") < mount


def test_prusa_printers_answers_through_app(client):
    r = client.get("/api/prusa/printers")
    assert r.status_code == 200, r.text
    assert r.json()["found"]


def test_preset_apply_and_of_find_a_sticker_printer(client):
    from aruco_studio.core import presets as P
    name = P.sticker_builtins()[0]["name"]
    sp = client.post("/api/new", json={"layout": "single", "preset": name}).json()
    assert sp["settings"]["make"]["by"] == "sticker"
    got = client.post("/api/preset/apply", json={"spec": sp, "name": name})
    assert got.status_code == 200, got.text
    back = client.post("/api/preset/of", json={"spec": got.json()}).json()
    assert back["matches"] == name
