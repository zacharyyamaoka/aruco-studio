# The Fusion adapter

How ArUco Studio meets Fusion. The core and the plan decide everything about a tag. The adapter only turns a `TagPlan` into Fusion calls, and reads Fusion back into numbers.

| | |
|---|---|
| Written | 2026-10-16, milestone M4 (PLAN.md) |
| Code | `aruco_studio/adapters/recipe.py` (host-neutral), `aruco_studio/adapters/fusion/` (needs `adsk`) |
| Tests | `tests/adapters/` on a recording stand-in for `adsk`: `tests/adapters/fake_adsk.py` |
| Run | `.venv/Scripts/python tools/check.py adapters` (96 tests, about 1 minute) |
| REF | the live add-in, cad-exporter worktree `aruco-fusion-plugin-0e9bcb` at `c8216ff`, read only |
| State | a SKELETON. It is not installed into Fusion. Fusion never imported it in this run. |

## 1. The boundary

```
  Fusion face / profile ──read──> Target + base frame ──> plan_tag() ──> TagPlan
                                  (adapters/fusion/target.py)            │
                                                                         v
                                            adapters/recipe.py: parts, solids, steps, shapes,
                                            combines, paint, frames in the host (pure, stdlib)
                                                                         │
                       ┌─────────────────────────────┬───────────────────┴──────────┐
                       v                             v                              v
              bodies.py: TBM boxes,         features.py: a sketch +         joint_origin.py: the
              cylinders, prisms ->          an extrude per layer            Joint Origin on the
              base features (the node)      (a plain build)                 plan's OpenCV frame
```

### 1.1 What the adapter does

| Job | Module | How |
|---|---|---|
| Face / profile selection | `target.py` | reads the clicked face or sketch profile once: its frame (REF `face_frame`, `keep_x`, `profile_rect`), its loops stroked in mm, the body under it boxed in the base frame. Hands `plan.Target` + the base frame to `plan_tag(spec, base=...)` |
| Bodies from the plan's layers | `bodies.py` | each `Layer` polygon as a TemporaryBRepManager box, cylinder or convex prism (REF's box-minus-big-boxes construction); a step = its polygons united; a solid = its steps united or taken away in order; a part = its solids united |
| Sketches and extrudes from the layers | `features.py` | the same recipe as ordinary features: one sketch per layer on the target's plane, its profiles extruded from `z[0]` by `z[1] - z[0]`, New body / Join / Cut with the part's body as the only participant |
| Combines | `feature.py` `combines_for` | `TagPlan.combines`: the tile joined to the body under (Join) or new; pins joined to the tile; the pocket cut from the body under or the tile; the recess cut; the trim column intersected |
| In-place restructure | `restructure.py` | release, delete, create, regroup the SAME node. What to delete and create is `core.restructure.restructure_plan`. Atomic: on any raise, what is left is regrouped and the edit command is taken back |
| The custom feature: create | `feature.py` `create` | frame sketch first (jo_v 2), per part: base feature, body named for its role, its combine; the node around them (`customFeatures.add`, every parameter, the "target" dependency, the "spec" named value); the measured fallbacks (wrap the base features first when a pocket splits the face; one timeline group when there is no node); paint LAST; record and Joint Origin after the node |
| The custom feature: compute | `feature.py` `compute` | reads the node (named value, parameters cm -> mm), plans, swaps every base body (`updateBody` inside `startEdit` / `finishEdit`, always left), repaints the swapped body in the same edit, moves the frame sketch. Never writes the record or a Joint Origin |
| The custom feature: edit | `feature.py` `apply_edit`, `edit` | `core.edits.merged` / `structural_change` / `core.restructure.refusal` say compute, in place or rebuild; writes only what changed (OK on no change writes nothing); the record and the Joint Origin from a fresh plan after |
| The Joint Origin from the plan's frame | `joint_origin.py` | on the frame sketch's point and lines (no angle, no offset), else on the face with `core.geometry.jo_decompose`'s (angle, offsets, flip) and the read-back fallback; ONE per tag, also when an old one refuses `deleteMe()` |
| Appearances | `paint.py` | the recipe's `paint`: pattern black (White only: white), a new tile's body and faces white, a joined tile's faces only, the pins' faces white |
| Records | `records.py` | `TagPlan.record` + the adapter's handles in the component attribute ("bam_aruco", "tags"); a node read back as a `TagSpec` (`plan.spec.from_record`); `body_role`; `preset_of_node` through `core.presets.preset_of` |
| Per-copy IDs as occurrences | `ids.py` | the design as an `AssemblySnapshot` (every copy, its "+" path, light bulbs, world transform, stamp, the ledger); numbering by `core.ids_design.plan_snapshot`; a copy's part as a new component occurrence built from `plan.variants.copy_plan` |
| Timeline behaviour | `feature.py`, `restructure.py`, `sync.py` | roll before the node to edit, never delete a rolled-back item, never leave the tag rolled back, regroup with the marker rolled to the node, the after-compute refresh (`core.edits.verdict`) queued by tag and run at idle |

