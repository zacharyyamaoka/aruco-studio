"""A tag's settings and numbers: the five generations and their rules.

Ported from REF `ArucoMarkers/aruco_feature.py` (cad-exporter c8216ff): the
adsk-free bodies only, copied verbatim. `settings_of` / `numbers_of` read a
node's stored values here as plain data (a `NodeState`, see core/edits.py)
instead of a Fusion custom feature.

| Rule | Where it lives | Stored as |
|---|---|---|
| spec version | `SPEC_VERSION = 2` | settings `"v"` |
| Auto size | `size_is_auto` | the size number 0 (ChArUco: its checker too) |
| old corner mark | `normalise` | `"chamfer": true` reads as `corner_mark: "cut"` |
| old Frame | `normalise` | `"frame"` dropped (the frame is OpenCV's) |
| cell multiple | `cells_of` -> `autosize.cells_of` | `"cells"`, absent = legacy 0.5 mm |
| trim | `trim_setting` -> `trim.trim_of` | `"trim"`, absent / junk = off |
| Joint Origin layout | `has_frame_sketch` | `"jo_v"` 1 or 2 |
| legacy numbers | `is_legacy` + `slabs.from_legacy` | parameters height / thickness / above |

`JO_AFTER` and `RESTRUCTURE_IN_PLACE` are REF's switches as they stood at
c8216ff (both True). `default_settings()` reads `JO_AFTER` when called, as
REF does (the trim golden was made with it off and sets it so).
"""
from __future__ import annotations

from typing import Optional

from . import autosize as _autosize
from . import chamfer as _chamfer
from . import label as _label
from . import markers as _markers
from . import origin as _origin
from . import slabs as _slabs
from . import trim as _trim


# REF's module accessors (aruco_core.module(...)), same names, so the copied
# bodies read unchanged.
def M():
    return _markers


def A():
    return _autosize


def SL():
    return _slabs


def CH():
    return _chamfer


def OR():
    return _origin


def AL():
    return _label


def TR():
    return _trim


SPEC_VERSION = 2


MODES = ("both", "black", "white")


OPS = ("join", "new")


HEIGHT_PARAMS = ("white_offset", "white_height", "black_offset", "black_height")


PIN_PARAMS = ("pin_size", "pin_length", "pin_tol")


PARAMS = ("marker_id", "size", "square") + HEIGHT_PARAMS + PIN_PARAMS


LEGACY_PARAMS = ("height", "thickness", "above")       # nodes made before 2026-10-08


INFO_NOTES = ("not a rectangle", "origin ", "corner mark form: ", "label: ",
              # the cell rule (bam_cad_core.aruco_autosize, settings "cells"):
              # a typed size snapped onto the grid, a cell under the preset's
              # minimum -- the dialog shows them; the node does not warn
              "cell multiple: ", "cell minimum: ",
              # Trim excess (aruco_trim): what it trims, nothing to trim, cut
              # anyway -- "trim refused: ..." IS a warning (the body is kept)
              "trim: ")


INFO_IN = (" fit, but ",)       # a board capped at its dictionary's ids


TARGET_KEYS = ("source", "z_sign", "x_sketch", "has_body", "key", "host_xform",
               # a face tag's x, fixed at creation (native component frame):
               # x_base the face frame's, x_ref the fitted pattern's (before
               # the Origin turn) -- an upstream edit cannot turn it 180°
               "x_base", "x_ref")


PARAM_LABELS = {"marker_id": "Marker ID (first)", "size": "Marker size (0 = Auto size)",
                "square": "Checker size (0 = Auto size)", "white_offset": "White offset",
                "white_height": "White height", "black_offset": "Black offset",
                "black_height": "Black height", "pin_size": "Pin size",
                "pin_length": "Pin length", "pin_tol": "Pin hole tolerance"}


JO_AFTER = True


RESTRUCTURE_IN_PLACE = True


def is_info(note):
    """An autosize note that only informs (no warning on the node)."""
    return note.startswith(INFO_NOTES) or any(t in note for t in INFO_IN)


