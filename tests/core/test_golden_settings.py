"""Golden replay: a tag's settings, numbers and the edit model (goldens/settings.json).

REF made it with ArucoMarkers/aruco_feature.py's own pure functions (and
aruco_restructure's refusal), exec'd from the pinned blob on FakeNode: a
custom feature as plain data. The replay hands the same facts to
core.settings / core.edits as a NodeState -- the adapter's reading of a node:

    stored        the "spec" named value, parsed
    params        each parameter the node has, in mm (Fusion's cm x 10.0, as REF did)
    black_linked  REF's black_follows(cf) (what the adapter reads off the expression)
    frame_sketch  REF's aruco_tags.frame_sketch_of(cf) is not None
    roles_error   REF's aruco_restructure.node_roles(cf, s) raising
"""
import golden_cases as GC
import pytest
from _golden import diff, load

from aruco_studio.core import edits as E, markers as Mk, settings as S, slabs as SL

DOC = load("settings")


def node_of(inp, black_linked):
    params = {pid: v * 10.0 if pid != "marker_id" else v for pid, v in inp["params_cm"].items()}
    return E.NodeState(stored=inp["stored"], params=params, black_linked=black_linked,
                       frame_sketch=inp["frame_sketch"], roles_error=inp["roles_error"])


def run(inp, want):
    fn = inp["fn"]
    if fn == "default_settings":
        old = S.JO_AFTER
        S.JO_AFTER = inp["jo_after"]
        try:
            return GC.norm(S.default_settings())
        finally:
            S.JO_AFTER = old
    if fn == "normalise":
        return GC.norm(S.normalise(inp["s"], partial=inp["partial"]))
    if fn == "size_is_auto":
        return S.size_is_auto(inp["s"], inp["n"])
    if fn == "default_numbers":
        return GC.norm(S.default_numbers(inp["mode"]))
    if fn == "structure":
        s, n = inp["s"], inp["n"]
        return GC.norm({"structure": S.structure(s, n), "node_structure": S.node_structure(s),
                        "effective_op": S.effective_op(s), "params_for": __import__(
                            "aruco_studio.core.restructure", fromlist=["x"]).params_for(s),
                        "trim_setting": S.trim_setting(s),
                        "follow": S.resolve_follow(dict(s, black_follows=True), n)})
    if fn == "keep_black_step":
        return GC.norm(E.keep_black_step(*inp["args"]))
    if fn == "settle":
        spec = Mk.TagSpec.from_dict(inp["spec"], lambda m: None, "golden")
        plan = SL.plan(inp["plan"][0], inp["plan"][1], inp["plan"][2],
                       inp["n"], inp["plan"][3])
        return GC.norm(E.settle(inp["s"], inp["n"], {"spec": spec, "plan": plan}))
    if fn == "node":
        node = node_of(inp, want["black_follows"])
        out = {"black_follows": want["black_follows"], "settings_of": node.settings,
               "numbers_of": node.numbers, "rebuild_reason": E.rebuild_reason(node)}
        try:
            out["merged"] = E.merged(node, dict(inp["s_new"]), dict(inp["n_new"]))
            s_old, _n_old, s, n = out["merged"]
            out["structural"] = E.structural_change(node, s_old, s, n)
            out["edit_kind"] = E.edit_kind(node, dict(inp["s_new"]), dict(inp["n_new"]))
        except Exception as exc:                   # noqa: BLE001
            out["raises"] = [type(exc).__name__, str(exc)]
        return GC.norm(out)
    raise ValueError(fn)


@pytest.mark.parametrize("case", DOC["cases"],
                         ids=[f"{i:04d}-{c['in']['fn']}" for i, c in enumerate(DOC["cases"])])
def test_settings_golden(case):
    d = diff(case["out"], run(case["in"], case["out"]))
    assert not d, d


def test_settings_golden_covers_every_generation():
    shapes = {c["in"]["shape"] for c in DOC["cases"] if c["in"]["fn"] == "node"}
    assert shapes == {"legacy_0810", "v2_jo1_no_origin_v", "v2_chamfer_checkbox", "v2_old_frame",
                      "v2_now", "v2_label_rule1_square", "v2_black_new"}
    kinds = {c["out"].get("edit_kind", {}).get("kind") for c in DOC["cases"] if c["in"]["fn"] == "node"}
    assert {"compute", "in place", "rebuild"} <= kinds


def test_spec_version_and_switches_kept():
    assert S.SPEC_VERSION == 2
    assert S.JO_AFTER is True and S.RESTRUCTURE_IN_PLACE is True
    assert DOC["args"]["switches"] == {"JO_AFTER": True, "RESTRUCTURE_IN_PLACE": True}
