"""REF: tests/test_print_beds_slicer.py (cad-exporter c8216ff), every check, against aruco_studio.core.beds.

The copy is tests/core/ref_suites/ref_print_beds_slicer.py (tools/port_ref_suites.py); one test per REF
section, each passing exactly as many checks as REF's own run did.
"""
from _ref_runner import make_tests

make_tests(globals(), "tests/test_print_beds_slicer.py", short="print_beds_slicer")
