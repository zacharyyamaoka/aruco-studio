// Lane verifyrange (2026-10-21, V4 "Range strip"): the reading range's engine
// (aruco_studio/core/reading_range.py) byte-identical in Pyodide and CPython.
// The engine never renders, so it runs end to end here on its pinhole reader
// ("analytic": the stdlib path; OpenCV's renders are compared in the e2e,
// against a CPython with the browser's OpenCV): the bracket, the 48 seeded
// SplitMix64 cases, the PAVA'd crossing, the 200 resamples, the near end;
// then the camera library and judge()'s verdicts and words.
export default function (presets, { marker, label, rect }) {
  const [, letter] = presets;
  const req = (m = {}, r = {}, l = {}) => ({ rect: rect(r), marker: marker(m), label: label(l), preset: letter, reference_face: false });
  const single = req({ auto: false, marker_mm: 30, first_id: 7 }, { w: 40, h: 40 });
  const grid = req({ type: "grid", cols: 3, rows: 1, auto: false, marker_mm: 30, separation_mm: 10, first_id: 19 }, { w: 113.5, h: 40 },
    { on: true, text: "#{ids}", place: "outside" });
  const range = (r, camera, extra = {}) => ({ req: r, camera, reader: "analytic", ...extra });
  // a fixed answer to judge, so the words are compared on their own
  const answer = { near_mm: 111.6, far_mm: 1181.2, near_by: "reads", far_limit: "cells", far_outline_px: 141.9, min_outline_px: 57.6,
    geometry: { bounds_mm: [-56.75, -20, 56.75, 20], cell_mm: 5, marker_mm: 30, ids: [19, 20, 21] } };
  return [
    ["cameras: the library and its sources", "cameras", {}],
    ["reading_range analytic: a 30 mm single on the D435", "reading_range", range(single, "d435")],
    ["reading_range analytic: a 3x1 grid with an outside label on the OAK-D 12 MP (focus 80 mm)", "reading_range", range(grid, "oakd12")],
    ["reading_range analytic: a custom camera, its focus at 400 mm, another seed, 32 cases", "reading_range",
      range(single, { resolution: [1280, 800], hfov_deg: 90, focus_mm: 400 }, { seed: 7, cases: 32 })],
    ["reading_range analytic: too small to read anywhere", "reading_range", range(req({ auto: false, marker_mm: 0.4 }, { w: 1, h: 1 }), "d405")],
    ["reading_range: an unknown camera, the same words", "reading_range", range(single, "kinect")],
    ["range_judge: covered", "range_judge", { range: answer, need: { min_mm: 300, max_mm: 1000 } }],
    ["range_judge: short at the far end, the size that reaches", "range_judge", { range: answer, need: { min_mm: 300, max_mm: 2000 } }],
    ["range_judge: too near and too far, no one size", "range_judge", { range: answer, need: { min_mm: 50, max_mm: 4000 } }],
    ["range_judge: nothing required", "range_judge", { range: answer, need: {} }],
  ];
}
