# Zach's feedback, 2026-10-16 ~20:45: ArUco Studio as a bare-bones mini CAD, file first

His three screenshots ("Pasted image 20261016204253.png", "…204333.png", "…205038.png") were not in the vault backup. The last one shows today's target editor, which he calls "this silly thing here to make these targets".

## What he wants

| ID | Requirement | His words, condensed |
|---|---|---|
| MC-1 | **The domain model first class.** By default the Studio feels like a whiteboard, or a SUPER bare-bones 3D modeller. | "Its like a super mini CAD thing." |
| MC-2 | **Draw shapes** (sketch). They ARE the inputs to our algorithm: the internal representation of profiles (Target loops), not a separate thing. | |
| MC-3 | **Extrude** turns shapes into 3D models (bodies), so tags can go on faces. | |
| MC-4 | **ArUco Extrude** is the entry point for adding a tag: on a profile or a face, as in Fusion. | It replaces today's target editor. |
| MC-5 | **Edit shapes**, and the markers regenerate their placement live. | "you should see the markers regenerate their locations" |
| MC-6 | **A bottom toolbar** bound to hotkeys. **S = search**: find a command or tool by name. | "fun to just like quickly adjust things and see how they work" |
| MC-7 | **Drag things around in 3D.** | |
| MC-8 | **Simple, not complicated.** The point is a way for users to MAKE TESTS of the algorithms, and to prove the interaction before moving it into CAD. | "this is a way for users to make tests that is all we want" |
| MC-9 | **File first.** Scenes, shapes and tags are raw text files that a person or an AI can write by typing. The Studio is a viewer and editor of the file. | "AI can just like easily generate a file by typing text… aruco studio is basically just like a viewer that helps us make it" |
| MC-10 | **Leave Fusion's design language** for something more modern. Make it a drop-in kit for our other tools; the FIELDS are what matter, the style can be redone. | |
| MC-11 | **PrusaSlicer Physical Printers**: can we read the settings from his Physical Printers? Those are the ones he actually uses. **Live updating** of the PrusaSlicer sync? | "very powerful though to have that sync" |
| MC-12 | Why it's worth it: the interaction gets proven in an isolated environment, it's easier to move to CAD later, and it's isolated from Fusion churn. | "definitely more robust" |

## Open technical question he raised

"Perhaps the best library for this is a super simple CAD modeller that lets you draw sketches and extrude them into 3D?" Choose between:
- our own minimal sketcher on today's plan/region.py booleans + three.js;
- a web CAD kernel (OpenCascade.js / replicad, JSCAD, …);
- a sketch constraint solver (planegcs / SolveSpace);
- or a mix.
