// Lane "reid" (2026-10-20): Re-ID (contract barrier 8, IdRequest.mode / start /
// fresh) in Pyodide and CPython: sequential numbering in document order from
// `start`, per family, round typed and reserved ids, the ledger honoured or
// (fresh) dropped, a full dictionary, a bad mode.
const item = (key, type = "single", dictionary = "DICT_4X4_50", count = 1, first_id = null) =>
  ({ key, type, dictionary, count, first_id });

export default function cases() {
  const mixed = Array.from({ length: 12 }, (_, k) => k % 3 === 1
    ? item(`m${11 - k}`, "grid", "DICT_4X4_250", 2 + (k % 4))
    : item(`m${11 - k}`, "single", k % 2 ? "DICT_4X4_250" : "DICT_4X4_50"));
  const page = Array.from({ length: 40 }, (_, k) => item(`p${(k * 7) % 40}`));
  return [
    ["reid sequential 12 mixed from 0", "assign_ids", { items: mixed, mode: "sequential" }],
    ["reid sequential from 100, two families", "assign_ids",
      { items: [item("a", "single", "DICT_4X4_250"), item("p", "single", "DICT_5X5_100"), item("g", "grid", "DICT_4X4_1000", 6), item("q", "grid", "DICT_5X5_250", 3)], mode: "sequential", start: 100 }],
    ["reid sequential round typed + reserved (map)", "assign_ids",
      { items: [item("a"), item("t1", "single", "DICT_4X4_50", 1, 2), item("g", "grid", "DICT_4X4_50", 4), item("b"), item("t2", "grid", "DICT_4X4_50", 2, 5), item("c", "single", "DICT_5X5_50")],
        mode: "sequential", reserved: { "4x4": [0, 9], aruco5x5: [0] } }],
    ["reid sequential honours the ledger (no fresh)", "assign_ids",
      { items: [item("a"), item("b"), item("c"), item("d")], ledger: { b: 1, d: 40, gone: 2 }, mode: "sequential" }],
    ["reid sequential fresh drops the ledger, typed still win", "assign_ids",
      { items: [item("a"), item("x", "single", "DICT_4X4_50", 1, 0), item("y", "single", "DICT_4X4_50", 1, 0), item("b")], ledger: { a: 0, b: 30 }, mode: "sequential", fresh: true }],
    ["reid hash fresh (a page re-hashed)", "assign_ids", { items: page, ledger: { p0: 1, p7: 2 }, fresh: true }],
    ["reid sequential fresh, 40 on a page", "assign_ids", { items: page, ledger: { p0: 1, p7: 2 }, mode: "sequential", fresh: true }],
    ["reid sequential 60 in DICT_4X4_50 (full)", "assign_ids",
      { items: Array.from({ length: 60 }, (_, k) => item(`s${59 - k}`)), mode: "sequential", start: 3 }],
    ["reid bad mode", "assign_ids", { items: [item("a")], mode: "random" }],
    ["reid bad start", "assign_ids", { items: [item("a")], mode: "sequential", start: -1 }],
  ];
}
