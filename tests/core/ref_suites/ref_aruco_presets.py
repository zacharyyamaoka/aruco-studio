# REF: tests/test_aruco_presets.py at c8216ff (cad-exporter), ported by tools/port_ref_suites.py:
# REF's checks verbatim, run against aruco_studio.core. Do not edit by hand.
"""Offline tests for ArucoMarkers/aruco_presets (the print presets' store)
and ArucoMarkers/aruco_prusa (PrusaSlicer's print profiles, read only).

PrusaSlicer is a FIXTURE copy (tests/fixtures/prusaslicer): Zach's two
Aruco print presets verbatim, the vendor sections they inherit from, and a
sparse synthetic preset whose numbers come from the vendor chain -- never
his live folder. The presets file lives in a temp home.

Run:  python tests/test_aruco_presets.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
pass  # REF put its own tree on sys.path here (ported: not needed)
HOME = tempfile.mkdtemp(prefix="aruco_presets_")
os.environ["USERPROFILE"] = os.environ["HOME"] = HOME
FIX = str(Path(__file__).resolve().parents[3] / "goldens" / "prusaslicer")
os.environ["BAM_ARUCO_PRUSASLICER_DIR"] = FIX

try:
    sys.stdout.reconfigure(errors="replace")
except AttributeError:
    pass

from ref_store_shim import P, R  # noqa: E402   REF: aruco_presets, aruco_prusa (files)

PASS, FAIL = 0, []


def check(label, condition, detail=""):
    global PASS
    if condition:
        PASS += 1
        print(f"  ok  {label}")
    else:
        FAIL.append(label)
        print(f"FAIL  {label}  {detail}")


ARUCO = "0.32mm SPEED @MK4IS 0.6 - Aruco"
BLACK = "0.15mm SPEED @MK4IS 0.25 - Aruco Black"
SPARSE = "0.20mm Sparse test @0.4 nozzle"
PATH = P.presets_path()

print("== PrusaSlicer (the fixture): his profiles as the coordinator measured them")
check("the folder: the env var wins", R.config_dir() == FIX)
names = [u["name"] for u in R.user_prints()]
check("three print presets, by name", names == [BLACK, SPARSE, ARUCO], names)
a = R.profile(ARUCO)
check("Aruco 0.6: nozzle 0.6, lines 0.68, layers 0.32 / first 0.2, top infill 0.55, arachne, "
      "no ironing, from 0.32mm SPEED @MK4IS 0.6",
      a["nozzle_mm"] == 0.6 and a["line_mm"] == 0.68 and a["layer_mm"] == 0.32
      and a["first_layer_mm"] == 0.2 and a["widths"]["top_infill_extrusion_width"] == 0.55
      and a["perimeter_generator"] == "arachne" and a["ironing"] is False
      and a["inherits"] == ["0.32mm SPEED @MK4IS 0.6"], a)
b = R.profile(BLACK)
check("Aruco Black 0.25: nozzle 0.25, lines 0.27 (first layer 0.32), layers 0.15 / 0.2",
      b["nozzle_mm"] == 0.25 and b["line_mm"] == 0.27 and b["layer_mm"] == 0.15
      and b["first_layer_mm"] == 0.2 and b["widths"]["first_layer_extrusion_width"] == 0.32, b)
s = R.profile(SPARSE)
check("a sparse preset: its numbers from the vendor chain (0.20mm SPEED @MK4IS 0.4 -> "
      "*MK4IS_common*): 0.45 lines, 0.2 layers; nozzle 0.4 from the condition",
      s["line_mm"] == 0.45 and s["layer_mm"] == 0.2 and s["nozzle_mm"] == 0.4, s)
check("... its first layer 150 % of the FIRST LAYER height (0.3); its top infill 0 = the "
      "extrusion width", s["widths"]["first_layer_extrusion_width"] == 0.3
      and s["widths"]["top_infill_extrusion_width"] == 0.45, s["widths"])
sysp, chain = R.resolve("0.32mm SPEED @MK4IS 0.6")
check("a system preset resolves through its abstract parents (*MK4IS_common06* over "
      "*MK4IS_common*): 0.68 lines, 0.32 layers",
      sysp and sysp.get("extrusion_width") == "0.68" and sysp.get("layer_height") == "0.32"
      and "inherits" not in sysp, sysp and {k: sysp.get(k) for k in ("extrusion_width",
                                                                     "layer_height")})
check("no such profile: None", R.profile("nope") is None and R.resolve("nope") == (None, []))
check("widths: '0' is auto (1.125 x the nozzle), '105%' of the layer, a number as is",
      abs(R.width_of({"extrusion_width": "0"}, "extrusion_width", 0.6, 0.2, 0.2) - 0.675) < 1e-12
      and abs(R.width_of({"extrusion_width": "250%"}, "extrusion_width", 0.6, 0.2, 0.2) - 0.5)
      < 1e-12 and R.width_of({"extrusion_width": "0.45"}, "extrusion_width", 0.4, 0.2, 0.2) == 0.45)
check("the nozzle without a condition: from the name, then the output file name",
      R.nozzle_of({}, "0.30mm QUALITY @0.6 nozzle - GEARS") == 0.6
      and R.nozzle_of({}, "0.32mm ERGO @COREONE 0.6") == 0.6
      and R.nozzle_of({"output_filename_format": "{x}_0.25n_{y}"}, "x") == 0.25
      and R.nozzle_of({}, "plain") is None)
check("only 'Aruco' profiles are built-ins (case-insensitive)",
      [p["name"] for p in R.aruco_profiles()] == [BLACK, ARUCO])
check("describe: one line", R.describe(a) == f"{ARUCO}: nozzle 0.6, lines 0.68, layers 0.32 "
      "(first 0.2), arachne", R.describe(a))
check("a missing PrusaSlicer folder: nothing, no error",
      R.user_prints(os.path.join(HOME, "none")) == [] and R.aruco_profiles(
          os.path.join(HOME, "none")) == [])

print("== built-ins: Default (the dialog as it was) and PrusaSlicer's Aruco profiles")
cat = P.catalog()
check("the catalog: Default, then the two Aruco profiles; nothing of the user's yet",
      [(n, k) for n, _p, k in cat["items"]] == [("Default", "builtin"), (BLACK, "builtin"),
                                                (ARUCO, "builtin")]
      and cat["last"] is None and not cat["notes"], cat)
d = P.default_preset()
from aruco_studio.core import slabs as S
check("Default: the marker in 0.5 mm steps (the legacy rule's step), min cell 2 mm",
      d["cells"] == {"of": "marker", "step": "mm", "mm": 0.5, "min_mm": 2.0, "min_lines": 0})
check("Default: the dialog's defaults (heights 0 / 2.0 / -0.6 flush, Auto, Join, quiet 1, "
      "triangle pin, label off, nozzle 0.6)",
      d["tag"]["white_height_mm"] == S.WHITE_HEIGHT and d["tag"]["black_height_mm"] == S.BLACK_HEIGHT
      and d["tag"]["black_step_mm"] == 0.0 and d["tag"]["mode"] == "auto"
      and d["tag"]["pin"] == "triangle" and d["label"]["on"] is False
      and d["label"]["nozzle_mm"] == 0.6)
pa, kind = P.find(cat, ARUCO)
check("the Aruco 0.6 preset: its profile, every cell a whole number of its 0.68 line width, "
      "the label at its nozzle, otherwise Default",
      kind == "builtin" and pa["profile"]["line_mm"] == 0.68 and pa["profile"]["layer_mm"] == 0.32
      and pa["cells"]["of"] == "cell" and pa["cells"]["step"] == "line"
      and pa["label"]["nozzle_mm"] == 0.6 and pa["tag"] == d["tag"], pa)
check("cell_setting: what the tag stores -- {rule 1, cell, 0.68, min 2.0}",
      P.cell_setting(pa) == {"rule": 1, "of": "cell", "mm": 0.68, "min_mm": 2.0})
check("Default's tag setting: {rule 1, marker, 0.5, 2.0}",
      P.cell_setting(d) == {"rule": 1, "of": "marker", "mm": 0.5, "min_mm": 2.0})
pb = P.find(cat, BLACK)[0]
check("min cell in lines: 3 lines of 0.27 = 0.81 mm",
      P.cell_setting(dict(pb, cells=dict(pb["cells"], min_lines=3)))["min_mm"] == 0.81)

print("== save as / update / delete / last; built-ins are read only")
mine = P.normalise(dict(d, name="x"))
mine["tag"]["white_height_mm"] = 1.6
mine["tag"]["mode"] = "both"
got = P.save_as("Thin tiles", mine)
check("save as: under its name, and it is the last", got == "Thin tiles"
      and P.catalog()["last"] == "Thin tiles")
back = P.find(P.catalog(), "Thin tiles")
check("round trip: the same preset, a user one, after the built-ins",
      back[1] == "user" and P.same(back[0], mine) and back[0]["name"] == "Thin tiles"
      and [n for n, _p, _k in P.catalog()["items"]][-1] == "Thin tiles")
check("save as a taken name -- a built-in's or the user's -- gets ' (2)'",
      P.save_as("Default", mine) == "Default (2)" and P.save_as("Thin tiles", mine)
      == "Thin tiles (2)")
for bad in ("", "  ", P.THIS_TAG, P.IMPORT, "x (modified)", "y" * 81, P.SAVE_AS,
            P.SEPARATOR, "Update 'Default'", "Delete 'x'"):
    try:
        P.save_as(bad, mine)
        ok = False
    except ValueError:
        ok = True
    check(f"not a name: {bad[:20]!r}", ok)
mine2 = P.copy_of(mine)
mine2["tag"]["white_height_mm"] = 1.2
P.update("Thin tiles", mine2)
check("update: the user's preset changed", P.find(P.catalog(), "Thin tiles")[0]["tag"][
    "white_height_mm"] == 1.2)
for name in ("Default", ARUCO, "nope"):
    for fn in (P.update, P.delete):
        try:
            fn(name, mine) if fn is P.update else fn(name)
            ok = False
        except ValueError:
            ok = True
        check(f"{fn.__name__} refuses {name!r}", ok)
P.delete("Thin tiles (2)")
check("delete: gone; the others stay", P.find(P.catalog(), "Thin tiles (2)") == (None, None)
      and P.find(P.catalog(), "Thin tiles")[1] == "user")
P.set_last(ARUCO)
check("the last OK's preset is remembered (a built-in too)", P.catalog()["last"] == ARUCO)
P.set_last("Thin tiles")
P.delete("Thin tiles")
check("deleting the last one forgets it (Default is used)", P.catalog()["last"] is None)
raw = json.loads(Path(PATH).read_text(encoding="utf-8"))
check("the file: schema, last, the user's presets only (no built-ins)",
      raw["schema"] == P.SCHEMA and set(raw["presets"]) == {"Default (2)"}, raw.keys())

print("== a broken file: the built-ins + a note; the next save moves it aside")
Path(PATH).write_text("{ not json", encoding="utf-8")
cat = P.catalog()
check("unreadable: Default and PrusaSlicer's still listed, with a note",
      [n for n, _p, _k in cat["items"]] == ["Default", BLACK, ARUCO]
      and cat["notes"] and "could not be read" in cat["notes"][0], cat["notes"])
check("set_last leaves a broken file alone", P.set_last("Default") is False
      and Path(PATH).read_text(encoding="utf-8") == "{ not json")
P.save_as("Fresh", d)
aside = [f for f in os.listdir(os.path.dirname(PATH)) if f.startswith("aruco_presets.broken-")]
check("save: the broken file is moved aside (kept), the new one is written",
      len(aside) == 1 and Path(os.path.dirname(PATH), aside[0]).read_text(encoding="utf-8")
      == "{ not json" and P.find(P.catalog(), "Fresh")[1] == "user", aside)
Path(PATH).write_text(json.dumps({"schema": "bam_aruco_presets/9", "presets": {
    "Odd": {"tag": {"mode": "sideways", "white_height_mm": "tall", "quiet_modules": 9,
                    "pin_size_mm": 0.1, "dictionary": "DICT_5X5_100", "grow": 1},
            "cells": {"of": "cell", "step": "line", "mm": -1, "min_lines": 2.5},
            "label": {"place": "white", "cap_mm": 3.5, "content": 7}, "extra": 1},
    "This tag": {}, 5: {}}, "last": "Odd"}), encoding="utf-8")
cat = P.catalog()
odd = P.find(cat, "Odd")[0]
check("another schema: read, with a note", cat["notes"] and "bam_aruco_presets/9" in cat["notes"][0])
check("wrong values fall back to Default's, right ones are kept, unknown keys dropped",
      odd["tag"]["mode"] == "auto" and odd["tag"]["white_height_mm"] == 2.0
      and odd["tag"]["quiet_modules"] == 1.0 and odd["tag"]["pin_size_mm"] == 3.0
      and odd["tag"]["dictionary"] == "DICT_5X5_100" and odd["tag"]["grow"] is False
      and odd["cells"]["mm"] == 0.5 and odd["cells"]["min_lines"] == 0
      and odd["cells"]["step"] == "line" and odd["label"]["place"] == "white"
      and odd["label"]["cap_mm"] == 3.5 and odd["label"]["content"] == "id"
      and "extra" not in odd, odd)
check("a reserved name in the file is skipped", P.find(cat, "This tag") == (None, None)
      and cat["last"] == "Odd")
Path(PATH).write_text("[1, 2]", encoding="utf-8")
check("not a presets file (a list): the built-ins + a note",
      [n for n, _p, _k in P.catalog()["items"]] == ["Default", BLACK, ARUCO]
      and P.catalog()["notes"])
os.remove(PATH)

print("== Import from PrusaSlicer…: a preset of any print profile")
got, p = P.import_profile(SPARSE)
check("the sparse 0.4 profile: a user preset under its name, cells of its 0.45 line width, "
      "the label at 0.4", got == SPARSE and P.find(P.catalog(), SPARSE)[1] == "user"
      and P.cell_setting(p) == {"rule": 1, "of": "cell", "mm": 0.45, "min_mm": 2.0}
      and p["label"]["nozzle_mm"] == 0.4, p)
got2, _p2 = P.import_profile(ARUCO)
check("importing a built-in's profile: a copy of yours, ' (2)'", got2 == ARUCO + " (2)")
try:
    P.import_profile("nope")
    ok = False
except ValueError:
    ok = True
check("no such profile: refused", ok)

print("== the Min cell field and the words for a change")
check("parse_min: '2', '2.0 mm', '3 lines', '1 line', '' -> (mm, lines)",
      [P.parse_min(t) for t in ("2", "2.0 mm", "3 lines", "1 line", "", " 2,5mm ")]
      == [(2.0, 0), (2.0, 0), (0.0, 3), (0.0, 1), (0.0, 0), (2.5, 0)])
check("parse_min: nonsense, negative, half a line -> None",
      [P.parse_min(t) for t in ("abc", "-1 mm", "2.5 lines", "nan")] == [None] * 4)
check("min_text", P.min_text({"min_mm": 2.0, "min_lines": 0}) == "2 mm"
      and P.min_text({"min_mm": 0.0, "min_lines": 3}) == "3 lines")
words = P.describe_changes(d, pa)
check("describe_changes(Default -> Aruco 0.6): the profile, round, multiple of -- in words",
      words.startswith(f"printer profile none → {ARUCO}, round marker → cell, "
                       "multiple of mm → line"), words)
check("same / changes: equal presets differ in nothing; a height does",
      P.same(d, P.default_preset()) and P.changes(d, mine) and not P.changes(pa, pa))

print("== heights in layers: a note, never a snap (C)")
check("0.6 mm black at 0.32 / 0.2 layers, face down: not whole -- 0.52 or 0.84 mm would be",
      P.layer_note(-0.6, 0.32, 0.2) == "black 0.60 mm face down = the 0.2 mm first layer + "
      "1.25 × 0.32 mm: 0.52 mm or 0.84 mm prints whole layers (face up it depends on the part)",
      P.layer_note(-0.6, 0.32, 0.2))
check("whole layers (0.2, 0.52, 0.84), no layer height, no depth: no note",
      [P.layer_note(d, 0.32, 0.2) for d in (0.2, 0.52, 0.84)] == [None] * 3
      and P.layer_note(0.6, 0.0, 0.2) is None and P.layer_note(0.0, 0.32, 0.2) is None)
check("under the first layer: says so",
      P.layer_note(0.1, 0.32, 0.2).startswith("black 0.10 mm face down is under the 0.2 mm"))

print()
print(f"{PASS} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