### 1.2 What the adapter must NOT do

| Never in the adapter | Where it lives |
|---|---|
| sizing, the fit, Auto size, rounding to the cell grid | `core/autosize.py`, `plan/evaluate.py` |
| the label: texts, slots, caps, strokes, the refusal | `core/label.py` |
| the cells, the corner mark, quiet zones | `core/markers.py`, `core/chamfer.py`, `core/dictionary.py` |
| Offset / Height slabs, pins, pocket, recess, trim | `core/slabs.py`, `core/trim.py` |
| print presets, PrusaSlicer profiles | `core/presets.py`, `core/prusa.py` |
| validation and the dialog's words | `core/validate.py`, `core/form.py`, `plan/fields.py` |
| the edit model, what an edit changes | `core/edits.py`, `core/restructure.py` |
| numbering, the ledger | `core/numbering.py`, `core/ids_design.py` |
| the Joint Origin maths | `core/geometry.py` (`jo_decompose`, `jo_compose`) |

A test holds the line: `tests/adapters/test_api_surface.py` checks that the adapter calls only the Fusion names in `api.SURFACE` and `api.METHODS`. Every number in a body comes from the recipe; `tests/adapters/test_build.py` probes every part against the plan's own 2D answer.

### 1.3 The protocol and the stand-in

| | |
|---|---|
| `api.SURFACE` | the 26 `adsk.core` / `adsk.fusion` names the adapter may name (`Point3D`, `TemporaryBRepManager`, `CustomFeature`, `JointGeometry`, ...) |
| `api.METHODS` | the methods and attributes it may call, by Fusion class |
| `fake_adsk.py` | implements exactly that: TBM boxes, cylinders and booleans as a CSG tree a point probe answers exactly; REF's timeline model (items, the marker, roll before / after, insert at the marker); base features, combines and extrudes replayed in timeline order; the custom feature (parameters, named values, dependencies, the compute event); Joint Origins with Fusion's measured composition; appearances reset by `add()` and `updateBody()`; attributes; occurrences; an edit command whose failure takes everything back |
| the import guard | `import aruco_studio.adapters.fusion` raises `RuntimeError` when `adsk` is not in `sys.modules`; `fake_adsk.install()` puts the stand-in there |

### 1.4 What the tests show

| Check (PLAN M4) | Test | Result |
|---|---|---|
| M4.1 the group is green | `tools/check.py adapters` | 96 passed |
| M4.2 one body step per Layer, its z, in `parts` order, on every `evaluate()` golden case | `test_recipe.py`, `test_build.py` | 814 cases (38 legacy + 776 matrix), 3,785 layers; each layer is exactly the TBM calls its shapes need and spans exactly its z |
| M4.3 CSG probes at the cells, label strokes, mark, pins, holes, tile, trim column | `test_build.py`, `test_features_path.py` | 69,565 probes per build, both builds; every one as the plan's 2D evaluation says |
| M4.4 a node read back gives the same TagSpec; Edit -> OK unchanged writes nothing | `test_records.py` | 814 golden cases replan equal (floats to 1e-9: Fusion keeps cm) |
| M4.5 Joint Origins: 200 random frames; one per tag after 12 edits | `test_joint_origin.py` | under 1e-6 mm / 1e-6 degree; the read-back fallback lands it under a changed convention; one per tag with a refused delete and with two tags |
| M4.6 restructure over every pair of structures x 2 layouts x sketch / none | `test_restructure.py` | 22 structures, 1,760 edits (about 95 % restructured in place, the rest a compute); a failure at each of the 5 steps leaves the document identical once the command is taken back |
| M4.7 this file maps every (F) bullet and every quirk row | `test_migration_doc.py` | missing 0 |
| M4.8 nothing imports adsk for real | `test_api_surface.py` | the import raises without `adsk`; no module outside `adapters/fusion` imports it |
| the call sequence per type | `test_call_sequence.py`, `test_features_path.py` | kept in `tests/adapters/sequences/*.txt`: single, grid, ChArUco, Black only, White only, New body with pins + label + mark, Trim excess; the plain build for the three types |

## 2. Fusion 2705 quirks the adapter must honour

From `docs/inventory/addin.md` ("Fusion 2705 behaviours and quirks on record"), which cites REF's code comments and `docs/research_aruco_*.md`, `docs/design_aruco_*.md`. Ids are the inventory's rows in order. "Skeleton" = done in `adapters/fusion/` and tested on the stand-in. "Later" = a Fusion-gated step (section 4). "UI" = the dialog layer, not this skeleton. "REF harness" = only REF's test tools care.

### Custom Features

