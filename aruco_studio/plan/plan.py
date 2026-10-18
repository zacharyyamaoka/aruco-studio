"""plan_tag(TagSpec) -> TagPlan: the adapter contract (ARCHITECTURE 3.2, 5.3).

`plan_tag` never raises. A request with a wrong VALUE plans to a TagPlan
with `warnings` (`Issue`s on the field they are about); a refusal (nothing
fits, the board's ids run past the dictionary, the pins do not fit) is
`ok: false` with `errors` and an `error` Issue. `ok` is false only when the
tag is not built at all; an `error` Issue with `ok: true` is a part that is
not built (a refused label), as REF's dialog says it.

The order is REF evaluate()'s (plan/evaluate.py): fit on the loops, the
Origin turn, the corner mark, the label (a strip grows the tile; the cut
and the pins follow), the pins, the trim, the slabs.

How the tag is made (`settings.make`, core.make, M6a) branches once, after
`check` and before evaluate(): a printed sticker plans as its 3D twin's
fit, mark and label on a thin stock (parts `sticker` and `ink`); a tag
without the key, or 3D printed, takes REF's path untouched. `made_by` and
`rules.make` say which.

2026-10-17 (the 2D pivot): make rule 2 (the black t/2 inside the paper,
parts sticker / pocket / ink, the frame on the paper's top) adds
`data["sticker"]` (`sticker_block`) and the page lint (`sticker_issues`:
an `error` on `numbers.size` with `ok` still true, CF-6); a shifted
sticker (`settings.shift`) adds `placement.shift_mm`. A rule-1 or 3D
plan's dict is exactly what it was.

2026-10-18 (the online Studio, docs/design/online_studio_v1.md):
`settings.as_typed` (evaluate.typed_fit) adds `data["overflow_mm"]`
([x, y] per side, the tile past the rectangle) and, when it is over, an
`error` on `numbers.size` with `ok` still true (`overflow_issues`). A plan
without the key is exactly what it was.
"""
from __future__ import annotations

import copy
import json
import math
import re
from dataclasses import dataclass, field
from typing import List, Optional

from ..core import edits as _E
from ..core import form as _F
from ..core import label as _AL
from ..core import make as _MK
from ..core import origin as _OR
from ..core import settings as _S
from ..core import trim as _TR
from ..core import validate as _V
from . import evaluate as EV
from . import layers as LY
from . import record as R
from .spec import Issue, TagSpec, check, has_legacy_numbers, numbers_of, settings_of

SCHEMA = LY.SCHEMA
FONT_RULE = 1          # the pixel font of 2026-10-10 (REF never versioned it)


@dataclass
class TagPlan:
    """The JSON contract, as a dict (`data`) with the evaluate() it came
    from (`ev`, None when refused) for in-process callers."""
    data: dict
    ev: Optional[dict] = None
    settings: Optional[dict] = None
    numbers: Optional[dict] = None
    request: Optional["TagSpec"] = None

    @property
    def ok(self) -> bool:
        return bool(self.data.get("ok"))

    def __getitem__(self, k):
        return self.data[k]

    def get(self, k, default=None):
        return self.data.get(k, default)

    def to_dict(self) -> dict:
        return copy.deepcopy(self.data)

    def to_json(self) -> str:
        return json.dumps(self.data, sort_keys=True, separators=(",", ":"), allow_nan=False)


# ------------------------------------------------------------ the words

# the plan's own notes -> (field, level); the first match wins. Then REF's
# dialog routes (core.validate.ROUTES) by their row.
NOTE_ROUTES = [
    (r"has ids \d+\.\.\d+; this board needs", "numbers.marker_id", "error"),
    (r"^ids \d+\.\.\d+ exceed", "numbers.marker_id", "error"),
    (r"pins? do(es)? not fit", "numbers.pin_size", "error"),
    (r"^the white needs some height", "numbers.white_height", "error"),
    (r"^a colour needs some height", "numbers.black_height", "error"),
    (r"^origin ", "settings.turn", None),
    (r"^corner mark form: ", "settings.corner_mark", "info"),
    (r"corner mark|corner cut|triangle", "settings.corner_mark", None),
    (r"^not a rectangle", "target.loops_mm", "info"),
    (r"^trim refused: ", "settings.trim", "warn"),
    (r"^trim: cut anyway", "settings.trim", "warn"),
    (r"^trim", "settings.trim", "info"),
    (r"^(no marker fits here|nothing printable fits)", "numbers.size", "error"),
    (r"^cell multiple: ", "numbers.size", None),      # the size the cells round (audit F9)
]
LEVEL_OF_ROUTE = {"block": "error", "error": "error", "warn": "warn", "info": "info",
                  "note": "info"}


def _plain(t):
    return _V._plain(t)


