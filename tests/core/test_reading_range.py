"""The reading range's engine (aruco_studio/core/reading_range.py), standard
library only: its PRNG against SplitMix64's published vectors, the cases
inside their budget, the fit's pieces by hand, and the whole engine against
an independent oracle -- the pinhole model's views have a closed-form read
limit per case, so the 95 % crossing can be computed without the engine
(and the oracle is shown to fail a wrongly built engine). Then judge(): the
requirement's pass / fail and the fixes it names."""
from __future__ import annotations

import json
import math

import pytest

from aruco_studio.core import cameras as CAMS
from aruco_studio.core import reading_range as RR

D435 = CAMS.camera_of("d435")
# a 30 mm DICT_4X4 single (6 modules: 5 mm cells) in a 40 mm quiet-zone box
SINGLE = {"bounds_mm": [-20.0, -20.0, 20.0, 20.0], "cell_mm": 5.0, "marker_mm": 30.0, "ids": [7]}


# ------------------------------------------------------------------ the PRNG and the cases

def test_splitmix64_matches_the_reference_vectors():
    """Vigna's splitmix64.c from state 0: the first three outputs."""
    r = RR.Rng(0)
    assert [r.next64() for _ in range(3)] == [0xE220A8397B1DCDAF, 0x6E789E6AA1B965F4, 0x06C45D188009454F]


def test_random_is_in_0_1_and_below_is_in_range():
    r = RR.Rng(5)
    xs = [r.random() for _ in range(2000)]
    assert min(xs) >= 0.0 and max(xs) < 1.0
    assert 0.45 < sum(xs) / len(xs) < 0.55
    assert {RR.Rng(k).below(7) for k in range(200)} == set(range(7))


def test_cases_lie_inside_the_field_budget_and_repeat():
    b = RR.BUDGETS["field"]
    cs = RR.cases(200, 11)
    assert len(cs) == 200
    for c in cs:
        assert math.hypot(c["tilt_deg"], c["yaw_deg"]) <= b["tilt_max_deg"] + 1e-9
        assert b["blur_px"][0] <= c["blur_px"] <= b["blur_px"][1]
        assert b["noise"][0] <= c["noise"] <= b["noise"][1]
        assert b["glare"][0] <= c["glare"] <= b["glare"][1]
        assert c["occlusion"] == 0.0 and 0 <= c["seed"] < 2 ** 31 - 1
    assert RR.cases(200, 11) == cs
    assert RR.cases(200, 12) != cs
    # every direction of tilt is drawn, not just one axis
    assert min(c["yaw_deg"] for c in cs) < -20 and max(c["yaw_deg"] for c in cs) > 20


def test_jitters_are_within_4_percent():
    js = RR.jitters(500, 3)
    assert min(js) >= 1 - RR.JITTER and max(js) <= 1 + RR.JITTER


# ------------------------------------------------------------------ the fit's pieces

def test_pava_pools_the_violators_and_keeps_the_mean():
    assert RR.pava_down([1.0, 0.9, 0.95, 0.5]) == pytest.approx([1.0, 0.925, 0.925, 0.5])
    ys = [0.2, 0.9, 0.4, 0.8, 0.1, 0.3]
    out = RR.pava_down(ys)
    assert all(a >= b - 1e-12 for a, b in zip(out, out[1:]))
    assert sum(out) == pytest.approx(sum(ys))
    assert RR.pava_down([1.0, 0.8, 0.3]) == [1.0, 0.8, 0.3]


def test_crossing_interpolates_in_log_distance():
    rows = [[True] * 10, [True] * 9 + [False], [False] * 10]
    grid = [100.0, 200.0, 400.0]
    # rate 1.0 at 100, 0.9 at 200: P_READ 0.95 is halfway in ln(d)
    assert RR.crossing(grid, rows, range(10)) == pytest.approx(100.0 * math.sqrt(2.0))
    assert RR.crossing(grid, [[False] * 10] * 3, range(10)) is None
    assert RR.crossing(grid, [[True] * 10] * 3, range(10)) == 400.0


