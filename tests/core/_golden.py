"""Load a golden and compare a replay with it (exact: ints, strings, floats)."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

GOLDENS = Path(__file__).resolve().parents[2] / "goldens"


@lru_cache(maxsize=None)
def load(name: str) -> dict:
    return json.loads((GOLDENS / f"{name}.json").read_text(encoding="utf-8"))


def diff(want, got, path="", tol=0.0):
    """The first place two JSON values differ, or "" (floats within `tol`,
    0 = exactly)."""
    if isinstance(want, dict) and isinstance(got, dict):
        for k in sorted(set(want) | set(got), key=str):
            if k not in want or k not in got:
                return f"{path}.{k}: only in {'golden' if k in want else 'replay'}"
            d = diff(want[k], got[k], f"{path}.{k}", tol)
            if d:
                return d
        return ""
    if isinstance(want, list) and isinstance(got, list):
        if len(want) != len(got):
            return f"{path}: {len(want)} items in the golden, {len(got)} in the replay"
        for i, (a, b) in enumerate(zip(want, got)):
            d = diff(a, b, f"{path}[{i}]", tol)
            if d:
                return d
        return ""
    if isinstance(want, float) or isinstance(got, float):
        if isinstance(want, bool) or isinstance(got, bool):
            return "" if want == got else f"{path}: {want!r} vs {got!r}"
        try:
            ok = (want == got) if tol == 0 else abs(float(want) - float(got)) <= tol
        except (TypeError, ValueError):
            ok = False
        return "" if ok else f"{path}: golden {want!r}, replay {got!r}"
    return "" if (want == got and type(want) is type(got)) else f"{path}: golden {want!r}, replay {got!r}"


def ids(cases, key=None):
    return [f"{i:04d}" + (f"-{key(c)}" if key else "") for i, c in enumerate(cases)]
