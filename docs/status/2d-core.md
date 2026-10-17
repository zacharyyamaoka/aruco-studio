# The 2D (inkjet sticker) model: lane/2d-core (2026-10-17)

Zach's pivot (CF-13, `docs/feedback/2026-10-17-markers-core-first.md`): "I will just be printing with ink jet moving forward... focus on just the 2D thing." This lane builds the 2D model in the core and the Studio: CF-7 (make rule 2: the black t/2 inside the paper), CF-4's inkjet half (the Inkjet printer presets on vinyl), CF-6's inkjet half (the page lint, Auto capped by the page), Q2 / Q3 (Auto on, turn to fit), Q7 (margin and cut line on the export sheet), and P3's Shift. 3D is left exactly as it was (a working placeholder, no new features).

| | |
|---|---|
| Branch | `lane/2d-core`, from `lane/fusion-core` (`3f45e39`, N-1's core brought up to the add-in) with `main` merged once (`590d114`: the gallery, the extrude proposals, the pivot note) |
| Worktree | `C:\Users\BAM\Documents\aruco-studio-wt\2d-core` (`.venv`, `studio/node_modules`, `e2e/node_modules`: junctions to main's) |
| Not touched | `aruco_studio/adapters/**` (N-1's), any versioned rule's behaviour, `goldens/**` |
| Not merged | the orchestrator merges |

## 1. What was built

### Make rule 2 (CF-7): the paper and the black inside it

"For 2D we should model it as a thin rectangle the thickness of the paper. Black part can be paper thickness/2 and go into the rectangle."

| | Rule 1 (kept for the tags that have it) | Rule 2 (every new inkjet sticker) |
|---|---|---|
| stored | `{"rule": 1, "by": "sticker", "thickness_mm", "margin_mm", "cut_line", "perimeter"}` | `{"rule": 2, "by": "sticker", "thickness_mm", "perimeter", "page", "page_margin_mm"}` |
| parts | `sticker` [0, t], `ink` [t, t + 0.01] (a film on top) | `sticker` [0, t] (ONE paper body, the whole cut outline), `pocket` [t/2, t] (the black's footprint, cut from it), `ink` [t/2, t] (a body of its own): REF's flush inlay on paper |
| combines | sticker new, ink new | sticker new, pocket cut into sticker, ink new |
| the tag frame (OpenCV's) | t + 0.01 | t: the paper's top (`frames.surface_mm` = `detector_z_mm` = t) |
| `marker.depth_m` | 0.01 mm | t/2 |
| the top view, the ids, the sizes | -- | the same as rule 1, polygon for polygon (only the black's depth moved) |
| margin, cut line | on the tag | on the sheet (Q7); a rule-2 `margin_mm` / `cut_line` is read as 0 / on with an info |
| the page | -- | `page`, `page_margin_mm`: what the lint and Auto's cap read |
| `plan.data["sticker"]` | absent (a rule-1 plan's dict is what it was) | `{rule, thickness_mm, paper_z_mm, ink_z_mm, frame_z_mm, perimeter, page: {page, margin_mm, size_mm, fits, how, over_mm, printable_mm}}` |

`plan/mesh.py` needed no change: its pocket rule (white less the pocket) gives the paper with the black sunk into it, closed meshes, the STL; the 3D view shows it (the gallery's `inkjet_paper` has two stickers on 2 mm "paper" so the inset is visible). Code: `core/make.py` (`INSET_RULE`, `Make.inset / ink_mm / ink_z / paper_z / top_mm`, `make_of` / `_rule2`, `rule_of_profile`, `new_make`, `twin_numbers`), `plan/layers.py` (`sticker_parts`, `sticker_layers`, `sticker_combines`), `plan/plan.py` (`sticker_block`, `_sticker_slabs`), `plan/evaluate.py` (the depth).

**Which tags get rule 2.** The preset decides (it is the machine): a profile's new key `make_rule` (2 on the vinyl presets). A sticker profile without it (every preset file, every frozen copy in a design file, the two older built-ins) is rule 1, so every existing file plans bit for bit as before, sugar included (the `sticker_sheet` example still plans rule 1: `tools/mesh_digests.py --check` 947 / 947 equal). No preset at all (a script's `made_by: "sticker"`): rule 2. A 3D tag stores rule 1 as before.

### Inkjet Printer presets (CF-4)

| | |
|---|---|
| The word | every UI label says **Inkjet printer** (Made by, the collection "Inkjet printers", the Library, the IDs table's tooltip, the Make tab, named **Inkjet** on a sticker). The stored kind stays `"sticker"` (every file reads as before) |
| Fields | paper size (`page`), **paper thickness** (`stock_mm`), page margins (`margin_mm`), dpi: the preset's; on the tag `make.thickness_mm`, `make.page`, `make.page_margin_mm` (a local override: the Preset row then reads This tag (modified), Zach's answer 1) |
| Built-ins | **Inkjet · Letter vinyl** and **Inkjet · A4 vinyl**: make rule 2, paper 0.10 mm, page margins 10 mm, 600 dpi (whole dots), min cell 1 mm, label stroke 0.2 mm, spaced sheets. The older "Sticker · Letter · 600 dpi" / "Sticker · A4 · 600 dpi" stay for the files that name them (`legacy: true`; the Preset list offers them only to a tag that has one; the Library keeps them in Built-in only) |
| The default thickness | **0.10 mm, flagged "measure yours"**: the sticker as it sits on the part, liner peeled off. Printable inkjet vinyl is a 3-4 mil (0.08-0.10 mm) face plus its adhesive, about 0.10 mm; the sheet with its liner measures about 0.2 mm, but the liner is not on the part, and the frame sits on the paper's top (t over the face). Measure a peeled sticker stuck to glass, the calipers zeroed on the glass |
| Suggestions | Paper thickness has a **Stocks** list beside it (a pick fills the value in; it can still be typed): vinyl liner off 0.10, paper label 0.08, vinyl + laminate 0.18, a sheet with its liner 0.20 (marked "not what is stuck on"). `core.make.PAPER_STOCKS`, served as the row's `suggestions` |
| A preset pick | an inkjet preset picked for a tag makes it that preset's sticker (its rule, paper, page; the Perimeter kept); a 3D preset on a sticker makes it 3D printed; a 3D preset on a 3D tag leaves `make` alone (`plan/newtag._make_into`) |
| The Preset row's match | `core.presets.same_machine`: two inkjet presets of which one makes rule-2 tags match only with the same rule, page and paper, so a rule-2 Letter tag reads "Inkjet · Letter vinyl", an A4 one "Inkjet · A4 vinyl", an old one "Sticker · Letter · 600 dpi" |
| The Library | an inkjet card's Info (paper size, thickness, page margins, dots, make rule) and its own Edit form (`schema_2d`: Inkjet printer, Paper size, Paper thickness, Page margins, Dots per inch, then cells, tag and label rows); a dpi change re-derives the dot (`line_mm` = 25.4 / dpi) |

### The page lint (CF-6, inkjet half) and Auto (Q2, Q3)

| | |
|---|---|
| The max | the printable area the sheet places in: the page less its margins, the footer and the scale bars' band (`core.sheet.printable_options`: Letter 195.9 × 233.4 mm portrait, 259.4 × 169.9 landscape), the sticker as it is or turned 90°, on a portrait or a landscape sheet. So the lint passing means the sheet can place it |
| Over it | allowed, flagged red: an `error` Issue on `numbers.size` ("Over the page by 70.6 mm: the sticker is 266.5 × 266.5 mm, Letter less 10 mm margins prints 195.9 × 233.4 mm (either way round, portrait or landscape). It still builds; the sheet will not place it..."), `ok` stays true; Perimeter = Profile puts it on `settings.make.perimeter`. The canvas draws the cut line red; the summary line is red |
| Fits only turned | an `info`: "fits Letter turned only: the sheet turns it (or print landscape)" |
| Auto (a new tag's default, Q2) | never picks a sticker over the printable area: when the face's own Auto sticker is over it, the fit runs again on the face clipped to a printable-sized box centred on the clear rectangle the size came from, each way round (Q3: it turns when that fits), and keeps the best that fits (most markers, then the largest); an `info` says it was capped. When the face's Auto fits, rule 2 picks exactly what rule 1 does. Perimeter = Profile: no cap (the paper is the outline; the lint says so) |
| Rule 1, 3D | no lint, no cap (they store no page; 3D is a placeholder) |

Code: `core/sheet.py` (`printable_options`, `fit_area`), `core/make.py` (`printable_mm`, `page_fit`, `lint_text`), `plan/evaluate.py` (`cap_to_page`), `plan/plan.py` (`sticker_issues`).

### The sheet's Sticker margin and Cut lines (Q7)

"Only in export sheet."

| | |
|---|---|
| `core.sheet.SheetSettings.sticker_margin_mm` (new, 0) | white paper round each sticker: `layout_stickers` grows each cut outline first (`grown_outline`: the outer loop mitred out, the holes as they are), so what is placed, drawn and written to sheet.json (`outline_mm`, `outline_page_mm`) is the sticker as cut |
| `cut_marks` (REF's) = Cut lines | off: no cut line, no crop mark |
| sheet.json | `sticker_margin_mm` / `cut_lines: false` only when not the default, so every sheet made before is byte for byte the same |
| Threaded through | `scene/sheet.py` (`sheet_settings`, `sticker_layout`, `sticker_files`), `scene/export.print_bundle`, the routes `sheet.svg`, `sheet.json`, `print.pdf`, `export/print`, `verify/sheet` (`sticker_margin_mm` 0-20, `cut_lines`), `verify/sheet_check` (the outline step skipped when the cut lines are off), the design file's `sheet` key |
| The Print dialog | Page, Landscape, Layout, Page margins, **Sticker margin**, **Cut lines**; the preview follows them |
| New tags | no `make.margin_mm` / `cut_line` (rule 2 has none); a rule-1 tag keeps its own rows (shown only for rule 1) and plans as before |

### Shift (CF-2, P3)

`settings.shift = {"rule": 1, "x_mm", "y_mm"}`: a sticker moved off where the fit puts it (the centre of its clear rectangle; a plain profile's centre) along the target's own u / v. Absent = centred, bit for bit. The ink, the ids, the layers in the pattern frame are unchanged; the pattern frame and OpenCV's frame move by exactly (x, y) (`placement.shift_mm`). Warns when the shifted sticker runs off the face (Marker) or the marker off the outline (Profile), or covers a hole. A 3D tag reads it and does not move (an info). The inspector: Shift X / Y on the Marker tab with a reset; the canvas: the selected sticker's crosshair, a drag in 0.5 mm steps (Alt: free), previewed live. The design sugar: `"shift": [x, y]` (and `"paper_mm"`: a tag's own paper thickness).

### The Studio

| | |
|---|---|
| Inspector | Inkjet first on a sticker: the Make tab named Inkjet with Paper thickness (+ Stocks), Paper size, Page margins and the grey t/2 line; the red lint row on Marker size; Shift on the Marker tab; 3D rows as they were. All from `plan/fields.py` (`GET /api/form`): new rows `settings.make.page`, `settings.make.page_margin_mm`, `settings.shift`; Sticker margin / Cut line shown for make rule 1 only (`show_when.values` on `settings.make.rule`) |
| Canvas | the Shift crosshair; an over-page sticker's cut line red |
| Print / sheet dialog | Sticker margin, Cut lines (from the file's `sheet`) |
| File › Open | the three older examples (forearm, plate_charuco, sticker_sheet) are gone from the list: the gallery covers them (the files stay for the tests; `GET /api/design/files` still lists them) |
| Gallery | a new group **Inkjet stickers (2D)**, second after the basics: `inkjet_paper` (rule 2 in 3D: real 0.10 mm vinyl and 2 mm "paper" to see the inset), `inkjet_presets` (Letter and A4 vinyl, a tag's own 0.18 mm), `page_lint` (a typed 200 mm marker flagged red, and Auto capped at the page), `shift` (centred, shifted 20, 8, a shifted disc); `sheet_options` in the sheet group (3 mm Sticker margin, Cut lines). The sticker examples that named the older Letter preset (two_ways, ids, labels_where, trim, sheet_tight, sheet_spaced) now use Inkjet · Letter vinyl (same sizes, ids and labels; the black now inside the paper). The manifest's new `lint` key counts the error rows an example shows on purpose (page_lint: 1); the gallery tests read it |

## 2. Verify

### WYSIWYG still holds (design note M6 g)

`tests/verify/test_sheet_rule2.py`: eleven stickers (rule 1 and rule 2; single, grid, ChArUco; labels; corner marks; the Ø53 disc with four holes; a D-shape; a shifted one; one on 2 mm paper), Letter, Spaced and Tight, Sticker margin 0 and 2.5 mm, rasterised by pdfium at 600 dpi, each sticker compared with its plan and read by OpenCV at true scale:

| Run | ink XOR | marker side | label IoU min | outline | bars |
|---|---|---|---|---|---|
| spaced, margin 0 | 0.23 % | 0.012 mm | 0.983 | 0.072 mm | 0.009 mm |
| spaced, margin 2.5 | 0.12 % | 0.009 mm | 0.977 | 0.097 mm | 0.009 mm |
| tight, margin 0 | 0.27 % | 0.009 mm | 0.978 | 0.072 mm | 0.009 mm |
| tight, margin 2.5 | 0.12 % | 0.011 mm | 0.976 | 0.072 mm | 0.009 mm |
| bars | <= 2 % | <= 0.15 mm | >= 0.9 | <= 0.15 mm | <= 0.1 mm |

Every id read; the disc's four holes found. Cut lines off: every check passes with the outline step skipped, and the raster has no grey cut pixel away from the ink. A sticker over the page is rejected by the sheet with its reason (the plan's red row said so). The older 12-sticker scene (`test_sheet_wysiwyg.py`, rule 1) passes unchanged.

### The tests (new behaviour, no REF: properties and OpenCV)

| File | Checks |
|---|---|
| `tests/plan/test_make_rule2.py` (111) | every layout × turn × mark × label: parts, combines, z ranges, nothing over the paper, the frame z = t, white + black = cut area × t, black = ink area × t/2, the top view = rule 1's, closed meshes; t 0.05 / 0.1 / 0.18 / 2 mm × Marker / Profile; OpenCV + PnP within 0.1 mm / 0.1°; the reading (margin / cut line ignored, a junk page, clamped margins, rule 2 on a 3D tag = rule 1); the label's white; which presets stamp rule 2, a frozen copy without the key rule 1; a preset pick; the `sticker_sheet` example still rule 1; `plan_sticker` (the bodies in build order) |
| `tests/plan/test_page_lint.py` (15) | the printable area = what the sheet places, each page each way; turned / landscape; a typed size red and still built, A3 clears it; Profile's lint on the perimeter; no lint on rule 1 / 3D; Auto capped; a long board turned; Auto unchanged where it fits; a property over 72 random faces × pages × margins × layouts: Auto never over the page |
| `tests/plan/test_shift.py` (62) | the frame and OpenCV's move by exactly (x, y) for every layout × turn × shift × rule, the ink unchanged; absent = 0 bit for bit; OpenCV + PnP; a 3D tag unmoved with an info; off the face, off the outline, over a hole; junk |
| `tests/core/test_sheet_options.py` (12) | margin 0 / cut lines on = the sheet as before (summary and PDF bytes); every outline grown by m, the holes kept, the ink unmoved; a 96-point disc grown; cut lines off draw no cut line or crop mark, the same places and ink; a margin can turn or reject a sticker |
| `tests/verify/test_sheet_rule2.py` (8) | the WYSIWYG table above |
| `tests/server/test_2d_api.py` (7) | the form's rows; `/api/new` under each preset; the Preset match; a pick; the Library (collection, Info, `schema_2d`, a 1200 dpi save; its limits against normalise); every sheet route's margin / cut lines; the sugar |
| `e2e/tests/inkjet.spec.ts` (3) | the inspector's Inkjet rows, a Stocks pick, the red lint (row, summary, cut line), Auto's capped info, a bigger page clearing it; Shift typed, dragged, reset; the Print dialog's Sticker margin / Cut lines and its preview |
| Changed on purpose | words (Inkjet printer / Paper thickness), the built-in lists (vinyl first), M6b.1 (`stickers.spec.ts`: a new sticker is rule 2: z 0.1, no margin row, Profile gives the white), Open's examples (`audit2.spec.ts`), the gallery's `lint` |

### The check

`.venv/Scripts/python tools/check.py` (full), on the lane after the second merge of `main` (`ceee19e`: lane/fusion-core 8f66ec2 and lane/scene-fixes 0e62f83) and `plan_sticker`, on ports 5380 / 5381 (`ARUCO_STUDIO_API_PORT` / `_UI_PORT`: 5370 / 5371 are Zach's preview; nothing listened on 5380 / 5381 after):

| Group | Result |
|---|---|
| adapters | 97 passed in 77 s |
| core | 7,433 passed, 4 skipped in 48 s |
| plan | 735 passed in 240 s |
| scene | 56 passed in 24 s |
| server | 114 passed in 39 s |
| verify | 128 passed in 125 s |
| studio | build + vitest passed in 10 s |
| e2e | 62 passed, 1 skipped (7.3 m) in 442 s |
| **all** | **OK in 1008 s** |

`tools/mesh_digests.py --check`: 947 cases, 0 differ (the 824 evaluate goldens replay in `plan`). `tools/check.py --trace`: missing 0. `tools/spec_status.py --check`: 92 passing, 4 planned, 0 failing (the orchestrator adds this lane's rows to `docs/spec.json`).

The second merge kept both sides of `scene/design.py`'s sugar: lane/scene-fixes' `perimeter` (a 3D tag's Trim excess) and this lane's `shift` / `paper_mm`. Its write-back fix (typed ids kept after an edit) also fixed the gallery copies here: editing the `shift` example's middle sticker no longer sends the others to #0.

## 3. Screenshots (light)

| File | Shows |
|---|---|
| `2d_core_inkjet_rows.png` | the inspector of an inkjet sticker on its Inkjet tab: Preset, Made by Inkjet printer, Paper thickness with Stocks and the grey t/2 line, Paper size, Page margins |
| `2d_core_lint.png`, `2d_core_lint_inspector.png` | `page_lint`: the typed 200 mm sticker's red cut line beside the capped Auto one; the red row under Marker size and the red summary |
| `2d_core_shift_drag.png` | a Shift drag: the crosshair, the live preview, "shift 14, -6 mm" |
| `2d_core_print_dialog.png` | the sheet dialog: Page margins, Sticker margin 3 mm, Cut lines, the preview |

## 4. For the Fusion sticker node (M7.4): the API to call

All pure, stdlib only, in `aruco_studio.core` / `aruco_studio.plan` (re-vendor the add-in's copy from this lane once merged; nothing in `adapters/` changed).

**The bodies: `aruco_studio.plan.plan_sticker(spec)`** (new, `plan/plan.py`; a TagSpec, its dict, or a TagPlan): None for a tag that is not a built sticker, else

```text
{"rule": 2, "thickness_mm": t,
 "bodies": [  # in build order
   {"part": "sticker", "role": "paper",  "op": "new", "into": None,      "colour": "white", "z_mm": [0, t],   "steps": [...]},
   {"part": "pocket",  "role": "pocket", "op": "cut", "into": "sticker", "colour": "none",  "z_mm": [t/2, t], "steps": [...]},
   {"part": "ink",     "role": "black",  "op": "new", "into": None,      "colour": "black", "z_mm": [t/2, t], "steps": [...]}],
 "frame": {"opencv": 4x4, "opencv_target": 4x4, "pattern_in_target": 4x4, "z_mm": t},
 "cut_line": {"kind": "marker" | "profile", "outer", "holes", "rect"?},
 "page": {"page", "margin_mm", "size_mm", "fits", "how", "over_mm", "printable_mm"},
 "lint": [the error Issues: the red page row],
 "record_make": settings.make as stored}
```

Each step: `{"name", "step": "add" | "sub", "z_mm": [lo, hi], "polygons": [{"outer", "holes"}]}` (mm, the pattern frame: the pattern's centre on the face, u = image right, v = image up, z out of the face; a "sub" step is a cut tool of its own body, already padded past the slab, REF `part_body`'s order). So the node: extrude the paper's polygon [0, t] as a New body; build the pocket's footprint (its add / sub steps) [t/2, t] and Combine-Cut it from the paper; build the same footprint as a New body, black; one Joint Origin at `frame.opencv` (z = t, on the paper's top). Rule 1 (an older tag) gives two bodies: `sticker` [0, t], `ink` [t, t + 0.01]. Under it `plan_tag(spec).data` has the same in `parts`, `layers`, `combines`, `frames`, `sticker`.

| What | Call / field |
|---|---|
| a new node's `make` | `core.make.new_make("sticker", preset["profile"])` or `core.form.new_tag_settings(s, has_body, preset=preset)` -> `{"rule": 2, "by": "sticker", "thickness_mm", "perimeter", "page", "page_margin_mm"}` |
| a stored node's | `core.make.make_of(settings)` -> `(Make, notes)`; `Make.inset` (rule 2), `.paper_z` (0, t), `.ink_z` (t/2, t), `.top_mm` (t: the frame), `.ink_mm` (t/2) |
| the inkjet preset fields | `preset["profile"]`: `kind` "sticker" (shown "Inkjet printer"), `page` (letter / a4 / legal / a3 / tabloid / a5), `stock_mm` (the paper thickness, 0.05-2.0), `margin_mm` (the page margins, 0-50), `dpi` (`line_mm` = 25.4 / dpi), `make_rule` (2; absent = 1); built-ins `core.presets.vinyl_preset("letter" / "a4")`; `core.presets.inkjet_schema()` the Edit rows; `core.presets.same_machine(a, b)` with `same_print` for the Preset row's match; `core.make.PAPER_STOCKS` the thickness suggestions |
| the page-lint rows | the plan's `warnings`: `{"field": "numbers.size", "level": "error", "text": "Over the page by ..."}` (Profile: field `settings.make.perimeter`), `ok` stays true; `info` on `numbers.size` "Auto size: capped by the page ..." / "fits Letter turned only ..."; `info` on `settings.make.thickness_mm` "the black is printed t/2 into ..."; directly: `core.make.page_fit(w_mm, h_mm, make)` -> `{fits, how, over_mm, worst_mm, area_mm, page, margin_mm}`, `core.make.lint_text(fit, w, h)`, `core.sheet.printable_options(page, margin_mm)`, `plan.plan.sticker_size_mm(guides)` (the cut outline's box) |
| Shift | `settings.shift = {"rule": 1, "x_mm", "y_mm"}` (the target's u / v), `core.make.shift_of(settings)`; the plan moves the frame (`placement.shift_mm`) and warns on `settings.shift` |
| the sheet options | `core.sheet.SheetSettings(sticker_margin_mm=..., cut_marks=...)` into `core.sheet.layout_stickers(items, settings)` (items: `scene.sheet.sticker_item(tag, plan)`, the cut outline and the plan's black); or `scene.sheet.sticker_files(scene, plans, page, landscape, mode, margin_mm, proofs, date, sticker_margin_mm=, cut_lines=)` -> sheet.pdf / .svg / .json; `core.sheet.grown_outline(outline, d)` |

The volumes to gate on (F-M7.5, t = 0.1): paper + black = the cut outline's area × t; black = the ink's area × t/2; one Joint Origin at t (`tests/plan/test_make_rule2.py` checks the same on the plan's own meshes).

## 5. Questions for Zach

1. **Measure your vinyl.** The default is 0.10 mm (liner off). Peel one printed sticker, stick it to glass, zero the calipers on the glass: the number goes in the vinyl preset (or the tag's Paper thickness).
2. **The new-tag preset.** A tag made with nothing picked still uses "Default" (the 3D printer). Since 2D is the only path now, should the Studio's new-tag preset be "Inkjet · Letter vinyl"?
3. **The printable area includes the sheet's footer and scale bars** (Letter: 195.9 × 233.4 mm, not 195.9 × 259.4), so a sticker the lint passes always lands on the sheet. Or should the bars move aside for a big sticker?
4. **A Sticker margin round a Profile sticker** grows its outline (the paper overhangs the face by the margin); the holes stay. Is that what you want, or the margin on Marker stickers only?
5. **Your inkjet's real margins**: the presets keep 10 mm page margins (most inkjets need 3-6 mm). Say your printer's and the presets follow.