| Id | Quirk (short) | Honoured where |
|---|---|---|
| Q1 | Custom Features, `beginStep`, `editingFeature`, `DesignIntentTypes` are preview API | Later: pin the Fusion build in the gate runs |
| Q2 | the definition must be made in `run()`; one definition id per add-in folder per session | Skeleton: `feature.register()` is meant for `run()` only; Later: the entry module |
| Q3 | the manifest needs an `"id"` GUID | Later: the add-in folder's manifest |
| Q4 | `editCommandId` must name an existing command | Skeleton: `register()` sets `EDIT_CMD_ID`; Later: create the command first |
| Q5 | compute may change only base bodies, sketch contents, parameters | Skeleton: `compute()` writes no record, no Joint Origin; `sync.py` refreshes after |
| Q6 | a custom feature's range cannot hold a joint | Skeleton: the node holds base features, combines and its sketch only |
| Q7 | a non-root face must be given as its root-context proxy to `addDependency` | Later: `target.py` keeps the picked proxy for the dependency, `native_of` for reading |
| Q8 | a root node may depend on a face proxy inside a linked design | Later: `ids.py` dependency choice |
| Q9 | `CustomFeatureParameters.itemById(unknown)` raises | Skeleton: `records.param()` catches it; the stand-in raises too |
| Q10 | an error reported in compute inside `add()` makes `add()` raise | Skeleton: compute skips while the spec is not written yet |
| Q11 | `addWarning("API_COMPUTE_WARNING")` makes the node an ERROR | Skeleton: only non-info notes warn (`core.settings.is_info`) |
| Q12 | Fusion ignores the status text; the words go in the node's name | Skeleton: `plan.record.node_name(..., node_warning)` |
| Q13 | a node with a warning must warn at once | Skeleton: create() names the node with its warning; Later: the nudge recompute |
| Q14 | `beginStep()` in activate undoes the roll and fires execute | UI: the edit command |
| Q15 | parameters as expressions; `max()` takes `;`; compare without spaces | Later: `link_black` / `follow_expression` (Core request R9) |
| Q16 | a pocket that splits the face kills the dependency; wrap first | Skeleton: `feature.wrap_first`; the stand-in models the split face |
| Q17 | `customNamedValues` showed no write lag | Skeleton: the spec lives in a named value |
| Q18 | `FusionEditFeatureCommand` does not reach the edit command from the API | UI: the edit routes |

### Edit Feature in Part designs

| Id | Quirk (short) | Honoured where |
|---|---|---|
| Q19 | in a Part design there is no Edit Feature for an add-in's node | UI: the marking-menu entry and the toolbar route |
| Q20 | the fix: a marking-menu entry and the toolbar opening the node's edit | UI |
| Q21 | nodes made inside a hidden command showed Edit Feature | REF harness |

### The timeline

| Id | Quirk (short) | Honoured where |
|---|---|---|
| Q22 | `timelineObject.index` raises inside a collapsed group | Later: every `_idx` call reads the group's index; the stand-in raises for a released node only |
| Q23 | a roll recomputes everything after the marker; rolling per node is quadratic | Skeleton: the plan is pure, so the record is written from a fresh plan without a roll (`refresh_record`) |
| Q24 | delete + create cascade-deletes downstream features | Skeleton: `restructure.py` restructures in place |
| Q25 | a fillet on the plate dies on structural edits | Later: open item OI-FILLET |
| Q26 | a sketch-point move recomputes lazily | Later: read the face after Compute All in gates |
| Q27 | a reversed longest edge turned the pattern 180 degrees | Skeleton: `target.keep_x` with `x_base`, `Target.x_ref`; tested with reversed edges |
| Q28 | `TimelineGroup` has no `entityToken` | Skeleton: `make_group` falls back to "group lo..hi" |
| Q29 | a Joint Origin after the node is not re-evaluated when compute moves the sketch | Skeleton: `sync.after_compute` + `run_pending` re-place it after the compute |
| Q30 | Undo is one clean step; compute does not run on Undo | Later: `core.edits.SyncState.undoing` set from Fusion's undo events |
| Q31 | `reorder(count)` throws; `reorder(count - 1)` | Later: `ids.py` part placement |
| Q32 | a sub-assembly moved without Capture Position goes back | Later: `ids.py` OK captures positions first |
| Q33 | a moved copy does not recompute the IDs node | Later: `ids.py` hooks |

### Appearances

| Id | Quirk (short) | Honoured where |
|---|---|---|
| Q34 | `add()`, `updateBody()` and a replay reset base-body appearances | Skeleton: paint LAST in create(); repaint inside the edit in compute; the stand-in resets them |
| Q35 | painting the source body inside the edit sticks; face-level paint survives joins and pieces | Skeleton: `paint.repaint_source`; tile and pin faces painted |
| Q36 | a cut tile's second piece is "tag tile <key> (1)" | Later: `paint` of every tile piece (REF `tile_pieces`) |
| Q37 | a boolean result carries no colour (IDs parts came back "Steel - Satin") | Later: the IDs repaint hook |
| Q38 | a joined tile's refilled cell came out in the plate's colour | Later: `ids.py` face colours |
| Q39 | a custom-graphics dashed line is not drawn | UI |

### Joint Origins and joints