def route(note: str, refused: bool = False):
    """(field, level) of one of the plan's notes."""
    text = _plain(note)
    for rx, fld, lv in NOTE_ROUTES:
        if re.search(rx, text):
            if lv is None:
                lv = "info" if _S.is_info(text) else "warn"
            return fld, lv
    for rx, anchor, lv in _V.ROUTES:
        if re.search(rx, text):
            if anchor == "@offset":
                anchor = "white_offset"
            elif anchor == "@pin":
                m = re.match(r"^pin (size|length|tol)", text)
                anchor = f"pin_{m.group(1)}" if m else "pin_tol"
            level = LEVEL_OF_ROUTE.get(lv, "warn")
            if level == "error" and not refused:
                level = "warn"
            return _V.field_of(anchor), level
    return "tag", ("info" if _S.is_info(text) else ("error" if refused else "warn"))


# a label message goes under the row its words name (audit F7): REF's dialog
# put a cap's refusal under Position when its reason did not match
LABEL_WORDS = [
    # label rule 4: a ChArUco square too small for the text is about the
    # Label itself (fewer columns or Content #id), not the letter height
    (r"\bno room in a [\d.]+ mm ChArUco square\b", "settings.label"),
    (r"^(label: )?(cap \d|letters \d|.*\beven at [\d.]+ mm letters)", "settings.label.cap_mm"),
    (r"^(label: )?(not )?on the (black|white)\b", "settings.label.place"),
    (r"^(label: )?.*\bnozzle\b.*\bneeds\b", "settings.label.nozzle_mm"),
]


def label_field(text: str, default: str) -> str:
    """The label row a label message is about, by its first clause."""
    head = re.split(r" -- |; |\. ", _plain(text), maxsplit=1)[0]
    for rx, fld in LABEL_WORDS:
        if re.search(rx, head):
            return fld
    return default


def _same_words(a: str, b: str, n: int = 48) -> bool:
    """Two messages that say the same thing: one starts with the other's
    first `n` characters ("label: " and case aside)."""
    na = re.sub(r"^label: ", "", a).strip().lower()
    nb = re.sub(r"^label: ", "", b).strip().lower()
    k = min(n, len(na), len(nb))
    return k > 0 and (na[:k] == nb[:k] or na in nb or nb in na)


def force_issue(ev, s, spec: TagSpec) -> Optional[Issue]:
    """A typed cols x rows the plan did not build (audit F2): the fit drops a
    count that does not fit (REF evaluate's _layout_rect), and on a face it
    lays out as many as fit. Said under Columns x rows, never silent."""
    f = (spec.settings or {}).get("force")
    lay = ev["layout"]
    if not f or s.get("layout") == "single" or not isinstance(f, (list, tuple)) or len(f) != 2:
        return None
    if (lay.cols, lay.rows) == (int(f[0]), int(f[1])):
        return None
    t = spec.target
    if not t.is_profile:
        return Issue("settings.force", "info",
                     f"{f[0]} × {f[1]} typed: a face lays out as many as fit, "
                     f"{lay.cols} × {lay.rows} here (a sketch profile takes a typed count)")
    unit = (f"{lay.square_m * 1000.0:.1f} mm checkers" if s.get("layout") == "charuco"
            else f"{lay.marker_m * 1000.0:.1f} mm markers")
    return Issue("settings.force", "warn",
                 f"{f[0]} × {f[1]} does not fit the {t.w_mm:g} × {t.h_mm:g} mm target at "
                 f"{unit}: using {lay.cols} × {lay.rows}")


_CELL_MIN = re.compile(r"^cell minimum: a ([\d.]+) mm cell is under the ([\d.]+) mm minimum")


