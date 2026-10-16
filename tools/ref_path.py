"""Where REF is, and how to read it without writing anything.

REF = the cad-exporter worktree that holds the Fusion add-in. It is READ ONLY:
other agents commit there and Zach's Fusion loads its add-in from it. Every
read here goes through the pinned commit, so a mid-edit file never leaks in.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

REF = Path(os.environ.get(
    "ARUCO_STUDIO_REF",
    r"C:\Users\BAM\Documents\cad-exporter\.claude\worktrees\aruco-fusion-plugin-0e9bcb"))
REF_COMMIT = "c8216ff"
ROOT = Path(__file__).resolve().parents[1]


def git(*args: str) -> str:
    """`git -C REF ...` (read-only commands only)."""
    return subprocess.run(["git", "-C", str(REF), *args], capture_output=True,
                          check=True).stdout.decode("utf-8")


def show(path: str, commit: str = REF_COMMIT) -> bytes:
    """A file's bytes at the pinned commit."""
    return subprocess.run(["git", "-C", str(REF), "show", f"{commit}:{path}"],
                          capture_output=True, check=True).stdout


def sha256_at(path: str, commit: str = REF_COMMIT) -> str:
    return hashlib.sha256(show(path, commit)).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def same_as_pinned(rel: str) -> bool:
    """True when REF's working-tree file equals the pinned commit's blob, so
    importing it from the working tree runs exactly the pinned code."""
    p = REF / rel
    if not p.exists():
        return False
    # a checkout may hold CRLF where the blob has LF; git calls that "no change"
    return p.read_bytes().replace(b"\r\n", b"\n") == show(rel).replace(b"\r\n", b"\n")


def status() -> str:
    """`git status --porcelain` of REF: compared before and after every run."""
    return git("status", "--porcelain")
