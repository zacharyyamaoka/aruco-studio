# Ported from REF ArucoMarkers/aruco_presets.py at c8216ff. The presets, their
# normalising, comparing and words, the catalog rules and the heights-in-layers
# note are copied verbatim. The FILE is not here (core never reads a file):
# load / save took a path; here they take a store with `.text` (the file's
# text, None = no file) and `.aside` (texts moved aside), and the same parse /
# broken / write rules run on that text. MemoryStore is the in-memory store
# the tests use; server/store.py (M2b) is the one on disk (atomic writes).
# `prusa_dir` became `prusa`: a core.prusa.PrusaSources.
"""ArUco Extrude PRINT PRESETS: named sets of the dialog's print settings.

Zach, 2026-10-14: "the ability to quickly switch between presets and save
new presets", and "a custom width multiple ... 0.5 mm (default), but for a
0.6 mm nozzle maybe I want to round to a multiple of 0.675 mm". Design:
docs/design_aruco_print_presets.md.

One JSON file per user, never a Fusion attribute and never per document:

    %USERPROFILE%/CADExporter/aruco_presets.json
    {"schema": "bam_aruco_presets/1", "last": "<the preset of the last OK>",
     "presets": {"<name>": <preset>, ...}}           (the user's own only)

Built-in presets are made at every read and never stored; they cannot be
changed or deleted:

    "Default"   the dialog's defaults exactly as they were before presets
                (the marker in 0.5 mm steps: the legacy size rule's step)
    one per PrusaSlicer print profile with "Aruco" in its name (aruco_prusa,
                read only): every cell a whole number of its line width

A preset, every length in mm:

    {"name": "...",
     "profile": {"name", "nozzle_mm", "line_mm", "layer_mm", "first_layer_mm",
                 "source": "prusaslicer" | ""},
     "cells":   {"of": "cell" | "marker", "step": "line" | "mm", "mm": 0.5,
                 "min_mm": 2.0, "min_lines": 0},
     "tag":     {"dictionary", "mode", "op", "quiet_modules", "grow",
                 "corner_mark", "white_offset_mm", "white_height_mm",
                 "black_height_mm", "black_step_mm", "pin", "pin_size_mm",
                 "pin_length_mm", "pin_tol_mm"},
     "label":   {"on", "content", "text", "place", "row", "side", "scope",
                 "cap_mm" (0 = Auto size), "nozzle_mm"}}

Never in a preset: the target, the Type (single / grid / ChArUco), Auto
size or a typed size, the ids, the Origin / turn, Flip, the tag's name, the
label's position and "Build anyway".

ArUco Studio M6a (2026-10-16, not REF's): the preset is the MACHINE.
`profile` may carry the kind of printer and, for a sticker printer, its
page; a preset without them is a 3D printer, exactly as before, and the
file stays `bam_aruco_presets/1` (REF's normalise drops the keys it does
not know, so a Studio file still loads in the add-in):

    "profile": {..., "kind": "print3d" | "sticker", "dpi": 600,
                "page": "letter", "landscape": false, "margin_mm": 10,
                "stock_mm": 0.1, "sheet": "spaced" | "tight"}

A sticker printer's `line_mm` is its dot, 25.4 / dpi; its nozzle and
layers are 0. Built-in: "Sticker · Letter · 600 dpi" and "Sticker · A4 ·
600 dpi" (whole dots, stock 0.1 mm, min cell 1 mm, label stroke 0.2 mm,
spaced). `collections` sorts a catalog into 3D printers / Sticker printers.

Reads are tolerant: a missing file is no presets; a broken one is no
presets plus a note, and the next save first moves it aside
(aruco_presets.broken-<time>.json) so nothing is lost. Writes are atomic.
A value of the wrong type or out of range falls back to Default's.

No adsk import (tests drive it directly).
"""
from __future__ import annotations

import copy
import json
import math
from typing import List, Optional

from ._ref_compat import aruco_core
from . import label as _label_module
from . import markers as _markers_module
from . import prusa as aruco_prusa
from . import slabs as _slabs_module

SCHEMA = "bam_aruco_presets/1"
FILE_NAME = "aruco_presets.json"
DEFAULT = "Default"
THIS_TAG = "This tag"                      # the edit dialog's own values (never a preset)
IMPORT = "Import from PrusaSlicer…"
MODIFIED = " (modified)"
# the Preset list's own actions (2026-10-16, Zach: "It's important for these
# interfaces to be compact"): below a separator in the same dropdown
SAVE_AS = "Save as new preset…"
SEPARATOR = "──────────"
ACTION_PREFIXES = ("Update '", "Delete '")
RESERVED = (THIS_TAG, IMPORT, SAVE_AS, SEPARATOR)
MAX_NAME = 80
CELL_RULE = 1                              # aruco_autosize.CELL_RULE: the tag setting's rule

MODES = ("auto", "both", "black", "white")
OPS = ("join", "new")
PINS = ("none", "triangle", "round")
MARKS = ("none", "cut", "triangle")
LABEL_CHOICES = {"content": ("id", "id_name", "name", "dict_id", "custom"),
                 "place": ("auto", "black", "white"),
                 "row": ("auto", "bottom", "top", "both", "square"),
                 "side": ("auto", "below", "above", "left", "right"),
                 "scope": ("auto", "each", "first")}