def default_settings():
    return {"v": SPEC_VERSION, "key": "", "mode": "black", "op": "join",
            "layout": "single", "dictionary": M().DEFAULT_DICTIONARY,
            "quiet_modules": 1.0, "grow": False, "rotate_deg": 0, "legacy": False,
            "size_auto": True, "force": None, "flip": False,
            # locating pins (White + black, New body): "none" / "triangle" / "round"
            "pin": "none",
            # Origin: the pattern turned on its own footprint (degrees, CCW
            # about the face normal): where OpenCV's frame lands, 4 choices
            # for every layout (bam_cad_core.aruco_origin; a rectangular
            # board at 90 / 270 swaps its cols / rows). create() stamps
            # "origin_v" (aruco_origin.ORIGIN_RULE); a node without it keeps
            # the old rule. The old "rotate_deg" turned the frame BEFORE the
            # fit; it stays for nodes that have it, the dialog never sets it.
            "turn": 0,
            # Corner mark (bam_cad_core.aruco_chamfer): "none" / "cut" (the
            # white tile's corner; a ChArUco board's top-left black square)
            # / "triangle" (a black triangle in any white corner). Inside the
            # existing parts: changing it is a compute, never a rebuild. The
            # old checkbox "chamfer": true reads as "cut" (normalise).
            "corner_mark": "none",
            # the optional LABEL (bam_cad_core.aruco_label.LabelSettings,
            # off by default): text printed on the tag -- its content, then
            # where it goes, how big, a nudge. Built inside the existing
            # parts (the pattern and what follows its footprint): changing
            # it is a compute, never a rebuild.
            "label": AL().LabelSettings().to_dict(),
            # scripts: start the black at the white top (Black only: the
            # face). create() resolves it and does not store it; in White +
            # black the black offset parameter is ALWAYS the white top + a
            # kept delta (an expression), see link_black.
            "black_follows": False,
            # the Joint Origin: 2 = after the node, on its frame sketch
            # (JO_AFTER); 1 = before the node, on its target
            "jo_v": 2 if JO_AFTER else 1,
            # NO "cells" here, ever (2026-10-14): the size grid
            # (aruco_autosize.cells_of) -- {"rule": 1, "of": "cell" | "marker",
            # "mm", "min_mm"} -- is stored only by a tag made (or whose size
            # settings were edited) under it; a node without it keeps the
            # legacy 0.5 mm steps, exactly (tests/test_aruco_cells_legacy.py)
            # set at creation from the target
            "source": "", "z_sign": 1, "x_sketch": None, "has_body": False,
            "host_xform": None}


def size_is_auto(s, n):
    """Auto size (2026-10-13): the size parameter 0 (a ChArUco board: its
    checker too) -- evaluate() fits the size on the face as it is NOW, on
    every compute, exactly as when it was made. A typed size is a number.
    Storing the number Auto picked made the next compute re-fit as a TYPED
    size, which on a face with holes is another layout or place (measured
    offline: a ChArUco 6 x 2 became 4 x 2; a single marker moved 45 mm)."""
    try:
        size = float((n or {}).get("size") or 0.0)
        square = float((n or {}).get("square") or 0.0)
    except (TypeError, ValueError):
        return False
    return size <= 0.0 and ((s or {}).get("layout") != "charuco" or square <= 0.0)


def has_frame_sketch(s):
    """Is this node made with a frame sketch (its Joint Origin after it)?"""
    try:
        return int((s or {}).get("jo_v") or 1) >= 2
    except (TypeError, ValueError):
        return False


def trim_setting(s):
    """The tag's Trim excess (aruco_trim.trim_of: {"rule", "axes",
    "margin_mm", "force"}) or None: off. default_settings() never holds
    "trim": a tag made before 2026-10-16 has none and builds exactly as it
    did (tests/test_aruco_trim_legacy.py)."""
    raw = (s or {}).get("trim")
    if not raw:
        return None
    try:
        return TR().trim_of(raw)
    except Exception:                              # noqa: BLE001
        return None


def normalise(s, partial=False):
    """Settings as this code keeps them (a copy): the old checkbox
    "chamfer" becomes "corner_mark" (true: "cut", which makes what it made);
    the removed Frame ("frame", 2026-10-08) is dropped -- the Joint Origin is
    OpenCV's frame. partial: an edit's changes (no default filled in)."""
    s = dict(s or {})
    if "chamfer" in s:
        on = bool(s.pop("chamfer"))
        if s.get("corner_mark") in (None, "none"):
            s["corner_mark"] = "cut" if on else "none"
    if not partial:
        s.setdefault("corner_mark", "none")
    if "corner_mark" in s and s["corner_mark"] not in CH().CHOICES:
        s["corner_mark"] = "none"
    if "label" in s:
        # the label's settings as the core keeps them (unknown values fall
        # back to the defaults)
        s["label"] = AL().LabelSettings.from_dict(
            s["label"] if isinstance(s["label"], dict) else None).to_dict()
    s.pop("frame", None)
    return s


