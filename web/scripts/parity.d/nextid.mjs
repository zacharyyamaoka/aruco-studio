// Lane "nextid" (2026-10-20 night): next id (core autoid rule 3', IdRequest.mode
// "next", the default) in Pyodide and CPython: a new driven marker takes the
// first free block after the highest id in use in its family, in document
// order; typed and reserved ids stepped over; families counted apart; past the
// dictionary's end, the lowest free block with an info issue; hash by name.
const item = (key, type = "single", dictionary = "DICT_4X4_50", count = 1, first_id = null) =>
  ({ key, type, dictionary, count, first_id });

export default function cases() {
  return [
    ["nextid empty document starts at 0", "assign_ids", { items: [item("a"), item("g", "grid", "DICT_4X4_50", 4), item("b")] }],
    ["nextid #5 pasted three times: 6, 7, 8", "assign_ids",
      { items: [item("five"), item("z"), item("m"), item("a")], ledger: { five: 5 } }],
    ["nextid typed 10 and reserved 12 stepped over", "assign_ids",
      { items: [item("a"), item("t", "single", "DICT_4X4_50", 1, 10), item("n"), item("g", "grid", "DICT_4X4_50", 3)], ledger: { a: 7 }, reserved: [12] }],
    ["nextid families counted apart (4x4 and 5x5)", "assign_ids",
      { items: [item("a4"), item("a5", "single", "DICT_5X5_100"), item("n4"), item("n5", "single", "DICT_5X5_100"), item("n4b", "single", "DICT_4X4_250")], ledger: { a4: 20, a5: 3 } }],
    ["nextid charuco block after the highest", "assign_ids",
      { items: [item("a"), item("c", "charuco", "DICT_5X5_100", 10), item("p", "single", "DICT_5X5_100")], ledger: { a: 5, gone: 30 } }],
    ["nextid wraps with an info issue", "assign_ids",
      { items: [item("hi"), item("t", "single", "DICT_4X4_50", 1, 0), item("n"), item("g", "grid", "DICT_4X4_50", 4)], ledger: { hi: 49 }, reserved: [1] }],
    ["nextid explicit, start ignored", "assign_ids", { items: [item("a"), item("b")], mode: "next", start: 30 }],
    ["nextid hash by name", "assign_ids", { items: [item("a"), item("b"), item("g", "grid", "DICT_4X4_250", 6)], mode: "hash" }],
  ];
}
