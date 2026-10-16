# REF: tests/test_aruco_label_rule1.py at c8216ff (cad-exporter), ported by tools/port_ref_suites.py:
# REF's checks verbatim, run against aruco_studio.core. Do not edit by hand.
"""Offline: a label made under the OLD rule never moves on its own.

The coordinator, 2026-10-13: "Existing labels must NOT move on their own:
Zach may already have printed tags, and a Compute All mustn't silently move
a white label from 2 to 1.25 modules." The label settings carry "rule":

    1  before 2026-10-13: one line, 2 modules from the black (the quiet ring
       + WHITE_GAP 1.0), the old auto search -- every record without "rule"
    2  the quiet ring is the hard line, 0.25 module preferred, the far search

tests/fixtures/aruco_label_rule1_golden.json holds 36 labels laid out by the
code of 8473e14 (tools/make_label_rule1_golden.py): strips, faces with holes,
keep-outs, typed caps, refusals, old offsets, Zach's GIM43 disc. Recomputed
today from the same settings (no "rule"), each must come out IDENTICAL: the
same kind and side, every slot, part and stroke to 1e-6 mm, the same grown
white, the same preview. And the same settings under rule 2 do move.

Run:  python tests/test_aruco_label_rule1.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
pass  # REF put its own tree on sys.path here (ported: not needed)
pass  # REF put its own tree on sys.path here (ported: not needed)

from aruco_studio.core import chamfer as C  # noqa: E402
from aruco_studio.core import label as L  # noqa: E402
from aruco_studio.core import markers as M  # noqa: E402

import ref_make_label_rule1_golden as G  # noqa: E402

PASS, FAIL = 0, []
TOL_MM = 1e-6


def check(label, condition, detail=""):
    global PASS
    if condition:
        PASS += 1
        print(f"  ok  {label}")
    else:
        FAIL.append(label)
        print(f"FAIL  {label}  {detail}")


def diff(a, b, path=""):
    """The first place two shapes differ (floats to TOL_MM), or ""."""
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            d = diff(a.get(k), b.get(k), f"{path}.{k}")
            if d:
                return d
        return ""
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            return f"{path}: {len(a)} items vs {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            d = diff(x, y, f"{path}[{i}]")
            if d:
                return d
        return ""
    if isinstance(a, float) or isinstance(b, float):
        try:
            return "" if abs(float(a) - float(b)) <= TOL_MM else f"{path}: {a} vs {b}"
        except (TypeError, ValueError):
            return f"{path}: {a!r} vs {b!r}"
    return "" if a == b else f"{path}: {a!r} vs {b!r}"


data = json.loads((Path(__file__).resolve().parents[3] / "goldens" / "ref" / "aruco_label_rule1_golden.json").read_text(encoding="utf-8"))["golden"]

print("== settings: no 'rule' is rule 1; a new label is rule 2")
check("LabelSettings() is rule 2 (what new labels are made under)",
      L.LabelSettings().rule == 2 == L.RULE)
check("a stored dict without 'rule' is rule 1, and says so when written back",
      L.LabelSettings.from_dict({"on": True}).rule == 1
      and L.LabelSettings.from_dict({"on": True}).to_dict()["rule"] == 1)
check("an unknown rule falls back to the new one, with a note",
      L.LabelSettings.from_dict({"on": True, "rule": 7}).rule == 2)

print(f"== {len(data['cases'])} labels laid out by {data['core']}: identical today")
moved = 0
for case in data["cases"]:
    assert "rule" not in case["settings"]
    got = G.shape(G.run(case, L, M, C))
    d = diff(case["golden"], got)
    check(f"rule 1, {case['name']}: identical ({got['kind']}"
          f"{', ' + got['side'] if got['side'] else ''})", not d, d)
    two = G.shape(G.run(dict(case, settings=dict(case["settings"], rule=2)), L, M, C))
    moved += bool(diff(case["golden"], two))
check(f"... and under rule 2 the same settings DO change ({moved} of {len(data['cases'])}): the "
      "rule is what keeps them", moved >= 10, moved)

print("== Zach's GIM43 disc, his old Offset (6, 4) record")
case = next(c for c in data["cases"] if c["name"] == "GIM43 Zach's offset (6, 4)")
lab = G.run(case, L, M, C)
check("rule 1: refused as it was, its two old reasons kept (the 2-module line, the hole)",
      lab.kind == "none" and lab.preview is not None and len(lab.preview.violations) == 2
      and any("1 module kept around the detector's clear zone" in v
              for v in lab.preview.violations)
      and any("from a hole" in v for v in lab.preview.violations), lab.preview.violations)
lines = L.describe(lab, "black")
check("the dialog says it is the older rule, in one grey line, and how to leave it",
      any(lv == L.NOTE and "older label rule" in t.lower() and "new" in t for lv, t in lines), lines)
two = G.run(dict(case, settings=dict(case["settings"], rule=2)), L, M, C)
check("... rule 2 says nothing of the sort",
      not any("older label rule" in t.lower() for _lv, t in L.describe(two, "black")))

print("== a rule-1 label keeps rule 1 through a record and a copy")
case = next(c for c in data["cases"] if c["name"] == "strip offset (+2, -1.5)")
lab = G.run(case, L, M, C)
rec = json.loads(json.dumps(lab.to_dict()))
back = L.from_dict(rec)
cp = L.relabel(rec, M.TagSpec(marker_id=31, marker_length_m=0.03))
check("the record keeps rule 1; a copy prints in the same slot",
      rec["settings"]["rule"] == 1 and back.settings.rule == 1
      and [s.rect for s in cp.slots] == [s.rect for s in lab.slots] and cp.ok, rec["settings"])
z1, z2 = L.clear_zones(M.TagSpec(**G.SINGLE), rule=1), L.clear_zones(M.TagSpec(**G.SINGLE))
check("clear_zones: rule 1's one line is 2 modules out; rule 2's hard line is the quiet ring",
      z1["hard"] == z1["preferred"] == (-25.0, -25.0, 25.0, 25.0)
      and z2["hard"] == (-20.0, -20.0, 20.0, 20.0), (z1, z2))

print()
print(f"{PASS} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
