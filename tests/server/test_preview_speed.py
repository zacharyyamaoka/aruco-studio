"""Lane speed (audit B1): a live edit of the forearm is fast, and answers
exactly what it answered before.

* the benchmark (tools/bench_preview.py) under a generous bound: a drag step
  (top views only, the light preview) and a 3D release (the meshes too);
* the light preview has no meshes, the release has them, both the same top
  views and plans;
* the answer's bytes are what FastAPI's encoder gave (plain_json), the
  cache's tuples are written as the lists they were;
* the GC hold (app.no_gc) always gives the collector back.
"""
from __future__ import annotations

import gc
import json
import sys
from pathlib import Path

import pytest
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import bench_preview as BP  # noqa: E402

# Generous: before the lane the drag step took 245-265 ms and a 3D edit
# 715-920 ms on Zach's box; after it about 90 ms and 280 ms. The bounds
# leave room for a loaded machine (the check runs groups side by side).
DRAG_MS = 400.0
RELEASE_MS = 1500.0


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ARUCO_STUDIO_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("ARUCO_STUDIO_SCENES", str(tmp_path / "scenes"))
    monkeypatch.setenv("BAM_ARUCO_PRUSASLICER_DIR", str(ROOT / "goldens" / "prusaslicer"))
    from aruco_studio.scene import Scene
    from aruco_studio.server import app as A
    from aruco_studio.server import design_api as DA
    A.STATE["scene"] = Scene(name="untitled")
    c = TestClient(A.app)
    yield c
    DA.D.unbind()


def test_the_benchmark_is_under_its_bound(client, tmp_path):
    res = BP.bench(n=5)
    print(json.dumps(res))
    assert res["open 2d"]["median"] < DRAG_MS, res
    assert res["bare 2d"]["median"] < DRAG_MS, res
    assert res["open 3d"]["median"] < RELEASE_MS, res
    assert gc.isenabled()


def test_the_light_preview_is_the_release_without_its_meshes(client):
    text = BP.forearm_text(151)
    light = client.post("/api/design/preview?top=1", json={"text": text}).json()["scene"]
    full = client.post("/api/design/preview?top=1&mesh=1", json={"text": text}).json()["scene"]
    assert len(light["tags"]) == len(full["tags"]) == 4
    for a, b in zip(light["tags"], full["tags"]):
        assert a["name"] == b["name"] and a["plan"]["ok"]
        assert "mesh" not in a["plan"] and b["plan"]["mesh"]
        assert a["plan"]["top"] == b["plan"]["top"]
        assert {k: v for k, v in b["plan"].items() if k != "mesh"} == a["plan"]


def test_plain_json_is_the_encoders_bytes(client):
    from aruco_studio.server import design_api as DA
    for q in ("top=1", "top=1&mesh=1"):
        r = client.post(f"/api/design/preview?{q}", json={"text": BP.forearm_text(152)})
        # the same answer the old route built: the encoder's walk, then JSONResponse
        mesh, top = "mesh=1" in q, True
        doc = DA.loads_design(BP.forearm_text(152))
        sc, issues = DA._DS.compile(doc, DA.resolver())
        from aruco_studio.server.app import cached_plan_dict
        old = {"scene": DA.scene_dict(sc, plans=True, mesh=mesh, top=top, plan_dict=cached_plan_dict),
               "issues": [i.to_dict() for i in issues], "error": None}
        assert r.content == JSONResponse(content=jsonable_encoder(old)).body
    # anything not plain JSON still goes through the encoder
    assert DA.plain_json({"p": Path("a")}).body == b'{"p":"a"}'


def test_the_kept_mesh_is_written_as_the_mesh(client, tmp_path):
    from aruco_studio.plan import mesh as ME
    from aruco_studio.plan import plan_tag
    from aruco_studio.server import app as A
    p = tmp_path / "forearm.arucostudio.json"
    p.write_text(BP.forearm_text(133), encoding="utf-8")
    assert client.post("/api/design/open", json={"path": str(p)}).status_code == 200
    body = client.get("/api/scene?plans=1&mesh=1&top=1").json()
    for t in body["tags"]:
        spec = A._DA.D.current().get(t["name"]).spec
        assert t["plan"]["mesh"] == json.loads(json.dumps(ME.mesh(plan_tag(spec))))
        kept = A._entry(spec)["mesh"]
        assert all(isinstance(b["positions"], tuple) for b in kept)
    again = client.get("/api/scene?plans=1&mesh=1&top=1").json()      # from the cache
    assert again == body


def test_the_gc_hold_gives_the_collector_back():
    from aruco_studio.server.app import no_gc
    assert gc.isenabled()
    with no_gc():
        assert not gc.isenabled()
        with no_gc():
            assert not gc.isenabled()
        assert not gc.isenabled()
    assert gc.isenabled()
    with pytest.raises(ValueError):
        with no_gc():
            raise ValueError("a failed plan")
    assert gc.isenabled()
    gc.disable()                      # off before: left off
    try:
        with no_gc():
            pass
        assert not gc.isenabled()
    finally:
        gc.enable()


def test_a_bad_text_still_answers_with_the_collector_on(client):
    r = client.post("/api/design/preview?top=1", json={"text": "{ nope"})
    assert r.status_code == 200 and r.json()["error"] and r.json()["scene"] is None
    assert gc.isenabled()
