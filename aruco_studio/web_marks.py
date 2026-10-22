"""Verify's label and corner-mark check: what a marker's LABEL and CORNER
MARK cost OpenCV's detector, measured on the simulated camera (Verify's,
verify.camera), never assumed. The guide "Label placement"
(web/public/guides/label-placement/, docs/build_guides.py) is its output.

WHY a paired check (2026-10-21): Verify's dialog shows one view, a clean
tilt sweep and a head-on read limit. On the label placement board they
catch only the worst places, and with OpenCV 5.0 (this repo's CPython) not
even those: its sweep reads every marker there to 75-80 deg. What tells the
places apart is the method of the REF studies behind core.label's rules
(430,260 simulated photos): the SAME plan read twice through the SAME
views, as planned ("marked": its label and corner mark drawn) and "bare"
(the same marker, both taken away), counting the reads one gets and the
other does not. The two scenes share their crop, grain and seed, so the
only pixels that differ are the label's and the mark's: a read the bare
marker gets and the marked one does not is the marks' doing.

A read is one marker id in one view: a grid or a ChArUco board counts each
of its markers, so its share is comparable with a single's (a view is not
all-or-nothing over ten markers).

The views: a grid of difficulty, scale free (px per cell on the sensor, so
a 10 mm and a 100 mm marker are tested alike): GRID's resolutions x blurs x
head on / Verify's field tilt (web_verify.FIELD_VIEW: 45 deg, grain 0.1) x
seeds. A marker reads in most of it and fails at its hard end (3 px per
cell with 2.5 px of blur); a label that costs anything costs it there.

The detector is whatever OpenCV this Python has (the result's `opencv`), and
it matters near the limits: on the board, OpenCV 4.11 (the browser's, in
Pyodide 314) lost 186 of 271 reads with a label touching the black, OpenCV
5.0 none (2026-10-21). The guide runs this check on ONE OpenCV, the newest
installed unless asked (docs/peps/0003 decision 3; opencv_choice).

What it cannot see (the simulator's limits; the guide says them): ink
spread (a printer's dots growing into the white: the REF study's "up to
-40 pts" in the quiet ring), grey ink, and the surface round the sticker
(Verify draws white beyond the sticker, so ink in the quiet zone never
joins a dark background).

numpy + OpenCV, as web_verify (which this builds on, unchanged). Bump
VERSION when GRID, the verdict's thresholds or the counting change: the
guide prints the version it was made with.
"""
from __future__ import annotations

import math
from typing import Optional

from . import web_verify as _V

VERSION = 1
GRID = {
    # the calculator's default camera (web/src/verify/bench.ts CALC0): only
    # OpenCV's perimeter limit (3 % of the longest side) depends on it here
    "camera": {"resolution": [1920, 1080], "hfov_deg": 70.0},
    # from the read limit (the head-on limit is 1.6-3.1 px per cell:
    # web_verify.READ_PX_PER_CELL) to Verify's bench (16 px per cell)
    "px_per_cell": [3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 13.0, 16.0],
    "blur_px": [0.5, 1.0, 1.5, 2.0, 2.5],
    "tilt_deg": [0.0, 45.0],
    "noise": 0.1,
    "seeds": 4,
}
# WHY these lines (the REF rules' own scale, core.label: "free" is a cost
# the study could not tell from zero, 0.7 module's -1.5 pts was kept as a
# tolerance, 0.5 module's -7 pts made the hard rule): a cost under
# MARGINAL_PTS % of the bare marker's reads, or one a two-sided sign test on
# the reads it lost and gained cannot tell from chance (P_MAX), is safe; up
# to UNSAFE_PTS % marginal; more is unsafe. So is losing EASY_SHARE of the
# reads the bare marker gets in its easy views (EASY_*: sharp and well
# resolved, where a bare marker never fails), EASY_MIN reads at least: a
# label that breaks easy reads breaks real ones, whatever it costs at the
# grid's hard end.
MARGINAL_PTS = 1.0
UNSAFE_PTS = 5.0
P_MAX = 0.05
EASY_PX_PER_CELL = 8.0
EASY_BLUR_PX = 1.0
EASY_SHARE = 0.02
EASY_MIN = 2
# WHY the pose too (2026-10-21, measured with this check): a ChArUco label
# moved near an inner chessboard corner (a 5 x 4 board of 12 mm squares,
# the label 3.5 mm off its square's centre toward a corner: under the 0.3
# square the REF chamfer study drew the line at) reads every id it read
# bare, but the corners the detector refines under it move: at 10 px per
# cell the board's mean pose error doubled (0.062 -> 0.119 mm, OpenCV 5.0).
# And a single marker's label run into its corner cells moved its corners
# in 13 of the 14 views where the bare pose was sharp, none the other way.
# Only where the pose is sharp, though: at 3-6 px per cell the bare board's
# own error is 4-13 mm, which buries any label. So the pose is judged over
# the views both pose and the bare pose is sharp (under POSE_SHARP_CELLS of
# a cell), at least POSE_MIN_VIEWS of them: the mean error growing by
# POSE_MARGINAL, more views worse than better and a sign test saying it is
# not chance, is marginal; growing by POSE_UNSAFE unsafe. A better pose
# never counts against a mark.
POSE_MARGINAL = 0.2
POSE_UNSAFE = 1.0
POSE_SHARP_CELLS = 0.1
POSE_MIN_VIEWS = 10
MARK_LAYER = "mark_"         # the corner mark's layers (core.chamfer: mark_triangle, mark_cut)
LEVELS = ("safe", "marginal", "unsafe")