# what a preset holds, in words (the dialog's "preset changes" line)
WORDS = {"profile.name": "printer profile", "cells.of": "round", "cells.step": "multiple of",
         "cells.mm": "multiple", "cells.min_mm": "min cell", "cells.min_lines": "min cell",
         "tag.dictionary": "dictionary", "tag.mode": "extrude", "tag.op": "operation",
         "tag.quiet_modules": "quiet zone", "tag.grow": "fuse corners",
         "tag.corner_mark": "corner mark", "tag.white_offset_mm": "white offset",
         "tag.white_height_mm": "white height", "tag.black_height_mm": "black height",
         "tag.black_step_mm": "black step", "tag.pin": "pin", "tag.pin_size_mm": "pin size",
         "tag.pin_length_mm": "pin length", "tag.pin_tol_mm": "pin tolerance",
         "label.on": "label", "label.content": "label text", "label.text": "label custom text",
         "label.place": "label position", "label.row": "label row", "label.side": "label side",
         "label.scope": "label markers", "label.cap_mm": "label size",
         "label.nozzle_mm": "label nozzle"}
TOL = 1e-6


def _SL():
    return _slabs_module


def _AL():
    return _label_module


def _markers():
    return _markers_module


# ------------------------------------------------------------- the presets

def default_preset():
    """"Default": the ArUco Extrude dialog's defaults exactly as they were
    before presets (aruco_extrude_cmd.defaults / label_defaults; a test pins
    the two together), the marker in the legacy 0.5 mm steps."""
    S = _SL()
    ls = _AL().LabelSettings()
    nozzle = float(ls.nozzle_mm)
    return {"name": DEFAULT,
            "profile": {"name": "", "nozzle_mm": nozzle,
                        "line_mm": round(aruco_prusa.AUTO_WIDTH * nozzle, 4),
                        "layer_mm": 0.0, "first_layer_mm": 0.0, "source": ""},
            "cells": {"of": "marker", "step": "mm", "mm": 0.5, "min_mm": 2.0, "min_lines": 0},
            "tag": {"dictionary": _markers().DEFAULT_DICTIONARY, "mode": "auto", "op": "join",
                    "quiet_modules": 1.0, "grow": False, "corner_mark": "none",
                    "white_offset_mm": float(S.WHITE_OFFSET),
                    "white_height_mm": float(S.WHITE_HEIGHT),
                    "black_height_mm": float(S.BLACK_HEIGHT), "black_step_mm": 0.0,
                    "pin": "triangle", "pin_size_mm": float(S.PIN_SIZE_MM),
                    "pin_length_mm": float(S.PIN_LENGTH_MM), "pin_tol_mm": float(S.PIN_TOL_MM)},
            "label": {"on": False, "content": ls.content, "text": "", "place": ls.place,
                      "row": ls.row, "side": ls.side, "scope": ls.scope, "cap_mm": 0.0,
                      "nozzle_mm": nozzle}}


def from_profile(profile, name=None):
    """A preset made from a PrusaSlicer print profile (aruco_prusa.profile):
    Default's settings, that profile, every cell a whole number of its line
    width, the label's nozzle its nozzle."""
    p = default_preset()
    p["name"] = name or profile.get("name") or "PrusaSlicer"
    p["profile"] = {k: profile.get(k) for k in ("name", "nozzle_mm", "line_mm", "layer_mm",
                                                "first_layer_mm")}
    p["profile"]["source"] = "prusaslicer"
    p["cells"] = {"of": "cell", "step": "line", "mm": 0.5, "min_mm": 2.0, "min_lines": 0}
    if profile.get("nozzle_mm"):
        p["label"]["nozzle_mm"] = float(profile["nozzle_mm"])
    return normalise(p)


def _num(v, lo=None, hi=None):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    if (lo is not None and v < lo) or (hi is not None and v > hi):
        return None
    return float(v)


def _pick(src, dst, key, check):
    """dst[key] = src[key] when `check` accepts it (-> the value to store)."""
    if not isinstance(src, dict) or key not in src:
        return
    got = check(src[key])
    if got is not None:
        dst[key] = got


def _choice(options):
    return lambda v: v if v in options else None


def _bool(v):
    return v if isinstance(v, bool) else None


def _text(limit=200):
    return lambda v: v[:limit] if isinstance(v, str) else None


