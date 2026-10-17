# Merge 2: wave 2 (M8c, then M8b1)

2026-10-17. Both lanes merged into main with `git merge --no-ff`, in this order:

| Lane | Merge commit | What it brings | Its record |
|---|---|---|---|
| lane/M8c (aea4078) | 08e6e08 | PrusaSlicer's physical printers, live sync, Send to PrusaSlicer, the headless slice check | docs/status/M8c.md, docs/API_prusa.md |
| lane/M8b1 (d8da387, cee497b, 8798009) | e33c08d | the bare-bones mini CAD in the Studio, file first | docs/status/M8b1.md, docs/STUDIO.md |

Git found no conflicts. The two lanes changed no file in common.

## Include lines added

| File | Line (at the end) |
|---|---|
| `aruco_studio/server/app.py` | `from . import prusa_api  # noqa: E402,F401  (M8c: PrusaSlicer printers, Send, the folder's watcher)` |

M8b1 asked for none.

## What the merge changed, and why

| # | Found | Fix | Test |
|---|---|---|---|
| 1 | The PrusaSlicer routes were only served once `prusa_api` was imported. | The include line above. The routes go before the web app's static mount. | `tests/server/test_merge2_wiring.py` |
| 2 | `/api/preset/apply` and `/api/preset/of` still read REF's `catalog`. A sticker printer was not found by name (404), and a sticker tag's preset matched nothing. Open since Merge 1, and named by M8c. | Both routes read `presets.catalog_all`, as `/api/new` and the Library do. | `test_merge2_wiring.py` (it fails without the fix) |
| 3 | `docs/ARCHITECTURE.md` still had the target editor (gone in M8b1) and no M8c rows. Neither lane owned the file. | The section 4 row is now "Sketch and shapes". Section 5.1 says the design file fills the Target. `core/prusa.py` lists M8c's functions. Section 3.5 has the M8c routes. | none (docs) |
| 4 | `studio/node_modules` in ROOT had none of M8b1's new packages (cmdk, @base-ui/react, Tailwind 4). `check.py` installs only when the folder is missing. | `npm ci` in `studio/`, from M8b1's lock file. | the studio and e2e groups |

Nothing was reverted. The e2e run rewrote the screenshots under `reports/screens/`; they are committed.

## The full check

`.venv/Scripts/python tools/check.py`, every group, from ROOT after the fixes. Ports 5360 and 5361 were free before and after.

| Group | Result | After Merge 1 |
|---|---|---|
| adapters | 97 passed in 42 s | 97 |
| core | 7,349 passed, 4 skipped in 37 s | 7,308 + 4 skipped |
| plan | 518 passed in 81 s | 513 |
| scene | 42 passed in 14 s | 36 |
| server | 78 passed in 19 s | 59 |
| verify | 117 passed, 1 skipped in 95 s | 111 |
| studio | build + vitest passed in 7 s | |
| e2e | 28 passed (2.5 m) in 155 s | 19 |
| **all** | **OK in 451 s**, exit 0 | 384 s |

The verify group's "1 skipped" is M8c's strict xfail (the cut-label stroke, below). The server's 78 is M8c's 74, the uvicorn test the lane had to deselect, and the 3 new wiring tests.

`tools/check.py --trace`: `missing: 0`.

## Worktrees and branches

`lane/M8c` and `lane/M8b1` are deleted, and their worktrees removed. `git worktree list` shows only ROOT and `aruco-studio-preview` (left alone). The folder `aruco-studio-wt` is empty.

## Still open (from the lane reports)

- **M8c.7, Zach decides.** A label cut out of the black, with a stroke under one line (0.64 mm against the preset's 0.68 mm), fails the label-pixel bar: 37 of 216 pixels on the forearm, 44 on a flat face. The choices: a minimum stroke of one line for cut labels (a new label rule number), or a finer nozzle for the black. The test is a strict xfail.
- A design file still in sugar re-expands from the current preset at its next compile, so a changed PrusaSlicer profile changes those tags then. The fix is to freeze the presets a design was opened with (`scene/design.py` or `server/design_api.py`).
- M8c.2's yes / no table for the MK4 MMU3 0.4 and 0.6 was read from the conditions by hand. Zach should look at the two dropdowns in PrusaSlicer once.
- The "Apply?" info is served by `GET /api/prusa/stale`; its inspector row and button are M8b2's.
- The inspector's Advanced tab shows "Make rule: rule [object Object]". The form from `plan/fields.py` is M8b2's.
- Not built in M8b1: snap to shape centres and edges, a slot's width from a second drag, the size arrow and label drag in 3D.
- The File drawer cannot show a broken text: `GET /api/design` serves the last text that parsed. It shows the error's line and column above it.
- The preview answer (80 kB for ten tags, 43 to 67 ms) is most of M8b1.3's budget.
- `docs/spec.json` was not updated by this merge.
