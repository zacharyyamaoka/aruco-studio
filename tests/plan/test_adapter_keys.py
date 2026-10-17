"""M2.5: the plan never reads the adapter's keys (ARCHITECTURE 5.2).

plan_tag(spec) gives byte-equal JSON with every adapter-only key deleted
from `settings` (x_base, x_ref, z_sign, has_body, source, jo_v, host_xform,
key, black_follows): the plan reads them from the Target and the spec. The
same with the settings round-tripped through core.settings.normalise."""
from __future__ import annotations

import copy

import pytest

import _evaluate_golden as G
from aruco_studio.core import settings as S
from aruco_studio.plan import plan_tag
from aruco_studio.plan.spec import ADAPTER_KEYS, TagSpec


def _json(spec):
    return plan_tag(spec).to_json()


@pytest.mark.parametrize("group", ["legacy", "matrix"])
def test_adapter_keys_never_change_the_plan(group):
    bad = []
    for c in G.cases(group):
        spec = TagSpec.from_dict(c["in"])
        full = _json(spec)
        stripped = copy.deepcopy(spec)
        for k in ADAPTER_KEYS:
            stripped.settings.pop(k, None)
        if _json(stripped) != full:
            bad.append((c["id"], "stripped"))
        # and set to nonsense: still nothing
        junk = copy.deepcopy(spec)
        junk.settings.update(x_base=[0.0, 1.0, 0.0], x_ref=[-1.0, 0.0, 0.0], z_sign=-1,
                             has_body=not spec.target.has_body, source="cloud", jo_v=7,
                             host_xform=[2.0] * 16, key="zzz", black_follows=True)
        if _json(junk) != full:
            bad.append((c["id"], "junk"))
    assert not bad, bad[:5]


@pytest.mark.parametrize("group", ["legacy", "matrix"])
def test_normalised_settings_give_the_same_plan(group):
    """normalise() is what a node stores after an edit (chamfer -> corner
    mark, the Frame dropped, the label's settings complete): the plan is the
    same, warnings aside (they quote what the request said)."""
    bad = []
    for c in G.cases(group):
        spec = TagSpec.from_dict(c["in"])
        a = plan_tag(spec).to_dict()
        n = copy.deepcopy(spec)
        n.settings = S.normalise(n.settings)
        b = plan_tag(n).to_dict()
        a.pop("warnings")
        b.pop("warnings")
        if a != b:
            bad.append(c["id"])
    assert not bad, bad[:5]
