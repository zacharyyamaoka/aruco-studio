"""Which OpenCV a script runs (aruco_studio/opencv_choice.py; docs/peps/0003
decision 3, Zach 2026-10-21: "Let's only run one, but you can choose, and by
default it should be the most recent one"): versions compare as numbers, the
default is the newest installed, a choice is a version prefix or a Python,
one that is not installed is refused in words, and a call runs in the
chosen Python (here when it is this one)."""
from __future__ import annotations

import sys

import pytest

from aruco_studio import opencv_choice as OC


def test_versions_compare_as_numbers():
    assert OC.version_key("4.11.0") > OC.version_key("4.9.0")
    assert OC.version_key("5.0.0") > OC.version_key("4.11.0")
    assert OC.version_key("4.11.0-pre") == OC.version_key("4.11.0")
    assert OC.short("4.11.0") == "4.11" and OC.short("5.0.0") == "5.0"


def test_the_default_is_the_newest_whatever_the_order_found(monkeypatch):
    """The ruler can fail: the newest wins even found last, ties go to the first found."""
    found = {"/a/.venv-old/bin/python": "4.11.0", "/b/.venv/bin/python": "4.9.0", "/c/.venv-new/bin/python": "5.0.0",
             "/d/.venv-dup/bin/python": "5.0.0", "/e/.venv-none/bin/python": None}
    monkeypatch.setattr(OC, "candidates", lambda root=OC.ROOT: list(found))
    monkeypatch.setattr(OC, "version_of", lambda python: found[python])
    assert [c["opencv"] for c in OC.installed()] == ["5.0.0", "4.11.0", "4.9.0"]
    assert OC.choose() == {"opencv": "5.0.0", "python": "/c/.venv-new/bin/python"}
    assert OC.choose("4")["opencv"] == "4.11.0"            # a prefix: the newest it matches
    assert OC.choose("4.9")["python"] == "/b/.venv/bin/python"
    with pytest.raises(ValueError, match=r"--opencv 4\.10: not installed here; installed: 5\.0\.0"):
        OC.choose("4.10")
    monkeypatch.setattr(OC, "candidates", lambda root=OC.ROOT: [])
    with pytest.raises(ValueError, match="no Python here has OpenCV"):
        OC.choose()


def test_this_python_is_a_choice_and_runs_here():
    here = OC.here_version()
    if here is None:
        pytest.skip("this Python has no OpenCV")
    c = OC.choose(sys.executable)
    assert c == {"opencv": here, "python": sys.executable} and OC.is_here(c)
    assert here in [x["opencv"] for x in OC.installed()]
    assert OC.call(c, "aruco_studio.opencv_choice", "here_version") == here
    with pytest.raises(ValueError, match="no such Python"):
        OC.choose("/no/such/python")


def test_another_opencv_runs_in_its_own_python():
    others = [c for c in OC.installed() if not OC.is_here(c)]
    if not others:
        pytest.skip("one OpenCV here: nothing to run elsewhere (tools/requirements-browser-opencv.txt makes a second)")
    for c in others:
        assert OC.call(c, "aruco_studio.opencv_choice", "here_version") == c["opencv"]
