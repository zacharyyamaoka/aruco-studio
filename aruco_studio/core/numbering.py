# Ported from REF CADExporter/bam_cad_core/aruco_numbering.py at c8216ff:
# copied verbatim, only the package-relative imports renamed.
"""ArUco IDs: one marker id per physical tag in the WHOLE design.

Zach, 2026-10-09: "My goal is not really thinking about this at all. At any
given level we can assume that all the ArUco markers basically need to be
unique, otherwise the camera could detect one in multiple places. We should
number them, and then if we want we can override it with anything we want,
or clear the autoset and return it to normal."

So there are no assembly levels any more. Every tag instance -- one ArUco
Extrude on one occurrence path, inside a linked design or not -- is a row of
ONE table, numbered so that no two VISIBLE instances print the same marker
(per dictionary family: DICT_4X4_50 is the first 50 markers of
DICT_4X4_1000, so the two share ids; 4x4 and 5x5 never collide). A row can
be overridden with any id; clearing the override returns it to auto.

Where the ids live (the Fusion side, ArucoMarkers/aruco_ids_feature.py): in
ONE "ArUco IDs" timeline feature in the design's ROOT component -- its named
values hold the overrides and the last auto assignment, its base-feature
bodies are the per-copy parts. The root is editable by definition, so an id
is never stored inside a linked (read-only) design (G0.6); `owner` says so on
every row.

Stability (G0.4, G0.7) is the rule that decides who keeps which id. Zach,
2026-10-10: "as we add to a design ... instead of redoing an ID we would do
another one for the new things ... We want to avoid having to like reprint
things." Every id a copy ever printed is in the design's ID LEDGER (`Ledger`:
a root attribute that outlives the ArUco IDs node -- see
docs/proposal_aruco_ids_stability.md). A copy is found in it by its stamp
chain, else by its place, else by its path (`match_ledger`). Then:

    1. tags in the ROOT component ("fixed": no occurrence to give a part of
       its own -- an ArUco Extrude edit renumbers those) keep what they print;
    2. overrides take exactly what they say (two overrides on one id are
       FLAGGED, never moved);
    3. every other visible tag keeps ITS ledger id when that is still free;
    4. then the id the node's last OK gave its path (`previous`: a node made
       before the ledger), when free and printed by no other copy;
    5. then the id its geometry prints today (`base`), when free and printed
       by no other copy, oldest copy first (`born`), then natural path order
       -- so an already-unique design changes nothing and the first of six
       copies keeps its id;
    6. the rest get the lowest block of their size (a board's ids are one
       contiguous block) that NO copy ever printed, inside their own
       dictionary: a deleted copy's id is not handed out again;
    7. only when the dictionary has no such block left: the block retired
       the longest ago (a warning names who printed it), then a hidden
       copy's -- or a refusal that names the tag when the dictionary is full.

Without a ledger (plan_ids(ledger=None)) steps 3 and 7 do nothing and step 6
is "the lowest free block": the numbering of 2026-10-09.

Hidden tags (their occurrence or an ancestor is off) are listed, not
numbered: nothing is printed there. A hidden copy the ledger knows keeps its
id reserved until it is shown again.

Standard library only (the decoding helpers load the dictionary tables
lazily, as markers.cell_boxes does).
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field, replace
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .dictionary import ARUCO_DICTS
from .markers import (KEY_SEP, UNIT_TO_M, OccurrenceRef, OverrideRecord, Resolution, TagDef,
                      TagSpec, resolve, slot_key, split_path)

SCHEMA = "bam_aruco_ids/1"

SOURCES = ("auto", "override", "model", "fixed", "hidden")
# where a row's id came from (IdsRow.basis): its own ledger id, the node's
# last OK (by path), what its geometry prints, a never-printed block, or --
# the dictionary out of never-printed blocks -- a retired / a hidden copy's
BASES = ("fixed", "override", "hidden", "ledger", "previous", "geometry", "new", "reused",
         "reused-hidden")


# ------------------------------------------------------------------ helpers

def family(dictionary: str) -> str:
    """Dictionaries whose ids are the same printed squares share a family:
    every DICT_<n>X<n>_* is a prefix of DICT_<n>X<n>_1000 (OpenCV's own
    tables), so 4X4_50 #3 and 4X4_1000 #3 are one marker. The original
    ArUco set and the AprilTag sets are families of their own."""
    m = re.match(r"DICT_(\d)X\1_", dictionary or "")
    return f"aruco{m.group(1)}x{m.group(1)}" if m else (dictionary or "?")


def capacity(dictionary: str) -> int:
    return int(ARUCO_DICTS.get(dictionary, 0))


def natural_key(s: str):
    """'Plate:10' after 'Plate:2' (a plain sort puts it first)."""
    return [(0, int(t)) if t.isdigit() else (1, t.lower())
            for t in re.split(r"(\d+)", s or "") if t != ""]


def instance_name(path: str, key: str) -> str:
    """One tag on one occurrence path -- the key every table uses (the same
    string as markers.TagInstance.name)."""
    return f"{path or '(root)'}{KEY_SEP}{key}"


def split_name(name: str) -> Tuple[str, str]:
    path, _sep, key = (name or "").rpartition(KEY_SEP)
    return ("" if path == "(root)" else path), key


def parse_id(text) -> Optional[int]:
    """What an ID field means: '' (or blanks) is auto -> None; an integer
    (with stray blanks or a leading '#') is that id; anything else raises
    ValueError with a message for the dialog. Never "Invalid expression"."""
    if text is None:
        return None
    if isinstance(text, bool):
        raise ValueError("an id is a whole number")
    if isinstance(text, int):
        return int(text)
    s = str(text).strip().lstrip("#").strip()
    if s == "":
        return None
    if not re.fullmatch(r"[+-]?\d+", s):
        raise ValueError(f"'{text}' is not an id: type a whole number, or clear "
                         "the field for auto")
    return int(s)


# --------------------------------------------------------------------- rows

@dataclass
class IdsRow:
    """One tag instance in the IDs table."""
    name: str                       # "<path>|<key>" (instance_name)
    path: str                       # occurrence path of the tag's component; "" = root
    key: str
    component: str
    layout: str
    dictionary: str
    count: int                      # markers in the target (a board's block)
    modelled: int                   # the id its ArUco Extrude encodes
    base: int                       # what its geometry prints without an IDs node
    final: int = 0                  # what it prints after OK
    override: Optional[int] = None  # the user's id, None = auto
    source: str = "auto"            # SOURCES
    hidden: bool = False            # not drawn here: listed, not numbered
    linked: bool = False            # inside a linked (read-only) design
    fixed: bool = False             # keeps what it prints: no part possible (a tag
                                    # in the root component, or `fixed` below)
    note: str = ""                  # why it is fixed, for the dialog
    previous: Optional[int] = None  # what the last OK gave it
    conflict: str = ""              # an override that collides (flagged, kept)
    error: str = ""                 # cannot be numbered (refusal)
    owner: str = ""                 # where the id is stored: "" = the design's root
    world: Optional[List[float]] = None   # tag frame (world, design units)
    uid: str = ""                   # stamp chain + '|' + key (copy_uid); '' = not stamped
    basis: str = ""                 # BASES: where `final` came from
    entry: Optional[int] = None     # the ledger entry this copy is (index), if any

    @property
    def at(self) -> Optional[List[float]]:
        """The tag's origin, world, design units (its place)."""
        w = self.world
        return [w[3], w[7], w[11]] if w and len(w) == 16 else None

    @property
    def family(self) -> str:
        return family(self.dictionary)

    @property
    def ids(self) -> List[int]:
        return [self.final + k for k in range(self.count)]

    @property
    def needs_part(self) -> bool:
        """Does this copy need a part of its own (its geometry prints
        something else)?"""
        return (not self.hidden and not self.error and not self.fixed
                and bool(self.path) and self.final != self.base)

    def label(self) -> str:
        ids = self.ids
        return f"#{ids[0]}" if len(ids) == 1 else f"#{ids[0]}-{ids[-1]}"

    def to_dict(self) -> dict:
        out = {"name": self.name, "path": self.path, "key": self.key,
               "component": self.component, "layout": self.layout,
               "dictionary": self.dictionary, "family": self.family,
               "count": self.count, "modelled": self.modelled, "base": self.base,
               "final": self.final, "ids": self.ids, "override": self.override,
               "source": self.source, "hidden": self.hidden, "linked": self.linked,
               "fixed": self.fixed, "previous": self.previous,
               "needs_part": self.needs_part, "owner": self.owner, "basis": self.basis}
        if self.uid:
            out["uid"] = self.uid
        if self.conflict:
            out["conflict"] = self.conflict
        if self.error:
            out["error"] = self.error
        return out


