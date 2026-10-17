"""The tag record on a component, and a node read back as a TagSpec.

| What | Where it comes from |
|---|---|
| the record's geometry (board, frame, mark, label) | `TagPlan.record` (plan/record.py, REF `_write_record`'s dict without Fusion's handles) |
| the record's `fusion` handles (tokens, body names, group, mode) | this module: what create() made |
| a node's settings + numbers | its "spec" named value and its parameters (cm -> mm here; nothing else) |
| the TagSpec of a node | `plan.spec.from_record` on what was read |
| the node's print settings as a preset | `core.presets.preset_of` (the mapping is the core's) |
| `body_role` | REF `aruco_export.body_role`: parses Fusion's body NAMES, so it is the adapter's |

Records live in the component attribute ("bam_aruco", "tags") as a JSON
list, one per tag key (REF `aruco_tags.read_tag_records` /
`write_tag_records`). A write that changes nothing is not made: an Edit ->
OK that changes nothing leaves the attribute untouched.
"""
from __future__ import annotations

import json

from ...core import edits as E
from ...core import presets as PR
from ...core import settings as S
from ...plan import spec as SP

G = "bam_aruco"                          # REF aruco_tags.G (core.markers.ATTR_GROUP)
TAGS_ATTR = "tags"
SPEC_VALUE = "spec"                      # the node's named value


# --------------------------------------------------------------- records

def read_tag_records(comp):
    a = comp.attributes.itemByName(G, TAGS_ATTR)
    if not a:
        return []
    try:
        data = json.loads(a.value)
        return data if isinstance(data, list) else []
    except ValueError:
        return []


def _dump(records):
    return json.dumps(records, sort_keys=True)


def write_tag_records(comp, records) -> bool:
    """-> True when the attribute was written (False: it already said so)."""
    a = comp.attributes.itemByName(G, TAGS_ATTR)
    text = _dump(records)
    if a is not None and a.value == text:
        return False
    comp.attributes.add(G, TAGS_ATTR, text)
    return True


def component_label(des, comp):
    return "" if comp is des.rootComponent else comp.name


def record_of_plan(plan, component="", fusion=None):
    """TagPlan.record with the component's label and the adapter's handles."""
    rec = json.loads(json.dumps(plan.data["record"]))
    rec["component"] = component
    fz = dict(rec.get("fusion") or {})
    fz.update(fusion or {})
    rec["fusion"] = fz
    return rec


def write_record(comp, rec, live_keys=None) -> bool:
    """The tag's record replaces the one with its key; records of keys not
    in `live_keys` (their node is gone) are dropped. -> written?"""
    every = read_tag_records(comp)
    keep = [r for r in every if r.get("key") != rec.get("key")
            and (live_keys is None or r.get("key") in live_keys)]
    old = next((r for r in every if r.get("key") == rec.get("key")), None)
    if old is not None:
        for k in ("joint_origin", "joint_origin_name"):
            if (old.get("fusion") or {}).get(k) and k not in rec["fusion"]:
                rec["fusion"][k] = old["fusion"][k]
    # keep the original order: the record where it was, else last
    out = []
    placed = False
    for r in every:
        if r.get("key") == rec.get("key"):
            out.append(rec)
            placed = True
        elif r in keep:
            out.append(r)
    if not placed:
        out.append(rec)
    return write_tag_records(comp, out)


def find_record(comp, key):
    return next((r for r in read_tag_records(comp) if r.get("key") == key), None)


# --------------------------------------------------------------- the node

def stored_of(cf):
    """The node's "spec" named value, parsed; None when not written yet
    (compute runs inside customFeatures.add(), before the spec exists)."""
    try:
        nv = cf.customNamedValues
        if not nv.isExistingValue(SPEC_VALUE):
            return None
        return json.loads(nv.value(SPEC_VALUE))
    except (AttributeError, RuntimeError, ValueError):
        return None


def param(cf, pid):
    """CustomFeatureParameters.itemById RAISES for an unknown id (2705)."""
    try:
        return cf.parameters.itemById(pid)
    except RuntimeError:
        return None


def params_mm(cf):
    """{param id: value} of every parameter the node HAS: mm (Fusion keeps
    cm), marker_id unitless."""
    out = {}
    for pid in S.PARAMS + S.LEGACY_PARAMS:
        p = param(cf, pid)
        if p is None:
            continue
        out[pid] = float(p.value) if pid == "marker_id" else float(p.value) * 10.0
    return out


def node_state(cf, roles_error=None, frame_sketch=True):
    """What the edit model (core.edits) needs of a node."""
    return E.NodeState(stored=stored_of(cf), params=params_mm(cf),
                       black_linked=False, frame_sketch=frame_sketch, roles_error=roles_error)


def settings_of(cf):
    return S.settings_from_stored(stored_of(cf))


def numbers_of(cf):
    s = settings_of(cf)
    return S.numbers_from_params(s, params_mm(cf) if cf is not None else None)


def spec_of_node(cf, target, record=None, name=""):
    """A node as a TagSpec: its stored settings, its parameters (mm, legacy
    ones too: the plan maps them), the Target the adapter read."""
    return SP.from_record(stored_of(cf) or {}, params_mm(cf), target, record=record,
                          name=name)


def preset_of_node(cf, profile=None):
    """REF aruco_preset_library.preset_of_node: read here, mapped by the core."""
    s = settings_of(cf)
    if s is None:
        return None
    return PR.preset_of(s, numbers_of(cf), profile)


# --------------------------------------------------------------- bodies

def body_role(body, black_bases=()):
    """'cells' (the black filament) or 'tile' (the white one), by the body's
    NAME. An ArUco IDs part's body ("aruco id <copy> . <body>") by the body
    it copies. REF aruco_export.body_role, verbatim."""
    n = body.name
    if n in black_bases:
        return "cells"
    if " . " in n and n.startswith("aruco id "):
        n = n.split(" . ", 1)[1]
    if n.startswith("aruco cells"):
        return "cells"
    if n.startswith("aruco white"):
        return "tile"
    return "cells" if n in black_bases else "tile"
