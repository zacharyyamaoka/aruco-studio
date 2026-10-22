// Lane onecv (2026-10-21): scene_keys, the key Verify's range cache uses
// (web_api.scene_key: what a camera sees of a marker, in its own frame) --
// the same digest in Pyodide and CPython, for a moved and turned profile
// too, so a browser's cache and a script agree on what is the same marker.
export default function (presets, { marker, label }) {
  const [d3, letter] = presets;
  const corners = (cx, cy, w, h, deg) => {
    const a = (deg * Math.PI) / 180, c = Math.cos(a), s = Math.sin(a);
    return [[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2], [-w / 2, h / 2]].map(([u, v]) => [cx + u * c - v * s, cy + u * s + v * c]);
  };
  const req = (cx, cy, deg, m = {}, l = {}, preset = letter) => ({ trim: "profile", profile: { loops: [corners(cx, cy, 123.5, 40, deg)] },
    holes: "avoid", marker: marker({ type: "grid", cols: 3, rows: 1, first_id: 19, corner_mark: "triangle", ...m }),
    label: label({ on: true, text: "#{ids}", place: "on_marker", ...l }), preset, reference_face: false, extrude: {} });
  return [
    ["scene_keys: a grid, moved and turned, then edited", "scene_keys", { reqs: [
      req(0, 0, 0), req(37.5, -12.25, 30), req(-80, 55, 135), req(0, 0, 0, { first_id: 31 }), req(0, 0, 0, {}, { on: false }),
      req(0, 0, 0, { dictionary: "DICT_4X4_100" }), req(0, 0, 0, {}, {}, d3), { bad: 1 },
    ] }],
  ];
}