def normalise(p, name=None):
    """A preset as this code keeps it: Default's shape, every value checked
    (a wrong one is Default's), unknown keys dropped. Never raises.
    Adapted (M6a): a profile's kind and its sticker keys are kept (KIND_KEYS);
    a sticker printer's dot (line_mm) and nozzle may be under 0.05 mm."""
    S = _SL()
    out = default_preset()
    p = p if isinstance(p, dict) else {}
    out["name"] = str(name or p.get("name") or out["name"])[:MAX_NAME]
    pr, src = out["profile"], p.get("profile")
    _pick(src, pr, "name", _text())
    dots = isinstance(src, dict) and src.get("kind") == "sticker"
    for k, lo in (("nozzle_mm", 0.0 if dots else 0.05), ("line_mm", 0.001 if dots else 0.05),
                  ("layer_mm", 0.0), ("first_layer_mm", 0.0)):
        _pick(src, pr, k, lambda v, lo=lo: _num(v, lo, 5.0))
    _pick(src, pr, "source", _text(40))
    _kind_keys(src, pr)
    c, src = out["cells"], p.get("cells")
    _pick(src, c, "of", _choice(("cell", "marker")))
    _pick(src, c, "step", _choice(("line", "mm")))
    _pick(src, c, "mm", lambda v: _num(v, 0.01, 20.0))
    _pick(src, c, "min_mm", lambda v: _num(v, 0.0, 50.0))
    _pick(src, c, "min_lines", lambda v: int(v) if _num(v, 0, 100) is not None
          and float(v).is_integer() else None)
    t, src = out["tag"], p.get("tag")
    dicts = aruco_core.module("fiducials").ARUCO_DICTS
    _pick(src, t, "dictionary", _choice(tuple(dicts)))
    _pick(src, t, "mode", _choice(MODES))
    _pick(src, t, "op", _choice(OPS))
    _pick(src, t, "quiet_modules", lambda v: _num(v, 0.0, 4.0))
    _pick(src, t, "grow", _bool)
    _pick(src, t, "corner_mark", _choice(MARKS))
    lim = float(S.LIMIT_MM)
    for k in ("white_offset_mm", "white_height_mm", "black_height_mm", "black_step_mm"):
        _pick(src, t, k, lambda v: _num(v, -lim, lim))
    _pick(src, t, "pin", _choice(PINS))
    for k, key in (("pin_size_mm", "pin_size"), ("pin_length_mm", "pin_length"),
                   ("pin_tol_mm", "pin_tol")):
        lo, hi = S.PIN_LIMITS[key]
        _pick(src, t, k, lambda v, lo=lo, hi=hi: _num(v, lo, hi))
    lb, src = out["label"], p.get("label")
    _pick(src, lb, "on", _bool)
    for k, opts in LABEL_CHOICES.items():
        _pick(src, lb, k, _choice(opts))
    _pick(src, lb, "text", _text())
    _pick(src, lb, "cap_mm", lambda v: _num(v, 0.0, 50.0))
    _pick(src, lb, "nozzle_mm", lambda v: _num(v, 0.05, 5.0))
    return out


def line_mm(p):
    """The preset's line width (mm): its profile's, or None. Adapted (M6a):
    a sticker printer's line is its dot (25.4 / dpi, under 0.05 mm)."""
    pr = (p or {}).get("profile") or {}
    v = pr.get("line_mm")
    lo = 0.001 if pr.get("kind") == "sticker" else 0.05
    return float(v) if _num(v, lo) is not None else None


def cell_setting(p):
    """The tag's "cells" setting this preset gives (mm, resolved: a "line"
    multiple is the profile's line width, a minimum in lines is mm) --
    {"rule": 1, "of", "mm", "min_mm"}, what aruco_autosize.cells_of reads."""
    c = normalise(p)["cells"]
    line = line_mm(p)
    m = line if (c["step"] == "line" and line) else c["mm"]
    mn = c["min_lines"] * line if (c["min_lines"] and line) else c["min_mm"]
    return {"rule": CELL_RULE, "of": c["of"], "mm": round(float(m), 6),
            "min_mm": round(float(mn), 6)}


def min_text(c):
    """A preset's minimum cell as the dialog's field shows it."""
    if c.get("min_lines"):
        n = int(c["min_lines"])
        return f"{n} line{'s' if n != 1 else ''}"
    return f"{float(c.get('min_mm') or 0.0):g} mm"


def parse_min(text):
    """The Min cell field: "2", "2.0 mm", "3 lines" (or "3 line") ->
    (min_mm, min_lines), lines 0 for a length; None when unreadable."""
    s = (text or "").strip().lower().replace(",", ".")
    if not s:
        return 0.0, 0
    for unit, lines in (("lines", True), ("line", True), ("mm", False), ("", False)):
        if unit and not s.endswith(unit):
            continue
        num = s[:len(s) - len(unit)].strip() if unit else s
        try:
            v = float(num)
        except ValueError:
            return None
        if not math.isfinite(v) or v < 0:
            return None
        if lines:
            return (0.0, int(round(v))) if float(v).is_integer() else None
        return round(v, 6), 0
    return None


# ------------------------------------------------------------- comparing

def _flat(p):
    n = normalise(p)
    out = {}
    for sect in ("profile", "cells", "tag", "label"):
        for k, v in n[sect].items():
            if sect == "profile" and k != "name":
                continue                           # the profile is named; its numbers follow
            out[f"{sect}.{k}"] = v
    return out


def changes(a, b):
    """What differs between two presets: [(field, value in a, value in b)],
    in WORDS' order (the profile by name only)."""
    fa, fb = _flat(a), _flat(b)
    out = []
    for k in WORDS:
        x, y = fa.get(k), fb.get(k)
        if isinstance(x, float) or isinstance(y, float):
            try:
                if abs(float(x) - float(y)) <= TOL:
                    continue
            except (TypeError, ValueError):
                pass
        elif x == y:
            continue
        out.append((k, x, y))
    return out


def same(a, b):
    return not changes(a, b)


def _show(k, v):
    if isinstance(v, bool):
        return "on" if v else "off"
    if isinstance(v, float):
        if k.endswith("_mm") or k == "cells.mm":
            return f"{v:g} mm"
        return f"{v:g}"
    if v in ("", None):
        return "none"
    return str(v)


def describe_changes(old, new, limit=6):
    """"extrude Auto → both, white height 2 mm → 1.6 mm, ..." (the dialog's
    line when a preset is applied), or ""."""
    ch = changes(old, new)
    words = [f"{WORDS[k]} {_show(k, x)} → {_show(k, y)}" for k, x, y in ch[:limit]]
    if len(ch) > limit:
        words.append(f"+{len(ch) - limit} more")
    return ", ".join(words)


# ---------------------------------------------------------------- the file
# REF kept it at %USERPROFILE%/CADExporter/aruco_presets.json. A store holds
# that file's text; server/store.py maps it onto a real file.