@dataclass
class IdsPlan:
    rows: List[IdsRow] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)       # refusals: OK must not build
    stale_overrides: Dict[str, int] = field(default_factory=dict)
    resolution: Optional[Resolution] = None
    ledger: Optional["Ledger"] = None                      # the ledger planned against
    matches: Dict[str, int] = field(default_factory=dict)  # row name -> its ledger entry

    @property
    def ok(self) -> bool:
        return not self.errors

    def row(self, name: str) -> Optional[IdsRow]:
        return next((r for r in self.rows if r.name == name), None)

    def visible(self) -> List[IdsRow]:
        return [r for r in self.rows if not r.hidden]

    def duplicates(self) -> Dict[str, List[str]]:
        """'<family>#<id>' -> visible rows printing it (only when 2+)."""
        groups: Dict[str, List[str]] = {}
        for r in self.visible():
            if r.error:
                continue
            for i in r.ids:
                groups.setdefault(f"{r.family}#{i}", []).append(r.name)
        return {k: v for k, v in groups.items() if len(v) > 1}

    def parts(self) -> Dict[str, List[IdsRow]]:
        """{occurrence path: the rows on it that need their own part}: one
        part per path (a component with two tags gets one part holding both)."""
        out: Dict[str, List[IdsRow]] = {}
        for r in self.rows:
            if r.needs_part:
                out.setdefault(r.path, []).append(r)
        return {p: out[p] for p in sorted(out, key=natural_key)}

    def retired(self) -> Dict[str, List[int]]:
        """{family: ids some copy printed before and none prints or keeps
        after this plan} -- a deleted copy's, a moved board's old block.
        They are not handed out again while the dictionary has others."""
        if self.ledger is None:
            return {}
        out: Dict[str, List[int]] = {}
        for fam, printed in self.ledger.printed.items():
            keep = set()
            for r in self.rows:
                if r.family != fam:
                    continue
                if not r.hidden and not r.error:
                    keep.update(r.ids)
                if r.entry is not None and (r.hidden or r.override is not None or r.error):
                    keep.update(self.ledger.entries[r.entry].block())
            ids = sorted(i for i in printed if i not in keep)
            if ids:
                out[fam] = ids
        return out

    def overrides(self) -> Dict[str, int]:
        """The overrides to store (hidden rows keep theirs)."""
        return {r.name: int(r.override) for r in self.rows if r.override is not None}

    def auto_state(self) -> Dict[str, int]:
        """What auto gave every visible, non-overridden row: the node keeps
        it, so the next OK changes nothing that does not have to change."""
        return {r.name: int(r.final) for r in self.rows
                if not r.hidden and not r.error and r.source in ("auto", "model")
                and r.override is None and not r.fixed}

    def export_records(self) -> List[OverrideRecord]:
        """The plan as root-level per-copy overrides: what CADExporter's
        payload["aruco"] carries, so markers.resolve() -- and every reader
        downstream of it (aruco.json, the URDF, the print sheet) -- reads the
        same ids the parts print. Every visible copy whose id is not what
        its geometry prints without the node."""
        recs: Dict[str, OverrideRecord] = {}
        for r in self.rows:
            if r.hidden or r.error or r.fixed or not r.path or r.final == r.base:
                continue
            parts = split_path(r.path)
            rec = recs.setdefault(parts[0], OverrideRecord("", parts[0], {}))
            rec.values[slot_key(parts[1:], r.key)] = {"marker_id": int(r.final)}
        return [recs[k] for k in sorted(recs, key=natural_key)]

    def summary(self) -> dict:
        vis = self.visible()
        return {"tags": len(self.rows), "numbered": len([r for r in vis if not r.error]),
                "hidden": len(self.rows) - len(vis),
                "linked": len([r for r in self.rows if r.linked]),
                "overrides": len([r for r in self.rows if r.override is not None]),
                "renumbered": len([r for r in self.rows if r.needs_part]),
                "parts": len(self.parts()), "duplicates": len(self.duplicates()),
                "conflicts": len([r for r in self.rows if r.conflict]),
                "errors": len(self.errors),
                "kept": len([r for r in vis if r.basis in ("ledger", "previous")]),
                "new": len([r for r in vis if r.basis == "new"]),
                "reused": len([r for r in vis if r.basis.startswith("reused")])}

    def to_dict(self) -> dict:
        out = {"schema": SCHEMA, "rows": [r.to_dict() for r in self.rows],
               "warnings": list(self.warnings), "errors": list(self.errors),
               "duplicates": self.duplicates(), "summary": self.summary(),
               "stale_overrides": dict(self.stale_overrides)}
        if self.ledger is not None:
            out["ledger"] = self.ledger.summary()
        return out


# -------------------------------------------------------------- the ledger
#
# docs/proposal_aruco_ids_stability.md. The ledger is the design's memory of
# every copy ArUco IDs numbered and of every id it ever printed. The Fusion
# side keeps it in ONE root-component attribute, so it outlives the IDs node
# (deleted, re-run), and stamps each occurrence on a tag's path with a random
# id (an attribute on the native occurrence; inside a linked design, which
# cannot be written, the occurrence's name stands in). A copy is then known
# by three things that rarely change together:
#
#     its stamp chain   survives a rename, a reorder, ':3' becoming ':2',
#                       a move, a linked design's refresh
#     its place         (the tag's origin, within 0.5 mm) survives a rename,
#                       a re-parent, a replaced linked design, a tag deleted
#                       and made again, a copy deleted and put back
#     its path          the 2026-10-09 key (a ledger from before the stamps)

