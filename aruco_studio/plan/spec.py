"""The request: TagSpec (ARCHITECTURE 5.2) and its per-field checks (5.6).

Not `core.markers.TagSpec` (the marker record in metres): that one is an
OUTPUT of the plan (`TagPlan.marker`).

Two layers, never mixed:

| Layer | Catches | Answer |
|---|---|---|
| `TagSpec.from_dict` | a wrong TYPE: a string where a number goes, a missing required key, an unknown `schema` | `SpecTypeError(path, message)` (the server's 422) |
| `check(spec)` | a wrong VALUE: out of range, not a choice | `[Issue(field, level, text)]` |

A value REF tolerates (it reads it a defined way: junk "trim" = off, an
unknown corner mark = none, a turn that is not a quarter = as laid out) is a
`warn`: the tag builds exactly as REF builds it. `error` means the plan is
not built (REF would raise, or the value names a rule this code does not
know).
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..core import autosize as _A
from ..core import board as _B
from ..core import chamfer as _CH
from ..core import dictionary as _D
from ..core import form as _F
from ..core import label as _L
from ..core import make as _MK
from ..core import origin as _OR
from ..core import settings as _S
from ..core import slabs as _SL
from ..core import trim as _TR
from .target import KINDS, SpecTypeError, Target

SCHEMA = "arucostudio.tagspec/1"
LEVELS = ("error", "warn", "info")

# the settings keys an adapter keeps there (ARCHITECTURE 5.2): carried
# through untouched, never read by the plan (tests/plan/test_adapter_keys.py)
ADAPTER_KEYS = ("x_base", "x_ref", "z_sign", "has_body", "source", "jo_v", "host_xform", "key",
                "black_follows")

QUIET_MIN, QUIET_LOW, QUIET_MAX = 0.5, 1.0, 3.0

# settings keys -> the type they must have (the 422 layer)
_STR = (str,)
_NUM = (int, float)
SETTINGS_TYPES = {"layout": _STR, "dictionary": _STR, "mode": _STR, "op": _STR,
                  "quiet_modules": _NUM, "turn": _NUM, "rotate_deg": _NUM,
                  "corner_mark": _STR, "pin": _STR, "grow": (bool,), "legacy": (bool,),
                  "chamfer": (bool,), "size_auto": (bool,), "flip": (bool,),
                  "label": (dict, type(None)), "cells": (dict, type(None)),
                  "force": (list, tuple, type(None)), "origin_v": (int, type(None)),
                  "make": (dict, type(None)), "holes": (str, type(None)),
                  "shift": (dict, type(None))}
NUMBER_KEYS = _S.PARAMS + _S.LEGACY_PARAMS


@dataclass
class Issue:
    """One message about one field of a TagSpec. `field` is its key path
    (`numbers.size`, `settings.label.cap_mm`, `target.loops_mm`, ...) or
    "tag" for the tag as a whole."""
    field: str
    level: str
    text: str

    def to_dict(self) -> dict:
        return {"field": self.field, "level": self.level, "text": self.text}

    @classmethod
    def from_dict(cls, d) -> "Issue":
        return cls(d["field"], d["level"], d["text"])


@dataclass
class TagSpec:
    settings: dict = field(default_factory=_S.default_settings)
    numbers: dict = field(default_factory=dict)
    target: Target = field(default_factory=Target)
    name: str = ""
    key: str = ""
    schema: str = SCHEMA

    def to_dict(self) -> dict:
        return {"schema": self.schema, "settings": copy.deepcopy(self.settings),
                "numbers": dict(self.numbers), "target": self.target.to_dict(),
                "name": self.name, "key": self.key}

    @classmethod
    def from_dict(cls, d) -> "TagSpec":
        if not isinstance(d, dict):
            raise SpecTypeError("", "a TagSpec object")
        schema = d.get("schema", SCHEMA)
        if schema != SCHEMA:
            raise SpecTypeError("schema", f"{schema!r} is not {SCHEMA!r}")
        s = d.get("settings", {})
        if not isinstance(s, dict):
            raise SpecTypeError("settings", "an object")
        for k, types in SETTINGS_TYPES.items():
            if k in s and s[k] is not None or (k in s and type(None) not in types):
                v = s[k]
                ok = isinstance(v, types) and not (isinstance(v, bool) and bool not in types)
                if not ok:
                    raise SpecTypeError(f"settings.{k}",
                                        f"{_type_words(types)}, not {type(v).__name__}")
        n = d.get("numbers", {})
        if not isinstance(n, dict):
            raise SpecTypeError("numbers", "an object")
        for k, v in n.items():
            if k in NUMBER_KEYS and v is not None and (isinstance(v, bool)
                                                       or not isinstance(v, (int, float))):
                raise SpecTypeError(f"numbers.{k}", f"a number, not {type(v).__name__}")
        if "target" not in d:
            raise SpecTypeError("target", "required")
        t = Target.from_dict(d["target"])
        for k in ("name", "key"):
            if not isinstance(d.get(k, ""), str):
                raise SpecTypeError(k, "a string")
        return cls(settings=copy.deepcopy(s), numbers=dict(n), target=t,
                   name=d.get("name", ""), key=d.get("key", ""), schema=schema)


def _type_words(types):
    words = {str: "a string", int: "a number", float: "a number", bool: "true or false",
             dict: "an object", list: "a list", tuple: "a list", type(None): "null"}
    return " or ".join(dict.fromkeys(words[t] for t in types))


# ======================================================== reading a spec

def settings_of(spec: TagSpec) -> dict:
    """The settings the plan works with: REF's settings_of (the defaults,
    then the stored dict normalise()d), with the target's facts in place of
    the adapter's keys, and the label's {key} from the spec."""
    s = _S.settings_from_stored(spec.settings) or _S.default_settings()
    t = spec.target
    s["has_body"] = bool(t.has_body)
    s["z_sign"] = int(t.z_sign)
    s["key"] = spec.key or ""
    for k in ("x_ref", "x_base", "host_xform", "black_follows"):
        s.pop(k, None)
    s["source"] = "profile" if t.is_profile else "face"
    _F.resolve_mode(s, t.has_body)                     # Auto, the dialog's default (create())
    d = s.get("dictionary")
    if isinstance(d, str) and d not in _D.DICTIONARY_NAMES:
        for nm in _D.DICTIONARY_NAMES:
            if nm.casefold() == d.casefold():
                s["dictionary"] = nm
    return s


def numbers_of(spec: TagSpec, s: dict) -> dict:
    """REF's numbers_of: the defaults of the mode, the numbers given, a
    node made before 2026-10-08 (height / thickness / above) mapped to
    Offset / Height pairs."""
    params = {k: v for k, v in (spec.numbers or {}).items() if k in NUMBER_KEYS and v is not None}
    return _S.numbers_from_params(s, params)


def has_legacy_numbers(spec: TagSpec) -> bool:
    return any(k in (spec.numbers or {}) for k in _S.LEGACY_PARAMS)


# ======================================================== the checks (5.6)

def _poly_area2(pts):
    return sum(pts[i - 1][0] * pts[i][1] - pts[i][0] * pts[i - 1][1] for i in range(len(pts)))


def _inside(loop, p):
    inside = False
    n = len(loop)
    for i in range(n):
        (x0, y0), (x1, y1) = loop[i - 1], loop[i]
        if (y0 > p[1]) != (y1 > p[1]) and p[0] < x0 + (p[1] - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside


def _finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def check(spec: TagSpec) -> List[Issue]:
    """The per-field checks of ARCHITECTURE 5.6 that need no plan. plan_tag
    runs them first; /api/validate returns them with the plan's own."""
    out: List[Issue] = []
    add = lambda f, lv, t: out.append(Issue(f, lv, t))
    raw = spec.settings or {}
    s = settings_of(spec)
    n = spec.numbers or {}
    t = spec.target

    # -- layout, dictionary
    if s.get("layout") not in _B.LAYOUTS:
        add("settings.layout", "error",
            f"unknown layout {s.get('layout')!r}: one of {', '.join(_B.LAYOUTS)}")
    d = s.get("dictionary")
    if d not in _D.DICTIONARY_NAMES:
        add("settings.dictionary", "error", f"unknown dictionary {d!r}")
    elif "dictionary" in raw and raw.get("dictionary") != d:
        add("settings.dictionary", "info", f"dictionary {raw.get('dictionary')!r} read as {d}")
    # -- marker id
    mid = n.get("marker_id", 0)
    if mid is not None and _finite(mid):
        if mid < 0 or abs(mid - round(mid)) > 1e-9:
            add("numbers.marker_id", "error", f"marker id {mid:g}: a whole number, 0 or more")
        elif d in _D.DICTIONARY_NAMES:
            cap = _D.dictionary_info(d)["capacity"]
            if round(mid) >= cap:
                add("numbers.marker_id", "error",
                    f"marker id {int(round(mid))} is outside {d} (ids 0..{cap - 1}, "
                    f"{cap} in all)")
    elif mid is not None:
        add("numbers.marker_id", "error", "marker id: not a finite number")
    # -- size, square
    for k, word in (("size", "Marker size"), ("square", "Checker size")):
        v = n.get(k, 0.0)
        if v is not None and (not _finite(v) or v < 0):
            # plain words, nothing the short line cuts (audit nit C2: "size -5.0: 0")
            add(f"numbers.{k}", "error", f"{word} {v:g} mm: 0 for Auto, or more than 0 mm"
                if _finite(v) else f"{word}: 0 for Auto, or more than 0 mm")
    sz, sq = n.get("size") or 0.0, n.get("square") or 0.0
    if s.get("layout") == "charuco" and _finite(sz) and _finite(sq) and sz > 0 and 0 < sq <= sz:
        add("numbers.square", "error",
            f"the square ({sq:g} mm) must be larger than the marker ({sz:g} mm)")
    # -- a forced board (cols, rows)
    f = raw.get("force")
    if f is not None:
        okf = (isinstance(f, (list, tuple)) and len(f) == 2
               and all(isinstance(c, int) and not isinstance(c, bool) for c in f))
        if not okf or min(f) < 1:
            add("settings.force", "error", f"cols / rows {f!r}: two whole numbers, 1 or more")
        elif s.get("layout") == "charuco" and min(f) < 2:
            add("settings.force", "error",
                f"a ChArUco board needs at least 2 x 2 squares (cv2 refuses {f[0]} x {f[1]})")
    # -- quiet zone
    q = s.get("quiet_modules", 1.0)
    if not _finite(q) or q < QUIET_MIN:
        add("settings.quiet_modules", "error",
            f"quiet zone {q} modules: at least {QUIET_MIN:g}")
    elif q < QUIET_LOW:
        add("settings.quiet_modules", "warn",
            f"quiet zone {q:g} modules: below {QUIET_LOW:g} reads worse")
    elif q > QUIET_MAX:
        add("settings.quiet_modules", "warn",
            f"quiet zone {q:g} modules: more than {QUIET_MAX:g} wastes the face")
    # -- cells
    if "cells" in raw and raw["cells"] is not None:
        c = raw["cells"]
        good = (isinstance(c, dict) and c.get("rule", _A.CELL_RULE) == _A.CELL_RULE
                and _A.cells_of(c) is not None)
        lo, hi = _A.MIN_STEP_M * 1000, _A.MAX_STEP_M * 1000
        legacy = "read as the legacy 0.5 mm steps"
        if not good and (isinstance(c, dict) and c.get("rule", _A.CELL_RULE) == _A.CELL_RULE
                         and c.get("of") in _A.CELL_OF):
            # the rule and its kind are known: the step is what is wrong (audit F8)
            mm = c.get("mm")
            shown = f"{mm:g}" if _finite(mm) else repr(mm)
            add("settings.cells.mm", "warn",
                f"cell {shown} mm: {lo:g} to {hi:g} mm ({legacy})")
        elif not good:
            rule = c.get("rule") if isinstance(c, dict) else None
            what = (f"rule {rule!r}" if isinstance(c, dict) and rule != _A.CELL_RULE else
                    f"kind {c.get('of')!r}" if isinstance(c, dict) else "not an object")
            add("settings.cells", "warn",
                f"cells: {what} is not a size grid this version knows (rule {_A.CELL_RULE}, "
                f"{' / '.join(_A.CELL_OF)}, {lo:g} to {hi:g} mm): {legacy}")
        elif isinstance(c.get("min_mm", 0.0), (int, float)) and c.get("min_mm", 0.0) < 0:
            add("settings.cells.min_mm", "warn", "a minimum below 0 reads as 0")
    # -- mode, op
    if s.get("mode") not in _SL.MODES:
        add("settings.mode", "error", f"unknown mode {s.get('mode')!r}: one of "
            f"{', '.join(_SL.MODES)} (or auto)")
    elif raw.get("mode") == "auto":
        add("settings.mode", "info", f"mode auto: {s['mode']} "
            f"({'a body under it' if t.has_body else 'nothing under it'})")
    if s.get("op") not in _SL.OPS:
        add("settings.op", "error", f"unknown operation {s.get('op')!r}: one of "
            f"{', '.join(_SL.OPS)}")
    # -- heights
    mode = s.get("mode") if s.get("mode") in _SL.MODES else "both"
    built = {"white": mode in ("both", "white"), "black": mode in ("both", "black")}
    legacy = has_legacy_numbers(spec)
    for k in _SL.NUMBER_KEYS:
        v = n.get(k)
        if v is None:
            continue
        if not _finite(v):
            add(f"numbers.{k}", "error", f"{k}: not a finite number")
        elif abs(v) > _SL.LIMIT_MM:
            add(f"numbers.{k}", "error", f"{k} {v:g} mm: at most {_SL.LIMIT_MM:g} mm either way")
    if not legacy:
        for colour, mn in (("white", _SL.WHITE_MIN_MM), ("black", _SL.BLACK_MIN_MM)):
            h = n.get(f"{colour}_height")
            if not built[colour] or h is None or not _finite(h):
                continue
            if h == 0:
                add(f"numbers.{colour}_height", "error",
                    f"the {colour} has no height (at least {mn:g} mm either way)")
            elif abs(h) < mn:
                add(f"numbers.{colour}_height", "warn",
                    f"{colour} height {h:g} mm is under {mn:g} mm (the dialog snaps it to "
                    f"{_SL.snap_height(h, mn):g})")
    for k in _S.LEGACY_PARAMS:
        if k in n:
            add(f"numbers.{k}", "info", f"{k}: a node made before 2026-10-08; read as "
                "Offset / Height pairs")
    # -- origin
    turn = raw.get("turn", 0)
    if _finite(turn) and int(round(turn)) % 90:
        add("settings.turn", "warn", f"Origin {turn}° is not a quarter turn: kept as laid out")
    ov = raw.get("origin_v")
    if ov is not None and ov != _OR.ORIGIN_RULE:
        add("settings.origin_v", "warn",
            f"origin rule {ov!r} is not {_OR.ORIGIN_RULE}: read as a node made before "
            "2026-10-09")
    # -- corner mark, pins
    cm = raw.get("corner_mark")
    if cm is not None and cm not in _CH.CHOICES:
        add("settings.corner_mark", "warn",
            f"corner mark {cm!r} is not one of {', '.join(_CH.CHOICES)}: none")
    pin = s.get("pin") or "none"
    if pin not in _SL.PIN_SHAPES:
        add("settings.pin", "error", f"unknown pin {pin!r}: one of {', '.join(_SL.PIN_SHAPES)}")
    elif pin != "none" and not _SL.pin_applies(mode, s.get("op", "join"), bool(t.has_body)):
        add("settings.pin", "info", "pins only on a tag printed on its own (White + black, "
            "New body): none here")
    for k, (lo, hi) in _SL.PIN_LIMITS.items():
        v = n.get(k)
        if v is None:
            continue
        if not _finite(v) or not lo <= v <= hi:
            add(f"numbers.{k}", "error", f"{k} {v} mm: {lo:g} to {hi:g} mm")
    # -- label
    lab = raw.get("label")
    if isinstance(lab, dict):
        notes = []
        ls = _L.LabelSettings.from_dict(lab, notes)
        for m in notes:
            key = m.split(":", 1)[1].strip().split(" ", 1)[0] if ":" in m else ""
            fld = f"settings.label.{key}" if key in ls.to_dict() else "settings.label"
            add(fld, "warn", m)
        for k in ("cap_mm", "nozzle_mm", "stroke_mm"):
            v = lab.get(k)
            if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float))
                                  or not math.isfinite(v) or v < 0):
                add(f"settings.label.{k}", "warn", f"label {k} {v!r}: 0 or more ({getattr(ls, k)} used)")
        if "nozzle_mm" in lab and _finite(lab["nozzle_mm"]) and lab["nozzle_mm"] <= 0:
            add("settings.label.nozzle_mm", "warn",
                f"nozzle {lab['nozzle_mm']} mm: more than 0 ({_L.NOZZLE_MM} used)")
        if ls.on and ls.cap_mm > 0:
            mc = _L.min_cap(ls.nozzle_mm, ls.stroke_mm)
            if ls.cap_mm < mc - 1e-9:
                add("settings.label.cap_mm", "warn",
                    f"letters {ls.cap_mm:g} mm are under the smallest that print with a "
                    f"{ls.nozzle_mm:g} mm nozzle ({mc:g} mm)")
        if ls.on and ls.content == "custom" and not (ls.text or "").strip():
            add("settings.label.text", "warn", "a custom label with no text")
    # -- trim
    if "trim" in raw and raw["trim"] not in (None, {}):
        tr = raw["trim"]
        if _TR.trim_of(tr) is None:
            add("settings.trim", "warn", f"trim {tr!r} is not a trim this version knows "
                f"(rule {_TR.RULE}, axes {' / '.join(_TR.AXES)}): off")
        else:
            m = tr.get("margin_mm", 0.0)
            if _finite(m) and not 0.0 <= m <= _TR.MARGIN_MAX_MM:
                add("settings.trim.margin_mm", "warn",
                    f"trim margin {m:g} mm: 0 to {_TR.MARGIN_MAX_MM:g} mm (clamped)")
    # -- how it is made (core.make), the holes rule
    for fld, lv, text in _MK.make_of(raw)[1] + _MK.holes_of(raw)[1] + _MK.shift_of(raw)[1]:
        add(fld, lv, text)
    # -- target
    if t.kind not in KINDS:
        add("target.kind", "error", f"unknown target kind {t.kind!r}: one of {', '.join(KINDS)}")
    if t.z_sign not in (1, -1):
        add("target.z_sign", "error", f"z_sign {t.z_sign}: 1 or -1")
    for k in ("w_mm", "h_mm"):
        v = getattr(t, k)
        if not _finite(v) or v <= 0:
            add(f"target.{k}", "error", f"the target's {k[0]} {v} mm: more than 0")
    for i, lp in enumerate(t.loops_mm):
        if len(lp) < 3:
            add("target.loops_mm", "error", f"loop {i} has {len(lp)} points: at least 3")
        elif any(not (_finite(u) and _finite(v)) for u, v in lp):
            add("target.loops_mm", "error", f"loop {i}: a point that is not a finite number")
    if len(t.loops_mm) > 1 and len(t.loops_mm[0]) >= 3:
        outer = t.loops_mm[0]
        for i, h in enumerate(t.loops_mm[1:], 1):
            if len(h) < 3:
                continue
            inside = [_inside(outer, p) for p in h]
            if not any(inside):
                # read even-odd it would be a second island (M6 note b)
                add("target.loops_mm", "error",
                    f"loop {i + 1} lies outside the outline: one target per face; pick the "
                    "faces one by one or together")
            elif not all(inside):
                add("target.loops_mm", "error", f"hole {i} is not inside the outer loop")
            else:
                for j, g in enumerate(t.loops_mm[1:i], 1):
                    if len(g) >= 3 and all(_inside(g, p) for p in h):
                        add("target.loops_mm", "error",
                            f"loop {i + 1} lies inside hole {j}: an island is a face of its "
                            "own (one target per face)")
                        break
    if t.body_mm is not None and not t.body_mm["z1"] > t.body_mm["z0"]:
        add("target.body_mm", "error", "the body's z1 must be above its z0")
    if t.x_ref is not None and math.hypot(*t.x_ref) < 1e-9:
        add("target.x_ref", "warn", "x_ref has no length: ignored")
    return out


def from_record(stored: dict, numbers_mm: dict, target: Target, record: Optional[dict] = None,
                name: str = "") -> TagSpec:
    """A REF node as a TagSpec: its "spec" named value as stored (the
    settings), its parameters in mm (marker_id unitless, REF numbers_of's
    reads), the target the adapter read; the key from the record (else the
    settings')."""
    key = (record or {}).get("key") or (stored or {}).get("key") or ""
    return TagSpec(settings=copy.deepcopy(stored or {}), numbers=dict(numbers_mm or {}),
                   target=target, name=name, key=key)
