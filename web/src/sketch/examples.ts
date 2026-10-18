// The golden examples: faces as sketches of the same closed shapes a user
// draws (a rectangle with two circles is the plate). Polygons are data.
import type { Vec2 } from "../core/contract";
import { circleShape, rectShape, type Shape } from "./model";

export interface Example { id: string; name: string; note: string; shapes: Shape[] }

/** A rounded end as points (counter-clockwise about c from a0 to a1, degrees). */
function arc(c: Vec2, r: number, a0: number, a1: number, n = 12): Vec2[] {
  const out: Vec2[] = [];
  for (let i = 0; i <= n; i++) {
    const a = ((a0 + ((a1 - a0) * i) / n) * Math.PI) / 180;
    out.push([+(c[0] + r * Math.cos(a)).toFixed(3), +(c[1] + r * Math.sin(a)).toFixed(3)]);
  }
  return out;
}

// the forearm's side: 160 long, 45 tall at the elbow tapering to 34 at the
// wrist, both ends rounded
const FOREARM: Vec2[] = [
  ...arc([142, 22.5], 17, -90, 90),
  ...arc([22.5, 22.5], 22.5, 90, 270),
];

export const EXAMPLES: Example[] = [
  {
    id: "plate", name: "Plate", note: "120 × 80 mm, two Ø20 holes",
    shapes: [rectShape("plate", 0, 0, 120, 80), circleShape("plate-h1", 25, 55, 20), circleShape("plate-h2", 95, 25, 20)],
  },
  {
    id: "bracket", name: "L bracket", note: "100 × 90 mm, 30 mm legs, two Ø8 holes",
    shapes: [
      { kind: "poly", id: "bracket", pts: [[0, 0], [100, 0], [100, 30], [30, 30], [30, 90], [0, 90]] },
      circleShape("bracket-h1", 15, 75, 8), circleShape("bracket-h2", 85, 15, 8),
    ],
  },
  {
    id: "disc", name: "Disc", note: "Ø90 mm, three Ø10 holes",
    shapes: [
      circleShape("disc", 0, 0, 90),
      ...[90, 210, 330].map((a, i) => circleShape(`disc-h${i + 1}`, +(30 * Math.cos((a * Math.PI) / 180)).toFixed(3),
        +(30 * Math.sin((a * Math.PI) / 180)).toFixed(3), 10)),
    ],
  },
  {
    id: "forearm", name: "Forearm side", note: "160 × 45 mm, tapered, two Ø5 holes",
    shapes: [
      { kind: "poly", id: "forearm", pts: FOREARM },
      circleShape("forearm-h1", 18, 22.5, 5), circleShape("forearm-h2", 146, 22.5, 5),
    ],
  },
  { id: "blank", name: "Blank sketch", note: "no face: draw a rectangle (R); Flip applies", shapes: [] },
];

export function example(id: string): Example | undefined {
  return EXAMPLES.find((e) => e.id === id);
}