LEDGER_SCHEMA = "bam_aruco_ids_ledger/1"
LEDGER_STATES = ("active", "hidden", "gone")
PLACE_TOL_M = 0.0005           # a copy this close to where a ledger copy was is that copy
ROOT_CHAIN = "(root)"


def chain_key(segments) -> Optional[str]:
    """An occurrence path's stable name: its segments joined, each '#<stamp>'
    (an occurrence we stamped) or '=<name>' (inside a linked design). None
    while a segment that can be stamped is not stamped yet."""
    segs = list(segments)
    if any(not s for s in segs):
        return None
    return "/".join(segs) if segs else ROOT_CHAIN


def copy_uid(path: str, key: str, chains: Optional[Dict[str, Optional[str]]]) -> str:
    """A tag copy's stable id: its path's chain + '|' + the tag key ('' when
    the chain is not known). A tag in the root component is unique by key."""
    if not path:
        return f"{ROOT_CHAIN}{KEY_SEP}{key}"
    c = (chains or {}).get(path)
    return f"{c}{KEY_SEP}{key}" if c else ""


@dataclass
class LedgerEntry:
    """One copy the ledger knows: what it is known by, and its id."""
    uid: str = ""                     # copy_uid ('' = known by place / path only)
    name: str = ""                    # its instance name when last seen
    family: str = ""
    count: int = 1                    # its block's size
    id: Optional[int] = None          # its AUTO id (None: only ever overridden)
    state: str = "active"             # active / hidden / gone (deleted)
    at: Optional[List[float]] = None  # the tag's origin when last seen (world, design units)
    born: int = 0                     # the ledger OK that first numbered it
    seen: int = 0                     # the last ledger OK that saw it

    def block(self) -> List[int]:
        return [] if self.id is None else [self.id + k for k in range(max(1, self.count))]

    def to_dict(self) -> dict:
        out = {"uid": self.uid, "name": self.name, "family": self.family, "count": self.count,
               "id": self.id, "state": self.state, "born": self.born, "seen": self.seen}
        if self.at is not None:
            out["at"] = [round(float(v), 6) for v in self.at]
        return out

    @classmethod
    def from_dict(cls, d) -> Optional["LedgerEntry"]:
        if not isinstance(d, dict):
            return None
        try:
            i, at = d.get("id"), d.get("at")
            e = cls(uid=str(d.get("uid") or ""), name=str(d.get("name") or ""),
                    family=str(d.get("family") or ""), count=max(1, int(d.get("count") or 1)),
                    id=None if i is None or isinstance(i, bool) else int(i),
                    state=d.get("state") if d.get("state") in LEDGER_STATES else "active",
                    at=[float(v) for v in at] if isinstance(at, list) and len(at) == 3 else None,
                    born=int(d.get("born") or 0), seen=int(d.get("seen") or 0))
        except (TypeError, ValueError):
            return None
        return e if e.family and (e.uid or e.name) else None


@dataclass
class Ledger:
    """Every copy ArUco IDs numbered in this design, and every id it ever
    printed: printed[family][id] = (the ledger OK that last printed it, by
    whom)."""
    seq: int = 0
    entries: List[LedgerEntry] = field(default_factory=list)
    printed: Dict[str, Dict[int, Tuple[int, str]]] = field(default_factory=dict)
    updated: str = ""

    def mark_printed(self, fam: str, ids: Iterable[int], seq: int, by: str) -> None:
        p = self.printed.setdefault(fam, {})
        for i in ids:
            p[int(i)] = (int(seq), str(by))

    def held(self, fam: str) -> Dict[int, str]:
        """id -> the copy (active or hidden) whose auto id it is, or which
        printed it at its last OK (an override's id)."""
        out: Dict[int, str] = {}
        live = {}
        for e in self.entries:
            if e.family == fam and e.state != "gone":
                for i in e.block():
                    out.setdefault(i, e.name)
                if e.state == "active":
                    live[e.name] = e.seen
        for i, (s, by) in self.printed.get(fam, {}).items():
            if by in live and live[by] == s:
                out.setdefault(i, by)
        return out

    def retired(self, fam: str) -> List[int]:
        """Ids printed once and no copy's any more: never handed out again
        while the dictionary has others."""
        held = self.held(fam)
        return sorted(i for i in self.printed.get(fam, {}) if i not in held)

    def summary(self) -> dict:
        fams = sorted(set(self.printed) | {e.family for e in self.entries})
        return {"seq": self.seq, "updated": self.updated,
                "copies": {s: len([e for e in self.entries if e.state == s]) for s in LEDGER_STATES},
                "printed": {f: len(self.printed.get(f, {})) for f in fams},
                "highest": {f: max(self.printed[f]) for f in fams if self.printed.get(f)},
                "retired": {f: self.retired(f) for f in fams if self.retired(f)}}

    def to_dict(self) -> dict:
        return {"schema": LEDGER_SCHEMA, "seq": self.seq, "updated": self.updated,
                "entries": [e.to_dict() for e in self.entries],
                "printed": {f: {str(i): [s, by] for i, (s, by) in sorted(p.items())}
                            for f, p in sorted(self.printed.items())}}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_any(cls, data) -> "Ledger":
        """A stored ledger back (tolerant: an empty ledger for nothing or
        anything unreadable; unreadable entries dropped)."""
        if isinstance(data, Ledger):
            return data
        if isinstance(data, (str, bytes)):
            try:
                data = json.loads(data)
            except (TypeError, ValueError):
                data = None
        if not isinstance(data, dict):
            return cls()
        led = cls(updated=str(data.get("updated") or ""))
        try:
            led.seq = max(0, int(data.get("seq") or 0))
        except (TypeError, ValueError):
            led.seq = 0
        for d in data.get("entries") or []:
            e = LedgerEntry.from_dict(d)
            if e is not None:
                led.entries.append(e)
        pr = data.get("printed")
        if isinstance(pr, dict):
            for fam, ids in pr.items():
                if not isinstance(ids, dict):
                    continue
                for i, v in ids.items():
                    try:
                        s, by = (v[0], v[1]) if isinstance(v, (list, tuple)) else (v, "")
                        led.printed.setdefault(str(fam), {})[int(i)] = (int(s), str(by))
                    except (TypeError, ValueError, IndexError):
                        continue
        return led


