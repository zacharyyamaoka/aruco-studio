// Lane "cadfacade" (2026-10-18): the fields a CAD shell reads (contract barrier
// 4, the Fusion adapter's N-6 report) in Pyodide and CPython: layers, cells and
// pattern_to_sketch, origin_z_mm, per-line label centres, sheet placements and
// the PDF's print flags, reserved ids, the exact plain-rectangle inscribe.
// readable is not here: Node's Pyodide has no OpenCV, so it answers
// analytically (measured false) where CPython measures.
export default function cases(presets, { marker, label, rect }) {
  const [d3, letter] = presets;
  const req = (m, r = {}, l = {}, preset = letter, face = false) =>
    ({ rect: rect(r), marker: marker(m), label: label(l), preset, reference_face: face });
  const item = (key, type = "single", dictionary = "DICT_4X4_50", count = 1, first_id = null) =>
    ({ key, type, dictionary, count, first_id });
  return [
    ["cad plan inkjet, flipped grid on a turned rect", "plan", req({ type: "grid", cols: 3, rows: 2, turn: 90, flip: true }, { cx: 15, cy: -8, angle_deg: 30 })],
    ["cad plan 3D on a face, corner mark", "plan", req({ corner_mark: "triangle" }, { w: 30, h: 30 }, {}, d3, true)],
    ["cad plan charuco 3D free", "plan", req({ type: "charuco", cols: 5, rows: 4 }, { w: 80, h: 60 }, {}, d3)],
    ["cad plan sans label, 3 lines", "plan", req({ first_id: 4 }, { w: 40, h: 50, angle_deg: 12.5 }, { on: true, text: "#{id}\n{dict}\n{type}" })],
    ["cad plan pixel label, 2 lines", "plan", req({}, { w: 40, h: 50 }, { on: true, text: "#{id}\n{dict}" }, d3)],
    ["cad sheet placements + print flags", "sheet", { items: [req({}, { w: 20, h: 20 }, { on: true, text: "a" }), req({ auto: false, marker_mm: 300 }, { w: 300, h: 300 }), req({ type: "grid", cols: 3, rows: 2 }, { w: 120, h: 60 })], cut_lines: true, mode: "tight", date: "2026-10-18" }],
    ["cad inscribe a plain 50 x 80 rectangle", "inscribe", { profile: { loops: [[[0, 0], [50, 0], [50, 80], [0, 80]]] }, holes: "avoid" }],
    ["cad assign_ids reserved (typed hit, ledger moved, per family)", "assign_ids",
      { items: [item("lid", "single", "DICT_4X4_50", 1, 3), item("a"), item("g", "grid", "DICT_5X5_50", 4)], ledger: { a: 7 }, reserved: [3, 7, 0, 1, 2] }],
    ["cad assign_ids bad reserved", "assign_ids", { items: [item("a")], reserved: [-1] }],
  ];
}
