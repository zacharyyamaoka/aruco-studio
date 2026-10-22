"""Which OpenCV a script's Verify runs: ONE per run, the newest installed
unless you choose another (Zach, 2026-10-21: "Let's only run one, but you can
choose, and by default it should be the most recent one"; docs/peps/0003,
decision 3).

OpenCV is one per Python (cv2 is a compiled module), so a choice is an
interpreter: this one, the repo's .venv (requirements.txt: 5.0) and the
CPythons beside it (.venv-cv411, tools/requirements-browser-opencv.txt: the
browser's 4.11), in this checkout and, from a lane's worktree, in the main
checkout too. `installed()` asks each which OpenCV it has; `choose(None)` is
the newest, `choose("4.11")` the one whose version starts so, and
`choose("/path/to/python")` that Python's. A script runs the choice itself
when it is this Python's OpenCV (`is_here`), else in that Python
(`run_in`): web_verify.range_table and its command line, docs/build_guides.py.

WHY versions, never "the worse of two": two OpenCVs draw the same view
differently (warpPerspective, warpAffine, GaussianBlur) and disagree near the
limits, so every result names the one that made it and a run uses one.

Standard library only (no cv2 import here unless this Python is asked for
its own version: the choice may be another Python's).
"""
from __future__ import annotations

import functools
import importlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_PROBE = "import json, cv2\nprint(json.dumps(cv2.__version__))"


def version_key(v: str) -> tuple:
    """"4.11.0" -> (4, 11, 0): the newest compares largest (a part's trailing letters ignored)."""
    out = []
    for part in str(v).split("."):
        digits = "".join(ch for ch in part if ch.isdigit()) if part[:1].isdigit() else ""
        out.append(int(digits[:9]) if digits else 0)
    return tuple(out)


def short(v: str) -> str:
    """"5.0.0" -> "5.0" (what the pages and the UI print)."""
    return ".".join(str(v).split(".")[:2])


def _checkouts(root: Path) -> list:
    """This checkout and, when it is a lane's worktree, the main checkout
    (worktrees symlink .venv only; .venv-cv411 lives beside the main one)."""
    out = [root]
    try:
        common = subprocess.run(["git", "-C", str(root), "rev-parse", "--path-format=absolute", "--git-common-dir"],
                                capture_output=True, text=True, timeout=20).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        common = ""
    if common:
        main = Path(common).parent
        if main.resolve() != root.resolve():
            out.append(main)
    return out


def _prefix_of(python: str) -> str:
    """A venv's python's environment (its prefix): what tells venvs apart (they share a base binary)."""
    return os.path.realpath(str(Path(python).parent.parent))


def candidates(root: Path = ROOT) -> list:
    """The Pythons that may have an OpenCV: every .venv*/bin/python (or
    Scripts\\python.exe) of this checkout and the main one, then this Python
    when it is none of them. WHY the repo's first: its venvs carry the pinned
    builds (requirements.txt; .venv-cv411 is byte for byte the browser's), so
    a tie on the version goes to them, not to a system OpenCV of that number."""
    seen, out = set(), []

    def add(python: str, prefix: str) -> None:
        key = os.path.realpath(prefix)
        if key not in seen and os.path.isfile(python):
            seen.add(key)
            out.append(python)

    for checkout in _checkouts(Path(root)):
        for pattern in (".venv*/bin/python", ".venv*/Scripts/python.exe"):
            for python in sorted(checkout.glob(pattern)):
                add(str(python), str(python.parent.parent))
    add(sys.executable, sys.prefix)
    return out


def here_version():
    """This Python's OpenCV (cv2.__version__), or None when it has none."""
    if "cv2" in sys.modules:
        return sys.modules["cv2"].__version__
    if importlib.util.find_spec("cv2") is None:
        return None
    try:
        import cv2
    except ImportError:
        return None
    return cv2.__version__


def _is_this_python(python: str) -> bool:
    return _prefix_of(python) == os.path.realpath(sys.prefix)


