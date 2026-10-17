"""adapters/fusion/restructure.py on the stand-in's timeline (PLAN M4.6;
REF tests/test_aruco_restructure_sim.py's cases, run through the adapter's
own create() and edit()).

For every pair of node structures core.slabs.plan makes (the mode, Join /
New, pins, a pocket or recess, Trim excess), in both layouts create() makes
(each combine after its base feature; every base feature first) and with
and without the frame sketch:

* the node is the SAME object, over one contiguous range, a user feature
  after it left out;
* its base features are in role order, named for their role; the frame
  sketch first;
* each role has a combine exactly when core.restructure.has_combine says,
  after its own base feature and every earlier role's combine, with its
  tool and target right;
* every role that stays keeps its base feature (the same object);
* the deletes and creates are what core.restructure.restructure_plan says;
* a failure injected at each step leaves the node grouped, and once the
  edit command is taken back (Fusion's executeFailed) the document is
  exactly as before.
"""
from __future__ import annotations

import itertools

import pytest

import fake_adsk as FK
from aruco_studio.adapters.fusion import feature as FT
from aruco_studio.adapters.fusion import restructure as RS
from aruco_studio.core import restructure as CR
from aruco_studio.core import settings as S

TRIM = {"rule": 1, "axes": "both", "margin_mm": 1.0, "force": True}
HEIGHTS = ((0, 2, 2, -0.6), (0, 2, 2, 0.6), (-1, 2, 1, -0.6), (0, 2, 2.5, 0.5),
           (0, 0.6, 0, -0.6), (0, 2, 0, 0.6))


def _settings(mode, op, pin, trim):
    s = {"layout": "single", "dictionary": "DICT_4X4_50", "mode": mode, "op": op, "pin": pin}
    s["trim"] = dict(TRIM) if trim else None
    return s


def _numbers(h):
    wo, wh, bo, bh = h
    return dict(S.default_numbers("both"), white_offset=wo, white_height=wh, black_offset=bo,
                black_height=bh, pin_length=1.5, pin_tol=0.15, pin_size=3.0)


def _structures():
    out = {}
    for mode, op, pin, h, trim in itertools.product(("both", "black", "white"), ("join", "new"),
                                                    ("none", "triangle"), HEIGHTS, (False, True)):
        s = dict(_settings(mode, op, pin, trim), has_body=True)
        if not trim:
            s.pop("trim")
        p = S.plan_of(s, _numbers(h))
        out.setdefault((mode, p.op, tuple(p.parts)), (mode, op, pin, h, trim))
    return [v for _k, v in sorted(out.items(), key=str)]


STRUCTURES = _structures()


def _build(a, layout, sketch):
    mode, op, pin, h, trim = a
    FK.reset()
    FT.register()
    _body, face = FK.plate()
    s = _settings(mode, op, pin, trim)
    if not trim:
        s.pop("trim")
    s["jo_v"] = 2 if sketch else 1
    out = FT.create(face, s, _numbers(h), key="k", layout=layout)
    des = FK.design()
    # a user feature after the node: never pulled into it
    des.timeline.moveToEnd()
    after = FK.BaseFeature(des.rootComponent, "Fillet after")
    des.timeline.insert(after)
    return out, after


