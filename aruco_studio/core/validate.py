"""Per-field messages: the Issue model, the routes from the info lines to
the rows, and the summary line.

Ported from REF (cad-exporter c8216ff): `ArucoMarkers/bam_fusion_ui.py`
(Issue, worst, head_of, summary_text, the colours; the Validator's model)
and `aruco_extrude_ui.py` (ROUTES, classify, the label / trim issues). The
functions under "verbatim" are REF's bodies unchanged.

An Issue's `anchor` is the dialog row it belongs to (REF's input ids);
`field` is the same place as a TagSpec key path (docs/ARCHITECTURE.md 5.6),
from `ANCHOR_FIELD`, so the Fusion dialog and the Studio's inspector name
the same field. `validate(spec, plan)` (one function from a TagPlan's notes
to Issues) needs the plan: it is M2's (plan/spec.check + this model).

Adapted (REF read Fusion's command inputs or the dialog's state):

| Here | REF | Took from the dialog |
|---|---|---|
| `label_issues(lab, mode, on)` | `label_issues(inputs, ev)` | the Label row's on, `_X.mode` |
| `trim_issues(pairs)` | `trim_issues(inputs, ev)` | the cmd's (input id, text) pairs |
| `RowModel` | `Validator` | what `show()` writes into the rows and the summary, without the rows |
"""
from __future__ import annotations

import html as _h
import re
from dataclasses import dataclass
from typing import Dict, List

from ._ref_compat import aruco_core


# -------------------------------------------------- verbatim from REF ArucoMarkers/bam_fusion_ui.py

LEVELS = ("block", "error", "warn", "info")


RANK = {lv: i for i, lv in enumerate(LEVELS)}


# message colours per Fusion theme (the dark dialog body is #3b4453: dark
# blue on it is unreadable -- seen 2026-10-16)
PALETTES = {
    "light": {"block": "#cc0000", "error": "#cc0000", "warn": "#c24e00", "info": "#777777",
              "note": "#0a66c2", "ok": "#3f7f3f"},
    "dark": {"block": "#ff7b72", "error": "#ff7b72", "warn": "#f0a35e", "info": "#9aa3ad",
             "note": "#9ccbf5", "ok": "#7fc77f"},
}


COLOUR = dict(PALETTES["light"])


def set_theme(name):
    """The message colours for Fusion's light ("light") or dark ("dark")
    theme (GeneralPreferences.userInterfaceTheme)."""
    COLOUR.update(PALETTES.get(name, PALETTES["light"]))
    return dict(COLOUR)


SIGN = {"block": "⚠ ", "error": "⚠ ", "warn": "⚠ ", "info": "", "note": ""}


MSG_SUFFIX = "__msg"