class MemoryStore:
    """The presets file in memory: `text` is its content (None: no file),
    `aside` the texts a save moved aside (REF: aruco_presets.broken-<time>.json)."""

    def __init__(self, text: Optional[str] = None):
        self.text = text
        self.aside: List[str] = []


def _empty():
    return {"schema": SCHEMA, "last": None, "presets": {}}


def parse(text):
    """REF load()'s rules on the file's text -> (data, note)."""
    if text is None:
        return _empty(), None
    try:
        raw = json.loads(text)
    except ValueError as exc:
        return _empty(), (f"{FILE_NAME} could not be read ({type(exc).__name__}): only the "
                          "built-in presets are listed; your file is kept and moved aside "
                          "on the next save")
    if not isinstance(raw, dict) or not isinstance(raw.get("presets"), dict):
        return _empty(), (f"{FILE_NAME} is not a presets file: only the built-in presets "
                          "are listed; it is moved aside on the next save")
    out = _empty()
    note = None
    if raw.get("schema") != SCHEMA:
        note = f"{FILE_NAME} says {raw.get('schema')!r}; read as {SCHEMA}"
    for name, p in raw["presets"].items():
        if not isinstance(name, str) or not valid_name(name) or not isinstance(p, dict):
            continue
        out["presets"][name] = normalise(p, name)
    if isinstance(raw.get("last"), str):
        out["last"] = raw["last"]
    return out, note


def broken(text):
    """REF _broken: a file there that is not a presets file."""
    if text is None:
        return False
    try:
        raw = json.loads(text)
    except ValueError:
        return True
    return not (isinstance(raw, dict) and isinstance(raw.get("presets"), dict))


_broken = broken


def dump(data):
    """What REF save() writes: the user's presets, normalised, as text."""
    out = {"schema": SCHEMA, "last": data.get("last"),
           "presets": {k: normalise(v, k) for k, v in (data.get("presets") or {}).items()}}
    return json.dumps(out, indent=1, sort_keys=True, allow_nan=False, ensure_ascii=False) + "\n"


def load(store):
    """-> (data, note): the user's presets, normalised, and a note when the
    file could not be read (None when fine or missing)."""
    return parse(store.text)


def save(data, store):
    """A file that could not be read is first moved aside, never overwritten."""
    if broken(store.text):
        store.aside.append(store.text)
    store.text = dump(data)
    return store


# ------------------------------------------------- the machine (M6a, not REF's)

KINDS = ("print3d", "sticker")
SHEET_MODES = ("spaced", "tight")
STICKER_PAGES = ("letter", "a4", "legal", "a3", "tabloid", "a5")   # core.sheet.PAGE_SIZES_MM
DPIS = (300, 600, 1200)
STICKER_DEFAULTS = {"dpi": 600, "page": "letter", "landscape": False, "margin_mm": 10.0,
                    "stock_mm": 0.1, "sheet": "spaced"}
KIND_KEYS = ("kind",) + tuple(STICKER_DEFAULTS)
KIND_COLLECTIONS = [("print3d", "3D printers", "cube"), ("sticker", "Sticker printers", "sticker")]
STICKER_STROKE_MM = 0.2          # the label's stroke on paper (min cap = 5 x 0.2 = 1 mm)
STICKER_MIN_CELL_MM = 1.0


def _kind_keys(src, pr):
    """The machine's keys of a profile (normalise): kept when given, a
    sticker printer's filled in; a profile without them is left as REF's."""
    if not isinstance(src, dict) or not any(k in src for k in KIND_KEYS):
        return
    kind = src.get("kind") if src.get("kind") in KINDS else "print3d"
    pr["kind"] = kind
    if kind != "sticker":
        return
    for k, v in STICKER_DEFAULTS.items():
        pr[k] = v
    _pick(src, pr, "dpi", lambda v: int(v) if _num(v, 72, 4800) is not None
          and float(v).is_integer() else None)
    _pick(src, pr, "page", _choice(STICKER_PAGES))
    _pick(src, pr, "landscape", _bool)
    _pick(src, pr, "margin_mm", lambda v: _num(v, 0.0, 50.0))
    _pick(src, pr, "stock_mm", lambda v: _num(v, 0.05, 2.0))
    _pick(src, pr, "sheet", _choice(SHEET_MODES))


def kind_of(p):
    """A preset's kind: "sticker" or "print3d" (absent: 3D, every REF file)."""
    k = ((p or {}).get("profile") or {}).get("kind")
    return k if k in KINDS else "print3d"


def sticker_preset(page="letter", dpi=600):
    """A built-in sticker printer: whole dots, stock 0.1 mm, min cell 1 mm,
    label stroke 0.2 mm, spaced sheets."""
    p = default_preset()
    pg = "A4" if page == "a4" else page[:1].upper() + page[1:]
    p["name"] = f"Sticker · {pg} · {dpi} dpi"
    p["profile"] = {"name": f"Sticker printer, {pg}, {dpi} dpi", "nozzle_mm": 0.0,
                    "line_mm": round(25.4 / dpi, 6), "layer_mm": 0.0, "first_layer_mm": 0.0,
                    "source": "", "kind": "sticker", "dpi": int(dpi), "page": page,
                    "landscape": False, "margin_mm": 10.0, "stock_mm": 0.1, "sheet": "spaced"}
    p["cells"] = {"of": "cell", "step": "line", "mm": 0.5, "min_mm": STICKER_MIN_CELL_MM,
                  "min_lines": 0}
    p["tag"].update(mode="both", op="new", pin="none", grow=False)
    p["label"]["nozzle_mm"] = STICKER_STROKE_MM
    return normalise(p)


