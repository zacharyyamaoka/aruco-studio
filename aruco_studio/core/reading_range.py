"""Verify's reading range (V4 "Range strip", Zach 2026-10-21): how near and how
far a marker reads on one camera, through a budget of tilt, blur, grain and
glare. Zach: "maybe I can just select the camera and then Verify can tell me
what is a suitable range... so I can just do a sense check".

One marker on one camera answers `near_mm` - `far_mm`: the distances between
which EVERY id reads in P_READ (95 %) of the budget's cameras, with a 90 %
interval on the far end (`band_mm`, `pm`). An optional requirement (min / max
viewing distance) turns it into a test: judge() says pass or fail and what to
change.

Standard library only (core/), so Fusion's Python and the browser's Pyodide
import it, and web/scripts/parity.d/verify_range.mjs proves it byte-identical
there: the engine never renders. sweep() is a generator that asks for one
view at a time -- a distance and a case (one camera drawn from the budget:
tilt, yaw, blur, grain, glare, a seed) -- and is sent back whether that view
read every id and which ids it missed. The shell supplies the reader:
web_verify renders the plan and runs OpenCV's ArucoDetector on it (measured);
analytic_reader() is the pinhole model (the no-OpenCV fallback, the parity
case and the tests' oracle). run() drives the generator to its answer;
web_verify.range_step drives it in time slices for the browser's progress.

The method is the 2026-10-21 proposal's (docs/build_verify_test_proposals.py,
reading_range), measured there against 1,536 renders of a board:
- Far: from 300 mm out in x1.4 steps, 12 cases a step that must all read, to
  the first step that misses (the bracket); then 6 distances log-spaced over
  [0.6 x, 1.5 x] the bracket, every one of the `n` cases at each (its distance
  jittered by its own +/- 4 %: where a cell edge lands on the pixel grid
  makes single distances lucky or unlucky), the read rate made non-increasing
  (pool adjacent violators) and its P_READ crossing interpolated in
  ln(distance); the 90 % interval from 200 resamples of the cases (no new
  renders). WHY not bisection (measured 2026-10-21, board B, D435): bisecting
  on 24 cases landed 12 % past the true crossing -- the farthest distance a
  lucky case set passes wins.
- Near: where the board (label included) fills 90 % of the frame head on, or
  the camera's stated focus distance, whichever is farther; stepped out x1.15
  until 8 cases read (a tilted board's near edge runs off the frame first).
  WHY an outward search when 300 mm fails: a whole-module label knocked out of
  a single's border row fails at 0.3 m and reads at 1.2 m -- up close its
  letters resolve and cut the border; farther out the blur fills them in.

The cases are seeded (SEED) from a stdlib PRNG of our own (SplitMix64), so
the same board, camera and budget give the same answer on every run and in
every Python (a unit test must not be flaky). VERSION names the method: bump
it with any change to a constant, the PRNG or the order of the draws (the
browser caches answers by it).
"""
from __future__ import annotations

import math

VERSION = "reading-range/1"
SEED = 20261021

P_READ = 0.95             # every id reads in this share of the budget's cameras
N_CASES = 48              # cases per distance in the far fit
N_BRACKET = 12            # cases per bracket step: all must read
N_NEAR = 8                # cases per near probe: all must read
JITTER = 0.04             # each case's distance x U(1 - 4 %, 1 + 4 %) in the fit
START_MM = 300.0          # the bracket starts here
STEP = 1.4                # the bracket's step
MIN_MM = 60.0             # the bracket never goes nearer
MAX_MM = 30000.0          # ... nor farther
OUTWARD_MAX_MM = 6000.0   # the outward search (300 mm fails) gives up here
FIT_DISTANCES = 6
FIT_SPAN = (0.6, 1.5)     # the fit's distances span this x the bracket
FIT_INWARD = 0.7          # one more distance this much nearer ...
FIT_INWARD_MAX = 3        # ... at most this often, while the nearest misses P_READ
BOOT = 200                # resamples of the cases for the 90 % interval
BAND = (5.0, 95.0)
NEAR_FILL = 0.9           # the board fills this share of the frame at the near end
NEAR_STEP = 1.15
NEAR_STEPS = 6
LABEL_BISECT = 1.08       # the outward search's near end, to this ratio
PERIMETER_RATE = 0.03     # OpenCV's default minMarkerPerimeterRate (x the image's longest side)
OUTLINE_SLACK = 1.25      # the far end is "outline-limited" within this of OpenCV's minimum
MAX_TILT = 85.0           # verify.camera clamps tilt and yaw here

