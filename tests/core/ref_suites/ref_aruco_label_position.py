# REF: tests/test_aruco_label_position.py at c8216ff (cad-exporter), ported by tools/port_ref_suites.py:
# REF's checks verbatim, run against aruco_studio.core. Do not edit by hand.
"""Offline: where a label on the white goes, and who decides (2026-10-13).

Zach, on his GIM43 disc: "As I position the label manually it would be
helpful if the quiet zone is drawn" ... "Auto positioning should find the
closest valid spot: out of the quiet zone, near the bottom, not on a hole,
still on the face. I would say that is a good place no?" ... "Offset X and
Offset Y can start at auto?"

  * the clearance rule, two numbers: the quiet ring is the HARD line
    (WHITE_GAP_MIN beyond it, a violation inside: Build anyway); auto keeps
    WHITE_GAP_PREF more when it fits, and nearer is no violation, no note
    (tools/study_aruco_label_gap.py -> reports/media/aruco/marks/gap_black.json)
  * Zach's real disc (tests/fixtures/aruco_label_gim43_disc.json): auto
    finds a spot below the marker, beside the hole under it, on the face;
    his own spot is no longer in the clear zone (only 0.4 mm too near the
    hole); 1 mm further right it is built without Build anyway
  * Auto position: position_of() is auto's spot; a manual position there
    gives the very same label (taking over never moves it), elsewhere
    the label sits there, as big as fits (never above auto's cap)
  * older records' offset_x_mm / offset_y_mm: auto's label moved by them
  * no room anywhere: refused, saying why, in three lines at most
  * ArUco IDs copies (relabel, label_for_instance, copy_regions) print
    their own id at a manual spot
  * the far search: past REACH, as far as the face goes

Run:  python tests/test_aruco_label_position.py
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
pass  # REF put its own tree on sys.path here (ported: not needed)
sys.path.insert(0, str(HERE))

from aruco_studio.core import label as L  # noqa: E402
from aruco_studio.core import markers as M  # noqa: E402

import ref_aruco_label_fixtures as FX  # noqa: E402

PASS, FAIL = 0, []


def check(label, condition, detail=""):
    global PASS
    if condition:
        PASS += 1
        print(f"  ok  {label}")
    else:
        FAIL.append(label)
        print(f"FAIL  {label}  {detail}")


def close(a, b, tol=1e-6):
    if isinstance(a, (tuple, list)):
        return a is not None and len(a) == len(b) and all(close(x, y, tol) for x, y in zip(a, b))
    return a is not None and abs(a - b) <= tol


def circle(cx, cy, r, n=96, cw=False):
    pts = [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n))
           for k in range(n)]
    return pts[::-1] if cw else pts


def boxes(lab):
    return [b.to_list(6) for b in lab.boxes()]


def shifted(lab, dx, dy):
    return [[round(b.cx + dx, 6), round(b.cy + dy, 6), round(b.length, 6), round(b.width, 6),
             round(b.angle, 6)] for b in lab.boxes()]


def mod(spec):
    return spec.module_m * 1000.0


SINGLE = M.TagSpec(marker_id=12, marker_length_m=0.03)
G = FX.gim43()
GS, GP = G["spec"], G["plan"]
GL = dict(G["label"])
gm = mod(GS)
ge = max(L.WHITE_EDGE * gm, L.EDGE_MIN_MM)
HOLE = (2.09, -23.75, 1.425)                     # the hole under the marker (the fixture's)


def hole_gap(lab):
    """The label's ink to the hole under the marker (mm)."""
    r = lab.parts[0].rect
    return L.rect_point_dist(r, HOLE[:2]) - HOLE[2]


# ======================================================== the clearance rule
print("== the clearance rule: a hard line and a preferred margin")
check("WHITE_GAP_MIN = 0 (the quiet ring itself), WHITE_GAP_PREF = 0.25 module",
      L.WHITE_GAP_MIN == 0.0 and L.WHITE_GAP_PREF == 0.25)
z = L.clear_zones(SINGLE)
m = mod(SINGLE)
check("clear_zones: hard = the black grown by the quiet ring (1 module), preferred = 0.25 "
      "module more", close(z["hard"], (-20.0, -20.0, 20.0, 20.0))
      and close(z["preferred"], (-21.25, -21.25, 21.25, 21.25)) and m == 5.0, z)
roomy = [L.rect_loop((-60.0, -60.0, 60.0, 60.0))]
lab = L.plan_label(SINGLE, {"rule": 2, "on": True, "place": "white", "side": "below", "nozzle_mm": 0.45},
                   mode="black", op=None, region=roomy)
