# M6: stickers, profiles, sheet layout, print (design note, 2026-10-16 evening)

A plan, nothing built. It turns `docs/feedback/2026-10-16-stickers-profiles-print.md` (FB-1..FB-16) into work for ArUco Studio and for the Fusion add-in. It extends `manufacturing_intent.md` (Made by: 3D printed / Printed sticker); where the two differ, this note wins.

| | |
|---|---|
| Written against | ArUco Studio `main` at `2fabae1` (M1-M4 built, the audit fixes landing); REF = cad-exporter `aruco-fusion-plugin-0e9bcb` at `9829cd4` (the v2 dialog ON, ARROW_TYPE_BOX ON), read only |
| Keeps | every versioned rule as it is: `SPEC_VERSION 2`, `CELL_RULE 1`, label `RULE 2` (a new rule 3 is added beside it), `ORIGIN_RULE 2`, trim `RULE 1`, `MAKE_RULE 1` (from the earlier note), `bam_aruco_presets/1`, `arucostudio.scene/1`, `arucostudio.tagplan/1` |
| Zach's workflow it serves | click a face, the tag places itself; set the board, the mark, a label; click 3 more faces; make the ids unique; press Print |

## 0. The plan in one paragraph

The **preset is the machine**: picking "Prusa MK4 0.6" or "Sticker printer, Letter, 600 dpi" says how the tag is made, and the form shows only that machine's rows. The profile is our own `Target.loops_mm` (already); the placement is the largest clear rectangle (already), with a new **Holes: avoid / ignore** switch. A sticker has a **Perimeter: Marker / Profile** (on a 3D tag that row IS Trim excess). The sheet packs stickers **tight** (shared cut lines) or **spaced** (gaps with the id and name), draws every cut line (outline, holes), and carries the scale bars. **One plan feeds the Studio canvas, the Fusion body and the PDF**, and a test rasterises the PDF and compares it with the plan. **Multi-face**: several tags in one go, the same settings on each. **Print** opens the print dialog from the Studio and from Fusion. Four milestones: M6a (core, plan, scene, sheet, server), M6b (Studio UI), M6c (print), M7 (Fusion, gated).

## a. The machine preset is the method (FB-1, FB-2, FB-15)

### What changes against `manufacturing_intent.md`

| Earlier note | Now |
|---|---|
| "Made by" is the first row of a new tag; the Preset list is filtered by that choice (1.2, 2.6) | The **Preset** row is first. The preset carries the method. "Made by" is a read-only line under Preset: `Made by: Printed sticker · 600 dpi · Letter` |
| A preset never holds Made by | A preset holds its **kind** (`profile.kind`): it is a machine |
| The Library shows one kind at a time | The Library shows both, in two collections: **3D printers** and **Sticker printers** |
| `POST /api/new` takes `made_by` | `/api/new` takes `preset` (exists); `made_by` stays as an override for scripts |

