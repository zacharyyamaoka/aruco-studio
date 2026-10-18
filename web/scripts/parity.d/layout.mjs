// Lane layout (2026-10-18): auto layout through sheet() -- core.pack's
// guillotine packer, tight and spaced, gap_mm, a sticker that has to turn,
// A4 -- so Pyodide and CPython agree on the placements, cuts and fill.
export default function (presets, { marker, label, rect }) {
  const [, letter, a4] = presets;
  const req = (m, r = {}, l = {}, preset = letter) =>
    ({ rect: rect(r), marker: marker(m), label: label(l), preset, reference_face: false });
  const squares = (n, side, l = {}, preset = letter) =>
    Array.from({ length: n }, (_, i) => req({ first_id: i }, { w: side, h: side }, l, preset));
  const mixed = [[40, 40], [40, 40], [30, 30], [30, 30], [50, 25], [25, 50], [90, 35], [35, 90], [70, 22], [22, 70]]
    .map(([w, h], i) => req({ first_id: i }, { w, h }));
  const date = "2026-10-18";
  return [
    ["sheet layout: 12 x 40 mm tight, letter", "sheet", { items: squares(12, 40), cut_lines: true, mode: "tight", date }],
    ["sheet layout: 12 x 40 mm spaced with labels, letter", "sheet", { items: squares(12, 40, { on: true, text: "part {id}" }), cut_lines: true, mode: "spaced", date }],
    ["sheet layout: mixed sizes tight, letter", "sheet", { items: mixed, cut_lines: true, mode: "tight", date }],
    ["sheet layout: mixed sizes spaced, gap 7, A4", "sheet", { items: mixed.map((it) => ({ ...it, preset: a4 })), cut_lines: false, mode: "spaced", gap_mm: 7, date }],
    ["sheet layout: a grid longer than the page turns", "sheet", { items: [req({ type: "grid", cols: 8, rows: 1 }, { w: 220, h: 30 }), ...squares(4, 30)], cut_lines: true, mode: "tight", date }],
  ];
}