check("room to spare: auto keeps the preferred margin (the label's top on that line)",
      lab.ok and close(lab.slots[0].rect[3], z["preferred"][1]), lab.slots and lab.slots[0].rect)
tight = [L.rect_loop((-40.0, -24.0, 40.0, 40.0))]       # 4 mm of white below the ring
lab = L.plan_label(SINGLE, {"rule": 2, "on": True, "place": "white", "side": "below", "nozzle_mm": 0.45},
                   mode="black", op=None, region=tight)
check("only the hard line has room: auto uses it -- no violation, no note about it",
      lab.ok and close(lab.slots[0].rect[3], z["hard"][1]) and not lab.violations
      and not any("clear zone" in n or "margin" in n for n in lab.notes)
      and not L.check_label(SINGLE, lab), (lab.notes, lab.slots and lab.slots[0].rect))
base = L.plan_label(SINGLE, {"rule": 2, "on": True, "place": "white", "side": "below", "nozzle_mm": 0.45},
                    mode="black", op=None, region=roomy)
for dy, words in ((1.25, None), (1.25 + 0.5, "inside the detector's clear zone by 0.5 mm")):
    mv = L.plan_label(SINGLE, {"rule": 2, "on": True, "place": "white", "side": "below", "nozzle_mm": 0.45,
                               "offset_y_mm": dy}, mode="black", op=None, region=roomy)
    if words is None:
        check("moved up to the hard line (the preferred margin given up): built, nothing said",
              mv.ok and not mv.violations and not any("clear zone" in n for n in mv.notes),
              mv.notes)
    else:
        check(f"0.5 mm past it: not built -- '{words}' (the hard zone, by name and number)",
              mv.kind == "none" and mv.preview is not None and words in mv.preview.violations,
              mv.preview and mv.preview.violations)

# ===================================================== Zach's GIM43 disc
print(f"== Zach's GIM43 disc ({'measured' if G['source'].startswith('MEASURED') else 'GUESS'}): "
      f"{GS.marker_length_m * 1000:g} mm marker, '#0', nozzle {GL['nozzle_mm']:g}")
t0 = time.perf_counter()
auto = L.plan_label(GS, GL, **GP)
dt = (time.perf_counter() - t0) * 1000.0
hard = L.clear_zones(GS)["hard"]
pos = L.position_of(auto)
check(f"D1 Side Auto (as he had it): built, below the marker, upright ({dt:.0f} ms)",
      auto.ok and auto.side == "below" and auto.slots[0].rot == 0 and dt < 1000.0,
      (auto.kind, auto.side, auto.notes))
check("D2 ... outside the detector's clear zone, on the face, clear of the hole under the "
      f"marker by the edge margin ({hole_gap(auto):.2f} >= {ge:.2f} mm)",
      not L.label_violations(GS, auto, loops=GP["region"], keep=L.mark_keepouts(GP["mark"]))
      and auto.parts[0].rect[3] <= hard[1] + 1e-9 and hole_gap(auto) >= ge - 1e-6
      and not L.check_label(GS, auto), auto.parts[0].rect)
zx, zy = G["zach"]["position_mm"]
check(f"D3 ... near his spot: the same band below the marker (y {pos[1]:.1f} vs his {zy:.1f}), "
      f"beside the same hole (x {pos[0]:+.1f} vs his {zx:+.1f})",
      abs(pos[1] - zy) < 2.0 and abs(pos[0]) < 8.0 and abs(pos[0] - zx) < 12.0, pos)
below = L.plan_label(GS, dict(GL, side="below"), **GP)
check("D4 Side Below gives the same spot", close(L.position_of(below), pos), L.position_of(below))
man = L.plan_label(GS, dict(GL, position="manual", x_mm=zx, y_mm=zy), **GP)
vs = man.preview.violations if man.preview else []
check("D5 his own spot (X 6, Y -20.8): no longer in the clear zone; what is left is 0.4 mm "
      "to the hole (the edge margin is 1.2) -- shown there, named, not built",
      man.kind == "none" and man.preview is not None
      and not any("clear zone" in v for v in vs)
      and vs == ["0.4 mm from a hole (it needs 1.2 mm)"]
      and close(L.position_of(man), (zx, zy), 1e-6), vs)
