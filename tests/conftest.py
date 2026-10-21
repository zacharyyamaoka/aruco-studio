r"""pytest set-up for every group.

* ROOT and tools/ on sys.path (aruco_studio, golden_cases, ref_path);
* USERPROFILE, HOME and ARUCO_STUDIO_HOME point at a temp dir for the whole
  run, so nothing can land in Zach's %USERPROFILE%\CADExporter;
* the `ref(suite, section)` marker names the REF suite a test came from.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "tools"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

_HOME = tempfile.mkdtemp(prefix="aruco_studio_tests_")
os.environ["USERPROFILE"] = os.environ["HOME"] = _HOME
os.environ["ARUCO_STUDIO_HOME"] = os.path.join(_HOME, "studio")
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"


def pytest_configure(config):
    config.addinivalue_line("markers", "ref(suite, section): the REF suite and section ported")


def pytest_collection_modifyitems(session, config, items):
    """tools/check.py --trace: every test's ref(suite, section) markers -> a JSON file."""
    config._fidelity_collected = any("test_port_fidelity" in it.nodeid for it in items)
    out = os.environ.get("ARUCO_TRACE_OUT")
    if not out:
        return
    import json
    rows = [{"nodeid": it.nodeid, "suite": m.args[0], "section": m.args[1]}
            for it in items for m in it.iter_markers("ref")]
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rows, f)


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """A skipped port-fidelity check is not a pass: say so in the run's own
    output, not only under -rs (tools/check.py repeats it in its group line)."""
    import ref_path
    note = ref_path.head_missing_note()
    if note and getattr(config, "_fidelity_collected", False):
        terminalreporter.write_line(f"WARNING: {note}", yellow=True, bold=True)
