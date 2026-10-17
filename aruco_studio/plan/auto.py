"""Auto size at creation (REF aruco_extrude_cmd._check_auto, c8216ff L2169-2202).

A node made with Auto size before 2026-10-13 stores the number Auto picked
then. On Edit, Auto shows ON only if Auto builds exactly that tag here now
(the same board, size and place: a typed size re-fits differently on a face
with holes); otherwise Auto shows OFF at its number, with a note. So OK on
an unchanged dialog never changes the tag.

REF read the dialog's rows and Fusion's host; here the comparison is two
`plan_tag` calls and `core.form.same_build`, so any adapter (and the
Studio's inspector, through /api/auto_check) asks the same question.
"""
from __future__ import annotations

import copy
from typing import Tuple

from ..core import form as _F
from .plan import plan_tag
from .spec import TagSpec


def auto_still_fits(spec, stored_size: float, stored_square: float = 0.0,
                    base=None) -> Tuple[bool, str]:
    """-> (keep_auto, note). `spec`: the node's request (a TagSpec or its
    dict); `stored_size` / `stored_square`: the numbers (mm) the node holds.
    keep_auto is True when Auto (size 0) builds the same tag as the stored
    numbers; else the note says what Auto would build now."""
    if isinstance(spec, dict):
        spec = TagSpec.from_dict(spec)
    charuco = (spec.settings or {}).get("layout") == "charuco"
    auto = copy.deepcopy(spec)
    auto.numbers = dict(auto.numbers or {}, size=0.0, square=0.0)
    fixed = copy.deepcopy(spec)
    fixed.numbers = dict(fixed.numbers or {}, size=float(stored_size),
                         square=float(stored_square) if charuco else 0.0)
    a, b = plan_tag(auto, base=base), plan_tag(fixed, base=base)
    ea = a.ev if a.ok else None
    eb = b.ev if b.ok else None
    if ea is not None and eb is not None and _F.same_build(ea, eb):
        return True, ""
    now = ea["spec"].label() if ea is not None else "nothing"
    built = eb["spec"].label() if eb is not None else f"{float(stored_size):g} mm"
    return False, (f"Auto size would build {now} here now; this tag is {built} "
                   "(Auto size at creation): tick Auto size to re-fit it")
