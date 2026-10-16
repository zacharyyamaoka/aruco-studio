"""One row per tag copy, as the IDs and Export tables show it.

Ported from REF (cad-exporter c8216ff) `ArucoMarkers/aruco_marker_table.py`
(its pure half: names, rows, order, duplicates, the column layout),
`aruco_ids_cmd.py` (`_how`, `_tone`: the Status words) and
`aruco_ids_preview.py` (`spec_of`, `specs_of`, `marker_row`). Verbatim, with
one change: `spec_info` imported REF's `aruco_core` inside the function; here
it imports core/_ref_compat's (the same lookup of `markers`).

Not here: the double-click timing, the viewport pick, the zoom camera and the
navigation state machine. They are the table's UI: the Studio re-does them in
studio/src/table/, the Fusion adapter keeps REF's Python.
"""
from __future__ import annotations

import dataclasses
import html
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

SEP = "|"                                          # markers.KEY_SEP
COLUMNS = ("tag", "ids", "marker", "status")
WIDTHS = {"lead": 1, "tag": 6, "ids": 2, "marker": 3, "status": 5}
PREFIX = {"tag": "l", "ids": "i", "marker": "m", "status": "s"}
MAX_ROWS, MIN_ROWS = 16, 4
TONES = {"warn": "#a06800", "part": "#a06800", "error": "#c00000", "muted": "#808080"}


def name_of(path: str, key: str) -> str:
    """One tag on one occurrence path -- aruco_numbering.instance_name."""
    return f"{path or '(root)'}{SEP}{key}"


def split_name(name: str) -> Tuple[str, str]:
    path, _sep, key = (name or "").rpartition(SEP)
    return ("" if path == "(root)" else path), key


def natural_key(s: str):
    """'Plate:10' after 'Plate:2' -- aruco_numbering.natural_key."""
    return [(0, int(t)) if t.isdigit() else (1, t.lower())
            for t in re.split(r"(\d+)", s or "") if t != ""]


def family(dictionary: str) -> str:
    """Dictionaries printing the same squares -- aruco_numbering.family."""
    m = re.match(r"DICT_(\d)X\1_", dictionary or "")
    return f"aruco{m.group(1)}x{m.group(1)}" if m else (dictionary or "?")


def where(path: str, key: str, depth: int = 3) -> str:
    """The Tag column: the last `depth` levels of the path and the key,
    "… › Sub:1 › Plate:2 · top" ("(root) · top" for the root component)."""
    parts = (path or "").split("+")
    shown = " › ".join(parts[-depth:]) if path else "(root)"
    if path and len(parts) > depth:
        shown = "… › " + shown
    return f"{shown} · {key}"


def kind_text(layout: str, cols: int = 1, rows: int = 1) -> str:
    if layout == "grid":
        return f"grid {cols}×{rows}"
    if layout == "charuco":
        return f"ChArUco {cols}×{rows}"
    return "single"


def dict_text(dictionary: str) -> str:
    d = dictionary or "?"
    return d[5:] if d.startswith("DICT_") else d


def ids_text(ids: Sequence[int]) -> str:
    ids = list(ids or ())
    if not ids:
        return "—"
    return f"#{ids[0]}" if len(ids) == 1 else f"#{ids[0]}-{ids[-1]}"


def status_html(text: str, tone: str = "") -> str:
    """A status cell: the words, coloured by tone (muted / warn / part / error)."""
    body = html.escape(text or "")
    colour = TONES.get(tone or "")
    return f"<span style='color:{colour}'>{body}</span>" if colour else body


