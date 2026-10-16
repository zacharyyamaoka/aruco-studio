"""The edit model: what OK does to a tag's node, from numbers alone.

Ported from REF `ArucoMarkers/aruco_feature.py` (cad-exporter c8216ff):
`settle`, `keep_black_step`, `_merged`, `structural_change`, `edit_kind`,
`_settings_key`, `_edit_changes`, `rebuild_reason`, `_trim_not_in_place`; and
from `aruco_extrude_sync.py` the after-compute `verdict` and `BUDGET_MS`.
The bodies are REF's. Where REF read a Fusion custom feature `cf`, these
take a `NodeState`: the plain values the adapter reads off the node.

| REF read | NodeState field |
|---|---|
| `settings_of(cf)` (the "spec" named value) | `stored` (the JSON, parsed) -> `.settings` |
| `numbers_of(cf)`, `_param(cf, pid)` | `params` ({id: mm}) -> `.numbers`, `.has_param` |
| `black_follows(cf, s)` | `black_linked` |
| `aruco_tags.frame_sketch_of(cf) is not None` | `frame_sketch` |
| `aruco_restructure.node_roles(cf, s)` raising | `roles_error` |
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Sequence

from . import numbering as _numbering
from . import restructure as _restructure
from . import settings as _settings
from .settings import (MODES, OR, PARAMS, SL, SPEC_VERSION, TARGET_KEYS, effective_op,
                       has_frame_sketch, is_legacy, node_structure, normalise, plan_of,
                       resolve_follow, size_is_auto, structure, trim_setting)


@dataclass
class NodeState:
    """What a tag's node holds, as the adapter read it."""
    stored: Optional[dict]                         # the "spec" named value (JSON-parsed)
    params: Dict[str, float] = field(default_factory=dict)   # every parameter it HAS, mm
    black_linked: bool = False                     # the black offset follows the white top
    frame_sketch: bool = True                      # its frame sketch is there (jo_v 2)
    roles_error: Optional[str] = None              # its features do not match its parts

    @property
    def settings(self) -> Optional[dict]:
        return _settings.settings_from_stored(self.stored)

    @property
    def numbers(self) -> dict:
        return _settings.numbers_from_params(self.settings, self.params)

    def has_param(self, pid: str) -> bool:
        return pid in self.params and self.params[pid] is not None


def _flags():
    """REF's switches, read when called (a test may set them on settings)."""
    return _settings.JO_AFTER, _settings.RESTRUCTURE_IN_PLACE


def settle(s, n, ev):
    """What a new node stores, from create()'s settings / numbers and the
    evaluate() it builds (copies): its parts, the spec version, no pin
    where the plan has none, Auto size as the size parameters 0 (a typed
    size as the number it was built at), its Joint Origin layout.
    `ev`: {"spec": markers.TagSpec, "plan": slabs.Plan} (evaluate()'s)."""
    s, n = dict(s), dict(n)
    spec, plan = ev["spec"], ev["plan"]
    if "trim" in s:                     # Trim excess: kept normalised, or not at all
        t = trim_setting(s)
        if t is None:
            s.pop("trim")
        else:
            s["trim"] = t
    s["parts"] = list(plan.parts)
    s["v"] = SPEC_VERSION
    if plan.pin is None:
        s["pin"] = "none"
    s["size_auto"] = size_is_auto(s, n)
    if s["size_auto"]:
        # Auto size stays Auto: the parameters 0, so every compute fits the
        # size on the face as it is then -- what this evaluate() built
        n.update(size=0.0, square=0.0)
    else:
        # a typed size is the number it was built at (clamped to fit)
        n.update(size=spec.marker_length_m * 1000.0,
                 square=spec.square_length_m * 1000.0 if s["layout"] == "charuco" else 0.0)
    s["jo_v"] = 2 if has_frame_sketch(s) else 1
    return s, n


