"""The ArUco Extrude custom feature: create, compute, edit (thin).

Every decision is the core's or the plan's:

| Decision | Made by |
|---|---|
| the size, the fit, the label, the mark, the cells, the pins, the trim, the slabs | `plan.plan_tag` (from the Target this adapter read) |
| what a new node stores (parts, Auto size as 0, jo_v) | `plan.plan.settle` (REF settle) |
| the node's name and its warning words | `plan.record.node_name`, `node_warning` |
| which parameters a node carries | `core.settings.params_for`, `PARAMS` |
| what an edit is (compute / in place / rebuild) and why | `core.edits.merged`, `structural_change`, `core.restructure.refusal`, `core.edits.trim_not_in_place` |
| what an in-place restructure deletes and creates | `core.restructure.restructure_plan` (in restructure.py) |
| which notes are only info (no compute warning) | `core.settings.is_info` |

What is left here is Fusion: the base features and their bodies, the
combines, the node around them (`customFeatures.add`, its parameters, its
dependency, its named value), the measured fallbacks (wrap the base
features first when a pocket splits the face; a timeline group when there
is no node), the frame sketch, the record and the Joint Origin after the
node, the paint LAST.
"""
from __future__ import annotations

import json
import types

import adsk.core
import adsk.fusion

from ...core import form as F
from ...core import restructure as CR
from ...core import settings as S
from ...core import edits as E
from ...plan import auto as AU
from ...plan import plan as PL
from ...plan import record as R
from ...plan.spec import TagSpec
from .. import recipe as RC
from . import bodies as B
from . import joint_origin as JO
from . import paint as PT
from . import records as REC
from . import target as TG
from .api import clear_selections, delete_quietly, op, valid

DEF_ID = "bamAruco.ArucoExtrude"          # REF aruco_feature.DEF_ID
DEF_NAME = "ArUco Extrude"
EDIT_CMD_ID = "bamArucoExtrudeEdit"
PARAM_LABELS = S.PARAM_LABELS
STATE = types.SimpleNamespace(definition=None, handlers=[], compute_log=[],
                              restructuring=False)


# -------------------------------------------------------------- register

class _Compute(adsk.fusion.CustomFeatureEventHandler):
    def notify(self, args):
        compute(args.customFeature, args.computeStatus)


def register(resource_folder=""):
    """The definition, made inside the add-in's run() (from an event handler
    `customFeatures.add` fails "scriptInfoFound"); its edit command must
    exist already. Handlers are kept: Fusion holds them weakly."""
    d = adsk.fusion.CustomFeatureDefinition.create(DEF_ID, DEF_NAME, resource_folder)
    d.editCommandId = EDIT_CMD_ID
    h = _Compute()
    d.customFeatureCompute.add(h)
    STATE.handlers.append(h)
    STATE.definition = d
    return d


def is_registered():
    return STATE.definition is not None


def is_ours(cf):
    try:
        return cf is not None and cf.definition is not None and cf.definition.id == DEF_ID
    except Exception:                              # noqa: BLE001
        return False


# -------------------------------------------------------------- helpers

def design():
    return adsk.fusion.Design.cast(adsk.core.Application.get().activeProduct)


def mm_expr(v):
    """REF _mm_expr: a parameter's expression."""
    return f"{round(float(v), 6):g} mm"


def base_body(comp, temp, name):
    """REF _base_body: one base feature holding one body."""
    bf = comp.features.baseFeatures.add()
    bf.startEdit()
    try:
        comp.bRepBodies.add(temp, bf)
    finally:
        bf.finishEdit()
    body = bf.bodies.item(0)
    body.name = name
    bf.name = name
    return bf, body


def combine(comp, target, tool, operation, keep=False):
    tools = adsk.core.ObjectCollection.create()
    tools.add(tool)
    ci = comp.features.combineFeatures.createInput(target, tools)
    ci.operation = op(operation)
    ci.isKeepToolBodies = keep
    return comp.features.combineFeatures.add(ci)


