# The check run (Definition of Done D1)

`.venv/Scripts/python tools/check.py`, every group, 2026-10-16 about 21:00, after the post-M3 audit fixes (`docs/status/AUDIT.md`). Ports 5360 and 5361 were free before the run, and `netstat` showed nothing listening on them after it.

| Group | Result |
|---|---|
| adapters | 97 passed in 42 s |
| core | 7,245 passed, 4 skipped in 38 s |
| plan | 193 passed in 60 s |
| scene | 7 passed in 5 s |
| server | 35 passed in 14 s |
| verify | 104 passed in 93 s |
| studio | build + vitest (19) passed in 4 s |
| e2e | 19 passed (1.5 m) in 91 s |
| **all** | **OK in 349 s**, exit 0 |

`tools/check.py --trace`: `missing: 0`.

## Other done checks seen in this run

| # | Check | Seen |
|---|---|---|
| D6 | OpenCV reads every PNG / PDF export | the PDF sticker sheet now too: `tests/verify/test_pdf_sheet.py`, `e2e/tests/export.spec.ts` |
| D11 | every feature and test built / passing, or planned with a reason | `tools/spec_status.py`: features built 43, partial 9, deferred 3, planned 5; tests passing 70, planned 4 |
| D12 | no server left on 5360 / 5361 | none after the run |
| D12 | nothing written into REF | this run read REF only (`git show`, the Read tool). `git -C <REF> status` shows ` M .claude/launch.json` and untracked reports: other sessions' work in that worktree, not this run's |
| D13 | local only | `git remote -v` is empty. `git worktree list` also shows `aruco-studio-preview` (detached at 827b0f5): another session's, left alone |