def match_ledger(rows: Sequence["IdsRow"], ledger: Optional[Ledger],
                 tol: float) -> Dict[str, int]:
    """{row name: index of the ledger entry that copy is}. Each entry is
    taken at most once and only within the row's family. Passes, strongest
    first:

        1. the same stamp chain (uid); two rows with one uid (a pasted copy
           carries its original's stamp): the one at the entry's path wins
        2. the same path AND the same place (within `tol`)
        3. the same place, same block size: renamed, re-parented, made again
        4. the same path -- only for an entry without a stamp (a ledger from
           a node of 2026-10-09): a STAMPED entry whose copy is gone must
           not be found again by a new copy that Fusion gave the old name
    """
    if ledger is None or not ledger.entries:
        return {}
    ents = ledger.entries
    left = set(range(len(ents)))
    out: Dict[str, int] = {}
    rows = sorted(rows, key=lambda r: natural_key(r.name))

    def near(e, r) -> bool:
        a, b = e.at, r.at
        return a is not None and b is not None and math.dist(a, b) <= tol

    def dist(e, r) -> float:
        a, b = e.at, r.at
        return math.dist(a, b) if a is not None and b is not None else 9e99

    def rank(i, r):
        e = ents[i]
        return (e.name != r.name, e.state == "gone", -e.seen, i)

    passes = (
        (lambda e, r: bool(r.uid) and e.uid == r.uid, rank),
        (lambda e, r: e.name == r.name and near(e, r), rank),
        (lambda e, r: near(e, r) and e.count == r.count, lambda i, r: (dist(ents[i], r),) + rank(i, r)),
        (lambda e, r: e.name == r.name and not e.uid, rank),
    )
    for k, (ok, key) in enumerate(passes):
        order = rows
        if k == 0:
            # the row at an entry's own path goes first for that uid
            home = {(ents[i].uid, ents[i].name) for i in left}
            order = sorted(rows, key=lambda r: ((r.uid, r.name) not in home, natural_key(r.name)))
        for r in order:
            if r.name in out:
                continue
            cands = [i for i in left if ents[i].family == r.family and ok(ents[i], r)]
            if not cands:
                continue
            i = min(cands, key=lambda i, r=r: key(i, r))
            out[r.name] = i
            left.discard(i)
    return out


def ledger_after(plan: "IdsPlan", chains: Optional[Dict[str, Optional[str]]] = None,
                 when: str = "") -> Ledger:
    """The ledger after `plan` is built (a new object; plan.ledger is not
    changed). `chains`: the paths' stamp chains AFTER the OK stamped what it
    had to (copies first seen now get their uid here). Every visible copy's
    ids are marked printed; a known copy keeps its entry (its new path, uid,
    place); a hidden one stays reserved; a copy that is gone is retired --
    its ids stay printed."""
    old = plan.ledger or Ledger()
    new = Ledger(seq=old.seq + 1, entries=[replace(e) for e in old.entries],
                 printed={f: dict(p) for f, p in old.printed.items()}, updated=when)
    s = new.seq
    used = set()
    for r in plan.rows:
        i = plan.matches.get(r.name)
        e = new.entries[i] if i is not None else None
        uid = (copy_uid(r.path, r.key, chains) if chains is not None else "") or r.uid \
            or (e.uid if e is not None else "")
        if e is not None:
            used.add(i)
        if r.error:
            if e is not None:
                e.seen = s
            continue
        if r.hidden:
            if e is not None:
                e.uid, e.name, e.at, e.state, e.seen = uid, r.name, r.at, "hidden", s
            continue
        auto_id = int(r.final) if r.source in ("auto", "model", "fixed") else None
        if e is None:
            e = LedgerEntry(uid=uid, name=r.name, family=r.family, count=r.count, id=auto_id,
                            born=s)
            new.entries.append(e)
        elif auto_id is not None:
            e.id, e.count = auto_id, r.count
        # an override leaves the copy's auto id where it was: clearing the
        # override gives it back
        e.uid, e.name, e.family, e.at, e.state, e.seen = uid, r.name, r.family, r.at, "active", s
        new.mark_printed(r.family, r.ids, s, r.name)
    printing = {}                      # family -> ids visible copies print now
    for r in plan.rows:
        if not r.hidden and not r.error:
            printing.setdefault(r.family, set()).update(r.ids)
    for i, e in enumerate(new.entries):
        if i < len(old.entries) and i not in used:
            e.state = "gone"
        if e.state != "active" and any(k in printing.get(e.family, ()) for k in e.block()):
            e.id = None                # its id went to another copy (a full dictionary)
    return new


def seed_ledger(state, rows: Sequence["IdsRow"] = ()) -> Ledger:
    """A ledger from a node made before the ledger existed (its stored
    "final", "auto", "overrides"): every id it printed is printed, every
    copy it numbered is an entry known by its path (and its place, when the
    copy is still there). `rows`: the design's rows now (families, sizes,
    places); a copy that is gone takes its family from the node's
    "families" or its parts' records, else it is left out."""
    st = read_state(state)
    led = Ledger()
    by = {r.name: r for r in rows}
    fams = {}
    for name, fc in (st.get("families") or {}).items():
        if isinstance(fc, (list, tuple)) and len(fc) == 2:
            fams[str(name)] = (str(fc[0]), int(fc[1]))
    for part in st.get("parts") or []:
        for t in (part or {}).get("tags") or []:
            try:
                sp = TagSpec.from_dict(dict((t.get("rec") or {}).get("spec") or {}),
                                       lambda m: None, "tag")
            except Exception:                      # noqa: BLE001
                sp = None
            if sp is not None and t.get("name"):
                fams.setdefault(str(t["name"]), (family(sp.dictionary), int(sp.marker_count)))

    def comp_key(name):
        """('Tag', 'top') for 'Box:1+Tag:3|top': the copy's component and tag key."""
        path, key = split_name(name)
        last = (split_path(path) or [""])[-1]
        return last.rsplit(":", 1)[0], key
    # a vanished copy of a tag that has other copies: that tag's family
    by_ck = {}
    for r in rows:
        by_ck.setdefault(comp_key(r.name), (r.family, r.count))
    for name, fc in fams.items():
        by_ck.setdefault(comp_key(name), fc)
    for name, fid in sorted((st.get("final") or {}).items(), key=lambda kv: natural_key(kv[0])):
        r = by.get(name)
        fc = (r.family, r.count) if r is not None else (fams.get(name) or by_ck.get(comp_key(name)))
        if not fc:
            continue
        fam, cnt = fc
        auto = (st.get("auto") or {}).get(name)
        if auto is None and name not in (st.get("overrides") or {}):
            auto = fid
        led.entries.append(LedgerEntry(uid="", name=name, family=fam, count=cnt, id=auto,
                                       state="gone" if r is None else
                                       ("hidden" if r.hidden else "active"),
                                       at=r.at if r is not None else None))
        led.mark_printed(fam, range(int(fid), int(fid) + cnt), 0, name)
    return led


def stamp_losers(items: Iterable[Tuple[str, str, str]]) -> set:
    """Native occurrences that must get a NEW stamp: (native key, its stamp,
    the native key recorded when it was stamped) -- several natives with one
    stamp (a copied-and-pasted occurrence carries its original's) keep it
    only on the one still where it was stamped, else on the first in
    natural order."""
    by: Dict[str, Dict[str, str]] = {}
    for nk, uid, home in items:
        if uid:
            by.setdefault(uid, {}).setdefault(nk, home)
    out = set()
    for uid, nks in by.items():
        if len(nks) < 2:
            continue
        keys = sorted(nks, key=natural_key)
        win = next((k for k in keys if nks[k] == k), keys[0])
        out |= set(keys) - {win}
    return out


# ------------------------------------------------------------------ planning

def _visible_map(occurrences: Sequence[OccurrenceRef]) -> Dict[str, bool]:
    """path -> drawn. An occurrence is drawn only when it and every ancestor
    are (Fusion's isVisible already is that; a caller with raw light bulbs
    gets the same answer)."""
    own = {o.path: bool(o.visible) for o in occurrences}
    out = {}
    for path in own:
        parts = split_path(path)
        out[path] = all(own.get("+".join(parts[:k + 1]), True) for k in range(len(parts)))
    return out


