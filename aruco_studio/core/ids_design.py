"""ArUco IDs over an assembly snapshot: numbering a whole design.

Ported from REF (cad-exporter c8216ff) `ArucoMarkers/aruco_ids_feature.py`,
its pure part. `stamp_chains`, `plan_design` and `_warning_text` are REF's
bodies verbatim. REF's `collect_design(des)` read Fusion into a dict
("coll"); here an `AssemblySnapshot` (docs/ARCHITECTURE.md 5.4) holds the
same facts as plain data and `collection()` makes that dict, so
`plan_design` runs unchanged on a Studio scene, a Fusion design or a
build123d assembly.

Adapted (REF read Fusion objects):

| Here | REF | Took from Fusion |
|---|---|---|
| `ComponentLabels(names, root)` | `Labels(des)` | `des.allComponents`, `des.rootComponent` |
| `unique_name(names, base, taken)` | `_unique_name(des, base, taken)` | the design's component names |
| `node_state_of(value)` | `node_state(cf)` | the node's named value "ids" |
| `stamps(info)` | the tail of `read_stamps(...)` | the occurrences' stamp attributes, already read into `info` |
| `auto_verdict(state, digest, now)` | `auto_verdict(des, digest)` | the document's hook state |

Not here: `staleness` and `_drift` (they measure the built parts in Fusion),
`part_plan`, `id_regions`, `label_slots`, `part_paint_plan` (plan/variants.py,
M2), `export_overrides` (reads the node).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from . import markers as _markers
from . import numbering as _numbering
from .edits import SyncState


def M():
    return _markers


def N():
    return _numbering


SNAPSHOT_SCHEMA = "arucostudio.snapshot/1"

NV = "ids"


# Id stability (docs/proposal_aruco_ids_stability.md): the design's ID LEDGER
# is one attribute of the ROOT component -- it outlives the node (deleted,
# re-run) on purpose -- and every occurrence on a numbered copy's path that
# can be written carries a stamp {"uid", "born", "home"} (aruco_numbering).
LEDGER_ATTR = "idsLedger"


# After an upstream change (docs/design_aruco_ids_upstream.md): where the
# parts are rebuilt on their own -- "all" documents, "mine" (only documents
# this add-in created in this session: the gates' test documents), "off" (a
# warning asks for OK). "all" since 2026-10-13, after G8.5 passed 10/10 in
# Fusion (run B2; Zach: "ideally it just rebuilds correctly")
AUTO_REBUILD = "all"


def stamp_chains(info, losers=()):
    """{path: chain (aruco_numbering.chain_key)}, {path: born} from read_stamps' info."""
    markers = M()
    chains, born = {}, {}
    for path in info:
        parts = markers.split_path(path)
        segs, b = [], None
        for k in range(len(parts)):
            e = info.get(markers.join_path(parts[:k + 1]))
            if e is None:
                segs.append(None)
            elif e["inside_linked"]:
                segs.append("=" + parts[k])
            elif e["uid"] and e["nk"] not in losers:
                segs.append("#" + e["uid"])
                if e["born"] is not None:
                    b = e["born"] if b is None else max(b, e["born"])
            else:
                segs.append(None)
        chains[path] = N().chain_key(segs)
        if b is not None:
            born[path] = b
    return chains, born


def plan_design(coll, overrides=None, previous=None):
    """aruco_numbering.plan_stable on a collection: against the design's ID
    ledger (seeded from the node's state when the design has none yet), the
    stamps telling it which copy is which. overrides / previous default to
    the node's (a first OK: the ids an older ArUco IDs printed)."""
    markers = M()
    state = coll.get("state") or {}
    if overrides is None:
        overrides = dict(state.get("overrides") or {})
    if previous is None:
        previous = dict(state.get("auto") or {})
        if not previous and coll.get("legacy_overrides"):
            # migrating from per-level overrides: keep every number already printed
            old = markers.resolve(coll["tags"], list(coll["inherited"])
                                  + [x["record"] for x in coll["legacy_overrides"]],
                                  coll["occs"], coll["root"], "cm")
            previous = {N().instance_name(i.path, i.tag.key): int(i.spec.marker_id)
                        for i in old.instances}
    stale = {(r.get("component") or "", r.get("key")): r["_stale"]
             for r in coll["recs"] if r.get("_stale")}
    fixed = {}
    if stale:
        for o in coll["occs"]:
            for (comp, key), why in stale.items():
                if o.component == comp:
                    fixed[N().instance_name(o.path, key)] = f"its linked design's record lags ({why})"
    stamps = coll.get("stamps") or {}
    plan = N().plan_stable(coll["tags"], coll["occs"], ledger=coll.get("ledger"), state=state,
                           chains=stamps.get("chains"), born=stamps.get("born"),
                           overrides=overrides, previous=previous, inherited=coll["inherited"],
                           root_component=coll["root"], fixed=fixed)
    plan.warnings[:0] = list(coll.get("warnings") or [])
    return plan


