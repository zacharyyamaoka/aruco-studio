"""M2.1 / M2.2: REF's evaluate() goldens replay through the plan.

* goldens/evaluate/legacy.json: REF's own 12 cells + 26 trim evaluate()
  cases (tests/fixtures/aruco_*_legacy_golden.json) re-run at c8216ff on the
  stand-ins their makers used, every output kept;
* goldens/ref/aruco_{cells,trim}_legacy_golden.json: what the OLD code
  (196454c, 5cf71bd) gave for them -- REF's own bar (floats to 9 decimals);
* goldens/evaluate/matrix.json: 786 cases of REF's evaluate() at c8216ff.

Each replays exactly: floats too, and the sign of every zero.
"""
from __future__ import annotations

import collections
import json
import math

import pytest

import _evaluate_golden as G
from aruco_studio.core import settings as S
from aruco_studio.plan import plan_tag
from aruco_studio.plan.plan import settle
from aruco_studio.plan.spec import TagSpec

CELLS = "tests/test_aruco_cells_legacy.py"
TRIM = "tests/test_aruco_trim_legacy.py"
LEGACY_SHAPES = ("chamfer_true", "chamfer_false", "no_origin_v", "rotate_deg", "frame",
                 "legacy_numbers", "label_scope_square", "junk_trim", "no_label_rule")


def _strict(a, b, path=""):
    """G.diff, and the sign of a zero and the type of a number too."""
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            d = _strict(a.get(k), b.get(k), f"{path}.{k}")
            if d:
                return d
        return ""
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            return f"{path}: {len(a)} vs {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            d = _strict(x, y, f"{path}[{i}]")
            if d:
                return d
        return ""
    if isinstance(a, float) and isinstance(b, float):
        if a == b and math.copysign(1.0, a) == math.copysign(1.0, b):
            return ""
        return f"{path}: {a!r} vs {b!r}"
    return "" if a == b and type(a) is type(b) else f"{path}: {a!r} vs {b!r}"


def _replay(case):
    got, _ev = G.run_ref_inputs(case)
    want = case["out"]
    if "error" in want or "error" in got:
        return "" if want.get("error") == got.get("error") else \
            f"error: {want.get('error')!r} vs {got.get('error')!r}"
    return _strict(G.norm(got), {k: want[k] for k in got})


def _ref_golden(name):
    return json.loads((G.ROOT / "goldens" / "ref" / f"{name}.json").read_text(
        encoding="utf-8"))["golden"]


@pytest.mark.ref(CELLS, "== {len(data['evaluate'])} evaluate() results (aruco_feature, no "
                 "'cells' in the settings): identical")
def test_cells_legacy__12_evaluate_cases_against_196454c():
    """M2.1: REF's 12 cells-golden evaluate() cases, today's plan vs the code
    of 196454c (spec, tag, notes, layout)."""
    ref = _ref_golden("aruco_cells_legacy_golden")["evaluate"]
    cases = [c for c in G.cases("legacy") if c["group"] == "cells"]
    assert len(cases) == len(ref) == 12
    bad = []
    for c, want in zip(cases, ref):
        got, _ev = G.run_ref_inputs(c)
        assert "error" not in got, got
        mine = {"spec": got["ev"]["spec"], "tag": got["ev"]["tag"], "notes": got["ev"]["notes"],
                "layout": got["layout"]}
        d = G.diff(G.norm(mine), want["got"])
        if d:
            bad.append((c["id"], d))
    assert not bad, bad[:3]


def _trim_legacy_got(case):
    got, _ev = G.run_ref_inputs(case)
    assert "error" not in got, got
    s2 = got["settled"]["settings"]
    n2 = got["settled"]["numbers"]
    return G.norm(G.r9({"ev": got["ev"], "settled": {"settings": s2, "numbers": n2},
                        "params_for": S.params_for(s2), "structure": list(S.structure(s2, n2)),
                        "node_structure": list(S.node_structure(s2)),
                        "plan_of": G.plan_dict(S.plan_of(s2, n2))}))


def _trim_ref_shape(got):
    """REF's trim golden keeps evaluate()'s fields of its own day (no
    "trim" key in the ev then)."""
    return got


@pytest.mark.ref(TRIM, "== {len(gold['evaluate'])} tags evaluated with no 'trim': identical")
def test_trim_legacy__26_evaluate_cases_against_5cf71bd():
    """M2.1: REF's 26 trim-golden cases: evaluate, settle, params_for,
    structure, node_structure, plan_of -- identical to the code of 5cf71bd."""
    ref = _ref_golden("aruco_trim_legacy_golden")["evaluate"]
    cases = [c for c in G.cases("legacy") if c["group"] == "trim"]
    assert len(cases) == len(ref) == 26
    bad = []
    for c, want in zip(cases, ref):
        d = G.diff(_trim_legacy_got(c), want["got"])
        if d:
            bad.append((c["id"], d))
    assert not bad, bad[:3]


JUNK = [None, {}, {"rule": 2, "axes": "x"}, {"axes": "sideways"}, {"rule": "one", "axes": "x"},
        "x", 3, [], {"rule": 1}]


