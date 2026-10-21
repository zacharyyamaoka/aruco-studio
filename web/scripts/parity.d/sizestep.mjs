// Lane sizestep (contract barrier 11, 2026-10-20 night): the size step --
// whole printer dots (autosize rule 3: 25.4 / dpi exactly, typed sizes as
// typed), a round mm step (rule 2 on 0.1 / 0.5 / 1) or the 3D line; the
// marker's over the preset's; the Marker row's note -- so Pyodide and
// CPython agree on it.
export default function (presets, { marker, label, rect }) {
  const [d3, letter, a4] = presets;
  const req = (m, r = {}, preset = letter) =>
    ({ rect: rect(r), marker: marker(m), label: label({}), preset, reference_face: false });
  const dots = { of: "dots" };
  const mm = (v) => ({ of: "mm", mm: v });
  const grid31 = { type: "grid", cols: 3, rows: 1 };
  const board = { type: "charuco", cols: 5, rows: 4 };
  return [
    ["sizestep: single dots 37.3 x 37.3 (27.94 exact)", "plan", req({ size_step: dots }, { w: 37.3, h: 37.3 })],
    ["sizestep: grid 3x1 dots in 112 x 40", "plan", req({ ...grid31, size_step: dots }, { w: 112, h: 40 })],
    ["sizestep: charuco dots, A4 preset's own step", "plan", req(board, { w: 93, h: 71 }, { ...a4, size_step: dots })],
    ["sizestep: charuco set checker 17.33, dots", "plan", req({ ...board, checker_mm: 17.33, size_step: dots }, { w: 93, h: 71 })],
    ["sizestep: typed 29.97 / 6.0113, dots", "plan", req({ ...grid31, auto: false, marker_mm: 29.97, separation_mm: 6.0113, size_step: dots }, { w: 120, h: 45 })],
    ["sizestep: grid 3x1 0.1 mm, rotated", "plan", req({ ...grid31, size_step: mm(0.1) }, { w: 120, h: 45, angle_deg: 17 })],
    ["sizestep: charuco 1 mm", "plan", req({ ...board, size_step: mm(1) }, { w: 93, h: 71 })],
    ["sizestep: the marker's 1 mm over the preset's dots", "plan", req({ ...grid31, size_step: mm(1) }, { w: 112, h: 40 }, { ...letter, size_step: dots })],
    ["sizestep: a step it cannot read (said)", "plan", req({ size_step: { of: "inches" } }, { w: 40, h: 40 })],
    ["sizestep: dots on a 3D preset (no dpi, said)", "plan", req({}, { w: 40, h: 40 }, { ...d3, size_step: dots })],
    ["sizestep: 3D line on the marker", "plan", req({ ...grid31, size_step: { of: "line" } }, { w: 112, h: 40 }, { ...d3, cell_step_mm: 0.675 })],
    ["sizestep: suggest grid, dots", "suggest", req({ type: "grid", size_step: dots }, { w: 112, h: 40 })],
    ["sizestep: suggest charuco, 0.1 mm", "suggest", req({ type: "charuco", size_step: mm(0.1) }, { w: 93, h: 71 })],
    ["sizestep: svg single, dots", "svg", req({ size_step: dots }, { w: 37.3, h: 37.3 })],
  ];
}
