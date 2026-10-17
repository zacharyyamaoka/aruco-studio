"""REF: tests/test_aruco_settings.py (cad-exporter c8216ff): the dialogs'
memory (REF ArucoMarkers/aruco_settings.py, now aruco_studio.server.remembered).

The copy (tests/server/ref_suites/ref_settings.py) is REF's script with its
import pointed here; each REF section must pass exactly as many checks as
REF's own run did (tests/ref_sections.json). The Studio's own file is
ARUCO_STUDIO_HOME/remembered.json (server/store.py); REF's settings_path()
is kept verbatim for this suite and never called by the server.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
from _ref_runner import run_copy, slug, suite_info  # noqa: E402

REL = "tests/test_aruco_settings.py"
INFO = suite_info(REL)
ROWS = INFO["sections"]
COPY = Path(__file__).resolve().parent / "ref_suites" / "ref_settings.py"


@pytest.fixture(scope="module")
def ref_run():
    return run_copy(COPY, ROWS, None)


def _make(row):
    key = row["key"]

    @pytest.mark.ref(REL, row["text"])
    def test(ref_run):
        got = ref_run["counts"].get(key, {"ok": 0, "fail": 0, "skip": 0, "fails": []})
        assert got["fail"] == 0, "\n".join(got["fails"])
        want = INFO["ref_counts"][key]["ok"]
        assert got["ok"] == want, f"{got['ok']} checks passed, REF passed {want}"
    test.__doc__ = f"REF: {REL} section {row['text']!r} (line {row['line']})"
    return test


for _i, _row in enumerate(ROWS):
    globals()[f"test_settings__s{_i:02d}__{slug(_row['text'])}"] = _make(_row)


def test_settings__exits_0_and_totals_match(ref_run):
    assert ref_run["exit"] == 0
    assert sum(c["ok"] for c in ref_run["counts"].values()) == \
        sum(c["ok"] for c in INFO["ref_counts"].values())
