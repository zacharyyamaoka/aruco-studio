"""Golden replay: the tag form's words and the per-field messages (goldens/form.json).

REF made it with the dialog's own pure functions (aruco_extrude_cmd,
aruco_extrude_ui, bam_fusion_ui), exec'd from the pinned blobs with the
dialog's state as plain stand-ins. The replay calls core.form /
core.validate, which take that state as arguments.
"""
import golden_cases as GC
import pytest
from _golden import diff, load

from aruco_studio.core import form as X, label as L, markers as Mk, trim as T, validate as V

DOC = load("form")


def spec_of(d):
    return Mk.TagSpec.from_dict(dict(d), lambda m: None, "form")


def label_of(case):
    region = GC.REGIONS.get(case["region"]) if case["region"] else None
    return L.plan_label(spec_of(case["spec"]), dict(case["settings"]), mode=case["mode"],
                        op=case["op"] if case["mode"] == "both" else None, name=case["name"],
                        key=case["key"], region=region, grow=case["grow"])


AXES = dict(X.TRIM_LABELS)


def run(inp):
    fn = inp["fn"]
    if fn == "defaults":
        return GC.norm({"defaults": X.defaults(), "label": X.label_defaults()})
    if fn == "_base_from":
        return GC.norm(X._base_from(inp["vals"]))
    if fn == "cells":
        sp = spec_of(inp["spec"])
        return GC.norm({"cells_line": X.cells_line(sp, inp["s"], X.cell_line_mm(inp["profile"])),
                        "warn": X._cell_warnings(sp, inp["s"])})
    if fn == "_origin_line":
        return X._origin_line(spec_of(inp["spec"]), inp["turn"])
    if fn == "size_line":
        return X.size_line(spec_of(inp["spec"]))
    if fn == "round_line":
        return X.round_line(spec_of(inp["spec"]), *inp["args"])
    if fn == "_mm_text":
        return X._mm_text(inp["v"])
    if fn == "layer_lines":
        return X.layer_lines(inp["s"], inp["n"], inp["profile"])
    if fn == "_choice_of_cells":
        return X._choice_of_cells(inp["c"])
    if fn == "_same_value":
        return X._same_value(inp["a"], inp["b"])
    if fn == "_same_label_settings":
        return X._same_label_settings(inp["a"], inp["b"])
    if fn == "classify":
        return GC.norm([[i.anchor, i.level, i.text, i.note, i.detail]
                        for i in V.classify(inp["lines"], "black_offset")])
    if fn == "info_rows":
        return X.info_rows(inp["lines"])
    if fn == "_short_note":
        return V._short_note(inp["t"])
    if fn == "_short":
        return V._short(inp["t"])
    if fn == "summary":
        sub = [V.Issue(*i) for i in inp["issues"]]
        return GC.norm({"summary": V.summary_text(sub, {"size": "Size", "quiet": "Quiet zone"},
                                                  {"size": "Marker"}, "✓ ok"),
                        "worst": V.worst(sub), "heads": [V.head_of(i.text) for i in sub]})
    if fn == "label":
        lab = label_of(inp["case"])
        mode = inp["case"]["mode"]
        return GC.norm({"entries": X.label_entries(lab, mode),
                        "issues": [[x.anchor, x.level, x.text] for x in V.label_issues(lab, mode)]})
    if fn == "trim":
        axes = AXES[inp["axes"]]
        margin_mm = inp["margin_cm"] * 10.0 if inp["valid"] else None
        values = X.trim_values(axes, margin_mm, inp["force"])
        body = (-25.0, -20.0, 25.0, 20.0)
        face = ([[(-25, -20), (25, -20), (25, 20), (-25, 20)]] if not inp["refuse"] else
                [[(-25, -20), (25, -20), (25, 0), (0, 0), (0, 20), (-25, 20)]])
        tp = T.plan_trim("x", (-10.0, -10.0, 10.0, 10.0), body, face,
                         volumes=(50 * 40 * 5.0, 30 * 40 * 5.0), z=(-5.0, 0.0), force=inp["force"])
        ev = {"trim": tp}
        issues = X.trim_issues(axes, ev, margin_ok=inp["valid"])
        s = {"trim": values, "has_body": True}
        return GC.norm({"values": values, "issues": issues,
                        "lines": X.trim_lines(s, ev, issues, "Plate")})
    raise ValueError(fn)


@pytest.mark.parametrize("case", DOC["cases"],
                         ids=[f"{i:03d}-{c['in']['fn']}" for i, c in enumerate(DOC["cases"])])
def test_form_golden(case):
    d = diff(case["out"], run(case["in"]))
    assert not d, d
