"""adapters/fusion/ids.py: per-copy IDs as occurrences, on the stand-in.

* three copies of an Arm that holds one tag (one copy's light bulb off)
  read as an AssemblySnapshot: every copy, its "+"-joined path, its world
  transform, its visibility, the tag record;
* core numbering on it gives the visible copies distinct ids (the hidden
  one listed, not numbered);
* a renumbered copy's part is a new component occurrence at the copy's world
  transform whose pattern body prints the copy's id (its plan is
  plan.variants.copy_plan's), painted black;
* the ledger is written once and not again when it says the same.
"""
from __future__ import annotations

import fake_adsk as FK
from aruco_studio.adapters import recipe as RC
from aruco_studio.adapters.fusion import feature as FT
from aruco_studio.adapters.fusion import ids as IDS
from aruco_studio.core import settings as S


def _arm():
    FT.register()
    des = FK.design()
    arm = des._new_component("Arm")
    _body, face = FK.plate(comp=arm)
    out = FT.create(face, {"layout": "single", "dictionary": "DICT_4X4_50", "mode": "both",
                           "op": "join"}, S.default_numbers("both"), key="t1")
    occs = []
    for i in range(3):
        m = FK.Matrix3D()
        m.setWithCoordinateSystem([10.0 * i, 0.0, 0.0], [1, 0, 0], [0, 1, 0], [0, 0, 1])
        occs.append(des.rootComponent.occurrences.addExistingComponent(arm, m))
    occs[2].isLightBulbOn = False
    return des, arm, out, occs


def test_the_snapshot_holds_every_copy():
    des, _comp, out, occs = _arm()
    snap = IDS.snapshot(des)
    assert [o["path"] for o in snap.occurrences] == ["Arm:1", "Arm:2", "Arm:3"]
    assert [o["visible"] for o in snap.occurrences] == [True, True, False]
    assert snap.occurrences[1]["world"][3] == 10.0
    assert [t["key"] for t in snap.tags] == ["t1"] and snap.tags[0]["component"] == "Arm"


def test_numbering_gives_the_visible_copies_their_own_ids():
    des, _comp, _out, _occs = _arm()
    plan = IDS.plan_ids(des)
    assert plan.ok, plan.errors
    vis = [r for r in plan.rows if not r.hidden]
    assert len(plan.rows) == 3 and len(vis) == 2
    assert len({r.final for r in vis}) == 2


def test_a_copys_part_prints_its_own_id():
    des, _comp, out, _occs = _arm()
    world = [1.0, 0, 0, 10.0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0]
    occ, copy, rec = IDS.make_part(des, out["plan"], 7, world, "Arm:2")
    assert copy.data["ids"] == [7] and out["plan"].data["ids"] == [0]
    comp = occ.component
    names = [b.name for b in comp.bRepBodies]
    assert "aruco id Arm:2 . aruco cells t1" in names
    pat = comp.bRepBodies.itemByName("aruco id Arm:2 . aruco cells t1")
    assert pat.appearance.name == "Plastic - Matte (Black)"
    # the copy's cells, not the template's: some cell differs
    t_rec = RC.recipe(out["plan"])
    cells_t = {tuple(map(lambda v: round(v, 6), q["outer"]["c"]))
               for _p, _s, st in RC.steps(t_rec) if st["layer"] == "pattern"
               for q in st["polygons"]}
    cells_c = {tuple(map(lambda v: round(v, 6), q["outer"]["c"]))
               for _p, _s, st in RC.steps(rec) if st["layer"] == "pattern"
               for q in st["polygons"]}
    assert cells_t != cells_c


def test_the_ledger_is_written_once():
    des, _comp, _out, _occs = _arm()
    led = {"schema": "bam_aruco_ids_ledger/1", "entries": []}
    assert IDS.write_ledger(des, led) is True
    assert IDS.write_ledger(des, dict(led)) is False