def test_percentile_is_numpys_linear():
    xs = [5.0, 1.0, 9.0, 3.0, 7.0]
    assert RR.percentile(xs, 0) == 1.0 and RR.percentile(xs, 100) == 9.0
    assert RR.percentile(xs, 50) == 5.0
    assert RR.percentile(xs, 10) == pytest.approx(1.8)      # 1 + 0.4 x (3 - 1)
    np = pytest.importorskip("numpy")
    ys = [((k * 37) % 101) / 7.0 for k in range(57)]
    for q in (5, 17.5, 50, 95):
        assert RR.percentile(ys, q) == pytest.approx(float(np.percentile(ys, q)), abs=1e-12)


# ------------------------------------------------------------------ the engine against the pinhole oracle

def _limits(geo, cam, view):
    """The pinhole model's read window for one case, by hand: it reads at D
    (mm) iff near_lim <= D <= far_lim (analytic_reader's three conditions)."""
    w, h = cam["resolution"]
    f = (w / 2.0) / math.tan(math.radians(cam["hfov_deg"]) / 2.0)
    t, y = math.radians(view["tilt_deg"]), math.radians(view["yaw_deg"])
    across = math.cos(t) * math.cos(y)
    need = (RR.PPC_LIMIT * math.sqrt((1 + (view["blur_px"] / RR.PPC_BLUR) ** 2) / 2)
            * (1 + RR.NOISE_COST * view["noise"]) * (1 + RR.GLARE_COST * view["glare"]))
    by_cells = geo["cell_mm"] * f * across / need
    by_outline = 2 * geo["marker_mm"] * f * (math.cos(t) + math.cos(y)) / (RR.PERIMETER_RATE * max(w, h))
    u0, v0, u1, v1 = geo["bounds_mm"]
    grow = 1 + 0.5 * math.sqrt(max(0.0, 1 - across * across))
    near_lim = max((u1 - u0) * f * grow / w, (v1 - v0) * f * grow / h)
    return near_lim, min(by_cells, by_outline)


def _oracle(geo, cam, n=RR.N_CASES, seed=RR.SEED):
    views = RR.cases(n, seed)
    js = RR.jitters(n, seed + 1)
    lims = [_limits(geo, cam, v) for v in views]
    # each case's own far end, its distance jittered: it reads at d iff d * j <= far
    ends = sorted(far / j for (_near, far), j in zip(lims, js))
    need = math.ceil(RR.P_READ * n)                  # 46 of 48
    return views, js, lims, ends[n - need]           # the farthest d where `need` still read


def _check_against_oracle(geo, cam, rr, n=RR.N_CASES, seed=RR.SEED):
    """The engine's answer re-derived: its fit rows' counts from the closed
    form, the P_READ crossing of those counts in ln(d), and the near end."""
    views, js, lims, d95 = _oracle(geo, cam, n, seed)
    grid = [row["d_mm"] for row in rr["rows"]]
    counts = [sum(1 for (lo, hi), j in zip(lims, js) if lo <= d * j <= hi) for d in grid]
    assert counts == [row["ok"] for row in rr["rows"]], (counts, rr["rows"])
    rates = [c / n for c in counts]
    assert all(a >= b for a, b in zip(rates, rates[1:]))        # monotone: PAVA has nothing to pool
    far = None
    for i in range(len(rates) - 1):
        if rates[i] >= RR.P_READ > rates[i + 1]:
            t = (rates[i] - RR.P_READ) / (rates[i] - rates[i + 1])
            far = math.exp(math.log(grid[i]) + t * (math.log(grid[i + 1]) - math.log(grid[i])))
            step = grid[i + 1] / grid[i]
            break
    assert far is not None
    assert rr["far_mm"] == pytest.approx(far, abs=0.2)
    # and the true 95 % point lies in the grid step the engine interpolated in
    assert abs(math.log(rr["far_mm"] / d95)) <= math.log(step)
    # the near end: the frame's fill (or the focus), stepped x1.15 until the first 8 read
    u0, v0, u1, v1 = geo["bounds_mm"]
    w, h = cam["resolution"]
    f = (w / 2.0) / math.tan(math.radians(cam["hfov_deg"]) / 2.0)
    near = max((u1 - u0) * f / (RR.NEAR_FILL * w), (v1 - v0) * f / (RR.NEAR_FILL * h), cam.get("focus_mm") or 0.0)
    for _ in range(RR.NEAR_STEPS):
        if all(lo <= near <= hi for lo, hi in lims[:RR.N_NEAR]):
            break
        near *= RR.NEAR_STEP
    assert rr["near_mm"] == pytest.approx(near, abs=0.06)
    return d95