@functools.lru_cache(maxsize=None)
def version_of(python: str):
    """The OpenCV a Python has (cv2.__version__, e.g. "4.11.0"), or None."""
    if _is_this_python(python):
        return here_version()
    try:
        p = subprocess.run([python, "-c", _PROBE], capture_output=True, text=True, timeout=120,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    except (OSError, subprocess.SubprocessError):
        return None
    if p.returncode:
        return None
    try:
        return str(json.loads(p.stdout.strip().splitlines()[-1]))
    except (ValueError, IndexError):
        return None


def installed(root: Path = ROOT) -> list:
    """Every OpenCV a Python here has, newest first: [{opencv, python}], one
    per version (the repo's venvs first: candidates)."""
    out, seen = [], set()
    for python in candidates(root):
        v = version_of(python)
        if v and v not in seen:
            seen.add(v)
            out.append({"opencv": v, "python": python})
    return sorted(out, key=lambda c: version_key(c["opencv"]), reverse=True)


def _words(found: list) -> str:
    return ", ".join(f"{c['opencv']} ({c['python']})" for c in found) or "none"


def choose(want=None, root: Path = ROOT) -> dict:
    """The OpenCV a run uses: {opencv, python}. `want` None: the newest
    installed; a version ("4.11", "4.11.0", "5"): the installed one whose
    version starts with those parts; a path to a Python: that Python's.
    Refused in words when there is no such OpenCV."""
    if want is not None and (os.sep in str(want) or str(want).startswith(".") or os.path.isfile(str(want))):
        python = str(want)
        if not os.path.isfile(python):
            raise ValueError(f"--opencv {want}: no such Python")
        v = version_of(python)
        if not v:
            raise ValueError(f"--opencv {want}: that Python has no OpenCV (import cv2 failed)")
        return {"opencv": v, "python": python}
    found = installed(root)
    if not found:
        raise ValueError("no Python here has OpenCV: make the repo's .venv (README.md, requirements.txt)")
    if want is None or str(want).strip() == "":
        return dict(found[0])
    parts = str(want).strip().lstrip("v").split(".")
    hits = [c for c in found if c["opencv"].split(".")[:len(parts)] == parts]
    if not hits:
        raise ValueError(f"--opencv {want}: not installed here; installed: {_words(found)} "
                         "(the browser's 4.11: tools/requirements-browser-opencv.txt)")
    return dict(hits[0])


def is_here(choice: dict) -> bool:
    """The choice is this Python (its environment): run it here, else in that Python."""
    return _is_this_python(choice["python"])


def run_in(choice: dict, args: list, stdin: str = "", live: bool = False) -> str:
    """Run `python args...` in the chosen Python with this checkout's code
    (PYTHONPATH); its stdout, or RuntimeError. `live`: its stderr (a long
    run's progress) goes straight through; else it is kept for the error."""
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([choice["python"], *args], input=stdin, stdout=subprocess.PIPE,
                       stderr=None if live else subprocess.PIPE, text=True, cwd=str(ROOT), env=env)
    if p.returncode:
        why = "its output above" if live else (p.stderr or "").strip()[-1200:]
        raise RuntimeError(f"OpenCV {choice['opencv']} ({choice['python']}) failed: {why}")
    return p.stdout


_CALL = ("import importlib, json, sys\na = json.load(sys.stdin)\n"
         "out = getattr(importlib.import_module(a['module']), a['fn'])(*a['args'], **a['kwargs'])\n"
         "sys.stdout.write(json.dumps(out))")


def call(choice: dict, module: str, fn: str, *args, **kwargs):
    """module.fn(*args, **kwargs) on the chosen OpenCV: here when it is this
    Python, else in its Python (JSON in, JSON out)."""
    if is_here(choice):
        return getattr(importlib.import_module(module), fn)(*args, **kwargs)
    out = run_in(choice, ["-c", _CALL], json.dumps({"module": module, "fn": fn, "args": list(args), "kwargs": kwargs}))
    return json.loads(out)


def main(argv=None) -> int:
    """python -m aruco_studio.opencv_choice [--opencv X]: the OpenCVs installed here, and which a run would use."""
    import argparse
    ap = argparse.ArgumentParser(prog="python -m aruco_studio.opencv_choice", description=main.__doc__)
    ap.add_argument("--opencv", help="a version (5.0, 4.11) or a Python; default: the newest installed")
    a = ap.parse_args(argv)
    found = installed()
    for c in found:
        print(f"OpenCV {c['opencv']:10s} {c['python']}")
    try:
        c = choose(a.opencv)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1
    print(f"a run uses OpenCV {c['opencv']} ({c['python']})" + (" -- this Python" if is_here(c) else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
