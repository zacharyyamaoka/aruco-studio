"""The Export table's rows and words.

Ported from REF (cad-exporter c8216ff) `ArucoMarkers/aruco_commands.py`
(`_split_black`, `_plural`, `eta_text`, `progress_message`, `_dup_rows`,
`_export_status`, `_tick_part`), `aruco_export.py` (`_slug`, `SLOTS`,
`KINDS`) and `aruco_export_preview.py` (`_ids_text`), verbatim.

Not here: `body_role` (it reads Fusion's body NAMES, "tag tile <key>": the
adapter's), and the rows' collection from the design (`print_rows`,
`tag_parts`, `_export_rows`: they walk Fusion's occurrences; the Studio
builds rows from its scene). Which files each type writes is the server's
export (M2b), from `KINDS`.
"""
from __future__ import annotations

import re

from . import marker_table as T


# -------------------------------------------------- verbatim from REF ArucoMarkers/aruco_commands.py

def _split_black(thickness_m, sits):
    """(depth_m, raise_m) for a black layer of `thickness_m`."""
    if sits == "raised":
        return 0.0, thickness_m
    if sits == "half":
        return thickness_m / 2.0, thickness_m / 2.0
    return thickness_m, 0.0


def _plural(n, one, many=None):
    return f"{n} {one if n == 1 else (many or one + 's')}"


def eta_text(done, total, elapsed_s):
    """The time left, from the export's own pace so far: "about 40 s left",
    "about 3 min left"; "estimating..." until two parts are written."""
    if not total or done is None or done < 2 or elapsed_s <= 0:
        return "estimating time left..."
    left = elapsed_s / float(done) * max(0, total - done)
    if left < 1.5:
        return "almost done"
    if left < 90:
        return f"about {int(round(left / 5.0) * 5) or 1} s left"
    return f"about {int(round(left / 60.0))} min left"


def progress_message(done, total, label, elapsed_s):
    """The progress dialog's text: where it is, the time left, what it is
    working on (Zach 2026-10-10: "a loading bar with estimated time, and
    tells me what its currently working on")."""
    label = (label or "").replace("%", "")
    if done is None:                               # a step without a count
        return f"{label}..." + chr(10) + "(the last step; a few seconds)"
    # 1-based while a part is being written ("Part 1 of 36" for the first)
    return (f"Part {min(done + 1, total or done + 1)} of {total or '?'} · "
            f"{eta_text(done, total, elapsed_s)}" + chr(10) + f"Writing: {label}")


def _dup_rows(rows):
    """Row names that print the same marker as another visible row."""
    return {n for names in T.duplicates(rows).values() for n in names}


def _export_status(row, on, info, dup=False):
    """The Status words of an Export row -> (text, tone)."""
    if info.get("root"):
        return "root component — not a part (PDF only)", "muted"
    if row.hidden:
        text, tone = "hidden — not printed", "muted"
    elif on:
        n = int(info.get("copies") or 0)
        text = ("prints · its ArUco IDs part" if info.get("own_part")
                else f"prints · {row.part}" + (f" ×{n}" if n > 1 else ""))
        tone = ""
    else:
        text, tone = f"not ticked · {row.part}", "muted"
    if row.linked:
        text += " · linked"
    if dup and not row.hidden:
        text += " · ⚠ the same marker as another copy"
        tone = "warn"
    return text, tone


def _tick_part(cid):
    """'part_3' / 'part_3__1' -> 3; anything else -> None."""
    if not cid.startswith("part_"):
        return None
    head = cid[5:].split("__", 1)[0]
    return int(head) if head.isdigit() else None


# -------------------------------------------------- verbatim from REF ArucoMarkers/aruco_export.py

def _slug(s):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_") or "design"


SLOTS = (1, 2, 3, 4, 5)


# ArUco Export's types (Zach 2026-10-08: one type per export, chosen at the
# top of the dialog like Fusion's Save As Mesh). What each writes besides
# aruco.json + joint_origins.json, which every export writes:
#   prusaslicer  aruco/print3d/: one STL per body + parts.json, the multi-bed
#                project aruco_tags.3mf (MMU colours), beds/, parts/
#   stl          aruco/stl/<part>__<role>.stl: one STL per body of the chosen
#                parts, oriented for printing (print_beds.write_part_stls)
#   pdf          aruco/markers.json, aruco/images/, aruco/print_<page>.pdf
KINDS = ("prusaslicer", "stl", "pdf")


# -------------------------------------------------- verbatim from REF ArucoMarkers/aruco_export_preview.py

def _ids_text(spec):
    ids = list(spec.get("ids") or [spec.get("marker_id", 0)])
    return f"#{ids[0]}" if len(ids) == 1 else f"#{ids[0]}-{ids[-1]}"


# public names (ARCHITECTURE 3.1)
slug = _slug
plural = _plural
split_black = _split_black
export_status = _export_status
dup_rows = _dup_rows
ids_text = _ids_text
