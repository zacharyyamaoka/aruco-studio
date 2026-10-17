"""Audit A1 (2026-10-17): a design file still in sugar is frozen against the
presets it was first expanded with (scene/design.freeze, `frozen_presets`).

* pure: a sugar file compiled, its presets frozen, the profile's line
  changed 0.68 -> 0.65, compiled again: the same tags (and without the
  freeze they would differ, so the test bites);
* the server: opening a typed sugar file adds `frozen_presets` at the end
  of the text and keeps the rest as typed; a changed PrusaSlicer profile
  then changes no tag, on a reopen or an edit of another tag, and the
  "Apply?" info names the tag; a copy no sugar feature uses is dropped;
* a hand-typed file that already holds the copies is read, never rewritten.
"""
from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aruco_studio.core import presets as P
from aruco_studio.scene import design as DS
from aruco_studio.scene.file import loads_design

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "tests" / "fixtures" / "prusaslicer_m8c"
EX = ROOT / "examples"
PRESET = "0.32mm SPEED @MK4IS 0.6 - Aruco"


def _catalog(line):
    p = P.default_preset()
    p["name"] = PRESET
    p["profile"].update(name=PRESET, nozzle_mm=0.6, line_mm=line, layer_mm=0.32,
                        source="prusaslicer")
    p["cells"] = {"of": "cell", "step": "line", "mm": line, "min_mm": 2.0, "min_lines": 0}
    return {PRESET: p}


def _specs(doc, cat):
    sc, issues = DS.compile(doc, cat)
    assert not [i for i in issues if i.level == "error"]
    return {t.name: t.spec.to_dict() for t in sc.tags}


def test_a_frozen_sugar_file_compiles_the_same_under_a_changed_profile():
    doc = loads_design((EX / "plate_charuco.arucostudio.json").read_text(encoding="utf-8"))
    old, new = _catalog(0.68), _catalog(0.65)
    before = _specs(doc, old)
    assert before["tag"]["settings"]["cells"]["mm"] == 0.68
    assert _specs(doc, new)["tag"]["settings"]["cells"]["mm"] == 0.65   # unfrozen: it moves
    assert DS.freeze(doc, old) is True
    assert list(doc[DS.FROZEN]) == [PRESET]
    assert DS.freeze(doc, new) is False                   # once: never refreshed by itself
    assert _specs(doc, new) == before
    doc2 = json.loads(json.dumps(doc))                    # the copy survives the file
    assert _specs(doc2, new) == before and _specs(doc2, None) == before


def test_freeze_drops_unused_copies_and_skips_unknown_names():
    doc = loads_design((EX / "plate_charuco.arucostudio.json").read_text(encoding="utf-8"))
    DS.freeze(doc, _catalog(0.68))
    doc["features"][1]["settings"] = {"layout": "single"}
    doc["features"][1]["numbers"] = {"size": 20.0}
    assert DS.freeze(doc, _catalog(0.68)) is True and DS.FROZEN not in doc
    doc = loads_design((EX / "plate_charuco.arucostudio.json").read_text(encoding="utf-8"))
    assert DS.freeze(doc, {}) is False and DS.FROZEN not in doc   # unknown: Default, a warn


def test_a_bad_frozen_presets_is_an_error_on_its_path():
    doc = loads_design((EX / "plate_charuco.arucostudio.json").read_text(encoding="utf-8"))
    doc[DS.FROZEN] = {PRESET: 3}
    _sc, issues = DS.compile(doc, _catalog(0.68))
    assert (f"{DS.FROZEN}.{PRESET}", "error") in [(i.field, i.level) for i in issues]


# ------------------------------------------------------------------ the server