# The budgets: every case is a camera somewhere inside one. "field" is the
# proposal's (2026-10-21): tilt up to 45 deg in any direction, blur sigma
# 0.3-1.5 px, grain 0.02-0.2 (x 50 grey levels), glare 0-0.5, no dirt. WHY no
# dirt: the simulator sizes a dirt blob from the whole board, so any dirt
# hides a whole 30 mm marker in most draws (12 % of views read at 0.5 %
# dirt, measured 2026-10-21): it belongs to a "k of n markers" rule, not here.
BUDGETS = {
    "field": {"name": "Field", "tilt_max_deg": 45.0, "blur_px": (0.3, 1.5), "noise": (0.02, 0.2),
              "glare": (0.0, 0.5), "occlusion": 0.0},
}
DEFAULT_BUDGET = "field"

# analytic_reader: the pinhole model at the limits the simulator measured.
# WHY 3.1 px per cell at blur 0.8 (web_verify.READ_PX_PER_CELL, measured
# 2026-10-18 over 4 cameras x 5 markers): the head-on limit of a decent
# camera; more blur needs proportionally more pixels per cell (the blur's
# sigma against the cell), grain and glare a little more.
PPC_LIMIT = 3.1
PPC_BLUR = 0.8
NOISE_COST = 0.6
GLARE_COST = 0.3

_MASK = (1 << 64) - 1


class Rng:
    """SplitMix64 (Steele, Lea, Flood 2014): 64-bit integer arithmetic only,
    so the same seed draws the same numbers in CPython and Pyodide, today and
    after any change to Python's own `random`."""

    def __init__(self, seed: int):
        self.state = int(seed) & _MASK

    def next64(self) -> int:
        self.state = (self.state + 0x9E3779B97F4A7C15) & _MASK
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _MASK
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _MASK
        return z ^ (z >> 31)

    def random(self) -> float:
        """[0, 1), 53 bits."""
        return (self.next64() >> 11) * (1.0 / 9007199254740992.0)

    def uniform(self, lo: float, hi: float) -> float:
        return lo + (hi - lo) * self.random()

    def below(self, n: int) -> int:
        """An integer in [0, n): the bias of the modulo is under n / 2^64."""
        return self.next64() % n


def budget_of(budget) -> dict:
    """A budget by name ("field") or as a dict of BUDGETS' keys."""
    if isinstance(budget, dict):
        return dict(BUDGETS[DEFAULT_BUDGET], **budget)
    try:
        return dict(BUDGETS[budget or DEFAULT_BUDGET])
    except KeyError:
        raise ValueError(f"no budget {budget!r}: one of {', '.join(BUDGETS)}") from None


def cases(n: int = N_CASES, seed: int = SEED, budget=DEFAULT_BUDGET) -> list:
    """n cameras inside the budget, seeded: the same cases at every distance,
    so the read rate falls (nearly) monotonically with distance. Each is a
    ViewConditions without the camera: tilt of a random size up to the budget
    in a random direction (tilt about the marker's x, yaw about its y), blur,
    grain and glare uniform in their ranges, a seed for the grain and glare."""
    b = budget_of(budget)
    rng = Rng(seed)
    out = []
    for _ in range(int(n)):
        size = rng.uniform(0.0, b["tilt_max_deg"])
        way = rng.uniform(0.0, 2.0 * math.pi)
        out.append({"tilt_deg": size * math.cos(way), "yaw_deg": size * math.sin(way),
                    "blur_px": rng.uniform(*b["blur_px"]), "noise": rng.uniform(*b["noise"]),
                    "glare": rng.uniform(*b["glare"]), "occlusion": float(b["occlusion"]),
                    "seed": rng.below(2 ** 31 - 1)})
    return out


def jitters(n: int = N_CASES, seed: int = SEED + 1) -> list:
    rng = Rng(seed)
    return [rng.uniform(1.0 - JITTER, 1.0 + JITTER) for _ in range(int(n))]


