"""The new-tag rule's server names: the pure functions live in
plan/newtag.py (M8a), so the design file's compile (scene/design.py) and
the server call the same code."""
from ..plan.newtag import (  # noqa: F401
    ADAPTER_KEYS, LAYOUTS, _print_into, apply_preset, new_spec, preset_of,
)