def bare_plan(d: dict) -> dict:
    """The plan without its corner mark (its mark_* layers): the same marker,
    cells, frames and sticker."""
    return dict(d, layers=[L for L in d["layers"] if not str(L.get("name", "")).startswith(MARK_LAYER)])


def sign_p(lost: int, gained: int) -> float:
    """Two-sided exact sign test (McNemar's) on the discordant reads: the
    chance of a split this uneven if the marks made no difference."""
    n = lost + gained
    if n == 0:
        return 1.0
    k = min(lost, gained)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2.0 ** n
    return min(1.0, 2.0 * tail)


def views(g: dict, cell_mm: float):
    """GRID's views for a marker of this cell: (px per cell, Verify's ViewConditions)."""
    w, h = (int(v) for v in g["camera"]["resolution"])
    hfov = float(g["camera"]["hfov_deg"])
    f_px = (w / 2.0) / math.tan(math.radians(hfov) / 2.0)
    for ppc in g["px_per_cell"]:
        cam = {"distance_mm": cell_mm * f_px / float(ppc), "resolution": [w, h], "hfov_deg": hfov}
        for blur in g["blur_px"]:
            for tilt in g["tilt_deg"]:
                for seed in range(int(g["seeds"])):
                    yield float(ppc), {"camera": cam, "tilt_deg": float(tilt), "yaw_deg": 0.0,
                                       "blur_px": float(blur), "noise": float(g["noise"]),
                                       "glare": 0.0, "occlusion": 0.0, "seed": seed}


def verdict_of(cost_pts: float, p: float, easy_lost: int, easy_bare: int) -> str:
    """The reads' verdict: what the marks cost of the bare marker's reads."""
    if easy_lost >= EASY_MIN and easy_bare and easy_lost >= EASY_SHARE * easy_bare:
        return "unsafe"
    if p >= P_MAX or cost_pts < MARGINAL_PTS:
        return "safe"
    return "unsafe" if cost_pts >= UNSAFE_PTS else "marginal"


def pose_verdict(growth: float, p: float, worse: int, better: int) -> str:
    """The pose's verdict: how much the mean pose error grew (a share)."""
    if p >= P_MAX or worse <= better or growth < POSE_MARGINAL:
        return "safe"
    return "unsafe" if growth >= POSE_UNSAFE else "marginal"


def worst(*verdicts: str) -> str:
    return max(verdicts, key=LEVELS.index)


