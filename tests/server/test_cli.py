"""M8a.9 (and M8a.1's exit code): python -m aruco_studio check / render / plan.

* `check examples/*.json` exits 0; a file with a bad feature exits 1 and
  prints the feature's path; a broken file prints file:line:col;
* `render` writes an SVG whose data-layer paths, tag by tag, are the ones
  POST /api/export/svg gives for that tag;
* `plan --json` equals GET /api/scene?plans=1's plans for the same file.

(The roadmap names this file tests/test_cli.py; it sits in tests/server/
so tools/check.py's server group runs it.)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
EX = sorted((ROOT / "examples").glob("*.arucostudio.json"))


@pytest.fixture()
def env(tmp_path, monkeypatch):
    e = dict(os.environ, ARUCO_STUDIO_HOME=str(tmp_path / "home"),
             BAM_ARUCO_PRUSASLICER_DIR=str(ROOT / "goldens" / "prusaslicer"),
             PYTHONIOENCODING="utf-8")
    for k in ("ARUCO_STUDIO_HOME", "BAM_ARUCO_PRUSASLICER_DIR"):
        monkeypatch.setenv(k, e[k])
    monkeypatch.setenv("ARUCO_STUDIO_SCENES", str(tmp_path / "scenes"))
    return e


def cli(env, *args):
    return subprocess.run([sys.executable, "-m", "aruco_studio", *args], cwd=str(ROOT), env=env,
                          capture_output=True, text=True, encoding="utf-8")


@pytest.fixture()
def client(env):
    from aruco_studio.scene import Scene
    from aruco_studio.server import app as A
    from aruco_studio.server import design_api as DA
    A.STATE["scene"] = Scene(name="untitled")
    yield TestClient(A.app)
    DA.D.unbind()


def test_check_the_examples_exits_0(env):
    assert len(EX) == 3
    r = cli(env, "check", *[str(p) for p in EX])
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.count("0 error(s)") == 3


def test_check_a_bad_file_exits_1_with_the_path(env, tmp_path):
    doc = json.loads((ROOT / "examples" / "forearm.arucostudio.json").read_text(encoding="utf-8"))
    doc["features"][1]["aruco"][1] = "forearm.lid"
    bad = tmp_path / "bad.arucostudio.json"
    bad.write_text(json.dumps(doc), encoding="utf-8")
    r = cli(env, "check", str(bad))
    assert r.returncode == 1
    assert f"{bad}: features[1].aruco[1]: error:" in r.stdout and "lid" in r.stdout
    broken = tmp_path / "broken.arucostudio.json"
    broken.write_text('{\n "schema": "arucostudio.scene/2",\n "name": \n}', encoding="utf-8")
    r = cli(env, "check", str(broken))
    assert r.returncode == 1 and f"{broken}:4:1: error:" in r.stdout
    r = cli(env, "check", "--strict", str(ROOT / "examples" / "sticker_sheet.arucostudio.json"))
    assert r.returncode == 1 and "t4 not built" in r.stdout      # Default can't print the disc's board


def _paths(svg: str):
    return re.findall(r'<path data-layer="[^"]+"[^>]*/>', svg)


def test_render_draws_each_tag_as_api_export_svg(env, client, tmp_path):
    for p in EX:
        out = tmp_path / (p.stem + ".svg")
        r = cli(env, "render", str(p), "--svg", str(out))
        assert r.returncode == 0, r.stdout + r.stderr
        svg = out.read_text(encoding="utf-8")
        assert svg.startswith("<svg") and 'data-shape="' in svg
        client.post("/api/design/open", json={"path": str(p)})
        tags = client.get("/api/scene?plans=1").json()["tags"]
        drawn = 0
        for t in tags:
            m = re.search(rf'<g data-tag="{re.escape(t["name"])}" transform="matrix\([^)]*\)">'
                          r'(.*?)</g>', svg)
            if not t["plan"]["ok"]:
                assert m is None
                continue
            e = client.post("/api/export/svg", json=t["spec"])
            assert e.status_code == 200
            assert _paths(m.group(1)) == _paths(e.text), (p.name, t["name"])
            drawn += 1
        assert drawn >= 1
        if p.stem.startswith("forearm"):
            assert svg.count("data-hinge=") == 4


def test_plan_json_equals_the_scenes_plans(env, client, tmp_path):
    for p in EX:
        out = tmp_path / (p.stem + ".plans.json")
        r = cli(env, "plan", str(p), "--json", "--out", str(out))
        assert r.returncode == 0, r.stdout + r.stderr
        got = json.loads(out.read_text(encoding="utf-8"))
        client.post("/api/design/open", json={"path": str(p)})
        want = {t["name"]: t["plan"] for t in client.get("/api/scene?plans=1").json()["tags"]}
        assert got == want
