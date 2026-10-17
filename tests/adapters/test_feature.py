"""adapters/fusion/feature.py and sync.py on the stand-in: what REF's
create(), _on_compute and apply_edit measured, as calls.

* compute swaps every base body for the plan's (updateBody inside
  startEdit / finishEdit, ALWAYS left) and paints the swapped body again in
  the same edit (2705 drops it); it writes no record and moves no Joint
  Origin; inside customFeatures.add() (no spec yet) it skips;
* a compute whose numbers need other parts is an error that says what to do;
* a warning note becomes a compute warning, an info note does not;
* no definition registered -> the tag's features as ONE timeline group;
* a pocket that splits the face -> the base features wrapped first, the
  combines after the node, the node stretched over them;
* an edit a node cannot take in place (made before 2026-10-08) is rebuilt
  with the same key;
* after an upstream change the record is out of date: sync queues it
  (core.edits.verdict) and the idle refresh rewrites it and its Joint Origin.
"""
from __future__ import annotations

import json

import fake_adsk as FK
from aruco_studio.adapters.fusion import feature as FT
from aruco_studio.adapters.fusion import records as REC
from aruco_studio.adapters.fusion import sync as SY
from aruco_studio.core import settings as S
from aruco_studio.plan import record as R

SINGLE = {"layout": "single", "dictionary": "DICT_4X4_50", "mode": "both", "op": "join"}


def _tag(s=SINGLE, n=None, **plate):
    FT.register()
    body, face = FK.plate(**plate)
    out = FT.create(face, dict(s), dict(n or S.default_numbers(s.get("mode", "both"))),
                    key="t1")
    return out, body, face


def test_compute_swaps_bodies_and_paints_inside_the_edit():
    out, _body, _face = _tag()
    des = FK.design()
    FK.LOG.clear()
    (cf, st), = des.recompute()
    log = [x.split("(")[0] for x in FK.LOG]
    assert log.count("BaseFeature.updateBody") == len(out["recipe"]["parts"])
    assert log.count("BaseFeature.startEdit") == log.count("BaseFeature.finishEdit")
    # every painted part is painted again between its updateBody and its finishEdit
    painted = 0
    for i, h in enumerate(log):
        if h == "BaseFeature.updateBody":
            j = log.index("BaseFeature.finishEdit", i)
            painted += any(x.endswith("appearance=") for x in log[i:j])
    assert painted == len(out["recipe"]["paint"])
    assert not [x for x in FK.LOG if x.startswith(("attributes.add", "jointOrigins.add"))]
    pat = out["made"]["pattern"].bodies.item(0)
    assert pat.appearance.name == "Plastic - Matte (Black)"
    assert st.messages == []
    assert FT.STATE.compute_log[-1]["digest"] == out["plan"].data["digest"]


def test_compute_inside_add_skips():
    _tag()
    first = next(e for e in FT.STATE.compute_log if "skipped" in e)
    assert first["skipped"] == "spec not written yet"


def test_numbers_that_need_other_parts_are_an_error():
    out, _b, _f = _tag()
    cf = out["node"]
    REC.param(cf, "black_height").value = 0.06          # 0.6 mm: the black stands proud
    REC.param(cf, "black_offset").value = 0.2           # on the white top
    (_cf, st), = FK.design().recompute()
    assert st.messages and st.messages[0][0] == "error"
    assert "press OK to rebuild it" in st.messages[0][2]


def test_a_warning_note_warns_an_info_note_does_not():
    out, _b, _f = _tag()
    cf = out["node"]
    REC.param(cf, "size").value = 5.5                    # 55 mm: does not fit, clamped
    s = REC.settings_of(cf)
    (_cf, st), = FK.design().recompute()
    plan = FT.plan_for(cf.dependencies.itemById("target").entity, s, REC.numbers_of(cf), "t1")[0]
    warn = [t for t in plan.data["notes"] if not S.is_info(t)]
    info = [t for t in plan.data["notes"] if S.is_info(t)]
    assert warn and [m[2] for m in st.messages if m[0] == "warning"] == warn
    assert not any(m[2] in info for m in st.messages)


