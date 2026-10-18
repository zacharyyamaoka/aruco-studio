# Stable / Preview for the online Studio

The online Studio (`web/`) runs locally under Zach's shared Stable / Preview runtime
(`/home/bam/stable_preview_switcher`, contract `docs/CONTRACT.md` there). The repo holds **data only**:
`stable-preview.json` at the repo root (plus `web/public/icon.svg`, the dock icon). No chip, no launcher, no
`vite.config` change. JSON has no comments, so the reasons live here.

| Channel | URL | What it is |
|---|---|---|
| Stable | http://127.0.0.1:5382 | a pinned build of `main`; changes only on `sps promote` / chip "Make Stable" |
| Preview | http://127.0.0.1:5383 | the Vite dev server on the main checkout (hot reload) |
| `pack` | 127.0.0.1:5384 | Preview's helper process (below); nothing to open |
| lanes (`sps dev` in a worktree) | 5400-5499 | the runtime's default range |

Commands: `sps status`, `sps open`, `sps open --preview`, `sps promote`, `sps rollback`, `sps stop --all`,
`sps install-desktop` (dock icon: click = Stable, right-click = Preview / Make Preview Stable / Roll Stable Back).

## Why it is shaped this way

- **The app root is the repo root, not `web/`.** The snapshot and the fingerprint cover the app directory only.
  The web app imports the kit from `../studio/packages/bam-ui` (`web/vite.config.ts` alias) and its pack step reads
  `../aruco_studio`; a `web/` root would build a Stable without either. Vite itself still runs in `web/`:
  `preview.command` is the adapter's own `serve.mjs` with `--vite-root {checkout}/web` (CONTRACT §10.3), and the
  Stable build is the adapter's `build.mjs --root {source}/web` (`stable.output` is `web/dist`).
- **Ports.** 5382 / 5383 / 5384 sit beside the web app's own 5380 (`npm run dev`) and 5381 (`vite preview`), so
  "538x is the online Studio". 5370 is on `tools/check.py`'s never-ours list (`OTHER_TOOLS`) and 5371 is Zach's
  preview of another tool, so neither is taken; 5360 / 5361 are the old local Studio and its e2e. Checked free with
  `ss -ltn` and against every other app's `stable-preview.json` on 2026-10-18. Lanes keep the default 5400-5499.
- **`pack-core` before Vite, and again when Python changes.** `web/public/py/` and `web/public/pyodide/` are
  gitignored build products, so a fresh checkout has none. Stable: the first `stable.build` step runs
  `web/scripts/pack-core.mjs` in the snapshot (`vite build` copies `public/` into the release). Preview and lanes: the
  runtime starts `preview.processes` first and the web server last, each only after its health answers, so the
  `pack` process runs `pack-core` and then serves the packed folder with `python3 -m http.server` (the port and
  health check are all the runtime asks of a process). Its `watch` of `aruco_studio/**/*.py` makes the runtime
  restart it on a change, which packs again; Vite serves `public/` from disk, so a page reload loads the new core.
  Anchored pattern on purpose (CONTRACT §10.11: an unanchored `*.py` walks the whole checkout each second). If
  `pack-core` fails the process exits and Preview fails with its log tail, rather than serving a stale core.
- **Stable skips `tsc -b`.** `npm run build` type-checks first; the runtime's Stable build is the app's `vite build`
  (the type check stays in `npm run build` and the deploy).
- **Stable's `_build.json` has no git describe.** The release snapshot is not a git repository, so the core's
  version reads `0.1.0` without a commit suffix (Preview and lanes have it). The chip names the commit anyway.
- **`snapshot.exclude`** keeps what the online build never reads (`docs/`, `reports/`, `tests/`, `e2e/`,
  `goldens/`, `examples/`, `tools/`, the server/adapters/verify halves of `aruco_studio/`, and the old local Studio's
  own files under `studio/`, but not `studio/packages/bam-ui`) out of the snapshot AND the fingerprint, so a docs
  or old-Studio commit does not read "Stable is behind". `snapshot.link` is `web/node_modules` (the default,
  `node_modules`, would not match the nested folder).
- **The old local Studio (`studio/`, 5360) is not part of this.**