ok1 = L.plan_label(GS, dict(GL, position="manual", x_mm=zx + 1.0, y_mm=zy), **GP)
check("D6 1 mm further right: built there, no Build anyway, its centre exactly there",
      ok1.ok and not ok1.violations and not ok1.forced
      and close(L.position_of(ok1), (zx + 1.0, zy), 1e-6)
      and not L.label_violations(GS, ok1, loops=GP["region"]) and not L.check_label(GS, ok1),
      (ok1.notes, ok1.preview and ok1.preview.violations))
lines = L.describe(man, "black")
check("D7 the dialog says it in two lines: what is wrong (with the number), what to do",
      len(lines) == 2 and lines[0][0] == L.ERROR and "0.4 mm from a hole" in lines[0][1]
      and "Build anyway" in lines[1][1] and not any("label:" in t for _l, t in lines), lines)
old_rec = {k: v for k, v in GL.items() if k != "rule"}            # as an older record
legacy = L.plan_label(GS, dict(old_rec, offset_x_mm=6.0, offset_y_mm=4.0), **GP)
check("D8 had he saved his Offset (6, 4) (an older record: rule 1), it would recompute as it "
      "was: refused, 4.0 mm inside the old 2-module line and 0.4 mm from the hole",
      legacy.settings.rule == 1 and legacy.kind == "none" and legacy.preview is not None
      and any("4.0 mm inside the 1 module kept around" in v for v in legacy.preview.violations)
      and any("0.4 mm from a hole" in v for v in legacy.preview.violations)
      and close(L.position_of(legacy), (zx, zy), 1e-3), legacy.preview and legacy.preview.violations)

# ===================================================== Auto position
print("== Auto position: Offset X / Y show auto's spot; typing one takes over")
for what, spec, kw, settings in (
        ("GIM43, the white", GS, GP, dict(GL)),
        ("a strip below a 30 mm tag", SINGLE, {"grow": True},
         {"rule": 2, "on": True, "place": "white", "nozzle_mm": 0.45}),
        ("the black, both rows", M.TagSpec(marker_id=12, marker_length_m=0.04), {},
         {"rule": 2, "on": True, "place": "black", "content": "id_name"})):
    a = L.plan_label(spec, settings, name="Arm", **kw)
    p = L.position_of(a)
    same = L.plan_label(spec, dict(settings, position="manual", x_mm=p[0], y_mm=p[1]),
                        name="Arm", **kw)
    near = L.plan_label(spec, dict(settings, position="manual", x_mm=round(p[0], 3),
                                   y_mm=round(p[1], 3)), name="Arm", **kw)
    check(f"{what}: unticking Auto position at auto's spot changes nothing (same boxes, same "
          "cap; a field rounded to 0.001 mm too)",
          a.ok and same.ok and boxes(same) == boxes(a) and near.ok and boxes(near) == boxes(a)
          and same.cap == a.cap, (p, same.notes))
a = L.plan_label(GS, GL, **GP)
p = L.position_of(a)
moved = L.plan_label(GS, dict(GL, position="manual", x_mm=p[0] - 0.3, y_mm=p[1] + 0.5), **GP)
check("a spot that has room (0.3 left, 0.5 up -- into auto's preferred margin, which is no "
      "rule): the label there, exactly (its centre), at auto's cap",
      moved.ok and close(L.position_of(moved), (p[0] - 0.3, p[1] + 0.5), 1e-6)
      and close(moved.cap, a.cap), (moved.notes, moved.cap, a.cap))
squeeze = L.plan_label(GS, dict(GL, position="manual", x_mm=zx + 1.0, y_mm=zy), **GP)
check("a tighter spot: Auto size shrinks it to fit there (never above auto's cap), no note",
      squeeze.ok and squeeze.cap < a.cap - 1e-9 and squeeze.cap >= L.min_cap(0.6) - 1e-9
      and not any("shrunk" in n for n in squeeze.notes), (squeeze.cap, a.cap, squeeze.notes))
typed = L.plan_label(GS, dict(GL, cap_mm=3.5, position="manual", x_mm=zx + 1.0, y_mm=zy), **GP)
check("... a typed cap that does not fit there: shrunk, with a note",
      typed.ok and typed.cap < 3.5 and any("shrunk" in n for n in typed.notes),
      (typed.cap, typed.notes))
blk = L.plan_label(M.TagSpec(marker_id=12, marker_length_m=0.04),
                   {"rule": 2, "on": True, "place": "black", "content": "id_name"}, name="Arm")