def keep_black_step(mode_old, n_old, mode, n, followed=False):
    """An edit that does not say where the black starts keeps where it
    stood against its own surface -- the white top in White + black, the
    face in Black only -- like the dialog (its "Black offset" moves with
    the white): when the mode changes, and in White + black when the black
    followed the white (link_black). 2026-10-09: a Black only node rebuilt
    as White + black kept its black at the face, UNDER the new tile; the
    pocket (the black's bottom up to the white top) went through the whole
    tile and cut it in two -- the second piece, "tag tile ck (1)", stayed
    the component's grey. -> n (a copy, black offset set when it applies)."""
    S = SL()
    if mode not in ("both", "black"):
        return n
    old = mode_old if mode_old in MODES else "both"
    if mode == old and not (mode == "both" and followed):
        return n
    try:
        step = float(n_old["black_offset"]) - S.white_top(old, n_old)
        return dict(n, black_offset=S.clamp_offset(S.white_top(mode, n) + step))
    except (KeyError, TypeError, ValueError):
        return n


def merged(node: NodeState, s_new, n_new):
    """REF `_merged(cf, s_new, n_new)`: an edit's settings and numbers over
    the node's own (read only): -> (s_old, n_old, s, n) as apply_edit
    writes them."""
    JO_AFTER, _ = _flags()
    s_old, n_old = node.settings, node.numbers
    s_new = normalise(s_new, partial=True)
    s = dict(s_old)
    s.update({k: v for k, v in s_new.items()
              if k not in TARGET_KEYS})
    n = dict(n_old)
    n.update(n_new)
    if s.get("mode") == "auto":
        s["mode"] = "black" if s.get("has_body") else "both"
    # only an edit that ASKS puts the black at the white top: a node made
    # earlier today stored "black_follows", which must not undo a step the
    # user dialled in (the dialog sends the black offset it shows)
    s.pop("black_follows", None)
    if s_new.get("black_follows"):
        n = resolve_follow(dict(s, black_follows=True), n)
    elif "black_offset" not in n_new:
        n = keep_black_step(s_old.get("mode"), n_old, s["mode"], n,
                            node.black_linked)
    if plan_of(s, n).pin is None:
        s["pin"] = "none"
    if "turn" in s_new:
        s["origin_v"] = OR().ORIGIN_RULE    # an Origin picked now: every one there is
    # Auto size is the size parameter 0 (the dialog sends 0 for Auto); a
    # node made before that keeps its flag while its numbers stay as they are
    same_size = all(abs(float(n.get(k) or 0.0) - float(n_old.get(k) or 0.0)) < 1e-9
                    for k in ("size", "square"))
    s["size_auto"] = size_is_auto(s, n) or (same_size and bool(s_old.get("size_auto")))
    # the node's own Joint Origin layout (a script may ask for the frame
    # sketch); JO_AFTER moves an older node's Joint Origin behind it -- by a
    # rebuild, and only on an edit that changes something (OK on an
    # unchanged dialog changes nothing)
    s["jo_v"] = s_new.get("jo_v", s_old.get("jo_v", 1))
    if JO_AFTER and not has_frame_sketch(s_old) and edit_changes(node, s, n, s_old, n_old):
        s["jo_v"] = 2
    return s_old, n_old, s, n


_merged = merged


def structural_change(node: NodeState, s_old, s, n):
    """Does an edit change what the node is made of (its parts, Join / New,
    the mode; an older node; its frame sketch)? A Type change alone needs
    no other parts: in place it is a compute."""
    _, RESTRUCTURE_IN_PLACE = _flags()
    sketch_lost = has_frame_sketch(s_old) and not node.frame_sketch
    return bool(is_legacy(s_old) or structure(s, n) != node_structure(s_old)
                or (s["layout"] != s_old["layout"] and not RESTRUCTURE_IN_PLACE) or sketch_lost
                or has_frame_sketch(s) != has_frame_sketch(s_old))


def trim_not_in_place(s_old, s, n):
    """Why a structural edit with a Trim excess part cannot be done in place
    (aruco_restructure knows the role once "trim" is in its ROLE_ORDER;
    until then such an edit is rebuilt -- never a column body left loose),
    or None."""
    try:
        if "trim" in tuple(getattr(_restructure, "ROLE_ORDER", ()) or ()):
            return None
    except Exception:                              # noqa: BLE001
        pass
    try:
        if "trim" in ((s_old or {}).get("parts") or ()) or "trim" in plan_of(s, n).parts:
            return "the trim is not made in place yet"
    except Exception:                              # noqa: BLE001
        return "the trim is not made in place yet"
    return None


