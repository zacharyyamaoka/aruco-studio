"""Verify accuracy for the online Studio (CoreApi.verify / readable): the plan
rendered as a camera would see it, read by OpenCV's own ArUco detector.
Lane "verify" of the 2026-10-18 dispatch implements it (numpy + OpenCV, which
Pyodide loads on the first call). Stub until then."""
from __future__ import annotations


def verify(req: dict, view: dict) -> dict:
    raise NotImplementedError("verify: not built yet")


def readable(req: dict, camera: dict) -> dict:
    raise NotImplementedError("readable: not built yet")
