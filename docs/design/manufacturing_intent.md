# Manufacturing intent: "Made by" (design note, 2026-10-16)

A design note only. Nothing here is built. It answers Zach's ask of 2026-10-16:

> "I want to make the manufacturer technique first class supported. ... when you do aruco extrude ... you need to define as one of the first things whether this is going to be a 3D printed or a printed marker (Sticker or Modelled?) ... it should definitely ... change what controls we get ... when you export it simple to detect. ... the design intent for this needs to kinda be stated up front as it does change a lot down stream ... in a single environment we can have both 2D and 3D markers ... and the ids shall work across all."

| | |
|---|---|
| Written against | ArUco Studio `main` at `17a47a6` (M1, M2 built; M3 / M4 / M5 in progress); REF = cad-exporter `aruco-fusion-plugin-0e9bcb` at `c8216ff` plus its 2026-10-16 trim commits, read only |
| Touches later | `docs/ARCHITECTURE.md` 5.2 / 5.3 (two rows), `docs/API.md`, `docs/spec.json` (section 10 lists the entries), the Fusion add-in (section 7) |
| Does not touch | any versioned rule that exists: `SPEC_VERSION 2`, `CELL_RULE 1`, label `RULE 2`, `ORIGIN_RULE 2`, trim `RULE 1`, the record's shape, `bam_aruco_presets/1`, `arucostudio.scene/1` |

## 0. The recommendation in one paragraph

Every tag says how it is made: **Made by: 3D printed** or **Made by: Printed sticker**. It is the first choice of a new tag, before Type, stored on the tag as a versioned rule (`settings.make`, rule 1), defaulted from the preset or the last choice, and read by everything downstream: the form shows only the rows that apply, the plan makes either slabs or a sticker, the preset library shows PrusaSlicer profiles or print-shop profiles, the 2D / 3D views draw a thin sticker or a stack, the scene keeps one ID ledger for both, and ONE Export writes the sticker sheet and the 3D parts from the same scene. A tag made before the field exists has no `make` key and is a 3D-printed tag, bit for bit as today. In Fusion a sticker is a thin White + black body (stock 0.1 mm, ink 0.01 mm): today's node, today's Joint Origin, today's IDs parts, no new Fusion paths.

## 1. The concept and its name

### 1.1 Name

| Where | Words |
|---|---|
| The concept, in docs and code | manufacturing intent; module `core/make.py`; key `make` |
| The row | **Made by** |
| The choices | **3D printed** (code `print3d`) · **Printed sticker** (code `sticker`) · reserved for later: **Engraved** (`engrave`: laser / CNC, the pattern cut into the face) |
| Short badges (canvas, tables) | `3D` · `2D` |

"Made by" rather than "2D / 3D": 2D and 3D already name the two VIEWS, and an engraved tag is neither. The codes are the manufacturing process, so a third one fits without renaming.

### 1.2 Where it sits: the first choice

| Shell | Place |
|---|---|
| Studio, new tag | the New-tag control: `[Made by: 3D printed ▾]` first, then Type (single / grid / ChArUco), then the target. `POST /api/new` gets `made_by` |
| Studio, inspector | the header block above the tabs (with the name and the Preset row): row 1 `Made by`, row 2 `Preset`. Editable later; what a change does is in 1.5 |
| Fusion, ArUco Extrude v2 | a ROOT row before Preset. Root rows show as the first rows of every tab (measured 2026-10-16, `docs/design_aruco_ui_v2.md` section 10), so it is the first thing on every tab. v1: the first row, before Profile |
| Fusion, Edit | the same row, showing what the node is; a change is a structural edit (1.5) |

### 1.3 The stored setting (versioned, like `cells` and `trim`)

```
settings["make"] = {"rule": 1, "by": "print3d"}
settings["make"] = {"rule": 1, "by": "sticker", "thickness_mm": 0.1, "margin_mm": 0.0, "cut_line": true}
```