| Id | Quirk (short) | Honoured where |
|---|---|---|
| Q40 | Fusion's composition: angle about the UNFLIPPED z, flip about x', offsets along the final axes | Skeleton: `core.geometry.jo_decompose`; the stand-in composes this way on its own; 200 random frames |
| Q41 | offsets and angle go in through the input; editing them needs a roll | Skeleton: `joint_origin.add` sets them on the input only |
| Q42 | `deleteMe()` on a Joint Origin can refuse | Skeleton: `delete_quietly`, the `_MADE` tracking, keep the old and drop the new; tested |
| Q43 | rigid joints to proxies work; a joint lives in the lowest common component | Later: `ids.py` part joints |
| Q44 | `addNewComponent` pins the first part to its parent | Later: `ids.py` |
| Q45 | a root joint on a copy in a linked rig goes back after capture | Later: `ids.py` |
| Q46 | physical properties count hidden bodies | Later: report mass without hidden originals |

### Occurrences, attributes, delete, linked designs

| Id | Quirk (short) | Honoured where |
|---|---|---|
| Q47 | per-path light bulbs are independent and transacted | Skeleton: `ids.snapshot` reads visibility per path |
| Q48 | occurrence attributes are per path; component attributes are shared | Skeleton: stamps on occurrences, records on components |
| Q49 | a parent cannot find a linked design's feature by token | Later: `ids.py` `_record_live` rule |
| Q50 | `createForAssemblyContext` proxies' `transform2` is not world below level one | Skeleton: `ids.snapshot` reads `root.allOccurrences` proxies |
| Q51 | an occurrence name may contain "+" | Skeleton: paths go to `core.markers.split_path` unchanged |
| Q52 | Fusion's Delete of a copy holding a part hangs on a modal | Later: the replaced Delete command |
| Q53 | Fusion's Delete on the IDs node leaves the originals off | Later: the add-in's own delete |
| Q54 | `DataFolders.itemByName` raises | Later: walk the folders (export) |
| Q55 | `bRepBodies.itemByName("")` raises | Skeleton: the stand-in raises; the adapter never asks for "" |
| Q56 | closing an edited linked design while uploading crashed Fusion | REF harness / Later: gate pacing |
| Q57 | Fusion's autosave crashed after a test document closed | REF harness: paced closes |

### Dialog inputs and events

| Id | Quirk (short) | Honoured where |
|---|---|---|
| Q58 | inputs set by code echo `inputChanged` | UI |
| Q59 | a button fires `inputChanged` twice; no double-click in tables | UI |
| Q60 | a tab switch sends "APITabBar" | UI |
| Q61 | root inputs show on every tab | UI |
| Q62 | list items all with icons or all without | UI |
| Q63 | a list icon only from `listItems.add()` | UI |
| Q64 | an input's name is fixed; `validateInputs` has no reason text | UI: messages come from `core.validate` Issues |
| Q65 | the value box at an arrow belongs to the focused input | UI |
| Q66 | `mouseDragEnd` for a manipulator drag | UI |
| Q67 | re-placing an arrow can fight a drag | UI |
| Q68 | no tooltip to synthetic hovers | REF harness |
| Q69 | the first click after a tab switch is sometimes lost | REF harness |
| Q70 | a dropdown in a table row shows no arrow until clicked | UI |
| Q71 | Fusion holds event handlers weakly | Skeleton: `feature.STATE.handlers` keeps the compute handler |
| Q72 | the Export highlight must be drawn from `executePreview` only | UI |
| Q73 | clearing a selection input re-enters `inputChanged` | UI |
| Q74 | preview 2-5 ms, refresh 12-37 ms, real features 540-580 ms (single) | Skeleton: `plan_tag` is about 1.2 ms per tag offline; Later: measure the build |

### Palettes and HTML

| Id | Quirk (short) | Honoured where |
|---|---|---|
| Q75 | a palette works with ArUco Extrude's command open | UI |
| Q76 | messages at creation are lost; queue until "ready" | UI (`bam_channel.js`) |
| Q77 | palettes die on a workspace switch | UI |
| Q78 | one click arrives twice: opening the library is idempotent | UI |
| Q79 | a title with or without " (Team name)" is the same document | Later: `sync.py` document keys |

### Selection, crashes and the bridge

| Id | Quirk (short) | Honoured where |
|---|---|---|
| Q80 | never delete a selected node | Skeleton: `api.clear_selections()` before every delete (restructure, rebuild, Joint Origins) |
| Q81 | a request under the user's hands crashed Fusion | REF harness: guards |
| Q82 | Fusion drops an add-in's event registrations on stop | Later: the entry module re-registers on start |
| Q83 | one CPython for every add-in; CAD Exporter purges `bam_` modules | Later: ship `aruco_studio` (no `bam_` prefix) under the add-in folder |
| Q84 | Fusion moved to Python 3.14; ship `.py` only | Later: no compiled files in the add-in folder; the core is stdlib only |
| Q85 | hot reload is live in the user's session | REF harness |

