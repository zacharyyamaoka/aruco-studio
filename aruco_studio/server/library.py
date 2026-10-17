"""The print preset Library's state: REF `aruco_preset_library.Library`
(build / state / the card), on the Studio's own store.

| REF | Here |
|---|---|
| `recent()`, `add_recent()`, `forget_recent()` on `~/CADExporter/aruco_preset_library.json` | the same file shape under the Studio's home (server/store.py) |
| `Library.nodes()`: the Fusion design's tags | the open scene's tags (`newtag.preset_of` of each) |
| `Library.dialog()`: the open dialog's print settings | the selected tag's (`dialog` argument) |
| `Library.prints()`: PrusaSlicer's print profiles | `core.prusa.user_prints` over `store.prusa_sources()` |

The words, thumbs, Info sections and the Edit form are core.presets'
(`subtitle`, `cells_words`, `thumb_svg`, `info`, `edit_schema`,
`group_nodes`), unchanged.
"""
from __future__ import annotations

import json
from typing import List, Optional, Tuple

from ..core import presets as _P
from ..core import prusa as _PR
from . import store as S

FILE_NAME = "aruco_preset_library.json"


# ------------------------------------------------------------------ recent

def _path():
    return S.home() / FILE_NAME


def _load() -> dict:
    p = _path()
    try:
        data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        if not isinstance(data, dict):
            raise ValueError
    except (OSError, ValueError):
        data = {}
    rec = data.get("recent")
    data["recent"] = ([r for r in rec if isinstance(r, str) and r][:_P.MAX_RECENT]
                      if isinstance(rec, list) else [])
    data["schema"] = _P.LIBRARY_SCHEMA
    return data


def recent() -> List[str]:
    """The recent presets' names, newest first."""
    return list(_load()["recent"])


def add_recent(name: str) -> List[str]:
    if not name:
        return recent()
    data = _load()
    data["recent"] = ([name] + [r for r in data["recent"] if r != name])[:_P.MAX_RECENT]
    S.write_atomic(_path(), json.dumps(data, indent=1) + "\n")
    return list(data["recent"])


def forget_recent(name: str) -> List[str]:
    data = _load()
    if name in data["recent"]:
        data["recent"] = [r for r in data["recent"] if r != name]
        S.write_atomic(_path(), json.dumps(data, indent=1) + "\n")
    return list(data["recent"])


# ------------------------------------------------------------------ cards

def _differs(dialog, p):
    """What Select would change on the tag ("" when it prints the same: a
    tag stores its RESOLVED Extrude, a preset's Auto matches it)."""
    if dialog is None or _P.same_print(dialog, p):
        return ""
    return _P.describe_changes(dialog, p, limit=8)


def _card(cid, name, p, kind, where, dialog):
    p = _P.normalise(p, name)
    pr, t = p["profile"], p["tag"]
    return {"id": cid, "name": name, "kind": kind, "in": list(where),
            "editable": kind == "user", "subtitle": _P.subtitle(p),
            "nozzle": pr["nozzle_mm"], "line": pr["line_mm"], "layer": pr["layer_mm"] or None,
            "dictionary": t["dictionary"], "mode": t["mode"],
            "mode_words": _P.MODE_WORDS[t["mode"]], "profile": pr["name"],
            "cells": _P.cells_words(p), "thumb": _P.thumb_svg(p), "used": 0,
            "info": _P.info(p), "recent": None,
            "differs": _differs(dialog, p),
            "preset": p}