def combines_for(comp, role, made, rec, body_under):
    """REF _combines: the combine that follows one base feature, as the
    plan's `combines` says (into the body under, or the new tile)."""
    out = []
    tool = made[role].bodies.item(0)
    for c in rec["combines"]:
        if c["part"] != role or c["op"] == "new":
            continue
        target = body_under if c["into"] == "body" else made["tile"].bodies.item(0)
        out.append(combine(comp, target, tool, c["op"]))
    return out


def make_frame_sketch(comp, rec):
    """REF make_frame_sketch: hidden, on the component's XY plane; a point at
    OpenCV's origin, a line along its x, one along its z."""
    sk = comp.sketches.add(comp.xYConstructionPlane)
    try:
        fs = rec["frame_sketch"]
        sk.name = fs["name"]
        o, px, pz = (sk.modelToSketchSpace(adsk.core.Point3D.create(*p))
                     for p in fs["points_cm"])
        lines = sk.sketchCurves.sketchLines
        lx = lines.addByTwoPoints(o, px)
        lines.addByTwoPoints(lx.startSketchPoint, pz)
        sk.isVisible = False
    except Exception:
        delete_quietly(sk)
        raise
    return sk


def frame_sketch_of(cf):
    for f in (cf.features if cf is not None else []):
        sk = adsk.fusion.Sketch.cast(f)
        if sk is not None and sk.name.startswith(RC.FRAME_SKETCH):
            return sk
    return None


def move_frame_sketch(sk, rec, tol_cm=1e-9):
    """Compute: the frame sketch's point and line ends MOVED onto the plan's
    frame (never recreated: the Joint Origin after the node uses them)."""
    lines = sk.sketchCurves.sketchLines
    lx, lz = lines.item(0), lines.item(1)
    want = [sk.modelToSketchSpace(adsk.core.Point3D.create(*p))
            for p in rec["frame_sketch"]["points_cm"]]
    moved = 0
    for sp, q in ((lx.startSketchPoint, want[0]), (lx.endSketchPoint, want[1]),
                  (lz.endSketchPoint, want[2])):
        g = sp.geometry
        d = adsk.core.Vector3D.create(q.x - g.x, q.y - g.y, q.z - g.z)
        if d.length > tol_cm:
            sp.move(d)
            moved += 1
    return moved


def node_parts(cf, s):
    """{role: base feature} by the spec's "parts", in order (REF parts_of)."""
    bfs = [b for b in (adsk.fusion.BaseFeature.cast(f) for f in cf.features) if b is not None]
    return dict(zip(list(s.get("parts") or []), bfs))


def spec_for(entity, s, n, key, name="", body_under=None):
    """Read the target. -> (TagSpec, Target, base, creation keys)."""
    t, base, keys = TG.read(entity, s, body_under)
    spec = TagSpec(settings=dict(s, **keys), numbers=dict(n), target=t, name=name, key=key)
    return spec, t, base, keys


def plan_for(entity, s, n, key, name="", body_under=None):
    """Read the target, plan the tag. -> (TagPlan, Target, base, creation keys)."""
    spec, t, base, keys = spec_for(entity, s, n, key, name, body_under)
    return PL.plan_tag(spec, base=base), t, base, keys


def edit_open(cf):
    """What the Edit dialog opens with (REF _check_auto at its first
    refresh): the node's settings and numbers, and whether Auto size shows
    ON. A node made with Auto stores the number Auto picked then; Auto stays
    ON only if it builds that same tag here now (plan.auto.auto_still_fits),
    else OFF at its number with `note`. -> {"settings", "numbers", "auto",
    "note"}."""
    s = REC.settings_of(cf)
    n = REC.numbers_of(cf)
    out = {"settings": s, "numbers": n, "auto": bool(s.get("size_auto", True)), "note": ""}
    if not out["auto"] or not float(n.get("size") or 0.0) > 0.0:
        return out
    entity = cf.dependencies.itemById("target").entity
    spec, _t, base, _k = spec_for(entity, s, n, s.get("key") or "tag", "", _body_under(entity))
    keep, note = AU.auto_still_fits(spec, float(n["size"]), float(n.get("square") or 0.0),
                                    base=base)
    out.update(auto=keep, note=note)
    return out


def _body_under(entity):
    native = TG.native_of(entity)
    body = getattr(native, "body", None)
    return TG.native_of(body) if body is not None else None