bp = L.position_of(blk)
bm = L.plan_label(M.TagSpec(marker_id=12, marker_length_m=0.04),
                  {"rule": 2, "on": True, "place": "black", "content": "id_name", "position": "manual",
                   "x_mm": bp[0] + 2.0, "y_mm": bp[1] + 3.0}, name="Arm")
check("on the black: along its row only -- x taken, y clamped with a note",
      bm.ok and close(L.position_of(bm)[0], bp[0] + 2.0, 1e-6)
      and abs(L.position_of(bm)[1] - bp[1]) < 1.0
      and any("along its row only" in n for n in bm.notes), (L.position_of(bm), bm.notes))
nowhere = [circle(0.0, 0.0, 20.0)]
hand = L.plan_label(GS, dict(GL, position="manual", x_mm=0.0, y_mm=-30.0), mode="black", op=None,
                    region=[circle(0.0, -10.0, 32.0)])
check("auto refused on that side, but a spot put by hand has room: built there",
      hand.ok and close(L.position_of(hand), (0.0, -30.0), 1e-6), (hand.notes, hand.kind))

print("== settings: position auto | manual (x, y); old records keep their offsets")
s = L.LabelSettings.from_dict({"on": True, "offset_x_mm": 1.5, "offset_y_mm": -2.0})
check("an old dict (no 'position', no 'rule'): auto, its offset kept as a nudge, rule 1",
      s.position == "auto" and s.offset_x_mm == 1.5 and s.nudged and not s.manual
      and s.rule == 1)
d = L.LabelSettings(on=True, position="manual", x_mm=6.0, y_mm=-20.5).to_dict()
check("manual round-trips; auto stores no spot",
      L.LabelSettings.from_dict(d).manual and L.LabelSettings.from_dict(d).x_mm == 6.0
      and L.LabelSettings(on=True, x_mm=3.0).to_dict()["x_mm"] == 0.0
      and L.LabelSettings.from_dict({"position": "nope"}).position == "auto")
for spec, kw, settings, off in (
        (SINGLE, {"grow": True}, {"rule": 2, "on": True, "place": "white", "nozzle_mm": 0.45}, (2.0, -1.5)),
        (GS, GP, dict(GL), (-0.3, 0.5)),
        (M.TagSpec(marker_id=12, marker_length_m=0.04), {},
         {"rule": 2, "on": True, "place": "black", "content": "id"}, (1.5, 0.0))):
    a = L.plan_label(spec, settings, **kw)
    old = L.plan_label(spec, dict(settings, offset_x_mm=off[0], offset_y_mm=off[1]), **kw)
    p = L.position_of(a)
    as_manual = L.plan_label(spec, dict(settings, position="manual", x_mm=p[0] + off[0],
                                        y_mm=p[1] + off[1]), **kw)
    check(f"the offset path (older records), offset {off}: auto's label, every stroke moved "
          f"by the offset (= a manual spot there) [{a.kind}]",
          old.ok and boxes(old) == shifted(a, *off) and boxes(as_manual) == boxes(old),
          (old.notes, old.preview and old.preview.violations))

# ===================================================== no room anywhere
print("== no room anywhere: refused, saying why, in three lines")
lab = L.plan_label(GS, dict(GL, side="auto"), mode="black", op=None, region=nowhere)
lines = L.describe(lab, "black")
check("a 40 mm disc under a 28 mm marker: not built, a preview, the reason in plain words",
      lab.kind == "none" and lab.preview is not None and "no room" in lab.reason
      and "outside the detector's clear zone" in lab.reason, (lab.reason, lab.notes))
check("... three lines: the error first, where it is shown (with what it breaks), what to do",
      len(lines) == 3 and [lv for lv, _t in lines] == [L.ERROR, L.WARN, L.WARN]
      and "not built" in lines[0][1] and "Shown in orange" in lines[1][1]
      and "Build anyway" in lines[2][1] and not any("label:" in t for _l, t in lines), lines)
check("... the refusal note is not said twice", sum("no room" in t for _l, t in lines) == 1,
      lines)
good = L.describe(L.plan_label(GS, GL, **GP), "black")
check("a good label: one line of result, one grey detail",
      [lv for lv, _t in good] == [L.OK, L.NOTE] and "'#0'" in good[0][1], good)

# ===================================================== ArUco IDs copies
print("== ArUco IDs: copies print their own id at a manual spot")
plate = [circle(0.0, 0.0, 60.0)]
SPOT = (8.0, -27.0)
tpl = L.plan_label(GS, dict(GL, position="manual", x_mm=SPOT[0], y_mm=SPOT[1]), key="top2",
                   mode="black", op=None, region=plate)
