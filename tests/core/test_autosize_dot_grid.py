"""Merge 1: a sticker printer's dot (25.4 / 600 mm) as the cell grid.

Sizes are kept to 0.1 um (_r7); a dot is not a whole number of 0.1 um, so
k Ls and j m land up to 0.05 um off the grid. Before the fix S_next could
return the same square for ever: a ChArUco sticker on a disc hung the plan.
"""
from __future__ import annotations

import multiprocessing as mp

import pytest

from aruco_studio.core import autosize as A
from aruco_studio.core import presets as P

DOT_MM = round(25.4 / 600, 6)
CELLS = {"rule": 1, "of": "cell", "mm": DOT_MM, "min_mm": 1.0}


def test_snap_is_the_old_constants_on_a_whole_grid():
    for step_mm in (0.5, 0.45, 0.68, 0.4, 0.62, 0.02, 1.0, 2.0):
        assert A._snap(step_mm / 1000.0) == (A._K_EPS, A.EPS_M)


def test_legacy_grid_is_unchanged():
    G = A._Grid(4, None)
    assert (G.ke_L, G.tol_L, G.ke_m, G.tol_m) == (A._K_EPS, A.EPS_M, A._K_EPS, A.EPS_M)


@pytest.mark.parametrize("n", [4, 5, 6, 7])
def test_steps_down_on_a_dot_grid_always_move(n):
    G = A._Grid(n, CELLS)
    assert G.cell and G.ke_m > A._K_EPS
    for j in range(1, 800):
        x = G.S_of(j)
        assert G.S_j(x) == j, (j, x)
        nx = G.S_next(x)
        assert nx < x or nx == 0.0
    for k in range(1, 200):
        x = G.L_of(k)
        assert G.L_k(x) == k
        assert G.L_next(x) == G.L_of(k - 1)


def _plan_disc(q):
    from aruco_studio.plan import newtag as N
    from aruco_studio.plan.plan import plan_tag
    from aruco_studio.plan.spec import TagSpec
    from aruco_studio.plan import target as T
    tgt = T.disc(25.0, [(0.0, 18.0, 3.0)]).to_dict()
    sp = N.new_spec("charuco", tgt, P.sticker_builtins()[0])
    p = plan_tag(TagSpec.from_dict(sp))
    q.put((bool(p.data.get("ok")), p.data.get("made_by")))


def test_charuco_sticker_on_a_disc_plans():
    """The case that hung (run in a child so a regression fails, not hangs)."""
    q = mp.get_context("spawn").Queue()
    pr = mp.get_context("spawn").Process(target=_plan_disc, args=(q,))
    pr.start()
    pr.join(60)
    if pr.is_alive():
        pr.terminate()
        pr.join()
        pytest.fail("the plan did not finish in 60 s")
    ok, made_by = q.get(timeout=5)
    assert ok and made_by == "sticker"