@pytest.mark.parametrize("camera", ["d435", "d455", "oakd12", "picam3"])
def test_the_engine_matches_the_pinhole_oracle(camera):
    cam = CAMS.camera_of(camera)
    rr = RR.run(RR.sweep(SINGLE, cam), RR.analytic_reader(SINGLE, cam))
    d95 = _check_against_oracle(SINGLE, cam, rr)
    assert rr["band_mm"][0] <= rr["far_mm"] <= rr["band_mm"][1]
    assert rr["near_mm"] < rr["far_mm"]
    assert rr["version"] == RR.VERSION and rr["renders"] > 0
    # the analytic limit is a px-per-cell rule: at the far end a cell spans about
    # PPC_LIMIT px or more (blur and tilt need more), never fewer
    f = RR.focal_px(cam["resolution"][0], cam["hfov_deg"])
    assert SINGLE["cell_mm"] * f / d95 >= RR.PPC_LIMIT * math.sqrt(0.5) - 1e-9


def test_a_focus_distance_sets_the_near_end():
    cam = dict(D435, focus_mm=400.0)
    rr = RR.run(RR.sweep(SINGLE, cam), RR.analytic_reader(SINGLE, cam))
    assert rr["near_mm"] == 400.0 and rr["near_by"] == "focus"
    _check_against_oracle(SINGLE, cam, rr)


def test_the_oracle_fails_a_wrong_engine(monkeypatch):
    """The ruler can go red: an engine that fits the 90 % crossing instead of
    the 95 % one is caught (mutation test of the gate above)."""
    cam = D435
    monkeypatch.setattr(RR, "P_READ", 0.90)
    wrong = RR.run(RR.sweep(SINGLE, cam), RR.analytic_reader(SINGLE, cam))
    monkeypatch.setattr(RR, "P_READ", 0.95)
    with pytest.raises(AssertionError):
        _check_against_oracle(SINGLE, cam, wrong)


def test_a_view_is_read_once_and_the_answer_is_the_same_bytes():
    asked = []
    read = RR.analytic_reader(SINGLE, D435)

    def counting(d, view):
        asked.append((d, view["seed"]))
        return read(d, view)
    a = RR.run(RR.sweep(SINGLE, D435), counting)
    assert len(asked) == len(set(asked)) == a["renders"]
    b = RR.run(RR.sweep(SINGLE, D435), RR.analytic_reader(SINGLE, D435))
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    c = RR.run(RR.sweep(SINGLE, D435, seed=99), RR.analytic_reader(SINGLE, D435))
    assert c["rows"] != a["rows"]


def test_a_board_too_big_for_the_frame_at_300_mm_reads_from_its_fill():
    """300 mm fails (it does not fit), the outward search finds where it does:
    the near end is the frame's, not the label's."""
    big = dict(SINGLE, bounds_mm=[-300.0, -150.0, 300.0, 150.0], cell_mm=80.0, marker_mm=480.0)
    rr = RR.run(RR.sweep(big, D435), RR.analytic_reader(big, D435))
    assert rr["far_mm"] and rr["near_mm"] > 300.0
    assert rr["near_by"] == "frame"


