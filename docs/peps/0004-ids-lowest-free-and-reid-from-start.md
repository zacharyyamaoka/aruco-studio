# 0004 — New markers take the lowest free ids; Re-ID numbers a selection from a start, in reading order

Date: 2026-11-13 · Status: accepted · Merged: lane/os-margins-reid

## Context
Zach (2026-11-13), after pasting six markers that came out #59–64 on a page whose
markers stopped at #31: "they are not incrementing from the next available one … deleted
markers are not releasing their ids. By default when you copy paste markers they should
increment to the next available IDs in order left to right … from actually the available
IDs, deleted markers need to release. Ok but what if you want to increment from a higher
ID and leave a gap? Here is where Re-ID comes in: batch select a bunch of ids, set the
starting ID, and it will Re-ID all of them, left to right, top to bottom in priority …
starting ID 100 and then all of them would go 100, 101, etc."

## Decisions
1. **Next id, version 3: the lowest free block** (`core/autoid.py` rule 3', mode `"next"`,
   still the default). An id is in use only while its feature is in the request, so a deleted
   marker's ids are free at once. Version 2 (2026-10-20) numbered after the *highest* id in
   use and reused a freed id only at the dictionary's end, on purpose: *a freed id may still
   be printed on a part somewhere*. Zach chose release over that protection; the risk is
   now his to manage (a sticker from a deleted marker that is still on a part can share an
   id with a new marker). Rules 1 and 2 are untouched: ledger ids never move, typed ids are
   exact, a typed marker's old id stays held for it.
2. **Reading order is the order new ids are given out.** The core numbers in request order;
   the Studio puts pasted copies and the markers `A` makes on several rectangles into the
   document in reading order (`web/src/model/geom.ts` `readingOrder`: rows top to bottom, a
   row being the boxes level with its topmost one's middle, each row left to right), and
   Re-ID asks in reading order.
3. **Re-ID of a selection from a start.** The batch panel's *First ID* field numbers the
   selected markers from the typed id (`app/commands.ts` `reIdFrom`); the Re-ID dialog reads
   the canvas selection as well as the batch panel's, and the canvas menu offers it for 2+
   selected markers. *Keep typed ids* is a live switch: off by default for a selection (you
   picked them to renumber them), on for the whole document.
4. **A start past the dictionary grows it.** DICT_4X4_50 ends at #49, so "from 100" used to
   wrap to 0 with a warning, which read as Re-ID doing nothing. Now the renumbered markers
   move to the smallest dictionary of the same bit size that holds the ids (4X4_50 → 4X4_250;
   the first ids' patterns are the same in every size), and the note / dialog says so.

## Undo
`git revert` of the lane's merge restores version 2 and the document-order Re-ID; documents
keep whatever ids they were given (the ledger holds them).
