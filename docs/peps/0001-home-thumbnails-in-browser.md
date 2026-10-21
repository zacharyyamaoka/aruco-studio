# 0001 — Home thumbnails are drawn in the browser, kept by content hash

Date: 2026-10-21 · Status: accepted · Merged: lane/os-thumbs

## Context
Zach (2026-10-21): "Please make sure thumbnail previews are showing." Only the open file had a
picture on Home; every other card showed the file icon. Simple Hosted Files has no thumbnail field
("only your app can draw them"), and writing a picture into the file would add a version and move
the file up Recents just from looking at Home.

## Decision
Each Home card reads its own file once it is on screen, draws its shapes at once and plans its
markers in the background. The picture is stored in this browser (IndexedDB, up to 300) keyed by
the file's sha256 from the server, so a duplicate (same bytes) reuses it. Every save stores the
picture of exactly the bytes it wrote. Code: `web/src/app/thumbs.ts`.

## Consequences
- A new browser pays one read + one plan per visible file; a deploy (new core version) re-plans
  quietly once per browser, showing the old picture meanwhile.
- Revisit if Simple Hosted Files grows a thumbnail slot (a spec change, Zach's call).
