# REF: tests/test_aruco_trim.py at c8216ff (cad-exporter), ported by tools/port_ref_suites.py:
# REF's checks verbatim, run against aruco_studio.core. Do not edit by hand.
"""Offline: Trim excess, the pure model (bam_cad_core.aruco_trim).

Zach, 2026-10-16: "trim excess on the outside ... like an extrude delete of
the bodies outside ... by default is off". docs/design_aruco_trim.md: the
setting (versioned, junk reads as off), the outline, the kept column and
the sides it cuts, the refusals (not a rectangle, holes, the part bigger
than its face, nothing measured), Cut anyway, the words.

Run:  python tests/test_aruco_trim.py
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
pass  # REF put its own tree on sys.path here (ported: not needed)
try:
    sys.stdout.reconfigure(errors="replace")
except AttributeError:
    pass

from aruco_studio.core import trim as T  # noqa: E402

PASS, FAIL = 0, []


def check(label, condition, detail=""):
    global PASS
    if condition:
        PASS += 1
        print(f"  ok  {label}")
    else:
        FAIL.append(label)
        print(f"FAIL  {label}  {detail}")


def rect(u0, v0, u1, v1):
    return [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]


def circle(cx, cy, r, n=64, cw=False):
    pts = [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n))
           for k in range(n)]
    return pts[::-1] if cw else pts


def near(a, b, tol=1e-9):
    if isinstance(a, (tuple, list)):
        return len(a) == len(b) and all(near(x, y, tol) for x, y in zip(a, b))
    return abs(a - b) <= tol


TAG = T.outline((-20.0, -20.0, 20.0, 20.0))
PLATE = (-25.0, -25.0, 25.0, 25.0)
PLATE_FACE = [rect(*PLATE)]
PLATE_MM3 = 50.0 * 50.0 * 5.0


def plate_removed(keep):
    """mm3 a 50 x 50 x 5 plate loses outside `keep`."""
    u0, v0 = max(PLATE[0], keep[0]), max(PLATE[1], keep[1])
    u1, v1 = min(PLATE[2], keep[2]), min(PLATE[3], keep[3])
    return PLATE_MM3 - max(0.0, u1 - u0) * max(0.0, v1 - v0) * 5.0


def plate_plan(axes, out=TAG, **kw):
    keep, _cut = T.keep_and_cut(axes, out, PLATE)
    return T.plan_trim(axes, out, PLATE, PLATE_FACE, volumes=(PLATE_MM3, plate_removed(keep)),
                       z=(-5.0, 2.0), **kw)


print("== the setting: versioned, junk reads as off")
check("trim_of: None, {}, a list, a string, an unknown rule / axes, no axes -> None (off)",
      all(T.trim_of(r) is None for r in (None, {}, [], "x", 3, {"rule": 2, "axes": "x"},
                                         {"rule": "one", "axes": "x"}, {"axes": "z"},
                                         {"rule": 1})))
check("trim_of: a stored dict -> normalised (rule 1, margin rounded, force bool)",
      T.trim_of({"axes": "x", "margin_mm": 1.23456789, "force": 1})
      == {"rule": 1, "axes": "x", "margin_mm": 1.234568, "force": True})
check("trim_of: a negative / NaN / huge / text margin -> 0 / 0 / 50 / 0",
      [T.trim_of({"axes": "y", "margin_mm": m})["margin_mm"]
       for m in (-3, float("nan"), 1e9, "big")] == [0.0, 0.0, 50.0, 0.0])
check("setting('off') is None; setting('both', 2) the stored dict",
      T.setting("off") is None and T.setting("both", 2.0)
      == {"rule": 1, "axes": "both", "margin_mm": 2.0, "force": False})
check("setting() round-trips through trim_of unchanged (an unchanged edit writes nothing)",
      all(T.trim_of(T.setting(a, m, f)) == T.setting(a, m, f)
          for a in T.AXES for m in (0.0, 0.15, 1.5, 0.68 * 3) for f in (False, True)))
check("cut_axes: x / y / both", [T.cut_axes(a) for a in T.AXES]
      == [(True, False), (False, True), (True, True)])
check("CHOICES: off first", T.CHOICES == ("off", "x", "y", "both"))

print("== the outline: the base, what sticks out, the margin")
check("outline(base) is the base", T.outline((-1, -2, 3, 4)) == (-1, -2, 3, 4))
check("outline takes in extras (a label strip below, a pin) and skips None",
      T.outline((-10, -10, 10, 10), [(-8, -16, 8, -11), None, (-9, 5, -6, 9)])
      == (-10, -16, 10, 10))
check("outline grows by the margin all round (a negative margin is 0)",
      T.outline((-10, -10, 10, 10), margin=1.5) == (-11.5, -11.5, 11.5, 11.5)
      and T.outline((-10, -10, 10, 10), margin=-3) == (-10, -10, 10, 10))

print("== polygons: area, clip, the outer loop")
check("area of a CCW 10 x 4 rect is 40, CW is -40",
      near(T.area(rect(0, 0, 10, 4)), 40.0) and near(T.area(rect(0, 0, 10, 4)[::-1]), -40.0))
check("clip a 10 x 10 square to its right half: area 50",
      near(abs(T.area(T.clip(rect(-5, -5, 5, 5), (0, -9, 9, 9)))), 50.0))
check("clip keeps a CW polygon's area too", near(abs(T.area(T.clip(rect(-5, -5, 5, 5)[::-1],
                                                                       (-9, 0, 9, 9)))), 50.0))
check("clip of a disjoint polygon is empty", T.clip(rect(20, 20, 30, 30), (0, 0, 10, 10)) == [])
outer, holes = T.split_loops([circle(0, 0, 2, cw=True), rect(-25, -25, 25, 25),
                              circle(10, 0, 3, cw=True)])
check("split_loops: the outer loop is the biggest, whatever the order",
      near(abs(T.area(outer)), 2500.0) and len(holes) == 2)
check("face_area subtracts the holes; kept_area clips them too",
      near(T.face_area(outer, holes), 2500.0 - math.pi * 13, 0.3)
      and near(T.kept_area(outer, holes, (-25, -25, 0, 25)), 1250.0 - math.pi * 2, 0.2))

print("== keep and cut: the outline on the sides cut, past the body elsewhere")
keep, cut = T.keep_and_cut("x", TAG, PLATE, pad=10.0)
check("Width: left / right cut 5 mm, the column the outline in x and past the body in y",
      cut == {"left": 5.0, "right": 5.0} and keep == (-20.0, -35.0, 20.0, 35.0), (keep, cut))
keep, cut = T.keep_and_cut("y", TAG, PLATE, pad=10.0)
check("Height: bottom / top cut, x past the body",
      cut == {"bottom": 5.0, "top": 5.0} and keep == (-35.0, -20.0, 35.0, 20.0), (keep, cut))
keep, cut = T.keep_and_cut("both", TAG, PLATE, pad=10.0)
check("Both: all four sides, the column IS the outline", len(cut) == 4 and keep == TAG)
keep, cut = T.keep_and_cut("both", (-20, -25.005, 24.995, 30), PLATE, pad=10.0)
check("a side whose excess is under TOL_MM (or negative) is not cut: no sliver, no coplanar face",
      cut == {"left": 5.0} and keep == (-20.0, -35.0, 35.0, 35.0), (keep, cut))
keep, cut = T.keep_and_cut("both", T.outline(TAG, margin=10), PLATE, pad=10.0)
check("a margin past the body: nothing to cut", cut == {} and keep == T.grow(PLATE, 10.0))
check("pad_for: the body's diagonal, 10 mm at least",
      near(T.pad_for(PLATE, (-5, 2)), math.sqrt(50 ** 2 * 2 + 7 ** 2))
      and T.pad_for((0, 0, 1, 1)) == T.PAD_MIN_MM)

print("== a plate under its face: trims, no refusal")
p = plate_plan("x")
check("Width: active, cuts, not refused; face and part both lose 20 %",
      p.active and p.cuts and not p.refused and not p.refusals
      and near(p.face_share, 0.2) and near(p.body_share, 0.2), (p.refusals, p.face_share))
check("its column is the keep; after it the plate is 40 x 50",
      p.column() == p.keep and near(p.size_after(), (40.0, 50.0)))
check("the words: 'trims 5.0 mm off each side (width): plate 50.0 → 40.0 mm wide; removes "
      "2.50 cm³ (20 % of it)'",
      T.summary(p, "plate") == "trims 5.0 mm off each side (width): plate 50.0 → 40.0 mm wide; "
      "removes 2.50 cm³ (20 % of it)", T.summary(p, "plate"))
p = plate_plan("both")
check("Both: 36 % of each, no refusal; 'plate 50.0 × 50.0 → 40.0 × 40.0 mm'",
      p.cuts and near(p.face_share, 0.36) and near(p.body_share, 0.36)
      and "(width and height): plate 50.0 × 50.0 → 40.0 × 40.0 mm" in T.summary(p, "plate"),
      T.summary(p, "plate"))
p = plate_plan("y", out=(-20, -18, 20, 22.5))
check("Height, off centre: 'trims 7.0 mm bottom, 2.5 mm top (height): plate 50.0 → 40.5 mm high'",
      T.summary(p, "plate").startswith("trims 7.0 mm bottom, 2.5 mm top (height): plate 50.0 → "
                                       "40.5 mm high"), T.summary(p, "plate"))
p = plate_plan("x", margin=2.0, out=T.outline(TAG, margin=2.0))
check("a 2 mm margin: 3 mm off each side, plate 50 → 44", near(p.cut["left"], 3.0)
      and near(p.size_after()[0], 44.0) and p.margin == 2.0)

print("== nothing to trim")
p = plate_plan("x", out=(-25, -20, 25, 20))
check("a tag spanning the width: Width trims nothing -- not active, a note, the column keeps "
      "everything", not p.active and not p.cuts and not p.refusals
      and bool(p.notes) and p.notes[0].startswith("nothing to trim (width)")
      and T.inside(PLATE, p.column()), (p.cut, p.notes))
check("... and its column contains the body with room (no coplanar faces)",
      T.inside(T.grow(PLATE, 1.0), p.column()))
check("summary says it", T.summary(p).startswith("nothing to trim"))

print("== refusals: not a rectangle")
disc = [circle(0, 0, 25)]
removed = math.pi * 625 * 5 - 40 * 40 * 5 + 0.0       # the disc is inside the square's corners
p = T.plan_trim("both", TAG, PLATE, disc, volumes=(math.pi * 625 * 5, 1000.0), z=(-5, 0))
check("a disc: refused -- 'the face is not a rectangle ... (it fills 78 % of its box ...)'",
      p.refused and any("not a rectangle" in r and "78 %" in r for r in p.refusals), p.refusals)
check("refused: the node keeps the body whole (the column contains it)",
      not p.cuts and T.inside(PLATE, p.column()))
p2 = T.plan_trim("both", TAG, PLATE, disc, volumes=(math.pi * 625 * 5, 1000.0), z=(-5, 0),
                 force=True)
check("Cut anyway: forced, not refused, cuts (the column is the outline)",
      p2.forced and not p2.refused and p2.cuts and p2.column() == p2.keep)
rr = [rect(-25, -25, 25, 25)]
r = 3.0
rounded = [[(x * (25 - r) / 25.0 if abs(x) > 25 - r and abs(y) > 25 - r else x, y)
            for x, y in rr[0]]]
fillet = []
for (cx, cy, a0) in ((22, -22, -90), (22, 22, 0), (-22, 22, 90), (-22, -22, 180)):
    fillet += [(cx + r * math.cos(math.radians(a0 + k * 90 / 8)),
                cy + r * math.sin(math.radians(a0 + k * 90 / 8))) for k in range(9)]
p = T.plan_trim("both", TAG, PLATE, [fillet], volumes=(PLATE_MM3, plate_removed(TAG)),
                z=(-5, 0))
check("a rounded-corner plate (r = 3 mm) is a rectangle (fills >= 98 %): no refusal",
      not p.refusals, p.refusals)
ell = [[(-25, -25), (25, -25), (25, 0), (0, 0), (0, 25), (-25, 25)]]
p = T.plan_trim("x", TAG, PLATE, ell, volumes=(PLATE_MM3 * 0.75, 1000.0))
check("an L: refused (not a rectangle)", p.refused and "not a rectangle" in p.refusals[0])
turned = [[(0, -35.3), (35.3, 0), (0, 35.3), (-35.3, 0)]]
p = T.plan_trim("x", TAG, (-35.3, -35.3, 35.3, 35.3), turned, volumes=(10000.0, 2000.0))
check("a plate turned 45° to the tag: refused (fills 50 % of its box)",
      p.refused and "50 %" in p.refusals[0], p.refusals)

print("== refusals: holes")
holed = [rect(*PLATE), circle(-23, 0, 1.5, cw=True), circle(19.5, 10, 1.5, cw=True),
         circle(0, 0, 2, cw=True)]
keep, _c = T.keep_and_cut("x", TAG, PLATE)
p = T.plan_trim("x", TAG, PLATE, holed, volumes=(PLATE_MM3, plate_removed(keep)))
check("a hole in the excess is removed, one on the trim line is cut through, one inside is "
      "kept: 'the trim removes 1 hole and cuts through 1 hole of the face'",
      p.refused and p.holes == (1, 1)
      and "the trim removes 1 hole and cuts through 1 hole of the face" in p.refusals, p.refusals)
p = T.plan_trim("x", TAG, PLATE, [rect(*PLATE), circle(0, 0, 2, cw=True)],
                volumes=(PLATE_MM3, plate_removed(keep)))
check("a hole the tag keeps clear of: no refusal", not p.refusals and p.holes == (0, 0),
      p.refusals)
p = T.plan_trim("y", TAG, PLATE, holed, volumes=(PLATE_MM3, 2000.0))
check("Height only: the same holes sit inside the kept band -> no hole refusal",
      p.holes == (0, 0) and not any("hole" in r for r in p.refusals), (p.holes, p.refusals))

print("== refusals: the part is bigger than its face (a boss on a plate)")
boss_face = [rect(-22, -22, 22, 22)]
body = (-60.0, -60.0, 60.0, 60.0)
vb = 120 * 120 * 5 + 44 * 44 * 10
keep, _c = T.keep_and_cut("both", TAG, body)
vr = vb - (40 * 40 * 15)
p = T.plan_trim("both", TAG, body, boss_face, volumes=(vb, vr), z=(-15, 2))
check("a 44 mm boss on a 120 mm plate: the trim takes 74 % of the part, 17 % of the face -> "
      "refused, both shares in the words",
      p.refused and any("74 %" in r and "17 %" in r and "beyond this face" in r
                        for r in p.refusals), (p.refusals, p.body_share, p.face_share))
check("... and it says how far the part reaches past the face (a note)",
      any("reaches past the face" in t and "38.0 mm left" in t for t in p.notes), p.notes)
fil_face = [rect(-23, -23, 23, 23)]
keep, _c = T.keep_and_cut("both", TAG, PLATE)
p = T.plan_trim("both", TAG, PLATE, fil_face, volumes=(PLATE_MM3 - 4 * 50 * 2 * 0.86,
                                                       plate_removed(keep) - 4 * 40 * 0.86))
check("a plate with 2 mm fillets on its top edges: the face is 2 mm smaller -- no refusal, "
      "a note 'trimmed with the excess'", not p.refusals
      and any("trimmed with the excess" in t for t in p.notes), (p.refusals, p.notes))

print("== refusals: nothing measured")
p = T.plan_trim("x", TAG, PLATE, None, volumes=(PLATE_MM3, 2500.0))
check("no face to measure: refused", p.refused and "no face" in p.refusals[0])
p = T.plan_trim("x", TAG, PLATE, None, volumes=(PLATE_MM3, 2500.0), need_face=False)
check("need_face=False: no refusal for it", not p.refusals)
p = T.plan_trim("x", TAG, PLATE, PLATE_FACE, volumes=None)
check("no volumes: refused 'what the trim removes could not be measured'",
      p.refused and p.refusals == ["what the trim removes could not be measured"])
f = T.failed("both", None, "the body is gone")
check("failed(): refused, not active, Cut anyway cannot make it cut, a column around "
      "everything", f.refused and not f.active and not f.cuts
      and T.inside((-5000, -5000, 5000, 5000), f.column()))
f = T.failed("x", PLATE, "x", force=True)
check("failed(body): its column contains the body", T.inside(PLATE, f.column()) and f.refused)

print("== the ghost's regions: the removed strips, never overlapping")
for axes, n in (("x", 2), ("y", 2), ("both", 4)):
    p = plate_plan(axes)
    regs = p.regions()
    tot = sum((r[2] - r[0]) * (r[3] - r[1]) for r in regs)
    k = p.keep
    kept = (min(PLATE[2], k[2]) - max(PLATE[0], k[0])) * (min(PLATE[3], k[3]) - max(PLATE[1], k[1]))
    check(f"{axes}: {n} strips, their area = the plate's - what is kept",
          len(regs) == n and near(tot, 2500.0 - kept), (regs, tot, kept))

print("== random plates: the column keeps the outline, cuts only past it")
rng = random.Random(16)
bad = []
for _ in range(400):
    bw, bh = rng.uniform(10, 200), rng.uniform(10, 200)
    cx, cy = rng.uniform(-5, 5), rng.uniform(-5, 5)
    body = (cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2)
    tw, th = rng.uniform(2, bw * 1.2), rng.uniform(2, bh * 1.2)
    out = (-tw / 2, -th / 2, tw / 2, th / 2)
    axes = rng.choice(T.AXES)
    keep, cut = T.keep_and_cut(axes, out, body)
    tx, ty = T.cut_axes(axes)
    ok = T.inside(T.union([out]), keep, 1e-9) or not T.inside(out, body)
    ok = ok and all(keep[i] == out[i] for side, i in (("left", 0), ("right", 2), ("bottom", 1),
                                                     ("top", 3)) if side in cut)
    ok = ok and all((side in cut) == (axis_on and ex > T.TOL_MM) for side, axis_on, ex in (
        ("left", tx, out[0] - body[0]), ("right", tx, body[2] - out[2]),
        ("bottom", ty, out[1] - body[1]), ("top", ty, body[3] - out[3])))
    ok = ok and all((keep[i] < body[i] if i < 2 else keep[i] > body[i])
                    for side, i in (("left", 0), ("bottom", 1), ("right", 2), ("top", 3))
                    if side not in cut)
    if not ok:
        bad.append((axes, body, out, keep, cut))
check("400 random plates / tags / axes: outline kept on cut sides, every other side past the "
      "body, a side cut iff its axis is trimmed and its excess > TOL", not bad, bad[:2])

print()
print(f"{PASS} passed, {len(FAIL)} failed")
if FAIL:
    sys.exit(1)
