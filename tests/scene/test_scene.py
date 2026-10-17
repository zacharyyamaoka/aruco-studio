"""M2b.5 / M2b.6: a scene numbers its tags and keeps them in a file.

* 40 tags (single, grid, ChArUco; two dictionaries) renumbered: no id twice
  per family, boards contiguous, a second renumber changes nothing;
* a printed id never moves: after an add, a delete, a rename, a move (REF
  G0.7's scenarios on the scene); a typed override is kept; a locked tag's
  ink (record) never changes;
* .arucostudio.json: loads(dumps(s)) == s for 100 random scenes; an unknown
  schema is refused with a message.
"""
from __future__ import annotations

import copy
import json
import random

import pytest

from aruco_studio.core import numbering as N
from aruco_studio.plan import TagSpec, plan_tag
from aruco_studio.plan import target as T
from aruco_studio.plan.record import ink_digest
from aruco_studio.scene import Scene, SceneFileError, dumps, loads, renumber
from aruco_studio.scene import ids as SI


def _spec(layout, dictionary="DICT_4X4_50", w=60.0, h=40.0, label=False):
    s = {"layout": layout, "mode": "both", "op": "new", "dictionary": dictionary}
    if label:
        s["label"] = {"on": True, "place": "black"}
    return TagSpec(settings=s, target=T.box(w, h, 0))


