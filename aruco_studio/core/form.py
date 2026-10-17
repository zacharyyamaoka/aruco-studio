"""The tag form's pure model: defaults, choices, and the info lines' words.

Ported from REF (cad-exporter c8216ff) `ArucoMarkers/aruco_extrude_cmd.py`
(the ArUco Extrude dialog) and `aruco_extrude_ui.py` (dialog v2). The
functions below the line "verbatim" are REF's bodies unchanged; they still
spell the add-in's modules (`aruco_core.module(...)`, `aruco_feature.A()`,
`aruco_presets.layer_note`), which core/_ref_compat.py maps onto this core.

Where REF read the dialog's own state (`_X`: the preset's printer profile,
the node being edited) or Fusion's command inputs, the function here takes
those values as arguments instead; each says which REF function it is:

| Here | REF | What it took from the dialog |
|---|---|---|
| `cells_line(spec, s, line_mm)` | `cells_line(spec, s)` | `_cell_line_mm()`: the preset profile's line width |
| `layer_lines(s, n, profile)` | `layer_lines(s, n)` | `_X.profile` |
| `edit_kind_line(kind, dependents)` | `_edit_kind_line(s, n)` | `aruco_feature.edit_kind(_X.edit_cf, s, n)` and the edit's dependents |
| `preset_lines(note, msgs, catalog_notes)` | `_preset_lines()` | `_X.preset_note`, `_X.preset_msgs`, `_X.catalog["notes"]` |
| `trim_values(axes, margin_mm, force, has_row)` | `trim_values(inputs)` | the Trim rows |
| `trim_issues(trim, ev, margin_ok, margin_shown)` | `trim_issues(inputs, ev)` | the Trim rows |
| `trim_lines(s, ev, issues, body_name)` | `trim_lines(inputs, s, ev, body_name)` | (through trim_issues) |

Not here, on purpose: the dialog's refresh state machine (`_refresh`, `_X`),
`values(inputs)` / `label_values(inputs)` / `preset_values(...)` (they read
Fusion's command inputs row by row; the Studio's inspector is driven by
`/api/form` and writes settings / numbers directly), `snap_size` and
`_size_limit` (they set Fusion input limits), `_check_auto` (Fusion's host).
"""
from __future__ import annotations

import json

from . import presets as aruco_presets
from . import settings as aruco_feature
from ._ref_compat import aruco_core


# ------------------------------------------------------------ verbatim from REF ArucoMarkers/aruco_extrude_cmd.py

LAYOUT_LABELS = [("Single marker", "single"), ("Grid board", "grid"),
                 ("ChArUco board", "charuco")]


MODE_LABELS = [("Auto", "auto"), ("White + black", "both"),
               ("Black only", "black"), ("White only", "white")]


OP_LABELS = [("Join", "join"), ("New body", "new")]


PIN_LABELS = [("None", "none"), ("Triangle", "triangle"), ("Round", "round")]


# the Label (aruco_label.LabelSettings): content, then position, then size
LABEL_CONTENT = [("#id", "id"), ("#id + name", "id_name"), ("Name", "name"),
                 ("Dictionary #id", "dict_id"), ("Custom", "custom")]


LABEL_PLACE = [("Auto", "auto"), ("On the black", "black"), ("On the white", "white")]


LABEL_ROW = [("Auto", "auto"), ("Bottom row", "bottom"), ("Top row", "top"),
             ("Both rows", "both"), ("Black square", "square")]


LABEL_SIDE = [("Auto", "auto"), ("Below", "below"), ("Above", "above"), ("Left", "left"),
              ("Right", "right")]


LABEL_SCOPE = [("Auto", "auto"), ("Each marker", "each"), ("First marker", "first")]


# the cell multiple: ONE row under Size, "Cells" (2026-10-16, Zach: "I was
# hoping that would be more obvious"). Its words carry the numbers ("Line
# width (0.68 mm)"), so the choice is kept by code (_X.cells_choice), never by
# its label; remembered by hand (remember)
CELLS = ("marker", "line", "custom")


def SL():
    return aruco_core.module("aruco_slabs")


