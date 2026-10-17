"""M8c.1 and M8c.3: PrusaSlicer's physical printers resolved to their
printer preset's numbers, and the allow-list (M8 note 5.2, 5.6).

The fixture is tests/fixtures/prusaslicer_m8c/ (made by
tests/fixtures/make_prusaslicer_m8c.py from PrusaSlicer 2.9.6's folder on
Zach's box, every host key a placeholder). The core reads TEXTS: the test
opens the files.
"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from aruco_studio.core import presets as P
from aruco_studio.core import prusa as PR

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "tests" / "fixtures" / "prusaslicer_m8c"
MARK = "MARKER-7f3c-do-not-leak"
MK4_04 = "Original Prusa MK4 MMU3 0.4 nozzle - (Black, Clear, White)"
MK4_06 = "Original Prusa MK4 MMU3 0.6 nozzle - (Black, Clear, White)"


def texts(folder: Path, sub: str):
    d = folder / sub
    return {f.stem: f.read_text(encoding="utf-8") for f in sorted(d.glob("*.ini"))}


def sources(folder: Path = FIX):
    return PR.sources_from_texts(
        texts(folder, "print"), [t for _n, t in sorted(texts(folder, "vendor").items())],
        printer_texts=texts(folder, "printer"), physical_texts=texts(folder, "physical_printer"),
        ini_text=(folder / "PrusaSlicer.ini").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def src():
    return sources()


# ------------------------------------------------------------------ M8c.1

EXPECT = {   # physical printer -> (printer preset, nozzle, model, variant, bed, source)
    "Haribo": ("Prusa CORE One 0.6 nozzle", 0.6, "COREONE", "0.6", [250.0, 220.0], "system"),
    "Le Mis": ("Prusa CORE One 0.6 nozzle", 0.6, "COREONE", "0.6", [250.0, 220.0], "system"),
    "aburi": ("Original Prusa i3 MK3 0.6 nozzle", 0.6, "MK3", "0.6", [250.0, 210.0], "system"),
    "kappa": ("Original Prusa MK3.5 & MK3.5S 0.6 nozzle", 0.6, "MK3.5", "0.6", [250.0, 210.0],
              "system"),
    "ontario": (MK4_04, 0.4, "MK4ISMMU3", "0.4", [250.0, 210.0], "user"),
}


def test_the_five_physical_printers_resolve(src):
    got = {e["name"]: e for e in PR.physical_printers(src)}
    assert sorted(got) == sorted(EXPECT)
    for name, (preset, noz, model, variant, bed, kind) in EXPECT.items():
        e = got[name]
        assert e["preset"] == preset and e["presets"] == [preset], name
        pr = e["printer"]
        assert (pr["nozzle_mm"], pr["model"], pr["variant"], pr["bed_mm"], pr["source"]) == \
            (noz, model, variant, bed, kind), name
        assert e["technology"] == "FFF" and e["host_kind"] in ("prusaconnect", "prusalink")
        assert "config" not in pr                       # the resolved dump stays in the core


def test_a_user_printer_preset_over_its_system_parent(src):
    """ontario: the user's printer/*.ini, `inherits` the system MK4 MMU3 0.4."""
    pr = PR.printer_of(MK4_04, src)
    assert pr["source"] == "user"
    assert pr["inherits"][:2] == ["Original Prusa MK4 MMU3 0.4 nozzle",
                                  "Original Prusa MK4 Input Shaper 0.4 nozzle"]
    assert pr["extruders"] == 5 and pr["max_height_mm"] == 220.0
    assert pr["layer_mm"] == [0.07, 0.25]
    assert pr["default_print"] == "0.20mm SPEED @MK4IS 0.4"
    assert "PRINTER_MODEL_MK4IS" in pr["notes"] and "\n" in pr["notes"]
    pr6 = PR.printer_of(MK4_06, src)
    assert (pr6["nozzle_mm"], pr6["variant"], pr6["source"]) == (0.6, "0.6", "user")


def test_a_bundle_only_printer_through_a_three_deep_chain(src):
    """Haribo: Prusa CORE One 0.6 nozzle -> HF0.6 -> HF0.4 (which holds the
    model), bundle only; later parents win, own keys last."""
    pr = PR.printer_of("Prusa CORE One 0.6 nozzle", src)
    assert pr["source"] == "system"
    assert pr["inherits"] == ["Prusa CORE One HF0.6 nozzle", "Prusa CORE One HF0.4 nozzle"]
    assert pr["model"] == "COREONE"          # only the deepest parent sets it
    assert pr["variant"] == "0.6"            # its own key wins over the parents'
    assert pr["config"]["nozzle_high_flow"] == "0"


def test_the_selected_pair_and_the_installed_models(src):
    sel = src.selection
    assert sel["physical_printer"] == "ontario" and sel["physical_preset"] == MK4_04
    assert sel["printer"] == MK4_04 and sel["print"] == "0.20mm SPEED @MK4IS 0.4"
    assert sel["filaments"] == ["Generic PLA @PGIS"] * 5
    assert src.installed["MK4ISMMU3"] == ["0.4", "0.6"]
    cur = [e for e in PR.physical_printers(src) if e["current"]]
    assert [e["name"] for e in cur] == ["ontario"]
    assert [p["name"] for p in cur[0]["prints"] if p["current"]] == ["0.20mm SPEED @MK4IS 0.4"]
    assert PR.selected("[presets]\nprint = x\n") is None        # no printer: nothing selected