def cell_min_fix(note: str, ev, spec: TagSpec) -> str:
    """The cell-minimum warn of a ChArUco board with what passes (the
    2026-10-17 audit: "a fresh default should not start with an orange
    warning" -- the warn now says the fix): the checker that gives cells of
    the minimum, and the board that fits at it here. Words only: the layout
    Auto picks is the versioned rule's, unchanged."""
    m = _CELL_MIN.match(_plain(note))
    lay = ev.get("layout")
    if not m or lay is None or getattr(lay, "kind", "") != "charuco" or not lay.square_m:
        return note
    cell, need = float(m.group(1)), float(m.group(2))
    if cell <= 0:
        return note
    sq = math.ceil(lay.square_m * 1000.0 * need / cell * 2.0 - 1e-6) / 2.0     # 0.5 mm steps
    t = spec.target
    cols, rows = int((t.w_mm + 1e-6) // sq), int((t.h_mm + 1e-6) // sq)
    lp = t.loops_mm or []
    boxy = not lp or (len(lp) == 1 and len(lp[0]) == 4)      # the count is the box's
    if cols < 2 or rows < 2:
        how = f"no ChArUco board passes here (it needs {sq:g} mm checkers): a single marker or a grid"
    elif not boxy:                                # holes, curves: the count follows the clear room
        how = f"a Checker size of {sq:g} mm or more passes"
    elif not t.is_profile:
        how = f"a Checker size of {sq:g} mm passes ({cols} × {rows} on this face)"
    else:
        how = f"{cols} × {rows} passes (a Checker size of {sq:g} mm)"
    # " — ", not "; ": the inspector's short line (the kit's shortText) cuts at
    # "; " and dropped the fix (the morning check, 2026-10-17)
    return f"{note.rstrip('.')} — {how}"


def issues_of(ev, s, n, spec: TagSpec) -> List[Issue]:
    """Every message of a built plan, on its field (ARCHITECTURE 5.6). A
    message is shown once: a label note that repeats a label Issue is dropped."""
    out: List[Issue] = []
    seen = set()

    def add(f, lv, t):
        t = re.sub(r"\s+", " ", _plain(t)).strip()
        if t and (f, t) not in seen:
            seen.add((f, t))
            out.append(Issue(f, lv, t))
    for note in ev["notes"]:
        if note.startswith(("label", "label warning")):
            continue                                    # the label's own words, below
        f, lv = route(note)
        add(f, lv, cell_min_fix(note, ev, spec))
    fi = force_issue(ev, s, spec)
    if fi is not None:
        add(fi.field, fi.level, fi.text)
    lab = ev.get("label")
    if lab is not None and lab.settings.on:
        said = []
        for i in _V.label_issues(lab, ev["mode"], True):
            fld = label_field(i.text, _V.field_of(i.anchor))
            add(fld, "error" if i.level in ("error", "block") else "warn", i.text)
            said.append(i.text)
        for t in lab.notes:
            if t.startswith("label: ") and not any(_same_words(t, x) for x in said):
                add(label_field(t, "settings.label"), "info", t)
                said.append(t)
    spec_m = ev["spec"]
    # the dialog's info lines (REF info_rows): each on its field
    add("numbers.size", "info", _F.size_line(spec_m))
    cl = _F.cells_line(spec_m, s)
    if cl:
        add("settings.cells", "info", cl)
    add("settings.turn", "info", _F._origin_line(spec_m, ev["turn"]))
    mark = ev.get("mark")
    if mark is not None and mark.note:
        add("settings.corner_mark", "info", mark.note)
    for t in _F.layer_lines(s, n, None):
        add("numbers.black_height", "info", t)
    for t in ev["plan"].notes:
        add("settings.mode", "info", t)
    if has_legacy_numbers(spec):
        add("numbers", "info", "heights read from a node made before 2026-10-08 (height / "
            "thickness / above), as Offset / Height pairs")
    return out


# ------------------------------------------------------------- the plan

def _rules(s, spec, ev, make=None):
    lab = ev.get("label") if ev else None
    return {"spec": _S.SPEC_VERSION, "make": make.rule if make is not None else None,
            "origin": s.get("origin_v") if s.get("origin_v") == _OR.ORIGIN_RULE else None,
            "cells": copy.deepcopy(s.get("cells")) if _S.cells_of(s) is not None else None,
            "label": (lab.settings.rule if lab is not None and lab.settings.on else None),
            "trim": _TR.RULE if _S.trim_setting(s) is not None else None,
            "legacy_numbers": has_legacy_numbers(spec), "font": FONT_RULE}


def _lay(lay):
    return {"kind": lay.kind, "marker_mm": LY._r(lay.marker_m * 1000.0),
            "square_mm": LY._r(lay.square_m * 1000.0), "cols": lay.cols, "rows": lay.rows,
            "separation_mm": LY._r(lay.separation_m * 1000.0),
            "margins_mm": [LY._r(v * 1000.0) for v in lay.margins_m], "fill": lay.fill,
            "notes": list(lay.notes), "badges": list(lay.badges), "ok": lay.ok,
            "dictionary": lay.dictionary, "quiet_modules": lay.quiet_modules}


def _trim(tp):
    if tp is None:
        return None
    return {"axes": tp.axes, "margin_mm": tp.margin, "outline": list(tp.outline),
            "body": list(tp.body), "keep": list(tp.keep), "column": list(tp.column()),
            "pad": tp.pad, "cut": dict(tp.cut), "refusals": list(tp.refusals),
            "notes": list(tp.notes), "forced": tp.forced, "cuts": tp.cuts,
            "face": list(tp.face) if tp.face is not None else None,
            "face_share": tp.face_share, "body_share": tp.body_share,
            "removed_mm3": tp.removed_mm3, "body_mm3": tp.body_mm3, "holes": list(tp.holes),
            "z": list(tp.z) if tp.z is not None else None}


BODY_NOMINAL_MM = 3.0      # a body whose thickness the adapter did not measure, as drawn


def _body(target, loops):
    """The body under the tag, for the views and the render: its outline in
    the pattern frame and its z range (the target's body_mm; else a nominal
    3 mm under the face, `nominal` true). None when there is no body."""
    if not target.has_body or not loops:
        return None
    b = target.body_mm
    if b:
        return {"loops": loops, "z": [b["z0"], b["z1"]], "nominal": False}
    return {"loops": loops, "z": [-BODY_NOMINAL_MM, 0.0], "nominal": True}


def writes(s, n, ev):
    """What a node of this plan stores back (REF settle), as the changes to
    the request's settings / numbers. `jo_v` is the adapter's own key and
    stays out (settle keeps it as it is, 2 / 1)."""
    s2, n2 = _E.settle(s, n, ev)
    w = {k: s2[k] for k in ("parts", "v", "pin", "size_auto")}
    if "trim" in s:
        w["trim"] = s2.get("trim")                    # None: settle drops it
    return {"settings": w, "numbers": {"size": n2["size"], "square": n2["square"]}}


def settle(stored: dict, numbers: dict, plan: "TagPlan") -> tuple:
    """REF settle(s, n, ev) from a plan: the stored settings / numbers with
    the plan's writes, the trim dropped when it reads as off, `jo_v` by
    REF's rule. -> (settings, numbers)."""
    s, n = dict(stored), dict(numbers)
    w = plan.data["writes"]
    for k, v in w["settings"].items():
        if k == "trim" and v is None:
            s.pop("trim", None)
        else:
            s[k] = copy.deepcopy(v)
    n.update(w["numbers"])
    s["jo_v"] = 2 if _S.has_frame_sketch(s) else 1
    return s, n


def refused(spec: TagSpec, issues: List[Issue], errors: List[str]) -> TagPlan:
    return TagPlan({"schema": SCHEMA, "ok": False, "errors": list(errors), "marker": None,
                    "layout": None, "placement": None, "parts": [], "layers": [],
                    "combines": [], "frames": None, "ids": [], "labels": [], "mark": None,
                    "label": None, "trim": None, "pins": [], "guides": None,
                    "warnings": [i.to_dict() for i in issues],
                    "rules": {"spec": _S.SPEC_VERSION, "font": FONT_RULE},
                    "writes": None, "record": None, "notes": [], "node_warning": "",
                    "digest": None, "name": spec.name, "key": spec.key})


def plan_tag(spec, base=None) -> TagPlan:
    """TagSpec (or its dict) -> TagPlan. Never raises."""
    try:
        if isinstance(spec, dict):
            spec = TagSpec.from_dict(spec)
        return _plan(spec, base)
    except Exception as exc:                       # noqa: BLE001
        nm = getattr(spec, "name", "") if not isinstance(spec, dict) else ""
        ky = getattr(spec, "key", "") if not isinstance(spec, dict) else ""
        path = getattr(exc, "path", None)
        fld = path if path else "tag"
        t = TagSpec(name=nm or "", key=ky or "")
        return refused(t, [Issue(fld, "error", f"{type(exc).__name__}: {exc}"[:300])],
                       [f"{type(exc).__name__}: {exc}"[:300]])


def sticker_inputs(spec: TagSpec, s: dict, n: dict, make):
    """A sticker's settings and numbers (its 3D twin's: White + black, New
    body, a flush ink inlay on the stock) and what that changed, as Issues."""
    s2, notes = _MK.twin_settings(make, s)
    out = [Issue(f, lv, t) for f, lv, t in notes]
    if s.get("pin") not in (None, "none"):
        out.append(Issue("settings.pin", "info", "a sticker has no locating pins"))
    lab = s2.get("label")
    if isinstance(lab, dict) and lab.get("on") and lab.get("place") == "white" \
            and not _MK.has_white(make):
        s2["label"] = dict(lab, place="auto")
        out.append(Issue("settings.label.place", "warn",
                         "no white outside the quiet zone (Perimeter = Marker): the label goes "
                         "on the black"))
    if make.perimeter == "profile" and s2.get("corner_mark") == "cut":
        s2["corner_mark"] = "none"
        out.append(Issue("settings.corner_mark", "info",
                         "a Profile sticker keeps its outline: no corner cut (Perimeter = Marker "
                         "cuts one)"))
    return s2, _MK.twin_numbers(make, n), out


def _plan(spec: TagSpec, base=None) -> TagPlan:
    issues = check(spec)
    errs = [i for i in issues if i.level == "error"]
    if errs:
        return refused(spec, issues, [i.text for i in errs])
    s = settings_of(spec)
    n = numbers_of(spec, s)
    make, _notes = _MK.make_of(spec.settings or {})        # its notes are check()'s
    sticker = make if make.sticker else None
    if sticker is not None:
        s, n, more = sticker_inputs(spec, s, n, make)
        issues += more
    try:
        ev = EV.evaluate(spec.target, s, n, base=base, name=spec.name, sticker=sticker)
        optical = R.optical_of_ev(ev, spec.key or "tag")
    except Exception as exc:                       # noqa: BLE001
        text = str(exc) if isinstance(exc, ValueError) else f"{type(exc).__name__}: {exc}"
        f, _lv = route(text, refused=True)
        return refused(spec, issues + [Issue(f, "error", text[:400])], [text[:400]])
    return build(spec, s, n, ev, optical, issues, make=make)


# autosize's printability note is about an FDM nozzle (MIN_MODULE_M: three
# 0.4 mm lines). WHY dropped for a sticker: Zach, 2026-10-18 -- an inkjet
# preset said "hard to print with a 0.4 mm nozzle". A sticker's own minimum
# is its preset's cell rule ("cell minimum: ..."), which still shows.
FDM_NOZZLE_NOTE = "hard to print with a 0.4 mm nozzle"

# the rows a sticker does not have (its heights are fixed): their notes go
STICKER_QUIET = ("numbers.white_offset", "numbers.white_height", "numbers.black_offset",
                 "numbers.black_height", "settings.mode", "settings.op", "settings.pin")


def _crosses(poly_pts, rect) -> bool:
    """Does a polygon (a hole) overlap a rect by some area?"""
    kept = _TR.clip(list(poly_pts), tuple(rect))
    if len(kept) < 3:
        return False
    a = 0.0
    for i in range(len(kept)):
        a += kept[i - 1][0] * kept[i][1] - kept[i][0] * kept[i - 1][1]
    return abs(a) / 2.0 > 1e-6


def extra_issues(spec: TagSpec, s: dict, ev: dict, fr: dict, make, guides: dict) -> List[Issue]:
    """The M6a messages: holes crossed under Holes: ignore, a Profile
    sticker's extra cuts, a ChArUco label off its black square."""
    out: List[Issue] = []
    raw = spec.settings or {}
    loops = guides.get("target") or []
    holes = loops[1:] if len(loops) > 1 else []
    if raw.get("holes") == "ignore" and holes:
        if make is not None and make.sticker:
            rect = _AL.sticker_rect(ev["spec"])
            for k, h in enumerate(holes, 1):
                if _crosses(h, rect):
                    out.append(Issue("settings.holes", "warn",
                                     f"the marker crosses hole {k}: cut the hole out after "
                                     "sticking, or Avoid"))
        else:
            rect = fr["tile_rect"] or _AL.sticker_rect(ev["spec"])
            k = sum(1 for h in holes if _crosses(h, rect))
            if k:
                out.append(Issue("settings.holes", "warn",
                                 f"the tile covers {k} hole{'s' if k != 1 else ''}"))
    if make is not None and make.sticker and make.perimeter == "profile" and holes:
        k = len(holes)
        out.append(Issue("settings.make.perimeter", "info",
                         f"the outline has {k} hole{'s' if k != 1 else ''}: {k} extra cut"
                         f"{'s' if k != 1 else ''}"))
    lab = raw.get("label")
    if s.get("layout") == "charuco" and isinstance(lab, dict) and lab.get("on"):
        if lab.get("place") == "white":
            out.append(Issue("settings.label.place", "warn",
                             "a ChArUco label belongs in a black square"))
        elif lab.get("row") in ("bottom", "top", "both"):
            out.append(Issue("settings.label.row", "warn",
                             "a ChArUco label belongs in a black square"))
    return out


def _box(pts):
    us = [float(p[0]) for p in pts]
    vs = [float(p[1]) for p in pts]
    return (min(us), min(vs), max(us), max(vs))


def _inside_area(outer, rect) -> bool:
    """Does `rect` lie inside the polygon `outer` (by area, 1e-4 mm2)?"""
    kept = _TR.clip(list(outer), tuple(rect))
    if len(kept) < 3:
        return False
    a = abs(sum(kept[i - 1][0] * kept[i][1] - kept[i][0] * kept[i - 1][1]
                for i in range(len(kept)))) / 2.0
    return a >= (rect[2] - rect[0]) * (rect[3] - rect[1]) - 1e-4


def sticker_size_mm(guides: dict):
    """A sticker's size on paper: its cut outline's box (w, h) mm."""
    cut = guides.get("cut_line") or {}
    outer = cut.get("outer") or []
    if len(outer) < 3:
        u0, v0, u1, v1 = guides["sticker"]
    else:
        u0, v0, u1, v1 = _box(outer)
    return (u1 - u0, v1 - v0)


def sticker_block(make, guides: dict) -> dict:
    """plan.data["sticker"] of a rule-2 sticker (2026-10-17): what the
    paper and the black are, where the frame sits, and the page it prints
    on -- what an adapter's sticker node builds from (docs/status/2d-core.md)."""
    t = float(make.thickness_mm)
    lo, hi = make.ink_z
    w, h = sticker_size_mm(guides)
    fit = _MK.page_fit(w, h, make) or {}
    return {"rule": make.rule, "thickness_mm": LY._r(t), "paper_z_mm": [0.0, LY._r(t)],
            "ink_z_mm": [LY._r(lo), LY._r(hi)], "frame_z_mm": LY._r(make.top_mm),
            "perimeter": make.perimeter,
            "page": {"page": make.page, "margin_mm": LY._r(make.page_margin_mm),
                     "size_mm": [LY._r(w), LY._r(h)], "fits": bool(fit.get("fits")),
                     "how": fit.get("how"), "over_mm": fit.get("over_mm"),
                     "printable_mm": fit.get("area_mm")}}


def sticker_issues(spec: TagSpec, ev: dict, fr: dict, make, guides: dict) -> List[Issue]:
    """The 2026-10-17 messages: a rule-2 sticker's paper and page (the red
    page lint, CF-6: built anyway), Auto's cap, and a Shift that runs off
    the face. Nothing for a tag without rule 2 or a shift."""
    out: List[Issue] = []
    raw = spec.settings or {}
    sh, notes = _MK.shift_of(raw)
    if "shift" in raw and not (make is not None and make.sticker):
        if sh != (0.0, 0.0):
            out.append(Issue("settings.shift", "info",
                             "Shift moves stickers only: a 3D tag stays where the fit puts it "
                             "(3D is kept as it is, CF-13)"))
    if make is None or not make.sticker:
        return out
    if make.inset:
        t = float(make.thickness_mm)
        out.append(Issue("settings.make.thickness_mm", "info",
                         f"the black is printed {t / 2.0:g} mm into the {t:g} mm paper (t/2, "
                         f"make rule 2); the tag frame sits on the paper's top, {t:g} mm over "
                         "the face"))
        w, h = sticker_size_mm(guides)
        fit = _MK.page_fit(w, h, make)
        cap = ev.get("page_cap")
        if cap and cap.get("capped"):
            a, b = cap["from_mm"]
            c, d = cap["to_mm"]
            out.append(Issue("numbers.size", "info",
                             f"Auto size: capped by the page -- the face holds a {a:.1f} × "
                             f"{b:.1f} mm sticker, {_MK.page_words(make.page)} less "
                             f"{make.page_margin_mm:g} mm margins prints {c:.1f} × {d:.1f} mm "
                             f"({cap['how']})"))
        if fit is not None and not fit["fits"]:
            fld = "settings.make.perimeter" if make.perimeter == "profile" else "numbers.size"
            text = _MK.lint_text(fit, w, h)
            if make.perimeter == "profile":
                text += " (Perimeter = Profile: the paper is the whole outline; Marker cuts the marker only)"
            out.append(Issue(fld, "error", text))
        elif fit is not None and fit["how"] not in (None, "portrait"):
            out.append(Issue("numbers.size", "info",
                             f"fits {_MK.page_words(make.page)} {fit['how'].replace('portrait, ', '')}"
                             " only: the sheet turns it (or print landscape)"))
    if sh != (0.0, 0.0):
        loops = guides.get("target") or []
        if loops:
            outer = [tuple(p) for p in loops[0]]
            if make.perimeter == "profile":
                rect = tuple(guides["sticker"])
                if not _inside_area(outer, rect):
                    out.append(Issue("settings.shift", "warn",
                                     "the shifted marker runs off the outline: the paper is cut "
                                     "along the outline, the marker with it"))
            else:
                cut = guides.get("cut_line") or {}
                rect = tuple(cut.get("rect") or guides["sticker"])
                if not _inside_area(outer, rect):
                    out.append(Issue("settings.shift", "warn",
                                     "the shifted sticker runs off the face: shift it back, or "
                                     "Perimeter = Profile cuts the paper along the face"))
            if raw.get("holes") != "ignore":
                rect = tuple(guides["sticker"])
                for k, hl in enumerate(loops[1:], 1):
                    if _crosses(hl, rect):
                        out.append(Issue("settings.shift", "warn",
                                         f"the shifted marker covers hole {k}"))
    return out


def overflow_issues(spec: TagSpec, ev: dict) -> List[Issue]:
    """`settings.as_typed` (2026-10-18): a typed size that does not fit the
    rectangle is drawn as typed and flagged red on its row, built anyway
    (calib.io's linter: "it won't block you, it may just throw a warning")."""
    ox, oy = ev.get("overflow_mm") or (0.0, 0.0)
    if max(ox, oy) <= 1e-6:
        return []
    t = spec.target
    by = [f"{2.0 * v:.1f} mm {w}" for v, w in ((ox, "wider"), (oy, "taller")) if v > 1e-6]
    return [Issue("numbers.size", "error",
                  f"{' and '.join(by)} than the {t.w_mm:g} × {t.h_mm:g} mm rectangle: drawn as "
                  "typed (a smaller size, or Auto, fits it)")]


def build(spec: TagSpec, s: dict, n: dict, ev: dict, optical=None, issues=(),
          make=None) -> TagPlan:
    """The TagPlan of an evaluate() result (plan/variants.py builds a copy's
    plan from its template's this way). `make` (core.make.Make): a printed
    sticker builds its two parts."""
    issues = list(issues)
    if make is None:
        make = _MK.make_of(spec.settings or {})[0]
    sticker = make.sticker
    if optical is None:
        optical = R.optical_of_ev(ev, spec.key or "tag")
    target = spec.target
    fr = LY.pattern_frames(ev, target)
    guides = LY.guides(ev, fr, target, ev["base"])
    if sticker:
        guides["cut_line"] = LY.cut_line(ev, fr, target, make)
        layers = LY.sticker_layers(ev, n, fr, make, guides["cut_line"])
    else:
        lb = LY.LayerBuilder(ev, n, fr)
        layers = lb.build()
    parts = LY.sticker_parts(make) if sticker else None
    guides["target_ignored"] = (guides["target"][1:] if (spec.settings or {}).get("holes")
                                == "ignore" else [])
    lab = ev.get("label")
    lay = ev["layout"]
    pl = ev.get("placement")
    _o, x, _y, _z = ev["tag"]
    xt = fr["Tv"](x)
    xf = fr["Tv"](ev["x_fit"])
    o_t = fr["T"](fr["fo"])
    placement = {"cx_mm": LY._r(o_t[0]), "cy_mm": LY._r(o_t[1]),
                 "angle_deg": LY._r(math.degrees(math.atan2(xt[1], xt[0]))),
                 "fit_angle_deg": LY._r(math.degrees(math.atan2(xf[1], xf[0]))),
                 "turn_deg": int(ev["turn"]), "lift_mm": LY._r(ev["lift_cm"] * 10.0),
                 "fit": ({"cx_mm": LY._r(pl["cx"] * 1000.0), "cy_mm": LY._r(pl["cy"] * 1000.0),
                          "angle_deg": pl.get("angle_deg", 0.0)} if pl else None)}
    labels = []
    if lab is not None and lab.kind != "none":
        for p in lab.parts:
            labels.append({"slot": p.slot, "text": "|".join(p.lines), "cap_mm": LY._r(p.cap),
                           "stroke_mm": LY._r(p.stroke)})
    pins = []
    cu, cv = fr["pin_centre"]
    for p in ev["pins"]:
        if p["kind"] == "circle":
            pins.append({"kind": "circle", "c": [LY._r(cu + p["c"][0]), LY._r(cv + p["c"][1])],
                         "r": LY._r(p["r"])})
        else:
            pins.append({"kind": "poly", "pts": LY._pts([(cu + a, cv + b) for a, b in p["pts"]])})
    rec = R.record(ev, key=spec.key or "tag", component="",
                   fusion={"make": make.to_dict()} if sticker else None)
    found = issues_of(ev, s, n, spec)
    if sticker:
        found = [i for i in found if i.field not in STICKER_QUIET
                 and FDM_NOZZLE_NOTE not in i.text]
    found += extra_issues(spec, s, ev, fr, make, guides)
    found += sticker_issues(spec, ev, fr, make, guides)
    found += overflow_issues(spec, ev)
    w = writes(s, n, ev)
    if sticker:
        w["settings"].update(parts=list(parts), pin="none")
        w["settings"].pop("trim", None)
    data = {"schema": SCHEMA, "ok": True, "errors": [],
            "made_by": make.by,
            "marker": ev["spec"].to_dict(), "layout": _lay(lay), "placement": placement,
            "parts": list(parts) if sticker else list(ev["plan"].parts),
            "layers": [l.to_dict() for l in layers],
            "combines": LY.sticker_combines(make) if sticker else LY.combines(ev["plan"]),
            "frames": LY.frames_dict(ev, fr, optical),
            "ids": list(ev["spec"].ids), "labels": labels,
            "mark": R.mark_record(ev), "label": R.label_record(ev), "trim": _trim(ev.get("trim")),
            "pins": pins, "guides": guides,
            "warnings": [i.to_dict() for i in issues + found],
            "rules": _rules(s, spec, ev, make), "writes": w, "record": rec,
            "notes": list(ev["notes"]), "node_warning": R.node_warning(ev),
            "digest": R.ev_digest(ev), "name": spec.name, "key": spec.key,
            "body": _body(target, LY.guides_target(ev, fr, target)),
            "slabs": _sticker_slabs(make) if sticker else {
                      "white": ev["plan"].layers.white, "black": ev["plan"].layers.black,
                      "pattern": list(ev["plan"].layers.pattern),
                      "surface": ev["plan"].layers.surface, "depth": ev["plan"].layers.depth,
                      "raise": ev["plan"].layers.raise_, "recess": ev["plan"].layers.recess,
                      "pocket": ev["plan"].pocket, "pin": ev["plan"].pin,
                      "recesses": [[w, list(sl)] for w, sl in ev["plan"].recess]}}
    if sticker and make.inset:
        data["sticker"] = sticker_block(make, guides)
    if ev.get("shift_mm"):
        data["placement"]["shift_mm"] = [LY._r(v) for v in ev["shift_mm"]]
    if "overflow_mm" in ev:                        # settings.as_typed only
        data["overflow_mm"] = [LY._r(v) for v in ev["overflow_mm"]]
    data = json.loads(json.dumps(data, allow_nan=False))
    return TagPlan(data, ev=ev, settings=s, numbers=n, request=spec)


def _sticker_slabs(make) -> dict:
    t = float(make.thickness_mm)
    if make.inset:
        lo, hi = make.ink_z
        return {"white": [0.0, t], "black": [lo, hi], "pattern": [lo, hi], "surface": hi,
                "depth": make.ink_mm, "raise": 0.0, "recess": 0.0, "pocket": [lo, hi],
                "pin": None, "recesses": []}
    top = t + _MK.INK_MM
    return {"white": [0.0, t], "black": [t, top], "pattern": [t, top], "surface": top,
            "depth": _MK.INK_MM, "raise": 0.0, "recess": 0.0, "pocket": None, "pin": None,
            "recesses": []}


BODY_ROLES = {"sticker": ("paper", "white"), "pocket": ("pocket", "none"), "ink": ("black", "black")}


def plan_sticker(spec_or_plan) -> Optional[dict]:
    """What a CAD adapter's sticker node builds (2026-10-17; the Fusion
    sticker node, M7.4): a sticker's TagPlan regrouped by body, in build
    order, or None for a tag that is not a printed sticker (or not built).
    `spec_or_plan`: a TagSpec, its dict, or a TagPlan / its dict.

    -> {"rule": 1 | 2, "thickness_mm": t, "bodies": [{"part", "role"
    ("paper" / "pocket" / "black"), "op" ("new" / "cut"), "into" (None /
    "sticker"), "colour", "z_mm": [lo, hi], "steps": [{"name", "step"
    ("add" / "sub"), "z_mm", "polygons": [{"outer", "holes"}]}]}], "frame":
    {"opencv": 4x4, "opencv_target": 4x4, "pattern_in_target": 4x4, "z_mm"},
    "cut_line", "page" (rule 2: plan.sticker.page), "lint": [the error
    Issues, the red rows], "record_make"}. All mm, the pattern frame (the
    pattern's centre on the face, z out of it).

    Rule 2: `sticker` [0, t] New body (the cut outline), `pocket` [t/2, t]
    CUT from it (the black's footprint), `ink` [t/2, t] New body, black.
    Rule 1: `sticker` [0, t], `ink` [t, t + 0.01]. A step "sub" is a cut
    tool of its own solid (REF part_body's order), made MARK_PAD past the
    slab."""
    try:
        if isinstance(spec_or_plan, TagPlan):
            d = spec_or_plan.data
        elif isinstance(spec_or_plan, dict) and "layers" in spec_or_plan and "ok" in spec_or_plan:
            d = spec_or_plan
        else:
            d = plan_tag(spec_or_plan).data
    except Exception:                              # noqa: BLE001
        return None
    if not d.get("ok") or d.get("made_by") != "sticker":
        return None
    comb = {c["part"]: c for c in d["combines"]}
    bodies = []
    for part in d["parts"]:
        steps = [{"name": L["name"], "step": L["step"], "z_mm": list(L["z"]),
                  "polygons": L["polygons"]} for L in d["layers"] if L["part"] == part]
        adds = [s["z_mm"] for s in steps if s["step"] == "add"]
        role, colour = BODY_ROLES.get(part, (part, "none"))
        c = comb.get(part, {})
        bodies.append({"part": part, "role": role, "op": c.get("op", "new"),
                       "into": c.get("into"), "colour": colour,
                       "z_mm": [min(z[0] for z in adds), max(z[1] for z in adds)] if adds else None,
                       "steps": steps})
    fr = d["frames"]
    rec = (d.get("record") or {}).get("fusion") or {}
    t = (d.get("sticker") or {}).get("thickness_mm")
    if t is None:
        t = next((b["z_mm"][1] for b in bodies if b["part"] == "sticker"), None)
    return {"rule": d["rules"].get("make"), "thickness_mm": t, "bodies": bodies,
            "frame": {"opencv": fr["opencv"], "opencv_target": fr["opencv_target"],
                      "pattern_in_target": fr["pattern_in_target"], "z_mm": fr["surface_mm"]},
            "cut_line": d["guides"].get("cut_line"),
            "page": (d.get("sticker") or {}).get("page"),
            "lint": [w for w in d["warnings"] if w["level"] == "error"],
            "record_make": rec.get("make")}


def validate(spec) -> List[dict]:
    """/api/validate: the checks and the plan's own Issues."""
    p = plan_tag(spec)
    return p.data["warnings"]
