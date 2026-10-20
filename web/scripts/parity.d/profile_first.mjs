// Lane "profcore" (2026-10-20 evening, contract barrier 9): PROFILE first --
// requests with a profile and no rect, the core placing the marker (the
// profile itself when it is a rectangle, rotated too; else the largest clear
// box, holes avoided or ignored) and returning it as fit_rect; trim profile /
// marker, the deprecated "rectangle", and a profile with no room, in Pyodide
// and CPython. The rules: tests/web/test_web_profile_first.py.
export default function cases(presets, { marker, label }) {
  const [d3, letter] = presets;
  const disc = (cx, cy, rad, n = 72) => Array.from({ length: n }, (_, k) =>
    [cx + rad * Math.cos(-2 * Math.PI * k / n), cy + rad * Math.sin(-2 * Math.PI * k / n)]);
  const plate = { loops: [[[-60, -40], [60, -40], [60, 40], [-60, 40]], disc(-35, 0, 10), disc(35, 0, 10)] };
  const corners = ({ cx, cy, w, h, angle_deg }) => {
    const a = (angle_deg * Math.PI) / 180, c = Math.cos(a), s = Math.sin(a);
    return [[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2], [-w / 2, h / 2]]
      .map(([u, v]) => [cx + u * c - v * s, cy + u * s + v * c]);
  };
  const turned = { loops: [corners({ cx: 5, cy: 3, w: 30, h: 20, angle_deg: 30 })] };
  const tilted = { loops: [corners({ cx: -4, cy: 2, w: 40, h: 24, angle_deg: 120 })] };
  const tiny = { loops: [[[0, 0], [0.05, 0], [0, 0.05]]] };
  const req = (profile, extra = {}, m = {}, l = {}, preset = letter) =>
    ({ profile, marker: marker(m), label: label(l), preset, reference_face: false, ...extra });
  return [
    ["profile plan plate, holes avoid", "plan", req(plate)],
    ["profile plan plate, holes ignore", "plan", req(plate, { holes: "ignore" })],
    ["profile plan plate, grid + label outside", "plan", req(plate, {}, { type: "grid", cols: 3, rows: 2 }, { on: true, text: "#{ids}", place: "outside" })],
    ["profile plan rectangle at 30 deg, label on", "plan", req(turned, {}, {}, { on: true, text: "#{id}" })],
    ["profile plan rectangle at 120 deg, 3D", "plan", req(tilted, {}, { type: "charuco", cols: 4, rows: 3 }, {}, d3)],
    ["profile plan trim marker", "plan", req(plate, { trim: "marker" })],
    ["profile plan trim rectangle (reads as profile, said)", "plan", req(plate, { trim: "rectangle" })],
    ["profile plan no clear box (refused)", "plan", req(tiny)],
    ["profile suggest plate", "suggest", req(plate, {}, { type: "grid" })],
    ["profile svg plate, label on", "svg", req(plate, {}, {}, { on: true, text: "lid {id}" })],
    ["profile svg rectangle at 30 deg", "svg", req(turned)],
    ["profile svg no clear box (error)", "svg", req(tiny)],
    ["profile sheet mixed", "sheet", { items: [req(plate), req(turned, {}, { first_id: 4 }, { on: true, text: "#{id}" }), req(plate, { trim: "marker", holes: "ignore" }, { first_id: 9 }), req(tiny)], cut_lines: true, date: "2026-10-20" }],
  ];
}
