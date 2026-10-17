"""Golden replays of REF's core modules, one table each (goldens/<name>.json).

Every golden was made by REF's own module at c8216ff, read only
(tools/make_goldens_from_ref.py); each case is replayed through the SAME
runner (tools/golden_cases.py) on aruco_studio.core and must come out
EXACTLY equal: ints, strings, lists and floats.
"""
import golden_cases as GC
import pytest
from _golden import diff, load

from aruco_studio.core import (autosize as A, board as B, chamfer as C, faces as G, label as L,
                               markers as M, origin as OR, slabs as S, trim as T)


def _cases(name):
    doc = load(name)
    return pytest.mark.parametrize("case", doc["cases"],
                                   ids=[f"{i:04d}" for i in range(len(doc["cases"]))])


@_cases("board")
def test_board_golden(case):
    d = diff(case["out"], GC.norm(GC.board_run(case["in"], B)))
    assert not d, d


@_cases("origin")
def test_origin_golden(case):
    d = diff(case["out"], GC.norm(GC.origin_run(case["in"], OR)))
    assert not d, d


@_cases("slabs")
def test_slabs_golden(case):
    d = diff(case["out"], GC.norm(GC.slabs_run(case["in"], S)))
    assert not d, d


@_cases("chamfer")
def test_chamfer_golden(case):
    inp = case["in"]
    got = (GC.norm(GC.guarded(C.choice_of, inp["settings"])) if inp.get("fn") == "choice_of"
           else GC.norm(GC.chamfer_run(inp, C)))
    d = diff(case["out"], got)
    assert not d, d


@_cases("autosize")
def test_autosize_golden(case):
    d = diff(case["out"], GC.norm(GC.autosize_run(case["in"], A, G)))
    assert not d, d


@_cases("label")
def test_label_golden(case):
    d = diff(case["out"], GC.norm(GC.label_run(case["in"], L, M, C)))
    assert not d, d


@_cases("trim")
def test_trim_golden(case):
    inp = case["in"]
    got = (GC.norm(GC.guarded(T.trim_of, inp["raw"])) if inp.get("fn") == "trim_of"
           else GC.norm(GC.trim_run(inp, T)))
    d = diff(case["out"], got)
    assert not d, d


def test_versioned_rule_numbers_kept():
    """The rule numbers the goldens were made under, and the ones REF's
    stored settings carry."""
    assert OR.ORIGIN_RULE == 2
    assert A.CELL_RULE == 1
    assert L.RULE == 2 and sorted(L.RULES) == [1, 2, 3, 4]    # 3: M6a, 4: the 2026-10-17 audit
    assert T.RULE == 1
    assert {c["in"]["rule"] for c in load("origin")["cases"]} == {2, None}
    assert {c["out"]["record"]["settings"]["rule"] for c in load("label")["cases"]} == {1, 2}
