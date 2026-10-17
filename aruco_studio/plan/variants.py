"""A copy's plan from its template's (REF aruco_ids_feature: part_plan,
id_regions, label_slots, label_warning; aruco_tags.copy_label).

A copy of a tagged part (a renumbered occurrence, a scene tag duplicated)
keeps its template's material and prints its own ids: the same fit, frame,
mark, slabs, pins and trim; the cells re-split by the new id; the label
laid out again in the template's slots with the copy's own text
(core.label.relabel). Nothing else may differ (tests/plan/test_variants.py).
"""
from __future__ import annotations

import copy
import dataclasses
from typing import List, Optional, Tuple

from ..core import label as _AL
from ..core import markers as _M
from .plan import TagPlan, build
from .spec import Issue

Rect = Tuple[float, float, float, float]


def copy_spec(spec, final_id: int):
    """The board a copy prints: the template's, its first id `final_id`."""
    return dataclasses.replace(spec, marker_id=int(final_id))


def copy_plan(template: TagPlan, final_id: int, name: Optional[str] = None,
              key: Optional[str] = None, spec=None) -> TagPlan:
    """The copy's TagPlan. `name`: {name} for the copy (REF part_name of its
    occurrence path), the template's by default; `key` the record key.
    `spec`: the template's TagSpec request (the copy's request keeps it,
    marker_id changed)."""
    if not template.ok or template.ev is None:
        return template
    ev = dict(template.ev)
    ev["notes"] = list(template.ev["notes"])
    new = copy_spec(template.ev["spec"], final_id)
    ev["spec"] = new
    lab = template.ev.get("label")
    k = key if key is not None else template.data.get("key", "")
    nm = name if name is not None else template.data.get("name", "")
    if lab is not None and lab.settings.on and lab.kind != "none":
        ev["label"] = _AL.relabel(lab.to_dict(6), new, name=nm, key=k)
    req = spec if spec is not None else template.request
    req = dataclasses.replace(req, name=nm, key=k,
                              numbers=dict(req.numbers or {}, marker_id=int(final_id)))
    s = dict(template.settings)
    n = dict(template.numbers, marker_id=int(final_id))
    return build(req, s, n, ev)


def cells_mm(spec) -> List[Rect]:
    return [(x0 * 1000.0, y0 * 1000.0, x1 * 1000.0, y1 * 1000.0)
            for (x0, y0, x1, y1) in _M.cell_boxes(spec)]


def id_regions(template: TagPlan, copy_: TagPlan) -> dict:
    """Where the pattern's colour depends on the id (mm, pattern frame):
    the template's cells and the copy's (a rasteriser or a boolean gives
    stop = old - new, start = new - old); the corner mark and a ChArUco
    board's squares are the same in both and cancel."""
    a, b = template.ev["spec"], copy_.ev["spec"]
    old, new = cells_mm(a), cells_mm(b)
    same = sorted(set(map(tuple, old)) & set(map(tuple, new)))
    return {"old": old, "new": new, "same": same,
            "changed": sorted(set(map(tuple, old)) ^ set(map(tuple, new)))}


def label_slots(template: TagPlan, final_id: int, name: str = "") -> List[Rect]:
    """The slots the template's label text lies in (core.label.copy_regions):
    where a copy repaints its own text. [] for no label."""
    lab = template.data.get("label")
    if not lab or lab.get("kind") in (None, "none"):
        return []
    reg = _AL.copy_regions(lab, copy_spec(template.ev["spec"], final_id), name=name,
                           key=template.data.get("key", ""))
    return [tuple(r) for r in reg.get("slots") or []] if reg.get("on") else []


def label_warning(template: TagPlan, final_id: int, name: str = "") -> str:
    """REF label_warning: "" when the copy's label is fine or there is none;
    else why it prints no label, or that it was built anyway."""
    lab = template.data.get("label")
    if not lab:
        return ""
    try:
        reg = _AL.copy_regions(lab, copy_spec(template.ev["spec"], final_id), name=name,
                               key=template.data.get("key", ""))
        return (reg or {}).get("warning") or ""
    except Exception as exc:                       # noqa: BLE001
        return f"the label could not be checked ({type(exc).__name__}: {exc})"[:200]