def check(req: dict, grid: Optional[dict] = None) -> dict:
    """What the request's label and corner mark cost the detector over the
    views of `grid` (GRID, any key replaced). Reads are ids in views:
    `reads` the marked and the bare marker's; `lost` / `gained` the reads one
    got and the other did not; `cost_pts` the net loss in % of the bare
    marker's reads; `p` the sign test's; `easy` the same in the easy views;
    `wrong` the views where the marked one read an id it does not print and
    the bare one did not; `views_lost` the views where any id was lost, as
    Verify's ViewConditions (verify(req, view) draws one); `map` the reads
    per resolution x blur ([px per cell][blur]: marked, bare, ids x views);
    `pose` over the views where the bare pose is sharp (POSE_SHARP_CELLS):
    their count, the mean pose error (mm) marked and bare, the views the
    marks made it worse / better, the sign test's p, whether there were
    enough to judge, the growth of the mean and its verdict. `verdict` is the
    worse of the reads' (`reads_verdict`) and the pose's, one plain line in
    `text`. Nothing to compare (no label drawn: off, or Flip; no corner
    mark) is said, its reads counted once."""
    _V._need_cv("the label and corner-mark check")
    g = dict(GRID, **(grid or {}))
    req = _V.placed(req)
    d = _V._plan(req)
    lab = _V._label(req, d)
    d0 = bare_plan(d)
    has_mark = len(d0["layers"]) != len(d["layers"])
    marked = _V._C.scene_of(d, lab)
    # WHY the marked scene's bounds and area for the bare one: the crop (and
    # with it the grain's draw) is cut round the bounds, so equal bounds give
    # equal crops and the same noise pixel for pixel
    bare = _V._C.Scene(d0, marked.bounds, marked.centre, marked.area, None)
    same = lab is None and not has_mark
    ids = len(d["ids"])
    W_, B_ = len(g["px_per_cell"]), len(g["blur_px"])
    per = len(g["tilt_deg"]) * int(g["seeds"])
    cells = [[[0, 0, per * ids] for _b in range(B_)] for _p in range(W_)]
    reads_m = reads_b = lost = gained = wrong = 0
    easy = {"lost": 0, "gained": 0, "bare": 0}
    views_lost, pose_m, pose_b = [], [], []
    worse = better = 0
    sharp = POSE_SHARP_CELLS * _V.cell_mm(d)
    k = 0
    for ppc, view in views(g, _V.cell_mm(d)):
        i, j = k // (B_ * per), (k // per) % B_
        k += 1
        cam = _V._C.Cam.of(view["camera"])
        b = _V._view(d, bare, cam, view, picture=False)
        m = b if same else _V._view(d, marked, cam, view, picture=False)
        fb, fm = set(b["found"]), set(m["found"])
        lo, ga = len(fb - fm), len(fm - fb)
        reads_b += len(fb)
        reads_m += len(fm)
        lost += lo
        gained += ga
        cells[i][j][0] += len(fm)
        cells[i][j][1] += len(fb)
        wrong += bool(m["wrong"]) and not b["wrong"]
        if ppc >= EASY_PX_PER_CELL and view["blur_px"] <= EASY_BLUR_PX:
            easy["lost"] += lo
            easy["gained"] += ga
            easy["bare"] += len(fb)
        if lo:
            views_lost.append(view)
        if (m["pose_error_mm"] is not None and b["pose_error_mm"] is not None
                and b["pose_error_mm"] < sharp):
            pose_m.append(m["pose_error_mm"])
            pose_b.append(b["pose_error_mm"])
            worse += m["pose_error_mm"] > b["pose_error_mm"]
            better += m["pose_error_mm"] < b["pose_error_mm"]
    cost = 100.0 * (lost - gained) / reads_b if reads_b else 0.0
    p = sign_p(lost, gained)
    reads_verdict = "safe" if same else verdict_of(cost, p, easy["lost"], easy["bare"])
    mean_m = sum(pose_m) / len(pose_m) if pose_m else None
    mean_b = sum(pose_b) / len(pose_b) if pose_b else None
    judged = not same and len(pose_b) >= POSE_MIN_VIEWS
    growth = (mean_m / mean_b - 1.0) if judged and mean_b > 0 else 0.0
    pose_p = sign_p(worse, better)
    pv = pose_verdict(growth, pose_p, worse, better) if judged else "safe"
    verdict = worst(reads_verdict, pv)
    what = " and ".join(([] if lab is None else ["label"]) + (["corner mark"] if has_mark else []))
    if same:
        text = "no label or corner mark drawn: nothing to cost"
    elif lost == 0:
        text = f"the {what} lost none of the bare marker's {reads_b} reads"
    else:
        text = (f"the {what} lost {lost} of the bare marker's {reads_b} reads"
                + (f" (and gained {gained})" if gained else "")
                + (f", {easy['lost']} of them in sharp, well-resolved views" if easy["lost"] else "")
                + (f"; {wrong} views read a wrong id" if wrong else ""))
    if pv != "safe":
        text += (f"; where the bare pose is sharp, the pose came out worse in {worse} views and "
                 f"better in {better}: a mean error of {mean_m:.3f} mm against {mean_b:.3f} mm bare")
    return {"version": VERSION, "opencv": _V.cv2.__version__, "views": k, "ids": ids, "label": lab is not None,
            "corner_mark": has_mark,
            "reads": {"marked": reads_m, "bare": reads_b}, "lost": lost, "gained": gained,
            "cost_pts": round(cost, 2), "p": round(p, 6), "easy": easy, "wrong": wrong,
            "reads_verdict": reads_verdict, "verdict": verdict, "text": text,
            "grid": {key: g[key] for key in ("px_per_cell", "blur_px", "tilt_deg", "noise", "seeds")},
            "map": cells, "views_lost": views_lost,
            "pose": {"views": len(pose_b),
                     "marked_mm": None if mean_m is None else round(mean_m, 4),
                     "bare_mm": None if mean_b is None else round(mean_b, 4),
                     "worse": worse, "better": better, "p": round(pose_p, 6), "judged": judged,
                     "growth": round(growth, 4), "verdict": pv}}