@pytest.fixture()
def env(tmp_path, monkeypatch):
    ps = tmp_path / "PrusaSlicer"
    shutil.copytree(FIX, ps)
    monkeypatch.setenv("ARUCO_STUDIO_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("ARUCO_STUDIO_SCENES", str(tmp_path / "scenes"))
    monkeypatch.setenv("BAM_ARUCO_PRUSASLICER_DIR", str(ps))
    from aruco_studio.scene import Scene
    from aruco_studio.server import app as A
    from aruco_studio.server import design_api as DA
    from aruco_studio.server import prusa_api  # noqa: F401
    from aruco_studio.server import prusa_watch as PW
    A.STATE["scene"] = Scene(name="untitled")
    c = TestClient(A.app)
    w = PW.PrusaWatch(lambda e, d: None)
    monkeypatch.setattr(PW, "WATCH", w)
    yield c, ps, tmp_path, DA
    w.stop()
    DA.D.unbind()


def _line(ps, old, new):
    f = ps / "print" / f"{PRESET}.ini"
    t = f.read_text(encoding="utf-8")
    assert old in t
    f.write_text(t.replace(old, new), encoding="utf-8")


def test_open_freezes_into_the_file_and_a_changed_profile_changes_nothing(env):
    c, ps, tmp, DA = env
    p = tmp / "plate.arucostudio.json"
    typed = (EX / "plate_charuco.arucostudio.json").read_text(encoding="utf-8")
    p.write_text(typed, encoding="utf-8")
    assert c.post("/api/design/open", json={"path": str(p)}).status_code == 200
    text = p.read_text(encoding="utf-8")
    assert text.startswith(typed.rstrip()[:-1].rstrip())          # the typed text kept as typed
    doc = json.loads(text)
    assert list(doc[DS.FROZEN]) == [PRESET]
    assert doc[DS.FROZEN][PRESET]["profile"]["line_mm"] == 0.68
    spec0 = c.get("/api/scene").json()["tags"][0]["spec"]
    assert spec0["settings"]["cells"]["mm"] == 0.68

    _line(ps, "extrusion_width = 0.68", "extrusion_width = 0.65")
    assert c.post("/api/design/open", json={"path": str(p)}).status_code == 200     # a reopen
    assert c.get("/api/scene").json()["tags"][0]["spec"] == spec0
    assert p.read_text(encoding="utf-8") == text                  # nothing rewritten
    st = c.get("/api/prusa/stale").json()["stale"]
    assert [(s["tag"], s["text"]) for s in st] == [
        ("tag", "the profile changed: line 0.68 -> 0.65 mm; Apply?")]

    # an edit of another tag: the typed one is still the same
    sp = c.post("/api/new", json={"layout": "single", "target_key": "box40"}).json()
    assert c.post("/api/scene/tags", json={"spec": sp, "name": "other", "x_mm": 120}).status_code == 200
    tags = {t["name"]: t["spec"] for t in c.get("/api/scene").json()["tags"]}
    assert tags["tag"] == spec0
    assert list(json.loads(p.read_text(encoding="utf-8"))[DS.FROZEN]) == [PRESET]


def test_an_external_write_in_sugar_is_frozen_and_a_studio_file_is_left_alone(env):
    c, ps, tmp, DA = env
    p = tmp / "forearm.arucostudio.json"
    shutil.copy(EX / "forearm.arucostudio.json", p)
    assert c.post("/api/design/open", json={"path": str(p)}).status_code == 200
    frozen = p.read_text(encoding="utf-8")
    assert DS.FROZEN in json.loads(frozen)
    # a file that already holds its copies: opened, never rewritten
    q = tmp / "again.arucostudio.json"
    q.write_text(frozen, encoding="utf-8")
    assert c.post("/api/design/open", json={"path": str(q)}).status_code == 200
    assert q.read_text(encoding="utf-8") == frozen
    # the watcher's reload of a typed file without the copies freezes it
    typed = json.loads((EX / "forearm.arucostudio.json").read_text(encoding="utf-8"))
    typed["name"] = "renamed by hand"
    q.write_text(json.dumps(typed, indent=2) + "\n", encoding="utf-8")
    DA.D._on_change(str(q), q.read_text(encoding="utf-8"), None)
    now = json.loads(q.read_text(encoding="utf-8"))
    assert now["name"] == "renamed by hand" and list(now[DS.FROZEN]) == [PRESET]
    raw = q.read_bytes().decode("utf-8")
    assert c.get("/api/design").json()["text"] == raw
    assert raw.count("\r\n") == raw.count("\n")          # one kind of line end (as written)
