"""M8c.2: which print presets fit which printer (core.prusa.fits and its
condition evaluator, M8 note 5.2 step 3).

The table for the MK4 MMU3 0.4 and 0.6 printer presets is in
docs/status/M8c.md. PrusaSlicer's window is never opened by the tests, so
the table was read from the conditions by hand, the PrusaSlicer way
(boost::regex_match is a FULL match; `!` on a bool vector's [0]); it is
the list PrusaSlicer's print dropdown should show for those printers.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from aruco_studio.core import prusa as PR

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "tests" / "fixtures" / "prusaslicer_m8c"
MK4_04 = "Original Prusa MK4 MMU3 0.4 nozzle - (Black, Clear, White)"
MK4_06 = "Original Prusa MK4 MMU3 0.6 nozzle - (Black, Clear, White)"

TEN = ["0.15mm SPEED @MK4IS 0.25 - Aruco Black", "0.20mm DETAIL @0.6 nozzle MK3 - BAM",
       "0.30mm QUALITY @0.6 nozzle - GEARS", "0.30mm QUALITY @0.6 nozzle MK3 - Ergo Adapter",
       "0.30mm QUALITY @0.6 nozzle MK3 - No Loops", "0.32mm ERGO @COREONE 0.6",
       "0.32mm SPEED @MK3.5 0.6 - Main", "0.32mm SPEED @MK4IS 0.6 - Aruco",
       "0.32mm SPEED @MK4IS 0.6 - Main", "0.40mm DRAFT @0.6 nozzle MK3 - BAM PROTOTYPE"]
# the print dropdown, by hand from the conditions (docs/status/M8c.md)
FITS_06 = {"0.32mm SPEED @MK4IS 0.6 - Aruco", "0.32mm SPEED @MK4IS 0.6 - Main"}
FITS_04 = set()


@pytest.fixture(scope="module")
def src():
    def texts(sub):
        return {f.stem: f.read_text(encoding="utf-8") for f in sorted((FIX / sub).glob("*.ini"))}
    return PR.sources_from_texts(texts("print"), list(texts("vendor").values()),
                                 printer_texts=texts("printer"),
                                 physical_texts=texts("physical_printer"),
                                 ini_text=(FIX / "PrusaSlicer.ini").read_text(encoding="utf-8"))


def test_zachs_ten_print_files_are_the_fixture(src):
    assert sorted(src.user) == TEN


def test_every_condition_parses(src):
    for n in TEN:
        cond = src.user[n].get("compatible_printers_condition")
        assert cond and PR.parses(cond), n


@pytest.mark.parametrize("printer,want", [(MK4_04, FITS_04), (MK4_06, FITS_06)],
                         ids=["MK4 MMU3 0.4", "MK4 MMU3 0.6"])
def test_the_dropdown_for_the_mk4_mmu3_printers(src, printer, want):
    pr = PR.printer_of(printer, src)
    got = {}
    for n in TEN:
        cfg, _chain = PR.resolve(n, src)
        got[n] = PR.fits(cfg, pr)
    assert "maybe" not in got.values(), got
    assert {n for n, f in got.items() if f == "yes"} == want


def test_each_physical_printer_gets_its_prints(src):
    by = {e["name"]: [p["name"] for p in e["prints"]] for e in PR.physical_printers(src)}
    assert by["Haribo"] == by["Le Mis"] == ["0.32mm ERGO @COREONE 0.6"]
    assert by["kappa"] == ["0.32mm SPEED @MK3.5 0.6 - Main"]
    assert by["aburi"] == ["0.20mm DETAIL @0.6 nozzle MK3 - BAM",
                           "0.30mm QUALITY @0.6 nozzle - GEARS",
                           "0.30mm QUALITY @0.6 nozzle MK3 - Ergo Adapter",
                           "0.30mm QUALITY @0.6 nozzle MK3 - No Loops",
                           "0.40mm DRAFT @0.6 nozzle MK3 - BAM PROTOTYPE"]
    assert by["ontario"] == ["0.20mm SPEED @MK4IS 0.4"]          # the current, a system print
    allp = {e["name"]: [p["name"] for p in e["prints"]]
            for e in PR.physical_printers(src, system=True)}
    assert "0.32mm STRUCTURAL @COREONE 0.6" in allp["Haribo"]     # system ones on request
    assert all(not n.startswith("*") for v in allp.values() for n in v)


def test_aruco_first_and_the_line_from_the_print_the_nozzle_from_the_printer(src):
    pr = dict(PR.printer_of(MK4_06, src), physical="")
    got = PR.prints_for(pr, src)
    assert [p["name"] for p in got] == ["0.32mm SPEED @MK4IS 0.6 - Aruco",
                                        "0.32mm SPEED @MK4IS 0.6 - Main"]
    assert got[0]["aruco"] and got[0]["line_mm"] == 0.68 and got[0]["nozzle_mm"] == 0.6


# ------------------------------------------------------------------ the evaluator

CFG = {"printer_notes": "Keep these\\nPRINTER_MODEL_MK4IS\\nPG", "nozzle_diameter": "0.6,0.4",
       "printer_model": "MK4ISMMU3", "nozzle_high_flow": "0,1", "max_layer_height": "0.4",
       "printer_variant": "0.6"}


@pytest.mark.parametrize("cond,want", [
    ("", True),
    ("nozzle_diameter[0]==0.6", True),
    ("nozzle_diameter[1]==0.6", False),
    ("nozzle_diameter[0]!=0.6", False),
    ("nozzle_diameter[0]>0.5 and nozzle_diameter[0]<=0.6", True),
    ("printer_notes=~/.*MK4IS.*/", True),
    ("printer_notes=~/MK4IS/", False),                 # a FULL match, as boost::regex_match
    ("printer_notes!~/.*HF_NOZZLE.*/", True),
    ("printer_model=~/(COREONE|MK4ISMMU3)/", True),
    ('printer_model=="MK4ISMMU3"', True),
    ('printer_model!="MK3.5MMU3"', True),
    ("! nozzle_high_flow[0]", True),
    ("! nozzle_high_flow[1]", False),
    ("not nozzle_high_flow[0]", True),
    ("nozzle_diameter[0]==0.4 or printer_notes=~/.*PG.*/", True),
    ("(nozzle_diameter[0]==0.4 or nozzle_diameter[0]==0.6) and ! nozzle_high_flow[0]", True),
    ("nozzle_diameter[0]==0.4 && nozzle_diameter[1]==0.4", False),
    ("nozzle_diameter[0]==0.4 || nozzle_diameter[1]==0.4", True),
    ("unknown_option==1", None),                        # an option we do not know: maybe
    ("nozzle_diameter[0]==0.6 and unknown_option==1", None),
    ("nozzle_diameter[0]==0.4 and unknown_option==1", False),   # no is no
    ("nozzle_diameter[0]==0.6 or unknown_option==1", True),
    ("printer_model > 3", None),                        # a string against a number
    ("num_extruders * 2 == 4", None),                   # outside the subset: maybe
    ("printer_notes=~/.*[/", None),
])
def test_condition(cond, want):
    assert PR.condition(cond, CFG) is want


def test_fits_compatible_printers_names_decide_first():
    pr = {"preset": "A", "inherits": ["Parent"], "config": CFG}
    assert PR.fits({"compatible_printers": '"A";"B"'}, pr) == "yes"
    assert PR.fits({"compatible_printers": '"Parent"'}, pr) == "yes"
    assert PR.fits({"compatible_printers": '"C"',
                    "compatible_printers_condition": "nozzle_diameter[0]==0.6"}, pr) == "no"
    assert PR.fits({}, pr) == "yes"
    assert PR.fits({"compatible_printers_condition": "foo==1"}, pr) == "maybe"
