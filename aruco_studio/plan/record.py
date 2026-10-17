"""The record a tag stores, its digests and the node's words.

Ported from REF (cad-exporter c8216ff), bodies unchanged:

| REF | Here |
|---|---|
| `aruco_feature.node_warning`, `_label`, `mark_record`, `label_record`, `record_extras`, `optical_of_ev`, `record_same`, `frame_digest`, `ev_digest`, `record_digest`, `_same_label` | the same names (`_label` as `node_name`) |
| `aruco_tags.optical_frame_cm` | `optical_frame_cm` |

`record(ev, key, component)` is `_write_record`'s dict without Fusion's
handles (tokens, body names, the group): `TagDef.to_dict()` plus
`fusion.mark` / `fusion.label`. The adapter adds its handles.
"""
from __future__ import annotations

import hashlib
import json

from ..core import chamfer as _CH
from ..core import label as _AL
from ..core import markers as _M
from ..core import settings as _S


def CH():
    return _CH


def AL():
    return _AL


def M():
    return _M


is_info = _S.is_info


def node_name(key, spec, mode, warn=""):
    """REF `_label`: the node's name; `warn` its warning in plain words."""
    what = {"both": "", "black": " · black only", "white": " · white only"}[mode]
    return f"ArUco {key}: {spec.label()}{what}" + (f" -- {warn}" if warn else "")


def node_warning(ev, limit=80):
    """The node's first warning (not an info note), in plain words for its
    name, or ''."""
    for t in (ev or {}).get("notes") or []:
        # a clamped typed size is STORED clamped (settle): no lasting warning
        if is_info(t) or t.startswith("clamped"):
            continue
        if t.startswith("label warning: "):
            t = "label " + t[len("label warning: "):]
        t = t.split(" (Build anyway")[0].strip()
        return t if len(t) <= limit else t[:limit - 1].rstrip() + "…"
    return ""


def optical_frame_cm(tag):
    """The frame OpenCV reports for this tag, in its component (cm).

    Tag frame (pattern centre on the face) composed with
    `markers.detector_frame` -- identity for a single marker, OpenCV's board
    origin for grid/ChArUco, lifted by raise_m for a raised black layer.
    """
    markers = M()
    D = list(markers.detector_frame(tag.spec))
    for i in (3, 7, 11):
        D[i] *= 100.0                              # m -> cm
    Wm = markers.mat_mul(tag.frame_matrix(), D)
    return ([Wm[3], Wm[7], Wm[11]], [Wm[0], Wm[4], Wm[8]],
            [Wm[1], Wm[5], Wm[9]], [Wm[2], Wm[6], Wm[10]])


def optical_of_ev(ev, key="tag"):
    """OpenCV's frame for what evaluate() gives (cm): where the tag's Joint
    Origin must read back."""
    o, x, y, z = ev["tag"]
    tag = M().TagDef(key=key or "tag", component="", spec=ev["spec"], origin=list(o),
                     x_axis=list(x), y_axis=list(y), z_axis=list(z))
    return optical_frame_cm(tag)


def mark_record(ev):
    """The corner mark as the tag record keeps it (fusion.mark), or None."""
    mark = ev.get("mark")
    return mark.to_dict(6) if mark is not None else None


def label_record(ev):
    """The label as the tag record keeps it (fusion.label), or None when the
    label is off. A refused label keeps its settings and notes."""
    lab = ev.get("label")
    if lab is None or not lab.settings.on:
        return None
    return lab.to_dict(6)


def record_extras(fz, ev):
    """fz (a record's "fusion" dict) with the corner mark and the label as
    `ev` makes them (set, or dropped when there is none). -> fz."""
    for k, v in (("mark", mark_record(ev)), ("label", label_record(ev))):
        if v is not None:
            fz[k] = v
        else:
            fz.pop(k, None)
    return fz


def record(ev, key="tag", component="", fusion=None):
    """The tag record (REF `_write_record`'s dict, without Fusion's handles):
    the board, its frame (cm), the corner mark and the label."""
    o, x, y, z = ev["tag"]
    tag = M().TagDef(key=key, component=component, spec=ev["spec"], origin=list(o),
                     x_axis=list(x), y_axis=list(y), z_axis=list(z), name=f"ArUco {key}")
    rec = tag.to_dict()
    rec["fusion"] = record_extras(dict(fusion or {}), ev)
    return rec


def _same_label(a, b):
    """Two records' labels: both none, or the same settings, texts and
    geometry (aruco_label.same: the strokes to 1 um)."""
    if not a and not b:
        return True
    if not a or not b:
        return False
    try:
        la, lb = AL().from_dict(a), AL().from_dict(b)
        return (la.settings.to_dict() == lb.settings.to_dict() and la.texts() == lb.texts()
                and AL().same(a, b))
    except Exception:                              # noqa: BLE001
        return False


def record_same(old, ev, tol_cm=1e-7):
    """Does a tag record still say what evaluate() gives -- the board (spec),
    its frame, corner mark and label?"""
    if old is None:
        return False
    try:
        return (json.dumps(old.get("spec"), sort_keys=True)
                == json.dumps(ev["spec"].to_dict(), sort_keys=True)
                and all(max(abs(a - b) for a, b in zip(old.get(k) or [9e9] * 3, v)) < tol_cm
                        for k, v in zip(("origin", "x_axis", "y_axis", "z_axis"), ev["tag"]))
                and CH().same((old.get("fusion") or {}).get("mark"), mark_record(ev))
                and _same_label((old.get("fusion") or {}).get("label"), label_record(ev))
                and "frame" not in old and "frame_offset" not in old)
    except Exception:                              # noqa: BLE001
        return False


def frame_digest(spec_dict, frame, nd=6):
    """A short digest of a tag as its record keeps it: the board and its
    frame (cm, rounded to 1e-6)."""
    body = json.dumps([spec_dict, [[round(float(c), nd) for c in v] for v in frame]],
                      sort_keys=True)
    return hashlib.sha1(body.encode("utf-8")).hexdigest()[:16]


def ev_digest(ev):
    return frame_digest(ev["spec"].to_dict(), ev["tag"])


def record_digest(rec):
    try:
        return frame_digest(rec.get("spec"), [rec.get(k) for k in ("origin", "x_axis", "y_axis",
                                                                   "z_axis")])
    except Exception:                              # noqa: BLE001
        return None


def ink_digest(plan_dict):
    """What a PRINTED tag must keep (the Studio's lock): the board, its
    frame, the mark and the label's geometry and texts -- a digest of the
    record's pieces, so a move of the whole tag on the canvas (which is the
    scene's pose, not the plan) never changes it."""
    rec = plan_dict.get("record") or {}
    fz = rec.get("fusion") or {}
    lab = fz.get("label") or {}
    body = json.dumps([rec.get("spec"), [[round(float(c), 6) for c in rec.get(k) or []]
                                         for k in ("origin", "x_axis", "y_axis", "z_axis")],
                       fz.get("mark"), lab.get("parts"), lab.get("white"), lab.get("kind")],
                      sort_keys=True)
    return hashlib.sha1(body.encode("utf-8")).hexdigest()[:16]
