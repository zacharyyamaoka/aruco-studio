// Lane "plan2" (2026-10-18, contract 56235bd): the label INSIDE the marker
// rectangle, its font by method (sans inkjet / pixel 3D), multi-line text,
// the ChArUco origin in a square, the dimensions and the cut line, in Pyodide
// and CPython. The rules: tests/web/test_web_plan2.py.
export default function cases(presets, { marker, label, rect }) {
  const [d3, letter] = presets;
  const req = (m, r = {}, l = {}, preset = letter) =>
    ({ rect: rect(r), marker: marker(m), label: label(l), preset, reference_face: false });
  const on = (l = {}) => ({ on: true, text: "#{ids}", ...l });
  return [
    ["plan2 label below, grid 4x4", "plan", req({ type: "grid", cols: 4, rows: 4 }, { w: 60, h: 60 }, on())],
    ["plan2 label above, single", "plan", req({}, { w: 40, h: 40 }, on({ side: "above" }))],
    ["plan2 label left, charuco 5x4", "plan", req({ type: "charuco", cols: 5, rows: 4 }, { w: 80, h: 60 }, on({ side: "left" }))],
    ["plan2 label right + offset, rotated 30", "plan", req({ type: "grid", cols: 3, rows: 2 }, { cx: 7, cy: -4, w: 70, h: 50, angle_deg: 30 }, on({ side: "right", offset_mm: [1, 2] }))],
    ["plan2 multi-line, typed cap", "plan", req({}, { w: 30, h: 40 }, on({ text: "#{id}\n{dict}\n{type}", height_mm: 2.5 }))],
    ["plan2 3D pixel font, two lines", "plan", req({ type: "grid", cols: 2, rows: 2, turn: 90, flip: true }, { w: 50, h: 70, angle_deg: 12.5 }, on({ text: "#{ids}\nlid ü" }), d3)],
    ["plan2 3D typed thin cap (warned)", "plan", req({}, { w: 30, h: 30 }, on({ height_mm: 2 }), d3)],
    ["plan2 typed size over the box", "plan", req({ auto: false, marker_mm: 30 }, { w: 40, h: 40 }, on({ height_mm: 5, gap_mm: 1 }), { ...letter, cell_step_mm: 0 })],
    ["plan2 charuco origin_square [2,1]", "plan", req({ type: "charuco", cols: 5, rows: 4, origin_square: [2, 1] }, { w: 80, h: 60 })],
    ["plan2 charuco origin_square turned, rotated", "plan", req({ type: "charuco", cols: 5, rows: 4, turn: 90, origin_square: [3, 4] }, { cx: 5, cy: -3, w: 80, h: 60, angle_deg: 30 })],
    ["plan2 charuco origin_square out of range", "plan", req({ type: "charuco", cols: 5, rows: 4, origin_square: [5, 0] }, { w: 80, h: 60 })],
    ["plan2 grid 1x3 dims (vertical gap)", "plan", req({ type: "grid", cols: 1, rows: 3 }, { w: 30, h: 90 })],
    ["plan2 svg sans, two lines", "svg", req({ auto: false, marker_mm: 15 }, { w: 30, h: 40 }, on({ text: "#{id}\n{dict}" }))],
    ["plan2 svg pixel", "svg", req({ type: "grid", cols: 2, rows: 1 }, { w: 50, h: 30 }, on({ side: "left" }), d3)],
  ];
}
