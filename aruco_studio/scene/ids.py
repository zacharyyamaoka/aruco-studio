"""Unique ids across a scene, through REF's numbering (core.numbering).

The scene is handed to `plan_stable` as an assembly (ARCHITECTURE 5.4):
every scene tag is a component of its own name holding one tag (key
"tag"), with one occurrence at the tag's place on the canvas. Its stamp
chain is the tag's uid, so a renamed or moved tag is still the same copy
for the ledger. A locked (printed) tag is `fixed`: it keeps what it prints
and the others go round it. The ledger lives in the scene file: an id a
tag ever printed is never handed to another tag.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from ..core import markers as _M
from ..core import numbering as _N
from ..plan import plan_tag
from .model import Scene, mat_mul

KEY = "tag"


def instance(name: str) -> str:
    return _N.instance_name(name, KEY)


def snapshot(scene: Scene, plans: Optional[dict] = None):
    """(tags, occurrences, overrides, fixed, chains, errors) for plan_stable."""
    plans = plans if plans is not None else scene.plans()
    tags, occs, fixed, chains, errors = [], [], {}, {}, {}
    for t in scene.tags:
        p = plans[t.name]
        if not p.ok:
            errors[t.name] = "; ".join(p.data["errors"])
            continue
        o, x, y, z = p.ev["tag"]
        # the tag frame (cm in the target frame) as the record keeps it, in mm
        tags.append(_M.TagDef(key=KEY, component=t.name, spec=p.ev["spec"],
                              origin=[c * 10.0 for c in o], x_axis=list(x), y_axis=list(y),
                              z_axis=list(z), units="mm", name=t.name))
        occs.append(_M.OccurrenceRef(path=t.name, component=t.name, transform=t.pose,
                                     visible=not t.hidden))
        chains[t.name] = "#" + t.uid
        if t.locked:
            fixed[instance(t.name)] = "locked: a printed tag keeps its ids"
    overrides = {instance(n): int(i) for n, i in scene.overrides.items()
                 if n in scene.names()}
    return tags, occs, overrides, fixed, chains, errors


def plan_ids(scene: Scene, plans: Optional[dict] = None):
    """The numbering (core.numbering.IdsPlan) the scene would get."""
    tags, occs, overrides, fixed, chains, errors = snapshot(scene, plans)
    led = _N.Ledger.from_any(scene.ledger) if scene.ledger else None
    plan = _N.plan_stable(tags, occs, ledger=led, overrides=overrides, fixed=fixed,
                          chains=chains, design_units="mm", root_component="")
    return plan, chains, errors


def renumber(scene: Scene, when: str = "") -> dict:
    """Number the scene: every visible tag its own ids (per dictionary
    family), boards contiguous, printed ids kept (the ledger), overrides
    taken as typed, locked tags untouched. Writes each tag's marker_id and
    the ledger. -> the report {rows, changed, duplicates, warnings, errors}."""
    plans = scene.plans()
    plan, chains, errors = plan_ids(scene, plans)
    changed = []
    by = {r.name: r for r in plan.rows}
    for t in scene.tags:
        r = by.get(instance(t.name))
        if r is None or r.hidden or r.error or t.locked:
            continue
        cur = int(round(float((t.spec.numbers or {}).get("marker_id", 0) or 0)))
        if r.final != cur:
            t.spec.numbers = dict(t.spec.numbers or {}, marker_id=int(r.final))
            changed.append({"tag": t.name, "from": cur, "to": int(r.final)})
    if plan.ok:
        scene.ledger = _N.ledger_after(plan, chains, when=when).to_dict()
    rows = []
    for r in plan.rows:
        d = r.to_dict()
        d["tag"] = _N.split_name(r.name)[0]
        rows.append(d)
    return {"rows": rows, "changed": changed, "duplicates": plan.duplicates(),
            "warnings": list(plan.warnings), "errors": list(plan.errors) + [
                f"{n}: {e}" for n, e in errors.items()], "ok": plan.ok}


def duplicates(scene: Scene) -> Dict[str, List[str]]:
    """'<family>#<id>' -> the visible tags printing it (two or more)."""
    out: Dict[str, List[str]] = {}
    for t in scene.tags:
        if t.hidden:
            continue
        p = plan_tag(t.spec)
        if not p.ok:
            continue
        fam = _N.family(p.data["marker"]["dictionary"])
        for i in p.data["ids"]:
            out.setdefault(f"{fam}#{i}", []).append(t.name)
    return {k: v for k, v in out.items() if len(v) > 1}


def marker_centres(scene: Scene, plans: Optional[dict] = None) -> List[dict]:
    """Every marker's centre in the scene (mm): [{tag, id, x, y}]."""
    from ..core import board as _B
    plans = plans if plans is not None else scene.plans()
    out = []
    for t in scene.tags:
        p = plans[t.name]
        if not p.ok or t.hidden:
            continue
        sp = _M.TagSpec.from_dict(p.data["marker"], lambda m: None, t.name)
        M = mat_mul(t.pose, p.data["frames"]["pattern_in_target"])
        for mid, cs in _B.marker_corners_m(_M.board_spec(sp)).items():
            u = sum(c[0] for c in cs) / 4.0 * 1000.0
            v = sum(c[1] for c in cs) / 4.0 * 1000.0
            out.append({"tag": t.name, "id": int(mid), "x": M[0] * u + M[1] * v + M[3],
                        "y": M[4] * u + M[5] * v + M[7],
                        "dictionary": sp.dictionary})
    return out
