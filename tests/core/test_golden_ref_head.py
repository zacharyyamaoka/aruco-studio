"""N-1 (2026-10-17): the core does what REF's core does at ref_path.REF_HEAD.

goldens/ref_head/charuco_print.json holds the answers REF's OWN bam_cad_core
gave at REF_HEAD (tools/make_goldens_ref_head.py: git archive, python -I) to
tools/ref_head_scenario.py: the ChArUco boards on paper as the CAD has them
(da6e622: print items with CAD ink, the sheet check, layouts, PDF bytes with
and without the print dialog, sticker boxes, fit_pages, offset_polygon) and
the rounded record digests (4c8810b). Here the same scenario runs on
aruco_studio.core and every answer must be the golden's, exactly.
"""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from aruco_studio.core import chamfer, label, markers, numbering, sheet

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = json.loads((ROOT / "goldens" / "ref_head" / "charuco_print.json").read_text(encoding="utf-8"))
SCENARIO = ROOT / "tools" / "ref_head_scenario.py"


def _scenario():
    spec = importlib.util.spec_from_file_location("ref_head_scenario", SCENARIO)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ANSWERS = _scenario().run(markers, sheet, label, chamfer, numbering)


def test_the_scenario_is_the_one_the_golden_ran():
    got = hashlib.sha256(SCENARIO.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    assert got == GOLDEN["scenario_sha256"], "the scenario changed: remake the golden from REF"


def test_every_answer_is_there():
    assert sorted(ANSWERS) == sorted(GOLDEN["golden"])


@pytest.mark.parametrize("name", sorted(GOLDEN["golden"]))
def test_answer_equals_refs(name):
    assert json.loads(json.dumps(ANSWERS[name], sort_keys=True)) == GOLDEN["golden"][name]