def _linked_map(occurrences: Sequence[OccurrenceRef]) -> Dict[str, bool]:
    own = {o.path: bool(getattr(o, "linked", False)) for o in occurrences}
    out = {}
    for path in own:
        parts = split_path(path)
        out[path] = any(own.get("+".join(parts[:k + 1]), False) for k in range(len(parts)))
    return out


def plan_ids(tags: Iterable[TagDef], occurrences: Sequence[OccurrenceRef],
             overrides: Optional[Dict[str, int]] = None,
             previous: Optional[Dict[str, int]] = None,
             inherited: Iterable[OverrideRecord] = (),
             root_component: str = "", design_units: str = "cm",
             fixed: Optional[Dict[str, str]] = None,
             ledger: Optional[Ledger] = None,
             chains: Optional[Dict[str, Optional[str]]] = None,
             born: Optional[Dict[str, float]] = None) -> IdsPlan:
    """Number every tag instance of the design. Pure.

    tags          every modelled tag (TagDef), linked designs included
    occurrences   the whole occurrence tree (root context), with visibility
                  as the USER set it (the IDs node's own hiding undone) and
                  `linked` for what sits in an externally referenced design
    overrides     {instance name: first id} -- the user's
    previous      {instance name: first id} -- what the last OK gave (auto)
    inherited     per-copy overrides that are part of the geometry already
                  and cannot be changed here (old ArUco IDs records inside a
                  linked design): they set what a copy prints without us
    fixed         {instance name: why} -- copies that must keep what they
                  print (no part can be built for them, e.g. a tag in a
                  linked design whose record lags its geometry); the others
                  go around them, like around a root-component tag
    ledger        the design's id ledger (None: the 2026-10-09 numbering)
    chains        {occurrence path: its stamp chain (chain_key)} -- how the
                  ledger knows a copy that was renamed or moved
    born          {occurrence path: when its copy was first stamped} -- the
                  oldest copy first where ids are handed out
    """
    born = dict(born or {})
    fixed = dict(fixed or {})
    occs = list(occurrences)
    overrides = dict(overrides or {})
    previous = dict(previous or {})
    plan = IdsPlan()
    res = resolve(list(tags), list(inherited), occs, root_component, design_units)
    plan.resolution = res
    plan.warnings += res.warnings
    vis = _visible_map(occs)
    linked = _linked_map(occs)
    names = set()
    for inst in res.instances:
        name = instance_name(inst.path, inst.tag.key)
        names.add(name)
        spec = inst.spec
        row = IdsRow(name=name, path=inst.path, key=inst.tag.key,
                     component=inst.tag.component, layout=spec.layout,
                     dictionary=spec.dictionary, count=spec.marker_count,
                     modelled=int(inst.tag.spec.marker_id), base=int(spec.marker_id),
                     hidden=bool(inst.path) and not vis.get(inst.path, True),
                     linked=bool(inst.path) and linked.get(inst.path, False),
                     fixed=not inst.path or name in fixed, world=inst.world,
                     note=fixed.get(name, "") if inst.path else "a tag in the root component")
        row.uid = copy_uid(inst.path, inst.tag.key, chains)
        row.final = row.base
        if name in overrides:
            try:
                row.override = parse_id(overrides[name])
            except ValueError as exc:
                row.error = str(exc)
                plan.errors.append(f"{name}: {row.error}")
        if name in previous:
            try:
                row.previous = parse_id(previous[name])
            except ValueError:
                row.previous = None
        plan.rows.append(row)
    plan.rows.sort(key=lambda r: natural_key(r.name))
    for name in sorted(set(overrides) - names, key=natural_key):
        plan.stale_overrides[name] = overrides[name]
        plan.warnings.append(f"override {name} = {overrides[name]}: no such tag any more "
                             "(the copy was removed or renamed) -- dropped at OK")

    plan.ledger = ledger
    tol = PLACE_TOL_M / UNIT_TO_M.get(design_units, 0.01)
    plan.matches = match_ledger(plan.rows, ledger, tol)
    for r in plan.rows:
        r.entry = plan.matches.get(r.name)

    def entry_of(r: IdsRow) -> Optional[LedgerEntry]:
        return ledger.entries[r.entry] if (ledger is not None and r.entry is not None) else None

    by_family: Dict[str, List[IdsRow]] = {}
    by_all: Dict[str, List[IdsRow]] = {}
    for r in plan.rows:
        by_all.setdefault(r.family, []).append(r)
        if r.hidden:
            r.source = "hidden"
            r.basis = "hidden"
            r.final = r.base
            continue
        by_family.setdefault(r.family, []).append(r)

    for fam in sorted(by_family):
        rows = by_family[fam]
        claims: Dict[int, str] = {}

        def free(start: int, r: IdsRow) -> bool:
            cap = capacity(r.dictionary)
            return (start >= 0 and start + r.count <= cap
                    and all(start + k not in claims for k in range(r.count)))

        def claim(start: int, r: IdsRow) -> List[str]:
            hit = sorted({claims[start + k] for k in range(r.count) if start + k in claims},
                         key=natural_key)
            for k in range(r.count):
                claims.setdefault(start + k, r.name)
            return hit

        def in_range(start: int, r: IdsRow) -> bool:
            return start >= 0 and start + r.count <= capacity(r.dictionary)

        # 1. root-component tags: what they print
        for r in rows:
            if not r.fixed or r.error:
                continue
            r.final, r.source = r.base, "fixed"
            if r.override is not None and r.override != r.base:
                r.conflict = (f"cannot be renumbered here ({r.note or 'no part possible'}; "
                              f"it prints {r.label()})")
                plan.warnings.append(f"{r.name}: {r.conflict}")
            hit = claim(r.final, r)
            if hit:
                r.conflict = (r.conflict or f"prints the same marker as {', '.join(hit)} "
                              "(both in the root component: edit one ArUco Extrude)")
                plan.warnings.append(f"{r.name}: {r.conflict}")
        # 2. overrides: exactly what they say; collisions flagged, never moved
        for r in rows:
            if r.fixed or r.error or r.override is None:
                continue
            if not in_range(r.override, r):
                cap = capacity(r.dictionary)
                what = (f"id {r.override}" if r.count == 1
                        else f"ids {r.override}..{r.override + r.count - 1}")
                r.error = f"{what} not in {r.dictionary} (0..{cap - 1})"
                r.final = r.base
                plan.errors.append(f"{r.name}: {r.error}")
                continue
            r.final, r.source = r.override, "override"
            hit = claim(r.final, r)
            if hit:
                r.conflict = f"prints the same marker as {', '.join(hit)}"
                plan.warnings.append(f"{r.name} = {r.label()}: {r.conflict} (your override "
                                     "is kept; change one of them)")
                for other in rows:
                    if other.name in hit and not other.conflict:
                        other.conflict = f"prints the same marker as {r.name}"
        for r in rows:
            if r.fixed and not r.error:
                r.basis = "fixed"
            elif r.source == "override":
                r.basis = "override"
        auto = [r for r in rows if not r.fixed and not r.error and r.override is None]
        # every id a copy ever printed (the ledger): not handed to ANOTHER copy
        printed = ledger.printed.get(fam, {}) if ledger is not None else {}

        def mine(r: IdsRow) -> set:
            e = entry_of(r)
            return set(e.block()) if e is not None else set()

        def unused(start: int, r: IdsRow) -> bool:
            m = mine(r)
            return all((start + k) in m or (start + k) not in printed for k in range(r.count))

        def take(r: IdsRow, start: int, basis: str) -> None:
            r.final, r.basis = start, basis
            claim(start, r)
            done.add(r.name)

        done = set()
        # 3. the copy's own ledger id, when still free
        for r in auto:
            e = entry_of(r)
            if e is not None and e.id is not None and free(e.id, r) and unused(e.id, r):
                take(r, e.id, "ledger")
        # oldest copy first (its stamp's birth), then natural path order
        order = sorted(auto, key=lambda r: (born.get(r.path) is None, born.get(r.path) or 0.0,
                                            natural_key(r.name)))
        # 4. what the node's last OK gave this path (a node from before the ledger)
        for r in order:
            if (r.name not in done and r.previous is not None and free(r.previous, r)
                    and unused(r.previous, r)):
                take(r, r.previous, "previous")
        # 5. what the geometry prints today, when nobody else ever printed it
        for r in order:
            if r.name not in done and free(r.base, r) and unused(r.base, r):
                take(r, r.base, "geometry")
        # the auto ids of hidden and overridden copies: reserved for them
        held: Dict[int, str] = {}
        for r in by_all.get(fam, []):
            e = entry_of(r)
            if e is not None and (r.hidden or r.override is not None or r.error):
                for i in e.block():
                    held.setdefault(i, r.name)
        # 6. the lowest block NO copy ever printed; 7. the dictionary out of
        # those: the block retired the longest ago, then a hidden copy's
        for r in order:
            if r.name in done:
                continue
            cap = capacity(r.dictionary)
            starts = range(0, max(0, cap - r.count + 1))
            start = next((s for s in starts if free(s, r) and unused(s, r)), None)
            basis = "new"
            if start is None:
                for basis, ok in (("reused", lambda s, r=r: not any(s + k in held
                                                                   for k in range(r.count))),
                                  ("reused-hidden", lambda s: True)):
                    cands = [s for s in starts if free(s, r) and ok(s)]
                    if cands:
                        start = min(cands, key=lambda s, r=r: (
                            max(printed.get(s + k, (-1, ""))[0] for k in range(r.count)), s))
                        break
            if start is None:
                r.error = (f"{r.dictionary} is full ({cap} ids): {r.name} cannot get "
                           f"{'an id' if r.count == 1 else f'a block of {r.count} ids'} of "
                           "its own -- use a bigger dictionary for this tag")
                r.final = r.base
                plan.errors.append(r.error)
                continue
            take(r, start, basis)
            if basis != "new":
                was = sorted({printed[i][1] for i in r.ids if i in printed and printed[i][1]},
                             key=natural_key)
                whose = (f"a hidden copy's ({', '.join(sorted({held[i] for i in r.ids if i in held}))})"
                         if basis == "reused-hidden" else "retired")
                plan.warnings.append(
                    f"{r.name}: {r.dictionary} has no never-used "
                    f"{'id' if r.count == 1 else f'block of {r.count}'} left -- it reuses "
                    f"{r.label()}, {whose}, last printed by {', '.join(was) or 'a deleted copy'}. "
                    "Make sure that part is not on the robot any more, or give this tag a "
                    "bigger dictionary (DICT_4X4_100 / _1000 keep every 4x4 id as it is).")
        for r in auto:
            if not r.error:
                r.source = "model" if r.final == r.modelled else "auto"
    return plan


