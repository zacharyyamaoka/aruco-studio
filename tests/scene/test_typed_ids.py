"""Renumber all and typed ids (lane/scene-fixes, 2026-10-17: the gallery's
finding 1, docs/status/gallery.md).

The IDs ledger's rules (core.numbering, the add-in's ArUco IDs): every
visible tag is numbered and no two print one id; a typed first id (an
override) is kept as typed; a locked (printed) tag keeps its ids. A design
file types an id as `first_id` (sugar); the Studio's write moves it into
`overrides` and writes that feature exact, so its numbers keep the id:

* the sticker sheet (typed 0, 1, 2, 8): Renumber all keeps them and the
  file written back plans them (it used to send every tag to #0);
* any write keeps the untouched tags' typed ids (a move of one tag);
* a typed list (`first_id` per face; `null` = auto) and exact numbers whose
  `first_id` differs;
* a file the old write-back left (sugar, the ids in `overrides`, no
  `first_id`) plans its typed ids, and Back to auto keeps the ids;
* Renumber all ends unique: new tags go round the typed and the locked;
* a list face that does not compile stays in the file, its typed id too.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from aruco_studio.core import presets as P
from aruco_studio.plan import plan_tag
from aruco_studio.scene import design as DS
from aruco_studio.scene import loads_design, renumber, set_first_id
from aruco_studio.scene.ids import duplicates

ROOT = Path(__file__).resolve().parents[2]
TYPED = {"t1": 0, "t2": 1, "t3": 2, "t4": 8}         # the sticker sheet's first_id


def example(name):
    return loads_design((ROOT / "examples" / f"{name}.arucostudio.json").read_text(encoding="utf-8"))


def presets():
    """The built-in catalog: Default and the sticker printers (no PrusaSlicer)."""
    return {n: p for n, p, _k in P.catalog_all(P.MemoryStore(), None)["items"]}


def firsts(sc):
    return {t.name: t.spec.numbers["marker_id"] for t in sc.tags}


def ids_of(sc):
    return {t.name: plan_tag(t.spec).data["ids"] for t in sc.tags}


def written(doc, sc, pr=None):
    """`sc` written back into `doc`, through the file's JSON, compiled again."""
    DS.write_back(doc, sc, pr)
    doc2 = json.loads(json.dumps(doc))
    back, _issues = DS.compile(doc2, pr)
    return doc2, back


def test_renumber_all_keeps_the_sticker_sheets_typed_ids():
    pr = presets()
    doc = example("sticker_sheet")
    sc, _ = DS.compile(doc, pr)
    assert sc.overrides == TYPED and firsts(sc) == TYPED
    before = ids_of(sc)
    rep = renumber(sc)
    assert rep["ok"] and rep["changed"] == [] and rep["duplicates"] == {}
    assert {r["tag"]: r["final"] for r in rep["rows"]} == TYPED
    doc2, back = written(doc, sc, pr)
    # the typed ids moved into `overrides`; each feature is exact, its numbers keep them
    assert doc2["overrides"] == TYPED
    tags = [f for f in doc2["features"] if "aruco" in f]
    assert not any("first_id" in f for f in tags)
    assert [f["numbers"]["marker_id"] for f in tags] == [0, 1, 2, 8]
    # the file plans what the Renumber said: no tag sent to #0
    assert firsts(back) == TYPED and back.overrides == TYPED
    assert ids_of(back) == before and duplicates(back) == {}
    assert [t.spec.to_dict() for t in back.tags] == [t.spec.to_dict() for t in sc.tags]
    # a second Renumber all changes nothing, and its file is the same
    assert renumber(back)["changed"] == []
    doc3, again = written(copy.deepcopy(doc2), back, pr)
    assert doc3["features"] == doc2["features"] and firsts(again) == TYPED


def test_any_write_keeps_the_untouched_tags_typed_ids():
    pr = presets()
    doc = example("sticker_sheet")
    sc, _ = DS.compile(doc, pr)
    sc.move("t1", 5.0, 0.0)
    _doc2, back = written(doc, sc, pr)
    assert firsts(back) == TYPED and back.overrides == TYPED
    assert back.get("t1").x_mm == 5.0


def test_a_typed_list_keeps_each_faces_first_id():
    doc = example("forearm")
    f = next(f for f in doc["features"] if "aruco" in f)
    f.pop("marker_ids")
    f["first_id"] = [0, None, 10, 16]             # the right face on auto
    sc, _ = DS.compile(doc)
    assert sc.overrides == {"tag.front": 0, "tag.back": 10, "tag.left": 16}
    renumber(sc)
    got = firsts(sc)
    assert (got["tag.front"], got["tag.back"], got["tag.left"]) == (0, 10, 16)
    assert duplicates(sc) == {}
    doc2, back = written(doc, sc)
    assert firsts(back) == got and back.overrides == sc.overrides
    assert [t.spec.to_dict() for t in back.tags] == [t.spec.to_dict() for t in sc.tags]
    tags = [f for f in doc2["features"] if "aruco" in f]
    assert len(tags) == 1 and "first_id" not in tags[0]          # still one feature
    assert tags[0]["marker_ids"] == [got[t.name] for t in sc.tags]