# -------------------------------------------------------------- create

def create(entity, s, n, *, key=None, name="", live=True, layout="create"):
    """Build an ArUco Extrude on a planar face or a sketch profile (inside a
    command's execute: one undo step). -> {"node", "record", "plan",
    "recipe", "made"}."""
    des = design()
    s = dict(S.default_settings(), **S.normalise(dict(s)))
    is_face = adsk.fusion.Profile.cast(entity) is None
    body_under = _body_under(entity) if is_face else None
    s["source"] = "face" if is_face else "profile"
    s["has_body"] = body_under is not None
    s = F.new_tag_settings(s, s["has_body"])         # origin_v + Extrude Auto: the core's rule
    key = key or s.get("key") or "tag"
    s["key"] = key
    n = S.resolve_follow(s, n)
    s.pop("black_follows", None)
    plan, t, base, keys = plan_for(entity, s, n, key, name, body_under)
    if not plan.ok:
        raise ValueError("; ".join(plan.data["errors"]) or "the plan refused")
    s.update(keys)
    if is_face and not s.get("x_ref"):
        s["x_ref"] = [round(c, 12) for c in plan.ev["x_fit"]]
    s, n = PL.settle(s, n, plan)
    rec = RC.recipe(plan, base[:4], layout=layout, frame_sketch=S.has_frame_sketch(s))
    comp = body_under.parentComponent if body_under is not None else des.rootComponent
    tl = des.timeline
    start = tl.markerPosition
    feats, sk = [], None
    if S.has_frame_sketch(s):
        sk = make_frame_sketch(comp, rec)
        feats.append(sk)
    made = {}
    paints = {e["role"]: e for e in rec["paint"]}
    for p in rec["parts"]:
        bf, body = base_body(comp, B.part_body(rec, p), p["name"])
        made[p["role"]] = bf
        feats.append(bf)
        if p["role"] in ("tile", "pin"):
            # face-level: carried through the join, into every piece a pocket cuts
            PT.paint_body(des, body, dict(paints[p["role"]], body=False))
        if layout == "create":
            feats += combines_for(comp, p["role"], made, rec, body_under)
    if layout == "wrap_first":
        for p in rec["parts"]:
            feats += combines_for(comp, p["role"], made, rec, body_under)
    cf, live_error, group = None, None, None
    if live and is_registered():
        try:
            cf = wrap(comp, entity, feats, s, n, plan)
        except Exception as exc:                   # noqa: BLE001
            live_error = f"{type(exc).__name__}: {exc}"[:300]
        if (cf is None and "face" in (live_error or "") and s["mode"] in ("black", "white")
                and any(adsk.fusion.CombineFeature.cast(f) is not None for f in feats)):
            # the pocket SPLIT the face: wrap while the face is whole (2705)
            try:
                cf, feats = wrap_first(comp, entity, feats, made, rec, body_under, s, n, plan)
                live_error = None
            except Exception as exc:               # noqa: BLE001
                live_error += f" | wrapped first: {type(exc).__name__}: {exc}"[:300]
                cf = None
    if cf is not None and plan.data["node_warning"]:
        cf.name = R.node_name(key, plan.ev["spec"], s["mode"], plan.data["node_warning"])
    try:
        last = cf.timelineObject if cf is not None else feats[-1].timelineObject
        if tl.markerPosition <= last.index:
            last.rollTo(False)
    except Exception:                              # noqa: BLE001
        pass
    if cf is None and sk is not None:
        feats = [f for f in feats if f is not sk]
        delete_quietly(sk)
        sk = None
    if cf is None:
        group = make_group(des, feats, start, R.node_name(key, plan.ev["spec"], s["mode"]))
    # colours LAST: customFeatures.add() resets its base bodies' appearance
    PT.paint_node(des, rec, {r: bf.bodies.item(0) for r, bf in made.items()
                             if bf.bodies.count})
    fz = {"custom_feature": cf.entityToken if cf is not None else None,
          "base_feature": made["pattern"].entityToken,
          "tile_body": (made["tile"].bodies.item(0).name if "tile" in made and
                        not rec["joined"] else (body_under.name if body_under else None)),
          "cells_body": made["pattern"].bodies.item(0).name, "mode": s["mode"],
          "group": group, "rotate_deg": s.get("rotate_deg", 0)}
    if live_error:
        fz["live_error"] = live_error
    record = REC.record_of_plan(plan, REC.component_label(des, comp), fz)
    jo = place_joint_origin(comp, key, sk, entity, rec, record)
    record["fusion"].update(jo_fields(jo))
    REC.write_record(comp, record)
    return {"node": cf, "record": record, "plan": plan, "recipe": rec, "made": made,
            "settings": s, "numbers": n, "sketch": sk}