# ------------------------------------------------------------------ the fit

def pava_down(ys: list) -> list:
    """Pool adjacent violators: the closest non-increasing sequence (equal weights)."""
    blocks = [[float(y), 1] for y in ys]
    i = 0
    while i < len(blocks) - 1:
        if blocks[i][0] < blocks[i + 1][0]:
            a, b = blocks[i], blocks[i + 1]
            k = a[1] + b[1]
            blocks[i] = [(a[0] * a[1] + b[0] * b[1]) / k, k]
            del blocks[i + 1]
            i = max(0, i - 1)
        else:
            i += 1
    out = []
    for v, k in blocks:
        out.extend([v] * k)
    return out


def crossing(grid: list, reads: list, idx) -> float | None:
    """Where the read rate over the cases `idx` (non-increasing, PAVA) falls
    through P_READ, interpolated in ln(distance); None when even the nearest
    distance misses; the farthest distance when none does (censored)."""
    m = len(idx)
    rates = pava_down([sum(1 for k in idx if row[k]) / m for row in reads])
    if rates[0] < P_READ:
        return None
    for i in range(len(rates) - 1):
        if rates[i + 1] < P_READ:
            t = (rates[i] - P_READ) / max(1e-9, rates[i] - rates[i + 1])
            return math.exp(math.log(grid[i]) + t * (math.log(grid[i + 1]) - math.log(grid[i])))
    return grid[-1]


def percentile(xs: list, q: float) -> float:
    """numpy's default (linear between the closest ranks)."""
    s = sorted(xs)
    pos = (len(s) - 1) * q / 100.0
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def focal_px(width: int, hfov_deg: float) -> float:
    return (width / 2.0) / math.tan(math.radians(hfov_deg) / 2.0)


# ------------------------------------------------------------------ the engine

