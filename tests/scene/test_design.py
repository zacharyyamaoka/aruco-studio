"""M8a.4, M8a.8 and the compile's issues (scene/design.py).

* the forearm: four Targets (120 x 40, 40 x 40, 120 x 40, 40 x 40), each
  with a body 40 or 120 deep, each pose a right-handed orthonormal 4x4 whose
  z is the face's outward normal, each tag's OpenCV frame on its face;
  `tag.front` .. `tag.left`; an edit of one tag's mark splits the list into
  four features (and Renumber alone keeps it one, with `marker_ids`);
* sugar expands to what POST /api/new stores; after one write the feature
  holds the exact settings / numbers and no sugar;
* errors on their JSON path: a hole outside, a curved side, an unknown
  feature, a missing shape; unknown keys kept as `info`;
* the edits: add / delete (what the tag alone used goes too) / rename (the
  uid stays) / move (the sketch, or the shape in a shared sketch).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from aruco_studio.core import presets as P
from aruco_studio.plan import TagSpec, plan_tag
from aruco_studio.plan import newtag as NEW
from aruco_studio.plan import shapes as SH
from aruco_studio.plan import target as T
from aruco_studio.scene import design as DS
from aruco_studio.scene import loads_design, renumber
from aruco_studio.scene.model import mat_mul

ROOT = Path(__file__).resolve().parents[2]
EX = ROOT / "examples"


def example(name):
    return loads_design((EX / f"{name}.arucostudio.json").read_text(encoding="utf-8"))


def errors(issues, level="error"):
    return [(i.field, i.text) for i in issues if i.level == level]


def cols(M):
    return [[M[r * 4 + c] for r in range(3)] for c in range(4)]


# ------------------------------------------------------------ the forearm (M8a.4)

def test_the_forearm_four_faces():
    sc, issues = DS.compile(example("forearm"))
    assert not errors(issues)
    assert [t.name for t in sc.tags] == ["tag.front", "tag.right", "tag.back", "tag.left"]
    want = {"tag.front": (120, 40, (0, -1, 0)), "tag.right": (40, 120, (1, 0, 0)),
            "tag.back": (120, 40, (0, 1, 0)), "tag.left": (40, 120, (-1, 0, 0))}
    for t in sc.tags:
        w, depth, n = want[t.name]
        tg = t.spec.target
        assert (tg.w_mm, tg.h_mm) == (w, 40) and tg.has_body
        assert tg.body_mm["depth"] == depth
        assert t.spec.name == "forearm" and t.spec.settings["layout"] == "charuco"
        u, v, z, o = cols(t.pose_3d)
        for a in (u, v, z):
            assert abs(sum(c * c for c in a) - 1.0) < 1e-12
        assert abs(sum(a * b for a, b in zip(u, v))) < 1e-12
        cross = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
        assert cross == pytest.approx(z) and z == pytest.approx(list(n))
        # the face centre lies on the box's side, half-way up
        half = {"tag.front": 20, "tag.back": 20, "tag.right": 60, "tag.left": 60}[t.name]
        assert sum(a * b for a, b in zip(o, n)) == pytest.approx(half)
        assert o[2] == pytest.approx(20.0)
        # OpenCV's frame (the plan's, in the target frame) lands on that face
        p = plan_tag(t.spec)
        assert p.ok, p.data["errors"]
        oc = p.data["frames"]["opencv_target"]
        W = mat_mul(t.pose_3d, oc)
        wu, wv, wz, wo = cols(W)
        sign = 1 if oc[10] > 0 else -1                 # a board's OpenCV z points into the face
        assert sign == (1 if t.spec.settings["layout"] == "single" else -1)
        assert wz == pytest.approx([sign * c for c in n], abs=1e-9)
        off = sum((a - b) * c for a, b, c in zip(wo, o, n))
        assert off == pytest.approx(p.data["frames"]["opencv_target"][11], abs=1e-9)
        assert 0.0 <= off <= 3.0
        along = [sum((a - b) * c for a, b, c in zip(wo, o, ax)) for ax in (u, v)]
        assert abs(along[0]) <= w / 2 and abs(along[1]) <= 20
    # the 2D view: each side unfolded about its edge, outside the box
    assert (sc.get("tag.front").x_mm, sc.get("tag.front").y_mm) == (0.0, -40.0)
    assert (sc.get("tag.right").x_mm, sc.get("tag.right").rotation_deg) == (80.0, 90.0)
    assert sc.get("tag.front").source["hinge_xy"] == [[-60.0, -20.0], [60.0, -20.0]]


def test_one_edit_splits_the_list_and_renumber_does_not():
    doc = example("forearm")
    doc["features"][1].pop("marker_ids")      # the list as typed, before the shipped ids
    sc, _ = DS.compile(doc)
    renumber(sc)
    ids = [t.spec.numbers["marker_id"] for t in sc.tags]
    assert len(set(ids)) == 4
    DS.write_back(doc, sc)
    tags = [f for f in doc["features"] if "aruco" in f]
    assert len(tags) == 1 and tags[0]["marker_ids"] == ids and "layout" not in tags[0]
    back, _ = DS.compile(doc)
    assert [t.spec.to_dict() for t in back.tags] == [t.spec.to_dict() for t in sc.tags]
    # one tag's mark: four features, the file says so
    assert back.edit("tag.right", settings={"corner_mark": "none"}) == []
    DS.write_back(doc, back)
    tags = [f for f in doc["features"] if "aruco" in f]
    assert [f["id"] for f in tags] == ["tag.front", "tag.right", "tag.back", "tag.left"]
    assert [f["aruco"] for f in tags] == ["forearm.front", "forearm.right", "forearm.back",
                                          "forearm.left"]
    assert tags[1]["settings"]["corner_mark"] == "none"
    again, _ = DS.compile(doc)
    assert [t.name for t in again.tags] == [t.name for t in back.tags]
    assert [t.uid for t in again.tags] == [t.uid for t in back.tags]
    assert [t.spec.to_dict() for t in again.tags] == [t.spec.to_dict() for t in back.tags]


# ------------------------------------------------------------ sugar (M8a.8)

def _preset():
    return P.default_preset()


def test_sugar_expands_to_what_api_new_stores():
    doc = {"schema": DS.SCHEMA, "sketches": [{"id": "sk", "shapes": [{"id": "a", "rect": [80, 50]}]}],
           "features": [{"id": "t", "aruco": "a", "layout": "charuco", "cols": 5, "rows": 3,
                         "label": "#id"}]}
    sc, issues = DS.compile(doc)
    assert not errors(issues)
    s = sc.get("t").spec
    want = NEW.new_spec("charuco", T.box(80, 50, 0).to_dict(), None, key="t")
    want["settings"]["force"] = [5, 3]
    want["settings"]["label"] = dict(want["settings"]["label"], on=True, content="id")
    assert s.settings == want["settings"] and s.numbers == want["numbers"]
    for k in ("origin_v", "cells", "label"):
        assert k in s.settings
    from aruco_studio.core import label as L
    # a new tag stores label rule 3 (M6a, label.NEW_RULE; Merge 1), a 3D make and Holes avoid
    assert s.settings["label"]["rule"] == L.NEW_RULE and s.settings["cells"] == P.cell_setting(_preset())
    assert s.settings["make"]["by"] == "print3d" and s.settings["holes"] == "avoid"
    # one write (a size typed through the Scene API): exact settings / numbers, no sugar
    sc.edit("t", numbers={"size": 6.0})
    DS.write_back(doc, sc)
    f = doc["features"][0]
    assert not set(DS.SUGAR) & set(f)
    assert f["settings"] == s.settings and f["numbers"] == dict(s.numbers, size=6.0)
    back, _ = DS.compile(doc)
    assert back.get("t").spec.to_dict() == sc.get("t").spec.to_dict()


def test_sugar_keys_one_by_one():
    base = {"schema": DS.SCHEMA, "sketches": [{"id": "sk", "shapes": [{"id": "a", "rect": [60, 60]}]}],
            "features": [{"id": "b", "extrude": "a", "height": 4}]}

    def spec_of(**f):
        d = copy.deepcopy(base)
        d["features"].append(dict({"id": "t", "aruco": "b.top"}, **f))
        sc, issues = DS.compile(d)
        assert not errors(issues), issues
        return sc.get("t").spec, sc
    s, _ = spec_of(mark="triangle", pins="round", turn=90, op="new", mode="both",
                   dictionary="DICT_5X5_100")
    assert (s.settings["corner_mark"], s.settings["pin"], s.settings["turn"], s.settings["op"],
            s.settings["mode"], s.settings["dictionary"]) == ("triangle", "round", 90, "new", "both",
                                                              "DICT_5X5_100")
    s, _ = spec_of(mode="auto")
    assert s.settings["mode"] == "black"                       # Auto on a body: Black only
    s, _ = spec_of(size=20)
    assert s.numbers["size"] == 20.0 and s.settings["size_auto"] is False
    s, _ = spec_of(label="Arm 3")
    assert s.settings["label"]["content"] == "custom" and s.settings["label"]["text"] == "Arm 3"
    s, _ = spec_of(perimeter="profile")
    assert s.settings["trim"] == "both"
    s, sc = spec_of(first_id=7, name="arm")
    assert sc.overrides == {"t": 7} and s.numbers["marker_id"] == 7 and s.name == "arm"
    s, _ = spec_of(settings={"layout": "single", "mode": "both", "op": "new"}, layout="grid")
    assert s.settings == {"layout": "single", "mode": "both", "op": "new"}


def test_a_preset_by_name():
    doc = example("plate_charuco")
    seen = []

    def presets(name):
        seen.append(name)
        return dict(_preset(), name=name)
    sc, issues = DS.compile(doc, presets)
    assert seen and set(seen) == {"0.32mm SPEED @MK4IS 0.6 - Aruco"}
    assert sc.presets_used == ["0.32mm SPEED @MK4IS 0.6 - Aruco"]
    sc2, issues2 = DS.compile(doc)                           # unknown here: Default, a warn
    assert [i.field for i in issues2 if i.level == "warn"] == ["preset"]


# ------------------------------------------------------------ errors on their paths

def _doc(shapes, features):
    return {"schema": DS.SCHEMA, "sketches": [{"id": "sk", "shapes": shapes}], "features": features}


def test_a_hole_outside_is_an_error_on_its_path():
    d = _doc([{"id": "a", "rect": [40, 40], "holes": [{"circle": 5, "at": [50, 0]}]},
              {"id": "b", "rect": [30, 30], "at": [100, 0]}],
             [{"id": "t1", "aruco": "a"}, {"id": "t2", "aruco": "b"}])
    sc, issues = DS.compile(d)
    assert ("sketches[0].shapes[0].holes[0]", "a hole must lie inside its shape") in errors(issues)
    assert [t.name for t in sc.tags] == ["t2"]                # the rest compiles


def test_a_tag_on_a_circles_side_is_an_error_naming_curved():
    d = _doc([{"id": "d", "circle": 50}], [{"id": "cyl", "extrude": "d", "height": 20},
                                           {"id": "t", "aruco": ["cyl.top", "cyl.side0"]}])
    sc, issues = DS.compile(d)
    errs = errors(issues)
    assert len(errs) == 1 and errs[0][0] == "features[1].aruco[1]" and "curved" in errs[0][1]
    assert [t.name for t in sc.tags] == ["t.top"]


def test_unknown_things():
    d = _doc([{"id": "a", "rect": [40, 40], "colour": "red"}],
             [{"id": "x", "revolve": "a"}, {"id": "t", "aruco": "a", "wobble": 1},
              {"id": "u", "aruco": "nope"}, {"id": "v", "aruco": "a.top"},
              {"id": "a", "aruco": "a"}])
    d["mystery"] = True
    sc, issues = DS.compile(d)
    errs = dict(errors(issues))
    assert "unknown feature" in errs["features[0]"]
    assert "no shape 'nope'" in errs["features[2].aruco"]
    assert "is a shape, not a body" in errs["features[3].aruco"]
    assert "taken" in errs["features[4].id"]
    infos = [i.field for i in issues if i.level == "info"]
    assert {"mystery", "sketches[0].shapes[0].colour", "features[1].wobble"} <= set(infos)
    assert [t.name for t in sc.tags] == ["t"]


# ------------------------------------------------------------ the edits

def test_add_delete_rename_move():
    doc = example("plate_charuco")
    sp = TagSpec.from_dict(NEW.new_spec("single", T.box(30, 30, 3).to_dict()))
    DS.add_tag(doc, sp, 100.0, 0.0, 90.0, name="extra")
    sc, issues = DS.compile(doc)
    assert not errors(issues)
    e = sc.get("extra")
    assert (e.x_mm, e.y_mm, e.rotation_deg) == (100.0, 0.0, 90.0)
    assert e.spec.target.to_dict() == sp.target.to_dict()
    assert {f["id"] for f in doc["features"]} >= {"extra", "extra_body"}
    # rename: the uid stays (the ledger knows the tag by it)
    DS.rename_tag(doc, "extra", "side_tag")
    sc2, _ = DS.compile(doc)
    assert sc2.get("side_tag").uid == "extra" and sc2.get("side_tag").spec.key == "extra"
    with pytest.raises(ValueError, match="taken"):
        DS.rename_tag(doc, "side_tag", "plate")             # a shape's id
    # move: a sketch with one shape moves; in a shared sketch the shape moves
    DS.move_tag(doc, "side_tag", 120.0, 5.0, 0.0)
    sk = next(s for s in doc["sketches"] if s["id"] == "extra_sketch")
    assert sk["at"] == [120.0, 5.0] and "rot" not in sk
    DS.move_tag(doc, "tag", 3.0, 4.0, 0.0)
    assert doc["sketches"][0]["at"] == [3.0, 4.0]
    two = _doc([{"id": "a", "rect": [30, 30]}, {"id": "b", "rect": [30, 30], "at": [40, 0]}],
               [{"id": "t1", "aruco": "a"}, {"id": "t2", "aruco": "b"}])
    DS.move_tag(two, "t2", 50.0, 10.0, 0.0)
    assert two["sketches"][0]["shapes"][1]["at"] == [50.0, 10.0] and "at" not in two["sketches"][0]
    # delete: what only that tag used goes too; a shape someone else uses stays
    DS.delete_tag(doc, "side_tag")
    assert "extra_sketch" not in {s["id"] for s in doc["sketches"]}
    assert "extra_body" not in {f["id"] for f in doc["features"]}
    DS.delete_tag(two, "t1")
    assert [s["id"] for s in two["sketches"][0]["shapes"]] == ["b"]


def test_doc_from_scene_round_trips_every_kind_of_target():
    from aruco_studio.scene import Scene
    sc = Scene(name="kinds")
    tgts = [T.box(40, 30, 0), T.box(40, 30, 2.5), T.from_face("ring", 3), T.from_face("lshape", 0),
            T.disc(20, [(5, 0, 2)], 4)]
    prof = T.box(50, 40, 3)
    prof.kind = "profile"
    prof.face_loops_mm = [prof.box_loop_mm()]
    flip = T.box(40, 40, 3)
    flip.z_sign = -1
    flip.x_ref = (0.0, 1.0)
    for k, tg in enumerate(tgts + [prof, flip]):
        sc.add(TagSpec.from_dict(NEW.new_spec("single", tg.to_dict())), x_mm=k * 70.0,
               rotation_deg=15.0 * k)
    doc = DS.doc_from_scene(sc)
    back, issues = DS.compile(doc)
    assert not errors(issues)
    assert back.to_dict() == sc.to_dict()
    exact = [f["id"] for f in doc["features"] if "target" in f]
    assert exact == [sc.tags[5].name, sc.tags[6].name]      # only what a shape cannot say
    assert [f.get("extrude") for f in doc["features"] if "extrude" in f]


def test_shapes_2d_places_every_shape():
    out = DS.shapes_2d(example("sticker_sheet"))
    assert [s["shape"] for s in out] == ["a", "b", "c", "d"]
    d = out[3]["loops"]
    assert len(d) == 2 and min(x for x, _ in d[0]) == pytest.approx(55.0)
    assert json.dumps(out)
