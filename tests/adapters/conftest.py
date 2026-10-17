"""The adapters group: the recording stand-in for adsk is installed before
anything imports aruco_studio.adapters.fusion, and reset for every test."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import fake_adsk  # noqa: E402

fake_adsk.install()


@pytest.fixture(autouse=True)
def fresh_fusion():
    """A fresh application, design and log; the adapter's state cleared."""
    if "adsk" not in sys.modules or not getattr(sys.modules["adsk"], "FAKE", False):
        fake_adsk.install()
    app = fake_adsk.reset()
    from aruco_studio.adapters.fusion import feature, joint_origin, restructure, sync
    feature.STATE.definition = None
    feature.STATE.handlers.clear()
    feature.STATE.compute_log.clear()
    feature.STATE.restructuring = False
    restructure.FAIL_AT = None
    joint_origin._MADE.clear()
    sync.STATE.pending.clear()
    yield app