| Rule | Same convention as |
|---|---|
| `core/make.py`: `MAKE_RULE = 1`, `BY = ("print3d", "sticker")`, `make_of(settings) -> Make`, the words | `core/trim.py` `RULE`, `trim_of` |
| `default_settings()` NEVER holds `make` | `cells` (2026-10-14), `trim` (2026-10-16) |
| A tag without the key is **3D printed**, and plans exactly as today: `make_of` gives `Make(by="print3d", legacy=True)` and nothing else in the plan changes | a node without `cells` keeps the 0.5 mm steps; without `trim` builds as before |
| An unknown rule number, an unknown `by`, junk: read as 3D printed, with a `warn` Issue on `settings.make` ("read as 3D printed") | junk `trim` reads as off with a `warn` |
| A new tag (`/api/new`, the Fusion dialog's OK) always stores `make` | a new tag always stores `cells` |
| An edit writes `make` only when the row was changed; OK unchanged writes nothing | `cells`, `trim` |
| `TagPlan.rules.make`: `1`, or `null` for a tag without the key; `TagPlan.made_by`: `"print3d"` / `"sticker"` (top level, so no shell parses settings) | `rules.cells`, `rules.trim` |
| The 2D fields: `thickness_mm` (the stock plus its laminate, 0.05..2, default 0.1), `margin_mm` (extra white outside the quiet zone, inside the cut line, 0..50, default 0), `cut_line` (draw it on the sheet, default on). Out of range: `warn`, clamped | `trim.margin_mm` |
| `plan/spec.check` rows: `settings.make` (level warn, bad `{"rule": 9}`), `settings.make.by` (warn, bad `"laser"`), `settings.make.thickness_mm` (warn, bad `-1`), `settings.make.margin_mm` (warn, bad `75`) | ARCHITECTURE 5.6 |

### 1.4 Defaults: preset, then memory

| Source | Wins when |
|---|---|
| the row, as the user set it | always |
| the preset's `profile.kind` (section 2.4: a PrusaSlicer profile is `print3d`, a print-shop profile `sticker`) | a preset was picked for the new tag |
| the remembered choice (`remembered.json` / `aruco_settings`: `made_by`, remembered at OK like Type is) | no preset says |
| `print3d` | a first run |

Picking a preset of the other kind while editing does not happen: the library shows only the presets of the tag's kind (2.4).

### 1.5 Changing it on an existing tag

| Shell | What happens |
|---|---|
| Studio | a plain edit of `settings.make`; the plan is remade. A **locked** (printed) tag refuses it: the frame moves by the sticker's thickness, so `plan/record.ink_digest` changes, which is exactly the lock's rule (ARCHITECTURE 5.5) |
| Fusion | a structural edit: the parts change (`tile, pocket, pattern, ...` to `sticker, ink`), so `core.edits.edit_kind` says rebuild, with today's words ("OK REBUILDS this tag ..."). In place later, when `core.restructure.ROLE_ORDER` knows `sticker` / `ink` |

## 2. Controls per intent

The rows are `plan/fields.py`'s 49 fields (= `GET /api/form`, = ARCHITECTURE 5.6), grouped as the Studio's inspector and the v2 dialog group them (Marker · Heights · Print · Label · Advanced; `studio/src/inspector/layout.ts`, REF `aruco_extrude_ui.ROUTE`). **3D** = Made by: 3D printed (today's rows, unchanged). **2D** = Made by: Printed sticker.

Legend: shown · hidden · **changed** (same field, other words or limits) · new.

### 2.1 Root (above the tabs)

| Row | Field | 3D | 2D | Note |
|---|---|---|---|---|
| Made by | `settings.make.by` | new | new | the first row |
| Preset | (the preset row) | shown | shown | the list filtered by kind (2.4) |
| Profile / Target | `target.*` (the target editor: `w_mm`, `h_mm`, `loops_mm`, `body_mm`) | shown | shown | a sticker is still fitted on a face with holes: Auto size, candidates, the quiet ring are the same. `body_mm` (thickness) is kept but cuts nothing; the editor says "nothing is cut: a sticker sits on the face" |
| Name | `name`, `key` | shown | shown | |

### 2.2 Marker tab

| Row | Field | 3D | 2D | Note |
|---|---|---|---|---|
| Type | `settings.layout` | shown | shown | |
| Auto size · Size | `numbers.size` | shown | shown | the arrow on the model too |
| Checker | `numbers.square` | shown | shown | ChArUco |
| Columns x rows | `settings.force` | shown | shown | |
| Cells | `settings.cells` | shown | **changed** | 3D: "Marker in 0.5 mm steps / Line width (0.68 mm) / Custom…". 2D: "Marker in 0.5 mm steps / **Whole dots (0.042 mm at 600 dpi)** / Custom…". The same `CELL_RULE 1`: `{"of": "cell", "mm": 25.4 / dpi}`. The rounding line reads "= 28.19 mm · 6 cells × 4.70 mm · 111 dots of 0.0423" |
| Layout (candidates) | (`/api/candidates`) | shown | shown | |
| Origin / Up | `settings.turn` | shown | shown | |
| Origin rule | `settings.origin_v` | shown (Advanced) | shown (Advanced) | read only |
| Corner mark | `settings.corner_mark` | shown | **changed** | 3D: None / Cut white corner / Black triangle (shape). 2D: None / **Cut corner** (the cut line's corner is cut at 45°: a person sees which way round; no ink) / Black triangle (ink in the quiet zone's corner, as today's core makes it). The sheet's grey triangle (`core.sheet.TRI_GREY`) stays the sheet's own mark and is off when the tag has a triangle (5.1) |
| Dictionary | `settings.dictionary` | shown | shown | |
| ID | `numbers.marker_id` | shown | shown | |

### 2.3 Heights tab (3D) / Print tab (2D)

| Row | Field | 3D | 2D | Note |
|---|---|---|---|---|
| Extrude (colours) | `settings.mode` | shown | hidden | a sticker is black ink on white stock. (A white-ink-on-black-vinyl sticker is the twin of White only; later, as `make.stock`) |
| Operation | `settings.op` | shown | hidden | nothing joins or cuts |
| Start / White offset · height | `numbers.white_offset`, `white_height` | shown | hidden | the stock's thickness is `make.thickness_mm` (below) |
| Black offset · height | `numbers.black_offset`, `black_height` | shown | hidden | the ink is `INK_MM` (3.1), never a parameter |
| Flip | (`settings.flip`) | shown | hidden | |
| Locating pin · Size · Length · Tolerance | `settings.pin`, `numbers.pin_*` | shown | hidden | pins need a printed tile |
| Printer | (the preset's profile line) | shown: "0.6 mm nozzle · 0.68 mm lines · 0.32 / 0.2 mm layers" | **changed**: "600 dpi · dot 0.042 mm · stock 0.1 mm" | |
| Min cell | `settings.cells.min_mm` | shown ("2 mm" or "3 lines") | **changed** ("1 mm" or "24 dots") | |
| Quiet zone | `settings.quiet_modules` | shown | shown | the sticker's white border. The study (`core.sheet` docstring): ink in the 1-module ring costs -11 pp; 1 module stays the default |
| Fuse corners | `settings.grow` | shown | hidden | 10 µm corner fusing is a TBM concern; ink is one path |
| Layers line | (info: the black's depth in layers) | shown | hidden | |
| Sticker thickness | `settings.make.thickness_mm` | — | new | stock + laminate, mm; the preset's default. It is where the frame sits (3.1) |
| Sticker margin | `settings.make.margin_mm` | — | new | extra white outside the quiet zone, inside the cut line (the 2D twin of Trim margin) |
| Cut line | `settings.make.cut_line` | — | new | drawn on the sheet as a hairline at quiet ring + margin (`core.sheet.CUT_LINE_MM`); the corner cut when the mark says so |
| Heights (as a tab) | | shown | **the tab is named Print and holds the rows above**; the Print tab's 3D rows (Printer, Min cell, Quiet zone, Fuse corners) move in | so a sticker has four tabs: Marker · Print · Label · Advanced |

### 2.4 Label tab

Same model (`core.label.LabelSettings`, rule 2), same words. The rules were measured for a camera, not for a nozzle: they hold on paper.

| Row | Field | 3D | 2D | Note |
|---|---|---|---|---|
| Label · Content · Custom text | `settings.label.on`, `content`, `text` | shown | shown | |
| Position · Row · Side · Markers | `place`, `row`, `side`, `scope` | shown | shown | on the black (knocked out) or on the white |
| Letter height | `cap_mm` | shown | shown | 0 = auto |
| Nozzle | `nozzle_mm` | shown | **changed**: **Stroke** | 2D default 0.2 mm; `min_cap` is `GLYPH_ROWS × stroke` = 1.0 mm, the sheet's own `MIN_CAP_MM`. The same pixel font, so a label reads the same from a print and from a sticker of the same size |
| Stroke (0 = auto) | `stroke_mm` | shown | hidden | folded into the row above |
| Placed · X · Y · legacy nudges · Build anyway · Label rule | the rest | shown | shown | |
| Caption under the sticker | (sheet option, 5.1) | — | shown as a note: "the sheet prints a caption under each sticker (Export)" | not a tag setting |

### 2.5 Advanced tab

| Row | Field | 3D | 2D | Note |
|---|---|---|---|---|
| Trim excess · margin · Cut anyway | `settings.trim`, `trim.margin_mm` | shown | hidden | nothing under a sticker to trim. A sticker tag never stores `trim` |
| Target kind · Side | `target.kind`, `target.z_sign` | shown | shown | |
| Make rule | `settings.make.rule` | shown, read only | shown, read only | like Origin rule |
| Name | `key` | shown | shown | |

### 2.6 What the Preset Library shows per intent

| Collection | 3D printed | Printed sticker |
|---|---|---|
| Built-in | **Default** (0.5 mm steps) · one per PrusaSlicer "Aruco" print profile (`core.prusa`, read only) | **Sticker** (600 dpi, whole dots, stock 0.1 mm, min cell 1 mm, label stroke 0.2 mm) |
| PrusaSlicer profiles · Import from PrusaSlicer | shown | hidden |
| My presets | mine of kind `print3d` | mine of kind `sticker` |
| This document / This scene | the tags of this kind | the tags of this kind |
| Card thumbnail | the cell hatched with the line width | the cell hatched with the dot pitch; a `2D` badge |

A preset carries its kind in `profile`: `{"kind": "print3d" | "sticker", "name", "nozzle_mm", "line_mm", "layer_mm", "first_layer_mm", "dpi", "stock_mm", "source"}`. `line_mm` is "the printer's smallest line" for both kinds (a nozzle's line, or `25.4 / dpi`), so `cells.step = "line"` and `core.presets.cell_setting` work unchanged. `normalise` keeps the three new keys and defaults `kind` to `print3d`, so a REF presets file reads as all-3D and the file stays `bam_aruco_presets/1`. REF's own `normalise` drops the keys it does not know, so a Studio file still loads in the add-in.

A preset never holds Made by itself (the preset's kind is what it is FOR, 1.4), nor `thickness_mm` as a tag setting: the preset's `stock_mm` is the default the row starts from. Like `cells`: the preset gives the number, the tag stores it.

## 3. The plan contract (TagPlan) for a sticker

`plan_tag` branches once, after `check` and before `evaluate`: `make_of(settings).by == "sticker"` goes to `core/make.plan_sticker`. Everything 3D goes where it goes today, untouched (M2's 824 goldens replay as they do now: a 3D tag has no new code on its path).

### 3.1 The sticker's numbers

| Constant | Value | Why |
|---|---|---|
| `STOCK_MM` | 0.1 (the preset's `stock_mm`; the row `thickness_mm`) | a paper label; vinyl + laminate is 0.15..0.25 |
| `INK_MM` | 0.01 | the printed film. Never a parameter. Positive, not zero, because every path here treats a layer as an interval (`plan/region`, `plan/mesh`, `verify/render`, Fusion's bodies) and because the CAD Exporter's record reader ignores a tag whose black has no thickness (REF `markers.TagSpec.from_dict`: "needs ... some thickness — tag ignored"). 0.01 mm is below every tolerance in this repo (the PnP bar is 0.1 mm) |

The sticker plans as a **flush inlay on a thin tile**: white stock `[0, t]`, black ink `[t, t + INK_MM]`, the surface (the tag frame's plane) at `t + INK_MM`, `depth = INK_MM`, `raise = 0`. That is `core.slabs.layers("both", ...)` with fixed numbers, so the record's `depth_m` is `1e-5` and `raise_m` is absent, as a flush 3D inlay stores it.

### 3.2 The fields

| Field | 3D (today) | Sticker |
|---|---|---|
| `made_by` | `"print3d"` (new field; also for legacy tags) | `"sticker"` |
| `rules.make` | `1`, or `null` without the key | `1` |
| `parts` | `tile, pin, pocket, pattern, recess, trim` as `core.slabs.plan` says | `["sticker", "ink"]` |
| `layers` | as today | `sticker` (part `sticker`, white, add, z `[0, t]`, the tile rectangle grown by a label strip, the corner cut as a missing corner when the mark is a cut) · `ink` (part `ink`, black, add, z `[t, t + INK_MM]`, `cell_boxes` per marker) · `mark_triangle`, `label_join` / `label_cut` inside the ink solid, exactly as `plan/layers.LayerBuilder.footprint` makes them for the pattern |
| `combines` | as today | `[{"part": "sticker", "op": "new", "into": null}]`: a body of its own, nothing joined or cut |
| `slabs` | as today | `white [0, t]`, `black [t, t + INK]`, `pattern = black`, `surface = t + INK`, `depth = INK`, `raise 0`, `recess 0`, `pocket null`, `pin null`, `recesses []` |
| `frames.opencv` | on the surface, lifted by raise | on the ink top: `detector_z_mm = surface_mm = t + INK_MM`. A camera sees the sticker's top, 0.11 mm over the face, and the Joint Origin says so |
| `marker` (the record's TagSpec) | as today | `depth_m 1e-5`, no `raise_m`; everything else as the 3D twin |
| `record.fusion` | `mark`, `label` | `mark`, `label`, **`make`** (`{"rule": 1, "by": "sticker", "thickness_mm", "margin_mm", "cut_line"}`). A 3D tag's record is byte-identical to today's: `make` goes in the record only for a sticker |
| `guides` | as today | plus `cut_line` (rect: the quiet ring grown by `margin_mm`; the view draws it dashed) |
| `trim`, `pins` | as today | `null`, `[]` |
| `warnings` | as today | the sticker's own: a cell that is not whole dots (info), `thickness_mm` clamped (warn), a label stroke under one dot (warn), `trim` present and ignored (info: "a sticker has nothing to trim") |
| `writes` | as today | `parts: ["sticker", "ink"]`, `pin "none"`, no `trim` |
| `digest`, `record_digest`, `ink_digest` | as today | the same functions; the frame includes `t`, so a thickness change is an ink change for the lock |

### 3.3 What the views show

| View | 3D printed | Printed sticker |
|---|---|---|
| 2D | target outline, layers, guides | the same, plus the cut line (dashed), the sticker rectangle as the "paper", the `2D` badge |
| 3D | the stack | a 0.1 mm plate with black faces on top; `zRange[1] = t + INK_MM`; the triad on the ink top |
| Inspector size line | "marker 28.0 mm · sticker 37.3 mm (white border ...)" | the same line plus "cut line 37.3 mm" (or "41.3 mm with a 2 mm margin") |

### 3.4 Versioning

`arucostudio.tagplan/1` stays: the new fields are additive (`made_by`, `rules.make`, `guides.cut_line`, two new `parts` words, two new layer names). A reader that does not know them sees a plan with parts it does not build; the Fusion adapter maps `sticker` to the tile path and `ink` to the pattern path (section 7). `arucostudio.tagspec/1` stays: `settings.make` is one more settings key, typed in `plan/spec.SETTINGS_TYPES` as `(dict, type(None))`.

## 4. One scene, both kinds

| Concern | Answer |
|---|---|
| One canvas | a `SceneTag` is a `TagSpec`; `settings.make` rides inside it. `arucostudio.scene/1` is unchanged: a file without `make` on a tag is a 3D tag |
| One ID ledger | ids are per dictionary FAMILY (`core.numbering.family`), never per intent. `scene/ids.py` already numbers every visible tag through `plan_stable` with one ledger: nothing changes. A camera cannot tell a sticker from a print, so a sticker #3 and a printed #3 are a duplicate, flagged as one |
| Renumber | unchanged. A locked tag of either kind is `fixed`; the ledger's `printed` is marked by the export of either kind (5.3) |
| Badges | each tag's canvas label carries `3D` or `2D`; the IDs table gets a **Made by** column (`core.marker_table.MarkerRow.made_by`); the tag's header in the inspector shows the row |
| Filters | the canvas toolbar: `All · 3D · 2D` (a `Show` flag in the store, like `quiet` / `axes`); the IDs table sorts by it |
| Duplicate / copy | `duplicate` keeps `make`; "Paste as sticker" is not needed: duplicate, then switch the row |
| `presets_used` | the scene's chips show both kinds; the Library's "This scene" collection splits them by kind |

## 5. Export, made simple by the intent

### 5.1 Printed stickers: the sheet

| Piece | What | Code |
|---|---|---|
| Items | one `PrintItem` per visible sticker tag: dictionary, first id, marker length, quiet modules, layout, rows / cols, separation, square, legacy; `label_lines` = the caption (`identity_label` + the tag's name); `top_label` = the name | `core.sheet.PrintItem` (REF `markers.print_items` does the same from a Resolution) |
| New on an item | `ink_mm`: the tag's top view polygons from the plan (`plan/mesh.top`), so the sheet prints the tag's label and corner mark as the plan has them (closes REF OI-PDF-LABEL); `margin_mm` (the cut line = sticker + margin); `cut_corner` | `core.sheet` (one optional field each, default off = today's behaviour) |
| Packing | first-fit-decreasing shelves on letter / A4 / A3 / ..., never scaled, rejected with a reason when a sticker is bigger than the page | `core.sheet.layout_sheet` |
| Page furniture | cut marks, the 100 mm and 4 in ruler bars, `#id` knocked out in the bottom border row, the part name in the top row, the orientation triangle (off for a tag whose own mark is a triangle: one mark per tag), a caption under each sticker, the title and date | `core.sheet.render_pdf` (`SheetSettings`: `cut_marks`, `ruler`, `labels`, `id_mark`, `top_label`, `orient_mark`) |
| Also written | `sheet.svg` (today's 1:1 scene sheet, the 2D tags only) and `images/<dict>_<id>.png / .svg` per distinct sticker | `scene/sheet.py`, `core.dictionary.marker_png / marker_svg`, `core.board.board_png / board_svg` |
| Scale check | the ruler bars are on every page; verify reads them back (6) | |

### 5.2 3D printed: the parts

| Piece | What | Code |
|---|---|---|
| Bodies | per 3D tag, one closed STL per body (white tile, black cells, the body under when the scene gives it a thickness), face-down orientation chosen by the tag | `plan/mesh.stl`, `core.beds.choose_orientation` / `orient_part` |
| Manifest | `parts.json` (`bam_aruco_print3d/1`): per part its bodies with `role` tile / cells, its tags with frames | `core.beds.load_parts` reads exactly this; REF `aruco_export._write_body_stls` writes it |
| Beds and project | packed on the printer's beds (MK4 250 × 210 by default), tile on the white slot, cells on the black slot, the wipe tower kept clear, PrusaSlicer's own last-used presets: `aruco_tags.3mf`, `beds/`, `parts/` | `core.beds.layout_beds`, `render_beds`, `render_projects` (ST-EXP-3MF, planned in M2, lands here) |
| Loose STLs | `stl/<part>__<role>.stl` oriented, millimetres | `core.beds.write_part_stls` (ST-EXP-STL's missing half) |
| Send to PrusaSlicer | the project opened in PrusaSlicer (`server/prusa_launch.py`, Windows only, never in tests) | REF `aruco_export.send_selection` is the Fusion twin |

### 5.3 A mixed scene: one action

`POST /api/scene/export/print` with `{page, landscape, margin_mm, proofs, bed_w_mm, bed_d_mm, black_slot, white_slot, open}`:

| Writes | From |
|---|---|
| `exports/<scene>/sheet.pdf`, `sheet.svg`, `images/` | every visible sticker tag; plus the 3D tags as paper proofs when `proofs` is on (off by default) |
| `exports/<scene>/print3d/` (STLs, `parts.json`, `aruco_tags.3mf`, `beds/`) | every visible 3D tag |
| `exports/<scene>/markers.json` | every tag: name, made by, dictionary, ids, frame in the scene, which file it went to |
| the ledger | `Ledger.mark_printed` for every tag exported, either kind, so a printed id never moves |

The Export panel shows two rows, each with a tick and a count: "4 stickers → sheet.pdf (1 page, A4)" and "3 parts → aruco_tags.3mf (1 bed)". A scene with only one kind shows one row. The per-format routes stay for scripts (`/api/scene/export/svg|png|json|stl|plan`); `stl` and the 3MF skip stickers, `pdf` skips 3D tags unless `proofs=1`.

### 5.4 Which existing code covers what

| | Fusion add-in today | Studio today | Studio after M6 |
|---|---|---|---|
| PDF sheet | Export dialog type "PDF print sheet" → `aruco_export.export(kind="pdf")` → `markers.sidecar_files` → `print_sheet` | `core/sheet.py` ported, unused (ST-EXP-PDF planned) | `scene/export.py` → `core.sheet` with `ink_mm` |
| STL | type "STL files" → `_write_body_stls` + `print_beds.write_part_stls` | `plan/exports.to_stl` per tag, as modelled | `core.beds.write_part_stls` over the plan's bodies, oriented |
| 3MF / beds | type "PrusaSlicer project" → `print_beds.write_beds` | `core/beds.py` ported, unused (ST-EXP-3MF planned) | `scene/export.py` → `core.beds` |
| Send to PrusaSlicer | `aruco_export.send_selection` | — | the project path handed to `server/prusa_launch.py` |
| Which tags go where | the dialog's ticks | — | the intent; ticks to override |

## 6. Verify (OpenCV)

Nothing changes for a 3D tag. For a sticker, three checks are added; the first two are the same oracle on a different picture.

| Check | 3D printed | Printed sticker |
|---|---|---|
| Ids and pose on the plan | the layers rendered (`verify/render`), ids read, PnP within 0.1 mm / 0.1 deg of `frames.opencv` (M2b.1) | the same; the render's "highest material" is the ink at `t + INK_MM`, so the same code reads it |
| The export read back | the mesh raster reads as the layers (M2b.4) | **print scale**: the PDF rasterised at 600 dpi (pymupdf, pinned in M2b), every sticker found at its true size within 0.15 mm (M2b.7's unbuilt bar), each centre where the sheet placed it |
| The scale bar | — | the 100 mm bar measured in the raster: 100.0 ± 0.1 mm; the 4 in bar 101.6 ± 0.1 |
| Whole dots | the Cells row's warning (cells not whole lines) | the same warning for dots; verify reports the worst cell-edge error in dots at the sheet's dpi |
| The quiet ring | — | no ink inside the 1-module ring but what rule 2 allows (the label's own check); a sticker with a `margin_mm` reports the margin's white as clear |
| A mixed scene | `/api/scene/verify` reads the scene sheet (every visible tag) | the same, plus the PDF check for the sticker rows; the report has a `made_by` column |

## 7. Fusion

### 7.1 The row

In the v2 dialog, `Made by` is a ROOT row before Preset: `ROUTE["made_by"] = "root"`, an icon dropdown (`LabeledIconDropDownStyle`; a new list, so its icons are given at `listItems.add`, the all-or-none rule of `bam_fusion_ui.ensure_icons`), a message row (`MSG_ROWS["made_by"]`), remembered at OK (`aruco_settings.remember(CMD_ID, {"made_by": ...})`). On a change the hook re-shows the tabs' rows (Heights' rows hide, the Print tab shows the sticker rows), refilters the Preset row and the library, and the ghost redraws (a thin plate). In v1 it is the first row before Profile. `values()` writes `settings["make"]`; `aruco_feature.evaluate()` branches to the same `plan_sticker` (a `bam_cad_core/aruco_make.py`, the same text as the Studio's `core/make.py`, under the port rules of ARCHITECTURE 2).

This is a change to the LIVE add-in in cad-exporter: its own Fusion-gated work order (test documents only, the paced rules of `docs/aruco_edit_gates_crash_20261013.md`), after the Studio side is green. The Studio's adapter skeleton (M4) does the fake-adsk half first (section 10).

### 7.2 What a sticker is in Fusion: three options

| Option | What it makes | For | Against |
|---|---|---|---|
| **A. A thin sticker body** | today's White + black, New body node with fixed heights: the stock as the white tile (`t`), the ink as the pattern (`INK_MM`), no pins, no pocket, no recess, no trim. Body names as today ("aruco white <key>", "aruco cells <key>"), so `aruco_export.body_role`, the IDs parts' recolour, paint and the Joint Origin code run unchanged. The record carries `fusion.make` | one custom feature, one compute path, one Joint Origin on the ink top (exactly where the camera sees it), per-copy IDs parts work (they copy bodies and re-split the cells by id), Export's rows and highlights work, the ghost is the plan; nothing new in Fusion | two very thin bodies on the part (0.1 mm raises the part's envelope, which is true of a sticker); the TBM booleans at 0.01 mm are untested in Fusion (`PIN_JOIN_OVERLAP_CM` is 0.01 mm today and works); a sticker in a mass property (negligible) |
| B. A decal | Fusion's Decals API with the sticker's PNG | looks like a sticker | measured facts (inventory): PNG / JPEG / TIFF only, no width field, size by `transform`, fails in direct-modelling designs, sometimes ignores `transform`; no body for the IDs parts to re-split, nothing for Export, no compute. This is the decal era `fiducials.py` left behind |
| C. Sketch + Joint Origin only | the frame sketch with the sticker outline and the ink as sketch curves, the Joint Origin on the face, the record on the component | no geometry, no mass, cheapest compute | nothing black or white in the viewport, the per-copy IDs parts have nothing to recolour (per-copy ids would need sketch text), Export's highlight has no bodies; a second kind of node to keep working through every edit gate |

**Recommendation: A.** It is today's node with two numbers fixed, so every measured Fusion behaviour (custom feature compute, `_wrap_first`, the Joint Origin layouts, the IDs parts, paint, the edit gates) is already paid for. C is the fallback if 0.01 mm bodies misbehave in Fusion (a gate records it: a compute of a sticker tag, its two bodies' volumes, an IDs copy of it, Undo / Redo).

### 7.3 Joint Origins and per-copy ids for a sticker

| | |
|---|---|
| Joint Origin | one per tag, on OpenCV's frame at the ink top (`t + INK_MM` over the face), through `core.geometry.jo_decompose` as today; JO_AFTER's frame sketch unchanged |
| ArUco IDs copies | unchanged: each copy's part is the original's two bodies re-split by its id (`part_bodies`, `_recolour`), the label relabelled (`plan/variants`) |
| Export | the PDF type pre-ticks the sticker tags and leaves the 3D tags unticked ("3D printed: a paper proof"); the PrusaSlicer and STL types grey out the sticker rows ("a sticker: see PDF print sheet"); Send to PrusaSlicer skips a sticker's bodies with a note. The Export's `markers.json` carries `made_by` |
| The ghost | `aruco_preview` draws the plan's layers: a thin plate and the ink; the trim ghost never shows |
| Edit | a change of Made by is a structural edit (1.5) |

## 8. build123d and viser, later

| Adapter | What the intent means |
|---|---|
| build123d | nothing new: `sticker` and `ink` are layers like any other (extrude the polygon with holes by `z[1] - z[0]`, place at `z[0]`, `fuse`); `combines` says the sticker is a body of its own. A composer who wants no sticker geometry reads `made_by == "sticker"` and places only `frames.opencv` as a `Location` (and, if drawing, the top view as a face). The STL per copy is for `print3d` tags only |
| viser | `TagPlan.mesh` draws both the same (a 0.1 mm plate with black faces); the `FrameHandle` on the ink top; a `2D` / `3D` label on the node. Renumbering through the scene graph is per family, as in the Studio |
| AssemblySnapshot | no intent in it: numbering does not care. The scene's `markers.json` (5.3) is where an external tool reads which tag is what |
| Engraved, later | `{"rule": 1, "by": "engrave", "depth_mm": 0.2}`: the pattern as a recess into the face (the Black only mode with a negative height, the body is the white), exported as a DXF / SVG of the cut paths. The key has room; nothing in this note needs changing for it |

## 9. Open questions for Zach (each with a default)

| # | Question | Recommended default |
|---|---|---|
| 1 | The row's words: "Made by: 3D printed / Printed sticker", or "Make: Modelled / Sticker", or "Output: 3D / 2D"? | **Made by: 3D printed / Printed sticker** (badges 3D / 2D) |
| 2 | The sticker's default thickness: 0.1 mm (a paper label) or 0.2 mm (vinyl + laminate)? It moves the Joint Origin by that much | **0.1 mm**; the Sticker preset carries it, a print-shop preset can say 0.2 |
| 3 | Should 3D tags go on the sticker sheet as paper proofs by default? | **No**: unticked, one click to add (`proofs`) |
| 4 | The corner triangle on paper: black (today's core, no new layer colour) or the sheet's 0.5 grey (measured +0.2 pp)? | **Black now**; grey later as a layer colour, if the study's margin matters to you |
| 5 | May a locked (printed) tag switch Made by? | **No**: the frame moves, so the lock refuses, as for any ink change; unlock first |
| 6 | Fusion: a thin body (A) or sketch + Joint Origin only (C)? | **A**, with C as the fallback the gate decides |

## 10. Milestone M6: manufacturing intent

After M3 / M4 / M5 have landed on `main` (they own `studio/`, `server/`, `adapters/` now). Three parts, in order; M6a and M6b by one agent on `main`; M6c is a cad-exporter work order.

| | |
|---|---|
| Goal | every tag says how it is made; the form, the plan, the presets, the scene, the exports, verify and the Fusion skeleton honour it; no existing tag changes |
| M6a owner paths | `aruco_studio/core/make.py` (new), `core/presets.py` (profile `kind`, `dpi`, `stock_mm`; the Sticker built-in), `core/form.py` (`MADE_BY_LABELS`, the 2D cells words), `core/validate.py` (`ANCHOR_FIELD["made_by"]`, `["make_thickness"]`, `["make_margin"]`, `["make_cut"]`), `core/sheet.py` (`PrintItem.ink_mm`, `margin_mm`, `cut_corner`; the triangle off per item), `core/marker_table.py` (`MarkerRow.made_by`), `plan/spec.py` (the type row, the four check rows), `plan/fields.py` (the new rows; every row gains `intent: "3d" | "2d" | "both"` and an optional `label_2d`), `plan/plan.py` (the branch, `made_by`, `rules.make`), `plan/layers.py` (`sticker`, `ink`), `plan/record.py` (`fusion.make`), `plan/exports.py` (sheet items from a plan), `scene/export.py` (new: the print bundle), `verify/sheet_check.py` (new: the PDF at 600 dpi, the ruler), `server/` (`/api/scene/export/print`, `/api/new` `made_by`, `/api/form` intents, presets by kind, `remembered.made_by`, `models.py`), `tests/core/test_make.py`, `tests/plan/test_make_plan.py`, `tests/scene/test_make_scene.py`, `tests/server/test_make_api.py`, `tests/verify/test_make_verify.py`, `docs/status/M6.md`, `docs/API.md` |
| M6b owner paths | `studio/src/**` (the New-tag control, the header row, `layout.ts` per intent, the Print tab for 2D, the canvas badge and filter, the IDs column, the Export panel's two rows, the Library's kind filter), `studio/e2e/**`, `reports/e2e/**`, `docs/STUDIO.md` |
| M6c owner paths | `aruco_studio/adapters/fusion/**` + `tests/adapters/test_make_fusion.py` (the fake-adsk half: a sticker tag builds two bodies, one Joint Origin, `body_role`, the export routing); then, in cad-exporter (Fusion-gated, its own order): `bam_cad_core/aruco_make.py`, `aruco_extrude_cmd` / `aruco_extrude_ui` (the row), `aruco_feature` (the branch, fixed heights), `aruco_export` / `aruco_commands` (the routing), `docs/aruco_spec.json` |
| May edit | `docs/ARCHITECTURE.md` 5.2 / 5.3 (two rows: `settings.make`; `made_by`, `rules.make`, the two parts), `docs/spec.json` by the orchestrator |
| Does not touch | any golden; any versioned rule's number or key; `goldens/**` |

### Done checks

| # | Check | Bar |
|---|---|---|
| M6.1 | legacy = 3D: every evaluate() golden case replays byte-identical (the existing test), AND `plan_tag(spec)` equals `plan_tag(spec with make {rule 1, by print3d})` except `rules.make` (`null` vs `1`) | 824 / 824, both ways |
| M6.2 | a sticker plan: `parts == ["sticker", "ink"]`; layers' z as 3.2; `frames.detector_z_mm == t + 0.01`; `ids` equal the 3D twin's; the ink's top view equals the 3D twin's pattern top view pixel for pixel at 20 px / mm | every layout × 4 turns × 3 marks × label off / on |
| M6.3 | OpenCV reads every sticker plan; PnP within 0.1 mm / 0.1 deg of `frames.opencv` | every case of M6.2 |
| M6.4 | junk `make` (rule 9, by "laser", thickness -1) plans as 3D / clamped with a `warn` on its key path; `plan_tag` never raises (the 2,000-spec fuzz drives `make` too) | 0 exceptions |
| M6.5 | a mixed 40-tag scene (20 / 20, two dictionaries) renumbers unique per family across kinds; a sticker #3 and a print #3 are one duplicate; a second renumber changes nothing; the ledger's shape is `bam_aruco_ids_ledger/1` unchanged | all |
| M6.6 | the print bundle of that scene: the PDF holds exactly the sticker tags, each at true size within 0.15 mm at 600 dpi, the 100 mm bar 100.0 ± 0.1 mm, a labelled sticker's label ink present where the plan's label boxes are; `print3d/` holds exactly the 3D tags' bodies, `parts.json` loads through `core.beds.load_parts`, `aruco_tags.3mf` has one object per part with cells on the black slot; `markers.json` names every tag with its kind and file | every check |
| M6.7 | presets: the Sticker built-in applied gives `cells {rule 1, of cell, mm 0.042333}` and `make.thickness_mm 0.1`; `preset_of(apply_preset(spec, p)) == p` for a sticker preset; a REF presets file (no `kind`) reads as all 3D; a Studio file with `kind` normalises through REF's pinned `aruco_presets.normalise` (exec'd from the blob, as M1 does) with the rest intact | all |
| M6.8 | `/api/form`: every row has `intent`; `/api/new` with `made_by: sticker` returns `settings.make` and no `trim`; `PUT /api/remembered` round-trips `made_by`; `GET /api/presets?made_by=sticker` lists no PrusaSlicer profile; a locked tag's `PATCH` of `settings.make` is a 409 | all |
| M6.9 | Playwright: New tag → Made by: Printed sticker → a grid on a 40 mm box; the inspector shows four tabs, no Heights rows, the Print tab's Sticker thickness; the canvas badge reads `2D`; add a 3D single marker; filter `2D` hides it; Export → both files exist; the 3D view's `zRange[1]` is 0.11 for the sticker | screenshots in `reports/e2e/` |
| M6.10 | fake adsk: a sticker tag builds two bodies (z 0..0.1 and 0.1..0.11), no combine, one Joint Origin at 0.11 mm after the 12-edit run; `body_role` maps them; `from_record` on its record gives back a sticker spec; the 3D export routing skips it | all |
| M6.11 | `tools/check.py` exits 0; no server left on 5360 / 5361; nothing written under `%USERPROFILE%\CADExporter` or into REF | true |

### New `docs/spec.json` entries (listed here, written by the orchestrator)

| Id | Area | Name |
|---|---|---|
| ST-MAKE | core | Manufacturing intent: Made by (versioned, `MAKE_RULE 1`; absent = 3D printed) |
| ST-MAKE-PLAN | plan | A sticker's plan: stock and ink layers, the frame on the ink top |
| ST-MAKE-FORM | plan | The form per intent: every row says where it applies |
| ST-MAKE-PRESETS | core | Presets by kind: PrusaSlicer profiles for 3D, print-shop profiles for stickers |
| ST-MAKE-SCENE | scene | Both kinds on one canvas, one ledger, badges and a filter |
| ST-MAKE-EXPORT | export | One export per scene: the sticker sheet and the 3D parts (makes ST-EXP-PDF and ST-EXP-3MF `built`) |
| ST-MAKE-VERIFY | verify | Print-scale and ruler checks on the sheet |
| ST-MAKE-UI | studio | Made by in the New-tag control and the inspector header |
| ST-MAKE-FUSION | adapter | A sticker as a thin body on the fake; the export routing |

| Id | Kind | Checks |
|---|---|---|
| ST-T-MAKE-1 | golden | M6.1 |
| ST-T-MAKE-2 | pytest | M6.2, M6.4 |
| ST-T-MAKE-3 | opencv | M6.3, M6.6 |
| ST-T-MAKE-4 | pytest | M6.5 |
| ST-T-MAKE-5 | pytest | M6.7, M6.8 |
| ST-T-MAKE-6 | playwright | M6.9 |
| ST-T-MAKE-7 | pytest | M6.10 |
