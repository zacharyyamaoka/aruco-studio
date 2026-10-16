"""REF: tests/test_aruco_presets.py (cad-exporter c8216ff), every check, against
aruco_studio.core.presets / core.prusa through ref_store_shim (REF's file API
over the pure core; server/store.py is M2b's).
"""
from _ref_runner import make_tests

make_tests(globals(), "tests/test_aruco_presets.py", short="presets")