def plan_stable(tags: Iterable[TagDef], occurrences: Sequence[OccurrenceRef],
                ledger: Optional[Ledger] = None, state: Optional[dict] = None,
                chains: Optional[Dict[str, Optional[str]]] = None,
                born: Optional[Dict[str, float]] = None, **kw) -> IdsPlan:
    """plan_ids against the design's ledger -- what ArUco IDs runs. A
    design with no ledger yet whose IDs node has a state (made before the
    ledger) gets one seeded from that state first, so the switch keeps every
    id. `kw`: plan_ids' other arguments."""
    tags, occs = list(tags), list(occurrences)
    if (ledger is None or not ledger.entries) and (state or {}).get("final"):
        rough = plan_ids(tags, occs, **kw)
        ledger = seed_ledger(state, rough.rows)
    return plan_ids(tags, occs, ledger=ledger if ledger is not None else Ledger(),
                    chains=chains, born=born, **kw)


# ------------------------------------------------------ the node's anchors

def dependency_copies(components: Iterable[str], occurrences: Sequence[OccurrenceRef],
                      hosts: Iterable[str]) -> Dict[str, str]:
    """{component: the copy the IDs node depends on for it}: ONE per
    component that has parts, on a visible copy that keeps its id (not a
    part host) when there is one, else the first host -- natural path order.

    Why (measured 2026-10-09): a copy the node depends on cannot be deleted
    (deleteMe returned True and left it; Fusion's Delete did nothing), and
    the renumbered copies are the ones a user adds and removes. The
    dependency only tells Fusion to recompute the parts when the part's
    geometry changes upstream, which any copy of it shows."""
    hosts = set(hosts)
    out: Dict[str, str] = {}
    vis = _visible_map(list(occurrences))
    for comp in sorted(set(components)):
        paths = sorted((o.path for o in occurrences if o.component == comp), key=natural_key)
        keep = [p for p in paths if p not in hosts and vis.get(p, True)]
        mine = [p for p in paths if p in hosts]
        if keep or mine:
            out[comp] = (keep or mine)[0]
    return out


# --------------------------------------------------------- the node's state

def node_state(plan: IdsPlan, extra: Optional[dict] = None) -> dict:
    """What the ArUco IDs node stores (its named value "ids", JSON): the
    overrides, the auto assignment, and -- for the readers that have no
    planner -- every visible copy's final id."""
    out = {"schema": SCHEMA, "overrides": plan.overrides(), "auto": plan.auto_state(),
           "final": {r.name: r.final for r in plan.rows if not r.hidden and not r.error},
           # what a ledger seeded from this node needs for a copy that is gone
           "families": {r.name: [r.family, r.count] for r in plan.rows
                        if not r.hidden and not r.error}}
    out.update(extra or {})
    return out


def read_state(text_or_dict) -> dict:
    """The node's state back (tolerant: {} for nothing / unreadable)."""
    import json
    if not text_or_dict:
        return {}
    if isinstance(text_or_dict, dict):
        data = text_or_dict
    else:
        try:
            data = json.loads(text_or_dict)
        except (TypeError, ValueError):
            return {}
    if not isinstance(data, dict):
        return {}
    for k in ("overrides", "auto", "final"):
        v = data.get(k)
        data[k] = {str(n): int(i) for n, i in v.items()
                   if isinstance(i, int) and not isinstance(i, bool)} if isinstance(v, dict) else {}
    return data