def _warning_text(reasons, why=""):
    head = "; ".join(reasons[:3])
    if len(reasons) > 3:
        head += f" (+{len(reasons) - 3} more)"
    return (f"ArUco IDs' parts are out of date: {head}. " + (why + " " if why else "")
            + "Double-click ArUco IDs and press OK to rebuild them.")[:480]

warning_text = _warning_text


# ------------------------------------------- adapted: Fusion reads as arguments

class ComponentLabels:
    """REF Labels(des): component -> its label in the tag records -- the
    name, or, when two components share one (two linked designs can both
    have "Component1"), the name with a number. `names`: every component's
    name in the design's order (allComponents); `root`: the root's index."""

    def __init__(self, names: Sequence[str], root: int = 0):
        self.root = root
        self.items = []
        by: Dict[str, List[int]] = {}
        for i, n in enumerate(names):
            by.setdefault(n, []).append(i)
        self.duplicates = sorted(n for n, cs in by.items() if len(cs) > 1)
        for name, cs in by.items():
            for k, c in enumerate(cs):
                if c == self.root:
                    lab = ""
                else:
                    lab = name if len(cs) == 1 else f"{name} <{k + 1}>"
                self.items.append((c, lab))
        self.by_label = {lab: c for c, lab in self.items}
        self.names = list(names)

    def label(self, comp: int) -> str:
        if comp == self.root:
            return ""
        for c, lab in self.items:
            if c == comp:
                return lab
        return self.names[comp]

    def comp(self, label: str) -> Optional[int]:
        if not label:
            return self.root
        return self.by_label.get(label)


def unique_name(names, base, taken=()):
    """REF _unique_name(des, base, taken): `base`, or longer variants, never a
    name another component has (two components sharing a name was the rack's
    export bug, 2026-10-09). `names`: the design's component names."""
    names = set(names) | set(taken)
    if base not in names:
        return base
    k = 2
    while f"{base} ({k})" in names:
        k += 1
    return f"{base} ({k})"


def node_state_of(value):
    """REF node_state(cf) on the node's named value "ids" (text or dict):
    {} when there is none or it cannot be read."""
    if value is None:
        return {}
    try:
        return N().read_state(value)
    except Exception:                              # noqa: BLE001
        return {}


def stamps(info):
    """The pure tail of REF read_stamps: from {path: {"nk", "inside_linked",
    "uid", "born", "home"}} -> {"info", "losers", "chains", "born"}."""
    losers = N().stamp_losers([(e["nk"], e["uid"], e["home"]) for e in info.values() if e["uid"]])
    chains, born = stamp_chains(info, losers)
    return {"info": info, "losers": set(losers), "chains": chains, "born": born}


def auto_verdict(state: SyncState, digest, now: float):
    """REF auto_verdict(des, digest): aruco_numbering.auto_decision for this
    document now, under AUTO_REBUILD."""
    return N().auto_decision(AUTO_REBUILD, state.doc_is_mine, bool(state.undoing or state.after_undo),
                             digest, done=state.done or (), failed=state.failed,
                             recent=state.recent or (), now=now)


# ------------------------------------------------------- the assembly snapshot

