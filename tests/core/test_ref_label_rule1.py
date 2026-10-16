"""REF: tests/test_aruco_label_rule1.py (cad-exporter c8216ff), every check, against aruco_studio.core.

The suite's copy is tests/core/ref_suites/ref_label_rule1.py (tools/port_ref_suites.py);
_ref_runner.py makes one test per REF section, each passing exactly as many
checks as REF's own run did (tests/ref_sections.json).
"""
from _ref_runner import make_tests

make_tests(globals(), "tests/test_aruco_label_rule1.py", short="label_rule1")
