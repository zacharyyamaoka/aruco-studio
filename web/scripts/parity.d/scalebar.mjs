// Lane scalebar (2026-10-20 night): sheet() with scale_bar hide | first | every
// on multi-page sets, so Pyodide and CPython agree on which pages draw the bar
// and keep its band (the packer's per-page height), and on the info issue.
export default function (presets, { marker, label, rect }) {
  const [, letter, a4] = presets;
  const squares = (n, side, preset = letter) => Array.from({ length: n }, (_, i) =>
    ({ rect: rect({ w: side, h: side }), marker: marker({ first_id: i, dictionary: "DICT_4X4_250" }), label: label(), preset, reference_face: false }));
  const date = "2026-10-20";
  const cases = [];
  for (const scale_bar of ["hide", "first", "every"]) {
    cases.push([`sheet scale_bar ${scale_bar}: 66 x 41.5 mm tight, letter`, "sheet", { items: squares(66, 41.5), cut_lines: true, mode: "tight", scale_bar, date }]);
    cases.push([`sheet scale_bar ${scale_bar}: 40 x 44 mm spaced, fewest cuts, A4`, "sheet", { items: squares(40, 44, a4), cut_lines: true, mode: "spaced", objective: "fewest_cuts", scale_bar, date }]);
  }
  cases.push(["sheet scale_bar default (first): 66 x 41.5 mm tight, letter", "sheet", { items: squares(66, 41.5), cut_lines: true, mode: "tight", date }]);
  cases.push(["sheet scale_bar nonsense: an error, the same words", "sheet", { items: squares(2, 40), scale_bar: "sometimes", date }]);
  return cases;
}
