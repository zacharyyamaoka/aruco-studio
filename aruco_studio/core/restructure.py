"""What a structural edit does to a node, as a plan (pure).

Ported from REF `ArucoMarkers/aruco_restructure.py` (cad-exporter c8216ff):
`ROLE_ORDER`, `has_combine`, `restructure_plan`, `new_parts`,
`needed_params`, `refusal`, `what_goes`, copied verbatim. The in-place
`restructure()` itself (release, delete, create, regroup, atomic),
`node_roles`, `_refs`, `dependents_of`, `downstream_snapshot` and
`lost_after` read Fusion's timeline and stay in the Fusion adapter.

`refusal` took the custom feature `cf`; here it takes a `core.edits.NodeState`
(what the adapter read off the node: its parameters, and whether its
features match its parts -- `node_roles` raising, as `roles_error`).

`params_for` (which custom parameters a node of these settings carries) is
REF `aruco_feature.params_for`; the module map left it with the adapter, but
it is pure and `needed_params` needs it, so it lives here.
"""
from __future__ import annotations

from . import settings as _settings

# "trim" (2026-10-16, Trim excess: docs/design_aruco_trim.md): the LAST
# part, the kept column; its combine INTERSECTS the body under the tag
ROLE_ORDER = ("tile", "pin", "pocket", "pattern", "recess", "trim")


def F():
    """REF's `aruco_feature` accessor: the settings model here."""
    return _settings


def params_for(s):
    """The custom parameters a node of these settings carries (besides
    marker_id): the size, the checker (ChArUco), each colour's Offset and
    Height, the pins' numbers when it has pins."""
    out = ["size"]
    if s["layout"] == "charuco":
        out.append("square")
    if s["mode"] in ("both", "white"):
        out += ["white_offset", "white_height"]
    if s["mode"] in ("both", "black"):
        out += ["black_offset", "black_height"]
    if "pin" in (s.get("parts") or ()):
        out += list(_settings.PIN_PARAMS)
    return out


def has_combine(role, op):
    """Does this role carry a combine (create's order: right after its base
    feature)? The tile only when joined to the body under it; the trim's
    intersect always (on the body under -- Join <-> New body never
    retargets it)."""
    return role in ("pin", "pocket", "recess", "trim") or (role == "tile" and op == "join")


def restructure_plan(parts_old, op_old, parts_new, op_new):
    """What an in-place restructure does (pure): {"delete_roles": roles
    whose base feature (and combine) go, "delete_combines": roles that stay
    but lose their combine (Join <-> New: the tile's join, the pocket's cut
    target), "create_roles": roles made new (base feature, and combine when
    it has one), "create_combines": roles that stay and get a (new)
    combine, "keep": roles that keep their base feature}."""
    gone = [r for r in parts_old if r not in parts_new]
    keep = [r for r in parts_new if r in parts_old]
    new = [r for r in parts_new if r not in parts_old]
    del_cb, add_cb = [], []
    for r in keep:
        had, has = has_combine(r, op_old), has_combine(r, op_new)
        # the combine's target changes with the op: the tile's join, the
        # pocket's cut (the joined body <-> the tile)
        retarget = op_old != op_new and r in ("tile", "pocket")
        if had and (not has or retarget):
            del_cb.append(r)
        if has and (not had or retarget):
            add_cb.append(r)
    return {"delete_roles": gone, "delete_combines": del_cb, "create_roles": new,
            "create_combines": add_cb, "keep": keep}


def new_parts(s, n):
    return list(F().plan_of(s, n).parts)


def needed_params(s, parts):
    return set(params_for(dict(s, parts=list(parts)))) | {"marker_id"}


def refusal(node, s_old, s, n):
    """Why this structural edit cannot be done in place (it is rebuilt by
    delete + create), or None. `node`: a core.edits.NodeState."""
    Fm = F()
    if not getattr(Fm, "RESTRUCTURE_IN_PLACE", False):
        return "it changes what the tag is made of"
    if Fm.is_legacy(s_old):
        return "made before 2026-10-08 (no parts)"
    parts = new_parts(s, n)
    missing = sorted(p for p in needed_params(s, parts) if not node.has_param(p))
    if missing:
        return ("it has no " + ", ".join(missing) + " parameter" + ("s" if len(missing) > 1 else "")
                + " (made before 2026-10-13: a node cannot gain a parameter)")
    if Fm.has_frame_sketch(s_old) and not Fm.has_frame_sketch(s):
        return "its Joint Origin goes back before it"
    if node.roles_error is not None:
        return f"its features do not match its parts ({node.roles_error})"
    return None


def what_goes(s_old, s, n):
    """The roles an edit removes from a node (in place or by a rebuild)."""
    try:
        old = list(s_old.get("parts") or [])
        new = new_parts(s, n)
    except Exception:                              # noqa: BLE001
        return []
    return [r for r in old if r not in new]
