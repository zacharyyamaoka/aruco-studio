"""Golden replay: the preset library's cards and preset_of_node's mapping
(goldens/preset_library.json, REF ArucoMarkers/aruco_preset_library.py)."""
import golden_cases as GC
import pytest
from _golden import diff, load

from aruco_studio.core import presets as P

DOC = load("preset_library")


def run(inp):
    fn = inp["fn"]
    if fn == "cards":
        p = inp["p"]
        return GC.norm({"subtitle": P.subtitle(p), "lines": P.lines_per_cell(p),
                        "words": P.cells_words(p), "info": P.info(p), "thumb": P.thumb_svg(p),
                        "thumb7": P.thumb_svg(p, 7)})
    if fn == "preset_of_node":
        return GC.norm(P.preset_of(dict(inp["s"]), dict(inp["n"]), inp["profile"]))
    if fn == "same_print":
        return P.same_print(inp["a"], inp["b"])
    if fn == "group_nodes":
        nodes = [tuple(x) for x in inp["nodes"]]
        cat = [tuple(x) for x in inp["catalog"]]
        return GC.norm(P.group_nodes(nodes, cat))
    if fn == "edit_schema":
        return GC.norm(P.edit_schema())
    raise ValueError(fn)


@pytest.mark.parametrize("case", DOC["cases"],
                         ids=[f"{i:03d}-{c['in']['fn']}" for i, c in enumerate(DOC["cases"])])
def test_preset_library_golden(case):
    d = diff(case["out"], run(case["in"]))
    assert not d, d