@dataclass
class MarkerRow:
    """One tag copy, as both dialogs show it."""
    name: str                       # "<path>|<key>": the row's identity
    path: str                       # the copy's occurrence path ('' = root component)
    key: str
    component: str = ""
    layout: str = "single"
    dictionary: str = ""
    cols: int = 1
    rows: int = 1
    ids: List[int] = field(default_factory=list)  # what it prints
    hidden: bool = False
    linked: bool = False            # inside a linked design
    frame: Optional[tuple] = None   # (origin, x, y, z): world cm, the tag's centre frame
    size_cm: Tuple[float, float] = (0.0, 0.0)      # the tile, w x h
    top_cm: float = 0.0             # the tag's top over its frame
    pick_paths: Tuple[str, ...] = ()  # occurrence paths a viewport click on means this row
    status: str = ""
    tone: str = ""
    part: str = ""                  # Export: the part (tick) it prints with
    tip: str = ""

    @property
    def where(self) -> str:
        return where(self.path, self.key)

    @property
    def marker(self) -> str:
        return f"{kind_text(self.layout, self.cols, self.rows)} · {dict_text(self.dictionary)}"

    @property
    def family(self) -> str:
        return family(self.dictionary)


def spec_info(spec) -> Optional[dict]:
    """What a row needs from a TagSpec (or its dict): layout, dictionary,
    grid, ids, the tile in cm and the top over the frame in cm."""
    if spec is None:
        return None
    s = spec
    if isinstance(spec, dict):
        try:
            from ._ref_compat import aruco_core
            s = aruco_core.module("markers").TagSpec.from_dict(spec, lambda _m: None, "row")
        except Exception:                          # noqa: BLE001 (no core: the dict as is)
            s = None
        if s is None:
            mid = int(spec.get("marker_id") or 0)
            ids = [int(i) for i in spec.get("ids") or [mid]]
            side = float(spec.get("marker_length_m") or 0.02) * 100.0
            return {"layout": spec.get("layout", "single"), "dictionary": spec.get("dictionary", ""),
                    "cols": int(spec.get("cols") or 1), "rows": int(spec.get("rows") or 1),
                    "ids": ids, "size_cm": (side, side),
                    "top_cm": max(0.0, float(spec.get("raise_m") or 0.0) * 100.0)}
    w, h = (v * 100.0 for v in s.tile_size_m)
    top = max(0.0, getattr(s, "black_top_m", s.raise_m) * 100.0, s.raise_m * 100.0)
    return {"layout": s.layout, "dictionary": s.dictionary, "cols": int(s.cols),
            "rows": int(s.rows), "ids": list(s.ids), "size_cm": (w, h), "top_cm": top}


def make_row(path: str, key: str, spec=None, ids=None, frame=None, **kw) -> MarkerRow:
    """A row from a copy's path + tag key + its spec (TagSpec or dict).
    `ids`: what it prints when that is not the spec's own (ArUco IDs)."""
    info = spec_info(spec) or {}
    row = MarkerRow(name=name_of(path, key), path=path or "", key=key or "",
                    layout=info.get("layout", "single"), dictionary=info.get("dictionary", ""),
                    cols=info.get("cols", 1), rows=info.get("rows", 1),
                    ids=list(ids if ids is not None else info.get("ids", [])),
                    frame=_frame(frame), size_cm=tuple(info.get("size_cm", (0.0, 0.0))),
                    top_cm=float(info.get("top_cm", 0.0)))
    for k, v in kw.items():
        setattr(row, k, v)
    if not row.pick_paths:
        row.pick_paths = (row.path,)
    return row


def _frame(frame):
    if frame is None:
        return None
    if len(frame) == 16:                           # a 4x4 row-major matrix
        return frame_of_matrix(frame)
    return tuple([float(c) for c in v] for v in frame)


def frame_of_matrix(m) -> tuple:
    """4x4 row-major -> (origin, x, y, z)."""
    return ([m[3], m[7], m[11]], [m[0], m[4], m[8]], [m[1], m[5], m[9]], [m[2], m[6], m[10]])


def order(rows: Sequence[MarkerRow]) -> List[MarkerRow]:
    """Visible rows first, then hidden; natural order of the name in each."""
    return sorted(rows, key=lambda r: (bool(r.hidden), natural_key(r.name)))


