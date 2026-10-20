// Lane "core3d" (2026-10-20 night, contract barrier 10): ArUco Extrude's
// heights -- PlanRequest.extrude driven from the preset (whole layers under a
// layered preset, 2.0 / 0.6 under Default) or set (honoured exactly, said on
// "extrude.<field>"), the black from the white's outer face, Black only into
// the body, White only with its label in `layers`, the inkjet paper, and Flip
// on a reference face, in Pyodide and CPython. The rules:
// tests/web/test_web_extrude.py.
export default function cases(presets, { marker, label, rect }) {
  const [d3, letter] = presets;
  const aruco = { ...d3, id: "aruco", name: "Aruco", builtin: false, nozzle_mm: 0.6, line_mm: 0.68,
    layer_mm: 0.32, first_layer_mm: 0.2 };
  const req = (extrude, m = {}, l = {}, preset = aruco, face = false, r = { w: 30, h: 36 }) => {
    const out = { rect: rect(r), marker: marker(m), label: label(l), preset, reference_face: face };
    if (extrude !== undefined) out.extrude = extrude;
    return out;
  };
  const outside = { on: true, text: "#{id}", place: "outside" };
  return [
    ["extrude plan driven, Aruco layers", "plan", req({})],
    ["extrude plan driven, Default", "plan", req({}, {}, {}, d3)],
    ["extrude plan no extrude, Aruco layers", "plan", req(undefined)],
    ["extrude plan set 3.0 / 1.0", "plan", req({ white_mm: 3, black_mm: 1 }, { type: "grid", cols: 2, rows: 2 }, {}, aruco, false, { w: 50, h: 50 })],
    ["extrude plan black only on a face", "plan", req({ black_mm: 0.84 }, {}, {}, aruco, true)],
    ["extrude plan black only on a face, flipped", "plan", req({}, { flip: true, corner_mark: "triangle" }, {}, aruco, true)],
    ["extrude plan both on a face", "plan", req({ mode: "both" }, { type: "charuco", cols: 4, rows: 3 }, {}, aruco, true, { w: 80, h: 60 })],
    ["extrude plan black taller than white", "plan", req({ white_mm: 1, black_mm: 1.4 })],
    ["extrude plan negative black (raised)", "plan", req({ black_mm: -0.3 })],
    ["extrude plan zero black (refused)", "plan", req({ black_mm: 0 })],
    ["extrude plan junk", "plan", req({ mode: "grey", white_mm: "tall", black_mm: true })],
    ["extrude plan white only, label outside, on a face", "plan", req({ mode: "white" }, {}, outside, aruco, true)],
    ["extrude plan white only, label knocked out", "plan", req({ mode: "white" }, {}, { on: true, text: "#{id}" })],
    ["extrude plan white only, label on the white", "plan", req({ mode: "white" }, {}, { on: true, text: "#{id}", surface: "white" }, aruco, true)],
    ["extrude plan inkjet driven", "plan", req({}, {}, {}, letter)],
    ["extrude plan inkjet paper 0.2, 3D fields said", "plan", req({ paper_mm: 0.2, white_mm: 3 }, {}, {}, letter)],
    ["extrude plan inkjet paper 0.01 (the core clamps, said)", "plan", req({ paper_mm: 0.01 }, {}, {}, letter)],
    ["extrude plan inkjet on a face, flipped, label", "plan", req({}, { flip: true }, { on: true, text: "#{id}" }, letter, true)],
    ["extrude svg inkjet paper 0.2", "svg", req({ paper_mm: 0.2 }, {}, { on: true, text: "#{id}" }, letter)],
    ["extrude svg white only", "svg", req({ mode: "white" }, {}, outside)],
    ["extrude sheet mixed", "sheet", { items: [req({ paper_mm: 0.2 }, {}, {}, letter), req({ white_mm: 1 }, { first_id: 3 }), req({ black_mm: 0 }, { first_id: 6 })], cut_lines: true, date: "2026-10-20" }],
  ];
}