def sticker_builtins():
    """Letter first (Zach, 2026-10-16), then A4."""
    return [sticker_preset("letter"), sticker_preset("a4")]


def collections(items):
    """[(name, preset, kind)] (a catalog's items) -> [{"id", "title", "icon",
    "names"}]: the 3D printers and the Sticker printers, each in order."""
    out = []
    for cid, title, icon in KIND_COLLECTIONS:
        out.append({"id": cid, "title": title, "icon": icon,
                    "names": [n for n, p, _k in items if kind_of(p) == cid]})
    return out


# ---------------------------------------------------------------- catalog

def builtins(prusa=None):
    """-> ([built-in presets], note): Default, then one per PrusaSlicer print
    profile with "Aruco" in its name (its folder unreadable: a note)."""
    out, note = [default_preset()], None
    try:
        for prof in aruco_prusa.aruco_profiles(prusa):
            out.append(from_profile(prof))
    except Exception as exc:                       # noqa: BLE001
        note = f"PrusaSlicer's profiles could not be read ({type(exc).__name__})"
    return out, note


def catalog(store, prusa=None):
    """Every preset the dialog lists: {"items": [(name, preset, "builtin" |
    "user")], "last": name or None, "notes": [str]} -- built-ins first
    (Default, then PrusaSlicer's), then the user's by name."""
    data, note = load(store)
    bis, bnote = builtins(prusa)
    items = [(p["name"], p, "builtin") for p in bis]
    taken = {p["name"] for p in bis}
    for name in sorted(data["presets"], key=str.lower):
        if name not in taken:
            items.append((name, data["presets"][name], "user"))
    last = data.get("last") if any(n == data.get("last") for n, _p, _k in items) else None
    return {"items": items, "last": last, "notes": [t for t in (note, bnote) if t]}


def catalog_all(store, prusa=None):
    """The Studio's catalog (M6a, not REF's): REF's catalog (Default,
    PrusaSlicer's, the user's) with the sticker printers after the 3D
    built-ins -- both kinds of machine, built-ins first."""
    cat = catalog(store, prusa)
    items = list(cat["items"])
    k = sum(1 for _n, _p, kind in items if kind == "builtin")
    taken = {n for n, _p, _k in items}
    st = [(p["name"], p, "builtin") for p in sticker_builtins() if p["name"] not in taken]
    users = [it for it in items[k:] if it[0] not in {p["name"] for p in sticker_builtins()}]
    return dict(cat, items=items[:k] + st + users)


def find(cat, name):
    """(preset, kind) of `name` in a catalog, or (None, None)."""
    for n, p, k in (cat or {}).get("items", []):
        if n == name:
            return p, k
    return None, None


def valid_name(name):
    s = (name or "").strip()
    return (bool(s) and len(s) <= MAX_NAME and s not in RESERVED and not s.endswith(MODIFIED)
            and not s.startswith(ACTION_PREFIXES))


def _builtin_names(prusa=None):
    return {p["name"] for p in builtins(prusa)[0]}


def unique_name(name, taken):
    base = (name or "").strip()[:MAX_NAME - 5] or "Preset"
    if base not in taken:
        return base
    i = 2
    while f"{base} ({i})" in taken:
        i += 1
    return f"{base} ({i})"


def save_as(name, preset, store, prusa=None):
    """A new user preset: -> the name it got (" (2)" when the name is taken
    -- a built-in's or another of the user's). Raises ValueError for a name
    that cannot be one."""
    if not valid_name(name):
        raise ValueError(f"not a preset name: {name!r}")
    data, _note = load(store)
    taken = set(data["presets"]) | _builtin_names(prusa)
    got = unique_name(name, taken)
    data["presets"][got] = normalise(preset, got)
    data["last"] = got
    save(data, store)
    return got


def update(name, preset, store, prusa=None):
    """Overwrite the user's preset `name` with `preset`. Built-ins (and a
    name that is not the user's) raise ValueError."""
    data, _note = load(store)
    if name in _builtin_names(prusa) or name not in data["presets"]:
        raise ValueError(f"{name!r} is not one of your presets (built-ins are read-only)")
    data["presets"][name] = normalise(preset, name)
    save(data, store)
    return name


def delete(name, store, prusa=None):
    """Delete the user's preset `name` (built-ins raise ValueError)."""
    data, _note = load(store)
    if name in _builtin_names(prusa) or name not in data["presets"]:
        raise ValueError(f"{name!r} is not one of your presets (built-ins cannot be deleted)")
    del data["presets"][name]
    if data.get("last") == name:
        data["last"] = None
    save(data, store)
    return name


def set_last(name, store):
    """Remember the preset of the last OK (a file that cannot be read is
    left alone: nothing to remember it in)."""
    data, note = load(store)
    if note and broken(store.text):
        return False
    if data.get("last") == name:
        return True
    data["last"] = name
    save(data, store)
    return True


def import_profile(profile_name, store, prusa=None):
    """"Import from PrusaSlicer…": a user preset made from that print
    profile (from_profile), saved under its name (" (2)" when taken) ->
    (name, preset). ValueError when PrusaSlicer has no such profile."""
    prof = aruco_prusa.profile(profile_name, prusa)
    if prof is None or not prof.get("line_mm"):
        raise ValueError(f"PrusaSlicer has no readable print profile {profile_name!r}")
    p = from_profile(prof)
    got = save_as(profile_name, p, store, prusa)
    return got, normalise(p, got)


def copy_of(p):
    return copy.deepcopy(p)


# ----------------------------------------------------- heights in layers (C)

