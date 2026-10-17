"""The print preset Library's state: REF `aruco_preset_library.Library`
(build / state / the card), on the Studio's own store.

| REF | Here |
|---|---|
| `recent()`, `add_recent()`, `forget_recent()` on `~/CADExporter/aruco_preset_library.json` | the same file shape under the Studio's home (server/store.py) |
| `Library.nodes()`: the Fusion design's tags | the open scene's tags (`newtag.preset_of` of each) |
| `Library.dialog()`: the open dialog's print settings | the selected tag's (`dialog` argument) |
| `Library.prints()`: PrusaSlicer's print profiles | `core.prusa.user_prints` over `store.prusa_sources()` |
| (M8c, not REF's) | a **Printers** collection: one card per PrusaSlicer physical printer, its fitting print presets as the card's `choices` (the "Aruco" ones first, the current pair marked); Select on a choice (`printer:<name>|<print>`, or the card for its default) makes the preset from the pair (`core.presets.from_pair`: the printer's nozzle, the print's line and layers) and imports it as one of yours. And a **Sticker printers** collection (M6a's sticker built-ins and yours): the catalog is `catalog_all` |

The words, thumbs, Info sections and the Edit form are core.presets'
(`subtitle`, `cells_words`, `thumb_svg`, `info`, `edit_schema`,
`group_nodes`), unchanged.
"""
from __future__ import annotations

import json
from typing import Dict, List, Optional, Tuple

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
    cat = _P.catalog_all(S.presets_store(), prusa)
    notes += list(cat.get("notes") or [])
    cards, names = {}, {}
    for name, p, kind in cat["items"]:
        cid = f"{'user' if kind == 'user' else 'builtin'}:{name}"
        where = ["mine" if kind == "user" else "builtin"]
        if _P.kind_of(p) == "sticker":
            where.append("stickers")
        cards[cid] = _card(cid, name, p, kind, where, dialog)
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
    if prusa is not None:
        try:
            for c in printer_cards(prusa, dialog):
                cards[c["id"]] = c
        except Exception as exc:                   # noqa: BLE001
            notes.append(f"PrusaSlicer's physical printers could not be read ({exc})"[:200])
    return cards, notes, prusa


COLLECTIONS = ([(c, "This scene" if c == "document" else n, i) for c, n, i in _P.COLLECTIONS]
               + [("printers", "Printers", "printer"), ("stickers", "Sticker printers", "sticker")])


# ------------------------------------------------------------------ the Printers (M8c)

PRINTER_PREFIX = "printer:"


def _choice_id(physical: str, print_name: str) -> str:
    return f"{PRINTER_PREFIX}{physical}|{print_name}"


def printer_cards(prusa, dialog=None) -> List[dict]:
    """One card per physical printer: its printer preset's numbers and its
    fitting print presets as `choices` (Aruco first; `current` the pair
    PrusaSlicer has selected). `preset` is the default choice's preset
    (made on Select, not stored)."""
    out = []
    for e in _PR.physical_printers(prusa):
        pr = e["printer"]
        cid = f"{PRINTER_PREFIX}{e['name']}"
        choices = [{"id": _choice_id(e["name"], p["name"]), "name": p["name"],
                    "fits": p["fits"], "line": p["line_mm"], "layer": p["layer_mm"],
                    "first_layer": p["first_layer_mm"], "nozzle": p["nozzle_mm"],
                    "aruco": p["aruco"], "current": p.get("current", False)}
                   for p in e["prints"]]
        default = next((c for c in choices if c["current"]), None) or             next((c for c in choices if c["fits"] == "yes"), None) or             (choices[0] if choices else None)
        sub = (f"{pr['model']} {pr['variant']} · nozzle {pr['nozzle_mm']:g} · "
               f"{len(choices)} print preset{'' if len(choices) == 1 else 's'}"
               if pr else f"its printer preset {e['preset']!r} was not found")
        card = {"id": cid, "name": e["name"], "kind": "printer", "in": ["printers"],
                "editable": False, "subtitle": sub, "thumb": "", "used": 0, "info": [],
                "recent": None, "differs": "", "current": e["current"],
                "printer": pr, "technology": e["technology"], "host_kind": e["host_kind"],
                "choices": choices, "default": default["id"] if default else None,
                "nozzle": pr["nozzle_mm"] if pr else None, "preset": None}
        if pr is None or default is None:
            card["unreadable"] = True
        else:
            p = _pair_preset(prusa, e["name"], default["name"])
            card.update(preset=p, line=p["profile"]["line_mm"],
                        layer=p["profile"]["layer_mm"] or None, differs=_differs(dialog, p))
        out.append(card)
    return out


def _pair_preset(prusa, physical: str, print_name: str) -> dict:
    """The preset Select makes from (physical printer, print preset)."""
    e = next((x for x in _PR.physical_printers(prusa) if x["name"] == physical), None)
    if e is None or e["printer"] is None:
        raise KeyError(f"{PRINTER_PREFIX}{physical}")
    pr = _PR.printer_of(e["preset"], prusa)
    pp = _PR.pair_profile(print_name, dict(pr, physical=physical), prusa)
    if pp is None or not pp.get("line_mm"):
        raise ValueError(f"'{print_name}' cannot be read as a print profile")
    return _P.from_pair(pp, f"{physical} · {print_name}")


