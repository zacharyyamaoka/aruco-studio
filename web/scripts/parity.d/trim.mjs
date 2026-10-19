// Lane "trim" (2026-10-18): the sticker cut to the profile, the rectangle
// (default) or the marker (contract barrier 5), in Pyodide and CPython: plan's
// cut / cut_shape and inkjet paper layer, the white-filled svg, the sheet
// cut along every sticker's cut_shape, and the trim's issues.
export default function cases(presets, { marker, label, rect }) {
  const [d3, letter] = presets;
  const disc = (cx, cy, rad, n = 72) => Array.from({ length: n }, (_, k) =>
    [cx + rad * Math.cos(-2 * Math.PI * k / n), cy + rad * Math.sin(-2 * Math.PI * k / n)]);
  const plate = { loops: [[[-60, -40], [60, -40], [60, 40], [-60, 40]], disc(-35, 0, 10), disc(35, 0, 10)] };
  const req = (trim, m = {}, r = {}, l = {}, preset = letter, profile = plate) =>
    ({ trim, profile, rect: rect(r), marker: marker(m), label: label(l), preset, reference_face: false });
  const clear = { w: 40, h: 40 };
  const turned = { cx: 5, cy: 3, w: 30, h: 20, angle_deg: 30 };
  return [
    ["trim plan rectangle, label on", "plan", req("rectangle", {}, clear, { on: true, text: "#{id}" })],
    ["trim plan profile with holes, turned rect, flip", "plan", req("profile", { flip: true }, turned)],
    ["trim plan profile, no profile (the rectangle, said)", "plan", req("profile", {}, clear, {}, letter, undefined)],
    ["trim plan profile, rectangle pokes out", "plan", req("profile", {}, { w: 100, h: 40 })],
    ["trim plan marker, label on (warned)", "plan", req("marker", { type: "grid", cols: 2, rows: 2 }, { w: 40, h: 50 }, { on: true, text: "#{ids}" })],
    ["trim plan profile, 3D", "plan", req("profile", {}, clear, { on: true, text: "#{id}" }, d3)],
    ["trim svg rectangle, label off", "svg", req("rectangle", {}, { w: 30, h: 40 })],
    ["trim svg profile, turned rect, label on", "svg", req("profile", {}, turned, { on: true, text: "lid" })],
    ["trim svg marker", "svg", req("marker", {}, { w: 30, h: 40 })],
    ["trim sheet mixed, spaced", "sheet", { items: [req("rectangle", {}, { w: 30, h: 24 }), req("profile", {}, turned, { on: true, text: "lid" }), req("marker", {}, { w: 30, h: 40 }, { on: true, text: "#{id}" }), req("profile")], cut_lines: true, date: "2026-10-18" }],
    ["trim sheet mixed, tight", "sheet", { items: [req("rectangle", {}, { w: 30, h: 24 }, { on: true, text: "a" }), req("profile"), req("marker", { first_id: 3 }, { w: 30, h: 40 })], cut_lines: true, mode: "tight", date: "2026-10-18" }],
  ];
}