def html(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


@dataclass
class Issue:
    """One message about one row. anchor: the input id it is about ("" = the
    whole dialog: the summary only). level: block (OK off) / error (that
    part not built) / warn / info (never counted). note: info shown in blue
    (a transient "what just changed")."""
    anchor: str
    level: str
    text: str
    note: bool = False
    detail: str = ""            # the tooltip's words when the row shows a short form

    @property
    def counts(self):
        return self.level != "info"


def worst(issues):
    lv = [i.level for i in issues if i.counts]
    return min(lv, key=lambda x: RANK[x]) if lv else None


def head_of(text, n=42):
    """A message's first clause (a general issue's name in the summary)."""
    import re
    h = re.split(r" \(| -- |: |; ", text or "", maxsplit=1)[0].strip()
    return h if len(h) <= n else h[:n - 1] + "…"


def summary_text(issues, names, tabs, ok_text="", limit=3):
    """The summary line (html): "⚠ OK is off -- Size (Marker): <why>" while a
    blocking issue remains, "⚠ 2 issues: Size (Marker) · Label position
    (Label)", or the ok text in grey."""
    counted = sorted((i for i in issues if i.counts), key=lambda i: RANK[i.level])
    if not counted:
        return f"<span style='color:{COLOUR['ok']}'>{html(ok_text)}</span>" if ok_text else ""

    def where(i):
        if not i.anchor:
            return ""
        nm = names.get(i.anchor) or i.anchor
        tab = tabs.get(i.anchor)
        return f"{nm} ({tab})" if tab else nm
    c = COLOUR[counted[0].level]
    if counted[0].level == "block":
        first = counted[0]
        w = where(first)
        txt = f"⚠ OK is off -- {w + ': ' if w else ''}{first.text}"
        rest = len(counted) - 1
        if rest:
            txt += f" (+{rest} more)"
        return f"<span style='color:{c}'>{html(txt)}</span>"
    seen = []
    for i in counted:
        w = where(i) or head_of(i.text)
        if w not in seen:
            seen.append(w)
    n = len(counted)
    head = f"⚠ {n} issue{'s' if n != 1 else ''}: "
    body = " · ".join(seen[:limit]) + (f" · +{len(seen) - limit}" if len(seen) > limit else "")
    return f"<span style='color:{c}'>{html(head + body)}</span>"


MAX_ROWS = 3


def rows_for(text, chars, most=MAX_ROWS):
    return max(1, min(most, -(-len(text) // max(10, chars))))


def fit_text(text, chars, rows):
    """`text` cut to fit `rows` lines of about `chars` characters, so a
    message row never scrolls (Fusion 2026-10-16: a refused label's words
    took four lines in a three-row box and the box scrolled). What goes
    first: asides in brackets, then whole sentences from the end (" …" says
    there is more), then words ("…"). The text itself when it fits."""
    import re
    budget = max(10, chars) * max(1, rows)
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(t) <= budget:
        return t
    t = re.sub(r"\s*\([^()]*\)", "", t)
    if len(t) <= budget:
        return t
    kept = ""
    for part in re.split(r"(?<=[.;])\s+", t):
        cand = (kept + " " + part).strip()
        if len(cand) + 2 > budget:
            break
        kept = cand
    if kept:
        kept = kept.rstrip(" ;,:")
        return kept + (" …" if kept.endswith(".") else "…")
    cut = t[:budget - 1]
    space = cut.rfind(" ")
    if space > budget // 2:
        cut = cut[:space]
    return cut.rstrip(" ;,:") + "…"


class K:
    """REF's `K` (bam_fusion_ui, as aruco_extrude_ui imported it)."""
    Issue = Issue


# -------------------------------------------------- verbatim from REF ArucoMarkers/aruco_extrude_ui.py

# an anchor that is hidden (Start = From face hides the offsets): its message
# goes to the next one shown
FALLBACK = {"white_offset": "start", "black_offset": "start", "white": "mode",
            "black": "mode", "pin_tol": "mode", "label_side": "label_place",
            "label_dy": "label_place", "label_cap": "label_place",
            "label_force": "label_place", "square": "size", "cell_mm": "cells",
            "trim_margin": "trim", "start": "mode"}


# today's info lines -> (row, level); the first that matches wins. Levels:
# block = OK off, error = not built, warn, info (not counted)
ROUTES = [
    (r"^(no marker fits here|the profile has no curves|the face is gone|the face or profile it "
     r"was made on is gone)", "size", "block"),
    (r"^ids \d+\.\.\d+ exceed", "marker_id", "block"),
    (r"^cell minimum:", "size", "warn"),
    (r"^module .*< ?1\.2 mm", "size", "warn"),
    (r"^nothing printable fits", "size", "warn"),
    (r"^default raised to", "size", "info"),
    (r"clamped", "size", "warn"),
    (r"^only one .* marker fits", "layout", "warn"),
    (r"inner corner", "layout", "warn"),
    (r"fit, but .* has \d+ ids", "dictionary", "warn"),
    (r"^White height", "white", "warn"),
    (r"^Black height", "black", "warn"),
    (r"^offset .* past the limit", "@offset", "warn"),
    (r"^pin (size|length|tol)", "@pin", "warn"),
    (r"^the pin stops", "pin_tol", "warn"),
    (r"^the white (starts|goes)", "white_offset", "warn"),
    (r"^the black (floats|is recessed|pokes)", "black_offset", "warn"),
    (r"^the black goes", "black", "warn"),
    (r"^a pinned tag prints", "black", "warn"),
    (r"^the white (floats|is recessed)", "white_offset", "warn"),
    (r"^the black (floats|is recessed) .* the face", "black_offset", "warn"),
    (r"^white border .* not whole lines", "quiet", "warn"),
    (r"^Min cell '", "cell_min", "warn"),
    (r"^the white tile is the area's box", "mode", "warn"),
    (r"belongs to the external reference", "target", "warn"),
    (r"^Auto size would build", "auto", "warn"),
    (r"^(saved as preset|preset '.*' (updated|deleted))", "preset_row", "info"),
    (r"^(not saved|not updated|not deleted|PrusaSlicer profile not imported|presets could not "
     r"be read|Update overwrites|only your own presets|preset: )", "preset_row", "warn"),
    (r"^(Preset '|Imported '|This tag's own settings back)", "preset_row", "note"),
]


def _plain(s):
    return _h.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


PRESET_EVENTS = ("preset", "preset_v2", "preset_library", "library", "preset_import")


def _short(text, n=150):
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= n else text[:n - 1] + "…"


def _level_of(line):
    m = re.search(r"color:\s*(#[0-9a-fA-F]{3,6})", line)
    c = (m.group(1).lower() if m else "")
    if c in ("#c00", "#cc0000"):
        return "red"
    if c in ("#c60", "#d45500", "#cc6600"):
        return "warn"
    if c in ("#06c", "#0a66c2"):
        return "note"
    if c in ("#888", "#888888"):
        return "grey"
    return "info"


def classify(lines, changed=""):
    """Today's info lines -> [Issue]. Label and Trim lines are left to their
    structured sources (label_issues, trim)."""
    out = []
    for ln in lines:
        kind = _level_of(ln)
        text = _plain(ln)
        if not text or kind in ("grey", "info") and not text.startswith("Preset '"):
            continue
        if text.startswith(("Label ", "Shown in orange", "Move it", "Tick Auto size",
                            "Try another", "Try On the white", "Untick Build anyway")):
            continue                                # label_issues has them
        if text.startswith(("Trim refused", "Trim margin", "cut anyway although", "it would:",
                            "Trim excess", "Trim ")):
            continue                                # trim_issues has them
        anchor, routed = "", None
        for rx, a, lv in ROUTES:
            if re.search(rx, text):
                anchor, routed = a, lv
                break
        if anchor == "@offset":
            anchor = changed if changed in ("white_offset", "black_offset") else "white_offset"
        elif anchor == "@pin":
            m = re.match(r"^pin (size|length|tol)", text)
            anchor = f"pin_{m.group(1)}" if m else "pin_tol"
        note = kind == "note" or routed == "note"
        detail = ""
        if note:
            level = "info"
            text, detail = _short_note(text), text
        elif routed is not None:
            level = routed
        else:
            level = "error" if kind == "red" else "warn"
        out.append(K.Issue(anchor, level, _short(text), note=note, detail=detail))
    return out


def _short_note(text):
    """"Preset 'Default': a → b, c → d, …" -> "Preset 'Default' applied · 8
    changes" (one line; the whole list is the row's tooltip)."""
    head, sep, rest = text.partition(": ")
    if not sep or "→" not in rest:
        return text
    n = rest.count("→")
    more = re.search(r"\+(\d+) more", rest)
    n += int(more.group(1)) if more else 0
    verb = "" if head.startswith(("Imported", "This tag")) else " applied"
    return f"{head}{verb} · {n} change{'s' if n != 1 else ''}"


# ---------------------------------------- adapted: the dialog's values as arguments

def label_issues(lab, mode="both", on=True):
    """REF label_issues(inputs, ev): the label's own words, under the row it
    is about. `lab` = the plan's Label, `mode` = REF's _X.mode, `on` = the
    Label row's checkbox."""
    if not on or lab is None:
        return []
    AL = aruco_core.module("aruco_label")
    try:
        lines = AL.describe(lab, mode or "both")
    except Exception:                              # noqa: BLE001
        return []
    errs = [t for lv, t in lines if lv == "error"]
    warns = [t for lv, t in lines if lv == "warn"]
    if not errs and not warns:
        return []
    s = lab.settings
    by_hand = bool(getattr(s, "manual", False) or getattr(s, "nudged", False))
    reason = getattr(lab, "reason", "") or ""
    pv = getattr(lab, "preview", None)
    if lab.kind == "none":
        if "under the smallest" in reason or "nozzle" in reason:
            anchor = "label_cap"
        elif by_hand and not reason:
            anchor = "label_dy"
        elif pv is not None and getattr(pv, "kind", "") == "white":
            anchor = "label_side"
        elif pv is None and s.content == "custom" and not (s.text or "").strip():
            anchor = "label_content"
        else:
            anchor = "label_place"
        text = errs[0] if errs else warns[0]
        if len(errs + warns) > 1:
            text += " " + (warns[-1] if warns else "")
        return [K.Issue(anchor, "error", _short(text, 200))]
    return [K.Issue("label_force", "warn", _short((warns or errs)[0], 200))]


def trim_issues(pairs):
    """REF trim_issues(inputs, ev) of aruco_extrude_ui: the Trim helper's
    (input id, text) pairs (core.form.trim_issues) as blocking Issues."""
    return [K.Issue(cid, "block", _short(text, 200)) for cid, text in pairs or ()]


# ------------------------------------------------------- the rows, as a model

class RowModel:
    """REF Validator without Fusion: which rows show which messages, and the
    summary line. `rows` are the anchors that have a message row; `alias`
    maps an anchor to the row it shares; `visible(anchor)` says whether a
    row is shown (REF: the input and every parent visible)."""

    def __init__(self, names=None, tabs=None, chars=56, ok_text="", rows=(), alias=None):
        self.names = dict(names or {})
        self.tabs = dict(tabs or {})
        self.chars = chars
        self.ok_text = ok_text
        self.rows = {a: a + MSG_SUFFIX for a in rows}
        self.alias = dict(alias or {})
        self.issues: List[Issue] = []

    def show(self, issues, ok_text=None, visible=lambda anchor: True):
        """-> {"rows": {anchor: {"html", "rows", "tip"} or None}, "summary": html}:
        what REF's Validator.show writes into each message row and the summary."""
        self.issues = list(issues)
        if ok_text is not None:
            self.ok_text = ok_text
        per_row: Dict[str, List[Issue]] = {}
        for i in self.issues:
            a = self.alias.get(i.anchor, i.anchor)
            if a in self.rows and (i.counts or i.note):
                per_row.setdefault(a, []).append(i)
        out = {}
        for a in self.rows:
            got = sorted(per_row.get(a, []), key=lambda i: RANK[i.level])
            if got and visible(a):
                parts, n = [], 0
                for i in got[:2]:
                    c = COLOUR["note"] if i.note else COLOUR[i.level]
                    parts.append(f"<span style='color:{c}'>{html(SIGN[i.level] + i.text)}</span>")
                    n += rows_for(SIGN[i.level] + i.text, self.chars)
                out[a] = {"html": "<br>".join(parts), "rows": max(1, min(3, n)),
                          "tip": "<br>".join(html(i.detail or i.text) for i in got[:2])}
            else:
                out[a] = None
        named = [Issue(self.alias.get(i.anchor, i.anchor), i.level, i.text, i.note, i.detail)
                 for i in self.issues]
        return {"rows": out, "summary": summary_text(named, self.names, self.tabs, self.ok_text)}

    def blocking(self):
        return [i for i in self.issues if i.level == "block"]

    def first_tab(self):
        """The tab of the most urgent issue (for a "show me" control)."""
        for i in sorted(self.issues, key=lambda i: RANK[i.level]):
            if i.counts and i.anchor in self.tabs:
                return self.tabs[i.anchor]
        return None


# ---------------------------------------------- the dialog's rows as key paths

# REF's dialog input ids -> the TagSpec key path the row writes
# (docs/ARCHITECTURE.md 5.6); "tag" = the tag as a whole.
ANCHOR_FIELD = {
    "": "tag", "target": "target", "size": "numbers.size", "auto": "numbers.size",
    "square": "numbers.square", "marker_id": "numbers.marker_id", "layout": "settings.layout",
    "dictionary": "settings.dictionary", "quiet": "settings.quiet_modules",
    "grow": "settings.grow", "mode": "settings.mode", "start": "settings.mode",
    "op": "settings.op", "white": "numbers.white_height", "white_height": "numbers.white_height",
    "white_offset": "numbers.white_offset", "black": "numbers.black_height",
    "black_height": "numbers.black_height", "black_offset": "numbers.black_offset",
    "pin": "settings.pin", "pin_size": "numbers.pin_size", "pin_length": "numbers.pin_length",
    "pin_tol": "numbers.pin_tol", "corner_mark": "settings.corner_mark", "turn": "settings.turn",
    "origin": "settings.turn", "cells": "settings.cells", "cell_mm": "settings.cells.mm",
    "cell_min": "settings.cells.min_mm", "trim": "settings.trim",
    "trim_margin": "settings.trim.margin_mm", "trim_force": "settings.trim.force",
    "label_on": "settings.label.on", "label_content": "settings.label.content",
    "label_text": "settings.label.text", "label_place": "settings.label.place",
    "label_row": "settings.label.row", "label_side": "settings.label.side",
    "label_scope": "settings.label.scope", "label_cap": "settings.label.cap_mm",
    "label_auto": "settings.label.cap_mm", "label_nozzle": "settings.label.nozzle_mm",
    "label_dx": "settings.label.x_mm", "label_dy": "settings.label.y_mm",
    "label_pos_auto": "settings.label.position", "label_force": "settings.label.build_anyway",
    "preset_row": "tag",
    # M6a (manufacturing intent, holes): the new rows
    "made_by": "settings.make.by", "make": "settings.make",
    "make_thickness": "settings.make.thickness_mm", "make_margin": "settings.make.margin_mm",
    "make_cut": "settings.make.cut_line", "perimeter": "settings.make.perimeter",
    "holes": "settings.holes",
}


def field_of(anchor):
    """The TagSpec key path of a dialog row (unknown rows: "tag")."""
    return ANCHOR_FIELD.get(anchor or "", "tag")