def _select_printer(card_id: str, prusa) -> Tuple[str, dict]:
    body = card_id[len(PRINTER_PREFIX):]
    physical, sep, print_name = body.partition("|")
    if not sep:
        card = next((c for c in printer_cards(prusa) if c["id"] == card_id), None)
        if card is None:
            raise KeyError(card_id)
        if not card["default"]:
            raise ValueError(f"'{physical}' has no print preset that fits")
        print_name = card["default"].partition("|")[2]
    elif physical not in prusa.physical:
        raise KeyError(card_id)
    p = _pair_preset(prusa, physical, print_name)
    st = S.presets_store()
    got = _P.save_as(p["name"], p, st, prusa)
    st.flush()
    add_recent(got)
    return got, _P.normalise(p, got)


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
            "schema": _P.edit_schema(), "limits": {k: list(v) for k, v in LIMITS.items()},
            "notes": notes, "dialog": dialog is not None}


def select(card_id: str, nodes) -> Tuple[str, dict]:
    """Select: (name, preset) to apply. A PrusaSlicer card is imported first,
    so the Preset row names a real preset (REF Library.select)."""
    if card_id.startswith(PRINTER_PREFIX):
        prusa = S.prusa_sources()
        if prusa is None:
            raise KeyError(card_id)
        return _select_printer(card_id, prusa)
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


def _limits() -> Dict[str, Tuple[float, float]]:
    """The range core.presets.normalise keeps each number of the Edit form
    in (outside it, a preset silently gets Default's value): the form checks
    against these first (audit F16; tests/server/test_audit_fixes.py checks
    them against normalise at both ends)."""
    from ..core import slabs as _SL
    lim = float(_SL.LIMIT_MM)
    out = {"profile.nozzle_mm": (0.05, 5.0), "profile.line_mm": (0.05, 5.0),
           "profile.layer_mm": (0.0, 5.0), "profile.first_layer_mm": (0.0, 5.0),
           "cells.mm": (0.01, 20.0), "cells.min_mm": (0.0, 50.0),
           "tag.quiet_modules": (0.0, 4.0),
           "label.cap_mm": (0.0, 50.0), "label.nozzle_mm": (0.05, 5.0)}
    for k in ("white_offset_mm", "white_height_mm", "black_height_mm", "black_step_mm"):
        out[f"tag.{k}"] = (-lim, lim)
    for k, key in (("pin_size_mm", "pin_size"), ("pin_length_mm", "pin_length"),
                   ("pin_tol_mm", "pin_tol")):
        out[f"tag.{k}"] = tuple(float(x) for x in _SL.PIN_LIMITS[key])
    return out


LIMITS = _limits()


class EditError(ValueError):
    """Edit -> Save refused: [{path, msg}], one per field."""

    def __init__(self, errors):
        super().__init__("; ".join(f"{e['path']}: {e['msg']}" for e in errors))
        self.errors = errors


def check_values(values: dict) -> list:
    """The Edit form's values against the schema's kinds and LIMITS:
    [{path, msg}] (empty = fine)."""
    import math as _m
    kinds = {path: (kind, label) for path, label, kind, _o in _P.edit_schema()}
    errs = []
    for path, v in (values or {}).items():
        if path not in kinds or kinds[path][0] != "number":
            continue
        label = kinds[path][1]
        try:
            x = float(v)
        except (TypeError, ValueError):
            errs.append({"path": path, "msg": f"{label}: '{v}' is not a number"})
            continue
        lo, hi = LIMITS.get(path, (-_m.inf, _m.inf))
        if not _m.isfinite(x) or not lo <= x <= hi:
            errs.append({"path": path, "msg": f"{label}: {v} is outside {lo:g} to {hi:g}"})
    return errs


def save_edit(card_id: str, name: str, values: dict, nodes) -> str:
    """Edit -> Save of one of mine (REF Library.save): its fields by path,
    maybe a new name. A value outside what a preset keeps is refused
    (EditError), never silently replaced by Default's. -> the preset's name."""
    cards, _notes, prusa = build(nodes)
    c = cards.get(card_id)
    if c is None:
        raise KeyError(card_id)
    if c["kind"] != "user":
        raise ValueError("only your own presets can be edited (Duplicate a built-in one)")
    if name is not None and name != "" and not name.strip():
        raise EditError([{"path": "name", "msg": "a preset needs a name"}])
    errs = check_values(values)
    if errs:
        raise EditError(errs)
    import copy
    p = copy.deepcopy(c["preset"])
    kinds = {path: kind for path, _l, kind, _o in _P.edit_schema()}
    for path, v in (values or {}).items():
        if path not in kinds:
            continue
        if kinds[path] == "number":
            v = float(v)
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