def layer_note(depth_mm, layer_mm, first_mm=0.0, what="black"):
    """A note when a colour's depth from the tag's face is not a whole
    number of layers printed FACE DOWN (the face on the bed: the first
    layer, then whole layers), or None (whole, or no layer height known).
    Face up it depends on where the face lands in the part's height, so this
    is a note only: nothing is snapped and no tag changes.
    -> "black 0.60 mm face down = the 0.2 mm first layer + 1.25 × 0.32 mm:
        0.52 or 0.84 mm prints whole layers (face up it depends on the part)"."""
    try:
        d, lay = abs(float(depth_mm)), float(layer_mm or 0.0)
        first = float(first_mm or 0.0) or lay
    except (TypeError, ValueError):
        return None
    if not (lay > 0 and d > 0):
        return None
    j = (d - first) / lay
    if j > -1e-6 and abs(j - round(j)) < 1e-3:
        return None
    lo = first + max(0, math.floor(j + 1e-9)) * lay if d > first else None
    hi = first + max(0, math.ceil(j - 1e-9)) * lay
    if j < 0:
        alts = f"{first:g} mm (the first layer)"
        head = f"{what} {d:.2f} mm face down is under the {first:g} mm first layer"
    else:
        alts = " or ".join(f"{v:.2f} mm" for v in (lo, hi) if v is not None and v > 0)
        head = (f"{what} {d:.2f} mm face down = the {first:g} mm first layer + "
                f"{j:.2f} × {lay:g} mm")
    return f"{head}: {alts} prints whole layers (face up it depends on the part)"


# ============================================ the preset library's pure half
# Verbatim from REF ArucoMarkers/aruco_preset_library.py at c8216ff (its SCHEMA is
# LIBRARY_SCHEMA here: this module's SCHEMA is the presets file's). Not here: the recent
# list's file (server/store.py, M2b), `Library` (the page model: M5's, over the server),
# `LibraryWindow` (Fusion's palette), `document_nodes` (rolls Fusion's timeline).

import sys as _sys  # noqa: E402

aruco_presets = _sys.modules[__name__]   # REF's name for this module


LIBRARY_SCHEMA = "bam_aruco_preset_library/1"


MAX_RECENT = 8


TITLE = "ArUco Print Presets"


COLLECTIONS = [("recent", "Recent", "clock"), ("document", "This document", "doc"),
               ("mine", "My presets", "star"), ("prusa", "PrusaSlicer profiles", "import"),
               ("builtin", "Built-in", "cube")]


def _g(v, unit=" mm"):
    if v in (None, "", 0, 0.0):
        return "–"
    return f"{v:g}{unit}" if isinstance(v, (int, float)) else str(v)


MODE_WORDS = {"auto": "Auto", "both": "White + black", "black": "Black only",
              "white": "White only"}


OP_WORDS = {"join": "Join", "new": "New body"}


MARK_WORDS = {"none": "None", "cut": "Cut corner", "triangle": "Black triangle"}


PIN_WORDS = {"none": "None", "triangle": "Triangle", "round": "Round"}


def subtitle(p):
    pr = p["profile"]
    bits = [f"nozzle {pr['nozzle_mm']:g}"]
    if pr.get("line_mm"):
        bits.append(f"lines {pr['line_mm']:g}")
    if pr.get("layer_mm"):
        bits.append(f"layers {pr['layer_mm']:g}")
    return " · ".join(bits)


def lines_per_cell(p):
    """The fewest print lines a cell has under this preset (its min cell in
    lines), or None when cells are not counted in lines."""
    c = aruco_presets.cell_setting(p)
    line = aruco_presets.line_mm(p)
    if c["of"] != "cell" or not line:
        return None
    if p["cells"]["step"] != "line" and abs(c["mm"] - line) > 1e-6:
        return None
    return max(1, int(math.ceil(c["min_mm"] / line - 1e-9)))


def cells_words(p):
    c = aruco_presets.cell_setting(p)
    if c["of"] == "marker":
        return f"marker in {c['mm']:g} mm steps"
    k = lines_per_cell(p)
    head = (f"every cell whole {c['mm']:g} mm lines" if k else
            f"every cell a multiple of {c['mm']:g} mm")
    return head + (f" (≥ {k} per cell)" if k else "") + f", min cell {c['min_mm']:g} mm"


def info(p):
    """Every value of a preset, in sections, as the Info panel shows them."""
    pr, c, t, lb = p["profile"], p["cells"], p["tag"], p["label"]
    return [
        ["Printer", [["Profile", pr["name"] or "none"], ["Nozzle", _g(pr["nozzle_mm"])],
                     ["Line width", _g(pr["line_mm"])], ["Layer", _g(pr["layer_mm"])],
                     ["First layer", _g(pr["first_layer_mm"])]]],
        ["Cells", [["Rounding", cells_words(p)],
                   ["Min cell", aruco_presets.min_text(c)]]],
        ["Tag", [["Dictionary", t["dictionary"]], ["Extrude", MODE_WORDS[t["mode"]]],
                 ["Operation", OP_WORDS[t["op"]]], ["Quiet zone", f"{t['quiet_modules']:g} module"],
                 ["Corner mark", MARK_WORDS[t["corner_mark"]]],
                 ["Fuse corners", "on" if t["grow"] else "off"]]],
        ["Heights", [["White offset", _g(t["white_offset_mm"]) if t["white_offset_mm"] else "0"],
                     ["White height", _g(t["white_height_mm"])],
                     ["Black height", _g(t["black_height_mm"])],
                     ["Black step", _g(t["black_step_mm"]) if t["black_step_mm"] else "flush"]]],
        ["Locating pin", [["Shape", PIN_WORDS[t["pin"]]], ["Size", _g(t["pin_size_mm"])],
                          ["Length", _g(t["pin_length_mm"])],
                          ["Tolerance", _g(t["pin_tol_mm"])]]],
        ["Label", [["Label", "on" if lb["on"] else "off"], ["Text", lb["content"]],
                   ["Position", lb["place"]],
                   ["Cap height", "auto" if not lb["cap_mm"] else _g(lb["cap_mm"])],
                   ["Nozzle", _g(lb["nozzle_mm"])]]],
    ]


