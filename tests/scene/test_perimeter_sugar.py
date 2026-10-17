"""The `perimeter` sugar (lane/scene-fixes, 2026-10-17: the gallery's
finding 2, docs/status/gallery.md).

M6 d: "A sticker has a Perimeter: Marker / Profile (on a 3D tag that row IS
Trim excess)". The sugar writes what the Inspector's Perimeter row writes
(studio/src/inspector/Inspector.tsx):

* a 3D printed tag: Marker = `settings.trim` {rule 1, axes both, margin 0,
  force false}, the body trimmed to the tag's outline (the plan's last part
  "trim"); Profile = no trim, the body keeps its outline (it used to write
  the strings "off" / "both", which the plan reads as off, inverted too);
* a sticker, on a bare shape or on a body's face: `settings.make.perimeter`;
* the sugar plans exactly as the Inspector's edit of the same tag;
* a 3D tag on a bare shape stores the trim and has nothing to cut;
* any other value is an error on its path.
"""
from __future__ import annotations

import copy

from aruco_studio.core import presets as P
from aruco_studio.plan import TagSpec, plan_tag
from aruco_studio.scene import design as DS

STICKER = next(n for n, p, _k in P.catalog_all(P.MemoryStore(), None)["items"]
               if P.kind_of(p) == "sticker")
TRIM_BOTH = {"rule": 1, "axes": "both", "margin_mm": 0.0, "force": False}   # the Inspector's Marker


def presets():
    return {n: p for n, p, _k in P.catalog_all(P.MemoryStore(), None)["items"]}


def compiled(*features, shapes=None):
    doc = {"schema": DS.SCHEMA,
           "sketches": [{"id": "sk", "shapes": shapes or [
               {"id": "a", "rect": [50, 50]}, {"id": "b", "rect": [50, 50], "at": [70, 0]}]}],
           "features": [{"id": "body", "extrude": "a", "height": 3}] + list(features)}
    sc, issues = DS.compile(doc, presets())
    return sc, issues


def errors(issues):
    return [(i.field, i.text) for i in issues if i.level == "error"]


def test_a_3d_tags_perimeter_is_trim_excess():
    sc, issues = compiled({"id": "m", "aruco": "body.top", "layout": "single", "perimeter": "marker"},
                          {"id": "p", "aruco": "body.top", "layout": "single", "perimeter": "profile"},
                          {"id": "n", "aruco": "body.top", "layout": "single"})
    assert not errors(issues)
    m, p, n = (sc.get(k).spec for k in "mpn")
    assert m.settings["make"]["by"] == "print3d"
    assert m.settings["trim"] == TRIM_BOTH
    assert "trim" not in p.settings and "perimeter" not in p.settings["make"]
    assert p.to_dict() == dict(n.to_dict(), key="p")         # Profile: what a tag has untyped
    pm, pp = plan_tag(m), plan_tag(p)
    assert pm.ok and pp.ok
    assert pm.data["parts"][-1] == "trim" and pm.data["trim"] is not None
    assert "trim" not in pp.data["parts"]
    assert pm.data["guides"]["trim"]["outline"]                # the cut the body gets


def test_the_sugar_plans_as_the_inspectors_perimeter_row():
    sc, _ = compiled({"id": "m", "aruco": "body.top", "layout": "grid", "cols": 3, "rows": 2,
                      "size": 9, "perimeter": "marker"},
                     {"id": "p", "aruco": "body.top", "layout": "grid", "cols": 3, "rows": 2,
                      "size": 9, "perimeter": "profile"})
    m, p = sc.get("m").spec, sc.get("p").spec
    # the row's Marker on the Profile tag, and its Profile on the Marker tag
    assert sc.edit("p", settings={"trim": dict(TRIM_BOTH)}) == []
    assert sc.edit("m", settings={"trim": None}) == []
    a = TagSpec.from_dict(dict(sc.get("p").spec.to_dict(), key="m"))      # the record's key aside
    b = TagSpec.from_dict(dict(sc.get("m").spec.to_dict(), key="p"))
    assert a.to_dict() == m.to_dict() and b.to_dict() == p.to_dict()
    assert plan_tag(a).to_dict() == plan_tag(m).to_dict()
    assert plan_tag(b).to_dict() == plan_tag(p).to_dict()


def test_a_stickers_perimeter_stays_make_perimeter():
    sc, issues = compiled(
        {"id": "on_body", "aruco": "body.top", "preset": STICKER, "layout": "single",
         "perimeter": "profile"},
        {"id": "bare", "aruco": "b", "preset": STICKER, "layout": "single", "perimeter": "profile"},
        {"id": "bare_m", "aruco": "b", "preset": STICKER, "layout": "single", "perimeter": "marker"},
        shapes=[{"id": "a", "rect": [50, 50]}, {"id": "b", "circle": 50, "at": [70, 0]}])
    assert not errors(issues)
    for name, want in (("on_body", "profile"), ("bare", "profile"), ("bare_m", "marker")):
        s = sc.get(name).spec
        assert s.settings["make"]["by"] == "sticker" and s.settings["make"]["perimeter"] == want
        assert "trim" not in s.settings, name
        p = plan_tag(s)
        assert p.ok and p.data["made_by"] == "sticker", name
        assert not [w for w in p.data["warnings"] if w["field"] == "settings.trim"], name
    # the profile's cut line follows the disc, the marker's is a rectangle
    cut = plan_tag(sc.get("bare").spec).data["guides"]["cut_line"]
    assert isinstance(cut, dict) and cut["outer"]
    assert len(plan_tag(sc.get("bare_m").spec).data["guides"]["cut_line"]) == 4


def test_a_3d_tag_on_a_bare_shape_has_nothing_to_trim():
    sc, issues = compiled({"id": "m", "aruco": "b", "layout": "single", "perimeter": "marker"})
    assert not errors(issues)
    s = sc.get("m").spec
    assert s.settings["trim"] == TRIM_BOTH and not s.target.has_body
    p = plan_tag(s)
    assert p.ok and "trim" not in p.data["parts"]


def test_a_bad_perimeter_is_an_error_on_its_path():
    _sc, issues = compiled({"id": "m", "aruco": "body.top", "layout": "single", "perimeter": "both"})
    assert errors(issues) == [("features[1].perimeter",
                               "perimeter: \"marker\" or \"profile\", not 'both'")]


def test_one_write_keeps_the_trim_exactly():
    doc = {"schema": DS.SCHEMA, "sketches": [{"id": "sk", "shapes": [{"id": "a", "rect": [50, 50]}]}],
           "features": [{"id": "body", "extrude": "a", "height": 3},
                        {"id": "m", "aruco": "body.top", "layout": "single", "perimeter": "marker"}]}
    sc, _ = DS.compile(doc, presets())
    want = copy.deepcopy(sc.get("m").spec.to_dict())
    sc.edit("m", numbers={"size": 20.0})
    DS.write_back(doc, sc, presets())
    f = doc["features"][1]
    assert "perimeter" not in f and f["settings"]["trim"] == TRIM_BOTH
    back, _ = DS.compile(doc, presets())
    assert back.get("m").spec.settings == want["settings"]
    assert back.get("m").spec.numbers == dict(want["numbers"], size=20.0)