def state_records(state: dict, base: Optional[Dict[str, int]] = None) -> List[OverrideRecord]:
    """A stored state's final ids as root-level per-copy overrides (what an
    exporter without the planner reads). `base`: {name: id the geometry
    prints without the node}; rows equal to it are left out."""
    recs: Dict[str, OverrideRecord] = {}
    for name, fid in sorted((state or {}).get("final", {}).items(),
                            key=lambda kv: natural_key(kv[0])):
        path, key = split_name(name)
        if not path:
            continue
        if base is not None and base.get(name) == fid:
            continue
        parts = split_path(path)
        rec = recs.setdefault(parts[0], OverrideRecord("", parts[0], {}))
        rec.values[slot_key(parts[1:], key)] = {"marker_id": int(fid)}
    return [recs[k] for k in sorted(recs, key=natural_key)]


# ------------------------------------------------- reading built geometry

def module_samples(spec: TagSpec) -> List[Tuple[int, int, int, float, float]]:
    """Every module centre of every marker in a target, in the TAG frame
    (centre of the pattern, +y up, metres): (marker id, row, col, x, y),
    row 0 = the marker's top row, border included."""
    from . import markers
    n = spec.bits + 2
    mod = spec.marker_length_m / n
    out = []
    if spec.layout == "single":
        corners = {int(spec.marker_id): [(-spec.marker_length_m / 2.0, spec.marker_length_m / 2.0)]}
    else:
        from . import board as aruco_board
        corners = aruco_board.marker_corners_m(markers.board_spec(spec))
    for mid, pts in corners.items():
        x0, y0 = pts[0]                                  # top-left, y up
        for r in range(n):
            for c in range(n):
                out.append((int(mid), r, c, x0 + (c + 0.5) * mod, y0 - (r + 0.5) * mod))
    return out


def expected_grid(dictionary: str, marker_id: int) -> List[List[int]]:
    from . import dictionary as aruco_dict
    return aruco_dict.marker_grid(dictionary, int(marker_id))


def _family_table(dictionary: str) -> str:
    """The largest dictionary of a family (every id of the family is in it)."""
    m = re.match(r"DICT_(\d)X\1_", dictionary or "")
    if m:
        return f"DICT_{m.group(1)}X{m.group(1)}_1000"
    return dictionary


def identify(dictionary: str, grid: List[List[int]]) -> Optional[int]:
    """The id of a sampled (n+2) x (n+2) grid (1 = black, row 0 = top, as
    printed in the tag frame -- no rotation tried) in the dictionary's
    FAMILY, or None. What a camera would read, minus the camera."""
    from . import dictionary as aruco_dict
    table = _family_table(dictionary)
    cap = capacity(table) or capacity(dictionary)
    for mid in range(cap):
        try:
            if aruco_dict.marker_grid(table, mid) == grid:
                return mid
        except ValueError:
            break
    return None


def decode(spec: TagSpec, is_black) -> Dict[int, Optional[int]]:
    """{expected marker id: the id the geometry prints there (or None)}:
    `is_black(x_m, y_m)` samples the built pattern in the tag frame. Each
    marker of the target is read where the spec puts it."""
    n = spec.bits + 2
    grids: Dict[int, List[List[int]]] = {}
    for mid, r, c, x, y in module_samples(spec):
        g = grids.setdefault(mid, [[0] * n for _ in range(n)])
        g[r][c] = 1 if is_black(x, y) else 0
    return {mid: identify(spec.dictionary, g) for mid, g in grids.items()}


# ------------------------------------------- the node's inputs (staleness)
#
# Zach, 2026-10-13, on his rack: "After I edited the aruco markers and then
# rebuilt the top level, I don't like how this feature then errored.. why is
# it erroring? ideally it just rebuilds correctly." He had added a corner
# triangle to a black tag (its footprint grew one module); the node's compute
# compared its STORED records with the geometry, found "its tag moved or
# changed upstream (4.667 mm)" and stopped on an ERROR, waiting for OK.
#
# Now the node stores what its parts were built FROM (`inputs`: per template
# component, its tag records -- minus the entity tokens an edit renews -- and
# its bodies and sub-assembly as numbers), and compute compares that with
# the design as it is (`inputs_diff`), plus what OK would number now
# (`plan_drift`). Out of date is not an error: the Fusion side rebuilds the
# parts right after the recompute, as one undo step (aruco_ids_feature).
# These are the pure halves.

INPUTS_SCHEMA = 1
# a record's "fusion" fields that are entity tokens (renewed whenever the
# ArUco Extrude node or its Joint Origin is made again) or bookkeeping that
# says nothing about the tag's shape
VOLATILE_FUSION = ("custom_feature", "base_feature", "joint_origin", "combine", "made",
                   "live_error", "group_error", "joint_origin_error", "joint_origin_anchor",
                   "joint_origin_after_error", "pruned_joint_origins")
VOL_REL_TOL = 1e-6           # a body's volume: relative ...
VOL_ABS_TOL_CM3 = 1e-9       # ... and absolute (cm^3)
LEN_TOL_CM = 1e-6            # a bounding box corner, a transform's translation (cm)
ROT_TOL = 1e-7               # a transform's rotation terms


def _clean_record(rec: dict) -> dict:
    out = {k: v for k, v in rec.items() if not str(k).startswith("_")}
    fz = out.get("fusion")
    if isinstance(fz, dict):
        out["fusion"] = {k: v for k, v in fz.items()
                         if k not in VOLATILE_FUSION and not str(k).endswith("_token")}
    return out


