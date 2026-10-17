"""The server's fixes after the M3 audit: a typed first id is checked and used
at once (F1), new tags and copies take the next free ids (F5), overlapping
tags are a scene issue and fail the sheet's Verify (F13), plans are cached
by their spec (F14), the Library's Edit form refuses values a preset would
drop (F16), Auto size at creation (C5), the PDF sheet (C1)."""
from __future__ import annotations

import base64
import copy
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
    A._CACHE.clear()
    return TestClient(A.app)


def _add(client, layout, x=0.0, number=True):
    sp = client.post("/api/new", json={"layout": layout, "target_key": "box40"}).json()
    r = client.post("/api/scene/tags", json={"spec": sp, "x_mm": x, "y_mm": 0.0, "number": number})
    assert r.status_code == 200, r.text
    return r.json()


def _ids(client):
    return {t["name"]: t["plan"]["ids"] for t in client.get("/api/scene?plans=1").json()["tags"]}


def test_f5_new_tags_and_copies_take_the_next_free_ids(client):
    _add(client, "single", 0)
    _add(client, "grid", 60)
    _add(client, "charuco", 120)
    ids = _ids(client)
    flat = [i for v in ids.values() for i in v]
    assert len(flat) == len(set(flat)), ids
    assert ids["tag1"] == [0]
    dup = client.post("/api/scene/tags/board1/duplicate?dx_mm=0&dy_mm=-60").json()
    ids = _ids(client)
    flat = [i for v in ids.values() for i in v]
    assert len(flat) == len(set(flat)), ids
    assert len(ids[dup["name"]]) == len(ids["board1"])
    # number=false keeps the spec's own id (an import, a test fixture)
    _add(client, "single", 180, number=False)
    assert _ids(client)["tag2"] == [0]


def test_f1_a_typed_first_id_is_checked_and_used_at_once(client):
    _add(client, "single", 0)
    _add(client, "grid", 60)
    r = client.put("/api/scene/overrides/tag1", json={"id": 20})
    assert r.status_code == 200 and r.json()["ids"] == [20]
    assert _ids(client)["tag1"] == [20]
    bad = client.put("/api/scene/overrides/board1", json={"id": 500})
    assert bad.status_code == 409
    (i,) = bad.json()["issues"]
    assert i["field"] == "override" and "not in DICT_" in i["text"] and "|" not in i["text"]
    assert client.put("/api/scene/overrides/board1", json={"id": -3}).status_code == 409
    assert _ids(client)["board1"] == [1, 2, 3, 4]                 # nothing changed
    assert client.get("/api/scene").json()["overrides"] == {"tag1": 20}
    client.patch("/api/scene/tags/board1", json={"locked": True})
    locked = client.put("/api/scene/overrides/board1", json={"id": 30})
    assert locked.status_code == 409 and "locked" in locked.json()["issues"][0]["text"]
    assert client.put("/api/scene/overrides/tag1", json={"id": None}).json()["overrides"] == {}


def test_f13_overlapping_tags_are_a_scene_issue_and_fail_the_sheet(client):
    _add(client, "single", 0)
    _add(client, "single", 60)
    doc = client.get("/api/scene?plans=1").json()
    assert doc["issues"] == []
    assert client.post("/api/scene/verify").json()["ok"] is True
    client.patch("/api/scene/tags/tag2", json={"x_mm": 38.0})      # 2 mm onto tag1
    doc = client.get("/api/scene?plans=1").json()
    (iss,) = doc["issues"]
    assert iss["kind"] == "overlap" and iss["tags"] == ["tag1", "tag2"]
    assert iss["text"].startswith("tag2 overlaps tag1 (80.0 mm²)")
    rep = client.post("/api/scene/verify").json()
    assert rep["markers_ok"] is True and rep["ok"] is False     # every marker found, still not OK
    assert rep["overlaps"] == [{"tags": ["tag1", "tag2"], "mm2": 80.0}]


def test_f14_plans_are_cached_by_their_spec(client, monkeypatch):
    from aruco_studio.server import app as A
    for k in range(6):
        _add(client, "single", 60 * k)
    calls = []
    real = A.plan_tag
    monkeypatch.setattr(A, "plan_tag", lambda *a, **kw: calls.append(1) or real(*a, **kw))
    client.get("/api/scene?plans=1&top=1")
    assert calls == []                                     # every plan already made
    client.patch("/api/scene/tags/tag3", json={"numbers": {"marker_id": 33}})
    calls.clear()
    client.get("/api/scene?plans=1&top=1")
    assert calls == []                                     # the PATCH planned the new spec
    client.patch("/api/scene/tags/tag3", json={"x_mm": 500.0})
    calls.clear()
    client.get("/api/scene?plans=1&top=1&mesh=1")
    assert calls == []                                     # a move changes no spec


def test_c5_auto_check(client):
    sp = client.post("/api/new", json={"layout": "single", "target_key": "box40"}).json()
    built = client.post("/api/plan", json=sp).json()["marker"]["marker_length_m"] * 1000.0
    assert client.post("/api/auto_check", json=sp).json() == {"auto": True, "note": ""}
    old = copy.deepcopy(sp)
    old["numbers"]["size"] = built
    assert client.post("/api/auto_check", json=old).json()["auto"] is True
    old["numbers"]["size"] = round(built * 0.8, 3)
    r = client.post("/api/auto_check", json=old).json()
    assert r["auto"] is False and "(Auto size at creation)" in r["note"]


def test_c1_the_pdf_sheet_exports(client):
    _add(client, "single", 0)
    _add(client, "grid", 60)
    r = client.post("/api/scene/export/pdf?save=0").json()
    pdf = base64.b64decode(r["inline"]["sheet.pdf"])
    assert pdf.startswith(b"%PDF-") and b"/Type /Page" in pdf


def test_f16_the_library_edit_form_refuses_what_a_preset_would_drop(client):
    from aruco_studio.core import presets as P
    from aruco_studio.server import library as L
    # the limits are normalise's: inside kept, outside dropped (Default's)
    for path, (lo, hi) in L.LIMITS.items():
        for v, kept in ((lo, True), (hi, True), (lo - 0.01, False), (hi + 0.01, False)):
            p = P.default_preset()
            P.set_path(p, path, v)
            got = P.normalise(p)
            a, b = path.split(".")
            assert (got[a][b] == v) == kept, (path, v, got[a][b])
    p = client.get("/api/presets").json()["items"][0]["preset"]
    assert client.post("/api/presets", json={"name": "Audit preset", "preset": p}).status_code == 200
    r = client.post("/api/library/save", json={"id": "user:Audit preset", "name": "Audit preset",
                                               "values": {"tag.quiet_modules": -3}})
    assert r.status_code == 422
    (e,) = r.json()["detail"]
    assert e["path"] == "tag.quiet_modules" and "outside 0 to 4" in e["msg"]
    st = client.get("/api/library").json()
    assert st["limits"]["tag.quiet_modules"] == [0.0, 4.0]
    ok = client.post("/api/library/save", json={"id": "user:Audit preset", "name": "Audit preset",
                                                "values": {"tag.quiet_modules": 2}})
    assert ok.status_code == 200
