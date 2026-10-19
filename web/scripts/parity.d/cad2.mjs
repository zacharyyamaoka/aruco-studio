// Lane "cadfacade2" (2026-10-19): contract barrier 6, the Fusion adapter's N-8
// asks, in Pyodide and CPython: layers[].into, the corner mark in the layers
// (a ChArUco board's notch, the tile's corner cut), the 3D label's ink as a
// layer, pattern_to_sketch at full precision (turned rectangles: libm's cos /
// sin in both), SheetRequest.print_dialog, IdRequest.reserved per family.
export default function cases(presets, { marker, label, rect }) {
  const [d3, letter] = presets;
  const req = (m, r = {}, l = {}, preset = letter, face = false) =>
    ({ rect: rect(r), marker: marker(m), label: label(l), preset, reference_face: face });
  const item = (key, type = "single", dictionary = "DICT_4X4_50", count = 1, first_id = null) =>
    ({ key, type, dictionary, count, first_id });
  return [
    ["cad2 plan charuco + corner mark, inkjet, turned rect", "plan", req({ type: "charuco", cols: 5, rows: 4, corner_mark: "triangle" }, { w: 80, h: 60, angle_deg: 17.3 })],
    ["cad2 plan charuco + corner mark, 3D on a face", "plan", req({ type: "charuco", cols: 4, rows: 3, corner_mark: "triangle" }, { w: 80, h: 60 }, {}, d3, true)],
    ["cad2 plan grid + triangle, 3D free, flipped", "plan", req({ type: "grid", cols: 3, rows: 2, corner_mark: "triangle", flip: true }, { cx: 4, cy: -2, angle_deg: -33 }, {}, d3)],
    ["cad2 plan single, the tile's corner cut (3D free)", "plan", req({ corner_mark: "cut" }, { w: 40, h: 40, angle_deg: 12.5 }, {}, d3)],
    ["cad2 plan pixel label as a layer, turned 30", "plan", req({ first_id: 9 }, { cx: 15, cy: -8, w: 40, h: 50, angle_deg: 30 }, { on: true, text: "#{id}\n{dict}" }, d3)],
    ["cad2 plan pixel label on a face", "plan", req({ type: "grid", cols: 2, rows: 2 }, { w: 60, h: 70 }, { on: true, text: "{type} #{ids}", side: "above" }, d3, true)],
    ["cad2 sheet print_dialog", "sheet", { items: [req({}, { w: 20, h: 20 }, { on: true, text: "a" }), req({ type: "grid", cols: 3, rows: 2 }, { w: 120, h: 60 })], cut_lines: true, print_dialog: true, date: "2026-10-19" }],
    ["cad2 assign_ids reserved per family (map, short key)", "assign_ids",
      { items: [item("lid", "single", "DICT_4X4_50", 1, 3), item("a"), item("b", "single", "DICT_5X5_50"), item("g", "grid", "DICT_5X5_50", 4)],
        ledger: { a: 7, b: 7 }, reserved: { aruco4x4: [3, 7, 0, 1, 2], "5x5": [8, 9] } }],
    ["cad2 assign_ids bad family", "assign_ids", { items: [item("a")], reserved: { "9x9": [1] } }],
  ];
}
