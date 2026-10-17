"""M8a.1 and M8a.7: the design file through the API.

* M8a.1: the three example files compile; each tag's record digest equals
  the digest of the same tag made through POST /api/new + POST /api/target
  (+ the PATCH edits the sugar stands for): the plate as a box 80 x 50 with
  a Ø18 hole, 5 mm thick, ChArUco 5 x 3;
* M8a.7: the old routes over the design: POST /api/scene/tags adds a sketch
  and a feature; PATCH with settings writes the exact dict into the feature
  and the file; duplicate, renumber, overrides, exports and verify answer
  as on main for the same scene (main's own server tests run unchanged
  beside these; here the same calls are replayed on a Scene by hand);
* /api/design: GET, PUT (verbatim, 422 with line:col, the hash's 409),
  open (anywhere; 403 under CADExporter; 404), save_as, preview (nothing
  written), reveal (only the command under test); /api/target strokes its
  holes as a design shape does.
"""
from __future__ import annotations

import copy
import json
import os
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aruco_studio.plan import plan_tag
from aruco_studio.plan import shapes as SH
from aruco_studio.core import make as MK
from aruco_studio.core import presets as P
from aruco_studio.plan.record import record_digest

ROOT = Path(__file__).resolve().parents[2]
EX = ROOT / "examples"
PRESET = "0.32mm SPEED @MK4IS 0.6 - Aruco"
STICKER = "Sticker · Letter · 600 dpi"   # the sticker example's preset (M6a; Merge 1)


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


def copy_example(tmp_path, name):
    p = tmp_path / f"{name}.arucostudio.json"
    shutil.copy(EX / f"{name}.arucostudio.json", p)
    return p


def digest(plan: dict):
    return record_digest(plan["record"]) if plan.get("record") else None


def same(a: dict, b: dict):
    """Two TagSpec dicts equal, the target's display name aside."""
    a, b = copy.deepcopy(a), copy.deepcopy(b)
    a["target"].pop("name", None)
    b["target"].pop("name", None)
    assert a == b


def via_old_routes(client, target, layout, name, edits, tag_name, preset=PRESET):
    """A tag made as the target editor and the inspector make it."""
    body = {"layout": layout, "target": target, "name": name}
    if preset:
        body["preset"] = preset
    sp = client.post("/api/new", json=body).json()
    client.post("/api/scene/new", json={"name": "ref"})
    t = client.post("/api/scene/tags", json={"spec": sp, "name": tag_name}).json()
    if edits:
        t = client.patch(f"/api/scene/tags/{tag_name}", json=edits).json()
    return t


def test_the_plate_equals_the_target_editors(client, tmp_path):
    p = copy_example(tmp_path, "plate_charuco")
    r = client.post("/api/design/open", json={"path": str(p)})
    assert r.status_code == 200 and r.json()["state"] == "ok" and not r.json()["issues"]
    tag = client.get("/api/scene?plans=1").json()["tags"][0]
    assert tag["name"] == "tag" and tag["plan"]["ok"]
    target = client.post("/api/target", json={"shape": "box", "w_mm": 80, "h_mm": 50,
                                               "holes": [[0, 0, 18]], "thickness_mm": 5}).json()
    ref = via_old_routes(client, target, "charuco", "plate",
                         {"settings": {"force": [5, 3], "corner_mark": "triangle",
                                       "label": {"on": True, "content": "id_name"}}}, "tag")
    same(tag["spec"], ref["spec"])
    assert digest(tag["plan"]) == digest(ref["plan"]) and digest(ref["plan"])
    assert tag["plan"]["layout"]["cols"] * tag["plan"]["layout"]["rows"] > 0


