"""REF: tests/test_aruco_trim_legacy.py (cad-exporter c8216ff): the trim golden.

default_settings() and 288 aruco_slabs.plan results of 5cf71bd compare EXACTLY on
aruco_studio.core (settings, slabs); a node without "trim" keeps its structure.
REF's own run installs a stand-in adsk for its 26 evaluate() cases, so it was not
counted: the expected counts below are the suite's own check lines. The
evaluate() sections are M2's (plan_tag).
"""
from _ref_runner import make_tests

make_tests(globals(), "tests/test_aruco_trim_legacy.py", short="trim_legacy",
           expected={"tree: {ROOT}": 0,
                     "== default_settings(): no 'trim', the rest as before": 2,
                     "== {len(gold['plans'])} aruco_slabs plans: identical, and trim=False is the same": 2,
                     "== a node with no 'trim' keeps its structure; the edit guard leaves it alone": 3},
           parked={"== {len(gold['evaluate'])} tags evaluated with no 'trim': identical",
                   "== the same tags with a 'trim' that reads as off: identical",
                   "== the shipped defaults (4babc4b: the Joint Origin after the node): no 'trim' "
                   "= junk 'trim'"})


def test_trim_legacy__288_plans_and_26_evaluate_cases_in_the_golden():
    """M1.6: 288 slabs.plan + default_settings exact; 26 evaluate() cases parked for M2."""
    from _golden import load
    g = load("ref/aruco_trim_legacy_golden")["golden"]
    assert len(g["plans"]) == 288 and len(g["evaluate"]) == 26 and g["default_settings"]
