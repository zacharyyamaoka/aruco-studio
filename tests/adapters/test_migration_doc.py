"""docs/FUSION_ADAPTER.md covers the inventory (PLAN M4.7).

* every (F) bullet of docs/inventory/addin.md's detailed list -- one row
  per file per bullet, keyed by the file and the bullet's first function --
  has a row in the (F) table naming both;
* every row of the inventory's quirk tables has its id (Q1.. in order) in
  the quirk tables, once, with a place it is honoured;
* every REF ArucoMarkers/*.py file of the inventory's per-file table is in
  the migration map with its line count and a class (a)-(d);
* the adapter modules the doc names exist.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INV = (ROOT / "docs" / "inventory" / "addin.md").read_text(encoding="utf-8")
DOC = (ROOT / "docs" / "FUSION_ADAPTER.md").read_text(encoding="utf-8")


def _section(text, start, end=None):
    s = text.split(start, 1)[1]
    return s.split(end, 1)[0] if end else s


def _rows(text):
    for line in text.splitlines():
        if line.startswith("| ") and not line.startswith("|---"):
            yield [c.strip() for c in line.strip().strip("|").split(" | ")]


def f_bullets():
    out = []
    det = _section(INV, "## Detailed responsibility list", "## The versioned rules")
    f = None
    for line in det.splitlines():
        if line.startswith("### "):
            f = line[4:].split(" (")[0]
        m = re.match(r"- \(F\) (.*)", line)
        if m:
            out.append((f, re.search(r"`([^`]+)`", m.group(1)).group(1)))
    return out


def quirk_rows():
    q = _section(INV, "## Fusion 2705 behaviours and quirks on record")
    return [r for r in _rows(q) if r[0] != "behaviour"]


def test_every_f_bullet_has_a_row():
    table = _section(DOC, "### 3.2 Every (F) responsibility", "### 3.3")
    rows = [r for r in _rows(table) if r[0] != "REF file"]
    bullets = f_bullets()
    assert len(bullets) >= 12
    missing = [(f, fn) for f, fn in bullets
               if not any(f"`{f}`" == r[0] and f"`{fn}`" in r[1] for r in rows)]
    assert not missing, f"missing: {len(missing)} {missing}"


def test_every_quirk_row_is_mapped():
    inv = quirk_rows()
    q = _section(DOC, "## 2. Fusion 2705 quirks the adapter must honour", "## 3.")
    rows = [r for r in _rows(q) if re.fullmatch(r"Q\d+", r[0])]
    ids = [r[0] for r in rows]
    want = [f"Q{i}" for i in range(1, len(inv) + 1)]
    missing = [i for i in want if i not in ids]
    assert not missing, f"missing: {len(missing)} {missing}"
    assert ids == want, "the quirk ids are the inventory's rows in order, once each"
    empty = [r[0] for r in rows if len(r) < 3 or not r[2]]
    assert not empty, empty


def test_every_ref_module_is_in_the_map():
    per_file = _section(INV, "## Per-file table", "## Detailed responsibility list")
    inv = {r[0]: int(r[1]) for r in _rows(per_file)
           if r[0].endswith(".py") and r[1].isdigit()}
    assert len(inv) == 45
    table = _section(DOC, "### 3.1 Every REF module", "### 3.2")
    rows = {r[0].strip("`"): r for r in _rows(table) if r[0].startswith("`")}
    missing = sorted(set(inv) - set(rows))
    assert not missing, f"missing: {len(missing)} {missing}"
    bad = [f for f, n in inv.items() if int(rows[f][1].replace(",", "")) != n
           or not re.search(r"\([abcd]\)", rows[f][3])]
    assert not bad, bad


def test_named_adapter_modules_exist():
    names = set(re.findall(r"`((?:adapters/fusion/)?(?:recipe|api|target|bodies|features|"
                           r"feature|paint|joint_origin|records|restructure|sync|ids)\.py)`",
                           DOC))
    for n in names:
        base = n.split("/")[-1]
        path = ROOT / "aruco_studio" / "adapters" / ("fusion" if base != "recipe.py" else "") \
            / base
        assert path.exists(), n