@pytest.mark.ref(TRIM, "== the same tags with a 'trim' that reads as off: identical")
def test_trim_legacy__junk_trim_reads_as_off():
    """The 26 again with a 'trim' that reads as off: identical (settle drops it)."""
    ref = _ref_golden("aruco_trim_legacy_golden")["evaluate"]
    cases = [c for c in G.cases("legacy") if c["group"] == "trim"]
    bad = []
    for junk in JUNK:
        for c, want in zip(cases, ref):
            c2 = json.loads(json.dumps(c))
            c2["s"]["trim"] = junk
            d = G.diff(_trim_legacy_got(c2), want["got"])
            if d:
                bad.append((junk, c["id"], d))
    assert not bad, bad[:3]


@pytest.mark.ref(TRIM, "== the shipped defaults (4babc4b: the Joint Origin after the node): "
                 "no 'trim' = junk 'trim'")
def test_trim_legacy__jo_after_on_settles_jo_v_2():
    """With the frame sketch (jo_v 2) the 26 settle with jo_v 2, and a junk
    trim is the same as none."""
    cases = [c for c in G.cases("legacy") if c["group"] == "trim"]
    for c in cases:
        c2 = json.loads(json.dumps(c))
        c2["s"]["jo_v"] = 2
        base = _trim_legacy_got(c2)
        assert base["settled"]["settings"]["jo_v"] == 2
        for junk in (None, {"rule": 2, "axes": "x"}, "x"):
            c3 = json.loads(json.dumps(c2))
            c3["s"]["trim"] = junk
            assert not G.diff(_trim_legacy_got(c3), base)


def test_legacy__every_output_of_todays_ref_code():
    """The 38 cases: every output today's REF records (the ev, the layout,
    the trim plan, settle, OpenCV's frame, the digest), exactly."""
    bad = [(c["id"], d) for c in G.cases("legacy") if (d := _replay(c))]
    assert not bad, bad[:3]


def test_matrix__size_and_every_legacy_shape():
    """M2.2's bar: >= 600 cases; every legacy shape of the settings >= 10 times."""
    cs = G.cases("matrix")
    assert len(cs) >= 600
    n = collections.Counter(c["legacy"] for c in cs)
    for k in LEGACY_SHAPES:
        assert n[k] >= 10, (k, n[k])
    assert sum(1 for c in cs if "error" in c["out"]) >= 5         # refusals too


GROUPS = ["cross", "features", "shapes", "sizes", "heights", "labels", "faces", "refused",
          "legacy", "frames"]


@pytest.mark.parametrize("group", GROUPS)
def test_matrix__evaluate_replays_exactly(group):
    """M2.2: REF's evaluate() at c8216ff, every output, every float (and
    the sign of every zero)."""
    cs = [c for c in G.cases("matrix") if c["group"] == group]
    assert cs
    bad = [(c["id"], d) for c in cs if (d := _replay(c))]
    assert not bad, f"{len(bad)} of {len(cs)}: {bad[:3]}"


def _plan_vs_ref(c):
    spec = TagSpec.from_dict(c["in"])
    p = plan_tag(spec, base=c["base"])
    want = c["out"]
    if "error" in want:
        if p.ok or not p.data["errors"]:
            return f"should refuse: {want['error']}"
        return ""
    if not p.ok:
        return f"refused: {p.data['errors']}"
    ev = want["ev"]
    d = (G.diff(p.data["marker"], ev["spec"]) or G.diff(p.data["parts"], ev["plan"]["parts"])
         or G.diff(p.data["mark"], ev["record_mark"])
         or G.diff(p.data["label"], ev["record_label"])
         or G.diff(p.data["notes"], ev["notes"])
         or G.diff(p.data["node_warning"], ev["node_warning"])
         or G.diff(p.data["digest"], want["digest"]))
    if d:
        return d
    s2, n2 = settle(c["s"], c["n"], p)
    ws, wn = want["settled"]["settings"], want["settled"]["numbers"]
    for k in ("parts", "v", "pin", "size_auto", "jo_v"):
        if s2.get(k) != ws.get(k):
            return f"settled {k}: {s2.get(k)!r} vs {ws.get(k)!r}"
    if ("trim" in s2) != ("trim" in ws) or s2.get("trim") != ws.get("trim"):
        return f"settled trim: {s2.get('trim')!r} vs {ws.get('trim')!r}"
    if (n2["size"], n2["square"]) != (wn["size"], wn["square"]):
        return f"settled numbers {n2['size'], n2['square']} vs {wn['size'], wn['square']}"
    return ""


@pytest.mark.parametrize("group", ["legacy", "matrix"])
def test_plan_tag__the_tagplan_says_what_ref_built(group):
    """plan_tag(TagSpec) -- the request as the Studio holds it (the stored
    settings, the numbers REF read, the target) -- gives REF's board, parts,
    mark, label, notes, warning words, digest and written-back settings."""
    bad = [(c["id"], d) for c in G.cases(group) if (d := _plan_vs_ref(c))]
    assert not bad, f"{len(bad)}: {bad[:3]}"
