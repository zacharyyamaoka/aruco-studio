"""Change what a node is MADE OF in place (REF aruco_restructure.restructure).

A structural edit (the mode, Join <-> New body, a pocket / pins / recess /
trim appearing or going) used to delete the node and create it again, and
Fusion then cascade-deleted every feature downstream that referenced it (a
joint on the tag's face, a fillet, a sketch, the IDs node). Compute cannot
do it (it may only change base-feature bodies, sketch contents and
parameters), so the edit command does it, with the timeline rolled before
the node:

| Step | What | Decided by |
|---|---|---|
| 1 release | the node lets go of its features (`setStartAndEndFeatures(None, None)`) | - |
| 2 delete | only the roles that go (their combine, then their base feature) and the combines whose target / operation changes | `core.restructure.restructure_plan` |
| 3 create | the roles that appear and the changed combines, each at its place in the node's order (the marker rolled behind the previous one) | `restructure_plan`; the bodies from the recipe |
| 4 regroup | the SAME node over its features again (the marker rolled to it: "Didn't roll editing feature back" otherwise) | - |

ATOMIC: on any exception after the release, what is left is regrouped
before the error goes on, and the edit command's executeFailed takes the
whole step back. `FAIL_AT` makes a step raise (tests only, as REF).
"""
from __future__ import annotations

import adsk.fusion

from ...core import restructure as CR
from ...core import settings as S
from . import bodies as B
from . import feature as FT
from . import paint as PT
from .api import clear_selections, valid

STEPS = ("release", "delete", "create", "regroup", "spec")
FAIL_AT = None


def _inject(step):
    if FAIL_AT == step:
        raise RuntimeError(f"injected failure at '{step}' (test)")


def _idx(f):
    try:
        return f.timelineObject.index
    except Exception:                              # noqa: BLE001
        return None


def node_roles(cf, s):
    """{role: {"bf", "cb"}} of a node by its spec's "parts" in order (both
    layouts create() makes). Raises when the node does not match them."""
    parts = list((s or {}).get("parts") or [])
    if not parts:
        raise ValueError("made before 2026-10-08 (no parts)")
    feats = list(cf.features)
    bfs = [b for b in (adsk.fusion.BaseFeature.cast(f) for f in feats) if b is not None]
    cbs = [c for c in (adsk.fusion.CombineFeature.cast(f) for f in feats) if c is not None]
    op = S.effective_op(s)
    with_cb = [r for r in parts if CR.has_combine(r, op)]
    if len(bfs) != len(parts):
        raise ValueError(f"{len(bfs)} base features for parts {parts}")
    if len(cbs) != len(with_cb):
        raise ValueError(f"{len(cbs)} combines for {with_cb}")
    roles = {r: {"bf": b, "cb": None} for r, b in zip(parts, bfs)}
    for r, c in zip(with_cb, cbs):
        roles[r]["cb"] = c
    return roles


def regroup(cf, feats):
    live = [f for f in feats if valid(f) and _idx(f) is not None]
    if not live:
        raise ValueError("nothing to regroup")
    live.sort(key=_idx)
    try:
        cf.timelineObject.rollTo(True)
    except Exception:                              # noqa: BLE001
        live[0].timelineObject.rollTo(True)
    if cf.setStartAndEndFeatures(live[0], live[-1]) is False:
        raise RuntimeError("setStartAndEndFeatures refused the regroup")
    return live[0], live[-1]


def restructure(cf, s_old, s, n, rec, body_under):
    """The node made of the recipe's parts in place. The timeline is rolled
    before the node (the edit's). -> {"parts", "deleted", "created", "kept",
    "plan"}. Raises -- after regrouping what is left -- when a step fails."""
    comp = cf.parentComponent
    des = FT.design()
    parts_new = [p["role"] for p in rec["parts"]]
    op_new = S.plan_of(s, n).op
    parts_old = list(s_old["parts"])
    op_old = S.effective_op(s_old)
    roles = node_roles(cf, s_old)
    sk = FT.frame_sketch_of(cf)
    orig = list(cf.features)
    by_role = {p["role"]: p for p in rec["parts"]}
    paints = {e["role"]: e for e in rec["paint"]}
    out = {"parts": parts_new, "deleted": [], "created": [], "kept": []}
    released = False
    try:
        _inject("release")
        clear_selections()
        cf.setStartAndEndFeatures(None, None)
        released = True
        _inject("delete")
        rp = CR.restructure_plan(parts_old, op_old, parts_new, op_new)
        out["plan"] = rp
        doomed = []
        for r in rp["delete_roles"]:
            doomed += [("combine " + r, roles[r]["cb"]), ("base " + r, roles[r]["bf"])]
            roles.pop(r)
        for r in rp["delete_combines"]:
            doomed.append(("combine " + r, roles[r]["cb"]))
            roles[r]["cb"] = None
        clear_selections()
        for label, f in doomed:
            if f is not None and valid(f):
                f.timelineObject.rollTo(False)     # never delete a rolled-back item
                f.deleteMe()
                out["deleted"].append(label)
        out["kept"] = [r for r in parts_new if r in roles]
        _inject("create")

        def placed():
            fs = [sk] if sk is not None else []
            for r in parts_new:
                if r in roles:
                    fs += [roles[r]["bf"]] + ([roles[r]["cb"]] if roles[r]["cb"] else [])
            return [f for f in fs if valid(f)]

        def roll_for_base(i):
            later = [roles[q]["bf"] for q in parts_new[i + 1:] if q in roles]
            later = [f for f in later if valid(f)]
            if later:
                min(later, key=_idx).timelineObject.rollTo(True)
            else:
                max(placed(), key=_idx).timelineObject.rollTo(False)

        def roll_for_combine(i, r):
            fs = [roles[r]["bf"]] + [roles[q]["cb"] for q in parts_new[:i]
                                     if q in roles and roles[q]["cb"] is not None]
            max([f for f in fs if valid(f)], key=_idx).timelineObject.rollTo(False)

        if S.has_frame_sketch(s) and sk is None:
            min(placed(), key=_idx).timelineObject.rollTo(True)
            sk = FT.make_frame_sketch(comp, rec)
            out["created"].append("frame sketch")
        for i, r in enumerate(parts_new):
            if r not in roles:
                roll_for_base(i)
                bf, body = FT.base_body(comp, B.part_body(rec, by_role[r]), by_role[r]["name"])
                if r in ("pin", "tile"):
                    PT.paint_body(des, body, dict(paints[r], body=False))
                roles[r] = {"bf": bf, "cb": None}
                out["created"].append("base " + r)
            if CR.has_combine(r, op_new) and roles[r]["cb"] is None:
                roll_for_combine(i, r)
                made = {q: v["bf"] for q, v in roles.items()}
                cbs = FT.combines_for(comp, r, made, rec, body_under)
                roles[r]["cb"] = cbs[0] if cbs else None
                out["created"].append("combine " + r)
        try:
            pb = roles["pattern"]["bf"].bodies.item(0)
            want = by_role["pattern"]["name"]
            if pb.name != want:
                pb.name = want
                roles["pattern"]["bf"].name = want
        except Exception:                          # noqa: BLE001
            pass
        _inject("regroup")
        regroup(cf, placed())
        released = False
        _inject("spec")
        return out
    except Exception:
        if released:
            try:
                rest = [f for f in orig if valid(f)] + ([sk] if sk is not None else [])
                for r in roles.values():
                    rest += [r.get("bf"), r.get("cb")]
                regroup(cf, [f for f in rest if f is not None])
            except Exception:                      # noqa: BLE001
                pass
        raise