def OR():
    return aruco_core.module("aruco_origin")


def CH():
    return aruco_core.module("aruco_chamfer")


def AL():
    return aruco_core.module("aruco_label")


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def defaults():
    """The dialog's own defaults (cm for lengths, like the inputs hold them),
    for a first run and Reset."""
    S = SL()
    return {"layout": "single", "dictionary": aruco_core.module("markers").DEFAULT_DICTIONARY,
            "auto": True, "mode": "auto", "op": "join", "quiet": 1.0, "grow": False,
            "corner_mark": "none",
            "pin": "triangle", "pin_size": S.PIN_SIZE_MM / 10.0,
            "pin_tol": S.PIN_TOL_MM / 10.0, "pin_length": S.PIN_LENGTH_MM / 10.0,
            "white_offset": S.WHITE_OFFSET / 10.0, "white_height": S.WHITE_HEIGHT / 10.0,
            "black_height": S.BLACK_HEIGHT / 10.0,
            # the cell multiple: the "Default" preset's (the marker in 0.5 mm
            # steps, as before presets); Custom's width; Print's minimum cell
            "cells": "marker", "cell_mm": 0.05, "cell_min": "2 mm"}


def _base_from(vals):
    """White + black's own Offset / Height (mm) from remembered values (cm).
    The black always starts flush (Zach, 2026-10-08: "by default at the
    start white and black should be the same height"): a remembered black
    height is kept only as an inlay depth (negative)."""
    d = defaults()
    out = {}
    for key in ("white_offset", "white_height", "black_height"):
        v = vals.get(key, d[key])
        out[key] = float(v) * 10.0 if _num(v) else float(d[key]) * 10.0
    if out["black_height"] >= 0.0:
        out["black_height"] = float(d["black_height"]) * 10.0
    return out


def _choice_of_cells(c):
    """A preset's cells (aruco_presets' shape) -> the Cells row's choice."""
    if c.get("of") == "marker":
        return "marker"
    return "line" if c.get("step") == "line" else "custom"


def _same_value(a, b, tol=1e-9):
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= tol
    return a == b


def _cell_warnings(spec, s):
    """A quiet zone that is not a whole number of lines under "Each cell"."""
    c = aruco_feature.A().cells_of(s.get("cells"))
    if c is None or c[0] != "cell" or spec.layout == "charuco":
        return []
    q = float(spec.quiet_modules)
    k = spec.module_m / c[1]
    if q > 0 and abs(q * k - round(q * k)) > 1e-6:
        return [f"white border {q * spec.module_m * 1000.0:.2f} mm = {q * k:g} × "
                f"{c[1] * 1000.0:g} mm: not whole lines (a whole quiet zone keeps it whole)"]
    return []


def label_defaults():
    """The Label inputs' defaults (lengths in cm, like the inputs): off."""
    ls = AL().LabelSettings()
    return {"label_on": False, "label_content": ls.content, "label_text": "",
            "label_place": ls.place, "label_row": ls.row, "label_side": ls.side,
            "label_scope": ls.scope, "label_auto": True,
            "label_cap": AL().min_cap(ls.nozzle_mm) / 10.0,      # 3.0 mm at 0.6
            "label_pos_auto": True, "label_dx": 0.0, "label_dy": 0.0,
            "label_nozzle": ls.nozzle_mm / 10.0}


def _same_label_settings(a, b, tol=1e-6):
    """Two label settings (dicts) the same but for their rule (lengths to tol)."""
    for k in (set(a) | set(b)) - {"rule"}:
        x, y = a.get(k), b.get(k)
        if isinstance(x, float) or isinstance(y, float):
            try:
                if abs(float(x) - float(y)) > tol:
                    return False
            except (TypeError, ValueError):
                return False
        elif x != y:
            return False
    return True


WARN_HTML = "#d45500"


LEVEL_HTML = {"error": "#c00", "warn": WARN_HTML, "ok": "", "note": "#888"}


INFO_ROWS = (4, 14)         # the info box: as many rows as it needs, within these


