"""REF's mutation tests, on the new core (ST-T-LEDGER-1, ST-T-LABEL-4).

REF tools/mutate_aruco_ids.py and mutate_aruco_label.py break ONE rule at a
time in a temporary copy of the core and require the suite written for that
rule to go red, with the aimed check among the failures. Here each mutation
(tests/core/ref_suites/ref_mutations.py: REF's tables, rows on a core file)
is applied to a temporary copy of aruco_studio, and the ported suite copy runs
against it. The replaced text must occur exactly once, so a mutation can
never silently miss.
"""
import shutil
from pathlib import Path

import pytest
from _ref_runner import ROOT, run_copy, suite_info

from ref_suites.ref_mutations import MUTATIONS  # noqa: E402  (tests/core on sys.path)

FILES = {"CADExporter/bam_cad_core/aruco_numbering.py": "numbering.py",
         "CADExporter/bam_cad_core/aruco_label.py": "label.py"}
COPIES = {"tests/test_aruco_ids_stability.py": "ref_aruco_ids_stability.py",
          "tests/test_aruco_label_preview.py": "ref_aruco_label_preview.py",
          "tests/test_aruco_label_rule1.py": "ref_aruco_label_rule1.py"}


@pytest.fixture(scope="module")
def pristine(tmp_path_factory):
    base = tmp_path_factory.mktemp("aruco_mut_src")
    shutil.copytree(ROOT / "aruco_studio", base / "aruco_studio",
                    ignore=shutil.ignore_patterns("__pycache__"))
    return base


def _failed_labels(res):
    out = []
    for c in res["counts"].values():
        for line in c["fails"]:
            out.append(line[6:].split("  ")[0].strip() if line.startswith("FAIL  ") else line)
    return out


@pytest.mark.parametrize("m", MUTATIONS, ids=[m["id"] for m in MUTATIONS])
def test_mutation_is_caught(m, pristine, tmp_path):
    mut = tmp_path / "pkg"
    shutil.copytree(pristine / "aruco_studio", mut / "aruco_studio")
    target = mut / "aruco_studio" / "core" / FILES[m["file"]]
    src = target.read_text(encoding="utf-8")
    assert src.count(m["old"]) == 1, f"the mutation's text occurs {src.count(m['old'])} times"
    target.write_text(src.replace(m["old"], m["new"]), encoding="utf-8", newline="\n")
    killed, aimed, seen = False, False, []
    for suite in m["suites"]:
        info = suite_info(suite)
        copy = Path(__file__).resolve().parent / "ref_suites" / COPIES[suite]
        assert copy.exists(), copy
        res = run_copy(copy, info["sections"], None, {"ARUCO_STUDIO_CORE_ROOT": str(mut)})
        fails = _failed_labels(res)
        seen += fails
        killed |= res["exit"] not in (0, None) or bool(fails)
        if m["tool"].endswith("mutate_aruco_ids.py"):
            aimed |= m["must"] in fails
        else:
            aimed |= any(m["must"] in x for x in fails)
        # REF counts a crash after the suite started (no FAIL line) as killed too;
        # a run that never reached a check is not a kill
        started = any(c["ok"] or c["fail"] for c in res["counts"].values())
        crashed = isinstance(res["exit"], str) and started
        assert started, f"{copy.name} never ran a check: {res['exit']}"
        aimed |= crashed and not fails
    assert killed, f"SURVIVED: {m['rule']}"
    assert aimed, f"killed elsewhere, not by {m['must']!r}: {seen[:5]}"
