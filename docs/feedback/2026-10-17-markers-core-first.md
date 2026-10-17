# Zach's feedback, 2026-10-17 morning: markers first, the core under Fusion, a gallery instead of a sketcher

This comes from his daily note. He was frustrated: "I added all of these features and some of the basic ones don't even work anymore." He was also calm about it: "we are not as far as I thought. I mean most of this stuff already works... I think I got stuck on some of the label stuff etc. which doesn't really matter that much!"

The key idea: "we have the markers that we can just do standalone and then all this other stuff we can add on top!"

## The model, in his words (CF = core first)

| ID | Requirement | His words, condensed | Today |
|---|---|---|---|
| CF-1 | **Functional core split from any CAD program.** We have our own profile representation; each program gets an adapter from what it provides to what we want. | "Allows me to easily use in different modelling software" | Exists: `aruco_studio/{core,plan}`, `plan/target.py` `Target.loops_mm`, `adapters/fusion` (a skeleton, not installed). The Fusion add-in still runs its own copy (`CADExporter/bam_cad_core` + `ArucoMarkers/*`). |
| CF-2 | **The most basic feature is drawing markers by hand.** Nothing auto. Auto placement, profiles and labels sit on top. | "Nothing would be 'auto' but its the ability to basically just like draw markers" | Manual size and position exist; they must work first and always. |
| CF-3 | **How it's made shapes how it's drawn.** One design can be made several ways (some tags 3D printed, some inkjet printed). Values come from the preset by default and can be overridden at export time. Black-box design: the outside (assembly, IDs) only updates the ID; everything else is defined at the lower level, which allows composition. | "by default when you export the values are taken from those presets but you can always override at the export time" | The preset is the machine (M6, FB-1). The export-time override is new. |
| CF-4 | **Two preset kinds: 3D Printer and Inkjet Printer.** **3D:** autosync from PrusaSlicer profiles; first layer width, default line width, first layer height, layer height, bed size, …; plus the print orientation (face down or other). **Face down sizes the cells by the first layer width.** **Inkjet:** paper size, paper thickness, margins, … | | 3D presets carry nozzle / line / layer / first layer height and PrusaSlicer sync (M8c). Sticker presets carry dpi / page / margin / stock 0.1 mm. **New:** first-layer *width*, bed size on the preset, the face-down rule for cells, the name "Inkjet Printer". |
| CF-5 | **Making a marker: type first (single, grid, ChArUco), then the inner numbers** (marker width, checker width, spacing, …). **The outer size is derived**, not typed. | "from that the outer dimensions are derived" | The inner numbers exist; check that the dialog leads with type → inner numbers and only shows the outer size. |
| CF-6 | **The maximum size:** inkjet = paper minus margins; 3D = the bed. **Invalid values are allowed but flagged red** (a linter), not refused. | "we can allow invalid values. but its just we should flag them with linter red" | New. PP-1 (2026-10-17) is the inkjet half. Today's ArUco Export PDF refuses an oversize board (OK greyed); the marker dialog should flag it red. |
| CF-7 | **2D is modelled as a thin rectangle the paper's thickness.** The black part is paper thickness / 2 deep, going INTO the rectangle. | "Black part can be paper thickness/2 and go into the rectangle" | Today's sticker plan is stock `t` plus a 0.01 mm ink film ON TOP (`core/make.py INK_MM`). Changing it is a new make rule, so existing tags keep theirs. |
| CF-8 | **3D: black and white flush on the surface only, for now.** The only options are the depth of the black and, if white is printed too, the depth of the white. **Flip:** a reference face sets the direction. Extruding in open space with no reference face gives a Flip option that puts the black on the top or the bottom of the extrusion, same depth. Flip exists only for black + white; black only goes from its location. | | Depths exist (`heights`); flush-only means hiding the raised / recessed variants by default. Flip with no reference face is new. |
| CF-9 | **Labels matter less.** Don't get stuck there. | | |
| CF-10 | **The IDs command is the other key piece.** | "Then the other key thing is this like ID command" | ArUco IDs (2-click flow). |
| CF-11 | **The core first, then the rest on top.** | "once you now have that core working... then you can add on the other stuff" | |
| CF-12 | **No sketch platform of our own in the Studio.** Bring sketches in from other programs (e.g. a DXF exported from Fusion). | "I am also moving away from aruco studio having its own like sketch platform no point in maintaining that... 100% we don't need to maintain yet another cad program" | **Supersedes SK-1..SK-6** (`2026-10-17-sketch-lines-regions.md`). The survey's SK-a..e plan (`docs/design/sketch_tools_survey.md`) is not built. |

## What he wants next

| ID | Ask | His words, condensed |
|---|---|---|
| N-1 | **Refactor the Fusion add-in onto ArUco Studio's functional core.** Run lots of acceptance tests and take control of Fusion as needed to verify it works. | "Please refactor so that the fusion plugin is now using the functional core of Aruco Studio. Make sure to run lots of acceptance tests and take control of fusion as needed" |
| N-2 | **5 UI/UX proposals for ArUco Extrude in Fusion.** Fusion's design language ("sometimes constraints are good, so let me lean into that"). **Preset is the first option**: it chooses the manufacturing method. **Tab 1 = Marker**, then perhaps a **Label** tab. | "Please make 5 proposals for the UI/UX of the aruco extrude feature in fusion" |
| N-3 | **The Studio shows golden examples** (as before) with **all the features: auto-positioning, labels, etc.** No user-drawn canvas for now: the inputs are drawn for the user. | "We can show some golden examples… we don't need to support user generated canvas right now you can just like draw the inputs. So show all the features for auto positioning label etc inside of aruco studio" |

## Dispatched (2026-10-17)

- **N-1:** one agent, in the cad-exporter add-in worktree, with an aruco-studio lane branch for core changes. ROADMAP M7.1 (vendor + sync), then the add-in's logic switched onto the vendored core behind a switch, proven equal, then the Fusion acceptance gates. It starts with a census of the basics, because of "some of the basic ones don't even work anymore".
- **N-2:** one agent; it writes `docs/design/extrude_ui_proposals/` here.
- **N-3:** one agent on an aruco-studio lane branch (`studio/` + `examples/`).
- **CF-4..CF-8** (the new preset fields, face-down cells, the size lint, paper thickness / 2 black, Flip) are model changes. N-2's proposals design them; they get built after N-1 lands, so the refactor changes no behaviour.