_trim_not_in_place = trim_not_in_place


def edit_kind(node: NodeState, s_new, n_new):
    """What OK does with these values (read only, for the dialog): {"kind":
    "compute" | "in place" | "rebuild", "why": why a rebuild, "goes": the
    roles the node loses, "op_changes": Join <-> New}."""
    s_old, _n_old, s, n = merged(node, s_new, n_new)
    if not structural_change(node, s_old, s, n):
        return {"kind": "compute", "why": None, "goes": [], "op_changes": False}
    why = _restructure.refusal(node, s_old, s, n) or trim_not_in_place(s_old, s, n)
    return {"kind": "rebuild" if why else "in place", "why": why,
            "goes": _restructure.what_goes(s_old, s, n),
            "op_changes": effective_op(s_old) != plan_of(s, n).op}


def settings_key(s, skip=()):
    """Settings as they matter to the build: without the spec version and a
    script's one-shot "black_follows" (never stored)."""
    return {k: v for k, v in (s or {}).items() if k not in ("v", "black_follows") + tuple(skip)}


_settings_key = settings_key


def edit_changes(node: NodeState, s, n, s_old, n_old):
    """Does an edit change the node: a setting, or a parameter it has?"""
    if settings_key(s, ("jo_v",)) != settings_key(s_old, ("jo_v",)):
        return True
    for pid in PARAMS:
        if not node.has_param(pid):
            continue
        try:
            if abs(float(n[pid]) - float(n_old[pid])) > 1e-9:
                return True
        except (KeyError, TypeError, ValueError):
            return True
    return False


_edit_changes = edit_changes


def rebuild_reason(node: NodeState):
    """Why OK in the edit dialog will rebuild this node instead of updating
    it, or None. Fusion shows only "Compute Failed" on a node whose new
    parameters need other parts, so the dialog says it."""
    JO_AFTER, _ = _flags()
    s = node.settings
    if not s:
        return None
    if is_legacy(s):
        return ("made by an older ArUco Extrude: OK rebuilds it with Offset / Height "
                "parameters (same geometry)")
    try:
        built, want = node_structure(s), structure(s, node.numbers)
    except Exception:                              # noqa: BLE001
        return None
    if built != want:
        return ("its parameters now need " + ", ".join(want[2]) + " (it has "
                + ", ".join(built[2]) + "): OK rebuilds it")
    if has_frame_sketch(s) and not node.frame_sketch:
        return "its Joint Origin's frame sketch is missing: OK rebuilds it"
    if JO_AFTER and not has_frame_sketch(s):
        return ("made with its Joint Origin before it: a change here moves the Joint "
                "Origin behind it, once (OK on no change keeps it as it is)")
    return None


# --------------------------------------------- after a compute (aruco_extrude_sync)

BUDGET_MS = 5.0            # after_compute gives up past this (it runs in EVERY compute)


@dataclass
class SyncState:
    """What REF's aruco_extrude_sync kept per document (its `_st()`)."""
    auto_refresh: str = "all"                     # aruco_extrude_sync.AUTO_REFRESH at c8216ff
    doc_is_mine: bool = False
    undoing: bool = False
    after_undo: bool = False
    done: Sequence = ()                           # digests already refreshed
    failed: Optional[dict] = None
    recent: Sequence = ()                         # recent refresh times (the burst limit)


def verdict(state: SyncState, digest, now: float):
    """REF `aruco_extrude_sync.verdict(des, digest)`: the after-compute
    check's conclusion -- core.numbering.auto_decision on the document's
    state. -> (action, why)."""
    return _numbering.auto_decision(state.auto_refresh, state.doc_is_mine,
                                    bool(state.undoing or state.after_undo), digest,
                                    done=state.done or (), failed=state.failed,
                                    recent=state.recent or (), now=now)