def sweep(geometry: dict, camera: dict, budget=DEFAULT_BUDGET, n: int = N_CASES, seed: int = SEED):
    """THE engine, a generator. `geometry`: {bounds_mm [u0, v0, u1, v1] (the
    board, label included, in its own frame), cell_mm, marker_mm, ids};
    `camera`: {resolution [W, H], hfov_deg, focus_mm (None)}.

    Yields {distance_mm, case, view, phase, done} -- one view to read (`view`
    the case's ViewConditions without the camera, `done` 0..1 for a progress
    bar) -- and is sent (ok, missing ids) back. Returns the answer (result()).
    A view asked twice is read once (the bracket's first step is also the
    near end's first look at 300 mm)."""
    b = budget_of(budget)
    n = int(n)
    views = cases(n, seed, b)
    jit = jitters(n, seed + 1)
    seen = {}
    miss_by_id = {}
    count = [0]

    def ask(d, k, phase, done):
        key = (d, k)
        if key not in seen:
            got = yield {"distance_mm": d, "case": k, "view": views[k], "phase": phase, "done": done}
            ok, missing = bool(got[0]), [int(i) for i in (got[1] or [])]
            seen[key] = (ok, missing)
            count[0] += 1
            if phase == "fit":
                for i in missing:
                    miss_by_id[i] = miss_by_id.get(i, 0) + 1
        return seen[key]

    def probe(d, m, phase, done):
        """The first m cases at d, all must read; stops at the first miss."""
        for k in range(m):
            ok, _missing = yield from ask(d, k, phase, done)
            if not ok:
                return False
        return True

    # --- the bracket (and its first step, the near end's look at 300 mm)
    at_start = yield from probe(START_MM, N_BRACKET, "bracket", 0.02)
    lo = hi = None
    steps = 0
    if at_start:
        lo, hi = START_MM, START_MM * STEP
        while hi < MAX_MM:
            steps += 1
            if not (yield from probe(hi, N_BRACKET, "bracket", min(0.3, 0.05 + 0.05 * steps))):
                break
            lo, hi = hi, hi * STEP
    else:
        hi, lo = START_MM, START_MM / STEP
        while lo > MIN_MM and not (yield from probe(lo, N_BRACKET, "bracket", 0.1)):
            hi, lo = lo, lo / STEP
        if lo <= MIN_MM:
            lo = hi = None
    near_label = None
    if not at_start:
        # the outward search: a label that breaks the border up close reads farther out
        d, found = START_MM * STEP, None
        while d < OUTWARD_MAX_MM:
            if (yield from probe(d, N_BRACKET, "bracket", 0.15)):
                found = d
                break
            d *= STEP
        if found is not None and (lo is None or lo < 150.0):
            a, z = found / STEP, found
            while z / a > LABEL_BISECT:
                mid = math.sqrt(a * z)
                if (yield from probe(mid, N_NEAR, "bracket", 0.2)):
                    z = mid
                else:
                    a = mid
            near_label = z
            lo, hi = found, found * STEP
            while hi < MAX_MM and (yield from probe(hi, N_BRACKET, "bracket", 0.25)):
                lo, hi = hi, hi * STEP
    if lo is None:
        return result(geometry, camera, b, n, seed, None, None, None, None, [], count[0], {}, False)

    # --- the far fit
    g0, g1 = FIT_SPAN[0] * lo, FIT_SPAN[1] * hi
    grid = [g0 * (g1 / g0) ** (i / (FIT_DISTANCES - 1.0)) for i in range(FIT_DISTANCES)]
    reads = []
    for i, d in enumerate(grid):
        row = []
        for k in range(n):
            ok, _m = yield from ask(d * jit[k], k, "fit", 0.3 + 0.55 * (i + k / n) / FIT_DISTANCES)
            row.append(ok)
        reads.append(row)
    inward = 0
    while sum(reads[0]) / n < P_READ and inward < FIT_INWARD_MAX and grid[0] > MIN_MM:
        d = grid[0] * FIT_INWARD
        row = []
        for k in range(n):
            ok, _m = yield from ask(d * jit[k], k, "fit", 0.85)
            row.append(ok)
        grid.insert(0, d)
        reads.insert(0, row)
        inward += 1
    everyone = list(range(n))
    far = crossing(grid, reads, everyone)
    boot = Rng(seed + 2)
    fs = []
    for _ in range(BOOT):
        x = crossing(grid, reads, [boot.below(n) for _k in range(n)])
        fs.append(x if x is not None else grid[0] * FIT_INWARD)
    band = (percentile(fs, BAND[0]), percentile(fs, BAND[1]))
    rows = [{"d_mm": round(d, 1), "ok": sum(r), "n": n} for d, r in zip(grid, reads)]

    # --- the near end
    u0, v0, u1, v1 = geometry["bounds_mm"]
    w, h = camera["resolution"]
    f = focal_px(w, camera["hfov_deg"])
    near = max((u1 - u0) * f / (NEAR_FILL * w), (v1 - v0) * f / (NEAR_FILL * h))
    near_by = "frame"
    focus = camera.get("focus_mm")
    if focus and focus > near:
        near, near_by = float(focus), "focus"
    if near_label is not None and near_label > near:
        # WHY two names (2026-10-21): the outward search finds where it first
        # reads; when the frame alone explains that (a big board fills the
        # frame there, within two near steps), it is the frame, not the label
        near_by = "frame" if near * NEAR_STEP * NEAR_STEP >= near_label else "label"
        near = near_label
    checked = False
    for s in range(NEAR_STEPS):
        if (yield from probe(near, N_NEAR, "near", 0.88 + 0.02 * s)):
            checked = True
            break
        near *= NEAR_STEP
        near_by = "reads"
    if far is not None and near >= far:
        near = far = None
    return result(geometry, camera, b, n, seed, near, far, band, near_by, rows, count[0], miss_by_id, checked)


