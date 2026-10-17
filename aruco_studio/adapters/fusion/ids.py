"""Per-copy IDs: the design as an AssemblySnapshot, and a copy's part.

Numbering is the core's (`core.ids_design.plan_snapshot` ->
`core.numbering.plan_stable`, the ledger, the stamps). A copy's geometry is
the plan's (`plan.variants.copy_plan`: the template's plan with the copy's
id and label). This module only reads Fusion's occurrence model into the
snapshot (ARCHITECTURE 5.4) and builds a copy's part as an occurrence:

| Read / made | Fusion | REF (aruco_ids_feature, c8216ff) |
|---|---|---|
| every copy: its path ("+"-joined), component, light bulbs up the path, linked flag, world transform | `Occurrence.fullPathName`, `isVisible`, `isReferencedComponent`, `transform2` | `collect_design` |
| the tag records | the component attribute ("bam_aruco", "tags") | `_record_live`, `read_tag_records` |
| a copy's stamp {"uid", "born", "home"} | the occurrence attribute ("bam_aruco", "stamp") | `read_stamps` |
| the ID ledger | the root attribute ("bam_aruco", "idsLedger") | `read_ledger` / `write_ledger` |
| a renumbered copy's part | a new component occurrence at the copy's world transform; one base feature per part of the copy's plan | `_make_part_occurrence`, `part_bodies` |

Not in this skeleton (Fusion-gated): the hidden-original rules for linked
designs, the joint that makes a part follow its copy, the repaint hook, the
replaced Delete command.
"""
from __future__ import annotations

import json

import adsk.core

from ...core import ids_design as ID
from ...plan import variants as VA
from .. import recipe as RC
from . import bodies as B
from . import feature as FT
from . import paint as PT
from . import records as REC

STAMP_ATTR = "stamp"
LEDGER_ATTR = "idsLedger"


def _attr_json(attrs, name):
    a = attrs.itemByName(REC.G, name)
    if not a:
        return None
    try:
        return json.loads(a.value)
    except ValueError:
        return None


def snapshot(des, overrides=None) -> ID.AssemblySnapshot:
    """The design as numbering needs it (every copy, hidden ones too)."""
    tags = []
    for comp in des.allComponents:
        label = REC.component_label(des, comp)
        for r in REC.read_tag_records(comp):
            if r.get("variant_of"):
                continue
            tags.append(dict(r, component=label))
    occs = []
    # root.allOccurrences: proxies whose transform2 IS the world transform
    # (one made with createForAssemblyContext down a path is not, 2705)
    for occ in des.rootComponent.allOccurrences:
        occs.append({"path": occ.fullPathName, "component": occ.component.name,
                     "visible": bool(occ.isVisible), "linked": bool(occ.isReferencedComponent),
                     "world": list(occ.transform2.asArray()),
                     "stamp": _attr_json(occ.attributes, STAMP_ATTR)})
    return ID.AssemblySnapshot(design_units="cm", tags=tags, occurrences=occs,
                               overrides=dict(overrides or {}),
                               ledger=_attr_json(des.attributes, LEDGER_ATTR),
                               root=des.rootComponent.name)


def plan_ids(des, overrides=None):
    """What ArUco IDs' OK would number the design as (core)."""
    return ID.plan_snapshot(snapshot(des, overrides))


def write_ledger(des, ledger_dict):
    """The ledger after OK (core's dict) on the root: printed ids never move."""
    text = json.dumps(ledger_dict, sort_keys=True)
    a = des.attributes.itemByName(REC.G, LEDGER_ATTR)
    if a is not None and a.value == text:
        return False
    des.attributes.add(REC.G, LEDGER_ATTR, text)
    return True


def make_part(des, template_plan, final_id, world, name, base=None):
    """A renumbered copy's part: a new component occurrence at the copy's
    world transform (row-major, cm), its bodies from the copy's plan. ->
    (occurrence, the copy's TagPlan, its recipe)."""
    copy = VA.copy_plan(template_plan, int(final_id), name=name)
    rec = RC.recipe(copy, base, frame_sketch=False)
    m = adsk.core.Matrix3D.create()
    o, x, y, z = RC.frame_of_matrix(world)
    m.setWithCoordinateSystem(adsk.core.Point3D.create(*o), adsk.core.Vector3D.create(*x),
                              adsk.core.Vector3D.create(*y), adsk.core.Vector3D.create(*z))
    occ = des.rootComponent.occurrences.addNewComponent(m)
    comp = occ.component
    comp.name = f"aruco id {name}"
    made = {}
    for p in rec["parts"]:
        if p["op"] != "add":
            continue                                # the cut tools belong to the template
        bf, body = FT.base_body(comp, B.part_body(rec, p), f"aruco id {name} . {p['name']}")
        made[p["role"]] = body
    PT.paint_node(des, rec, made)
    return occ, copy, rec