def wrap(comp, entity, feats, s, n, plan):
    """REF _wrap: the live node around `feats`. Raises (the features left as
    they were) when it cannot be made."""
    VI = adsk.core.ValueInput
    inp = comp.features.customFeatures.createInput(STATE.definition)
    inp.addCustomParameter("marker_id", PARAM_LABELS["marker_id"],
                           VI.createByReal(float(n.get("marker_id", 0))), "", True)
    used = S.params_for(s)
    # every parameter, the unused hidden: a node can never gain one later
    for pid in (S.PARAMS[1:] if S.RESTRUCTURE_IN_PLACE else used):
        inp.addCustomParameter(pid, PARAM_LABELS[pid], VI.createByString(mm_expr(n[pid])),
                               "mm", pid in used)
    inp.addDependency("target", entity)
    inp.setStartAndEndFeatures(feats[0], feats[-1])
    cf = comp.features.customFeatures.add(inp)
    try:
        cf.customNamedValues.addOrSetValue(REC.SPEC_VALUE, json.dumps(s, sort_keys=True))
    except Exception:
        release(cf)                                 # compute would skip it forever
        raise
    try:
        cf.name = R.node_name(s["key"], plan.ev["spec"], s["mode"])
    except Exception:                              # noqa: BLE001
        pass
    return cf


def wrap_first(comp, entity, feats, made, rec, body_under, s, n, plan):
    """REF _wrap_first: the combines undone, the base features wrapped while
    the face is whole, the combines made again after the node, the node
    stretched over them with the marker rolled to it."""
    clear_selections()
    for f in reversed(feats):
        if adsk.fusion.CombineFeature.cast(f) is not None:
            f.deleteMe()
    bfs = ([f for f in feats if adsk.fusion.Sketch.cast(f) is not None]
           + [made[p["role"]] for p in rec["parts"]])
    cf = wrap(comp, entity, bfs, s, n, plan)
    combos = []
    for p in rec["parts"]:
        combos += combines_for(comp, p["role"], made, rec, body_under)
    if combos:
        cf.timelineObject.rollTo(True)
        try:
            cf.setStartAndEndFeatures(bfs[0], combos[-1])
        finally:
            cf.timelineObject.rollTo(False)
    return cf, bfs + combos


def make_group(des, feats, start, label):
    """REF _group: no live node -> the tag's features as ONE timeline group."""
    tl = des.timeline
    try:
        idx = [f.timelineObject.index for f in feats if valid(f)]
        lo, hi = min(idx), max(idx)
    except Exception:                              # noqa: BLE001
        lo, hi = start, tl.markerPosition - 1
    if hi <= lo:
        return None
    g = tl.timelineGroups.add(lo, hi)
    g.name = label
    return getattr(g, "entityToken", None) or f"group {lo}..{hi}"


def release(cf):
    """REF _release: a node whose set-up failed after add() goes; its
    features go back to the timeline as they were."""
    clear_selections()
    try:
        cf.setStartAndEndFeatures(None, None)
    except Exception:                              # noqa: BLE001
        pass
    delete_quietly(cf)


def jo_fields(jo):
    """What ensure() said, as the record's REF keys."""
    out = {}
    if jo.get("token"):
        out["joint_origin"] = jo["token"]
    if jo.get("name"):
        out["joint_origin_name"] = jo["name"]
    if jo.get("problem"):
        out["joint_origin_problem"] = jo["problem"]
    return out