@dataclass
class AssemblySnapshot:
    """What numbering needs from a design (ARCHITECTURE 5.4), as plain data.

    tags: [TagDef.to_dict()], one per component that holds a tag;
    occurrences: [{"path", "component", "visible", "linked", "world" (16
    numbers or None), "stamp" ({"uid", "born", "home"} or None)}], every
    copy, hidden ones included; overrides: {instance name: id} typed by
    hand; inherited: [OverrideRecord.to_dict()] ids from inside linked
    designs; ledger: Ledger.to_dict() or None; state: the IDs node's state
    (node_state) or None; root: the root component's name."""
    design_units: str = "mm"
    tags: List[dict] = field(default_factory=list)
    occurrences: List[dict] = field(default_factory=list)
    overrides: Dict[str, int] = field(default_factory=dict)
    inherited: List[dict] = field(default_factory=list)
    ledger: Optional[dict] = None
    state: Optional[dict] = None
    root: str = ""
    warnings: List[str] = field(default_factory=list)
    schema: str = SNAPSHOT_SCHEMA

    def to_dict(self) -> dict:
        return {"schema": self.schema, "design_units": self.design_units, "tags": list(self.tags),
                "occurrences": list(self.occurrences), "overrides": dict(self.overrides),
                "inherited": list(self.inherited), "ledger": self.ledger, "state": self.state,
                "root": self.root, "warnings": list(self.warnings)}

    @classmethod
    def from_dict(cls, d: dict) -> "AssemblySnapshot":
        if (d or {}).get("schema", SNAPSHOT_SCHEMA) != SNAPSHOT_SCHEMA:
            raise ValueError(f"unknown snapshot schema {d.get('schema')!r}; "
                             f"this reads {SNAPSHOT_SCHEMA}")
        keys = ("design_units", "tags", "occurrences", "overrides", "inherited", "ledger",
                "state", "root", "warnings")
        return cls(**{k: d[k] for k in keys if k in d})


def _stamp_info(snap: AssemblySnapshot) -> dict:
    """read_stamps' "info" from the snapshot's occurrences: the native key
    '<owner label>/<occurrence name>', inside a linked design or not, the
    stamp."""
    linked = {o["path"]: bool(o.get("linked")) for o in snap.occurrences}
    comp = {o["path"]: o.get("component", "") for o in snap.occurrences}
    info = {}
    for o in snap.occurrences:
        path = o["path"]
        parts = M().split_path(path)
        parent = M().join_path(parts[:-1])
        inside = any(linked.get(M().join_path(parts[:k + 1]), False) for k in range(len(parts) - 1))
        owner = comp.get(parent, "") if parent else ""
        st = o.get("stamp") or {}
        info[path] = {"nk": f"{owner}/{parts[-1]}", "inside_linked": inside,
                      "uid": "" if inside else str(st.get("uid") or ""),
                      "born": (float(st["born"]) if st.get("born") is not None else None)
                      if not inside else None,
                      "home": "" if inside else str(st.get("home") or "")}
    return info


def collection(snap: AssemblySnapshot) -> dict:
    """The dict REF's collect_design returned, as plan_design reads it."""
    warns = list(snap.warnings)
    tags = [t for t in (M().TagDef.from_dict(d, warns.append) for d in snap.tags) if t is not None]
    occs = [M().OccurrenceRef(o["path"], o.get("component", ""), o.get("world"),
                              bool(o.get("visible", True)), bool(o.get("linked", False)))
            for o in snap.occurrences]
    inherited = [r for r in (M().OverrideRecord.from_dict(d, warns.append) for d in snap.inherited)
                 if r is not None]
    state = dict(snap.state or {})
    if snap.overrides:
        state = dict(state, overrides=dict(state.get("overrides") or {}, **snap.overrides))
    ledger = N().Ledger.from_any(snap.ledger) if snap.ledger else None
    return {"state": state, "recs": [], "tags": tags, "occs": occs, "inherited": inherited,
            "legacy_overrides": [], "warnings": warns, "root": snap.root,
            "stamps": stamps(_stamp_info(snap)), "ledger": ledger}


def plan_snapshot(snap: AssemblySnapshot, overrides=None, previous=None):
    """plan_design on a snapshot: what ArUco IDs' OK numbers it as."""
    return plan_design(collection(snap), overrides=overrides, previous=previous)