def test_parse_bundle_kinds_one_pass_and_the_old_shape():
    text = (FIX / "vendor" / "PrusaResearch.ini").read_text(encoding="utf-8")
    old = PR.parse_bundle(text)
    got = PR.parse_bundle(text, kinds=("print", "printer", "printer_model", "vendor"))
    assert old == got["print"] and "*MK4IS_common*" in old
    assert "Prusa CORE One 0.6 nozzle" in got["printer"]
    assert got["printer_model"]["COREONE"]["family"]
    assert got["vendor"][""]["name"] == "Prusa Research"
    assert "filament" not in got                     # skipped unread unless asked


def test_from_pair_carries_the_printer_block(src):
    pr = dict(PR.printer_of(MK4_06, src), physical="")
    pp = PR.pair_profile("0.32mm SPEED @MK4IS 0.6 - Aruco", pr, src)
    assert (pp["nozzle_mm"], pp["line_mm"], pp["layer_mm"], pp["first_layer_mm"]) == \
        (0.6, 0.68, 0.32, 0.2)
    p = P.from_pair(pp, "x")
    assert p["profile"]["printer"] == {"physical": "", "preset": MK4_06, "model": "MK4ISMMU3",
                                       "variant": "0.6"}
    assert p["profile"]["line_mm"] == 0.68 and p["cells"]["of"] == "cell"
    q = P.normalise(dict(p, profile=dict(p["profile"], printer={"model": 7, "junk": "y"})))
    assert "printer" not in q["profile"]              # nothing a printer block keeps
    assert "printer" not in P.from_profile(pp)["profile"]      # REF's from_profile unchanged
    assert P.same_print(p, P.from_profile(pp))        # the block is a label, not a setting


# ------------------------------------------------------------------ M8c.3

def marked(tmp_path: Path) -> Path:
    """The fixture with every host key of one physical printer and of the
    user printer presets set to the marker."""
    import shutil
    d = tmp_path / "ps"
    shutil.copytree(FIX, d)
    keys = ("print_host", "printhost_apikey", "printhost_authorization_type", "printhost_cafile",
            "printhost_password", "printhost_port", "printhost_ssl_ignore_revoke", "printhost_user")
    lines = [f"{k} = {MARK}-{k}" for k in keys]
    for f in [d / "physical_printer" / "ontario.ini"] + sorted((d / "printer").glob("*.ini")):
        kept = [ln for ln in f.read_text(encoding="utf-8").splitlines()
                if ln.split("=", 1)[0].strip() not in keys]
        f.write_text("\n".join(kept + lines) + "\n", encoding="utf-8")
    (d / "physical_printer" / "marked.ini").write_text(
        "\n".join([f"preset_names = \"{MK4_06}\"", "printer_technology = FFF",
                   "host_type = octoprint", f"apikey_extra = {MARK}"] + lines) + "\n",
        encoding="utf-8")
    return d


def _dump(x) -> str:
    if dataclasses.is_dataclass(x):
        x = dataclasses.asdict(x)
    return json.dumps(x, default=str)


def test_the_allow_list_drops_every_host_key(tmp_path):
    d = marked(tmp_path)
    raw = (d / "physical_printer" / "marked.ini").read_text(encoding="utf-8")
    assert raw.count(MARK) == 9                       # the marker is there to find
    got = PR.parse_physical(raw)
    assert set(got) <= set(PR.PHYSICAL_KEYS) and got["preset_names"] == [MK4_06]
    s = sources(d)
    assert MARK not in _dump(s)
    assert MARK not in _dump(PR.physical_printers(s, system=True))
    for name in s.printers:
        assert MARK not in _dump(PR.printer_of(name, s))
    assert not any(PR.private_key(k) for cfg in s.printers.values() for k in cfg)
    assert [e for e in PR.physical_printers(s) if e["name"] == "marked"][0]["printer"]["preset"] \
        == MK4_06


def test_private_key_rule():
    for k in ("print_host", "printhost_apikey", "printhost_password", "printhost_user",
              "printhost_cafile", "printhost_port", "printhost_authorization_type",
              "printhost_ssl_ignore_revoke", "foo_apikey", "x_password", "token"):
        assert PR.private_key(k), k
    for k in PR.PHYSICAL_KEYS + ("nozzle_diameter", "printer_notes", "printer_model"):
        assert not PR.private_key(k), k


def test_complete_files_and_half_written_ones():
    good = (FIX / "physical_printer" / "ontario.ini").read_text(encoding="utf-8")
    assert PR.ini_complete(good, "physical")
    assert not PR.ini_complete(good[:-1], "physical")           # no newline at the end
    assert not PR.ini_complete(good[:good.index("preset_names") + 7], "physical")
    assert not PR.ini_complete("host_type = prusalink\n", "physical")   # no printer named
    pr = (FIX / "print" / "0.32mm SPEED @MK4IS 0.6 - Aruco.ini").read_text(encoding="utf-8")
    assert PR.ini_complete(pr, "print") and not PR.ini_complete(pr[:40], "print")
    assert PR.ini_complete((FIX / "PrusaSlicer.ini").read_text(encoding="utf-8"), "ini")
