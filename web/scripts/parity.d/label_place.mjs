// Lane "core3" (contract barrier 7, 2026-10-20): the label ON the marker (its
// border row knocked out white, a ChArUco black square, or the white quiet
// zone) or OUTSIDE it at one module, and a set checker / separation honoured
// with Auto on, in Pyodide and CPython: plan, svg and sheet.
export default function cases(presets, { marker, label, rect }) {
  const [d3, letter] = presets;
  const req = (m = {}, l = {}, r = {}, preset = letter) =>
    ({ rect: rect(r), marker: marker(m), label: label({ on: true, text: "#{ids}", ...l }), preset, reference_face: false });
  const grid = { type: "grid", cols: 3, rows: 2 };
  const charuco = { type: "charuco", cols: 5, rows: 4, first_id: 35 };
  const board = { w: 80, h: 60 };
  return [
    ["label_place plan single, black below (the default)", "plan", req({}, {}, { w: 40, h: 40 })],
    ["label_place plan single, black left, turned rect", "plan", req({}, { side: "left" }, { w: 40, h: 40, angle_deg: 30 })],
    ["label_place plan single, white right, offset", "plan", req({}, { surface: "white", side: "right", offset_mm: [0.5, -1] }, { w: 40, h: 40 })],
    ["label_place plan grid, black above, two lines (warned)", "plan", req(grid, { side: "above", text: "#{ids}\n{dict}" })],
    ["label_place plan grid, white below", "plan", req(grid, { surface: "white" })],
    ["label_place plan charuco, black below", "plan", req(charuco, {}, board)],
    ["label_place plan charuco, white left", "plan", req(charuco, { surface: "white", side: "left" }, board)],
    ["label_place plan single 3D, black below (knocked-out ink)", "plan", req({}, {}, { w: 100, h: 100 }, d3)],
    ["label_place plan grid 3D, white above", "plan", req(grid, { surface: "white", side: "above" }, { w: 120, h: 80 }, d3)],
    ["label_place plan outside, driven one module", "plan", req(grid, { place: "outside" })],
    ["label_place plan outside 3D, left", "plan", req({}, { place: "outside", side: "left" }, { w: 60, h: 40 }, d3)],
    ["label_place plan typed cap over the row (warned)", "plan", req({}, { height_mm: 6 }, { w: 40, h: 40 })],
    ["label_place plan marker trim keeps a label on the marker", "plan", { ...req({}, {}, { w: 40, h: 40 }), trim: "marker" }],
    ["label_place svg single, knocked out, left", "svg", req({}, { side: "left" }, { w: 40, h: 40 })],
    ["label_place svg single, white below", "svg", req({}, { surface: "white" }, { w: 40, h: 40 })],
    ["label_place svg 3D, knocked out", "svg", req({}, {}, { w: 100, h: 100 }, d3)],
    ["label_place sheet knocked out, turned, white", "sheet", { items: [req({}, { side: "left" }, { w: 40, h: 40 }), req({}, { side: "right", first_id: 1 }, { w: 40, h: 40 }), req(grid, { surface: "white" }), req(charuco, {}, board)], cut_lines: true, date: "2026-10-20" }],
    ["label_place plan charuco auto, checker 20 as typed (overflow)", "plan", req({ ...charuco, checker_mm: 20 }, { on: false }, { w: 61.6, h: 77 }, d3)],
    ["label_place plan grid auto, separation 5 as typed", "plan", req({ ...grid, separation_mm: 5 }, { on: false })],
    ["label_place plan single, quiet zone 0 as typed", "plan", req({ quiet_modules: 0 }, { on: false }, { w: 40, h: 40 })],
  ];
}
