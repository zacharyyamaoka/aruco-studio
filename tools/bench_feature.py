"""How long one CAD feature takes to compute in CPython: the CPython host of
web/scripts/bench-feature.mjs (the Vibe Tracks KPI feature_compute_ms).

    echo '{"call": "plan", "payload": {...}, "runs": 30, "budget_s": 8}' | .venv/bin/python tools/bench_feature.py

One case per process, so its first call is a true cold one: the import of
aruco_studio.web_api is timed (startup_ms), then the first call (cold_ms),
then up to `runs` more calls of the same request (warm_ms), stopping early
once `budget_s` is spent and at least MIN_WARM ran. web_api keeps no cache,
so a repeat of one request costs what a drag step costs. Prints one JSON
object; a request the core refuses is still timed and says so in `error`.
"""
from __future__ import annotations

import json
import sys
import time

MIN_WARM = 10


def main() -> int:
    t0 = time.perf_counter()
    case = json.load(sys.stdin)
    t1 = time.perf_counter()
    from aruco_studio import web_api
    startup_ms = (time.perf_counter() - t1) * 1000
    text = json.dumps(case["payload"])
    runs, budget_s = int(case.get("runs", 30)), float(case.get("budget_s", 8))

    t = time.perf_counter()
    out = web_api.call(case["call"], text)
    cold_ms = (time.perf_counter() - t) * 1000
    warm: list[float] = []
    spent = time.perf_counter()
    while len(warm) < runs:
        t = time.perf_counter()
        web_api.call(case["call"], text)
        warm.append((time.perf_counter() - t) * 1000)
        if len(warm) >= MIN_WARM and time.perf_counter() - spent > budget_s:
            break
    answer = json.loads(out)
    json.dump({"host": "cpython", "runtime": "CPython " + sys.version.split()[0], "startup_ms": startup_ms,
               "cold_ms": cold_ms, "warm_ms": warm, "bytes": len(out),
               "error": answer.get("error"), "wall_ms": (time.perf_counter() - t0) * 1000}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
