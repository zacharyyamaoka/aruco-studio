"""Golden replay: every id of every dictionary (goldens/dictionary.json, REF aruco_dict)."""
import golden_cases as GC
import pytest
from _golden import diff, load

from aruco_studio.core import dictionary as D

DOC = load("dictionary")


@pytest.mark.parametrize("case", DOC["cases"], ids=[c["in"]["name"] for c in DOC["cases"]])
def test_dictionary_golden(case):
    d = diff(case["out"], GC.norm(GC.dictionary_run(case["in"], D)))
    assert not d, d


def test_dictionary_golden_covers_every_dictionary():
    assert [c["in"]["name"] for c in DOC["cases"]] == list(D.DICTIONARY_NAMES)
    assert sum(c["out"]["info"]["capacity"] for c in DOC["cases"]) == 9596