def record_digest(records: Iterable[dict]) -> str:
    """A component's tag records as one short digest: what they SAY (spec,
    frame, mode, mark, label, body names), not the tokens an edit renews."""
    import hashlib
    clean = sorted((_clean_record(r) for r in records or () if isinstance(r, dict)),
                   key=lambda r: str(r.get("key")))
    text = json.dumps(clean, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def _rounded(v, nd: int):
    if isinstance(v, float):
        r = round(v, nd)
        return 0.0 if r == 0 else r             # -0.0 and 0.0 alike
    if isinstance(v, dict):
        return {k: _rounded(x, nd) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_rounded(x, nd) for x in v]
    return v


def record_digest_r(records: Iterable[dict], nd: int = 6) -> str:
    """record_digest with every number rounded to `nd` decimals (cm: 1e-6 is
    0.01 um): two records that say the same tag compare equal whichever way
    they were written -- the IDs node's own evaluation of a lagging tag
    (collect_design) and ArUco Extrude's refresh that writes it afterwards
    (2026-10-16 night: one plate change rebuilt the parts twice)."""
    import hashlib
    clean = sorted((_rounded(_clean_record(r), nd) for r in records or () if isinstance(r, dict)),
                   key=lambda r: str(r.get("key")))
    text = json.dumps(clean, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def records_same(x: Optional[dict], y: Optional[dict]) -> bool:
    """A template's tag records unchanged between the inputs a node was built
    from (`x`) and the design's now (`y`): the exact digest as before; or,
    rounded, the records as they were (`records_r`) or as the node EVALUATED
    them when it was built (`records_eval_r`: a record that lagged its
    ArUco Extrude node -- the refresh writing it later is no edit)."""
    x, y = x or {}, y or {}
    if x.get("records") == y.get("records"):
        return True
    now = y.get("records_r")
    return now is not None and now in {x.get("records_r"), x.get("records_eval_r")} - {None}


def _close(a, b, tol) -> bool:
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return a == b


def _vol_close(a, b) -> bool:
    if a is None or b is None:
        return True                    # not readable (then or now): no evidence of a change
    return abs(float(a) - float(b)) <= max(VOL_ABS_TOL_CM3, VOL_REL_TOL * max(abs(a), abs(b)))


def _seq_close(a, b, tol) -> bool:
    if a is None or b is None:
        return True                    # not readable: no evidence of a change
    return len(a) == len(b) and all(_close(x, y, tol) for x, y in zip(a, b))


def body_changes(old: Sequence[dict], new: Sequence[dict]) -> List[str]:
    """What changed between two lists of body signatures ({"name", "solid",
    "on", "volume" cm^3, "bbox" [6] cm, "faces"}) -> short phrases."""
    out: List[str] = []
    a = {b.get("name"): b for b in old or ()}
    b_ = {b.get("name"): b for b in new or ()}
    gone, made = sorted(set(a) - set(b_), key=str), sorted(set(b_) - set(a), key=str)
    if gone:
        out.append("bodies gone: " + ", ".join(map(str, gone[:4])))
    if made:
        out.append("new bodies: " + ", ".join(map(str, made[:4])))
    for name in sorted(set(a) & set(b_), key=str):
        x, y = a[name], b_[name]
        if bool(x.get("solid")) != bool(y.get("solid")) or bool(x.get("on")) != bool(y.get("on")):
            out.append(f"'{name}' shown / hidden or no longer solid")
        elif not _vol_close(x.get("volume"), y.get("volume")):
            out.append(f"'{name}' {_mm3(x.get('volume'))} -> {_mm3(y.get('volume'))} mm^3")
        elif not _seq_close(x.get("bbox"), y.get("bbox"), LEN_TOL_CM):
            out.append(f"'{name}' moved or resized")
        elif None not in (x.get("faces"), y.get("faces")) and x.get("faces") != y.get("faces"):
            out.append(f"'{name}' {x.get('faces')} -> {y.get('faces')} faces")
    return out


def _mm3(v) -> str:
    try:
        return f"{float(v) * 1000.0:.3f}"
    except (TypeError, ValueError):
        return "?"


def _xf_close(a, b) -> bool:
    if a is None or b is None:
        return True
    if len(a) != len(b):
        return False
    for i, (x, y) in enumerate(zip(a, b)):
        tol = LEN_TOL_CM if i in (3, 7, 11) else ROT_TOL
        if not _close(x, y, tol):
            return False
    return True


def inputs_diff(old: Optional[dict], new: Optional[dict]) -> List[str]:
    """Why parts built from inputs `old` no longer match the design's
    inputs `new` (both {"v", "components": {label: {"records", "bodies",
    "children"}}}): [] when they still do. -> short reasons, per template."""
    old_c = (old or {}).get("components") or {}
    new_c = (new or {}).get("components") or {}
    out: List[str] = []
    for label in sorted(set(old_c) | set(new_c), key=natural_key):
        name = label or "(root)"
        x, y = old_c.get(label), new_c.get(label)
        if x is None or y is None:
            out.append(f"'{name}': {'no longer' if y is None else 'now'} a template with parts")
            continue
        why: List[str] = []
        if not records_same(x, y):
            why.append("its tag was edited")
        why += body_changes(x.get("bodies") or [], y.get("bodies") or [])
        kx = {k.get("path"): k for k in x.get("children") or []}
        ky = {k.get("path"): k for k in y.get("children") or []}
        if set(kx) != set(ky):
            why.append("its sub-assembly changed")
        else:
            for p in sorted(kx, key=natural_key):
                if (bool(kx[p].get("on")) != bool(ky[p].get("on"))
                        or not _xf_close(kx[p].get("xf"), ky[p].get("xf"))
                        or body_changes(kx[p].get("bodies") or [], ky[p].get("bodies") or [])):
                    why.append(f"'{p}' in it changed")
                    break
        if why:
            out.append(f"'{name}': " + "; ".join(why[:3]))
    return out


def plan_drift(state: dict, plan: "IdsPlan") -> List[str]:
    """What OK would number differently now than the node did (a copy added,
    removed, shown or hidden; a template's id edited): [] when nothing."""
    state = state or {}
    want = {r.name: int(r.final) for r in plan.rows if not r.hidden and not r.error}
    have = {str(k): int(v) for k, v in (state.get("final") or {}).items()}
    out: List[str] = []
    added = sorted(set(want) - set(have), key=natural_key)
    gone = sorted(set(have) - set(want), key=natural_key)
    moved = sorted((n for n in set(want) & set(have) if want[n] != have[n]), key=natural_key)
    if added:
        out.append(f"{len(added)} tag copy(ies) to number: " + ", ".join(added[:3]))
    if gone:
        out.append(f"{len(gone)} numbered copy(ies) gone or hidden: " + ", ".join(gone[:3]))
    if moved:
        out.append(f"{len(moved)} id(s) to change: "
                   + ", ".join(f"{n} {have[n]} -> {want[n]}" for n in moved[:3]))
    hosts_want = set(plan.parts())
    hosts_have = {p.get("host") for p in state.get("parts") or [] if isinstance(p, dict)}
    if hosts_want != hosts_have and not (added or gone or moved):
        out.append("the copies that need a part of their own changed")
    return out


def inputs_digest(inputs: Optional[dict], plan_final: Optional[Dict[str, int]] = None) -> str:
    """One short digest of the design's inputs as compute saw them (and
    what OK would number): the node's automatic rebuild runs ONCE per
    digest -- a rebuild that leaves the node out of date for the same
    inputs is not tried again (aruco_ids_feature)."""
    import hashlib
    text = json.dumps({"inputs": inputs or {}, "final": plan_final or {}}, sort_keys=True,
                      default=str, separators=(",", ":"))
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


AUTO_MODES = ("all", "mine", "off")
AUTO_BURST = (3, 30.0)       # at most 3 automatic rebuilds per document in 30 s


def auto_decision(mode: str, doc_is_mine: bool, undoing: bool, digest: str,
                  done: Sequence[str] = (), failed: Optional[dict] = None,
                  recent: Sequence[float] = (), now: float = 0.0) -> Tuple[str, str]:
    """What compute does with an out-of-date node: ("schedule", "") -- the
    parts are rebuilt right after this recompute, one undo step; ("quiet",
    why) -- nothing now (the user is walking the undo history: undoing a
    rebuild must not bring it back); ("warn", why) -- a warning on the
    node that says what to do (never an error)."""
    if undoing:
        return "quiet", "undo / redo"
    if mode not in AUTO_MODES or mode == "off":
        return "warn", ""
    if mode == "mine" and not doc_is_mine:
        return "warn", ""
    if failed and failed.get("digest") == digest:
        return "warn", f"the automatic rebuild failed ({failed.get('error') or '?'})."
    if digest in set(done or ()):
        return "warn", "the automatic rebuild did not bring them up to date."
    n, window = AUTO_BURST
    if len([t for t in recent or () if now - float(t) <= window]) >= n:
        return "warn", f"they were rebuilt {n} times in {int(window)} s and are still out of date."
    return "schedule", ""
