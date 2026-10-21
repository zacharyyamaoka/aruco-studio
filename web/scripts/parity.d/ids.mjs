// Lane "ids" (2026-10-18): assign_ids in Pyodide and CPython. Counts are the
// core's board.marker_count (a ChArUco 5x4 board prints 10 markers; pinned in
// tests/core/test_autoid.py).
const item = (key, type = "single", dictionary = "DICT_4X4_50", count = 1, first_id = null) =>
  ({ key, type, dictionary, count, first_id });

export default function cases() {
  const doc = [item("plate-a"), item("plate-b", "grid", "DICT_4X4_50", 6), item("cal", "charuco", "DICT_5X5_100", 10),
    item("lid", "single", "DICT_4X4_250", 1, 7), item("base", "grid", "DICT_4X4_250", 4)];
  const sixty = Array.from({ length: 60 }, (_, k) => item(`s${String(k).padStart(2, "0")}`));
  return [
    // WHY mode "hash" on these two (2026-10-20 night): "next" is the default now
    // and numbers in document order; the order-free answer is the hash's
    ["assign_ids mixed document, no ledger", "assign_ids", { items: doc, mode: "hash" }],
    ["assign_ids shuffled, same answer by key", "assign_ids", { items: [...doc].reverse(), mode: "hash" }],
    ["assign_ids with a ledger (kept, a new key routed round)", "assign_ids",
      { items: [item("plate-a"), item("new", "grid", "DICT_4X4_50", 4)], ledger: { "plate-a": 3, gone: 9 } }],
    ["assign_ids typed ranges that overlap (both flagged)", "assign_ids",
      { items: [item("x", "grid", "DICT_4X4_50", 4, 10), item("y", "single", "DICT_4X4_1000", 1, 12)] }],
    ["assign_ids 60 singles in DICT_4X4_50 (full: names DICT_4X4_100)", "assign_ids", { items: sixty }],
    ["assign_ids unicode key", "assign_ids", { items: [item("Deckel · ü/1"), item("蓋")] }],
    ["assign_ids bad request (duplicate key)", "assign_ids", { items: [item("a"), item("a")] }],
  ];
}