def test_the_forearm_and_the_stickers_equal_the_old_routes(client, tmp_path):
    for name in ("forearm", "sticker_sheet"):
        p = copy_example(tmp_path, name)
        assert client.post("/api/design/open", json={"path": str(p)}).status_code == 200
        tags = client.get("/api/scene?plans=1").json()["tags"]
        doc = json.loads(p.read_text(encoding="utf-8"))
        feats = {f["id"]: f for f in doc["features"] if "aruco" in f}
        for t in tags:
            f = feats[t["source"]["ref"] and t["name"].split(".")[0]]
            edits = {}
            s = {}
            if "cols" in f:
                s["force"] = [f["cols"], f["rows"]]
            if "mark" in f:
                s["corner_mark"] = f["mark"]
            if "label" in f:
                s["label"] = {"on": True, "content": {"#id": "id", "#id + name": "id_name"}[f["label"]]}
            if "perimeter" in f:
                # a PATCH replaces `make` whole: the sticker make /api/new stamps, with the perimeter
                # (the file's preset: the older Letter one, make rule 1 -- 2026-10-17)
                s["make"] = dict(MK.new_make("sticker", P.sticker_preset("letter")["profile"]),
                                 perimeter=f["perimeter"])
            if "holes" in f:
                s["holes"] = f["holes"]
            if s:
                edits["settings"] = s
            # the shipped ids (audit 2026-10-17: the examples open renumbered)
            if "marker_ids" in f:
                edits["numbers"] = {"marker_id": f["marker_ids"][t["source"]["entry"]]}
            if "first_id" in f:
                edits["numbers"] = {"marker_id": f["first_id"]}
            target = t["spec"]["target"]
            if name == "sticker_sheet":            # the target editor's own shapes
                sh = {"a": ("box", 30, 30), "b": ("box", 30, 30), "c": ("box", 60, 40)}
                if f["aruco"] in sh:
                    _k, w, h = sh[f["aruco"]]
                    target = client.post("/api/target", json={"shape": "box", "w_mm": w, "h_mm": h,
                                                              "thickness_mm": 0}).json()
                else:
                    target = client.post("/api/target", json={"shape": "disc", "r_mm": 25,
                                                              "holes": [[0, 18, 6]],
                                                              "thickness_mm": 0}).json()
            ref = via_old_routes(client, target, f["layout"], f.get("name", ""), edits, t["name"],
                                 preset=STICKER if name == "sticker_sheet" else PRESET)
            same(t["spec"], ref["spec"])
            assert digest(t["plan"]) == digest(ref["plan"]), t["name"]
            client.post("/api/design/open", json={"path": str(p)})


def test_old_routes_write_the_design(client, tmp_path):
    p = tmp_path / "bench.arucostudio.json"
    p.write_text(json.dumps({"schema": "arucostudio.scene/2", "name": "bench"}), encoding="utf-8")
    assert client.post("/api/design/open", json={"path": str(p)}).status_code == 200
    sp = client.post("/api/new", json={"layout": "grid", "target_key": "box40",
                                       "thickness_mm": 3}).json()
    t = client.post("/api/scene/tags", json={"spec": sp, "x_mm": 30, "y_mm": 5,
                                             "number": True}).json()
    doc = json.loads(p.read_text(encoding="utf-8"))
    assert [s["at"] for s in doc["sketches"]] == [[30.0, 5.0]]
    assert [f.get("aruco") or f.get("extrude") for f in doc["features"]] == \
        [f"{t['name']}_shape", f"{t['name']}_body.top"]
    # PATCH settings: the exact dict lands in the feature and the file
    r = client.patch(f"/api/scene/tags/{t['name']}", json={"settings": {"corner_mark": "triangle"},
                                                          "numbers": {"size": 9.0}})
    assert r.status_code == 200
    doc = json.loads(p.read_text(encoding="utf-8"))
    f = doc["features"][-1]
    assert f["settings"] == r.json()["spec"]["settings"] and f["settings"]["corner_mark"] == "triangle"
    assert f["numbers"] == r.json()["spec"]["numbers"] and f["numbers"]["size"] == 9.0
    # the design route says the same as the file
    g = client.get("/api/design").json()
    assert g["text"] == p.read_text(encoding="utf-8") and g["path"] == str(p)


