# Merge polish: lane/polish, then lane/speed

2026-10-17. Both lanes merged into `main` with `git merge --no-ff`, in this order:

| Lane | Merge commit | What it brings | Its record |
|---|---|---|---|
| lane/polish (00c97b6) | 9524b6a | label rule 5 (Q1's default), the tool box takes a paste and an IME, the final audit's nits A5, A6, A7, A10 and C2's server half | docs/status/polish.md |
| lane/speed (fa00cb1, aa8fca5) | 0b5a256 | live re-placement fast (audit B1): one sweep per slab, a linear simplify, a fast pinch check, no GC pauses mid-edit, the light drag preview in 3D | docs/status/speed.md |

Git found no conflicts. Two files were changed by both lanes, in different places:

| File | lane/polish | lane/speed |
|---|---|---|
| `aruco_studio/server/app.py` | `/api/health` adds `"file": "arucostudio.scene/2"` (A5) | `no_gc()`, `_kept_mesh`, the cache reads the kept plan dict |
| `docs/STUDIO.md` | the Tools row (paste, IME); the rule 5 row | the Live re-placement row |

Both sides are kept as they were.

## What the merge broke, and the fix

| # | Found | Fix | Test |
|---|---|---|---|
| 1 | The first full check failed in the plan group: 8 of `test_every_output_is_bit_identical`. Lane speed's fixture `tests/fixtures/mesh_digests.json` holds the digests of 947 plans as the code gave them at 46f2bac. Lane polish changed 39 of those plans on purpose. | `tools/mesh_digests.py --write-merge` writes `tests/fixtures/mesh_digests_merge.json`: the new `plan` digests of those 39 cases. It refuses to write if any other digest differs. The test now takes the plan digest from this file for those cases. Everything else still must match 46f2bac. | `tests/plan/test_mesh_digests.py` (plus one new test: `test_the_merge_overlay_is_only_lane_polish`) |

The 39 cases, and why each plan changed. I diffed every one against the pre-polish code (lane/speed's tip):

| Cases | What changed in the plan | From |
|---|---|---|
| 9 goldens (trim25, c0276, c0286, c0312, c0314, c0316, c0411, c0413, c0432) | only the cell-minimum warning's text: "; a Checker size of ..." is now " — a Checker size of ..." | C2's server half |
| 7 fuzz specs | only the size error's text: "size -2.0: 0 (Auto) ..." is now "Marker size -2 mm: 0 for Auto, ..." | C2's server half |
| 14 fuzz specs | only the unknown-rule warning: "not one of 1, 2, 3, 4" is now "not one of 1, 2, 3, 4, 5" | rule 5 exists |
| 11 example tags (the forearm at 120 and 153 mm, the plate, two stickers) | sugar tags expand as a new tag, so they now store label rule 5 (and the label's `line_mm`). Where the label is refused, its preview box is laid out at the new stroke | rule 5 is the new-tag rule |

Some cases are in more than one row. In all 947 cases the bodies, the top view, the mesh, the removed volume and the STL are still byte for byte the 46f2bac ones. So no built geometry changed: not in a golden, not in an example.

The new test checks that every case in the overlay really differs from 46f2bac, and that its plan carries one of the four marks above.

## Other changes at merge

- `docs/spec.json`: added ST-LABEL-RULE5 and ST-UI-LIVE-FAST (built), and the tests ST-T-LABEL-RULE5-1, ST-T-SPEED-1 and ST-T-TYPED-INPUT-1 (passing). ST-LABEL-RULE4's text now says new tags stored rule 4 until rule 5. `tools/spec_status.py --check`: tests passing 92, planned 4, failing 0.
- `docs/STATUS.md`: the B1 row says what lane speed fixed and what is still open. The nits row says both lanes are now merged.
- The e2e run rewrote the screenshots under `reports/screens/`. They are committed, as before.
- The raw check lines: `reports/merge_polish_check_2026-10-17.log`.

Nothing was reverted.

## The full check

`.venv/Scripts/python tools/check.py`, every group, from ROOT after the fix. Ports 5360 and 5361 were free before and after. 5370 / 5371 (Zach's preview) were not touched.

| Group | Result | Before the merge (46f2bac) |
|---|---|---|
| adapters | 97 passed in 40 s | 97 |
| core | 7,387 passed, 4 skipped in 36 s | 7,354 + 4 skipped |
| plan | 544 passed in 109 s | 529 |
| scene | 43 passed in 12 s | 42 |
| server | 97 passed in 18 s | 91 |
| verify | 120 passed in 87 s | 117 + 1 strict xfail |
| studio | build + vitest passed in 9 s | |
| e2e | 52 passed (4.1 m) in 250 s | 47 |
| **all** | **OK in 562 s**, exit 0 | 523 s |

The counts add up: plan 529 + 12 (speed) + 2 (polish) + 1 (the overlay test). Server 91 + 6 (speed). e2e 47 + 3 (polish) + 2 (speed). Verify: the strict xfail is now a pass, plus polish's 2 new slice tests.

`tools/check.py --trace`: `missing: 0`.

## Worktrees and branches

The lanes' worktrees had a `.venv` junction to ROOT's `.venv`. I removed each junction first (`rmdir`, which leaves the target alone), then `git worktree remove`. `lane/polish` and `lane/speed` are deleted. The empty `aruco-studio-wt` folder is gone. `git worktree list` shows only ROOT and `aruco-studio-preview` (left alone).

## Still open

- **Sugar tags take the new label rule.** A typed ArUco Extrude in sugar (no exact `settings`) expands as a new tag at every compile, so it moved from rule 4 to rule 5 with this merge. No built tag changed in the examples or the goldens (the solids are byte for byte the same). But a user's sugar file with a label cut from the black under 1.1 lines would now be refused at its next open. `frozen_presets` freezes the preset, not the label rule. `scenes/` in ROOT is empty, so no file of Zach's is affected today. If this should not happen, freeze the label rule next to the presets (a file format change).
- From lane speed: a drag step is 120-155 ms on a busy box (the target is 100 ms). The next step is a process pool. The 3D release builds the meshes in one process. `no_gc()` turns off the cyclic GC process-wide while a preview is in flight. The 3D drag slab is flat.
- From lane polish: rule 5's floor is 1.1 lines, not 1.0 (change `label.LINE_STROKE` before any rule-5 tag is printed). A9, C1, the Studio half of C2, C3 and C4 are not fixed. They were in the other lane's files; both lanes are merged now, so they can be done next (fixes proposed in `docs/status/polish.md`).
