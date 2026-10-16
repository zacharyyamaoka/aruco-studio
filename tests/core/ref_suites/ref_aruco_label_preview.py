# REF: tests/test_aruco_label_preview.py at c8216ff (cad-exporter), ported by tools/port_ref_suites.py:
# REF's checks verbatim, run against aruco_studio.core. Do not edit by hand.
"""The label is ALWAYS shown (Zach, 2026-10-11): "Its very frustrating with
the label that it doesn't show me the preview if it's not valid... It should
always show me the preview... but it can show a warning type thing... I
should always be able to see the label even if the linter is saying its
going to cause an error."

bam_cad_core.aruco_label, offline:

  * a label that cannot be placed inside the rules (no room, letters under
    the printable cap, no white at all) comes back NOT built (kind "none")
    with a preview: laid out where it was asked for, its violations in
    plain words, with how much ("hangs 1.7 mm off the face")
  * a nudge that breaks a rule is shown where it was nudged (no longer
    "kept where it was placed")
  * Build anyway (settings.build_anyway) builds exactly that preview,
    forced, its warnings kept; copies relabel it with their own id
  * records keep the preview and the warnings; copy_regions warns instead
    of dropping a label silently
  * Zach's GIM43 disc tag (28 mm marker, Black only, a 47.5 mm disc, #id On
    the white Above, nozzle 0.4): since 2026-10-13 (the quiet ring is the
    hard line) it fits above; a 40 mm disc does not -- previewed above, off
    the disc; On the black it fits ("#21" in the bottom row)

tools/mutate_aruco_label.py breaks each of these on purpose and checks this
suite (and the add-in's) turns red.

Run:  python tests/test_aruco_label_preview.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

pass  # REF put its own tree on sys.path here (ported: not needed)

from aruco_studio.core import label as L  # noqa: E402
from aruco_studio.core import markers as M  # noqa: E402

PASS = 0
FAIL = []
S = L.LabelSettings


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


def shift_of(a, b):
    ra, rb = L.ink_rect(a.boxes()), L.ink_rect(b.boxes())
    return (rb[0] - ra[0], rb[1] - ra[1]) if ra and rb else None


def has(vs, *words):
    return any(all(w in v for w in words) for v in vs)


GIM = M.TagSpec(marker_id=0, marker_length_m=0.028)
DISC47 = [circle(0.0, 0.0, 23.75)]                     # Zach's 47.5 mm disc, pattern frame
DISC = [circle(0.0, 0.0, 20.0)]                        # a 40 mm one: no room above
SINGLE = M.TagSpec(marker_id=12, marker_length_m=0.03)
BIG = M.TagSpec(marker_id=12, marker_length_m=0.04)
SMALL = M.TagSpec(marker_id=12, marker_length_m=0.018)
GRID31 = M.TagSpec(marker_id=9, marker_length_m=0.04, layout="grid", rows=1, cols=3,
                   separation_m=0.008)

print("== Zach's GIM43 disc tag: #id On the white, Above, nozzle 0.4")
want = S(on=True, place="white", side="above", nozzle_mm=0.4)
fit = L.plan_label(GIM, want, mode="black", op=None, region=DISC47)
check("P0 on his 47.5 mm disc it fits above now (the quiet ring is the hard line, "
      "2026-10-13): built, outside the clear zone, on the disc",
      fit.ok and fit.side == "above" and not L.check_label(GIM, fit)
      and fit.parts[0].rect[1] >= L.clear_zones(GIM)["hard"][3] - 1e-9
      and not L.label_violations(GIM, fit, loops=DISC47), (fit.notes, fit.violations))
print("== ... a 40 mm disc: no room above")
lab = L.plan_label(GIM, want, mode="black", op=None, region=DISC, slab=(-1.6, -1.0))
pv = lab.preview
check("P1 not built (kind none), the reason kept in the notes",
      lab.kind == "none" and any("no room on the white" in n for n in lab.notes), lab.notes)
check("P1b but a preview: on the white, above, '#0', 2.0 mm letters (the 0.4 nozzle's smallest)",
      pv is not None and pv.kind == "white" and pv.side == "above" and pv.texts() == ["#0"]
      and close(pv.cap, 2.0) and pv.role == "add" and lab.shown is pv, pv and pv.texts())
check("P1c just beyond the detector's clear zone and auto's preferred margin, centred on "
      "the marker", pv is not None and close(pv.parts[0].rect[1], L.clear_zones(GIM)["preferred"][3])
      and close((pv.parts[0].rect[0] + pv.parts[0].rect[2]) / 2.0, 0.0))
check("P1d what is wrong, in plain words with how much: it hangs 1.9 mm off the disc",
      pv is not None and pv.violations == ["hangs 1.9 mm off the face"], pv and pv.violations)
check("P1e kept in the slab it would be built in", pv is not None and pv.slab == (-1.6, -1.0)
      and pv.mode == "black")
forced = L.plan_label(GIM, S(on=True, place="white", side="above", nozzle_mm=0.4,
                             build_anyway=True), mode="black", op=None, region=DISC)
check("P2 Build anyway: built exactly there (forced), the warning kept, not 'ok'",
      forced.kind == "white" and forced.forced and not forced.ok
      and forced.violations == pv.violations and close(shift_of(pv, forced), (0.0, 0.0))
      and any("built anyway" in n for n in forced.notes), forced.violations)
black = L.plan_label(M.TagSpec(marker_id=21, marker_length_m=0.028),
                     S(on=True, place="black", nozzle_mm=0.4), mode="black", op=None, region=DISC)
check("P3 On the black at the 0.4 nozzle it fits: '#21' in the bottom row, 2.3 mm, no warning",
      black.ok and black.texts() == ["#21"] and close(black.cap, 2.3) and not black.violations
      and black.preview is None, (black.texts(), black.cap))

print("== nothing fits inside the rules: shown anyway")
lab = L.plan_label(SINGLE, S(on=True, place="white", cap_mm=2.0), grow=True)
check("P5 typed 2.0 mm letters at the 0.6 nozzle: not built, previewed AT 2.0 mm, 'won't print "
      "cleanly'", lab.kind == "none" and lab.preview is not None and close(lab.preview.cap, 2.0)
      and has(lab.preview.violations, "2.0 mm letters", "0.6 mm nozzle", "won't print cleanly",
              "3.0 mm"), lab.preview and lab.preview.violations)
lab = L.plan_label(SMALL, S(on=True, place="black"), mode="black", op=None,
                   region=[L.rect_loop((-12.0, -12.0, 12.0, 12.0))])
check("P6 an 18 mm marker On the black: previewed in its bottom row at 3.0 mm, taller than the "
      "row allows (1.5 mm)",
      lab.kind == "none" and lab.preview is not None and lab.preview.kind == "black"
      and close(lab.preview.cap, 3.0)
      and has(lab.preview.violations, "taller than the border row allows", "1.5 mm"),
      lab.preview and lab.preview.violations)
lab = L.plan_label(SINGLE, S(on=True, place="white"), mode="black", op=None)
check("P7 On the white with no white at all (Black only, nothing under it): previewed, "
      "'no white to sit on'", lab.kind == "none" and lab.preview is not None
      and has(lab.preview.violations, "no white to sit on"), lab.preview and lab.preview.violations)
lab = L.plan_label(SMALL, S(on=True), mode="black", op=None,
                   region=[L.rect_loop((-12.0, -12.0, 12.0, 12.0))])
pb = L.plan_label(SMALL, S(on=True, place="black"), mode="black", op=None,
                  region=[L.rect_loop((-12.0, -12.0, 12.0, 12.0))]).preview
pw = L.plan_label(SMALL, S(on=True, place="white"), mode="black", op=None,
                  region=[L.rect_loop((-12.0, -12.0, 12.0, 12.0))]).preview
check("P16 Auto with nothing that fits: the preview with fewer problems (here the white)",
      lab.preview is not None and len(lab.preview.violations)
      == min(len(pb.violations), len(pw.violations)) and lab.preview.kind == "white",
      (len(pb.violations), len(pw.violations)))
lab = L.plan_label(GRID31, S(on=True, place="black", nozzle_mm=0.8))
check("P6b a grid at a 0.8 nozzle: every marker's '#id' previewed in its own row",
      lab.kind == "none" and lab.preview is not None
      and lab.preview.texts() == ["#9", "#10", "#11"], lab.preview and lab.preview.texts())

print("== a nudge that breaks a rule: shown where it was nudged")
base = L.plan_label(BIG, S(on=True, place="white", side="below"), mode="black", op=None,
                    region=[circle(0.0, 0.0, 60.0), circle(18.0, -32.0, 3.0, cw=True)])
# the words are the plain-language violation's own (not the refusal note's)
for (dx, dy), words in (((0.0, 6.0), ("inside the detector's clear zone by",)),
                        ((0.0, -40.0), ("hangs", "off the face")),
                        ((18.0, 0.0), ("over a hole in the face",))):
    mv = L.plan_label(BIG, S(on=True, place="white", side="below", offset_x_mm=dx,
                             offset_y_mm=dy), mode="black", op=None,
                      region=[circle(0.0, 0.0, 60.0), circle(18.0, -32.0, 3.0, cw=True)])
    check(f"P8 nudge ({dx:+g}, {dy:+g}): not built, shown exactly there, '{words[0]}'",
          mv.kind == "none" and mv.preview is not None
          and close(shift_of(base, mv.preview), (dx, dy)) and has(mv.preview.violations, *words)
          and any("not built" in n for n in mv.notes),
          (mv.notes, mv.preview and mv.preview.violations))
mv = L.plan_label(BIG, S(on=True, place="white", side="below", offset_y_mm=10.0), mode="black",
                  op=None, region=[circle(0.0, 0.0, 60.0)])
ring = L.grow_rect(L._mm(BIG)[1], L.quiet_ring(BIG) * L._mm(BIG)[0])
r = mv.preview.parts[0].rect if mv.preview else None
want_d = min(r[2] - ring[0], ring[2] - r[0], r[3] - ring[1], ring[3] - r[1]) if r else -1.0
check(f"P8b 'inside the detector's clear zone by X mm': X is the geometry's ({want_d:.1f})",
      mv.preview is not None and want_d > 0
      and has(mv.preview.violations, f"inside the detector's clear zone by {want_d:.1f} mm"),
      (mv.preview and mv.preview.violations, want_d))
cb = L.plan_label(BIG, S(on=True, place="black", content="id_name"), name="Arm")
cn = L.plan_label(BIG, S(on=True, place="black", content="id_name", offset_x_mm=12.0),
                  name="Arm")
check("P10 on the black, a nudge into a corner cell: shown there, 'runs X mm into the corner "
      "cells'", cn.kind == "none" and cn.preview is not None
      and close(shift_of(cb, cn.preview), (12.0, 0.0))
      and has(cn.preview.violations, "into the corner cells"), cn.preview and cn.preview.violations)
sb = L.plan_label(SINGLE, S(on=True, place="white", side="below"), grow=True,
                  bounds=[L.rect_loop((-25.0, -32.0, 25.0, 25.0))])
sn = L.plan_label(SINGLE, S(on=True, place="white", side="below", offset_y_mm=-6.0), grow=True,
                  bounds=[L.rect_loop((-25.0, -32.0, 25.0, 25.0))])
check("P11 a strip nudged off the face: 'the tile would grow X mm off the face'",
      sb.ok and sn.kind == "none" and sn.preview is not None
      and has(sn.preview.violations, "tile would grow", "off the face"),
      (sb.notes, sn.notes, sn.preview and sn.preview.violations))
block = [L.rect_poly((5.0, -34.0, 9.0, -28.0))]
kb = L.plan_label(BIG, S(on=True, place="white", side="below"), mode="black", op=None,
                  region=[circle(0.0, 0.0, 60.0)])
kn = L.plan_label(BIG, S(on=True, place="white", side="below", offset_x_mm=4.0), mode="black",
                  op=None, region=[circle(0.0, 0.0, 60.0)], keepouts=block)
check("P17 a nudge onto a keep-out: 'touches the corner mark or a locating pin'",
      kn.kind == "none" and kn.preview is not None
      and has(kn.preview.violations, "corner mark or a locating pin"),
      (kn.notes, kn.preview and kn.preview.violations))
SQ = [L.rect_loop((-60.0, -60.0, 60.0, 60.0))]
eb = L.plan_label(BIG, S(on=True, place="white", side="below"), mode="black", op=None, region=SQ)
dy_edge = -(60.0 - 1.0) - eb.parts[0].rect[1]         # its lowest stroke 1.0 mm from the edge
en = L.plan_label(BIG, S(on=True, place="white", side="below", offset_y_mm=dy_edge),
                  mode="black", op=None, region=SQ)
check("P18 nudged next to the face's edge: '1.0 mm from the face's edge (it needs 1.7 mm)'",
      eb.ok and en.kind == "none" and en.preview is not None
      and has(en.preview.violations, "1.0 mm from the face's edge", "it needs 1.7 mm"),
      en.preview and en.preview.violations)

print("== every preview says what it breaks; a good label breaks nothing")
cases = [lab for lab in (
    L.plan_label(GIM, want, mode="black", op=None, region=DISC),
    L.plan_label(SINGLE, S(on=True, place="white", cap_mm=2.0), grow=True),
    L.plan_label(SMALL, S(on=True, place="black")),
    L.plan_label(SINGLE, S(on=True, place="white"), mode="black", op=None),
    cn, sn, kn, en)]
check("P4 every refused label has a preview with at least one violation",
      all(c.kind == "none" and c.preview is not None and c.preview.violations and c.preview.parts
          for c in cases), [len(c.preview.violations) if c.preview else None for c in cases])
good = [L.plan_label(BIG, S(on=True)), L.plan_label(SINGLE, S(on=True), grow=True), black, cb, kb]
check("P4b every good label: ok, no violations, no preview; label_violations finds nothing "
      "on a placed one", all(g.ok and not g.violations and g.preview is None for g in good)
      and not L.label_violations(BIG, good[0])
      and not L.label_violations(SINGLE, good[1], strip=True),
      [(g.ok, g.violations) for g in good])

print("== records, copies, determinism")
rec = L.plan_label(GIM, want, mode="black", op=None, region=DISC).to_dict()
back = L.from_dict(json.loads(json.dumps(rec)))
check("P12 the record keeps the preview and its warning (JSON round trip)",
      rec["kind"] == "none" and (rec.get("preview") or {}).get("violations")
      and back.preview is not None
      and back.preview.violations == pv.violations
      and L.same(rec.get("preview"), pv.to_dict()))
frec = forced.to_dict()
fback = L.from_dict(json.loads(json.dumps(frec)))
check("P12b a forced label's record keeps 'forced' and its violations",
      frec.get("forced") is True and fback.forced and fback.violations == forced.violations)
cp = L.relabel(frec, M.TagSpec(marker_id=37, marker_length_m=0.028), name="Disc:2")
check("P13 a copy of a label built anyway: its own id, forced, the same warnings",
      cp.kind == "white" and cp.forced and cp.texts() == ["#37"]
      and cp.violations == forced.violations, (cp.texts(), cp.violations))
w_not = L.copy_regions(rec, GIM)["warning"]
w_any = L.copy_regions(frec, M.TagSpec(marker_id=37, marker_length_m=0.028))["warning"]
w_ok = L.copy_regions(black.to_dict(), M.TagSpec(marker_id=5, marker_length_m=0.028))["warning"]
check("P14 copies are never silent: 'not built: <why>', 'built anyway although: <why>', '' when fine",
      w_not.startswith("the label is not built") and "off the face" in w_not
      and w_any.startswith("built anyway") and "off the face" in w_any and w_ok == "",
      (w_not, w_any, w_ok))
a = json.dumps(L.plan_label(GIM, want, mode="black", op=None, region=DISC).to_dict(),
               sort_keys=True)
b = json.dumps(L.plan_label(GIM, want, mode="black", op=None, region=DISC).to_dict(),
               sort_keys=True)
check("P15 deterministic, byte for byte", a == b)
check("P19 settings: build_anyway round-trips, off by default",
      S().build_anyway is False and S.from_dict(S(build_anyway=True).to_dict()).build_anyway
      and not S.from_dict({"on": True}).build_anyway)

print()
print(f"{PASS} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