def build(nodes: List[Tuple[str, dict]], dialog: Optional[dict] = None):
    """(cards by id, notes): REF Library.build on the Studio's sources."""
    prusa = None
    notes: List[str] = []
    try:
        prusa = S.prusa_sources()
    except Exception as exc:                       # noqa: BLE001
        notes.append(f"PrusaSlicer's folder could not be read ({type(exc).__name__})")
    cat = _P.catalog(S.presets_store(), prusa)
    notes += list(cat.get("notes") or [])
    cards, names = {}, {}
    for name, p, kind in cat["items"]:
        cid = f"{'user' if kind == 'user' else 'builtin'}:{name}"
        cards[cid] = _card(cid, name, p, kind, ["mine" if kind == "user" else "builtin"], dialog)
        names[name] = cid
    prints = []
    if prusa is not None:
        try:
            prints = _PR.user_prints(prusa)
        except Exception as exc:                   # noqa: BLE001
            notes.append(f"PrusaSlicer's print profiles could not be listed ({exc})"[:200])
    for up in prints:
        nm = up.get("name")
        if not nm:
            continue
        if nm in names:
            cards[names[nm]]["in"].append("prusa")
            continue
        try:
            prof = _PR.profile(nm, prusa)
        except Exception:                          # noqa: BLE001
            prof = None
        cid = f"prusa:{nm}"
        if prof is None or not prof.get("line_mm"):
            cards[cid] = {"id": cid, "name": nm, "kind": "prusa", "in": ["prusa"],
                          "editable": False, "subtitle": "not readable as a print profile",
                          "thumb": "", "unreadable": True, "used": 0, "info": [],
                          "differs": "", "preset": None, "recent": None}
            continue
        cards[cid] = _card(cid, nm, _P.from_profile(prof), "prusa", ["prusa"], dialog)
    for g in _P.group_nodes(nodes, cat["items"]):
        if g["matches"] and g["matches"] in names:
            c = cards[names[g["matches"]]]
            c["used"] += len(g["keys"])
            c["in"].append("document")
            continue
        cid = f"doc:{g['keys'][0]}"
        c = _card(cid, g["name"].replace("in this design", "in this scene"), g["preset"],
                  "document", ["document"], dialog)
        c["used"] = len(g["keys"])
        c["subtitle"] = g["note"].replace("design", "scene") + " · " + c["subtitle"]
        cards[cid] = c
    for i, nm in enumerate(recent()):
        cid = names.get(nm)
        if cid in cards:
            cards[cid]["in"].append("recent")
            cards[cid]["recent"] = i
    return cards, notes, prusa


COLLECTIONS = [(c, "This scene" if c == "document" else n, i) for c, n, i in _P.COLLECTIONS]


def state(nodes, dialog=None, selected=None) -> dict:
    """REF Library.state: the collections with counts, the cards (recent
    first, then by name), the Edit form, the notes."""
    cards, notes, _prusa = build(nodes, dialog)
    counts = {c: sum(1 for k in cards.values() if c in k["in"]) for c, _n, _i in COLLECTIONS}
    order = sorted(cards.values(), key=lambda k: (k["recent"] if k["recent"] is not None else 99,
                                                  k["name"].lower()))
    return {"title": "Print presets",
            "collections": [{"id": c, "name": n, "icon": i, "count": counts[c]}
                            for c, n, i in COLLECTIONS],
            "cards": order, "selected": selected if selected in cards else None,
            "schema": _P.edit_schema(), "notes": notes, "dialog": dialog is not None}


def select(card_id: str, nodes) -> Tuple[str, dict]:
    """Select: (name, preset) to apply. A PrusaSlicer card is imported first,
    so the Preset row names a real preset (REF Library.select)."""
    cards, _notes, prusa = build(nodes)
    c = cards.get(card_id)
    if c is None:
        raise KeyError(card_id)
    if c["kind"] == "prusa":
        if c.get("unreadable"):
            raise ValueError(f"'{c['name']}' cannot be read as a print profile")
        st = S.presets_store()
        got, p = _P.import_profile(c["name"], st, prusa)
        st.flush()
        add_recent(got)
        return got, p
    if c.get("preset") is None:
        raise ValueError(f"'{c['name']}' cannot be read")
    if c["kind"] != "document":
        add_recent(c["name"])
    return c["name"], c["preset"]


def save_edit(card_id: str, name: str, values: dict, nodes) -> str:
    """Edit -> Save of one of mine (REF Library.save): its fields by path,
    maybe a new name. -> the preset's name."""
    cards, _notes, prusa = build(nodes)
    c = cards.get(card_id)
    if c is None:
        raise KeyError(card_id)
    if c["kind"] != "user":
        raise ValueError("only your own presets can be edited (Duplicate a built-in one)")
    import copy
    p = copy.deepcopy(c["preset"])
    kinds = {path: kind for path, _l, kind, _o in _P.edit_schema()}
    for path, v in (values or {}).items():
        if path not in kinds:
            continue
        if kinds[path] == "number":
            try:
                v = float(v)
            except (TypeError, ValueError):
                raise ValueError(f"{path}: not a number: {v!r}") from None
        elif kinds[path] == "bool":
            v = bool(v)
        _P.set_path(p, path, v)
    name = (name or "").strip() or c["name"]
    st = S.presets_store()
    if name != c["name"]:
        got = _P.save_as(name, p, st, prusa)
        _P.delete(c["name"], st, prusa)
        st.flush()
        forget_recent(c["name"])
        return got
    _P.update(c["name"], p, st, prusa)
    st.flush()
    return c["name"]