# the Edit form: (path, label, kind, options) -- kind number / text / select / bool
def edit_schema():
    dicts = list(aruco_core.module("fiducials").ARUCO_DICTS)
    ch = aruco_presets.LABEL_CHOICES
    return [
        ["profile.name", "Printer profile", "text", None],
        ["profile.nozzle_mm", "Nozzle (mm)", "number", None],
        ["profile.line_mm", "Line width (mm)", "number", None],
        ["profile.layer_mm", "Layer (mm)", "number", None],
        ["profile.first_layer_mm", "First layer (mm)", "number", None],
        ["cells.of", "Round", "select", [["marker", "the marker size"], ["cell", "each cell"]]],
        ["cells.step", "Multiple of", "select", [["line", "the line width"], ["mm", "a width"]]],
        ["cells.mm", "Width (mm)", "number", None],
        ["cells.min_mm", "Min cell (mm)", "number", None],
        ["tag.dictionary", "Dictionary", "select", [[d, d] for d in dicts]],
        ["tag.mode", "Extrude", "select", [[k, v] for k, v in MODE_WORDS.items()]],
        ["tag.op", "Operation", "select", [[k, v] for k, v in OP_WORDS.items()]],
        ["tag.quiet_modules", "Quiet zone (modules)", "number", None],
        ["tag.grow", "Fuse corners", "bool", None],
        ["tag.corner_mark", "Corner mark", "select", [[k, v] for k, v in MARK_WORDS.items()]],
        ["tag.white_offset_mm", "White offset (mm)", "number", None],
        ["tag.white_height_mm", "White height (mm)", "number", None],
        ["tag.black_height_mm", "Black height (mm)", "number", None],
        ["tag.black_step_mm", "Black step (mm)", "number", None],
        ["tag.pin", "Locating pin", "select", [[k, v] for k, v in PIN_WORDS.items()]],
        ["tag.pin_size_mm", "Pin size (mm)", "number", None],
        ["tag.pin_length_mm", "Pin length (mm)", "number", None],
        ["tag.pin_tol_mm", "Pin tolerance (mm)", "number", None],
        ["label.on", "Label", "bool", None],
        ["label.content", "Label text", "select", [[k, k] for k in ch["content"]]],
        ["label.place", "Label position", "select", [[k, k] for k in ch["place"]]],
        ["label.cap_mm", "Cap height (mm, 0 = auto)", "number", None],
        ["label.nozzle_mm", "Label nozzle (mm)", "number", None],
    ]


def set_path(p, path, value):
    sect, key = path.split(".", 1)
    p.setdefault(sect, {})[key] = value
    return p


