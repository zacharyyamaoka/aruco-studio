"""M8a.2: the scene file `arucostudio.scene/2` and the `/1` migration.

* every `/1` scene the e2e suite saved (tests/scene/fixtures_v1/, copied
  from its last run) and a 25-tag scene of every kind of target migrate to
  `/2` and replan byte for byte (each plan's canonical JSON equal); names,
  uids, places, locks, the ledger and the overrides survive;
* the migrated file round-trips: loads_design(dumps_design(d)) == d, and
  dumps(loads(text)) == text;
* writers write `/2` with indent=1 and sorted keys; a newer schema is
  refused with today's message; a parse error says its line and column.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from aruco_studio.plan import TagSpec, plan_tag
from aruco_studio.plan import exports as X
from aruco_studio.plan import newtag as NEW
from aruco_studio.plan import target as T
from aruco_studio.scene import (DesignParseError, Scene, SceneFileError, design, dumps,
                                dumps_design, loads, loads_design, renumber)
from aruco_studio.scene.file import parse_v1

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures_v1"


def v1_text(sc: Scene) -> str:
    """A scene as the `/1` writer wrote it (main before M8a)."""
    d = sc.to_dict()
    for t in d["tags"]:
        t.pop("plan", None)
    return json.dumps(d, indent=1, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"


def scene25() -> Scene:
    """25 tags: boxes, plates, palette faces with and without a body, a box
    with the target editor's old 48-point holes, discs, a sketch profile
    over a body, a flipped face with x_ref, a measured body with a depth,
    locked and hidden tags, an override, the ledger after a renumber."""
    r = random.Random(25)
    sc = Scene(name="twenty-five")
    targets = []
    for key in ("box40", "disc40", "disc4", "dshape", "lshape", "plate_hole", "ring", "hexagon",
                "stadium", "notch", "strip", "triangle"):
        targets.append(T.from_face(key, r.choice([0.0, 3.0])))
    targets.append(T.box(60, 40, 0))
    targets.append(T.box(80, 50, 5))
    loops = [[(-30.0, -20.0), (30.0, -20.0), (30.0, 20.0), (-30.0, 20.0)],
             T.circle_pts(10.0, 0.0, 4.0, 48, cw=True)]
    targets.append(T.from_loops(loops, 2.0, centre=False))           # the old editor's holes
    targets.append(T.disc(25.0, [(0.0, 0.0, 3.0)], 4.0))
    prof = T.box(50, 40, 3)
    prof.kind = "profile"
    prof.face_loops_mm = [prof.box_loop_mm()]
    targets.append(prof)
    free = T.box(45, 45, 0)
    free.kind = "free"
    targets.append(free)
    flip = T.box(40, 40, 3)
    flip.z_sign = -1
    flip.x_ref = (0.0, 1.0)
    targets.append(flip)
    deep = T.box(40, 40, 0)
    deep.has_body = True
    deep.body_mm = {"u0": -20.0, "v0": -20.0, "u1": 20.0, "v1": 20.0, "z0": -30.0, "z1": 0.0,
                    "depth": 30.0, "measured": True}
    targets.append(deep)
    while len(targets) < 25:
        targets.append(T.box(r.choice([40.0, 60.0, 90.0]), r.choice([40.0, 70.0]),
                             r.choice([0.0, 2.0])))
    for k, tg in enumerate(targets):
        lay = r.choice(["single", "grid", "charuco"])
        sp = TagSpec.from_dict(NEW.new_spec(lay, tg.to_dict(), name=f"part {k}"))
        if r.random() < 0.3:
            sp.settings["label"] = dict(sp.settings["label"], on=True, content="id_name")
        sc.add(sp, x_mm=(k % 5) * 110.0 + r.uniform(-5, 5), y_mm=(k // 5) * 100.0,
               rotation_deg=r.choice([0.0, 90.0, 30.0, -12.5]))
    sc.tags[3].locked = True
    sc.tags[7].hidden = True
    sc.overrides[sc.tags[5].name] = 40
    renumber(sc)
    sc.rename(sc.tags[2].name, "renamed")
    sc.presets_used = ["Default"]
    return sc


def scenes_v1():
    out = [(f.name, f.read_text(encoding="utf-8")) for f in sorted(FIX.glob("*.arucostudio.json"))]
    assert len(out) == 3
    out.append(("scene25", v1_text(scene25())))
    return out


def plan_json(spec) -> str:
    return X.to_json(plan_tag(spec))


@pytest.mark.parametrize("name, text", scenes_v1(), ids=[n for n, _ in scenes_v1()])
def test_v1_migrates_and_replans_byte_for_byte(name, text):
    d1 = json.loads(text)
    assert d1["schema"] == "arucostudio.scene/1"
    old = parse_v1(d1)
    new = loads(text)                       # migrated, then compiled
    assert [t.name for t in new.tags] == [t.name for t in old.tags]
    for a, b in zip(old.tags, new.tags):
        assert b.uid == a.uid
        assert (b.x_mm, b.y_mm, b.rotation_deg, b.locked, b.hidden) == \
            (a.x_mm, a.y_mm, a.rotation_deg, a.locked, a.hidden)
        assert b.spec.to_dict() == a.spec.to_dict(), a.name
        assert plan_json(b.spec) == plan_json(a.spec), a.name
        assert b.pose_3d is None                      # every /1 tag still lies z-up at z 0
    assert new.overrides == old.overrides and new.ledger == old.ledger
    assert new.presets_used == old.presets_used and new.name == old.name
    # the migrated file round-trips
    doc = loads_design(text)
    assert doc["schema"] == "arucostudio.scene/2"
    text2 = dumps_design(doc)
    assert loads_design(text2) == doc
    assert dumps(loads(text2)) == text2
    assert loads(text2).to_dict() == new.to_dict()


def test_the_25_tag_scene_keeps_its_shapes_where_it_can():
    sc = scene25()
    doc = design.doc_from_scene(sc)
    feats = [f for f in doc["features"] if "aruco" in f]
    assert len(feats) == 25
    exact = [f["id"] for f in feats if "target" in f]
    # only the sketch profile, the free area, the flipped face and the measured body
    assert len(exact) == 4, exact
    kinds = [list(s["shapes"][0])[1:] for s in doc["sketches"]]
    assert any("rect" in k for k in kinds) and any("loops" in k for k in kinds)
    assert sum("extrude" in f for f in doc["features"]) >= 5


def test_the_writer_and_its_refusals():
    text = dumps(scene25())
    assert text.startswith('{\n "features": [')            # indent=1, sorted keys
    d = json.loads(text)
    assert d["schema"] == "arucostudio.scene/2"
    for bad in ("arucostudio.scene/3", "arucostudio.scene/9"):
        with pytest.raises(SceneFileError, match="newer ArUco Studio"):
            loads_design(json.dumps(dict(d, schema=bad)))
    with pytest.raises(SceneFileError, match="only mm"):
        loads_design(json.dumps(dict(d, units="in")))
    broken = text.replace('"features": [', '"features": [,', 1)
    with pytest.raises(DesignParseError) as e:
        loads_design(broken)
    assert (e.value.line, e.value.col) == (2, 15) and "line 2 col 15" in str(e.value)


def test_unknown_keys_survive_a_round_trip():
    doc = loads_design(dumps(scene25()))
    doc["note"] = "kept"
    doc["features"][1]["note"] = "also kept"
    doc["future_key"] = {"x": 1}
    again = loads_design(dumps_design(doc))
    assert again == doc
    sc, issues = design.compile(again)
    assert any(i.field == "future_key" and i.level == "info" for i in issues)
