// Lane round (2026-10-20 night): cells rule 2 (autosize.ROUND_RULE) -- an
// inkjet preset's driven marker, grid separation and ChArUco checker on
// 0.5 mm, re-fitted to the box; set values as typed; the dots note on the
// Marker row; the suggestions round -- so Pyodide and CPython agree on it.
export default function (presets, { marker, label, rect }) {
  const [d3, letter, a4] = presets;
  const req = (m, r = {}, l = {}, preset = letter, face = false) =>
    ({ rect: rect(r), marker: marker(m), label: label(l), preset, reference_face: face });
  // barrier 11: no size step over it, so the cell step is what it is made by
  const { size_step: _, ...noStep } = letter;
  const dots = { ...noStep, cell_step_mm: 0.042333 };
  const grid31 = { type: "grid", cols: 3, rows: 1 };
  return [
    ["round: Zach's 3x1 in 112 x 40 (was 29.9718 / 6.0113)", "plan", req(grid31, { w: 112, h: 40 })],
    ["round: the same board under the dots", "plan", req(grid31, { w: 112, h: 40 }, {}, dots)],
    ["round: 3x1 in 120 x 45, the gap to nearest", "plan", req(grid31, { w: 120, h: 45, angle_deg: 17 })],
    ["round: grid 2x2 on a face, A4", "plan", req({ type: "grid", cols: 2, rows: 2 }, { w: 77, h: 61 }, {}, a4, true)],
    ["round: single 40 x 40 (29.5 mm, the dots note)", "plan", req({}, { w: 40, h: 40 })],
    ["round: charuco 5x4 in 93 x 71", "plan", req({ type: "charuco", cols: 5, rows: 4 }, { w: 93, h: 71 })],
    ["round: typed 29.97 / 6.0113 as typed", "plan", req({ ...grid31, auto: false, marker_mm: 29.97, separation_mm: 6.0113 }, { w: 120, h: 45 })],
    ["round: typed 29.97, driven gap", "plan", req({ ...grid31, auto: false, marker_mm: 29.97 }, { w: 120, h: 45 })],
    ["round: set checker 17.33 with Auto", "plan", req({ type: "charuco", cols: 5, rows: 4, checker_mm: 17.33 }, { w: 93, h: 71 })],
    ["round: label outside, grid 3x1", "plan", req(grid31, { w: 120, h: 60 }, { on: true, text: "#{ids}", place: "outside" })],
    ["round: suggest grid 112 x 40", "suggest", req({ type: "grid" }, { w: 112, h: 40 })],
    ["round: suggest charuco 93 x 71", "suggest", req({ type: "charuco" }, { w: 93, h: 71 })],
    ["round: 3D default grid 3x1 unchanged", "plan", req(grid31, { w: 112, h: 40 }, {}, d3)],
    ["round: svg grid 3x1", "svg", req(grid31, { w: 112, h: 40 })],
  ];
}