def duplicates(rows: Sequence[MarkerRow]) -> Dict[str, List[str]]:
    """'<family>#<id>' -> the visible rows printing it (only when 2+)."""
    out: Dict[str, List[str]] = {}
    for r in rows:
        if r.hidden:
            continue
        for i in r.ids:
            out.setdefault(f"{r.family}#{i}", []).append(r.name)
    return {k: v for k, v in out.items() if len(v) > 1}


def ratio(lead: bool = False) -> str:
    cols = (("lead",) if lead else ()) + COLUMNS
    return ":".join(str(WIDTHS[c]) for c in cols)


def column(col: str, lead: bool = False) -> int:
    return COLUMNS.index(col) + (1 if lead else 0)


def cell_id(col: str, g, k) -> str:
    """The input id of a row's cell: l<g>_<k> (Tag), i (ids), m (marker), s (status)."""
    return f"{PREFIX[col]}{g}_{k}"


# -------------------------------------------------- verbatim from REF ArucoMarkers/aruco_ids_cmd.py

def _how(r):
    """The row's Status text: where its id comes from, and the id itself (so
    an emptied ID field still says what auto gives)."""
    if r.error:
        return f"⚠ {r.error}"
    if r.hidden:
        return "hidden — not numbered"
    lab = r.label()
    if r.conflict:
        text = f"⚠ {lab}: {r.conflict}"
    elif r.source == "override":
        text = f"override {lab}"
    elif r.source == "fixed":
        text = f"kept {lab} ({r.note or 'root tag'})"
    elif r.basis == "reused":
        text = f"⚠ auto {lab}: reuses a retired id (dictionary full)"
    elif r.basis == "reused-hidden":
        text = f"⚠ auto {lab}: takes a hidden copy's id (dictionary full)"
    else:
        # the id ledger (docs/proposal_aruco_ids_stability.md): "kept" = the
        # id this copy printed before; "new" = an id no copy ever printed
        why = {"ledger": " · kept", "previous": " · kept", "new": " · new"}.get(r.basis, "")
        text = f"auto {lab}{why}" + (f" (was #{r.base})" if r.needs_part else "")
    if r.linked:
        text += " · linked"
    return text


def _tone(r):
    """The Status colour (aruco_marker_table.TONES): red refusal, amber
    conflict / dictionary full / a part of its own, grey hidden."""
    if r.error:
        return "error"
    if r.hidden:
        return "muted"
    if r.conflict or r.basis in ("reused", "reused-hidden"):
        return "warn"
    return "part" if r.needs_part else ""


# -------------------------------------------------- verbatim from REF ArucoMarkers/aruco_ids_preview.py

T = None   # REF: `import aruco_marker_table as T`; set below to this module


def spec_of(specs, row):
    sp = specs.get((row.component, row.key))
    if sp is None:
        return None
    return dataclasses.replace(sp, marker_id=int(row.final))


def specs_of(coll):
    """{(component label, key): TagSpec as recorded} of a collection."""
    out = {}
    for t in coll.get("tags") or []:
        out[(t.component, t.key)] = t.spec
    return out


def marker_row(r, specs, part_paths=None, **kw):
    """An IdsRow as the shared table's row (aruco_marker_table.MarkerRow):
    what it prints after OK, where it is, what a click on it in the viewport
    may hit (the copy, or after OK its part). `kw`: status, tone, tip."""
    picks = (r.path,)
    if part_paths and part_paths.get(r.path):
        picks = (part_paths[r.path], r.path)
    return T.make_row(r.path, r.key, spec_of(specs, r), ids=list(r.ids), frame=r.world,
                      layout=r.layout, dictionary=r.dictionary, hidden=bool(r.hidden),
                      linked=bool(r.linked), component=r.component, pick_paths=picks, **kw)


import sys as _sys  # noqa: E402

T = _sys.modules[__name__]
