"""Golden replay: print presets and PrusaSlicer profiles (goldens/presets.json, prusa.json).

REF made them with ArucoMarkers/aruco_presets.py and aruco_prusa.py (no adsk)
over its PrusaSlicer fixture; the replay reads the same fixture, copied byte
for byte into goldens/prusaslicer/, through core.prusa's text readers.
"""
from pathlib import Path

import golden_cases as GC
import pytest
from _golden import GOLDENS, diff, load

from aruco_studio.core import presets as P, prusa as R

FIX = GOLDENS / "prusaslicer"


def fixture_sources():
    """The fixture folder read the way REF's aruco_prusa reads files
    (utf-8, errors replaced): what server/store.py will do for a real one."""
    read = lambda p: Path(p).read_text(encoding="utf-8", errors="replace")  # noqa: E731
    user = {p.stem: read(p) for p in sorted((FIX / "print").glob("*.ini"))}
    bundles = [read(p) for p in sorted((FIX / "vendor").glob("*.ini"))]
    return R.sources_from_texts(user, bundles)


SRC = fixture_sources()
PRESETS = load("presets")
PRUSA = load("prusa")


def preset_run(inp):
    fn = inp["fn"]
    if fn == "default_preset":
        return GC.norm(P.default_preset())
    if fn == "normalise":
        return GC.norm(P.normalise(inp["p"]))
    if fn == "cell_setting":
        return GC.norm(P.cell_setting(inp["p"]))
    if fn == "changes":
        a, b = inp["a"], inp["b"]
        return GC.norm({"changes": P.changes(a, b), "same": P.same(a, b),
                        "words": P.describe_changes(a, b), "words2": P.describe_changes(b, a, limit=2)})
    if fn == "from_profile":
        return GC.norm(P.from_profile(inp["profile"]))
    if fn == "parse_min":
        return GC.norm(P.parse_min(inp["text"]))
    if fn == "min_text":
        return P.min_text(inp["c"])
    if fn == "layer_note":
        return P.layer_note(*inp["args"])
    if fn == "valid_name":
        return [P.valid_name(inp["name"]), P.unique_name(inp["name"], {"Default", "Fine", "Fine (2)"})]
    raise ValueError(fn)


def prusa_run(inp):
    fn = inp["fn"]
    if fn == "profile":
        pr = R.profile(inp["name"], SRC)
        return GC.norm({"profile": pr, "describe": R.describe(pr), "resolve": R.resolve(inp["name"], SRC)})
    if fn == "resolve":
        return GC.norm(R.resolve(inp["name"], SRC))
    if fn == "aruco_profiles":
        return [p["name"] for p in R.aruco_profiles(SRC)]
    if fn == "user_prints":
        return [u["name"] for u in R.user_prints(SRC)]
    if fn == "width_of":
        return R.width_of(*inp["args"])
    if fn == "nozzle_of":
        return R.nozzle_of(*inp["args"])
    if fn == "length":
        return GC.norm(R.length(*inp["args"]))
    if fn == "describe":
        return R.describe(inp["p"])
    raise ValueError(fn)


@pytest.mark.parametrize("case", PRESETS["cases"],
                         ids=[f"{i:03d}-{c['in']['fn']}" for i, c in enumerate(PRESETS["cases"])])
def test_presets_golden(case):
    d = diff(case["out"], preset_run(case["in"]))
    assert not d, d


@pytest.mark.parametrize("case", PRUSA["cases"],
                         ids=[f"{i:03d}-{c['in']['fn']}" for i, c in enumerate(PRUSA["cases"])])
def test_prusa_golden(case):
    d = diff(case["out"], prusa_run(case["in"]))
    assert not d, d


def test_preset_schema_and_cell_rule_kept():
    assert P.SCHEMA == "bam_aruco_presets/1"
    assert P.CELL_RULE == 1