Everything else of the earlier note stands: the stored key `settings.make` (rule 1; absent = 3D printed, bit for bit today's tag), the sticker's plan (stock + ink, the frame on the ink top), one scene and one ledger, the mixed export.

### The preset shape (additive, `bam_aruco_presets/1` kept)

| Key | 3D printer | Sticker printer |
|---|---|---|
| `profile.kind` | `"print3d"` (default when absent, so every file today reads as 3D) | `"sticker"` |
| `profile.name`, `source` | the PrusaSlicer profile | the printer's name (typed) |
| `profile.nozzle_mm`, `line_mm`, `layer_mm`, `first_layer_mm` | as today (FB-2: line width and layer height are already there) | `line_mm = 25.4 / dpi` (the smallest dot), the rest 0 |
| `profile.dpi` | 0 | 600 (300 / 600 / 1200) |
| `profile.page`, `landscape`, `margin_mm` | — | `"letter"` / `"a4"` / ... (`core.sheet.PAGE_SIZES_MM`), false, 10 |
| `profile.stock_mm` | — | 0.1 (the default of `make.thickness_mm`) |
| `profile.sheet` | — | `"spaced"` / `"tight"` (the sheet's default mode, FB-8) |
| `cells` | as today | `{"of": "cell", "step": "line"}` = whole dots |

`core.presets.normalise` keeps the new keys and defaults `kind`; REF's `normalise` drops what it does not know, so a Studio file still loads in the add-in.

### Built-ins

| Collection | Cards |
|---|---|
| 3D printers | **Default** (0.5 mm steps, today's), one per PrusaSlicer "Aruco" profile (read only) |
| Sticker printers | **Sticker · Letter · 600 dpi**, **Sticker · A4 · 600 dpi** (whole dots, stock 0.1 mm, min cell 1 mm, label stroke 0.2 mm, spaced) |
| My presets | mine, either kind; Edit sets the kind's rows only |

### Picking a preset

| Event | Effect |
|---|---|
| a new tag under a preset | `settings.make.by` = the preset's kind; the form shows that kind's rows (the tables of `manufacturing_intent.md` 2.1-2.5, plus the rows of sections c and d below) |
| a preset of the other kind on an existing tag | the method changes: a plain edit in the Studio (a locked tag refuses, as before); a structural edit in Fusion (rebuild) |
| a tag whose settings match no preset | the Preset row says "custom"; `make` stays what it is |
| the last preset | remembered (`last` in the presets file, exists); the next new tag starts from it |

### One environment, both kinds (FB-15)

Ids are per dictionary family, never per kind (`core.numbering.family`; `scene/ids.py`; Fusion: the ArUco IDs node). A sticker #3 and a printed #3 are one duplicate and Renumber fixes both. Nothing to build here beyond the badge (`2D` / `3D`), the IDs table's **Made by** column and the canvas filter of the earlier note (4).

## b. The profile (FB-3)

**Confirmed: `plan/target.py` `Target.loops_mm` is the one representation.** The outer loop first, then the holes, mm, in the target's own frame; even-odd decides inside. The Fusion adapter fills it from a face (`adapters/fusion/target.py of_face`: every edge stroked at `STROKE_TOL_CM = 0.005`, REF's `face_loops_2d`) or a sketch profile (`of_profile`, curves stroked at 0.01 cm); the Studio from its target editor (`POST /api/target`); the palette faces at a 0.05 mm chord (`core/faces.py CHORD_TOL_MM`). The fit (`core/autosize.fit_on_loops`), the label's white region, the trim and the sticker's outline all read these loops.

Gaps, and what to do:

| Gap | Today | Do |
|---|---|---|
| Arcs and splines are polylines | a face: 0.05 mm chord; a sketch curve: 0.1 mm chord | one constant `plan.target.CHORD_MM = 0.05` for both; the cut line on paper is then within 0.05 mm of the true arc (a 0.1 mm hairline hides it). A circle of 96 points (the Studio's disc) is fine |
| Two outer loops | not checked: a hole outside the outer loop is read even-odd as a second island | `plan/spec.check`: a loop not inside the first is an `error` on `target.loops_mm` ("loop 2 lies outside the outline: one target per face; pick the faces one by one or together, section h") |
| A hole inside a hole (an island) | cannot come from Fusion (an island is its own face); even-odd would read it as material | no change; the check above names it when the Studio types one |
| Loop direction | `from_loops` fixes it; `from_dict` does not; nothing downstream cares (even-odd, `fill-rule="evenodd"`) | `from_dict` normalises too (outer counter-clockwise, holes clockwise), so the sheet's cut paths come out consistent |
| The sticker's outline in the pattern frame | `TagPlan.guides.target` already gives the loops turned into the pattern frame | the sticker's cut polygon reads it (section d) |
| Many points (a fine disc) | the clear-rectangle search is capped (`_CLEAR_CAP` 30,000 cells) and was measured on Zach's GIM43 disc (five loops) | measure once in M6a: a 96-point disc with 3 holes under 50 ms per fit; note the number in the status file |

## c. Placement (FB-4, FB-5)

### Today

`core/autosize.largest_clear_rect(loops, aspect, angle_deg)` is an exact branch and bound (proven bound `CLEAR_EPS_M` = 0.02 mm) for the largest rectangle inside the outer loop and outside every hole; `fit_on_loops` sizes the tag on it. `plan/evaluate.py` calls it with `angles_deg = (0,)` for a single marker and `(0, 90)` for a board. A plain rectangle takes the box answer exactly. Nothing to build for FB-4: it is the design.

### Arbitrary angles: not now

| | |
|---|---|
| What it would give | a bigger marker on a face whose clear rectangle is diagonal (a chamfered plate, a hexagon, a disc with holes on a diagonal). On a rectangle (the forearm's four sides) nothing |
| What it costs | the search runs once per angle class (mod 90): 15° steps = 6 searches instead of 1-2; the Origin turn, the label, the mark, the Joint Origin and the sheet all already accept any angle (`placement.angle_deg`, `jo_decompose`), so nothing else changes |
| Risk | a turned tag reads at a turned angle in the camera: harmless (calibration measures the pose). A diagonal tag on a rectangular sticker: the cut line is still the outline (section d), so no waste |
| Recommendation | **leave it at 0 / 90** for M6. The API hook is there (`fit_on_loops(angles_deg=...)`). If a real face asks for it, add `settings.fit = {"rule": 1, "angles": "square" / "any"}` later, absent = today |

### Holes: avoid / ignore (FB-5), defined exactly

| | |
|---|---|
| Stored key | `settings.holes`: `"avoid"` or `"ignore"`. **Absent = avoid** (today's tag, bit for bit). Junk reads as avoid with a `warn` on `settings.holes` |
| Row | Marker tab, under Layout: **Holes**: Avoid (the tag keeps clear of them) / Ignore (the tag may cover them). Shown only when the target has holes. Both kinds |
| The fit | `avoid`: `fit_on_loops(target.loops_m())` as today. `ignore`: `fit_on_loops([outer loop])`: the holes are not in the search; the candidates list (`/api/candidates`) the same |
| The label's white | `avoid`: the region is the face with its holes (today). `ignore`: the region is the outer loop only; a label may sit over a hole |
| The trim (3D) | unchanged: Trim excess still refuses when a hole is cut through, unless Cut anyway |
| The sticker's cut lines | unchanged by this switch: Perimeter = Profile draws every hole (section d). With `ignore` the marker may cross a hole: the plan says `warn` on `settings.holes`: "the marker crosses hole 2: cut the hole out after sticking, or Avoid" |
| A 3D tile over a hole | the white tile bridges the hole (printable, but the hole is filled): `warn` on `settings.holes`: "the tile covers 2 holes" (REF already warns this for a sketch area's box) |
| The views | an ignored hole is drawn dashed in the 2D view (`guides.target_ignored`), solid when avoided |
| Record | `settings.holes` rides in the record like `cells`; a new tag always stores it (`"avoid"`), an edit writes it only when changed |

## d. Perimeter: Marker or Profile (FB-9, FB-11)

One row, **Perimeter**, on the Marker tab for both kinds:

| Choice | A sticker (2D) | A 3D tag |
|---|---|---|
| **Marker** | the sticker is the marker's rectangle: the pattern + quiet zone + `make.margin_mm`, always a rectangle; its corner cut when the mark says so | **= Trim excess, Both**: the body is trimmed to the tag's outline (`settings.trim {rule 1, axes both, margin}`); New body: the tile already is the outline |
| **Profile** | the sticker keeps the profile's outline, any shape, holes included | = Trim excess Off: the body keeps its outline |
| Stored as | `settings.make.perimeter` (`"marker"` / `"profile"`, default **marker**) and `make.margin_mm` | `settings.trim` (exists, rule 1; absent = Profile). Advanced > Trim excess keeps Width / Height for the one-axis cases; the row then reads "Marker (width only)" |

### What the sticker's plan holds

| | Perimeter = Marker | Perimeter = Profile |
|---|---|---|
| `layers`: `sticker` (white, z `[0, t]`) | the rectangle (quiet ring + margin), one corner cut by the mark | `guides.target` (the outer loop with its holes, in the pattern frame) |
| `layers`: `ink` (black, z `[t, t + INK]`) | the cells, `mark_triangle`, the label's boxes, exactly as the pattern layer | the same |
| `guides.cut_line` | the rectangle, `[u0, v0, u1, v1]` | `{"outer": polygon, "holes": [polygon, ...]}` |
| `warnings` | the marker crossing a hole (Holes: ignore) | the same; plus `info` "the outline has N holes: N extra cuts" |
| The sheet (section f) | packed as a rectangle | packed by its box; the outline and every hole drawn as cut lines (grey 0.55, 0.1 mm hairline, `core.sheet.CUT_GREY` / `CUT_LINE_MM`); a hole under 3 mm gets a small cross (a punch, not scissors) |
| Orientation on paper | as seen from above = as seen from outside the face; **never mirrored**, so the cut shape matches the face when stuck. An asymmetric outline tells which way round (Zach's point) |

### The label rule (FB-11)

With Perimeter = Marker and margin 0, the only white outside the black is the quiet zone, and ink there costs (-11 pp, `core.label` docstring). So:

| | |
|---|---|
| The rule | the label's white region for a sticker is its cut polygon (Marker: the rectangle; Profile: the outline). `core.label.plan_label(region=...)` then fits the label outside the clear zone, or refuses with today's words. No new rule number |
| The form | Perimeter = Marker and margin 0: Position offers **On the black** only ("On the white" hidden). Margin > 0 or Profile: both |
| A stored `place: white` that has no white | `warn` on `settings.label.place`: "no white outside the quiet zone (Perimeter = Marker): the label goes on the black"; `place` is read as `auto` (black first). Nothing is refused that was built before: a 3D tag is not touched by this |
| The hint when the black has no room either | the refusal (today's) plus: "Perimeter = Profile, or a sticker margin of N mm, gives white for it" |

## e. Labels (FB-10, FB-12, FB-13)

| FB | Today (`core/label.py`, rule 2) | Change |
|---|---|---|
| FB-10 corner triangle; label on the black or the white | exists: `settings.corner_mark triangle`, `label.place black / white`, both as layers; on a sticker they become ink (section d) | none in the core. The sheet prints them from the plan (section g): this closes REF OI-PDF-LABEL |
| FB-12 auto placement, offsets by hand | exists: `position auto / manual`, `x_mm`, `y_mm` (the block's centre), the legacy nudge honoured | none |
| FB-13 ChArUco: only a black checker square | **partly**: `row auto` on a ChArUco board resolves to `square` (the top-left black square, `charuco_square`), cap <= 0.22 square, 0.1 square in from its edges, 0.35 square from every chessboard corner. BUT the form also offers the markers' border rows (`bottom / top / both`) and **On the white** for a ChArUco board, and a manual position must stay inside the TOP-LEFT square | see below |

### FB-13, exactly

| | |
|---|---|
| The form (Studio and Fusion) | a ChArUco board's Position offers **In a black square** only; Row hidden; Side hidden |
| A stored ChArUco label on a border row or on the white | built as it was (rule 2 keeps its layout: existing tags never change); `warn` on `settings.label.row` / `place`: "a ChArUco label belongs in a black square" |
| Any black square | **label rule 3**: `position manual` with (x_mm, y_mm) inside ANY black square of the board puts the label there, checked against THAT square (edges, corners); auto still picks the top-left. Rule 2 only accepted the top-left square (its `_manual` check uses `charuco_square`). A new tag stores `rule: 3`; a stored label keeps its rule; `RULES = {1, 2, 3}`; `plan/fields.py` lists 3 |
| Why a new rule and not a fix | rule 2 refused a manual spot in another square; rule 3 accepts it. A refusal turning into a built label would change a golden's plan. Rule 3 beside rule 2 changes nothing stored |
| The sheet | draws the plan's label (the pixel font boxes) in the square; the sheet's own grey "#0-3 / 5x7 / name" text (`core.sheet._marks`, `CHARUCO_LABEL_GREY`) is OFF when the item carries the plan's ink (section g), as are its per-marker "#id" border texts and its grey triangle |
| Verify | `tests/verify`: a ChArUco label in a non-top-left square still reads every chessboard corner and every id; the M2 finding 2 (a plain detector reading id 17 in a label's text) is re-checked on the pixel font in each square |

## f. The sticker sheet (FB-7, FB-8)

Single, grid and ChArUco are already `core.sheet.PrintItem`s and the scene already writes a PDF (`scene/sheet.py`, audit C1). What is added:

### Items

| `PrintItem` field | New | Meaning |
|---|---|---|
| `outline_mm` | yes | the cut polygon with holes, in the sticker's own frame (mm, y up); None = the rectangle as today |
| `ink_mm` | yes | the plan's black top view (`plan/mesh.top(plan)["black"]`): cells, mark, label. When given, the sheet draws THIS and switches its own marks off (`id_mark`, `top_label`, `orient_mark`, the ChArUco text) |
| `caption` | yes | the words for the gap in spaced mode: `#12 · forearm_left · 4X4_50 · 28.0 mm` (`identity_label` + the tag's name) |
| `made_by`, `key` | | for `layout_summary` and `markers.json` |
| the old fields | | kept, so REF's sidecar path keeps working unchanged |

### Two layouts (`SheetSettings.mode`)

| | **Spaced** (default) | **Tight** |
|---|---|---|
| Gap | `gap_mm` (4) between cells; the caption under each sticker; crop marks at each sticker's corners (short lines outside the corner, never inside the sticker) | **0**: neighbours share a cut line; no captions on the page (the id is in the sticker's own label if the tag has one); one line per shelf in the margin: "row 2: #12-15 forearm" |
| Algorithm | today's `layout_sheet`: first-fit-decreasing shelves (REF's) | **guillotine shelves**: items sorted by (height desc, width desc), identical sizes kept adjacent so they form a block; one shelf per height; a shelf is a full-width straight cut; inside a shelf the columns are straight cuts. Cuts = shelves + 1 + sum over shelves of (columns - 1). Four identical 30 x 30 stickers in a row: 2 long cuts + 5 short = 7, against 16 for four separate rectangles |
| Odd shapes (Profile) | packed by their bounding box, gap as above; the outline and holes drawn inside the box | packed by their bounding box with gap 0; the outline drawn; the box edges are NOT drawn (only outlines are cut lines), so a shape shares a straight cut only where its box edge is its outline |
| Rotation | 0 or 90 per item (a rectangle longer than the page turns) | the same |
| Pages | letter / A4 / A3 / ... from the preset; never scaled; a sticker bigger than the page is **rejected with a reason** (today's rule) | the same |
| Scale check | the 100 mm and 4 in bars on every page (today) | the same |

True polygon nesting (no-fit polygons, discs packed closer than their boxes) is **not in M6**: Zach's faces are rectangles; a disc wastes 21 % of its box. Listed as `ST-SHEET-NEST`, later.

### Outputs

| File | From |
|---|---|
| `sheet.pdf` | `core.sheet.render_layout_pdf` (vectors; the ink from `ink_mm`) |
| `sheet.svg` | new `core.sheet.render_layout_svg`: the same layout as vectors, for the Studio's preview and print page; the same numbers as the PDF |
| `sheet.json` | `layout_summary` + per sticker: page, x, y, rotation, outline, `made_by`, name, ids: the oracle of the WYSIWYG test |
| `images/<dict>_<id>.png / .svg` | as today |

## g. WYSIWYG (FB-6)

One `TagPlan` per tag. Every shell draws it, none re-derives it:

| Shell | Reads |
|---|---|
| The Studio canvas | `plan/mesh.top` (white, black) + `guides.cut_line` (the 2D view already fills the top view, M3) |
| The Fusion body | the `sticker` and `ink` layers as TBM bodies (M4 `bodies.py`; in the live add-in, section j) |
| The PDF | `PrintItem.ink_mm` = the same `plan/mesh.top(plan)["black"]`; `outline_mm` = `guides.cut_line` |

So a label is on paper exactly when it is in CAD: both read the plan's `label_*` layers.

### The test that proves the page equals the CAD (`verify/sheet_check.py`)

| Step | Check | Bar |
|---|---|---|
| 1 | rasterise the PDF with pypdfium2 (pinned in M2b) at 600 dpi (0.0423 mm / px) | every page |
| 2 | for each placed sticker (`sheet.json`: page, x, y, rotation), crop its box | |
| 3 | render the plan's top view with `verify/render.py` at the same 600 dpi, turned by the sticker's rotation | |
| 4 | **ink**: XOR of the two black masks over the union | <= 2 % (anti-aliasing on the edges is about 1 px wide) |
| 5 | **ids**: OpenCV reads the crop: every id, ChArUco corners, the marker side | side within 0.15 mm of the plan's `marker_length_m` (M2b.7's bar) |
| 6 | **label**: inside each of the plan's label boxes the ink matches the render | IoU >= 0.9 per box; no label box = no ink there |
| 7 | **outline**: the grey cut line (0.55 grey, by threshold) traced as a contour, compared with `outline_mm` | Hausdorff distance <= 0.15 mm; every hole found |
| 8 | **scale**: the 100 mm bar and the 4 in bar measured on the raster | 100.0 +/- 0.1 mm, 101.6 +/- 0.1 |
| 9 | the Fusion body (M7): the sticker node's ink faces, exported as the plan's top view by the gate | the same XOR bar against the plan |

`POST /api/scene/verify?sheet=1` runs 1-8 on the scene's own sheet and reports per sticker; the Studio's Verify drawer shows the worst number.

## h. Multi-face (FB-14)

### Studio: several targets at once

| Piece | How |
|---|---|
| Making four | add one tag, duplicate it three times (Ctrl+D, exists); or **Add to selection**: the New-tag control with N targets picked from the palette makes N tags in a row (`POST /api/scene/tags` x N, one undo step) |
| The same settings on each | **multi-select edit**: with N tags selected the inspector edits them all: a changed field goes to every selected tag (`PATCH` x N, one history entry); a field whose values differ shows "—" until typed; the target editor stays per tag |
| Ids | each new tag takes the next free ids of its family (`scene.number_one`, audit F14); Renumber all for the rest |

### Fusion: ArUco Extrude multi-select

Recommendation: **one node per face, made in one command, in one timeline group.**

| | One node per face (recommended) | One node with several tags |
|---|---|---|
| Fits what is measured | every measured Fusion path is per tag: the record, ONE Joint Origin per tag (JO-OPTICAL, the one-per-tag census), the edit dialog (the v2 dialog edits one node's values), the per-copy IDs parts (they re-split one tag's bodies by one id), Export's rows, the ghost | all of these would need a second shape: a record list, N Joint Origins on one node, a 4-tag edit UI, IDs parts per tag of a node. Months of gates |
| The timeline | N nodes; grouped as **"ArUco Extrude x4"** (a timeline group, as the IDs node groups its parts), so the timeline stays short; one undo step (one command execute) | one node |
| Edit later | double-click one face's node: today's edit | an edit dialog for a set |
| Auto size | per face: each gets its own largest clear rectangle; a typed size applies to all | the same |
| Ids | `aruco_tags.next_free_id(dictionary, count)` once per tag, in pick order, each after the one before | the same |
| Dependencies | each node depends on its own face (Q7) | N dependencies on one node |

The dialog: `setSelectionLimits(1, 0)` on the Profile selection; the ghost draws every face; the Size arrow on the first pick; "4 faces picked: 4 tags, ids #12, #13, #14, #15" under Profile; a face whose fit fails is reported under Profile and the others are still made.

## i. The Print button (FB-16)

### Studio

| | |
|---|---|
| Route | `GET /api/scene/print.pdf?page=&landscape=&mode=`: the sheet as `application/pdf`, `Content-Disposition: inline` (the same bytes as Export) |
| Button | Export menu: **Print sticker sheet…**. The app loads the PDF into a hidden `<iframe>` (a blob URL) and calls `iframe.contentWindow.print()`: Chrome and Edge open the system print dialog on the PDF at **Scale: Default = 100 %**. The page itself says "Print at 100 % / Actual size" above the bars |
| Fallback | Firefox prints the host page instead of the PDF: the dialog then offers **Open the PDF** (a new tab) and says "press Ctrl+P, Actual size" |
| Keeping 100 % | the PDF's MediaBox is the page size, so the viewer's default scale is 1:1; the bars on every page catch a wrong setting; the margin (10 mm) keeps the stickers inside any printer's unprintable edge |
| Test | the OS dialog cannot be driven: the e2e stubs the print call through `window.__studio.printHook`, checks it was called once with the PDF bytes `/api/scene/export/pdf` gives, and pdfium reads those bytes at true size (exists) |

### Fusion

Windows gives three mechanisms:

| Mechanism | What happens | Failure modes |
|---|---|---|
| `os.startfile(pdf, "print")` (ShellExecute, verb `print`) | the PDF's registered handler prints it; Adobe Reader / Foxit show their print dialog; SumatraPDF prints silently to the default printer | **Edge, Windows' stock PDF handler, registers no `print` verb**: `OSError` "No application is associated with the specified file for this operation". A silent handler may print "shrink to printable area" (SumatraPDF's default): the bars catch it, but the sheet is wasted |
| `printto` verb | the same, to a named printer | the same, and needs the printer's name |
| `os.startfile(pdf)` (open, verb `open`) | the PDF opens in the default viewer; the user presses Ctrl+P; "Actual size" | one more click; never fails |

Recommendation: **a Print button that tries the `print` verb when the registry says the handler has it, and otherwise opens the PDF.**

| Step | Do |
|---|---|
| 1 | `winreg` (stdlib): `HKCR\.pdf` default -> ProgID; does `HKCR\<ProgID>\shell\print\command` exist? Cache it per session |
| 2 | yes: `os.startfile(path, "print")`; the button reads **Print**; the info line: "printed through <ProgID>; check the 100 mm bar" |
| 3 | no, or step 2 raised `OSError`: `os.startfile(path)` (today's "Open when done"); the button reads **Open to print**; the message box: "The sheet is open in your PDF viewer. Press Ctrl+P and choose Actual size (100 %)" |
| 4 | the default printer is "Microsoft Print to PDF" or similar: the handler's own Save dialog appears; harmless, the message says so |
| 5 | never a silent print without the bars having been on the page: the sheet always carries them |

The Export dialog keeps its PDF type and its rows (page, landscape, margin); "Open when done" becomes "Print when done" with the step-3 wording when the verb is absent; "Sheet: Spaced / Tight" is a new row.

## j. The Fusion side

### What needs Fusion UI or adapter work

| Item | Where in the add-in | Kind of work |
|---|---|---|
| Preset = the machine: sticker presets in the Preset row and the Library (two collections); a sticker preset shows the Print tab's sticker rows and hides Heights | `aruco_extrude_ui` (ROUTE, the rows), `aruco_preset_library` (collections), `aruco_presets.normalise` (kind, dpi, page) | UI |
| The sticker node (thin stock + ink, `manufacturing_intent.md` 7.2 A) | `aruco_feature.evaluate` (one branch to fixed heights), the record's `fusion.make`, body names as today | feature; the deepest change |
| Holes: avoid / ignore | `aruco_extrude_ui` (one row), `aruco_feature.evaluate` (pass the outer loop only), the record key | UI + one line in evaluate |
| Perimeter: Marker / Profile | `aruco_extrude_ui`: the row writes Trim excess on a 3D tag (exists), `make.perimeter` on a sticker | UI |
| Multi-select, N nodes, one group | `aruco_extrude_cmd` (selection limits, the execute loop, the group), `aruco_preview` (N ghosts) | UI + feature |
| The PDF from the plan's ink, tight / spaced, the Print button | `aruco_export` (the sheet from `aruco_studio.core.sheet` with `ink_mm`), `aruco_commands` (the row, the button, the registry probe) | export; read-only on the design |
| ChArUco label: the form's choices; rule 3 | `aruco_extrude_ui` (Position choices per layout); `bam_cad_core/aruco_label.py` gains rule 3 (the same text as the Studio's) | UI + core text |
| Unique ids across kinds | nothing: the IDs node is per family | — |

### Can the add-in call `aruco_studio`'s core now? Yes, for the export.

| | |
|---|---|
| The first migration step as `docs/FUSION_ADAPTER.md` 3.3 lists it | step 1: "the add-in imports `aruco_studio.core` for presets, Prusa, remembered options, marker table, export rows: no risk" |
| Why the sheet is the right first piece | `core.sheet` is REF's `print_sheet` verbatim plus the new layout modes; `core.autosize` is REF's `aruco_autosize` verbatim (the placement needs no migration: it IS the same text; Holes: ignore is a call-site change in REF's evaluate). The PDF export reads the design and writes files: it changes no node, no record, no Joint Origin |
| How the plan's ink gets to the add-in | `aruco_studio.plan.plan_tag(spec)` on the node's stored spec (`adapters/fusion/records.spec_of_node`, M4.4: 814 golden cases replan equal) + `plan/mesh.top`. The 824 evaluate() goldens say the plan's ink equals the node's bodies |
| Packaging | the add-in folder gets `ArucoMarkers/aruco_studio/{core,plan}` copied by a sync tool (like `fusion-aruco`'s `tools/sync_from_cad_exporter.py`, the other way), pinned to a Studio commit in `aruco_studio/VERSION`; `.py` only (Q84), no `bam_` prefix (Q83), stdlib only (the purity test) |
| The gate | F1-lite, read only: for every ArUco Extrude node of the test documents, `plan_tag(spec_of_node)` gives the node's own `record_digest`; then the exported PDF passes the WYSIWYG test of section g |
| What waits for the full migration | the live dialog's placement and evaluate (step 4), the bodies (step 5): the sticker node and Holes: ignore touch REF's `evaluate`, so they are done in REF's own code (small, gated), not through the adapter |

So M7 is: vendor the core and plan; the PDF export through them; then the dialog rows; then the sticker node; each gated.

## k. Milestones

Each is built by ONE agent. M6a first; M6b and M6c after it (M6c may run beside M6b: disjoint paths); M7 after M6a, in the cad-exporter worktree, Fusion-gated. The earlier note's M6a / M6b / M6c paths and checks (`manufacturing_intent.md` 10) fold into these; its M6.1-M6.11 checks keep their numbers.

### M6a: core, plan, scene, sheet, verify, server

| | |
|---|---|
| Goal | the preset carries the method; a sticker plans with its perimeter and holes rule; the sheet packs tight or spaced from the plan's ink and draws every cut line; verify proves the page equals the plan; the API serves it all; no existing tag changes |
| Owner paths | `aruco_studio/core/make.py` (new: `MAKE_RULE 1`, `by`, `perimeter`, `margin_mm`, `thickness_mm`, `plan_sticker`, the sticker's label region), `core/presets.py` (kind, dpi, page, stock, sheet; the two Sticker built-ins; two collections), `core/label.py` (rule 3; `RULES`), `core/sheet.py` (`PrintItem.outline_mm / ink_mm / caption`, `SheetSettings.mode`, the tight guillotine shelves, cut lines and holes, crop marks, marks off with `ink_mm`, `render_layout_svg`, `layout_summary` per sticker), `core/form.py`, `core/validate.py`, `core/marker_table.py` (`made_by`), `plan/target.py` (`CHORD_MM`, `from_dict` normalises), `plan/spec.py` (`settings.holes`, `settings.make`, the loop-inside check), `plan/fields.py` (Holes, Perimeter, Make rows; `intent` per row; ChArUco label choices), `plan/plan.py` and `plan/evaluate.py` (the sticker branch; Holes: ignore = the outer loop; the hole-crossing warnings), `plan/layers.py` (`sticker`, `ink`, `guides.cut_line`, `guides.target_ignored`), `plan/record.py` (`fusion.make`), `scene/sheet.py` (items with outline and ink; mode; page), `scene/export.py` (new: the print bundle of the earlier note 5.3), `verify/sheet_check.py` (new: section g), `server/app.py` (`/api/scene/export/print`, `/api/scene/print.pdf`, `/api/scene/sheet.svg`, `/api/scene/verify?sheet=1`, `/api/new` from a preset, `/api/presets` both kinds, `models.py`), `tests/core/test_make.py`, `test_sheet_modes.py`, `test_label_rule3.py`, `tests/plan/test_make_plan.py`, `test_holes.py`, `tests/scene/test_print_bundle.py`, `tests/verify/test_sheet_wysiwyg.py`, `tests/server/test_make_api.py`, `docs/status/M6a.md`, `docs/API.md` |
| Does not touch | `goldens/**`; any rule's number; `studio/**`; `adapters/**` (M7 reads them) |

Done checks:

| # | Check | Bar |
|---|---|---|
| M6a.1 | the earlier note's M6.1-M6.8 (legacy = 3D byte for byte; the sticker plan; OpenCV reads it; junk `make`; a mixed 40-tag scene; the bundle; presets; the API) | as written there |
| M6a.2 | presets: `profile.kind` absent reads as 3D; the Sticker Letter built-in applied gives `cells {of cell, mm 0.042333}`, `make {by sticker, thickness_mm 0.1, perimeter marker}`; `GET /api/presets` lists both collections; a REF file round-trips through REF's pinned `normalise` with its keys intact | all |
| M6a.3 | Holes: on each of the ten palette faces with holes, `ignore` gives a marker >= `avoid`'s; `avoid` equals today's plan byte for byte (824 goldens replay with `holes` absent AND with `holes: avoid`); a marker crossing a hole under `ignore` carries the `warn`; junk reads as avoid with a `warn` | every face; 824 / 824 |
| M6a.4 | Perimeter: Marker gives a rectangular `cut_line`; Profile gives the target's loops with every hole; the sticker layer's polygon equals `cut_line`; a label `place: white` with Marker + margin 0 is read as auto with the `warn`; with margin 6 mm it builds on the white | every palette face x both; label off / black / white |
| M6a.5 | label rule 3: a manual spot in each black square of a 5 x 7 ChArUco builds there; the same under rule 2 is refused as today; `goldens/label.json` and the rule-1 golden replay exactly; the form offers a ChArUco board "In a black square" only | every square; 0 golden changes |
| M6a.6 | the sheet, tight: four identical 30 mm stickers on letter make one shelf, 7 cuts; a mix of 3 sizes makes one shelf per height, every shelf a straight full-width line (no sticker crosses a shelf line); spaced: today's layout plus a caption and crop marks per sticker; a 400 mm sticker is rejected with a reason in both modes | all |
| M6a.7 | odd shapes: the disc, the D-shape and an L (`core.faces`) with Perimeter = Profile are packed by their boxes in both modes and the PDF draws their outline and holes as hairlines; `sheet.json` holds each sticker's page, x, y, rotation and outline | all |
| M6a.8 | WYSIWYG (section g, steps 1-8) on a 12-sticker scene (single / grid / ChArUco, labels on the black and the white, triangle marks, two with Profile outlines) in both modes and both pages | ink XOR <= 2 %, every id, side within 0.15 mm, label IoU >= 0.9, outline <= 0.15 mm, bars +/- 0.1 mm |
| M6a.9 | `sheet.svg` and `sheet.pdf` of the same layout agree: every sticker's position within 0.01 mm (the SVG's `data-sticker` boxes against `sheet.json`) | all |
| M6a.10 | a 96-point disc with 3 holes: `plan_tag` under 50 ms with Holes: avoid (measured, printed in the status file) | true |
| M6a.11 | `tools/check.py` exits 0; nothing on 5360 / 5361 after; nothing written under `%USERPROFILE%\CADExporter` or into REF | true |

### M6b: the Studio UI

| | |
|---|---|
| Goal | the preset-first New-tag control, the per-kind form, the Holes and Perimeter rows, the ChArUco label choices, multi-select edit, the sheet dialog with its preview, badges and the Made-by column |
| Owner paths | `studio/src/**` (the New-tag control: Preset first with both collections; the inspector header's Made-by line; `layout.ts` per kind; the Print tab for a sticker; Holes and Perimeter rows; the Label tab per layout; multi-select edit; the canvas: `cut_line` dashed, ignored holes dashed, `2D` / `3D` badges, the `All · 3D · 2D` filter; the IDs table's Made-by column; the Export panel's **Sticker sheet…** dialog: page, landscape, Spaced / Tight, the SVG preview from `/api/scene/sheet.svg`, the rejected list, Export; the Library's two collections), `e2e/tests/**`, `reports/screens/**`, `docs/STUDIO.md`, `docs/status/M6b.md` |
| Does not touch | `aruco_studio/**`, `tests/**`, `docs/spec.json` |

Done checks (Playwright; every bar read from the DOM or `window.__studio`, screenshots in `reports/screens/`):

| # | Check | Bar |
|---|---|---|
| M6b.1 | New tag with the "Sticker · Letter · 600 dpi" preset on the disc: the header reads `Made by: Printed sticker`; four tabs; no Heights rows; the Print tab shows Sticker thickness, Sticker margin; the canvas badge is `2D`; `zRange[1]` = 0.11 | all |
| M6b.2 | Holes: Ignore on the disc with a hole: the marker grows (`numbers.size` from `/api/plan` larger); the hole is drawn dashed; the `warn` sits under Holes when the marker crosses it | all |
| M6b.3 | Perimeter: Profile on the disc: the canvas draws the disc outline as the cut line; Marker: a rectangle; with Marker + margin 0 the Position list has no "On the white"; a 3D tag's Perimeter = Marker gives a `trim_keep` layer | all |
| M6b.4 | a ChArUco board: Position offers "In a black square" only; dragging the label into another black square builds it there (no orange) | all |
| M6b.5 | multi-select: four tags selected, Corner mark set once: every tag's plan has `mark_triangle`; one undo restores all four | all |
| M6b.6 | the sheet dialog: Tight shows the shelf layout in the preview; Spaced shows captions and crop marks; Export writes `sheet.pdf`, `sheet.svg`, `sheet.json`; the preview's sticker boxes equal `sheet.json` | all |
| M6b.7 | the filter `2D` hides the 3D tags; the IDs table shows Made by; a sticker #3 and a 3D #3 show the duplicate mark; Renumber fixes it | all |
| M6b.8 | `npm run build` no TS errors; vitest green; every M3 / audit e2e still green; servers stopped | true |

### M6c: print

| | |
|---|---|
| Goal | Print from the Studio at 100 %, proven as far as a browser lets us |
| Owner paths | `studio/src/app/Print.tsx` (new: the hidden iframe, the fallback, the message), the Export menu item (`Toolbar.tsx`: one line), `studio/src/api/client.ts` (`printPdf`), `e2e/tests/print.spec.ts`, `docs/STUDIO.md` (a Print section), `docs/status/M6c.md`. The server route `GET /api/scene/print.pdf` is M6a's |
| Does not touch | everything else |

Done checks:

| # | Check | Bar |
|---|---|---|
| M6c.1 | Export > Print sticker sheet…: `window.__studio.printHook` is called once; the bytes it was given equal `/api/scene/export/pdf?inline=1`'s | byte-equal |
| M6c.2 | pdfium rasterises those bytes at 600 dpi: the 100 mm bar is 100.0 +/- 0.1 mm (the existing check on the print route's bytes) | true |
| M6c.3 | the fallback: with the hook refusing (Firefox), the dialog shows **Open the PDF** and the Ctrl+P note; the new tab's URL is the print route | true |
| M6c.4 | a scene with no sticker: the item is disabled with "no stickers in this scene (3D tags print on beds)" | true |
| M6c.5 | by hand, once, on Zach's printer: the printed bar measures 100 mm with a ruler; the number goes in `docs/status/M6c.md` | 100 +/- 0.5 mm |

### M7: the Fusion side (cad-exporter, the add-in worktree, Fusion-gated)

In the worktree `aruco-fusion-plugin-0e9bcb`, test documents only, the paced rules of `docs/aruco_edit_gates_crash_20261013.md`, after M6a is on `main`. Four steps in order, each with its gate; a step that fails its gate does not block the earlier ones.

| Step | What | Owner paths (cad-exporter) | Fusion check |
|---|---|---|---|
| M7.1 | vendor `aruco_studio/{core,plan}` into `ArucoMarkers/aruco_studio/` (`tools/sync_from_aruco_studio.py`, `VERSION` pinned to the Studio commit, `.py` only); the PDF export builds its items from `plan_tag(spec_of_node)` + `mesh.top` (`ink_mm`, `outline_mm`), Spaced / Tight row, the Print button (section i) | `ArucoMarkers/aruco_studio/**`, `tools/sync_from_aruco_studio.py`, `ArucoMarkers/aruco_export.py`, `aruco_commands.py` (the Export rows), `tests/test_aruco_export_dialog.py`, `docs/aruco_spec.json` | **F-M7.1** F1-lite: for every node of the test documents `plan_tag(spec_of_node).record_digest` == the node's record; **F-M7.2** the exported PDF passes section g's test (the labelled tag's label is on paper); the registry probe's answer and the `print` / open outcome recorded in `reports/aruco/print/` |
| M7.2 | multi-select: `setSelectionLimits(1, 0)`, N nodes in one execute, one timeline group "ArUco Extrude xN", N ghosts, ids in pick order | `aruco_extrude_cmd.py`, `aruco_extrude_ui.py`, `aruco_preview.py`, `aruco_feature.py` (the group), `tests/test_aruco_extrude_dialog.py` | **F-M7.3** the forearm case: 4 faces of a box in one dialog: 4 nodes in one group, 4 Joint Origins (the census), ids #0, #1, #2, #3 unique, ONE undo removes all four, Redo brings them back; the IDs node numbers two copies of the box; `aruco_edit_gates` sync / restructure / deps / atomic / jo green on one of the four |
| M7.3 | the Holes row (evaluate: the outer loop only under `ignore`) and the Perimeter row (= Trim excess on a 3D tag); ChArUco Position choices; rule 3 in `bam_cad_core/aruco_label.py` (the Studio's text) | `aruco_extrude_ui.py`, `aruco_extrude_cmd.py`, `aruco_feature.py` (one line), `bam_cad_core/aruco_label.py`, `tests/test_aruco_label*.py`, `tests/test_aruco_trim_dialog.py` | **F-M7.4** the GIM43 disc: Ignore grows the marker, the record carries `holes`; Edit -> OK unchanged writes nothing; Perimeter = Marker on a plate trims it (the trim gate `trim_test parts=board`); a manual ChArUco label in the second black square builds and OpenCV reads every corner |
| M7.4 | sticker presets in the Preset row and the Library (two collections); a sticker preset shows the sticker rows; the sticker node: `evaluate` branches to `aruco_studio.core.make.plan_sticker`'s numbers (stock `t`, ink 0.01, New body, no pins / pocket / recess / trim), `fusion.make` in the record, body names as today; Export pre-ticks stickers for the PDF and greys them for PrusaSlicer | `aruco_presets.py`, `aruco_preset_library.py`, `resources/preset_library/*`, `aruco_extrude_ui.py`, `aruco_feature.py`, `aruco_export.py`, `aruco_commands.py`, `tests/test_aruco_presets*.py`, `tests/test_aruco_extrude_fixes.py` | **F-M7.5** a sticker node on a plate: two bodies (volumes = area x 0.1 and ink area x 0.01 within 1 %), one Joint Origin at 0.11 mm, an IDs copy of it re-split by its id, Undo / Redo one step each; `aruco_edit_gates` on it; a mixed document's PDF holds the stickers only and the 3MF the 3D parts only. If the 0.01 mm bodies misbehave, option C of the earlier note (sketch + Joint Origin) is the fallback, recorded by the gate |

M7's done: each F-M7 record in `reports/aruco/m7/`, `docs/aruco_spec.json` updated, every offline suite green (`tests/test_aruco_*.py`), nothing in Zach's own documents touched.

### New `docs/spec.json` entries (the orchestrator writes them)

Features (the earlier note's ST-MAKE-* stay; these are added):

| Id | Area | Name | Milestone |
|---|---|---|---|
| ST-PRESET-KIND | core | The preset is the machine: kind, dpi, page, stock, sheet mode; two collections | M6a |
| ST-HOLES | plan | Holes: avoid / ignore (`settings.holes`; absent = avoid) | M6a |
| ST-PERIMETER | plan | Perimeter: Marker / Profile for a sticker; = Trim excess on a 3D tag; the no-white label rule | M6a |
| ST-LABEL-RULE3 | core | Label rule 3: a manual ChArUco label in any black square; the form offers a square only | M6a |
| ST-SHEET-MODES | export | The sticker sheet, spaced or tight (guillotine shelves); captions and crop marks; cut lines for outlines and holes | M6a |
| ST-SHEET-SVG | export | The sheet as SVG and JSON beside the PDF (the preview and the oracle) | M6a |
| ST-WYSIWYG | verify | The page equals the plan: ink, ids, label, outline, bars | M6a |
| ST-TARGET-CHECKS | plan | One chord tolerance; a loop outside the outline is refused; loops normalised | M6a |
| ST-UI-PRESET-FIRST | studio | Preset first; Made by read only; the per-kind form; Holes and Perimeter rows; ChArUco label choices | M6b |
| ST-UI-MULTI | studio | Multi-select edit; add several tags at once | M6b |
| ST-UI-SHEET | studio | The sticker sheet dialog with a preview, Spaced / Tight, page | M6b |
| ST-PRINT | studio | Print the sticker sheet at 100 % from the Studio; the fallback | M6c |
| ST-FUSION-CORE-VENDOR | adapter | The add-in ships `aruco_studio/{core,plan}`; the PDF export from the plan's ink | M7 |
| ST-FUSION-PRINT | adapter | Print from Fusion: the `print` verb when registered, else open | M7 |
| ST-FUSION-MULTI | adapter | Multi-select: one node per face, one group, one undo | M7 |
| ST-FUSION-HOLES-PERIMETER | adapter | The Holes and Perimeter rows in the v2 dialog | M7 |
| ST-FUSION-STICKER | adapter | The sticker node and sticker presets in Fusion | M7 |
| ST-SHEET-NEST | later | True polygon nesting of odd stickers | — |
| ST-FIT-ANGLES | later | Fit at any angle (`settings.fit`) | — |

Tests:

| Id | Kind | Checks |
|---|---|---|
| ST-T-PRESET-KIND-1 | pytest | M6a.2 |
| ST-T-HOLES-1 | golden + pytest | M6a.3 |
| ST-T-PERIMETER-1 | pytest | M6a.4 |
| ST-T-LABEL-RULE3-1 | golden + pytest | M6a.5 |
| ST-T-SHEET-MODES-1 | pytest | M6a.6, M6a.7, M6a.9 |
| ST-T-WYSIWYG-1 | opencv | M6a.8 |
| ST-T-TARGET-1 | pytest | the loop checks, `CHORD_MM`, M6a.10 |
| ST-T-UI-M6-1..7 | playwright | M6b.1-M6b.7 |
| ST-T-PRINT-1 | playwright | M6c.1-M6c.4 |
| ST-T-PRINT-2 | manual | M6c.5 |
| ST-T-FUSION-M7-1..5 | manual (Fusion gate records) | F-M7.1-F-M7.5 |

## l. Open questions for Zach

| # | Question | Recommended default |
|---|---|---|
| 1 | The sticker preset's default page: Letter or A4? (A Canon printer is on this box: Canon Quick Menu was seen on 2026-10-16) | **Letter** as the first card, A4 the second; the preset remembers your pick |
| 2 | Holes for a sticker: Avoid (keep clear, as a 3D tag) or Ignore (the sticker may cover them)? | **Avoid** for both kinds; Ignore is one click, and the plan warns when the marker crosses a hole |
| 3 | Fit at any angle, or 0 / 90 only? | **0 / 90 only** now (section c); `ST-FIT-ANGLES` later if a face asks for it |
| 4 | Odd stickers packed by their boxes, or true nesting? | **Boxes** now; nesting later (`ST-SHEET-NEST`) |
| 5 | Multi-select in Fusion: one node per face in one timeline group, or one node for the set? | **One node per face, one group, one undo** (section h) |
| 6 | Print from Fusion: try the `print` verb, else open the PDF; or always open? | **Try the verb, else open**, the button's words say which; the bars are always on the page |
| 7 | The Made-by row: gone (the preset decides) or kept as an override? | **Gone**: a read-only line under Preset; a tag matching no preset shows "custom" |
| 8 | A ChArUco label by hand in any black square (rule 3) or the top-left only? | **Any black square** (rule 3; auto stays top-left) |
| 9 | The earlier note's six questions (the row's words, stock 0.1 mm, proofs off, a black triangle on paper, no switch on a locked tag, a thin body in Fusion) | as answered there, with question 1 now moot |