def test_a_marker_too_small_to_read_reads_nowhere_and_says_why():
    tiny = dict(SINGLE, bounds_mm=[-0.2, -0.2, 0.2, 0.2], cell_mm=0.05, marker_mm=0.3)
    rr = RR.run(RR.sweep(tiny, D435), RR.analytic_reader(tiny, D435))
    assert rr["near_mm"] is None and rr["far_mm"] is None and rr["band_mm"] is None
    assert "misses an id at every distance" in rr["reason"]


def test_the_engine_never_renders_and_stays_standard_library():
    import ast
    import inspect
    src = inspect.getsource(RR)
    mods = {n.names[0].name.split(".")[0] for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Import)}
    mods |= {(n.module or "").split(".")[0] for n in ast.walk(ast.parse(src)) if isinstance(n, ast.ImportFrom) and n.level == 0}
    assert mods <= {"math", "__future__"}, mods


# ------------------------------------------------------------------ the requirement

def _rng(near, far, marker=30.0, near_by="frame", far_limit="cells", across=40.0):
    return {"near_mm": near, "far_mm": far, "near_by": near_by, "far_limit": far_limit, "far_outline_px": 60.0,
            "min_outline_px": 57.6, "reason": "it misses an id at every distance tried",
            "geometry": {"bounds_mm": [-across / 2, -across / 2, across / 2, across / 2], "marker_mm": marker}}


def test_nothing_required_is_no_verdict():
    assert RR.judge(_rng(100.0, 1500.0), None)["verdict"] is None
    assert RR.judge(_rng(100.0, 1500.0), {"min_mm": None, "max_mm": None})["verdict"] is None


def test_a_range_that_covers_the_requirement_passes():
    j = RR.judge(_rng(100.0, 1500.0), {"min_mm": 300.0, "max_mm": 1200.0})
    assert j["verdict"] == "pass" and j["hints"] == [] and all(c["ok"] for c in j["checks"])
    assert RR.judge(_rng(100.0, 1500.0), {"max_mm": 1500.0})["verdict"] == "pass"   # the edge counts


def test_too_short_fails_with_the_size_that_scales_to_it():
    j = RR.judge(_rng(100.0, 1500.0), {"min_mm": 300.0, "max_mm": 2000.0})
    assert j["verdict"] == "fail"
    mx = next(c for c in j["checks"] if c["side"] == "max")
    assert not mx["ok"] and mx["by_mm"] == 500.0
    assert j["size_mm"] == 40.0                      # 30 mm x 2000 / 1500, up to 0.5 mm
    assert "Short by 500 mm" in j["hints"][0] and "40 mm marker" in j["hints"][0]


def test_outline_limited_says_so():
    j = RR.judge(_rng(100.0, 1500.0, far_limit="outline"), {"max_mm": 2000.0})
    assert "minMarkerPerimeterRate" in j["hints"][0]


@pytest.mark.parametrize("near_by, words", [("frame", "Too big for the frame"), ("reads", "Too big for the frame"),
                                            ("focus", "focuses from"), ("label", "label")])
def test_too_near_names_the_cause(near_by, words):
    j = RR.judge(_rng(400.0, 3000.0, near_by=near_by), {"min_mm": 200.0})
    assert j["verdict"] == "fail" and words in j["hints"][0]


def test_a_requirement_no_one_size_can_meet_says_so():
    j = RR.judge(_rng(400.0, 1000.0, near_by="frame"), {"min_mm": 200.0, "max_mm": 3000.0})
    assert j["verdict"] == "fail" and j["size_mm"] is None
    assert any("No one size covers" in h for h in j["hints"])


def test_reading_nowhere_fails():
    j = RR.judge(_rng(None, None), {"max_mm": 1000.0})
    assert j["verdict"] == "fail" and "does not read at any distance" in j["hints"][0]
