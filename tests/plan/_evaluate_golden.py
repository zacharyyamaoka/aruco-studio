"""Shared by the evaluate() replays: the goldens, the outputs in the shape
tools/make_evaluate_goldens.py recorded them, and an exact diff."""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

from aruco_studio.core import edits as E
from aruco_studio.core import settings as S
from aruco_studio.plan import evaluate as EV
from aruco_studio.plan import record as R
from aruco_studio.plan.spec import TagSpec
from aruco_studio.plan.target import Target

ROOT = Path(__file__).resolve().parents[2]
GOLD = ROOT / "goldens" / "evaluate"


@lru_cache(maxsize=None)
def load(name):
    return json.loads((GOLD / f"{name}.json").read_text(encoding="utf-8"))


def cases(name):
    return load(name)["cases"]


def norm(x):
    return json.loads(json.dumps(x))


def plan_dict(p):
    L = p.layers
    return {"mode": p.mode, "op": p.op, "parts": list(p.parts), "pocket": p.pocket,
            "recess": [[w, list(s)] for w, s in p.recess], "pin": p.pin, "notes": list(p.notes),
            "structure": list(p.structure),
            "layers": {"white": L.white, "black": L.black, "pattern": L.pattern,
                       "surface": L.surface, "depth": L.depth, "raise": L.raise_,
                       "recess": L.recess, "gap": L.gap}}


def lay_dict(lay):
    return {"kind": lay.kind, "marker_m": lay.marker_m, "square_m": lay.square_m,
            "cols": lay.cols, "rows": lay.rows, "separation_m": lay.separation_m,
            "margins_m": list(lay.margins_m), "ok": lay.ok, "notes": list(lay.notes),
            "badges": list(lay.badges), "fill": lay.fill, "dictionary": lay.dictionary,
            "quiet_modules": lay.quiet_modules}


def trim_dict(tp):
    if tp is None:
        return None
    return {"axes": tp.axes, "margin": tp.margin, "outline": list(tp.outline),
            "body": list(tp.body), "keep": list(tp.keep), "pad": tp.pad, "cut": dict(tp.cut),
            "refusals": list(tp.refusals), "notes": list(tp.notes), "forced": tp.forced,
            "face": list(tp.face) if tp.face is not None else None,
            "face_share": tp.face_share, "body_share": tp.body_share,
            "removed_mm3": tp.removed_mm3, "body_mm3": tp.body_mm3, "holes": list(tp.holes),
            "z": list(tp.z) if tp.z is not None else None, "column": list(tp.column())}


def ev_dict(ev):
    lab = ev.get("label")
    mark = ev.get("mark")
    return {"spec": ev["spec"].to_dict(), "tag": ev["tag"], "tile": ev["tile"],
            "base": ev["base"], "notes": list(ev["notes"]), "lift_cm": ev["lift_cm"],
            "plan": plan_dict(ev["plan"]), "pins": ev["pins"], "pin_frame": ev["pin_frame"],
            "turn": ev["turn"], "x_fit": ev["x_fit"], "pin_tol": ev["pin_tol"],
            "mode": ev["mode"], "mark": mark.to_dict(6) if mark is not None else None,
            "label": lab.to_dict(6) if lab is not None else None,
            "label_white": ev.get("label_white"),
            "node_warning": R.node_warning(ev), "record_mark": R.mark_record(ev),
            "record_label": R.label_record(ev)}


def outputs(ev, s, n, key):
    """What the maker recorded, from this code's evaluate()."""
    out = {"ev": ev_dict(ev), "layout": lay_dict(ev["layout"]), "trim": trim_dict(ev.get("trim"))}
    s2, n2 = E.settle(s, n, ev)
    out["settled"] = {"settings": s2, "numbers": n2}
    out["optical"] = R.optical_of_ev(ev, key or "tg")
    out["digest"] = R.ev_digest(ev)
    return norm(out)


def run_ref_inputs(case):
    """evaluate() on the exact settings / numbers REF's evaluate() got."""
    spec = TagSpec.from_dict(case["in"])
    try:
        ev = EV.evaluate(spec.target, dict(case["s"]), dict(case["n"]), base=case["base"],
                         name=spec.name)
        return outputs(ev, case["s"], case["n"], case["s"].get("key")), ev
    except Exception as exc:                       # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}, None


def diff(a, b, path="", tol=0.0):
    """The first place two results differ ('' = the same). tol 0: exact."""
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            d = diff(a.get(k), b.get(k), f"{path}.{k}", tol)
            if d:
                return d
        return ""
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            return f"{path}: {len(a)} items vs {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            d = diff(x, y, f"{path}[{i}]", tol)
            if d:
                return d
        return ""
    if (isinstance(a, float) or isinstance(b, float)) and isinstance(a, (int, float)) \
            and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        if a == b or (tol and abs(a - b) <= tol):
            return ""
        return f"{path}: {a!r} vs {b!r}"
    return "" if a == b else f"{path}: {a!r} vs {b!r}"


def r9(v, nd=9):
    """REF's legacy goldens round every float to 9 decimals (their _r)."""
    if isinstance(v, float):
        return round(v, nd)
    if isinstance(v, (list, tuple)):
        return [r9(c, nd) for c in v]
    if isinstance(v, dict):
        return {str(k): r9(c, nd) for k, c in v.items()}
    return v
