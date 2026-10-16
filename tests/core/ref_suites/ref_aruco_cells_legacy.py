# REF: tests/test_aruco_cells_legacy.py at c8216ff (cad-exporter), ported by tools/port_ref_suites.py:
# REF's checks verbatim, run against aruco_studio.core. Do not edit by hand.
"""Offline: a tag made before cell multiples never changes size on its own.

The coordinator, 2026-10-14: "Existing tags must NEVER change on their own
(size, cells, heights, labels). Version every new rule in the stored
settings ... A record without the new key keeps its exact old geometry on
recompute; prove it with a golden test." A tag's settings carry "cells"
(bam_cad_core.aruco_autosize.cells_of) only when it was made -- or its size
settings were edited -- under the cell rule; none means the LEGACY rule:
the marker and the checker in 0.5 mm steps, typed sizes as typed.

tests/fixtures/aruco_cells_legacy_golden.json holds 511 sizings and 12
evaluate() results made by the code of 196454c (tools/make_cells_legacy_golden.py):
defaults, face defaults, ranked lists, typed and clamped sizes on boxes and
on faces with holes, every kind, five dictionaries, four quiet zones.
Recomputed today with no "cells", each must come out IDENTICAL -- every
Layout field (floats exactly, notes word for word), every placement, every
board as built. And "marker" cells with the 0.5 mm step are the same rule.

Run:  python tests/test_aruco_cells_legacy.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
pass  # REF put its own tree on sys.path here (ported: not needed)
pass  # REF put its own tree on sys.path here (ported: not needed)
os.environ["USERPROFILE"] = os.environ["HOME"] = tempfile.mkdtemp(prefix="aruco_cells_legacy_")

try:
    sys.stdout.reconfigure(errors="replace")
except AttributeError:
    pass

from aruco_studio.core import autosize as A  # noqa: E402

import ref_make_cells_legacy_golden as G  # noqa: E402

PASS, FAIL = 0, []


def check(label, condition, detail=""):
    global PASS
    if condition:
        PASS += 1
        print(f"  ok  {label}")
    else:
        FAIL.append(label)
        print(f"FAIL  {label}  {detail}")


def diff(a, b, path=""):
    """The first place two results differ (EXACT: floats too), or ""."""
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
    return "" if a == b else f"{path}: {a!r} vs {b!r}"


def norm(x):
    """JSON's view (tuples -> lists), as the golden was written."""
    return json.loads(json.dumps(x))


data = json.loads((Path(__file__).resolve().parents[3] / "goldens" / "ref" / "aruco_cells_legacy_golden.json").read_text(encoding="utf-8"))["golden"]

print("== the legacy rule: no 'cells' is None, so is anything unreadable")
check("cells_of: None, {}, a bad 'of', a zero / absurd step -> None (the legacy rule)",
      all(A.cells_of(c) is None for c in (None, {}, {"of": "lines", "mm": 0.5},
                                           {"of": "cell", "mm": 0}, {"of": "cell", "mm": 50},
                                           {"of": "cell"}, "cell", 3)))
check("cells_of: a stored dict (mm) -> (of, step m, min m)",
      A.cells_of({"rule": 1, "of": "cell", "mm": 0.68, "min_mm": 2.0}) == ("cell", 0.00068, 0.002))

print(f"== {len(data['cases'])} sizings recomputed with no 'cells': identical")
by_fn = {}
bad = []
for case in data["cases"]:
    got = norm(G.run(case, A))
    d = diff(got, case["got"])
    by_fn.setdefault(case["fn"], [0, 0])
    by_fn[case["fn"]][0] += 1
    if d:
        by_fn[case["fn"]][1] += 1
        bad.append((case["fn"], case["kw"], d))
for fn, (n, nbad) in sorted(by_fn.items()):
    check(f"{fn}: {n} cases identical", nbad == 0,
          next((f"{kw}: {d}" for f_, kw, d in bad if f_ == fn), ""))

print("== 'marker' cells with the 0.5 mm step (and no minimum) ARE the legacy rule")
legacy_step = {"rule": 1, "of": "marker", "mm": 0.5, "min_mm": 0.0}
real_kw = dict(G.run.__globals__)


def run_with(case, cells):
    """G.run with `cells` passed to every autosize call."""
    class Shim:
        def __getattr__(self, name):
            fn = getattr(A, name)
            if not callable(fn):
                return fn

            def call(*a, **k):
                return fn(*a, cells=cells, **k)
            return call
    return G.run(case, Shim())


bad = []
for case in data["cases"]:
    d = diff(norm(run_with(case, legacy_step)), case["got"])
    if d:
        bad.append((case["fn"], case["kw"], d))
check(f"all {len(data['cases'])} sizings identical under {{'of': 'marker', 'mm': 0.5}}",
      not bad, bad[:2])

print(f"== {len(data['evaluate'])} evaluate() results (aruco_feature, no 'cells' in the "
      "settings): identical")
print("  skip  parked for M2: evaluate() is plan/plan.py's plan_tag "
      f"({len(data['evaluate'])} cases, tests/plan/test_golden_evaluate.py)")
for want, got in []:
    label = f"{want['settings'].get('layout')} {want['settings'].get('mode')} " \
            f"{want['shape'] or 'area %s' % want['area']} {want['numbers'] or 'auto'}"
    d = diff(norm(got["got"]), want["got"])
    check(f"evaluate: {label}", not d, d)

print()
print(f"{PASS} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
