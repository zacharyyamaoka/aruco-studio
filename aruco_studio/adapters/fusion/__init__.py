"""The Fusion adapter: a TagPlan -> Fusion API calls (docs/FUSION_ADAPTER.md).

A SKELETON. It is not installed into Fusion and Fusion never imports it in
this run. The tests drive it against a recording stand-in
(tests/adapters/fake_adsk.py).

| Module | Does | REF it replaces (cad-exporter c8216ff) |
|---|---|---|
| `api.py` | the small part of `adsk` the adapter may call (the protocol) | - |
| `target.py` | a face / profile -> `plan.Target` + its base frame | `face_frame`, `keep_x`, `profile_rect`, `face_loops_2d`, `_trim_inputs` |
| `bodies.py` | the recipe's shapes -> temporary bodies (TemporaryBRepManager) | `cells_temp_body`, `poly_prism_temp_body`, `_prism`, `_box`, `part_body` |
| `features.py` | sketches + extrudes from the recipe (a plain, non-custom-feature build) | the 2026-10-07 `add_tag` / `aruco_extrude` path |
| `paint.py` | appearances | `paint`, `_update`'s repaint |
| `joint_origin.py` | the Joint Origin from the plan's frame, one per tag | `_place_joint_origin`, `_jo_add`, `_delete_quietly`, `_MADE` |
| `records.py` | the record on the component; node -> TagSpec; `body_role`; `preset_of_node` | `_write_record`, `read_tag_records`, `settings_of`, `numbers_of`, `body_role` |
| `feature.py` | the custom feature: create, compute, edit | `create`, `_wrap`, `_wrap_first`, `_group`, `_on_compute`, `apply_edit` |
| `restructure.py` | the in-place restructure (release, delete, create, regroup) | `aruco_restructure.restructure`, `node_roles`, `_regroup` |
| `sync.py` | the after-compute hook around `core.edits.verdict` | `aruco_extrude_sync.after_compute` |
| `ids.py` | the design -> `AssemblySnapshot`; per-copy parts as occurrences | `collect_design`, `_make_part_occurrence` |

Importing this package needs `adsk` already in `sys.modules` (Fusion's, or
the stand-in's `fake_adsk.install()`). Without it the import raises, so
nothing here can be imported by accident outside Fusion or a test.
"""
import sys as _sys

if "adsk" not in _sys.modules:
    raise RuntimeError(
        "aruco_studio.adapters.fusion needs Fusion's adsk module. Outside Fusion, install "
        "the stand-in first: tests/adapters/fake_adsk.install() (docs/FUSION_ADAPTER.md)")
