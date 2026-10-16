"""Turn a ported REF suite into pytest tests, one per REF section.

A REF suite is a plain script: `print("== a header")`, then `check(...)`
lines. tools/ref_sections.py listed every header of the suite at the pinned
commit and counted how many checks REF's own run passed under each one
(tests/ref_sections.json). Here the ported copy (tests/core/ref_suites/)
runs once per module in its own process, and each section becomes

    test_<suite>__s<NN>__<words of the header>    @pytest.mark.ref(suite, header)

which passes when that section had no FAIL and passed exactly as many
checks as REF's did. A section REF parked for M2 (it ran evaluate() on a
stand-in adsk) is skipped with the reason. Two more tests per suite: the
copy exits 0, and its total equals REF's.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SECTIONS = json.loads((ROOT / "tests" / "ref_sections.json").read_text(encoding="utf-8"))


def suite_info(rel):
    for s in SECTIONS["suites"]:
        if s["suite"] == rel:
            return s
    raise KeyError(rel)


def slug(text, n=60):
    s = re.sub(r"[^a-z0-9]+", "_", text.lower().replace("{", "").replace("}", "")).strip("_")
    return (s[:n].rstrip("_")) or "section"


def run_copy(copy, rows, entry):
    headers = [[r["key"], r["regex"]] for r in rows]
    with tempfile.TemporaryDirectory(prefix="aruco_ref_copy_") as tmp:
        env = dict(os.environ)
        env.update({"PYTHONDONTWRITEBYTECODE": "1", "USERPROFILE": tmp, "HOME": tmp,
                    "ARUCO_STUDIO_HOME": os.path.join(tmp, "studio"), "PYTHONIOENCODING": "utf-8"})
        env.pop("PYTHONPATH", None)
        p = subprocess.run([sys.executable, "-X", "utf8", str(HERE / "_ref_child.py"), str(copy),
                            json.dumps(headers), json.dumps(entry or [])],
                           cwd=tmp, env=env, capture_output=True, timeout=900)
    out = p.stdout.decode("utf-8", "replace").strip().splitlines()
    if not out:
        raise RuntimeError(f"{copy.name}: no result ({p.returncode}): "
                           + p.stderr.decode("utf-8", "replace")[-3000:])
    return json.loads(out[-1])


def make_tests(ns, rel, *, short, expected=None, parked=(), not_ported=None):
    """Fill module namespace `ns` with one test per section of REF suite `rel`.

    expected: {section key: ok count} for a suite REF's run could not count
    (it loads a stand-in adsk); parked: section keys parked for M2;
    not_ported: {section key: why} sections whose checks need Fusion."""
    info = suite_info(rel)
    copy = HERE / "ref_suites" / ("ref_" + Path(rel).stem[5:] + ".py")
    rows = [r for r in info["sections"] if not (info.get("entry") and r["func"] not in info["entry"])]
    ref_counts = info.get("ref_counts") or {}
    not_ported = not_ported or {}
    expected = expected or {}

    @pytest.fixture(scope="module")
    def ref_run():
        return run_copy(copy, rows, info.get("entry"))

    ns["ref_run"] = ref_run

    def section_test(row):
        key = row["key"]

        @pytest.mark.ref(rel, row["text"])
        def test(ref_run):
            if key in not_ported:
                pytest.skip(not_ported[key])
            got = ref_run["counts"].get(key, {"ok": 0, "fail": 0, "skip": 0, "fails": []})
            assert got["fail"] == 0, "\n".join(got["fails"])
            if key in parked:
                assert got["ok"] == 0
                pytest.skip("parked for M2: REF ran aruco_feature.evaluate() here "
                            "(plan/plan.py plan_tag, tests/plan/test_golden_evaluate.py)")
            want = expected.get(key, (ref_counts.get(key) or {}).get("ok"))
            assert want is not None, f"no REF count for {key!r}"
            assert got["ok"] == want, f"{got['ok']} checks passed, REF passed {want}"
        test.__doc__ = f"REF: {rel} section {row['text']!r} (line {row['line']})"
        return test

    for i, row in enumerate(rows, 1):
        name = f"test_{short}__s{i:02d}__{slug(row['text'])}"
        ns[name] = section_test(row)

    @pytest.mark.ref(rel, "(the whole suite)")
    def test_whole(ref_run):
        assert ref_run["exit"] in (0, None), ref_run["exit"]
        assert ref_run["FAIL"] == 0
        want = info.get("ref_pass")
        if want is not None and not info.get("entry"):
            assert ref_run["PASS"] == want, (ref_run["PASS"], want)
        elif info.get("entry"):
            got = sum(c["ok"] for c in ref_run["counts"].values())
            assert got == want, (got, want)
        pre = "(before the first section)"
        if pre in ref_run["counts"]:
            assert ref_run["counts"][pre]["ok"] == (ref_counts.get(pre) or {}).get("ok", 0)

    ns[f"test_{short}__whole_suite"] = test_whole