def test_the_old_answers_replayed_on_a_scene_by_hand(client):
    """The routes over the design answer as the Scene API on main does."""
    from aruco_studio.plan import TagSpec
    from aruco_studio.scene import Scene, number_one, renumber, set_first_id
    client.post("/api/scene/new", json={"name": "replay"})
    ref = Scene(name="replay")
    specs = [client.post("/api/new", json={"layout": lay, "target_key": key,
                                           "thickness_mm": th}).json()
             for lay, key, th in (("single", "box40", 3), ("grid", "plate_hole", 0),
                                  ("charuco", "ring", 2))]
    for k, sp in enumerate(specs):
        got = client.post("/api/scene/tags", json={"spec": sp, "x_mm": 100.0 * k,
                                                   "number": True}).json()
        t = ref.add(TagSpec.from_dict(sp), 100.0 * k, 0.0, 0.0)
        number_one(ref, t.name)
        assert got["name"] == t.name and got["spec"] == t.spec.to_dict()
    d = client.post("/api/scene/tags/board1/duplicate?dx_mm=5&dy_mm=7").json()
    c = ref.duplicate("board1", 5.0, 7.0)
    number_one(ref, c.name)
    assert (d["name"], d["x_mm"], d["y_mm"], d["spec"]) == (c.name, c.x_mm, c.y_mm,
                                                            c.spec.to_dict())
    o = client.put("/api/scene/overrides/tag1", json={"id": 30}).json()
    assert set_first_id(ref, "tag1", 30) == []
    assert o["overrides"] == ref.overrides and o["ids"] == plan_tag(ref.get("tag1").spec).data["ids"]
    bad = client.put("/api/scene/overrides/tag1", json={"id": 99999})
    assert bad.status_code == 409 and bad.json()["issues"][0]["field"] == "override"
    rep = client.post("/api/scene/renumber").json()
    want = renumber(ref)
    assert rep["changed"] == want["changed"] and rep["ok"] == want["ok"]
    import re
    strip = lambda x: re.sub(r"#[0-9a-f]{12}", "#uid", json.dumps(x, sort_keys=True))  # noqa: E731
    assert strip(rep["rows"]) == strip(want["rows"])           # uids are random per tag
    sc = client.get("/api/scene").json()
    assert [t["spec"] for t in sc["tags"]] == [t.spec.to_dict() for t in ref.tags]
    assert strip(sc["ledger"]) == strip(ref.ledger) and sc["overrides"] == ref.overrides
    # exports and verify on the same scene
    from aruco_studio.scene import sheet
    e = client.post("/api/scene/export/svg?save=0").json()
    import base64
    assert base64.b64decode(e["inline"]["sheet.svg"]).decode("utf-8") == sheet.to_svg(ref)
    j = client.post("/api/scene/export/json?save=0").json()
    text = base64.b64decode(j["inline"]["replay.arucostudio.json"]).decode("utf-8")
    assert json.loads(text)["schema"] == "arucostudio.scene/2"
    from aruco_studio.scene import loads
    assert [t.spec.to_dict() for t in loads(text).tags] == [t.spec.to_dict() for t in ref.tags]
    v = client.post("/api/scene/verify").json()
    from aruco_studio.verify.report import verify_scene
    w = verify_scene(ref, px_per_mm=10.0)
    w.pop("rows", None)
    assert strip(v) == strip(json.loads(json.dumps(w)))
    # PUT /api/scene with the compiled scene (the Studio's Undo) lands back on the design
    before = client.get("/api/scene").json()
    client.patch("/api/scene/tags/tag1", json={"settings": {"corner_mark": "triangle"}})
    r = client.put("/api/scene", json=before)
    assert r.status_code == 200
    assert [t["spec"] for t in client.get("/api/scene").json()["tags"]] == \
        [t["spec"] for t in before["tags"]]
    # delete and rename
    assert client.delete("/api/scene/tags/board2").status_code == 200
    r = client.patch("/api/scene/tags/charuco1", json={"new_name": "ring"})
    assert r.status_code == 200 and r.json()["name"] == "ring"
    names = [t["name"] for t in client.get("/api/scene").json()["tags"]]
    assert names == ["tag1", "board1", "ring"]