def test_exact_numbers_keep_a_typed_first_id_that_differs():
    doc = {"schema": DS.SCHEMA, "sketches": [{"id": "sk", "shapes": [{"id": "a", "rect": [40, 40]}]}],
           "features": [{"id": "t", "aruco": "a", "layout": "single"}]}
    sc, _ = DS.compile(doc)
    spec = sc.get("t").spec.to_dict()
    doc["features"][0].update(settings=spec["settings"], numbers=dict(spec["numbers"], marker_id=3),
                              first_id=5)
    sc, _ = DS.compile(doc)
    assert firsts(sc) == {"t": 5} and sc.overrides == {"t": 5}   # first_id wins, as typed
    renumber(sc)
    doc2, back = written(doc, sc)
    f = doc2["features"][0]
    assert "first_id" not in f and f["numbers"]["marker_id"] == 5 and doc2["overrides"] == {"t": 5}
    assert firsts(back) == {"t": 5}


def test_a_file_the_old_write_back_left_plans_its_typed_ids():
    """What Renumber all wrote before the fix: the sugar without `first_id`,
    the ids only in `overrides`. It planned every tag as #0; now a tag
    whose numbers are still sugar takes its first id from `overrides`."""
    pr = presets()
    doc = example("sticker_sheet")
    for f in doc["features"]:
        f.pop("first_id", None)
    doc["overrides"] = dict(TYPED)
    sc, _ = DS.compile(doc, pr)
    assert firsts(sc) == TYPED and duplicates(sc) == {}
    assert renumber(sc)["changed"] == []
    # Back to auto on t4: it keeps its ids until the next Renumber (scene.set_first_id)
    assert set_first_id(sc, "t4", None) == []
    doc2, back = written(doc, sc, pr)
    assert back.overrides == {"t1": 0, "t2": 1, "t3": 2}
    assert firsts(back) == TYPED
    t4 = next(f for f in doc2["features"] if f.get("id") == "t4")
    assert t4["numbers"]["marker_id"] == 8                         # written exact
    # exact numbers keep their own marker_id: an override does not move them
    doc2["overrides"]["t4"] = 30
    sc3, _ = DS.compile(doc2, pr)
    assert sc3.get("t4").spec.numbers["marker_id"] == 8


def test_renumber_all_ends_unique_round_the_typed_and_the_locked():
    pr = presets()
    doc = example("sticker_sheet")
    doc["sketches"][0]["shapes"] += [{"id": "e", "rect": [30, 30], "at": [0, -50]},
                                     {"id": "g", "rect": [30, 30], "at": [40, -50]}]
    doc["features"] += [{"id": "t5", "aruco": "e", "layout": "single"},          # #0, as t1
                        {"id": "t6", "aruco": "g", "layout": "single", "locked": True,
                         "first_id": 12}]                                        # printed #12
    sc, _ = DS.compile(doc, pr)
    assert duplicates(sc)
    rep = renumber(sc)
    assert rep["ok"] and rep["duplicates"] == {}
    _doc2, back = written(doc, sc, pr)
    m = firsts(back)
    assert (m["t1"], m["t2"], m["t3"], m["t4"]) == (0, 1, 2, 8)    # typed: kept
    assert m["t6"] == 12 and back.get("t6").locked                # locked: kept
    assert m["t5"] not in range(0, 13)                            # auto: round them, never #0
    assert ids_of(back) == ids_of(sc) and duplicates(back) == {}


def test_a_list_face_that_does_not_compile_stays_in_the_file():
    doc = {"schema": DS.SCHEMA,
           "sketches": [{"id": "sk", "shapes": [{"id": "a", "rect": [40, 40]},
                                                {"id": "b", "rect": [40, 40], "at": [60, 0]}]}],
           "features": [{"id": "t", "aruco": ["a", "nope", "b"], "layout": "single",
                         "first_id": [3, 4, 5]}]}
    sc, issues = DS.compile(doc)
    assert [t.name for t in sc.tags] == ["t.a", "t.b"]
    assert [i.field for i in issues if i.level == "error"] == ["features[0].aruco[1]"]
    renumber(sc)
    doc2, back = written(doc, sc)
    assert firsts(back) == {"t.a": 3, "t.b": 5}
    refs = sorted(r for f in doc2["features"] for r in DS._refs(f))
    assert refs == ["a", "b", "nope"]
    left = next(f for f in doc2["features"] if f.get("aruco") == ["nope"])
    assert left["id"] == "t" and left["first_id"] == [4]
