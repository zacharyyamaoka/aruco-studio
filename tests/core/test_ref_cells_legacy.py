"""REF: tests/test_aruco_cells_legacy.py (cad-exporter c8216ff): the cell-rule golden.

511 sizings of 196454c recompute EXACTLY on aruco_studio.core.autosize (floats
too), and "marker" cells with the 0.5 mm step are the same rule. REF's own run
installs a stand-in adsk for its 12 evaluate() cases, so it was not counted:
the expected counts below are the suite's own check lines (2 + one per sizing
function + 1). The 12 evaluate() cases are M2's (plan_tag).
"""
from _ref_runner import make_tests

S = "== {len(data['cases'])} sizings recomputed with no 'cells': identical"
make_tests(globals(), "tests/test_aruco_cells_legacy.py", short="cells_legacy",
           expected={"== the legacy rule: no 'cells' is None, so is anything unreadable": 2,
                     S: 7,     # default_layout, face_default, fit_on_loops, layout_for_size,
                               # clamp_to_fit, candidates, candidates_on_loops
                     "== 'marker' cells with the 0.5 mm step (and no minimum) ARE the legacy rule": 1},
           parked={"== {len(data['evaluate'])} evaluate() results (aruco_feature, no 'cells' in "
                   "the settings): identical"})


def test_cells_legacy__511_sizings_in_the_golden():
    """M1.4: 511 sizings + 12 evaluate() cases (parked for M2)."""
    from _golden import load
    g = load("ref/aruco_cells_legacy_golden")["golden"]
    assert len(g["cases"]) == 511 and len(g["evaluate"]) == 12