def test_api_target_strokes_holes_as_a_shape_does(client):
    h = client.post("/api/target", json={"shape": "box", "w_mm": 60.0, "h_mm": 40.0,
                                          "holes": [[20.0, 0.0, 6.0]], "thickness_mm": 0.0}).json()
    want = SH.stroke({"rect": [60, 40], "holes": [{"circle": 6, "at": [20, 0]}]})
    assert [[tuple(p) for p in lp] for lp in h["loops_mm"]] == want
    d = client.post("/api/target", json={"shape": "disc", "r_mm": 25.0}).json()
    assert [tuple(p) for p in d["loops_mm"][0]] == SH.stroke({"circle": 50})[0]
    bad = client.post("/api/target", json={"shape": "box", "w_mm": 20.0, "h_mm": 20.0,
                                            "holes": [[30.0, 0.0, 6.0]]})
    assert bad.status_code == 422 and bad.json()["detail"][0]["path"].startswith("holes[0]")


def test_design_routes(client, tmp_path):
    p = copy_example(tmp_path, "forearm")
    assert client.post("/api/design/open", json={"path": str(tmp_path / "nope.json")}).status_code \
        == 404
    home = Path(os.environ["USERPROFILE"]) / "CADExporter"
    assert client.post("/api/design/open", json={"path": str(home / "x.json")}).status_code == 403
    g = client.post("/api/design/open", json={"path": str(p)}).json()
    assert g["state"] == "ok" and g["text"] == p.read_text(encoding="utf-8")
    # PUT: the text kept verbatim
    doc = json.loads(g["text"])
    doc["name"] = "forearm v2"
    text = json.dumps(doc, indent=2) + "\n"
    r = client.put("/api/design", json={"text": text, "hash": g["hash"]})
    assert r.status_code == 200 and p.read_text(encoding="utf-8") == text
    assert client.get("/api/scene").json()["name"] == "forearm v2"
    # a stale hash: 409, nothing written
    r = client.put("/api/design", json={"text": g["text"], "hash": g["hash"]})
    assert r.status_code == 409 and p.read_text(encoding="utf-8") == text
    # not JSON: 422 with line and col
    r = client.put("/api/design", json={"text": '{"schema": "arucostudio.scene/2",\n "name": }'})
    assert r.status_code == 422 and r.json()["detail"][0]["line"] == 2
    # preview: compiled and planned, nothing written
    rev = client.get("/api/design").json()["revision"]
    doc["features"][0]["height"] = 60
    pv = client.post("/api/design/preview", json={"text": json.dumps(doc)}).json()
    assert pv["error"] is None and len(pv["scene"]["tags"]) == 4
    assert pv["scene"]["tags"][0]["spec"]["target"]["h_mm"] == 60.0
    assert pv["scene"]["tags"][0]["plan"]["ok"]
    assert p.read_text(encoding="utf-8") == text and client.get("/api/design").json()["revision"] == rev
    bad = client.post("/api/design/preview", json={"text": "{"}).json()
    assert bad["scene"] is None and bad["error"]["line"] == 1
    # save as: the new file is followed
    q = tmp_path / "copy.arucostudio.json"
    s = client.post("/api/design/save_as", json={"path": str(q)}).json()
    assert s["path"] == str(q) and q.read_text(encoding="utf-8") == text
    rv = client.post("/api/design/reveal", json={"open": False}).json()
    assert rv["opened"] is False and str(q) in " ".join(rv["command"])
    # the old save / open keep working over scenes/
    sv = client.post("/api/scene/save", json={"name": "fa"}).json()
    assert Path(sv["saved"]).exists()
    assert json.loads(Path(sv["saved"]).read_text(encoding="utf-8"))["schema"] == \
        "arucostudio.scene/2"
    assert client.post("/api/scene/open", json={"name": "fa"}).status_code == 200
    assert len(client.get("/api/scene").json()["tags"]) == 4