INFO_CHARS = 58             # characters a row holds at the dialog's width (DIALOG_SIZE)


def _html(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def label_entries(lab, mode):
    """The info's Label lines, [(level, html)] -- aruco_label.describe: a
    refused label in at most three lines (what is wrong, with the number;
    where it is shown in orange; what to do), else one result line and its
    notes. [] when off."""
    if lab is None or not lab.settings.on:
        return []
    out = []
    for level, text in AL().describe(lab, mode):
        t = _html(text)
        if t.startswith("Label "):
            t = "<b>Label</b> " + t[len("Label "):]
        colour = LEVEL_HTML.get(level, "")
        out.append((level, f"<span style='color:{colour}'>{t}</span>" if colour else t))
    return out


def label_lines(lab, mode):
    """label_entries' html only."""
    return [h for _level, h in label_entries(lab, mode)]


def info_rows(lines, chars=INFO_CHARS, rows=INFO_ROWS):
    """How many rows the info box needs for these html lines (each wraps at
    `chars`), within `rows`."""
    import html as _h
    import re as _re
    n = 0
    for ln in lines:
        t = _h.unescape(_re.sub(r"<[^>]+>", "", str(ln)))
        n += max(1, -(-len(t) // chars))
    return max(rows[0], min(rows[1], n))


def resolve_mode(s, has_body):
    if s.get("mode") == "auto":
        s["mode"] = "black" if has_body else "both"
    return s


def mode_for(mode, has_body):
    """Extrude Auto resolved for a target, as a plain value: REF
    resolve_mode's rule (Auto is Black only on a body, White + black
    without one). Not REF's: the one call every caller makes (audit C4)."""
    return resolve_mode({"mode": mode}, has_body)["mode"]


def new_tag_settings(s, has_body, preset=None, made_by=None):
    """A NEW tag's settings as today's dialog stores them on OK (REF
    aruco_feature.create): the Origin rule stamped (`origin_v` =
    aruco_origin.ORIGIN_RULE) and Extrude Auto resolved (resolve_mode).
    A copy; the adapter-only keys (`source`, `has_body`) stay the
    caller's. Not REF's: the one home of this rule, called by the Studio's
    new tag (server/newtag.py) and the Fusion adapter's create() (audit C4).
    An EXISTING node never goes through here: one without `origin_v`
    keeps the old Origin rule.

    M6a (2026-10-16) adds three stamps, each a versioned key a stored tag
    without it reads exactly as before: `make` (core.make, rule 1: how the
    tag is made -- `made_by`, else the preset's kind, else a `make` already
    there, else 3D printed; a sticker takes the preset's stock), `holes`
    ("avoid" unless one is given) and the label's rule (label.NEW_RULE: 5
    since 2026-10-17 -- a ChArUco label by hand in any black square (3), on
    auto in a black square only (4), and cut from the black at least 1.1
    cell lines thick (5)). A sticker is White + black,
    New body, no pins, no trim."""
    from . import make as _MK
    from . import presets as _PS
    s = dict(s)
    s["origin_v"] = OR().ORIGIN_RULE
    kind = made_by if made_by in _MK.BY else None
    if kind is None and isinstance(preset, dict):
        kind = _PS.kind_of(preset)
    have, _notes = _MK.make_of(s)
    if kind is None:
        kind = have.by if not have.legacy else "print3d"
    if have.legacy or have.by != kind or preset is not None:
        s["make"] = _MK.new_make(kind, (preset or {}).get("profile"))
    else:
        s["make"] = have.to_dict()
    if s.get("holes") not in _MK.HOLES:
        s["holes"] = "avoid"
    lab = s.get("label")
    lab = dict(lab) if isinstance(lab, dict) else AL().LabelSettings().to_dict()
    lab["rule"] = AL().NEW_RULE
    s["label"] = lab
    if kind == "sticker":
        s.update(mode="both", op="new", pin="none", grow=False)
        s.pop("trim", None)
        return s
    return resolve_mode(s, has_body)


def _origin_line(spec, turn):
    """The info's Joint Origin line (aruco_origin.describe): OpenCV's frame
    for this Origin, and a quarter-turned rectangular board's swap."""
    return OR().describe(spec.layout, turn, spec.cols, spec.rows) + \
        ": the ghost's axes, x red, y green, z blue"


def same_build(a, b, tol_cm=1e-7):
    """Do two evaluate() results build the same tag: the same board as built
    (dictionary, ids, cols x rows, sizes) at the same place and turn?"""
    try:
        if json.dumps(a["spec"].to_dict(), sort_keys=True) != \
                json.dumps(b["spec"].to_dict(), sort_keys=True):
            return False
        return all(abs(p - q) <= tol_cm for fa, fb in zip(a["tag"], b["tag"])
                   for p, q in zip(fa, fb))
    except Exception:                              # noqa: BLE001
        return False


ROLE_WORDS = {"tile": "white tile", "pin": "locating pins", "pocket": "pocket",
              "recess": "recess", "pattern": "pattern", "joined": "joined body's new faces"}


def _mark_line(mark, body_name):
    """Corner mark: what the corner gets, in the body's name (a tile joined
    to it: why a triangle and not a cut)."""
    note = mark.note
    if body_name:
        note = note.replace("joined to the body: a cut corner would cut the body",
                            f"joined to '{body_name}': a cut corner would cut '{body_name}'")
    return note


def _pin_line(s, n, plan, body_name):
    shape = {"triangle": "1 triangle pin (top-left corner)",
             "round": "2 round pins (top corners)"}.get(s.get("pin"), "pins")
    out = (f"{shape}, {n['pin_size']:.2f} mm, {n['pin_length']:.2f} mm long: "
           "WHITE, joined to the tile (it prints with it)")
    hole = next((sl for what, sl in plan.recess if what == "hole"), None)
    if hole is not None:
        out += (f"; holes in '{body_name or 'the body under it'}' "
                f"{n['pin_tol']:.2f} mm bigger all round, {-hole[0]:.2f} mm deep")
    elif not s.get("has_body"):
        out += "; nothing under it to hole"
    return out


def _mm_text(v_mm):
    """28.0, 27.25, 37.33: one decimal at least, two at most."""
    t = "%.2f" % v_mm
    return t[:-1] if t.endswith("0") else t


def size_line(spec):
    """What Size means, in the sizes Zach sees (2026-10-08: he thinks in
    "the square I see", which is the sticker): the marker (the black square
    OpenCV measures) and the sticker (marker + the white border)."""
    L = spec.marker_length_m * 1000.0
    mod = spec.module_m * 1000.0
    tw, th = (v * 1000.0 for v in spec.tile_size_m)
    if spec.layout == "charuco":
        return (f"marker {_mm_text(L)} mm · checker {_mm_text(spec.square_length_m * 1000.0)} mm"
                f" · board {tw:.1f} × {th:.1f} mm (no outer border) · module {mod:.2f} mm")
    q = float(spec.quiet_modules)
    box = f"{tw:.1f} mm" if abs(tw - th) < 1e-6 else f"{tw:.1f} × {th:.1f} mm"
    if q <= 0:
        return f"marker {_mm_text(L)} mm · no white border (quiet zone 0) · module {mod:.2f} mm"
    return (f"marker {_mm_text(L)} mm · sticker {box} (white border {q:g} module"
            f"{'' if q == 1 else 's'} = {q * mod:.2f} mm)")


TRIM_LABELS = [("Off", "off"), ("Width (the tag's X)", "x"), ("Height (the tag's Y)", "y"),
               ("Both", "both")]


TRIM_MISSING = object()        # trim_values(): the dialog has no Trim row (built before it)


def TRM():
    return aruco_core.module("aruco_trim")


# ------------------------------------------------------------ verbatim from REF ArucoMarkers/aruco_extrude_ui.py

def round_line(spec, cells_choice, line_mm, marker_step, typed=None):
    """"= 28.56 mm · 7 cells × 4.08 mm · 6 lines of 0.68" (the cells
    multiple), "= 28.00 mm · cell 4.67 mm · 0.5 mm steps" (the marker's
    steps); a typed size that snapped says so first."""
    L = spec.marker_length_m * 1000.0
    mod = spec.module_m * 1000.0
    n = spec.bits + 2 if getattr(spec, "bits", None) else None
    head = f"= {L:.2f} mm"
    if typed is not None and abs(typed - L) > 0.005:
        head = f"{typed:g} → {L:.2f} mm"
    if cells_choice == "marker":
        on_step = abs(L / marker_step - round(L / marker_step)) < 1e-6
        if typed is not None and not on_step:
            # the legacy rule keeps a typed size as typed; Auto rounds
            return (f"= {L:.2f} mm as typed · cell {mod:.2f} mm · Auto in {marker_step:g} mm "
                    "steps")
        return f"{head} · cell {mod:.2f} mm · marker in {marker_step:g} mm steps"
    cells = f"{n} cells × {mod:.2f} mm" if n else f"cell {mod:.2f} mm"
    if line_mm and cells_choice == "line":
        k = int(round(mod / line_mm))
        return f"{head} · {cells} · {k} lines of {line_mm:g}"
    return f"{head} · {cells}"


def json_key(v):
    import json
    return json.dumps(v, default=str, sort_keys=True)


# ------------------------------------------- adapted: the dialog state as arguments

def cells_line(spec, s, line_mm=None):
    """REF cells_line(spec, s), with `line_mm` = what REF read from the
    preset's profile (_cell_line_mm()): the info's cell line: "cells 3.40 mm
    = 5 × 0.68 mm lines" (or the marker's steps; an older tag's 0.5 mm
    steps, grey), or None."""
    c = aruco_feature.A().cells_of(s.get("cells"))
    mod = spec.module_m * 1000.0
    if c is None:
        return ("<span style='color:#888'>sizes in 0.5 mm steps, as this tag was made (before "
                "cell multiples): a change to its size, Type, dictionary, quiet zone or Cells "
                "gives it the Cells shown</span>")
    m = c[1] * 1000.0
    line = line_mm
    lines = line is not None and abs(m - line) < 1e-6
    if c[0] == "marker":
        return f"marker in {m:g} mm steps · cell {mod:.2f} mm"
    k = int(round(mod / m))
    return f"cells {mod:.2f} mm = {k} × {m:g} mm{' lines' if lines else ''}"


def cell_line_mm(profile):
    """REF _cell_line_mm(): the line width "Cells: Line width" means -- the
    preset's profile's."""
    return aruco_presets.line_mm({"profile": profile or {}})


def layer_lines(s, n, profile=None):
    """REF layer_lines(s, n), `profile` = REF's _X.profile: heights in layers
    (a note, never a snap): the black's depth from the face, printed face
    down with the preset profile's layers."""
    prof = profile or {}
    if s.get("mode") not in ("both", "black") or not prof.get("layer_mm"):
        return []
    if float(n.get("black_height") or 0.0) >= 0.0:
        return []                                  # a raised black is not printed face down
    note = aruco_presets.layer_note(n["black_height"], prof["layer_mm"],
                                    prof.get("first_layer_mm"))
    return [note] if note else []


def edit_kind_line(k, deps=None):
    """REF _edit_kind_line(s, n) on `k` = core.edits.edit_kind(...) and
    `deps` = {role: [(feature name, how it uses it)]} (the features after the
    node, read before the edit's roll): what OK does to the node when these
    values change what it is made of, or None for a plain compute."""
    if k is None or k["kind"] == "compute":
        return None
    deps = deps or {}

    def users(roles):
        out = []
        for r in roles:
            for nm, how in deps.get(r, []):
                item = f"{nm} ({how} the {ROLE_WORDS.get(r, r)})"
                if item not in out:
                    out.append(item)
        return out
    if k["kind"] == "in place":
        risk = list(k["goes"]) + (["joined"] if k["op_changes"] else [])
        text = "OK changes what this tag is made of IN PLACE: the node and what uses it stay"
        if k["goes"]:
            text += "; it removes the " + ", ".join(ROLE_WORDS.get(r, r) for r in k["goes"])
        u = users(risk)
        if u:
            text += " -- used by: " + "; ".join(u[:6]) + (f" (+{len(u) - 6})" if len(u) > 6 else "")
    else:
        text = f"OK REBUILDS this tag (delete + create: {k['why']})"
        u = users(list(deps))
        text += (" -- features after it that use it may be deleted with it: "
                 + "; ".join(u[:6]) + (f" (+{len(u) - 6})" if len(u) > 6 else "")
                 if u else "; nothing after it uses it")
    return f"<span style='color:#c60'>{_html(text)}</span>"


def preset_lines(note=None, msgs=(), catalog_notes=()):
    """REF _preset_lines(): what a preset just changed (blue: before OK, the
    ghost shows it), the last preset action, the catalog's notes."""
    out = []
    if note:
        out.append(f"<span style='color:#06c'>{_html(note)}</span>")
    for m in msgs or []:
        out.append(f"<span style='color:#c60'>{_html(m)}</span>")
    for m in catalog_notes or []:
        out.append(f"<span style='color:#c60'>{_html(m)}</span>")
    return out


def trim_values(axes, margin_mm=0.0, force=False, has_row=True):
    """REF trim_values(inputs): the dialog's Trim excess as a tag stores it
    (aruco_trim.setting): None = Off; TRIM_MISSING when the dialog has no
    Trim row. `margin_mm` None = not a length (REF read 0 then)."""
    if not has_row:
        return TRIM_MISSING
    if axes == "off":
        return None
    margin = 0.0
    if margin_mm is not None:
        margin = max(0.0, float(margin_mm))
    return TRM().setting(axes, round(margin, 6), bool(force))


def trim_issues(trim, ev, margin_ok=True, margin_shown=True):
    """REF trim_issues(inputs, ev): [(input id, text)] -- what keeps Trim
    excess from going ahead: a rule refusing it (not forced), a margin that
    is not a length. `trim` = the Trim row's choice ("off" / "x" / "y" /
    "both", None = no Trim row)."""
    out = []
    if trim is None or trim == "off":
        return out
    if margin_shown and not margin_ok:
        out.append(("trim_margin", "Trim margin is not a length (\"1.5 mm\")"))
    tp = (ev or {}).get("trim")
    if tp is not None and tp.refused:
        out.append(("trim", "Trim refused: " + "; ".join(tp.refusals)
                    + " -- tick Cut anyway, add a margin, or set Trim excess to Off"))
    return out


def trim_lines(s, ev, issues=(), body_name=None):
    """REF trim_lines(inputs, s, ev, body_name), `issues` = trim_issues(...):
    the info's Trim lines, [(level, html)] (levels as LEVEL_HTML): what it
    trims, in red-ghost words; refused, in orange; nothing to trim, grey."""
    t = aruco_feature.trim_setting(s)
    if t is None:
        return []
    if not s.get("has_body"):
        return [("note", "<span style='color:#888'>Trim excess: nothing under the tag to trim "
                         "(it trims the body the tag sits on)</span>")]
    tp = (ev or {}).get("trim")
    if tp is None:
        return []
    name = body_name or "the part"
    out = []
    for _cid, text in issues:
        out.append(("warn", f"<span style='color:{WARN_HTML}'>{_html(text)}</span>"))
    if tp.refused:
        if tp.active:
            out.append(("note", f"<span style='color:#888'>it would: "
                                f"{_html(TRM().summary(tp, name))}</span>"))
        return out
    if not tp.active:
        return out + [("note", f"<span style='color:#888'>Trim excess: "
                               f"{_html(tp.notes[0] if tp.notes else 'nothing to trim')}</span>")]
    out.append(("ok", "<b>Trim</b> " + _html(TRM().summary(tp, name))))
    if tp.forced and tp.refusals:
        out.append(("warn", f"<span style='color:{WARN_HTML}'>cut anyway although: "
                            f"{_html('; '.join(tp.refusals))}</span>"))
    for note in tp.notes:
        out.append(("note", f"<span style='color:#888'>{_html(note)}</span>"))
    return out