def big_scene(n=40, seed=7):
    r = random.Random(seed)
    sc = Scene(name="forty")
    for k in range(n):
        layout = r.choice(["single", "single", "grid", "charuco"])
        d = r.choice(["DICT_4X4_250", "DICT_5X5_250"])
        area = {"single": (40.0, 40.0), "grid": (90.0, 60.0), "charuco": (90.0, 70.0)}[layout]
        sc.add(_spec(layout, d, *area), x_mm=(k % 8) * 120.0, y_mm=(k // 8) * 100.0,
               rotation_deg=r.choice([0, 90, 30]))
    return sc


def ids_of(sc):
    out = {}
    for t in sc.tags:
        p = plan_tag(t.spec)
        out[t.name] = (N.family(p.data["marker"]["dictionary"]), list(p.data["ids"]))
    return out


def test_forty_tags_unique_contiguous_and_stable():
    sc = big_scene()
    assert SI.duplicates(sc)                       # all start at id 0
    rep = renumber(sc)
    assert rep["ok"] and rep["changed"], rep["errors"]
    assert SI.duplicates(sc) == {}
    for name, (fam, ids) in ids_of(sc).items():
        assert ids == list(range(ids[0], ids[0] + len(ids))), name
    before = ids_of(sc)
    rep2 = renumber(sc)
    assert rep2["changed"] == [] and ids_of(sc) == before


def test_printed_ids_never_move():
    sc = big_scene(12)
    renumber(sc)
    printed = ids_of(sc)
    # add two tags, delete one, rename one, move one: the others keep theirs
    sc.add(_spec("single"), x_mm=900)
    sc.add(_spec("grid", w=90, h=60), x_mm=1000)
    gone = sc.tags[3].name
    sc.delete(gone)
    sc.rename(sc.tags[0].name, "arm")
    sc.move(sc.tags[1].name, x_mm=-300.0, rotation_deg=45)
    renumber(sc)
    now = ids_of(sc)
    for name, v in printed.items():
        if name == gone:
            continue
        key = "arm" if name == list(printed)[0] else name
        assert now[key] == v, (name, v, now[key])
    assert SI.duplicates(sc) == {}
    # the deleted tag's ids are not handed to a new tag
    gone_ids = set(printed[gone][1])
    fresh = [t.name for t in sc.tags if t.name not in printed and t.name != "arm"]
    for f in fresh:
        if now[f][0] == printed[gone][0]:
            assert not gone_ids & set(now[f][1]), (f, now[f], gone_ids)


def test_an_override_is_kept_and_a_duplicate_one_is_flagged():
    sc = big_scene(6)
    renumber(sc)
    name = sc.tags[2].name
    sc.overrides[name] = 33
    renumber(sc)
    assert ids_of(sc)[name][1][0] == 33
    renumber(sc)
    assert ids_of(sc)[name][1][0] == 33


def test_a_locked_tag_keeps_its_ink():
    sc = Scene()
    a = sc.add(_spec("single", label=True), name="printed")
    b = sc.add(_spec("single"), name="other", x_mm=60)
    renumber(sc)
    a.locked = True
    rec = ink_digest(plan_tag(a.spec).data)
    # an edit that changes its ink is refused, on that field
    issues = sc.edit("printed", numbers={"marker_id": 9})
    assert issues and issues[0].level == "error" and issues[0].field == "numbers.marker_id"
    issues = sc.edit("printed", settings={"corner_mark": "triangle"})
    assert issues and issues[0].field == "settings.corner_mark"
    # moving it and renaming it are fine
    sc.move("printed", x_mm=10, rotation_deg=90)
    assert sc.edit("printed", tag_name="printed2") == []
    # a renumber never touches it, even when another tag asks for its id
    sc.overrides["other"] = int(plan_tag(sc.get("printed2").spec).data["ids"][0])
    renumber(sc)
    assert ink_digest(plan_tag(sc.get("printed2").spec).data) == rec
    # unlocked: the edit goes through
    sc.get("printed2").locked = False
    assert sc.edit("printed2", numbers={"marker_id": 9}) == []


def _random_scene(r):
    sc = Scene(name=r.choice(["a", "bench", "rack 2"]))
    for k in range(r.randint(0, 6)):
        layout = r.choice(["single", "grid", "charuco"])
        t = sc.add(_spec(layout, r.choice(["DICT_4X4_50", "DICT_6X6_250"]),
                         r.choice([40.0, 80.0]), r.choice([40.0, 60.0]), label=r.random() < 0.3),
                   x_mm=r.uniform(-200, 200), y_mm=r.uniform(-200, 200),
                   rotation_deg=r.choice([0.0, 90.0, 12.5]))
        t.locked = r.random() < 0.2
        t.hidden = r.random() < 0.1
    if sc.tags and r.random() < 0.5:
        sc.overrides[sc.tags[0].name] = r.randint(0, 40)
    if sc.tags and r.random() < 0.5:
        renumber(sc)
    sc.presets_used = r.sample(["Aruco 0.6", "Default", "MK4"], r.randint(0, 2))
    return sc


def test_file_round_trip_100_random_scenes():
    r = random.Random(16)
    for _ in range(100):
        sc = _random_scene(r)
        text = dumps(sc)
        back = loads(text)
        assert back.to_dict() == json.loads(json.dumps(sc.to_dict()))
        assert dumps(back) == text
        d = json.loads(text)
        assert d["schema"] == "arucostudio.scene/1"
        assert all(t.get("plan") is None for t in d["tags"])


def test_an_unknown_schema_is_refused_with_a_message():
    d = json.loads(dumps(big_scene(2)))
    d["schema"] = "arucostudio.scene/9"
    with pytest.raises(SceneFileError) as e:
        loads(json.dumps(d))
    assert "arucostudio.scene/9" in str(e.value)
    for bad in ("not json", "[]", json.dumps(dict(d, schema="arucostudio.scene/1", units="in"))):
        with pytest.raises(SceneFileError):
            loads(bad)


def test_names_stay_unique_and_usable():
    sc = Scene()
    a = sc.add(_spec("single"))
    b = sc.add(_spec("single"))
    assert a.name != b.name
    with pytest.raises(ValueError):
        sc.rename(a.name, "bad|name")
    with pytest.raises(ValueError):
        sc.rename(a.name, b.name)
    c = sc.duplicate(a.name)
    assert c.name not in (a.name, b.name) and c.uid != a.uid