def default_numbers(mode="both"):
    """mm (marker_id unitless): Offset / Height per colour, pins."""
    n = {"marker_id": 0, "size": 0.0, "square": 0.0}
    n.update(SL().default_numbers(mode if mode in MODES else "both"))
    n.update(SL().pin_defaults())
    return n


def effective_op(s):
    """'join' needs a body under the target; otherwise the tile is new."""
    if s.get("mode") != "both":
        return None
    return "join" if (s.get("op") == "join" and s.get("has_body")) else "new"


def resolve_follow(s, n):
    """n with the black offset at the white top (the face for Black only)
    when s says it follows -- what the dialog and create() build."""
    if s.get("black_follows") and s.get("mode") in ("both", "black"):
        n = dict(n, black_offset=SL().white_top(s["mode"], n))
    return n


def plan_of(s, n):
    """aruco_slabs.plan for these settings and numbers. Trim excess adds a
    last part "trim" (a tag with a body under it); a tag without the
    setting never passes trim=, so its plan is the one it was built with."""
    kw = {"trim": True} if trim_setting(s) is not None else {}
    return SL().plan(s["mode"], s.get("op", "join"), bool(s.get("has_body")), n,
                     s.get("pin") or "none", **kw)


def structure(s, n):
    """What features the node holds; a change here means rebuild, not compute."""
    return plan_of(s, n).structure + (bool(s.get("has_body")),)


def node_structure(s):
    """The structure a node was BUILT with (its spec's "parts"), or None for
    a node made before 2026-10-08 (no "parts": rebuilt on its next edit)."""
    if not s or not s.get("parts"):
        return None
    return (s["mode"], effective_op(s), tuple(s["parts"]), bool(s.get("has_body")))


def cells_of(s):
    """The tag's size grid as autosize takes it (None: the legacy rule)."""
    return A().cells_of((s or {}).get("cells"))


def is_legacy(s):
    """A node made before 2026-10-08: parameters height / thickness / above,
    no "parts" in its spec."""
    return bool(s) and not s.get("parts")


def params_for(s):
    """The custom parameters a node of these settings carries (besides
    marker_id): the size, the checker (ChArUco), each colour's Offset and
    Height, the pins' numbers when it has pins."""
    out = ["size"]
    if s["layout"] == "charuco":
        out.append("square")
    if s["mode"] in ("both", "white"):
        out += ["white_offset", "white_height"]
    if s["mode"] in ("both", "black"):
        out += ["black_offset", "black_height"]
    if "pin" in (s.get("parts") or ()):
        out += list(PIN_PARAMS)
    return out


# ------------------------------------------------- a node's stored values
# REF reads these off a Fusion custom feature (settings_of(cf) /
# numbers_of(cf)); here the adapter hands over what it read.

def settings_from_stored(stored) -> Optional[dict]:
    """REF `settings_of(cf)` on the node's named value "spec" already parsed
    from JSON: normalise()d over the defaults; None for no spec."""
    if stored is None or not isinstance(stored, dict):
        return None
    s = default_settings()
    s.update(normalise(stored))
    if "jo_v" not in stored:
        s["jo_v"] = 1                   # made before the frame sketch: never JO_AFTER's
    return s


def numbers_from_params(s, params) -> dict:
    """REF `numbers_of(cf)`: the node's numbers (mm) from its parameters
    `params` ({param id: value in mm, marker_id unitless}, only the ones the
    node has); a node made before 2026-10-08 (height / thickness / above)
    mapped to Offset / Height. `params is None` (no node): the defaults.
    REF reads Fusion's cm and multiplies by 10; the adapter does that."""
    if params is None:
        return default_numbers("both")
    s = s or {}
    mode = s.get("mode") if s.get("mode") in MODES else "both"
    n = default_numbers(mode)
    old = {}
    for pid in PARAMS + LEGACY_PARAMS:
        if pid not in params or params[pid] is None:
            continue
        v = params[pid]
        (old if pid in LEGACY_PARAMS else n)[pid] = v
    if old:
        n.update(SL().from_legacy(mode, old.get("height", 2.0), old.get("thickness", 0.6),
                                  old.get("above", 0.0)))
    return n