def place_joint_origin(comp, key, sk, entity, rec, record):
    """The tag's ONE Joint Origin where the plan's OpenCV frame is: on the
    frame sketch (jo_v 2, after the node), else on the face the tag stands
    on (jo_v 1)."""
    target = tuple(tuple(v) for v in rec["frames"]["opencv_cm"])
    geo = None
    if adsk.fusion.Profile.cast(entity) is None:
        geo = adsk.fusion.JointGeometry.createByPlanarFace(TG.native_of(entity), None, 0)
    try:
        return JO.ensure(comp, key, geo, target, sketch=sk,
                         token=(record.get("fusion") or {}).get("joint_origin"))
    except Exception as exc:                       # noqa: BLE001
        return {"problem": f"not created: {exc}"[:200]}


# -------------------------------------------------------------- compute

def compute(cf, status):
    """REF _on_compute: swap the bodies, move the frame sketch. Compute may
    change only base-feature bodies, sketch contents and parameters: no
    record, no Joint Origin (sync.py refreshes those after)."""
    entry = {"feature": cf.name}
    try:
        if STATE.restructuring:
            entry["skipped"] = "restructuring"
            return entry
        s = REC.settings_of(cf)
        if s is None:
            entry["skipped"] = "spec not written yet"          # inside add()
            return entry
        n = REC.numbers_of(cf)
        dep = cf.dependencies.itemById("target")
        entity = dep.entity if dep is not None else None
        if entity is None:
            raise ValueError("the face or profile it was made on is gone")
        if not S.is_legacy(s):
            built, want = S.node_structure(s), S.structure(s, n)
            if built != want:
                raise ValueError(
                    "these numbers change what the tag is made of (" + ", ".join(want[2])
                    + " instead of " + ", ".join(built[2]) + "): double-click the ArUco "
                    "Extrude node and press OK to rebuild it")
        body_under = _body_under(entity)
        plan, _t, base, _k = plan_for(entity, s, n, s.get("key") or "tag", "", body_under)
        if not plan.ok:
            raise ValueError("; ".join(plan.data["errors"]))
        rec = RC.recipe(plan, base[:4], frame_sketch=S.has_frame_sketch(s))
        des = design()
        paints = {e["role"]: e for e in rec["paint"]}
        by_role = {p["role"]: p for p in rec["parts"]}
        for role, bf in node_parts(cf, s).items():
            if role in by_role:
                update(des, bf, B.part_body(rec, by_role[role]), paints.get(role))
        if S.has_frame_sketch(s):
            sk = frame_sketch_of(cf)
            if sk is None:
                status.statusMessages.addWarning(
                    "API_COMPUTE_WARNING", "its Joint Origin's frame sketch is missing: "
                    "double-click the ArUco Extrude node and press OK to rebuild it")
            else:
                entry["frame_moved"] = move_frame_sketch(sk, rec)
        for note in plan.data["notes"]:
            if not S.is_info(note):
                status.statusMessages.addWarning("API_COMPUTE_WARNING", note)
        entry["digest"] = plan.data["digest"]
        entry["recipe"] = rec
    except Exception as exc:                       # noqa: BLE001
        entry["error"] = f"{type(exc).__name__}: {exc}"[:300]
        status.statusMessages.addError("API_COMPUTE_ERROR", str(exc)[:200])
    finally:
        STATE.compute_log = (STATE.compute_log + [entry])[-200:]
    return entry


def update(des, bf, temp, paint_entry=None):
    """REF _update: swap a base feature's one body and ALWAYS leave edit
    mode; updateBody drops the appearance, so it is put back inside the
    same edit."""
    if temp is None:
        return False
    bf.startEdit()
    try:
        src = list(bf.sourceBodies)[0]
        ok = bool(bf.updateBody(src, temp))
        if paint_entry is not None:
            PT.repaint_source(des, bf, paint_entry)
        return ok
    finally:
        bf.finishEdit()


# -------------------------------------------------------------- edit