def test_no_definition_makes_a_timeline_group():
    _body, face = FK.plate()
    out = FT.create(face, dict(SINGLE), S.default_numbers("both"), key="t1")
    des = FK.design()
    assert out["node"] is None and out["sketch"] is None
    g = des.timeline.timelineGroups.item(0)
    assert g.name.startswith("ArUco t1") and out["record"]["fusion"]["group"]
    assert g.lo == 0 and g.hi == des.timeline.count - 2       # the Joint Origin follows


def test_a_split_face_wraps_the_base_features_first():
    FT.register()
    _body, face = FK.plate()
    FK.design().split_face_on_cut = face
    s = {"layout": "grid", "dictionary": "DICT_4X4_50", "mode": "black", "op": "join"}
    out = FT.create(face, s, dict(S.default_numbers("black"), black_offset=0.0,
                                  black_height=-0.6), key="t1")
    cf = out["node"]
    assert cf is not None and "live_error" not in out["record"]["fusion"]
    kinds = [type(f).__name__ for f in cf.features]
    n_base = kinds.count("BaseFeature")
    assert kinds[0] == "Sketch" and kinds[1:1 + n_base] == ["BaseFeature"] * n_base
    assert set(kinds[1 + n_base:]) == {"CombineFeature"}
    assert any(x.startswith("CustomFeature.setStartAndEndFeatures") for x in FK.LOG)


def test_a_node_made_before_parts_is_rebuilt_with_its_key():
    out, _b, _f = _tag()
    cf = out["node"]
    s = REC.settings_of(cf)
    s.pop("parts")                                       # made before 2026-10-08
    cf.customNamedValues.addOrSetValue("spec", json.dumps(s, sort_keys=True))
    res = FT.edit(cf, {"dictionary": "DICT_5X5_100"}, {})
    assert res["rebuild"] and "2026-10-08" in res["why"]
    assert res["node"] is not cf and not cf.isValid
    assert REC.settings_of(res["node"])["key"] == "t1"
    assert [j.name for j in FK.design().rootComponent.jointOrigins] == ["aruco t1"]


def test_an_upstream_change_queues_and_refreshes_the_record():
    out, body, face = _tag()
    cf = out["node"]
    comp = FK.design().rootComponent
    old = REC.find_record(comp, "t1")
    # the plate moves 1 cm along x upstream: the tag's frame moves with it
    for co in face.loops[0].coEdges:
        e = co.edge
        a, b = e.geometry.startPoint, e.geometry.endPoint
        for p in (a, b):
            p.x += 1.0
        e.evaluator.pts = [[a.x, a.y, a.z], [b.x, b.y, b.z]]
    face.pointOnFace.x += 1.0
    FK.design().recompute()
    s = REC.settings_of(cf)
    plan = FT.plan_for(face, s, REC.numbers_of(cf), "t1")[0]
    assert R.record_digest(old) != plan.data["digest"]
    note = SY.after_compute(cf, s, plan)
    assert note == "record out of date: refresh scheduled", note
    assert SY.run_pending() == ["t1"]
    new = REC.find_record(comp, "t1")
    assert R.record_digest(new) == plan.data["digest"]
    assert SY.after_compute(cf, s, plan) is None          # up to date now
    assert [j.name for j in comp.jointOrigins] == ["aruco t1"]


def test_edit_open_keeps_auto_only_when_it_builds_the_stored_tag():
    """REF _check_auto (plan.auto.auto_still_fits): a node made with Auto
    stores the number Auto picked; Edit shows Auto ON while Auto still
    builds that tag, else OFF at its number with REF's note."""
    out, _body, _face = _tag()
    cf = out["node"]
    assert FT.edit_open(cf)["auto"] is True            # today's node: Auto stores size 0
    built = out["plan"].data["marker"]["marker_length_m"] * 1000.0
    p = REC.param(cf, "size")
    p.expression = FT.mm_expr(built)                   # a node made before 2026-10-13
    first = FT.edit_open(cf)
    assert first["settings"]["size_auto"] and first["numbers"]["size"] > 0
    assert first["auto"] is True and first["note"] == ""
    p.expression = FT.mm_expr(round(built * 0.8, 3))
    later = FT.edit_open(cf)
    assert later["auto"] is False
    assert "(Auto size at creation)" in later["note"]
