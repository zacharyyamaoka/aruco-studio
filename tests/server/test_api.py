"""M2b.8: the API. Every route answers with its schema; a wrong TYPE is a
422 naming its key path; /api/form lists every row of ARCHITECTURE 5.6;
files land only under the Studio's own folders; uvicorn serves it on
127.0.0.1:5360 and stops."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
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


def spec(layout="single", **s):
    st = {"layout": layout, "mode": "both", "op": "new", **s}
    return {"schema": "arucostudio.tagspec/1", "settings": st, "numbers": {},
            "target": {"kind": "face", "w_mm": 80.0, "h_mm": 60.0, "has_body": False},
            "name": "Arm", "key": "t1"}


def test_health_dictionaries_options_form_targets(client):
    h = client.get("/api/health").json()
    assert h["ok"] and h["ref_commit"] == "c8216ff"
    ds = client.get("/api/dictionaries").json()
    assert len(ds) == 21 and sum(d["capacity"] for d in ds) == 9596
    o = client.get("/api/options").json()
    assert {x["value"] for x in o["layouts"]} == {"single", "grid", "charuco"}
    f = client.get("/api/form").json()
    from aruco_studio.plan.fields import fields
    assert [r["path"] for r in f["fields"]] == [r["path"] for r in fields()]
    for p in ("settings.layout", "numbers.marker_id", "settings.label.cap_mm", "settings.trim",
              "target.loops_mm", "target.body_mm", "key"):
        assert p in {r["path"] for r in f["fields"]}
    t = client.get("/api/targets").json()
    assert len(t) == 12 and {x["key"] for x in t} >= {"box40", "disc40", "disc4", "ring"}


def test_plan_validate_and_the_422(client):
    from aruco_studio.server.models import TagPlanOut
    for layout in ("single", "grid", "charuco"):
        r = client.post("/api/plan", json=spec(layout))
        assert r.status_code == 200
        d = r.json()
        TagPlanOut.model_validate(d)
        assert d["ok"] and d["ids"] and d["schema"] == "arucostudio.tagplan/1"
        r = client.post("/api/plan?mesh=1", json=spec(layout))
        m = r.json()["mesh"]
        assert m and all(len(x["positions"]) % 3 == 0 for x in m)
    # a wrong TYPE: 422 naming the key path
    for path, val in (("numbers.size", "28"), ("settings.quiet_modules", "1"),
                      ("target.w_mm", "80"), ("settings.label", "on"),
                      ("target.loops_mm", [[[0, "a"]]])):
        d = spec()
        keys = path.split(".")
        cur = d
        for k in keys[:-1]:
            cur = cur[k]
        cur[keys[-1]] = val
        r = client.post("/api/plan", json=d)
        assert r.status_code == 422, (path, r.text)
        assert any(e["path"].startswith(path) for e in r.json()["detail"]), (path, r.json())
    # a wrong VALUE: a plan with an Issue on that field
    d = spec()
    d["numbers"]["size"] = -3.0
    r = client.post("/api/plan", json=d).json()
    assert not r["ok"] and any(w["field"] == "numbers.size" for w in r["warnings"])
    v = client.post("/api/validate", json=d).json()
    assert any(w["field"] == "numbers.size" and w["level"] == "error" for w in v)


def test_candidates_verify_exports(client):
    c = client.post("/api/candidates", json={"layout": "grid", "target": spec()["target"]}).json()
    assert c and all(x["cols"] >= 1 for x in c)
    r = client.post("/api/verify", json={"spec": spec("grid"), "px_per_mm": 15.0}).json()
    assert r["ok"] and r["ids_read"] == r["ids_expected"] and r["pnp_err_mm"] < 0.1
    for fmt, ctype in (("svg", "image/svg+xml"), ("png", "image/png"), ("stl", "model/stl"),
                       ("json", "application/json")):
        r = client.post(f"/api/export/{fmt}", json=spec("charuco"))
        assert r.status_code == 200 and r.headers["content-type"].startswith(ctype)
        assert len(r.content) > 100
    # the PNG: true size (pHYs 20 px / mm) and OpenCV reads every id off it
    import cv2
    import numpy as np
    from aruco_studio.plan import plan_tag
    from aruco_studio.verify import detect as D
    for layout in ("single", "grid", "charuco"):
        png = client.post("/api/export/png", json=spec(layout)).content
        assert png[37:41] == b"pHYs" and int.from_bytes(png[41:45], "big") == 20000
        img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_GRAYSCALE)
        p = plan_tag(spec(layout))
        assert D.detect(img, p.data)["ids"] == sorted(p.data["ids"])
    assert client.post("/api/export/pdf", json=spec()).status_code == 404
    bad = spec()
    bad["target"]["w_mm"] = 4.0
    bad["target"]["h_mm"] = 4.0
    assert client.post("/api/export/svg", json=bad).status_code == 400


def test_presets_live_under_the_studio_home(client, tmp_path):
    p = client.get("/api/presets").json()
    names = [x["name"] for x in p["items"]]
    assert names[0] == "Default" and any("Aruco" in n for n in names)      # PrusaSlicer's
    assert all(x["kind"] == "builtin" for x in p["items"])
    pre = p["items"][0]["preset"]
    r = client.post("/api/presets", json={"name": "Mine", "preset": pre})
    assert r.status_code == 200 and r.json()["name"] == "Mine"
    assert (tmp_path / "home" / "aruco_presets.json").exists()
    assert client.put("/api/presets/Mine", json=dict(pre, label={"on": True})).status_code == 200
    assert client.put("/api/presets/Default", json=pre).status_code == 400      # read only
    assert client.delete("/api/presets/Default").status_code == 400
    assert client.delete("/api/presets/Mine").status_code == 200
    pr = client.get("/api/prusa/profiles").json()
    assert pr["aruco"] and all(x["line_mm"] for x in pr["aruco"])
    assert client.put("/api/remembered/inspector", json={"layout": "grid"}).json() == {"layout": "grid"}
    assert (tmp_path / "home" / "remembered.json").exists()


def test_scene_crud_files_and_renumber(client, tmp_path):
    assert client.post("/api/scene/new", json={"name": "bench"}).json()["name"] == "bench"
    names = []
    for k, layout in enumerate(("single", "single", "grid", "charuco")):
        r = client.post("/api/scene/tags", json={"spec": spec(layout), "x_mm": 100.0 * k})
        assert r.status_code == 200 and r.json()["plan"]["ok"]
        names.append(r.json()["name"])
    assert len(set(names)) == 4
    rn = client.post("/api/scene/renumber").json()
    assert rn["ok"] and rn["duplicates"] == {}
    r = client.patch(f"/api/scene/tags/{names[0]}", json={"x_mm": 5.0, "rotation_deg": 90.0})
    assert r.status_code == 200 and r.json()["rotation_deg"] == 90.0
    r = client.patch(f"/api/scene/tags/{names[0]}", json={"locked": True})
    r = client.patch(f"/api/scene/tags/{names[0]}", json={"numbers": {"marker_id": 30}})
    assert r.status_code == 409 and r.json()["issues"][0]["field"] == "numbers.marker_id"
    assert client.patch(f"/api/scene/tags/{names[1]}", json={"numbers": {"size": "x"}}).status_code == 422
    assert client.post(f"/api/scene/tags/{names[1]}/duplicate?dx_mm=400").status_code == 200
    assert client.put(f"/api/scene/overrides/{names[1]}", json={"id": 40}).json()["overrides"]
    s = client.get("/api/scene?plans=1").json()
    assert all(t["plan"]["ok"] for t in s["tags"])
    assert client.post("/api/scene/save", json={"name": "bench"}).status_code == 200
    assert (tmp_path / "scenes" / "bench.arucostudio.json").exists()
    assert [x["name"] for x in client.get("/api/scenes").json()] == ["bench"]
    client.post("/api/scene/new", json={"name": "other"})
    s2 = client.post("/api/scene/open", json={"name": "bench"}).json()
    assert [t["name"] for t in s2["tags"]] == [t["name"] for t in s["tags"]]
    assert client.post("/api/scene/open", json={"name": "nope"}).status_code == 404
    for fmt in ("svg", "json", "stl", "plan", "png"):
        r = client.post(f"/api/scene/export/{fmt}").json()
        assert r["files"] and all(Path(f).exists() for f in r["files"])
        assert all(Path(f).resolve().is_relative_to((tmp_path / "home").resolve())
                   for f in r["files"])
    v = client.post("/api/scene/verify").json()
    assert v["ok"] and v["found"] == v["markers"]
    assert client.delete(f"/api/scene/tags/{names[2]}").status_code == 200
    assert client.delete("/api/scene/tags/nope").status_code == 404
    bad = client.put("/api/scene", json={"schema": "arucostudio.scene/7", "tags": []})
    assert bad.status_code == 400 and "arucostudio.scene/7" in bad.text


def test_cors_allows_the_dev_server(client):
    r = client.options("/api/health", headers={"Origin": "http://127.0.0.1:5361",
                                               "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") == "http://127.0.0.1:5361"
    r = client.options("/api/health", headers={"Origin": "http://evil.example",
                                               "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") is None


def test_the_store_refuses_cadexporter(monkeypatch, tmp_path):
    from aruco_studio.server import store as S
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("ARUCO_STUDIO_HOME", str(tmp_path / "CADExporter" / "studio"))
    with pytest.raises(S.StoreError):
        S.home()


def test_openapi_types_every_route(client):
    o = client.get("/openapi.json").json()
    paths = o["paths"]
    for p in ("/api/health", "/api/form", "/api/targets", "/api/plan", "/api/validate",
              "/api/candidates", "/api/verify", "/api/export/{fmt}", "/api/presets",
              "/api/prusa/profiles", "/api/scene", "/api/scene/tags", "/api/scene/renumber",
              "/api/scene/save", "/api/scene/open", "/api/scene/export/{fmt}", "/api/dictionaries",
              "/api/options"):
        assert p in paths, p
    schemas = o["components"]["schemas"]
    for k in ("TagSpecIn", "TagPlanOut", "TargetIn", "IssueOut", "LayerOut"):
        assert k in schemas


def _port_free(port):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def _free_port():
    """A port the OS has free now (ephemeral, never another tool's): the test
    is hermetic beside a lane's own server on 5360 (audit 2026-10-17)."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_uvicorn_serves_and_stops(tmp_path):
    from aruco_studio.server.app import PORT
    assert PORT == 5360                                  # the default the README names
    port = _free_port()
    env = dict(os.environ, ARUCO_STUDIO_HOME=str(tmp_path / "home"),
               ARUCO_STUDIO_SCENES=str(tmp_path / "scenes"), PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.Popen([sys.executable, "-m", "aruco_studio.server", "--port", str(port)],
                         cwd=str(ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        body = None
        for _ in range(100):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1) as r:
                    body = json.loads(r.read())
                    break
            except OSError:
                time.sleep(0.1)
        assert body and body["ok"], p.stdout.read(2000) if p.poll() is not None else "no answer"
    finally:
        p.terminate()
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait(timeout=10)
    for _ in range(50):
        if _port_free(port):
            break
        time.sleep(0.1)
    assert _port_free(port)
