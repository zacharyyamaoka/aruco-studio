"""adapters/fusion/features.py: the plain build (a sketch and an extrude per
layer), on the stand-in.

* every evaluate() golden case: each part, built as New body / Join / Cut
  extrudes of its layers' sketches, probes as the plan's own 2D evaluation
  says (the stand-in replays the extrudes in timeline order);
* the call sequence for each type (single, grid, ChArUco) on a plate is
  kept in tests/adapters/sequences/features_<type>.txt (ARUCO_UPDATE_SEQUENCES=1
  rewrites it): one sketch per layer, its profiles extruded from z[0] by
  z[1] - z[0], the part's body the only participant of every later step,
  the combines after their part.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

import _cases as C
import fake_adsk as FK
from aruco_studio.adapters import recipe as RC
from aruco_studio.adapters.fusion import feature as FT
from aruco_studio.adapters.fusion import features as FE
from aruco_studio.core import settings as S

SEQ = Path(__file__).resolve().parent / "sequences"
MIN_PROBES = {"legacy": 2000, "matrix": 30000}


@pytest.mark.parametrize("group", C.GROUPS)
def test_every_part_as_extrudes_probes_as_the_plan_says(group):
    bad, probes = [], 0
    for cid, p in C.plans(group):
        if not p.ok:
            continue
        FK.reset()
        comp = FK.design().rootComponent
        rec = RC.recipe(p)
        pf = rec["frames"]["pattern_cm"]
        for part in rec["parts"]:
            body, feats = FE.build_part(comp, comp.xYConstructionPlane, rec, part)
            n_steps = sum(len(s["steps"]) for s in part["solids"])
            if len(feats) != n_steps:
                bad.append((cid, part["role"], "features", len(feats), n_steps))
                continue
            for name, u, v, z in C.probe_points(p.data["layers"], part["role"]):
                want = C.part_has(p.data["layers"], part["role"], u, v, z)
                got = body.contains(RC.to_host(pf, u, v, z))
                probes += 1
                if got != want:
                    bad.append((cid, part["role"], name, round(u, 4), round(v, 4), got, want))
    assert probes > MIN_PROBES[group] and not bad, bad[:6]


TYPES = {"single": {"layout": "single", "dictionary": "DICT_4X4_50", "mode": "both",
                    "op": "join"},
         "grid": {"layout": "grid", "dictionary": "DICT_4X4_50", "mode": "both", "op": "new"},
         "charuco": {"layout": "charuco", "dictionary": "DICT_4X4_50", "mode": "both",
                     "op": "join"}}


@pytest.mark.parametrize("kind", sorted(TYPES))
def test_call_sequence_per_type(kind):
    body_under, face = FK.plate()
    s = dict(S.default_settings(), **TYPES[kind])
    s["has_body"] = True
    plan, _t, base, _k = FT.plan_for(face, s, S.default_numbers("both"), "t1", "", body_under)
    rec = RC.recipe(plan, base[:4], frame_sketch=False)
    FK.LOG.clear()
    bodies, feats = FE.build(face.body.parentComponent, face, rec, body_under)
    seq = FK.summary()
    text = "\n".join(seq) + "\n"
    path = SEQ / f"features_{kind}.txt"
    if os.environ.get("ARUCO_UPDATE_SEQUENCES") == "1" or not path.exists():
        path.write_text(text, encoding="utf-8", newline="\n")
    assert path.read_text(encoding="utf-8") == text
    # one sketch and one extrude per step; every later step joins / cuts its part only
    steps = list(RC.steps(rec))
    assert sum(1 for x in seq if x.startswith("sketches.add")) == len(steps)
    exts = [x for x in seq if x.startswith("extrudeFeatures.add")]
    assert len(exts) == len(steps)
    for x, (part, _s, st) in zip(exts, steps):
        lo, hi = st["z"]
        assert f"{lo / 10:.6g}, {hi / 10:.6g}" in x, (x, st["z"])
    cbs = [x for x in seq if x.startswith("combineFeatures.add")]
    assert len(cbs) == sum(1 for c in rec["combines"] if c["op"] != "new")
    # the pattern is its own body; the cut tools went into their combines
    solids = FK.design().solids()
    assert bodies["pattern"] in solids
    for r in ("pocket", "recess"):
        if r in bodies:
            assert bodies[r] not in solids