def result(geometry, camera, budget, n, seed, near, far, band, near_by, rows, renders, miss_by_id, checked):
    """The answer, JSON-ready (rounded to 0.1 mm): no timing, so the same
    inputs give the same bytes everywhere."""
    w, h = camera["resolution"]
    f = focal_px(w, camera["hfov_deg"])
    min_outline = PERIMETER_RATE * max(w, h)
    out = {"version": VERSION, "near_mm": None, "far_mm": None, "band_mm": None, "pm": None,
           "near_by": None, "near_checked": bool(checked), "far_limit": None, "far_px_per_cell": None,
           "far_outline_px": None, "min_outline_px": round(min_outline, 1), "weakest_id": None,
           "rows": rows, "renders": renders, "cases": n, "seed": seed, "p_read": P_READ,
           "budget": {k: (list(v) if isinstance(v, tuple) else v) for k, v in budget.items()},
           "camera": {"resolution": [int(w), int(h)], "hfov_deg": float(camera["hfov_deg"]),
                      "focus_mm": camera.get("focus_mm")},
           "geometry": {"bounds_mm": [round(float(x), 3) for x in geometry["bounds_mm"]],
                        "cell_mm": round(float(geometry["cell_mm"]), 4),
                        "marker_mm": round(float(geometry["marker_mm"]), 4),
                        "ids": [int(i) for i in geometry["ids"]]}}
    if far is None:
        out["reason"] = ("it misses an id at every distance tried (300 mm out to 6 m, and in to 60 mm)"
                         if not rows else "its near end (the frame, the focus or the label) is past its far end")
        return out
    ppc = geometry["cell_mm"] * f / far
    outline = 4.0 * geometry["marker_mm"] * f / far
    out.update({"near_mm": round(near, 1), "far_mm": round(far, 1),
                "band_mm": [round(band[0], 1), round(band[1], 1)],
                "pm": round((band[1] - band[0]) / (2.0 * far), 3), "near_by": near_by,
                "far_px_per_cell": round(ppc, 2), "far_outline_px": round(outline, 1),
                # WHY say which: past OpenCV's minimum outline no camera resolution helps
                # (only a bigger marker, or a smaller minMarkerPerimeterRate in the reader)
                "far_limit": "outline" if outline < OUTLINE_SLACK * min_outline else "cells"})
    if len(geometry["ids"]) > 1 and miss_by_id:
        worst = max(sorted(miss_by_id), key=lambda i: miss_by_id[i])
        out["weakest_id"] = int(worst)
    return out


def run(engine, read) -> dict:
    """Drive the engine to its answer: read(distance_mm, view) -> (ok, missing)."""
    try:
        ask = next(engine)
        while True:
            ask = engine.send(read(ask["distance_mm"], ask["view"]))
    except StopIteration as stop:
        return stop.value


def analytic_reader(geometry: dict, camera: dict):
    """The pinhole model as a reader (no OpenCV): a view reads when its cells
    span enough pixels across the tilt (PPC_LIMIT, more with blur, grain and
    glare), its outline is over OpenCV's minimum (PERIMETER_RATE) and the
    board fits the sensor. Deterministic, so the reading range it gives is
    exact to compute by hand (the tests' oracle). -> read(distance_mm, view)."""
    w, h = camera["resolution"]
    f = focal_px(w, camera["hfov_deg"])
    cell = float(geometry["cell_mm"])
    side = float(geometry["marker_mm"])
    u0, v0, u1, v1 = geometry["bounds_mm"]
    bw, bh = u1 - u0, v1 - v0
    min_outline = PERIMETER_RATE * max(w, h)
    ids = [int(i) for i in geometry["ids"]]

    def read(distance_mm, view):
        tilt = math.radians(max(-MAX_TILT, min(MAX_TILT, float(view.get("tilt_deg") or 0.0))))
        yaw = math.radians(max(-MAX_TILT, min(MAX_TILT, float(view.get("yaw_deg") or 0.0))))
        px_mm = f / float(distance_mm)
        across = math.cos(tilt) * math.cos(yaw)
        need = (PPC_LIMIT * math.sqrt((1.0 + (float(view.get("blur_px") or 0.0) / PPC_BLUR) ** 2) / 2.0)
                * (1.0 + NOISE_COST * float(view.get("noise") or 0.0))
                * (1.0 + GLARE_COST * float(view.get("glare") or 0.0)))
        cells = cell * px_mm * across >= need
        outline = 2.0 * side * px_mm * (math.cos(tilt) + math.cos(yaw)) >= min_outline
        grow = 1.0 + 0.5 * math.sqrt(max(0.0, 1.0 - across * across))
        fits = bw * px_mm * grow <= w and bh * px_mm * grow <= h
        ok = cells and outline and fits
        return ok, ([] if ok else list(ids))
    return read


# ------------------------------------------------------------------ the requirement

def _m(mm: float) -> str:
    return f"{mm / 1000.0:.2f} m" if mm >= 1000.0 else f"{mm:.0f} mm"


