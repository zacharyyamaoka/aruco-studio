"""Shells that turn a TagPlan into a host's bodies (ARCHITECTURE 1, 3.6).

| Module | What |
|---|---|
| `adapters/recipe.py` | pure, host-neutral: a TagPlan -> the ordered build steps (parts, solids, steps, shapes, combines, the host frames). Fusion, build123d or any CAD shell executes it. Stdlib only. |
| `adapters/fusion/` | thin: the recipe -> Fusion API calls (TemporaryBRepManager, base features, combines, the custom feature, Joint Origins, appearances). Needs `adsk`; NOT installed into Fusion in this run. See docs/FUSION_ADAPTER.md. |

Nothing here computes sizes, labels, cells, presets or validation. That is
the core's and the plan's.
"""