def _verify(cf, out_new, kept, after, sketch):
    errs = []
    feats = cf.features
    if not feats:
        return ["the node is empty"]
    if after in feats:
        errs.append("the user's feature is inside the node")
    if sketch and FK.Sketch.cast(feats[0]) is None:
        errs.append("the frame sketch is not first")
    s = FT.REC.settings_of(cf)
    entity = cf.dependencies.itemById("target").entity
    rec = FT.RC.recipe(FT.plan_for(entity, s, FT.REC.numbers_of(cf), "k", "",
                                   FT._body_under(entity))[0])
    roles = [p["role"] for p in rec["parts"]]
    bfs = [f for f in feats if FK.BaseFeature.cast(f) is not None]
    cbs = [f for f in feats if FK.CombineFeature.cast(f) is not None]
    if [b.name for b in bfs] != [p["name"] for p in rec["parts"]]:
        errs.append(f"base features {[b.name for b in bfs]} != {roles}")
        return errs
    if list(s["parts"]) != roles:
        errs.append(f"spec parts {s['parts']} != {roles}")
    by_role = dict(zip(roles, bfs))
    op = S.effective_op(s)
    want = [r for r in roles if CR.has_combine(r, op)]
    if len(cbs) != len(want):
        return errs + [f"{len(cbs)} combines, want {want}"]
    pos = {id(f): i for i, f in enumerate(feats)}
    last = -1
    plate = FK.design().rootComponent.bRepBodies.itemByName("Plate")
    for r, c in zip(want, cbs):
        if c.toolBodies[0] is not by_role[r].bodies.item(0):
            errs.append(f"combine for {r}: the wrong tool")
        tgt = plate if r in ("tile", "recess", "trim") or (r == "pocket" and op == "join") \
            else by_role["tile"].bodies.item(0)
        if c.targetBody is not tgt:
            errs.append(f"combine for {r}: wrong target {c.targetBody.name}")
        kind = {"tile": "join", "pin": "join", "pocket": "cut", "recess": "cut",
                "trim": "intersect"}[r]
        if FK.FeatureOperations.NAMES[c.operation] != kind:
            errs.append(f"combine for {r}: {c.operation}")
        if pos[id(c)] < pos[id(by_role[r])] or pos[id(c)] < last:
            errs.append(f"combine for {r} out of order")
        last = pos[id(c)]
    for r, b in kept.items():
        if r in by_role and by_role[r] is not b:
            errs.append(f"the {r} base feature was made again (it stays)")
    rp = out_new.get("restructured") or {}
    if rp:
        plan = rp["plan"]
        if sorted(x.split(" ", 1)[1] for x in rp["created"] if x.startswith("base ")) != \
                sorted(plan["create_roles"]):
            errs.append(f"created {rp['created']} != plan {plan['create_roles']}")
        if sorted(x.split(" ", 1)[1] for x in rp["deleted"] if x.startswith("base ")) != \
                sorted(plan["delete_roles"]):
            errs.append(f"deleted {rp['deleted']} != plan {plan['delete_roles']}")
    return errs


def test_there_are_many_structures():
    assert len(STRUCTURES) >= 20, len(STRUCTURES)
    assert any(a[4] for a in STRUCTURES)


@pytest.mark.parametrize("layout,sketch", [("create", False), ("create", True),
                                           ("wrap_first", False), ("wrap_first", True)])
def test_every_pair_restructures_in_place(layout, sketch):
    bad, runs = [], 0
    for a, b in itertools.product(STRUCTURES, STRUCTURES):
        if layout == "wrap_first" and a[0] == "both" and a[1] == "join":
            continue                           # create() never stretches a joined tile
        out, after = _build(a, layout, sketch)
        cf = out["node"]
        kept0 = dict(out["made"])
        mode, op, pin, h, trim = b
        try:
            res = FT.edit(cf, _settings(mode, op, pin, trim), _numbers(h))
        except Exception as exc:               # noqa: BLE001
            bad.append((a, b, f"raised {type(exc).__name__}: {exc}"))
            continue
        runs += 1
        if res["rebuild"]:
            bad.append((a, b, f"rebuilt: {res.get('why')}"))
            continue
        if res["node"] is not cf:
            bad.append((a, b, "not the same node"))
            continue
        parts_new = FT.REC.settings_of(cf)["parts"]
        kept = {r: kept0[r] for r in kept0 if r in parts_new}
        errs = _verify(cf, res, kept, after, sketch)
        if errs:
            bad.append((a, b, errs[:3]))
    assert runs > 300 and not bad, bad[:4]


@pytest.mark.parametrize("step", RS.STEPS)
def test_a_failure_at_each_step_is_taken_back_whole(step):
    a = next(x for x in STRUCTURES if x[0] == "black" and not x[4])
    b = next(x for x in STRUCTURES if x[0] == "both" and x[1] == "join" and x[2] == "none"
             and not x[4])
    out, _after = _build(a, "create", True)
    cf = out["node"]
    des = FK.design()
    before = des.signature()
    grouped = []
    RS.FAIL_AT = step
    try:
        with pytest.raises(RuntimeError, match="injected"):
            with FK.command(des):
                try:
                    FT.edit(cf, _settings(*b[:3], b[4]), _numbers(b[3]))
                finally:
                    # the node is grouped again BEFORE the command is taken back
                    grouped.append(cf.start is not None and len(cf.features) > 0)
    finally:
        RS.FAIL_AT = None
    assert grouped == [True]
    assert des.signature() == before
    assert not FT.STATE.restructuring