def apply_edit(cf, s_new, n_new):
    """REF apply_edit, the timeline rolled to the node. -> {"rebuild",
    "settings", "numbers", "restructured", "wrote"}."""
    from . import restructure as RS
    sk_ok = frame_sketch_of(cf) is not None
    node = REC.node_state(cf, frame_sketch=sk_ok)
    s_old, n_old, s, n = E.merged(node, s_new, n_new)
    restructured = None
    if E.structural_change(node, s_old, s, n):
        why = CR.refusal(node, s_old, s, n) or E.trim_not_in_place(s_old, s, n)
        if why is not None:
            s.pop("parts", None)
            return {"rebuild": True, "settings": s, "numbers": n, "why": why}
        dep = cf.dependencies.itemById("target")
        entity = dep.entity
        plan, _t, base, _k = plan_for(entity, s, n, s.get("key") or "tag", "",
                                      _body_under(entity))
        rec = RC.recipe(plan, base[:4], frame_sketch=S.has_frame_sketch(s))
        STATE.restructuring = True
        try:
            restructured = RS.restructure(cf, s_old, s, n, rec, _body_under(entity))
        finally:
            STATE.restructuring = False
        s["parts"] = list(restructured["parts"])
    s["v"] = S.SPEC_VERSION
    wrote = False
    if E.edit_changes(node, s, n, s_old, n_old) or restructured:
        cf.customNamedValues.addOrSetValue(REC.SPEC_VALUE, json.dumps(s, sort_keys=True))
    used = set(S.params_for(s)) | {"marker_id"}
    for pid in S.PARAMS:
        p = REC.param(cf, pid)
        if p is None:
            continue
        if bool(p.isVisible) != (pid in used):
            p.isVisible = pid in used
        if pid not in used or abs(float(n[pid]) - float(n_old[pid])) < 1e-9:
            continue
        if pid == "marker_id":
            p.value = float(int(round(n[pid])))
        else:
            p.expression = mm_expr(n[pid])
        wrote = True
    return {"rebuild": False, "settings": s, "numbers": n, "restructured": restructured,
            "wrote": wrote, "changed": E.edit_changes(node, s, n, s_old, n_old)}


def edit(cf, s_new, n_new):
    """The whole edit (the edit command's execute): roll to the node, write
    or restructure or rebuild, roll forward, then the record and the Joint
    Origin from a fresh plan (pure: no compute needed). Fusion recomputes
    the node on its own. A raise takes the command back whole (Fusion's
    executeFailed). -> what apply_edit said, and the record."""
    des = design()
    clear_selections()
    cf.timelineObject.rollTo(True)
    try:
        out = apply_edit(cf, s_new, n_new)
    finally:
        des.timeline.moveToEnd()
    if out["rebuild"]:
        dep = cf.dependencies.itemById("target")
        entity, key = dep.entity, out["settings"].get("key")
        clear_selections()                          # never delete a selected node
        delete_quietly(cf)
        made = create(entity, out["settings"], out["numbers"], key=key)
        out.update(node=made["node"], record=made["record"])
        return out
    out["node"] = cf
    if not (out["changed"] or out["restructured"]):
        out["record"] = None                       # OK on no change: nothing written
        return out
    out["record"] = refresh_record(cf)
    return out


def refresh_record(cf, rec=None):
    """After a compute (never inside it): the record and the Joint Origin."""
    s = REC.settings_of(cf)
    n = REC.numbers_of(cf)
    dep = cf.dependencies.itemById("target")
    entity = dep.entity
    body_under = _body_under(entity)
    plan, _t, base, _k = plan_for(entity, s, n, s["key"], "", body_under)
    rec = rec or RC.recipe(plan, base[:4], frame_sketch=S.has_frame_sketch(s))
    comp = cf.parentComponent
    old = REC.find_record(comp, s["key"]) or {}
    fz = dict(old.get("fusion") or {})
    fz.update(custom_feature=cf.entityToken, mode=s["mode"])
    R.record_extras(fz, plan.ev)
    record = REC.record_of_plan(plan, old.get("component", ""), fz)
    if not old or not R.record_same(old, plan.ev):
        jo = place_joint_origin(comp, s["key"], frame_sketch_of(cf), entity, rec,
                                {"fusion": {"joint_origin": fz.get("joint_origin")}})
        record["fusion"].update(jo_fields(jo))
    REC.write_record(comp, record)
    return record
