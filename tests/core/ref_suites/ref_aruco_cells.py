# REF: tests/test_aruco_cells.py at c8216ff (cad-exporter), ported by tools/port_ref_suites.py:
# REF's checks verbatim, run against aruco_studio.core. Do not edit by hand.
"""Offline tests for the CELL rule (bam_cad_core.aruco_autosize, `cells=`).

Zach, 2026-10-14: "Ability to set a custom width multiple of the marker, so
it could be 0.5 mm (default), but for a 0.6 mm nozzle maybe I want to round
to a multiple of 0.675 mm". The research he pasted: make each cell a clean
multiple of the line width. Under {"of": "cell", "mm": m}:

    module = k m (k >= 1), marker L = n k m
    ChArUco square S = j m, the white around its marker (S - L) / 2 = i m,
            i >= k (one module at least)
    grid gap = a whole number of m, >= max(0.2 L, L / n)
    a typed size snaps DOWN onto the grid, noted
    Auto (a single marker on a face): the LARGEST k whose sticker still fits

and {"of": "marker", "mm": m} is the legacy rule on another step. Checked
against brute force over random faces, and on faces with holes.

Run:  python tests/test_aruco_cells.py
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

pass  # REF put its own tree on sys.path here (ported: not needed)

from aruco_studio.core import autosize as A  # noqa: E402
from aruco_studio.core import board as aruco_board  # noqa: E402
from aruco_studio.core import markers as M  # noqa: E402

try:
    sys.stdout.reconfigure(errors="replace")
except AttributeError:
    pass

PASS, FAIL = 0, []


def check(label, condition, detail=""):
    global PASS
    if condition:
        PASS += 1
        print(f"  ok  {label}")
    else:
        FAIL.append(label)
        print(f"FAIL  {label}  {detail}")


def mm(v):
    return None if v is None else v / 1000.0


def cells(m, of="cell", min_mm=0.0):
    return {"rule": 1, "of": of, "mm": m, "min_mm": min_mm}


def whole(x_m, m_mm, tol=1e-9):
    """Is x a whole number (>= 1) of m?"""
    q = x_m / (m_mm / 1000.0)
    return round(q) >= 1 and abs(q - round(q)) < tol * 1e3


def n_of(d):
    return M.dictionary_bits(d) + 2


def on_grid(lay, m, d="DICT_4X4_50"):
    """Every length of a cell-rule layout a whole number of m, as the rule says."""
    n = n_of(d)
    if lay.marker_m <= 0:
        return False, "no marker"
    k = lay.marker_m / n / (m / 1000.0)
    if abs(k - round(k)) > 1e-6 or round(k) < 1:
        return False, f"module {lay.module_m * 1000:.4f} mm is {k:.4f} x {m}"
    k = round(k)
    if lay.kind == "grid" and not whole(lay.separation_m, m):
        return False, f"gap {lay.separation_m * 1000:.4f}"
    if lay.kind == "grid" and lay.separation_m < max(0.2 * lay.marker_m, lay.module_m) - 1e-9:
        return False, "gap under the rule"
    if lay.kind == "charuco":
        if not whole(lay.square_m, m):
            return False, f"square {lay.square_m * 1000:.4f}"
        white = (lay.square_m - lay.marker_m) / 2.0
        i = white / (m / 1000.0)
        if abs(i - round(i)) > 1e-6:
            return False, f"white around the marker {white * 1000:.4f} mm = {i:.3f} x {m}"
        if round(i) < k:
            return False, f"white {round(i)} < one module ({k})"
    return True, ""


C68 = cells(0.68)

print("== the spec's example: a typed 28.0 mm 6x6 marker at 0.68 mm lines")
lay = A.clamp_to_fit("single", mm(40), mm(40), mm(28.0), dictionary="DICT_6X6_250", cells=C68)
check("28.0 mm -> 27.2 mm, the note word for word",
      abs(lay.marker_m - 0.0272) < 1e-12 and lay.ok
      and lay.notes == ["cell multiple: 28.0 mm → 27.2 mm: cells 3.40 mm = 5 × 0.68 mm"],
      (lay.marker_m, lay.notes))
lay = A.layout_for_size("single", mm(40), mm(40), mm(28.0), dictionary="DICT_6X6_250", cells=C68)
check("layout_for_size snaps the same way, with the same note",
      abs(lay.marker_m - 0.0272) < 1e-12 and lay.notes[0].startswith("cell multiple: 28.0 mm"))
lay = A.clamp_to_fit("single", mm(40), mm(40), mm(27.2), dictionary="DICT_6X6_250", cells=C68)
check("a typed size already on the grid: as typed, no note", abs(lay.marker_m - 0.0272) < 1e-12
      and not any(t.startswith("cell multiple") for t in lay.notes), lay.notes)
lay = A.clamp_to_fit("single", mm(40), mm(40), mm(2.0), cells=C68)
check("a typed size under one multiple: one multiple (4.08 mm for 4x4), noted",
      abs(lay.marker_m - 0.00408) < 1e-12 and lay.notes and "2.0 mm → 4.08 mm" in lay.notes[0],
      lay.notes)
lay = A.clamp_to_fit("single", mm(20), mm(20), mm(30.0), cells=C68)
check("too big AND off the grid: snapped (noted), then clamped to the largest that fits "
      "(noted), still on the grid",
      lay.ok and on_grid(lay, 0.68)[0] and lay.tile_m[0] <= 0.020 + 1e-12
      and lay.notes[0].startswith("cell multiple: 30.0 mm → 28.56 mm")
      and any(t.startswith("clamped") for t in lay.notes), lay.notes)

print("== Auto on a face: the largest k whose sticker still fits (brute force)")
rng = random.Random(14)
bad = []
for _ in range(300):
    W, H = rng.uniform(8, 160), rng.uniform(8, 160)
    m = rng.choice((0.4, 0.45, 0.5, 0.675, 0.68, 0.27))
    d = rng.choice(("DICT_4X4_50", "DICT_5X5_100", "DICT_6X6_250", "DICT_7X7_50"))
    q = rng.choice((1.0, 0.0, 2.0))
    n = n_of(d)
    lay = A.face_default("single", mm(W), mm(H), dictionary=d, quiet_modules=q, cells=cells(m))
    # brute force: the largest k with (n + 2q) k m <= min(W, H) - 2 * 5 um, preferring printable
    side = min(W, H) - 2 * A.FILL_CLEARANCE_M * 1000.0
    ks = [k for k in range(1, 2000) if (n + 2 * q) * k * m <= side + 1e-9]
    printable = [k for k in ks if k * m >= 1.2 - 1e-9]
    want = (max(printable) if printable else (max(ks) if ks else 0))
    got = round(lay.marker_m / n / (m / 1000.0)) if lay.marker_m > 0 else 0
    if got != want or (lay.marker_m > 0 and not on_grid(lay, m, d)[0]):
        bad.append((W, H, m, d, q, got, want, lay.notes))
check("300 random faces x 6 multiples x 4 dictionaries x 3 quiet zones: Auto = the largest "
      "k that fits", not bad, bad[:3])

print("== boards: every length whole, the board fits, nothing overlaps")
bad = []
for _ in range(300):
    W, H = rng.uniform(20, 250), rng.uniform(20, 250)
    m = rng.choice((0.4, 0.45, 0.5, 0.675, 0.68))
    d = rng.choice(("DICT_4X4_50", "DICT_4X4_1000", "DICT_5X5_100", "DICT_6X6_250"))
    kind = rng.choice(("grid", "charuco"))
    for lay in (A.default_layout(kind, mm(W), mm(H), dictionary=d, cells=cells(m)),
                A.clamp_to_fit(kind, mm(W), mm(H), mm(rng.uniform(4, 40)),
                               mm(rng.uniform(6, 50)) if kind == "charuco" else 0.0,
                               dictionary=d, cells=cells(m))):
        if lay.marker_m <= 0 or not lay.ok:
            continue
        ok, why = on_grid(lay, m, d)
        tw, th = lay.tile_m
        fits = tw <= mm(W) + 1e-9 and th <= mm(H) + 1e-9
        try:
            aruco_board.check_spec(aruco_board.BoardSpec(
                layout=lay.kind, dictionary=d, first_id=0, marker_length_m=lay.marker_m,
                rows=lay.rows, cols=lay.cols, separation_m=lay.separation_m,
                square_length_m=lay.square_m))
            cv_ok = True
        except ValueError:
            cv_ok = False
        if not (ok and fits and cv_ok):
            bad.append((kind, W, H, m, d, lay.label(), why, fits, cv_ok))
check("600 boards (defaults and typed): on the grid, inside the face, OpenCV-valid",
      not bad, bad[:3])

print("== ChArUco: whole white around the marker, odd module counts too")
for d, m in (("DICT_4X4_50", 0.68), ("DICT_5X5_100", 0.68), ("DICT_7X7_50", 0.5),
             ("DICT_5X5_100", 0.45)):
    lay = A.default_layout("charuco", mm(100), mm(60), dictionary=d, cells=cells(m))
    ok, why = on_grid(lay, m, d)
    check(f"{d} at {m}: {lay.label()} -- whole", lay.ok and ok, why)
lay = A.clamp_to_fit("charuco", mm(100), mm(60), mm(14), mm(20), cells=C68)
check("typed 20 / 14 mm at 0.68: 19.04 / 12.24 mm (28 and 3 x 6 lines, 3 lines of white "
      "each side), noted", abs(lay.square_m - 0.01904) < 1e-12 and abs(lay.marker_m - 0.01224) < 1e-12
      and lay.notes[0] == "cell multiple: checker 20.0 mm → 19.04 mm, marker 14.0 mm → 12.24 mm: "
                          "cells 2.04 mm = 3 × 0.68 mm", lay.notes)
lay = A.clamp_to_fit("charuco", mm(100), mm(60), mm(3.5), mm(10.0), dictionary="DICT_5X5_100",
                     cells=cells(0.5))
check("5x5 (7 modules), 0.5 mm: a 3.5 mm marker in a typed 10.0 mm square would leave 3.25 mm "
      "-- the square steps to 9.5 (whole 3.0 mm white)",
      abs(lay.square_m - 0.0095) < 1e-12 and abs(lay.marker_m - 0.0035) < 1e-12
      and on_grid(lay, 0.5, "DICT_5X5_100")[0], (lay.label(), lay.notes))
lay = A.clamp_to_fit("charuco", mm(100), mm(60), mm(20), mm(20), cells=C68)
check("a typed marker too big for its square: the marker follows the square down (clamped)",
      lay.ok and on_grid(lay, 0.68)[0] and lay.marker_m < 0.0195, (lay.label(), lay.notes))

print("== grids: the gap rounds UP to whole lines")
lay = A.layout_for_size("grid", mm(100), mm(60), mm(20.4), cells=C68)
check("20.4 mm markers (5 x 0.68 cells): gap max(4.08, 3.4) = 4.08 = 6 lines",
      abs(lay.separation_m - 0.00408) < 1e-12, lay.separation_m)
lay = A.layout_for_size("grid", mm(100), mm(60), mm(16.32), cells=C68)
check("16.32 mm (4 lines a cell): 0.2 L = 3.264 -> 3.4 (5 lines)",
      abs(lay.separation_m - 0.0034) < 1e-12, lay.separation_m)

print("== 'marker' cells: the legacy rule on another step (0.675 = Zach's 0.6 nozzle)")
for kind in ("single", "grid", "charuco"):
    lay = A.face_default(kind, mm(100), mm(60), cells=cells(0.675, "marker"))
    k = lay.marker_m / 0.000675
    ks = lay.square_m / 0.000675
    check(f"{kind}: {lay.label()} -- the marker{' and the checker' if kind == 'charuco' else ''} "
          "whole steps of 0.675", lay.ok and abs(k - round(k)) < 1e-6
          and abs(ks - round(ks)) < 1e-6)
lay = A.clamp_to_fit("single", mm(40), mm(40), mm(27.3), cells=cells(0.675, "marker"))
check("a typed size is used as typed (the legacy rule's way)", abs(lay.marker_m - 0.0273) < 1e-12
      and not lay.notes, lay.notes)

print("== the minimum cell: a note, never a refusal")
lay = A.face_default("single", mm(15), mm(15), cells=cells(0.5, min_mm=2.0))
check("a 15 mm face at 0.5: cells 1.5 mm < 2.0 -> built (ok), one 'cell minimum' note",
      lay.ok and sum(t.startswith("cell minimum: a 1.50 mm cell is under the 2.0 mm minimum")
                     for t in lay.notes) == 1, lay.notes)
lay = A.face_default("single", mm(40), mm(40), cells=cells(0.5, min_mm=2.0))
check("a 40 mm face: no note", lay.ok and not lay.notes, lay.notes)
lay = A.face_default("single", mm(15), mm(15), cells=cells(0.5, min_mm=0.0))
check("min 0: no note", not any(t.startswith("cell minimum") for t in lay.notes))

print("== a face that is not a rectangle (holes, a disc, an L)")


def circle(cx, cy, r, n=64, cw=False):
    pts = [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n))
           for k in range(n)]
    return pts[::-1] if cw else pts


GIM43 = [circle(2.09, 0.0, 26.5, 96)] + [circle(x, y, 1.425, 48, cw=True) for x, y in
                                         ((25.84, 0.0), (2.09, 23.75), (-21.66, 0.0), (2.09, -23.75))]
PLATE = [[(-60, -20), (60, -20), (60, 20), (-60, 20)], circle(-50, 0, 4, cw=True),
         circle(50, 0, 4, cw=True)]
ELL = [[(0, 0), (60, 0), (60, 20), (20, 20), (20, 60), (0, 60)]]
for name, loops in (("GIM43 disc", GIM43), ("plate with end holes", PLATE), ("an L", ELL)):
    lm = [[(x / 1000.0, y / 1000.0) for x, y in lp] for lp in loops]
    for kind in ("single", "grid", "charuco"):
        lay, pl = A.fit_on_loops(kind, lm, cells=C68)
        ok, why = on_grid(lay, 0.68) if lay.marker_m > 0 else (False, "nothing")
        # the L's 20 mm leg holds no printable ChArUco at 0.68 lines: two
        # squares of 16 lines (a 2-line cell, 2 lines of white) are 21.8 mm
        unprintable = name == "an L" and kind == "charuco"
        check(f"{name}, {kind} Auto: {lay.label()} -- on the grid, placed"
              + (" (nothing printable fits the 20 mm leg: said so, ok False)" if unprintable
                 else ""),
              ok and pl is not None and (lay.ok != unprintable)
              and (not unprintable or any("nothing printable fits" in t for t in lay.notes)),
              (why, lay.notes))
    lay, pl = A.fit_on_loops("single", lm, marker_m=mm(15.0), cells=C68)
    check(f"{name}, a typed 15.0 mm: 12.24 mm (3 x 0.68 cells), noted",
          abs(lay.marker_m - 0.01224) < 1e-12 and any(t.startswith("cell multiple: 15.0 mm → 12.24")
                                                      for t in lay.notes), lay.notes)
lm = [[(x / 1000.0, y / 1000.0) for x, y in lp] for lp in GIM43]
lay, _pl = A.fit_on_loops("single", lm, cells=C68)
side_ub = 2 * 26.5 / math.sqrt(2)                   # the disc's inscribed square, at most
k_ub = int((side_ub - 0.01) / (8 * 0.68))
check(f"GIM43 disc: Auto picks k = {round(lay.module_m / 0.00068)} (the inscribed square allows "
      f"at most {k_ub}; the holes cost no more than one)",
      k_ub - 1 <= round(lay.module_m / 0.00068) <= k_ub)

print("== the ranked lists: every entry on the grid")
for kind in ("grid", "charuco"):
    cs = A.candidates(kind, mm(100), mm(60), limit=None, cells=C68)
    bad = [c.label() for c in cs if not on_grid(c, 0.68)[0]]
    check(f"candidates {kind} on 100 x 60: {len(cs)} entries, all whole", cs and not bad, bad)
    lm = [[(x / 1000.0, y / 1000.0) for x, y in lp] for lp in PLATE]
    cs = A.candidates_on_loops(kind, lm, cells=C68)
    bad = [c.label() for c in cs if not on_grid(c, 0.68)[0]]
    check(f"candidates_on_loops {kind} on the plate: {len(cs)} entries, all whole, no snap notes",
          cs and not bad and not any(t.startswith("cell multiple") for c in cs for t in c.notes),
          bad)

print()
print(f"{PASS} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