rec = json.loads(json.dumps(tpl.to_dict()))
check("the template: built at the manual spot, sized for every copy's id ('#00')",
      tpl.ok and close(L.position_of(tpl), SPOT, 1e-6)
      and tpl.slots[0].rect[2] - tpl.slots[0].rect[0]
      >= L.line_width("#00", L.metrics(tpl.cap)) - 1e-9, tpl.notes)
for mid in (7, 23, 49):
    cs = M.TagSpec(marker_id=mid, marker_length_m=GS.marker_length_m)
    cp = L.relabel(rec, cs, name="Holder:2")
    reg = L.copy_regions(rec, cs, name="Holder:2", key="top2")
    check(f"relabel #{mid}: its own text in the template's slot, centred on the manual spot, "
          "the template's cap; copy_regions the same",
          cp.ok and cp.texts() == [f"#{mid}"] and close(L._centre_of(cp), SPOT, 1e-6)
          and close(cp.cap, tpl.cap) and reg["on"] and reg["texts"] == cp.texts()
          and reg["slots"] == [tuple(sl.rect) for sl in cp.slots] and not L.check_label(cs, cp),
          (cp.texts(), cp.notes))
tight = L.plan_label(GS, dict(GL, position="manual", x_mm=zx + 1.0, y_mm=zy), key="top2", **GP)
cp = L.relabel(tight.to_dict(), M.TagSpec(marker_id=23, marker_length_m=GS.marker_length_m))
check("Zach's tight spot holds '#0' only: a copy numbered #23 says it does not fit (never "
      "silently)", tight.ok and not cp.parts and any("'#23' does not fit" in n for n in cp.notes),
      cp.notes)
tagdef = M.TagDef(key="top2", component="Aruco", spec=GS)
occ = [M.OccurrenceRef(f"Holder:{k}", "Holder", [1, 0, 0, 10 * k, 0, 1, 0, 0, 0, 0, 1, 0,
                                                 0, 0, 0, 1]) for k in (1, 2, 3)]
occ += [M.OccurrenceRef(f"Holder:{k}+Aruco:1", "Aruco", [1, 0, 0, 10 * k, 0, 1, 0, 0, 0, 0, 1,
                                                         0, 0, 0, 0, 1]) for k in (1, 2, 3)]
_planned, res = M.plan_serials([tagdef], [], occ, "Rig")
got = [(i.spec.marker_id, L.label_for_instance(rec, i)) for i in res.instances]
check("label_for_instance over a batch: every copy at the manual spot, its own id",
      len(got) >= 2 and all(lb.ok and close(L._centre_of(lb), SPOT, 1e-6)
                            and lb.texts() == [f"#{mid}"] for mid, lb in got),
      [(mid, lb.texts()) for mid, lb in got])

# ===================================================== the far search
print("== the far search")
narrow = [[(-25, -80), (25, -80), (25, 25), (-25, 25)]]
block = [[(-30.0, -60.0), (30.0, -60.0), (30.0, -24.0), (-30.0, -24.0)]]
t0 = time.perf_counter()
lab = L.plan_label(SINGLE, {"rule": 2, "on": True, "place": "white", "side": "below", "nozzle_mm": 0.45},
                   mode="black", op=None, region=narrow, keepouts=block)
dt = (time.perf_counter() - t0) * 1000.0
check(f"nothing within {L.REACH:g} modules: further out, the first spot past the keep-out "
      f"({dt:.0f} ms)", lab.ok and lab.parts[0].rect[3] < -60.0 and lab.parts[0].rect[3] > -66.0
      and dt < 1000.0, lab.parts and lab.parts[0].rect)
big = [[(-400, -400), (400, -400), (400, 400), (-400, 400)]]
wall = [[(-500.0, -390.0), (500.0, -390.0), (500.0, -21.0), (-500.0, -21.0)]]
t0 = time.perf_counter()
lab = L.plan_label(SINGLE, {"rule": 2, "on": True, "place": "white", "side": "below", "nozzle_mm": 0.45},
                   mode="black", op=None, region=big, keepouts=wall)
dt = (time.perf_counter() - t0) * 1000.0
check(f"an 800 mm face, the only room at its far edge: found, in bounded time ({dt:.0f} ms)",
      lab.ok and lab.parts[0].rect[3] < -390.0 and dt < 2000.0,
      (lab.notes, lab.parts and lab.parts[0].rect))

print()
print(f"{PASS} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