def _up(mm: float, step: float = 0.5) -> float:
    return math.ceil(mm / step - 1e-9) * step


def _down(mm: float, step: float = 0.5) -> float:
    return math.floor(mm / step + 1e-9) * step


def judge(rng: dict, need: dict | None) -> dict:
    """The reading range against a required viewing distance (`need`:
    {min_mm, max_mm}, either None): pass when the range covers it (near <=
    min, far >= max). -> {verdict "pass" | "fail" | None (nothing required),
    checks [{side "min" | "max", need_mm, got_mm, ok, by_mm}], hints [words],
    size_mm}: what to change, computed. WHY a size from proportion: the
    simulator is a pinhole, so a board scaled by k read from k x the distance
    is the same picture -- the far end scales with the marker exactly (a typed
    label height and the camera's focus distance are the exceptions)."""
    need = need or {}
    lo = need.get("min_mm")
    hi = need.get("max_mm")
    lo = float(lo) if lo not in (None, "") else None
    hi = float(hi) if hi not in (None, "") else None
    if lo is None and hi is None:
        return {"verdict": None, "checks": [], "hints": [], "size_mm": None}
    near, far = rng.get("near_mm"), rng.get("far_mm")
    geo = rng.get("geometry") or {}
    marker = float(geo.get("marker_mm") or 0.0)
    if far is None:
        return {"verdict": "fail", "checks": [{"side": s, "need_mm": v, "got_mm": None, "ok": False, "by_mm": None}
                                              for s, v in (("min", lo), ("max", hi)) if v is not None],
                "hints": ["It does not read at any distance on this camera: " + (rng.get("reason") or "")
                          + ". Try a bigger marker, or a camera with more pixels."],
                "size_mm": None}
    checks, hints = [], []
    size = None
    grow = shrink = None
    if hi is not None:
        ok = far >= hi
        checks.append({"side": "max", "need_mm": hi, "got_mm": far, "ok": ok, "by_mm": round(max(0.0, hi - far), 1)})
        if not ok:
            grow = _up(marker * hi / far) if marker else None
            words = f"Short by {_m(hi - far)}"
            if grow:
                words += f": a {grow:g} mm marker would read to {_m(hi)} (the range grows with the size)"
            if rng.get("far_limit") == "outline":
                words += (f"; or lower minMarkerPerimeterRate in your detector: its outline is "
                          f"{rng.get('far_outline_px', 0):.0f} px there, OpenCV's default skips under "
                          f"{rng.get('min_outline_px', 0):.0f} px")
            hints.append(words + ".")
    if lo is not None:
        ok = near is not None and near <= lo
        checks.append({"side": "min", "need_mm": lo, "got_mm": near, "ok": ok,
                       "by_mm": round(max(0.0, (near or 0.0) - lo), 1)})
        if not ok:
            by = rng.get("near_by")
            if by in ("frame", "reads"):
                bounds = geo.get("bounds_mm") or [0.0, 0.0, 0.0, 0.0]
                across = max(bounds[2] - bounds[0], bounds[3] - bounds[1])
                fits = across * lo / near if near else 0.0
                shrink = _down(marker * lo / near) if (marker and near) else None
                hints.append(f"Too big for the frame at {_m(lo)}: it fills it from {_m(near)}; "
                             f"at {_m(lo)} the board must be at most {fits:.0f} mm across"
                             + (f" (a {shrink:g} mm marker)" if shrink else "") + ", or move the camera back.")
            elif by == "focus":
                hints.append(f"The camera focuses from {_m(near)}: nearer than that the picture is soft; "
                             "move it back, or pick a camera that focuses closer.")
            else:
                hints.append(f"Up close it misses an id until {_m(near)}: the label's letters cut the border. "
                             "Put the label outside, or make it smaller (Auto).")
    if grow and shrink and shrink < grow:
        hints.append(f"No one size covers {_m(lo)} to {_m(hi)} on this camera: the far end needs at least "
                     f"{grow:g} mm, the near end at most {shrink:g} mm. A camera with more pixels, "
                     "or two markers of different sizes.")
        size = None
    else:
        size = grow if grow else shrink
    verdict = "pass" if all(c["ok"] for c in checks) else "fail"
    return {"verdict": verdict, "checks": checks, "hints": hints, "size_mm": size}
