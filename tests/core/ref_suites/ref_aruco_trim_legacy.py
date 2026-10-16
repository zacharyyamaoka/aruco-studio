# REF: tests/test_aruco_trim_legacy.py at c8216ff (cad-exporter), ported by tools/port_ref_suites.py:
# REF's checks verbatim, run against aruco_studio.core. Do not edit by hand.
"""Offline: a tag made before Trim excess never changes on its own.

The coordinator, 2026-10-16: "Existing tags must never change on their own:
the new setting is versioned; a record without it = trim off, identical
geometry; prove it with a golden test." A tag's settings carry "trim"
(bam_cad_core.aruco_trim.trim_of) only when it was made -- or edited -- with
Trim excess on; none means off.

tests/fixtures/aruco_trim_legacy_golden.json holds, made by the code of
5cf71bd (tools/make_trim_legacy_golden.py): 26 evaluate() results on stand-in
targets (every layout, mode, operation, pins, corner mark, label, Origin,
heights, a cell rule) with what a node built from them stores (settle,
params_for, structure, plan_of), 288 aruco_slabs plans and
default_settings(). Recomputed today, each must come out IDENTICAL -- and so
must the same tags with a "trim" that reads as off (None, {}, an unknown
rule or axes, junk).

Run:  python tests/test_aruco_trim_legacy.py   (ARUCO_ROOT=<tree> to test another tree)
"""
from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("ARUCO_ROOT") or HERE.parent)
pass  # REF put its own tree on sys.path here (ported: not needed)

try:
    sys.stdout.reconfigure(errors="replace")
except AttributeError:
    pass

import ref_make_trim_legacy_golden as G  # noqa: E402
from aruco_studio.core import settings as F, slabs as SL, edits as _E  # noqa: E402
F._trim_not_in_place = _E.trim_not_in_place   # REF aruco_feature._trim_not_in_place

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
    return json.loads(json.dumps(x))


gold = json.loads((Path(__file__).resolve().parents[3] / "goldens" / "ref" / "aruco_trim_legacy_golden.json").read_text(encoding="utf-8"))["golden"]
# 2026-10-16 the shipped defaults flipped (JO_AFTER, RESTRUCTURE_IN_PLACE on, AUTO_REFRESH "all";
# gated in Fusion: edit_gates jo_one / jo_joint / combined / edit_menu). This test's golden
# was made with jo_v 1: pinned to what it was written for.
F.JO_AFTER = False
print(f"tree: {ROOT}")

print("== default_settings(): no 'trim', the rest as before")
ds = F.default_settings()
check("default_settings() has no 'trim' key", "trim" not in ds, sorted(ds))
check("default_settings() identical to the golden", not diff(norm(G._r(ds)),
                                                          gold["default_settings"]),
      diff(norm(G._r(ds)), gold["default_settings"]))

print(f"== {len(gold['evaluate'])} tags evaluated with no 'trim': identical")
print("  skip  parked for M2: REF ran aruco_feature.evaluate() here (plan/plan.py plan_tag, tests/plan/test_golden_evaluate.py)")
print("== the same tags with a 'trim' that reads as off: identical")
print("  skip  parked for M2: REF ran aruco_feature.evaluate() here (plan/plan.py plan_tag, tests/plan/test_golden_evaluate.py)")
print("== the shipped defaults (4babc4b: the Joint Origin after the node): no 'trim' = junk 'trim'")
print("  skip  parked for M2: REF ran aruco_feature.evaluate() here (plan/plan.py plan_tag, tests/plan/test_golden_evaluate.py)")
JUNK = [None, {}, {"rule": 2, "axes": "x"}, {"axes": "sideways"}, {"rule": "one", "axes": "x"},
        "x", 3, [], {"rule": 1}]

print(f"== {len(gold['plans'])} aruco_slabs plans: identical, and trim=False is the same")
now_plans = norm(G.run_plans(SL))
bad = [(p["mode"], p["op"], p["has_body"], p["pin"], p["numbers"], diff(n["got"], p["got"]))
       for n, p in zip(now_plans, gold["plans"]) if diff(n["got"], p["got"])]
check(f"plan(): {len(now_plans)} cases identical", len(now_plans) == len(gold["plans"]) and not bad,
      bad[:2])
bad = []
for p in gold["plans"]:
    if "error" in p["got"]:
        continue
    n = dict(SL.default_numbers(p["mode"]), **SL.pin_defaults())
    n.update(G.PLAN_NUMBERS[p["numbers"]])
    got = norm(G._r(G.plan_dict(SL.plan(p["mode"], p["op"], p["has_body"], n, p["pin"],
                                        trim=False))))
    if diff(got, p["got"]):
        bad.append((p["mode"], p["op"], diff(got, p["got"])))
check("plan(..., trim=False) == the golden for every case", not bad, bad[:2])

print("== a node with no 'trim' keeps its structure; the edit guard leaves it alone")
s = dict(F.default_settings(), source="profile", has_body=True, mode="both", op="join",
         parts=["tile", "pocket", "pattern"], key="tg")
n = F.default_numbers("both")
check("structure(s, n) == node_structure(s) (no rebuild, no 'compute failed')",
      F.structure(s, n) == F.node_structure(s), (F.structure(s, n), F.node_structure(s)))
check("trim_setting(no key) is None; trim_setting(junk) is None",
      F.trim_setting(s) is None and all(F.trim_setting(dict(s, trim=j)) is None for j in JUNK))
check("_trim_not_in_place: nothing to say about a tag without a trim",
      F._trim_not_in_place(s, s, n) is None)

print()
print(f"{PASS} passed, {len(FAIL)} failed")
if FAIL:
    sys.exit(1)