def thumb_svg(p, marker_id=0):
    """A small SVG of the preset's dictionary marker (id 0) with its white
    border. When cells are whole print lines, one cell is shown magnified
    beside it, cut into its lines ("8 lines"): how many lines a cell has, at
    the least (the top-left cell is outlined: the one magnified)."""
    t = p["tag"]
    try:
        grid = aruco_core.module("aruco_dict").marker_grid(t["dictionary"], marker_id)
    except Exception:                              # noqa: BLE001
        grid = [[1] * 6] + [[1, 0, 1, 0, 1, 1]] * 4 + [[1] * 6]
    n = len(grid)
    q = min(1.5, max(0.0, float(t.get("quiet_modules", 1.0))))
    side = n + 2 * q
    k = lines_per_cell(p)
    width = side * 1.62 if k else side
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:g} {side:g}">'
             f'<rect width="{side:g}" height="{side:g}" fill="#fff"/><g shape-rendering="crispEdges">']
    for y, row in enumerate(grid):
        x = 0
        while x < len(row):
            if row[x]:
                x0 = x
                while x < len(row) and row[x]:
                    x += 1
                parts.append(f'<rect x="{x0 + q:g}" y="{y + q:g}" width="{x - x0}" height="1" '
                             f'fill="#111"/>')
            else:
                x += 1
    parts.append("</g>")
    if k:
        s = side * 0.5                             # the magnified cell
        x0, y0 = side * 1.1, side - s - side * 0.06
        parts.append(f'<rect x="{q:g}" y="{q:g}" width="1" height="1" fill="none" '
                     f'stroke="#38a6e8" stroke-width="0.12"/>')
        parts.append(f'<path d="M{q + 1:g} {q + 0.5:g}L{x0:g} {y0 + s / 2:g}" stroke="#38a6e8" '
                     f'stroke-width="0.08" stroke-dasharray="0.25 0.2" fill="none"/>')
        parts.append(f'<rect x="{x0:g}" y="{y0:g}" width="{s:g}" height="{s:g}" fill="#111" '
                     f'stroke="#38a6e8" stroke-width="0.12"/>')
        for i in range(1, k):
            xx = x0 + s * i / k
            parts.append(f'<line x1="{xx:g}" y1="{y0:g}" x2="{xx:g}" y2="{y0 + s:g}" '
                         f'stroke="#38a6e8" stroke-width="{min(0.1, s / k * 0.35):g}"/>')
        parts.append(f'<text x="{x0 + s / 2:g}" y="{y0 - side * 0.08:g}" font-size="{side * 0.13:g}" '
                     f'text-anchor="middle" fill="#38a6e8" font-family="Segoe UI, sans-serif">'
                     f'{k} line{"s" if k != 1 else ""}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _cells_from(cells_setting, line_mm):
    """A tag's stored "cells" -> a preset's cells (None: made before them)."""
    A = aruco_core.module("aruco_autosize")
    c = A.cells_of(cells_setting) if cells_setting else None
    if c is None:
        return None
    of, step_m, min_m = c
    mm = round(step_m * 1000.0, 6)
    step = "line" if (of == "cell" and line_mm and abs(mm - line_mm) < 1e-6) else "mm"
    return {"of": of, "step": step, "mm": mm, "min_mm": round(min_m * 1000.0, 6),
            "min_lines": 0}


def preset_of_node(s, n, profile=None):
    """An ArUco Extrude node's print settings (settings_of / numbers_of) as a
    preset (aruco_presets' shape): what a tag was made with."""
    p = aruco_presets.default_preset()
    if profile:
        p["profile"].update({k: profile.get(k, p["profile"][k]) for k in p["profile"]})
    t = p["tag"]
    for k in ("dictionary", "mode", "op"):
        if s.get(k):
            t[k] = s[k]
    t["quiet_modules"] = float(s.get("quiet_modules", t["quiet_modules"]))
    t["grow"] = bool(s.get("grow"))
    try:
        t["corner_mark"] = aruco_core.module("aruco_chamfer").choice_of(s)
    except Exception:                              # noqa: BLE001
        t["corner_mark"] = s.get("corner_mark") or "none"
    for k, nk in (("white_offset_mm", "white_offset"), ("white_height_mm", "white_height"),
                  ("black_height_mm", "black_height"), ("pin_size_mm", "pin_size"),
                  ("pin_length_mm", "pin_length"), ("pin_tol_mm", "pin_tol")):
        if isinstance(n.get(nk), (int, float)):
            t[k] = float(n[nk])
    try:
        top = aruco_core.module("aruco_slabs").white_top(t["mode"], n)
        t["black_step_mm"] = round(float(n.get("black_offset", top)) - top, 6)
    except Exception:                              # noqa: BLE001
        pass
    t["pin"] = s.get("pin") or "none"
    lb = s.get("label")
    if isinstance(lb, dict):
        for k in ("on", "content", "text", "place", "row", "side", "scope", "cap_mm", "nozzle_mm"):
            if k in lb:
                p["label"][k] = lb[k]
    c = _cells_from(s.get("cells"), aruco_presets.line_mm(p))
    if c is not None:
        p["cells"] = c
    return aruco_presets.normalise(p)


def _resolved(p):
    q = aruco_presets.normalise(copy.deepcopy(p))
    c = aruco_presets.cell_setting(q)
    q["cells"] = {"of": c["of"], "step": "mm", "mm": c["mm"], "min_mm": c["min_mm"],
                  "min_lines": 0}
    q["profile"]["name"] = ""
    return q


def same_print(a, b):
    """Do two presets print the same tag (the printer profile's name aside,
    cells compared as resolved widths)? A node stores its RESOLVED Extrude
    (white + black / black only / white only); a preset's Auto matches any."""
    ra, rb = _resolved(a), _resolved(b)
    if "auto" in (ra["tag"]["mode"], rb["tag"]["mode"]):
        ra["tag"]["mode"] = rb["tag"]["mode"] = "auto"
    return aruco_presets.same(ra, rb)


def group_nodes(nodes, catalog_items):
    """[(key, preset)] of the design's tags -> [{"name", "preset", "keys",
    "matches"}]: one per distinct print setting, named after the catalog
    preset it equals, else the first tag."""
    groups = []
    for key, p in nodes:
        for g in groups:
            if same_print(g["preset"], p):
                g["keys"].append(key)
                break
        else:
            groups.append({"preset": p, "keys": [key], "matches": None})
    for g in groups:
        for name, cp, _kind in catalog_items:
            if same_print(g["preset"], cp):
                g["matches"] = name
                break
        n = len(g["keys"])
        g["name"] = (g["matches"] if g["matches"] else f"Tag '{g['keys'][0]}' settings")
        g["note"] = f"{n} tag{'s' if n != 1 else ''} in this design"
    return groups


def preset_of(settings, numbers, profile=None):
    """A tag's print settings (its settings + numbers, mm) as a preset: REF
    preset_of_node's mapping. The adapter reads the node; this maps. A
    printed sticker (settings.make, M6a) reads as a sticker printer's preset
    (its dot from the cells, its stock from the make)."""
    from . import make as _MK
    mk, _n = _MK.make_of(settings or {})
    if mk.sticker and not profile:
        c = (settings or {}).get("cells") or {}
        dot = c.get("mm") if isinstance(c, dict) else None
        dot = float(dot) if _num(dot, 0.001, 5.0) is not None else round(25.4 / 600, 6)
        profile = {"name": "", "nozzle_mm": 0.0, "line_mm": dot, "layer_mm": 0.0,
                   "first_layer_mm": 0.0, "source": "", "kind": "sticker",
                   "dpi": int(round(25.4 / dot)), "stock_mm": mk.thickness_mm}
        p = preset_of_node(settings, numbers, None)
        p["profile"] = profile
        return normalise(p)
    return preset_of_node(settings, numbers, profile)
