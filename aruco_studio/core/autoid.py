"""Auto id for the marker features of ONE document (the online Studio's
CoreApi.assign_ids; aruco_studio/web_ids.py is its facade).

Zach, 2026-10-18: "Auto id -- with stable ids, so you rebuild consistently
... you just pass in something that doesn't change for that marker, and then
internally we hash it ... We don't want to have to worry about ensuring
unique IDs. By default the id if you are in an assembly should just
automatically start at a unique ID, and if you want to manually override
you can do that."

Every feature is an item {key, type, dictionary, count, first_id}: `key`
never changes for that marker, `count` is how many markers it prints (a
board's ids are one contiguous block), `first_id` None = driven (auto), a
number = typed. The ledger {key: first id} is every driven first id already
given out. Ids are unique per dictionary FAMILY, as core.numbering numbers a
Fusion design (`numbering.family`: DICT_4X4_50 is the first 50 markers of
DICT_4X4_1000, so the two share ids; 4x4 and 5x5 never collide).

    1. a driven item the ledger knows keeps its ledger id: printed ids never
       move (numbering's ledger rule). Only its own block no longer fitting
       (its dictionary or count changed) moves it, with a warning;
    2. typed ids are taken exactly as typed: two ranges that overlap (two
       typed, or a typed one over a ledger id) both keep their numbers and
       each gets an error that names the other (numbering's "two overrides
       on one id are FLAGGED, never moved");
    3. every other driven item, in sorted-key order, takes its PREFERRED
       first id -- sha256(dictionary, key) mapped into 0 .. capacity - count
       -- when that block is free, else the next free block forward,
       wrapping round. A typed item's old ledger id is held for it (clear
       the typed id and it comes back), as numbering holds an overridden
       copy's, and is handed out only when nothing else is free.

`reserved` (IdRequest.reserved, the Fusion adapter's N-6 ask): ids that are
never handed out -- markers already printed by an older tool. A list
reserves its ids in every family (id 3 reserved is 3 in DICT_4X4_* and in
DICT_5X5_*); a map {family: [id, ...]} (N-8) only in the families it names
-- numbering.family's names ("aruco4x4", "DICT_APRILTAG_36h11"), "4x4" short
for "aruco4x4"; an unknown family is a ValueError, never a silent no-op. A
driven item never takes one (a ledger id that now covers one moves, with a
warning); a typed id on one keeps its number and gets an error, as two typed
ranges that overlap do. Not covered: per-copy ids for the occurrences of one
component -- every item here is one feature with one block of ids.

WHY the ledger and not the hash keeps ids still: small dictionaries collide
often -- 10 keys hashed into DICT_4X4_50 share a preferred id 62 % of the
time (the birthday bound; 17 % in DICT_4X4_250) -- so which of two colliding
keys probes onward depends on who else is in the document, and a hash alone
would move an id when a feature is added. The hash only makes a FIRST build
reproducible with no ledger. What is guaranteed:

    * with the ledger the last call returned: adding or removing OTHER
      features never moves an existing id (a new feature, typed or driven,
      never displaces a ledger id; a removed one only frees ids);
    * with no ledger: the same set of items always gives the same ids,
      whatever order they arrive in (sorted keys, sha256 -- never Python's
      salted hash()).

Re-ID (IdRequest.mode / start / fresh, Zach, 2026-10-20: "we should be able
to have lots of the markers on a page and then re-id them"):

    * mode "hash" (the default) is everything above, unchanged;
    * mode "sequential" swaps rule 3's preferred id for a counter: the driven
      items, in REQUEST (document) order, each take the next free block of
      their count from the counter -- typed, ledger, held and reserved ids
      skipped -- and the counter moves past it. Each family has its own
      counter, all starting at `start` (default 0). Past the end of the
      dictionary the probe wraps round as rule 3's does, and a full
      dictionary is the same error;
    * fresh: the incoming ledger is ignored (no rule 1, nothing held), so
      every driven id is given out anew, in either mode, and the returned
      ledger replaces the old one. Typed ids still win; overlaps are flagged
      as in rule 2.

Standard library only (it runs in Pyodide).
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from . import dictionary as _D
from .autosize import CAPACITIES
from .numbering import family

TYPES = ("single", "grid", "charuco")
FIELD = "marker.first_id"           # the contract's Issue.field for every id issue


@dataclass
class Item:
    key: str
    type: str
    dictionary: str
    count: int
    first_id: Optional[int]         # typed; None = driven
    capacity: int = 0

    @property
    def family(self) -> str:
        return family(self.dictionary)


def _whole(v, what: str) -> int:
    if isinstance(v, bool) or not isinstance(v, int):
        raise ValueError(f"{what}: a whole number, got {v!r}")
    return v


def item_of(d) -> Item:
    """One request item, checked: an unknown type or dictionary, a count
    that is not a whole number >= 1 (a single prints 1) raise ValueError."""
    if not isinstance(d, dict):
        raise ValueError(f"an item is an object, got {d!r}")
    key = d.get("key")
    if not isinstance(key, str) or key == "":
        raise ValueError(f"item key: a non-empty string, got {key!r}")
    kind = d.get("type")
    if kind not in TYPES:
        raise ValueError(f"item {key!r}: type {kind!r} is not one of {', '.join(TYPES)}")
    info = _D.dictionary_info(d.get("dictionary"))
    count = _whole(d.get("count"), f"item {key!r} count")
    if count < 1 or (kind == "single" and count != 1):
        raise ValueError(f"item {key!r}: count {count} ({kind} prints "
                         f"{'1 marker' if kind == 'single' else '1 or more'})")
    first = d.get("first_id")
    if first is not None:
        first = _whole(first, f"item {key!r} first_id")
    return Item(key, kind, info["name"], count, first, int(info["capacity"]))


def preferred(key: str, dictionary: str, count: int, capacity: int) -> int:
    """The first id a driven item asks for: sha256 of its dictionary and
    key, mapped into 0 .. capacity - count (a board's whole block fits)."""
    span = capacity - count + 1
    if span <= 1:
        return 0
    h = hashlib.sha256(f"{dictionary}\n{key}".encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big") % span


def _label(first: int, count: int) -> str:
    return f"#{first}" if count == 1 else f"#{first}–{first + count - 1}"


def _issue(level: str, key: str, text: str) -> dict:
    return {"field": FIELD, "level": level, "text": text, "key": key}


def _bigger(it: Item, taken: Dict[int, str]) -> Optional[str]:
    """The smallest dictionary of the item's bit size, bigger than its own,
    that still has a free block of its count (its family's ids in use)."""
    m = re.fullmatch(r"DICT_(\d)X\1_\d+", it.dictionary)
    if not m:
        return None
    for cap in CAPACITIES:
        name = f"DICT_{m.group(1)}X{m.group(1)}_{cap}"
        if (cap > it.capacity and name in _D.ARUCO_DICTS
                and any(all(s + k not in taken for k in range(it.count))
                        for s in range(cap - it.count + 1))):
            return name
    return None


def reserved_of(reserved) -> List[int]:
    """The reserved ids, checked: whole numbers >= 0 (else ValueError), sorted."""
    out = set()
    for v in reserved or ():
        if _whole(v, "reserved id") < 0:
            raise ValueError(f"reserved id: 0 or more, got {v!r}")
        out.add(v)
    return sorted(out)


def families() -> List[str]:
    """Every dictionary family (numbering.family), sorted."""
    return sorted({family(d) for d in _D.DICTIONARY_NAMES})


def family_of_key(key) -> str:
    """A reserved map's key as its family: a numbering.family name, or
    "4x4" ("4X4") for "aruco4x4"; anything else raises ValueError."""
    known = families()
    if isinstance(key, str):
        if key in known:
            return key
        m = re.fullmatch(r"(\d)[xX]\1", key)
        if m and f"aruco{m.group(1)}x{m.group(1)}" in known:
            return f"aruco{m.group(1)}x{m.group(1)}"
    raise ValueError(f"reserved: family {key!r} is not one of {', '.join(known)} "
                     "(or 4x4 .. 7x7)")


def reserved_in(reserved) -> Dict[Optional[str], Set[int]]:
    """{family: its reserved ids} from a list (key None: every family) or a
    map {family: [id, ...]} (family_of_key); ids checked as reserved_of."""
    if isinstance(reserved, dict):
        out: Dict[Optional[str], Set[int]] = {}
        for k, ids in reserved.items():
            if not isinstance(ids, (list, tuple)):
                raise ValueError(f"reserved[{k!r}]: a list of ids, got {ids!r}")
            out.setdefault(family_of_key(k), set()).update(reserved_of(ids))
        return out
    return {None: set(reserved_of(reserved))}


MODES = ("hash", "sequential")


def assign(items, ledger: Optional[Dict[str, int]] = None, reserved=None,
           mode: str = "hash", start: int = 0, fresh: bool = False) -> dict:
    """{items: [{key, first_id, ids, driven}] in the request's order, ledger:
    the updated {key: first id}, warnings: [Issue with key]} (contract
    IdResult). An item that cannot get ids (out of its dictionary, or the
    dictionary is full) comes back with ids [] and an error. `reserved`:
    ids never handed out, a list in every family or a map per family (see
    the module's words). `mode` "hash" | "sequential", `start` (sequential's
    first id) and `fresh` (ignore the ledger): Re-ID, the module's words."""
    if mode not in MODES:
        raise ValueError(f"mode: {' or '.join(map(repr, MODES))}, got {mode!r}")
    if _whole(start, "start") < 0:
        raise ValueError(f"start: 0 or more, got {start!r}")
    if not isinstance(fresh, bool):
        raise ValueError(f"fresh: true or false, got {fresh!r}")
    sequential, origin = mode == "sequential", start      # `start` is reused below
    its = [item_of(d) for d in (items or [])]
    by_family = reserved_in(reserved)
    every = by_family.get(None, set())

    res_cache: Dict[str, Set[int]] = {}

    def res_of(fam: str) -> Set[int]:
        got = res_cache.get(fam)
        if got is None:
            got = res_cache[fam] = every | by_family.get(fam, set())
        return got
    seen = set()
    for it in its:
        if it.key in seen:
            raise ValueError(f"item key {it.key!r} appears twice: keys are unique")
        seen.add(it.key)
    # WHY: without `fresh`, sequential still honours the ledger -- ledgered
    # items keep their ids and only items the ledger does not know get
    # sequential numbers -- because printed ids never move unless asked
    # (rule 1). Renumbering what is already printed is the explicit Re-ID:
    # `fresh`, which drops the ledger (Zach, 2026-10-20).
    led = {} if fresh else {
        k: v for k, v in (ledger or {}).items()
        if isinstance(k, str) and isinstance(v, int) and not isinstance(v, bool) and v >= 0}
    order = sorted(its, key=lambda it: it.key)
    claims: Dict[str, Dict[int, str]] = {}      # family -> id -> the key printing it
    held: Dict[str, Dict[int, str]] = {}        # family -> id -> a typed item's old ledger id
    out: Dict[str, dict] = {}
    new_ledger: Dict[str, int] = {}
    warnings: List[dict] = []

    def clash(it: Item, start: int, avoid_held: bool = False) -> List[str]:
        """The keys printing (or, avoid_held, holding) any id of the block;
        avoid_held (the driven probe) also counts a reserved id, as "reserved"."""
        taken = claims.get(it.family, {})
        hold = held.get(it.family, {}) if avoid_held else {}
        got = {m.get(start + k) for m in (taken, hold) for k in range(it.count)} - {None}
        if avoid_held and on_reserved(it, start):
            got.add("reserved")
        return sorted(got)

    def take(it: Item, start: int, driven: bool) -> None:
        taken = claims.setdefault(it.family, {})
        for k in range(it.count):
            taken.setdefault(start + k, it.key)
        out[it.key] = {"key": it.key, "first_id": start,
                       "ids": [start + k for k in range(it.count)], "driven": driven}
        if driven:
            new_ledger[it.key] = start

    def refuse(it: Item, start: int, driven: bool) -> None:
        out[it.key] = {"key": it.key, "first_id": start, "ids": [], "driven": driven}

    def fits(it: Item, start: int) -> bool:
        return 0 <= start and start + it.count <= it.capacity

    def on_reserved(it: Item, start: int) -> List[int]:
        res = res_of(it.family)
        return [start + k for k in range(it.count) if start + k in res]

    def ids_words(ids: List[int]) -> str:
        return ("id " if len(ids) == 1 else "ids ") + ", ".join(map(str, ids))

    # 1. the ledger: printed ids never move
    for it in order:
        if it.first_id is not None or it.key not in led:
            continue
        start = led[it.key]
        if not fits(it, start):
            warnings.append(_issue("warn", it.key,
                                   f"its ledger id {_label(start, it.count)} is not in "
                                   f"{it.dictionary} (0..{it.capacity - 1}) any more: it moves"))
            continue
        hit = on_reserved(it, start)
        if hit:
            warnings.append(_issue("warn", it.key,
                                   f"its ledger ids {_label(start, it.count)} cover reserved "
                                   f"{ids_words(hit)}: it moves"))
            continue
        hit = clash(it, start)
        if hit:
            warnings.append(_issue("warn", it.key,
                                   f"its ledger ids {_label(start, it.count)} now overlap "
                                   f"{', '.join(hit)}'s: it moves"))
            continue
        take(it, start, True)
    # 2. typed ids: exactly as typed; overlaps flagged on both, never moved
    for it in order:
        if it.first_id is None:
            continue
        start = it.first_id
        if not fits(it, start):
            last = it.capacity - it.count
            warnings.append(_issue("error", it.key,
                                   f"{'ids' if it.count > 1 else 'id'} {_label(start, it.count)} "
                                   f"not in {it.dictionary} (0..{it.capacity - 1})"
                                   + (f": this board needs {it.count} ids, so {last} is the "
                                      "last first id" if it.count > 1 and last >= 0 else "")))
            refuse(it, start, False)
            continue
        hit = clash(it, start)
        take(it, start, False)
        mine = on_reserved(it, start)
        if mine:
            warnings.append(_issue("error", it.key,
                                   f"{_label(start, it.count)} covers reserved {ids_words(mine)} "
                                   "(never handed out): it keeps its ids, change it"))
        if hit:
            warnings.append(_issue("error", it.key,
                                   f"{_label(start, it.count)} overlaps {', '.join(hit)}: both "
                                   "keep their ids, change one"))
            for other in hit:
                warnings.append(_issue("error", other,
                                       f"{it.key}'s typed {_label(start, it.count)} overlaps "
                                       "these ids: both keep their ids, change one"))
    # a typed item's old ledger id: kept in the ledger and held for it
    for it in order:
        if it.first_id is not None and it.key in led:
            new_ledger[it.key] = led[it.key]
            if fits(it, led[it.key]):
                hold = held.setdefault(it.family, {})
                for k in range(it.count):
                    hold.setdefault(led[it.key] + k, it.key)
    # 3. the rest, driven: the preferred block, else the next free one (wrapping);
    #    sequential: in request order, from its family's counter
    counter: Dict[str, int] = {}
    for it in (its if sequential else order):
        if it.key in out:
            continue
        if sequential:
            want = counter.get(it.family, origin)
        else:
            want = preferred(it.key, it.dictionary, it.count, it.capacity)
        last = it.capacity - it.count
        starts = list(range(want, last + 1)) + list(range(0, min(want, last + 1)))
        start = next((s for s in starts if not clash(it, s, True)), None)
        if start is None:                          # a held block, never a reserved one
            start = next((s for s in starts if not clash(it, s) and not on_reserved(it, s)), None)
            if start is not None:
                whose = sorted({held[it.family][start + k] for k in range(it.count)
                                if start + k in held.get(it.family, {})})
                warnings.append(_issue("warn", it.key,
                                       f"{it.dictionary} has no other free "
                                       f"{'id' if it.count == 1 else f'block of {it.count}'}: it "
                                       f"takes {_label(start, it.count)}, held for "
                                       f"{', '.join(whose)} (typed now)"))
        if start is None:
            bigger = _bigger(it, {**{i: "reserved" for i in res_of(it.family)},
                                  **claims.get(it.family, {})})
            need = "id" if it.count == 1 else f"block of {it.count} ids"
            warnings.append(_issue("error", it.key,
                                   f"{it.dictionary} is full ({it.capacity} ids): no free {need} "
                                   "left -- "
                                   + (f"use {bigger}" if bigger else
                                      "no bigger dictionary of its size has room either")))
            refuse(it, want, True)
            continue
        take(it, start, True)
        counter[it.family] = start + it.count
    return {"items": [out[it.key] for it in its], "ledger": new_ledger, "warnings": warnings}
