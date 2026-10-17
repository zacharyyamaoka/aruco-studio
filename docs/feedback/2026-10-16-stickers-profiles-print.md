# Zach's feedback, 2026-10-16 evening: stickers, profiles, sheet layout, print

It applies to ArUco Studio AND the Fusion add-in ("in fusion and aruco studio"). His two screenshots ("Pasted image 20261016201654.png", "…202429.png", the second about tight vs spaced layout) were not in the vault backup, so this note works from his words.

## The goal in his words

"How can I make manufacturing aruco markers like really really stupid fast and easy… that is my goal." He doesn't regret the work: the markers are very helpful.

**Target workflow (Fusion, the 1-DoF arm's forearm):**
1. Click a face; the tag places itself automatically.
2. Set the ChArUco board size, the corner mark and a label.
3. Click the other 3 faces.
4. Make the IDs unique.
5. Press **Print**.

Exact mounting doesn't matter: a marker calibration always measures their relative poses afterwards.

## Requirements

| ID | Requirement | Notes |
|---|---|---|
| FB-1 | **2D and 3D markers**: each tag is 3D printed or a sticker. Choosing the method changes which options show. | Set it like a **machine preset**: the preset picks the method, and the options below follow. Extends docs/design/manufacturing_intent.md. |
| FB-2 | A 3D printer preset needs **line width** and **layer height**. | Already in the presets (PrusaSlicer profiles carry both). |
| FB-3 | **One profile representation, our own**: any shape, with interior holes, from a sketch profile OR a face selection. The result is the same input. | Exists: `plan/target.py` `Target.loops_mm` (outer loop + holes, mm, in the target's own frame). The Fusion adapter fills it from a BRepFace or Profile, the Studio from its target editor. |
| FB-4 | **Auto-placement = the biggest uninterrupted rectangle that fits in the profile** for the chosen marker type. | Exists: `core/autosize.fit_on_loops` → `largest_clear_rect` (exact branch and bound; tile inside the outer loop, outside every hole), at 0° and 90° only. Open: arbitrary angles? |
| FB-5 | Option to **ignore the inner geometry or account for it** (e.g. a sticker may cover holes). | New: a per-tag "Holes: avoid / ignore" switch; ignore = fit on the outer loop only. |
| FB-6 | **WYSIWYG**: what's on the printed page always matches the CAD exactly. A label on the page must be in CAD too. | A sticker's plan is the single source for the page and for CAD (Studio canvas, Fusion body, PDF). |
| FB-7 | 2D supports **single, grid and ChArUco**. | |
| FB-8 | **Sheet layout: tight or spaced.** Tight packs stickers so they share cut lines, which cuts down the number of cuts. Spaced leaves gaps, and info can go in the cut area. | New layout modes in the sticker sheet export. |
| FB-9 | **Perimeter = Marker or Profile.** Marker (trim): the sticker is the marker itself, always a rectangle. Profile: the sticker keeps the profile's outline, any shape. Draw that outline, and the holes and circles, so they can be cut with scissors. The sheet layout must handle these odd shapes. | Odd, asymmetric shapes help orient a sticker when placing it. For 3D tags this matches Trim excess. |
| FB-10 | **Helpers**: corner triangle; a label on the black or the white. | Exists for 3D (core label / marks). |
| FB-11 | With Perimeter = Marker there's **no label on the white**: the only white left is the quiet zone. | A validation rule plus hidden choices. |
| FB-12 | Labels **place automatically**, with **optional offsets** to position them by hand. | Exists (label rule 2, auto position, Offset X/Y). |
| FB-13 | **ChArUco: the label goes only in a black checker square.** | Check today's ChArUco label rule against this. |
| FB-14 | **Multi-face**: pick several faces in one go and get one tag per face, the same settings on each (the forearm's 4 sides). | Fusion: multi-select in ArUco Extrude. Studio: several targets at once. |
| FB-15 | **Unique IDs across everything** in one place: 2D and 3D tags together. | Exists in the Studio scene ledger; Fusion: the ArUco IDs node. |
| FB-16 | **Export to PDF AND a Print button** that opens the print dialog directly, saving the "find the PDF, open it, print" steps. | Must print at 100 % scale (true size); keep a scale check on the sheet. |

## Answer to his question: is the profile in Fusion's representation or our own?

**Our own.** `aruco_studio/plan/target.py` defines `Target`:
- `kind`: face, sketch profile or free;
- `w_mm`, `h_mm`;
- `loops_mm`: the outer loop first, then the holes, as [u, v] mm points in the target's own frame;
- the body under it.

"The plan never sees an entity." The Fusion adapter turns a clicked face or sketch profile into these loops; the Studio's target editor makes them by hand.

The placement already works on that representation: `core/autosize.fit_on_loops` finds the face's largest clear rectangle with an exact branch and bound, keeping the tile inside the outer loop and outside every hole. It currently tries 0° and 90° only.
