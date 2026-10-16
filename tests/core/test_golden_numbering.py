"""Golden replay: REF's numbering fixtures F1..F11 (goldens/numbering.json, REF aruco_numbering)."""
import golden_cases as GC
import pytest
from _golden import diff, load

from aruco_studio.core import markers as M, numbering as N

DOC = load("numbering")


def fixture(inp):
    tags = [M.TagDef.from_dict(d, lambda m: None) for d in inp["tags"]]
    occs = [M.OccurrenceRef(o["path"], o["component"], o["transform"], o["visible"], o["linked"])
            for o in inp["occurrences"]]
    return tags, occs


@pytest.mark.parametrize("case", DOC["cases"], ids=[c["in"]["fixture"] for c in DOC["cases"]])
def test_numbering_golden(case):
    got = GC.norm(GC.numbering_run(case["in"]["fixture"], fixture(case["in"]), N))
    d = diff(case["out"], got)
    assert not d, d