### Other measured facts

| Id | Quirk (short) | Honoured where |
|---|---|---|
| Q86 | TBM boxes touching at a corner fuse when grown 10 um | Skeleton: bodies are built from the plan's polygons as given; the plan owns any growth |
| Q87 | `BaseFeatureActivate` inside a collapsed group does nothing | Later: expand before edit |
| Q88 | a sketch on the pocketed face projects the pocket edges | Skeleton: `features.py` extrudes every profile it drew, never `profiles.item(0)` alone |
| Q89 | decals: PNG/JPEG/TIFF, size by transform | not used (the decal path is deferred) |
| Q90 | 20 copies / 600 bodies: IDs open 2.3 s, OK 7.7 s | Later: measure `ids.py` |
| Q91 | long mesh names pass Windows' 260-character limit | Later: export names (`core.export_rows.slug`) |

## 3. The migration map

### 3.1 Every REF module

Lines are `wc -l` at `c8216ff`. Class: (a) replaced by a core / plan call, (b) stays as a thin adapter, (c) UI, (d) test harness. A file with several classes lists its main one first; the split is the inventory's (C / F / U / T lines).

| REF `ArucoMarkers/` file | Lines | C / F / U / T | Class | Becomes |
|---|---:|---|---|---|
| `ArucoMarkers.py` | 77 | 0 / 77 / 0 / 0 | (b) | the add-in entry: `feature.register()`, the IDs definition, the commands, the hooks |
| `aruco_actions.py` | 1,882 | 0 / 0 / 0 / 1,882 | (d) | stays in REF (the dev bridge's actions) |
| `aruco_autosize_gallery.py` | 373 | 115 / 0 / 0 / 258 | (a) + (d) | `core/faces.py` (done in M1); the Fusion build of the gallery stays in REF |
| `aruco_bridge.py` | 252 | 0 / 0 / 0 / 252 | (d) | stays in REF |
| `aruco_cf_probe.py` | 1,388 | 0 / 0 / 0 / 1,388 | (d) | stays in REF (superseded research) |
| `aruco_chamfer_lab.py` | 679 | 0 / 0 / 0 / 679 | (d) | stays in REF |
| `aruco_commands.py` | 1,498 | 150 / 250 / 1,000 / 98 | (c) + (a) + (b) | the dialogs (c); the rows and words `core/export_rows.py` (a); `_TagExecute` / `_EditExecute` call `feature.create` / `feature.edit` (b) |
| `aruco_core.py` | 52 | 0 / 52 / 0 / 0 | (b) | a 20-line loader that puts the add-in's `aruco_studio` on `sys.path` (Q83) |
| `aruco_demo.py` | 284 | 0 / 0 / 0 / 284 | (d) | stays in REF |
| `aruco_edit_gates.py` | 1,727 | 0 / 0 / 0 / 1,727 | (d) | stays in REF; re-pointed at the adapter in step 7 |
| `aruco_edit_test.py` | 870 | 0 / 0 / 0 / 870 | (d) | stays in REF |
| `aruco_export.py` | 680 | 120 / 560 / 0 / 0 | (b) + (a) | `adapters/fusion/export.py` (not in the skeleton): STLs by Fusion's exporter, the project file; rows and kinds `core/export_rows.py`, files `plan/exports.py` |
| `aruco_export_lab.py` | 373 | 0 / 0 / 0 / 373 | (d) | stays in REF |
| `aruco_export_preview.py` | 260 | 20 / 0 / 240 / 0 | (c) + (a) | the highlight (c); `row_for_path`, `_ids_text` in `core/export_rows.py` |
| `aruco_extrude_cmd.py` | 2,860 | 450 / 250 / 2,050 / 110 | (c) + (a) + (b) | the dialog rows built from `plan/fields.py` and `core.validate` Issues (c); defaults, values, info lines `core/form.py`, `core/validate.py` (a); the target pick `target.py` (b) |
| `aruco_extrude_lab.py` | 1,300 | 0 / 0 / 0 / 1,300 | (d) | stays in REF |
| `aruco_extrude_sync.py` | 571 | 30 / 541 / 0 / 0 | (b) + (a) | `sync.py` (b); `verdict` is `core.edits.verdict` (a) |
| `aruco_extrude_ui.py` | 1,369 | 230 / 0 / 1,139 / 0 | (c) + (a) | the v2 dialog (c); `classify`, `round_line`, `snap_size` in `core/validate.py`, `core/form.py` (a) |
| `aruco_feature.py` | 3,769 | 900 / 2,709 / 70 / 90 | (b) + (a) | `feature.py`, `bodies.py`, `target.py`, `paint.py`, `records.py` (b); `evaluate` = `plan/evaluate.py` + `plan_tag`, the settings and edit model `core/settings.py`, `core/edits.py`, records `plan/record.py` (a) |
| `aruco_heights_lab.py` | 1,284 | 0 / 0 / 0 / 1,284 | (d) | stays in REF |
| `aruco_ids_accept.py` | 5,661 | 0 / 0 / 0 / 5,661 | (d) | stays in REF; the IDs gates G1-G9 re-run in step 8 |
| `aruco_ids_cmd.py` | 535 | 46 / 40 / 449 / 0 | (c) + (a) | the IDs dialog (c); the Status words `core/marker_table.py` (a) |
| `aruco_ids_feature.py` | 3,721 | 300 / 3,291 / 0 / 130 | (b) + (a) | `ids.py` grows into the IDs node (collect, parts, joints, repaint, hooks) (b); `plan_design`, the ledger, staleness `core/ids_design.py`; regions `plan/variants.py` (a) |
| `aruco_ids_follow_probe.py` | 1,237 | 0 / 0 / 0 / 1,237 | (d) | stays in REF |
| `aruco_ids_preview.py` | 260 | 35 / 0 / 225 / 0 | (c) + (a) | the ghost drawn from `plan/mesh.py` (c) |
| `aruco_ids_rack.py` | 203 | 0 / 0 / 0 / 203 | (d) | stays in REF |
| `aruco_ids_stability.py` | 428 | 0 / 0 / 0 / 428 | (d) | stays in REF |
| `aruco_ids_test.py` | 826 | 0 / 0 / 0 / 826 | (d) | stays in REF |
| `aruco_label_lab.py` | 993 | 0 / 0 / 0 / 993 | (d) | stays in REF |
| `aruco_live_test.py` | 795 | 0 / 0 / 0 / 795 | (d) | stays in REF |
| `aruco_marker_table.py` | 986 | 540 / 0 / 300 / 146 | (a) + (c) | `core/marker_table.py` (a); the Fusion table and the camera (c) |
| `aruco_marker_table_lab.py` | 581 | 0 / 0 / 0 / 581 | (d) | stays in REF |
| `aruco_origin_lab.py` | 456 | 0 / 0 / 0 / 456 | (d) | stays in REF |
| `aruco_preset_library.py` | 825 | 470 / 45 / 310 / 0 | (a) + (c) + (b) | cards and words `core/presets.py` (a); the palette (c, the Studio library is M5); `preset_of_node`, `document_nodes` in `records.py` (b) |
| `aruco_presets.py` | 570 | 570 / 0 / 0 / 0 | (a) | `core/presets.py`; the add-in keeps reading Zach's `aruco_presets.json` through the same functions |
| `aruco_preview.py` | 542 | 245 / 0 / 297 / 0 | (c) + (a) | the ghost drawn from the recipe / `plan/mesh.py` (c); its boxes ARE `plan/layers.py` (a) |
| `aruco_probe.py` | 243 | 0 / 0 / 0 / 243 | (d) | stays in REF |
| `aruco_prusa.py` | 273 | 273 / 0 / 0 / 0 | (a) | `core/prusa.py`; the directory walk is the host's |
| `aruco_restructure.py` | 565 | 80 / 475 / 0 / 10 | (b) + (a) | `restructure.py` (b); `restructure_plan`, `refusal` `core/restructure.py` (a) |
| `aruco_settings.py` | 326 | 269 / 0 / 57 / 0 | (a) + (c) | the file model `server/remembered.py` (REF's verbatim); the add-in keeps its own file path (a); `apply` into inputs (c) |
| `aruco_tags.py` | 3,550 | 300 / 2,850 / 0 / 400 | (b) + (a) | `target.py`, `bodies.py`, `joint_origin.py`, `records.py`, `ids.py` (b); the maths `core/geometry.py`, layers and records `plan/` (a) |
| `aruco_trim_lab.py` | 623 | 0 / 0 / 0 / 623 | (d) | stays in REF |
| `aruco_ui_config.py` | 61 | 0 / 0 / 61 / 0 | (c) | stays with the dialogs |
| `aruco_ui_lab.py` | 506 | 0 / 0 / 0 / 506 | (d) | stays in REF |
| `bam_fusion_ui.py` | 1,096 | 0 / 0 / 1,096 / 0 | (c) | the dialog kit stays; its Issue / Validator model is `core/validate.py` |
| **total** | **47,410** | **5,143 / 11,140 / 7,294 / 23,833** | | |

### 3.2 Every (F) responsibility

One row per REF file per (F) bullet of the inventory's detailed list, keyed by the file and the bullet's first function.

| REF file | (F) bullet, first function | Adapter module | What replaces the logic beside it |
|---|---|---|---|
| `ArucoMarkers.py` | `run` | the entry module (later); `feature.register` today | - |
| `aruco_commands.py` | `_TagExecute` | `feature.create` / `feature.edit`, called by the command | `core.form.values` for the inputs |
| `aruco_core.py` | `load` | the add-in's loader (later) | the core is `aruco_studio.core` |
| `aruco_export.py` | `_comp_key` | `export.py` (later); `records.body_role` today | `core.export_rows`, `plan.exports` |
| `aruco_extrude_cmd.py` | `_target` | `target.read`, `feature.plan_for` | `plan.target.Target`, `plan_tag` |
| `aruco_extrude_sync.py` | `after_compute` | `sync.after_compute`, `sync.run_pending` | `core.edits.verdict`, `plan.record.record_digest` |
| `aruco_feature.py` | `register` | `feature.register`, `compute`, `create`, `apply_edit`, `edit` | `plan_tag`, `plan.plan.settle`, `core.edits` |
| `aruco_feature.py` | `native_of` (reading Fusion) | `target.py` (`native_of`, `face_frame`, `of_profile`), `records.py` (`settings_of`, `numbers_of`) | `core.settings.settings_from_stored`, `numbers_from_params` |
| `aruco_feature.py` | `_tbm` (bodies) | `bodies.py` from `recipe.py` | `plan/layers.py` (the layers ARE the bodies) |
| `aruco_feature.py` | `_on_compute` (the node) | `feature.compute`, `wrap`, `wrap_first`, `make_group`, `release`, `paint.py`, `make_frame_sketch`, `move_frame_sketch` | `plan.record.node_name`, `node_warning` |
| `aruco_ids_cmd.py` | `_part_paths` | `ids.py` (later) | `core.marker_table` |
| `aruco_ids_feature.py` | `register` | `ids.snapshot`, `plan_ids`, `make_part`, `write_ledger`; the node, hooks and repaint later | `core.ids_design.plan_snapshot`, `plan.variants.copy_plan` |
| `aruco_preset_library.py` | `preset_of_node` | `records.preset_of_node`; `document_nodes` later | `core.presets.preset_of` |
| `aruco_restructure.py` | `node_roles` | `restructure.node_roles`, `regroup`, `restructure`; `_refs` / `dependents_of` later | `core.restructure.restructure_plan`, `has_combine`, `refusal` |
| `aruco_tags.py` | `face_frame` | `target.py` (frames, loops), `bodies.py` (temporary bodies), `records.py` (records), `joint_origin.py` (Joint Origins), `ids.py` (variants) | `core.geometry.jo_decompose`, `plan/record.py`, `plan/variants.py` |

### 3.3 The order: lowest risk first

Each step keeps every tag the same. The gate says how we know.

| Step | What moves | Risk | Gate that must stay green |
|---|---|---|---|
| 1 | the add-in imports `aruco_studio.core` for presets, Prusa, remembered options, marker table, export rows (its own pure copies go) | none: same functions, same files | REF's 17 Fusion-free suites; `goldens/*.json` |
| 2 | the dialogs' words and checks from `core.form`, `core.validate`, `plan/fields.py` | words only | `goldens/form.json`; REF `test_aruco_ui_v2` |
| 3 | reading a node: `records.settings_of` / `numbers_of` / `spec_of_node` | read only | M4.4 here; REF `test_aruco_edit_roundtrip` |
| 4 | `evaluate()` -> `target.read` + `plan_tag(spec, base=...)` | the biggest; pure | the 824 `evaluate()` golden cases replay exactly (M2); in Fusion: every node's `record_digest` the same before and after (Fusion-gated F1) |
| 5 | bodies: `part_body` -> `recipe.py` + `bodies.py` | geometry | M4.2 / M4.3 here; in Fusion: each node's bodies the same volume, faces and bounding box (F2) |
| 6 | Joint Origins: `_place_joint_origin` -> `joint_origin.py` | the frame | M4.5 here; REF `test_aruco_jo_one_per_tag`; in Fusion: the Joint Origin census and PnP (F3) |
| 7 | create / compute / edit / restructure / sync -> `feature.py`, `restructure.py`, `sync.py` | the timeline | M4.6 here; REF `aruco_edit_gates` (sync, restructure, deps, atomic, jo) and `trim_test` (F4) |
| 8 | IDs -> `ids.py` + `core.ids_design` | per-copy parts | REF IDs gates G1-G9, `aruco_ids_stability` (F5) |
| 9 | the dialogs and ghosts drawn from `plan/fields.py` and `plan/mesh.py` | UI | REF `aruco_ui_lab` v2 checks (F6) |
| 10 | the entry and the packaging: the add-in folder ships `aruco_studio/{core,plan,adapters}` | loading | the add-in starts, registers, and Zach's documents open with no recompute warnings (F7) |

### 3.4 Expected size afterwards

| Part | Today (REF) | After the migration |
|---|---:|---:|
| pure logic in the add-in (C) | 5,143 | 0 (it is `aruco_studio.core` and `plan`) |
| Fusion adapter (F) | 11,140 | about 5,500: this skeleton is 2,400 lines (with `recipe.py`); export, the IDs node (parts, joints, repaint, delete), the Joint Origin anchors and roll rules, the hooks and the entry add about 3,000 |
| UI (U) | 7,294 | about 5,000: the dialogs and ghosts stay, their models are the core's |
| test harness (T) | 23,833 | stays in REF; never shipped |
| add-in total shipped | about 23,600 | about 10,500, plus the shared core |

## 4. The Fusion-gated steps (Zach's Fusion, later)

None of these ran. Each needs Fusion, on test documents only, paced, with Zach's documents never touched.

| Gate | What runs in Fusion | Bar |
|---|---|---|
| F1 | for every ArUco Extrude node in a set of saved test documents: REF `evaluate()` and `target.read` + `plan_tag(base=...)` side by side (read only) | the same `record_digest`; the same notes |
| F2 | rebuild each node's bodies through `bodies.py` in a copy of the document | each body's volume, face count and bounding box equal to 1e-6 cm |
| F3 | `joint_origin.ensure` on every tag | read-back under 1e-5 cm / 1e-6 rad; one per tag (REF census); PnP on a render |
| F4 | create / compute / edit / restructure through `feature.py` with REF's edit gates re-pointed | REF `aruco_edit_gates` and `trim_test` green; no compute errors |
| F5 | IDs through `ids.py` | REF G1-G9 green; the ledger unchanged on Zach's rack (read only) |
| F6 | the dialogs driven by `plan/fields.py` | REF `aruco_ui_lab` checks |
| F7 | the add-in loads `aruco_studio` from its folder | starts, registers both definitions in `run()`, no `bam_` purge, `.py` only |
| F8 | measure the stand-in's guesses: the frame sketch Joint Origin by axis entities, `JointGeometry.createByCurve`'s frame, `OffsetStartDefinition` with a negative distance, `participantBodies` on Join / Cut | each matches the stand-in, or the stand-in is corrected first |

## 5. Core requests

Things the adapter needed that `core/` and `plan/` do not give yet. Not changed in this run (they belong to another builder). Each has a stop-gap in the adapter.

| # | Request | Why | Stop-gap now |
|---|---|---|---|
| R1 | `keep_x` (pure) into `core/geometry.py` | it is maths on vectors; it decides a face tag's x on every compute | a verbatim copy in `adapters/fusion/target.py` |
| R2 | `face_frame`'s pure half (longest straight edge -> x, extents -> centre and size) as a function of edge segments in `core/geometry.py` | so every adapter (build123d too) picks a face's x the same way | `target.face_frame` |
| R3 | `plan_tag(spec, base=...)` to also give `frames.pattern_host` and `frames.opencv_host` (the host's unit, 16 numbers) | an adapter should not compose frames | `recipe.host_frame(base, frames.pattern_in_target)`: about 1e-15 cm from REF's own frame |
| R4 | the body and sketch names (`aruco cells`, `aruco white`, `tag tile`, `aruco pin`, `aruco pocket`, `aruco recess`, `aruco trim`, `aruco frame`, `FRAME_LEN_CM = 0.5`) in `plan/record.py` | they are stored in records (`fusion.cells_body`) and read by the exporter | constants in `adapters/recipe.py` |
| R5 | a junk trim's warning prints its dict with sorted keys | a node stores its spec with sorted keys, so the same tag reads differently in the Studio and in Fusion ("trim {'axes': ..., 'rule': 1}" vs "{'rule': 1, 'axes': ...}") | `test_records.py` plans the sorted spec |
| R6 | `TagPlan.data` to carry `x_fit` (3D, the fit's x) | create() stores it as `x_ref`; today it reads `plan.ev`, so it needs the in-process plan | `plan.ev["x_fit"]` |
| R7 | `TagPlan.data["node_name"]` (REF `_label`) | `plan.record.node_name` needs a `core.markers.TagSpec`, not JSON | `node_name(key, plan.ev["spec"], ...)` |
| R8 | `plan.record.record_same(old, plan)` on a TagPlan | the refresh compares a record with a plan; today it needs `plan.ev` | `record_same(old, plan.ev)` |
| R9 | REF `follow_expression` (the black offset's `max(...; ...)` text) as a pure function in `core/settings.py` | it is string building; `core.edits.NodeState.black_linked` needs it to be read | not built: `link_black` is Later |
| R10 | `core.settings.params_for` is in two places (`core.settings`, `core.restructure`) | one source | the adapter uses `core.settings.params_for` |

## 6. Not in the skeleton

| Item | Why | When |
|---|---|---|
| export (STLs by Fusion's exporter, the PrusaSlicer project) | the Studio's exports come from `plan/` | step 5 / F2 |
| the IDs node itself (collect with linked designs, parts' recolour by TBM, joints, the repaint and rebuild hooks, the replaced Delete) | the snapshot, numbering and a copy's part are here; the rest is timeline work measured only in Fusion | step 8 / F5 |
| the Joint Origin before the node (jo_v 1) anchor rules (`_tag_face`, `_face_under`, the roll rules) | measured in Fusion | step 6 / F3 |
| `link_black` and the follow expression | Core request R9 | step 7 |
| the dialogs, the ghosts, the marking-menu route | UI | step 9 / F6 |
| idle detection and the hidden auto-execute command of the sync | Fusion events | step 7 / F4 |
