// The examples File › Examples… opens: the golden faces (../sketch/examples.ts,
// shapes only) and the documents that come with their ArUco Extrudes made.
// WHY the sticker sheet (Zach, 2026-10-20): "we should be able to have lots of
// the markers on a page and then re-id them": a page of markers whose auto
// ids are scattered by the hash, for Edit › Re-ID all markers… to number.
import { rectShape, type Shape } from "../sketch/model";
import { EXAMPLES as FACES } from "../sketch/examples";
import { newFeature, setField, type Feature } from "./doc";

export interface Example { id: string; name: string; note: string; shapes: Shape[]; features?: Feature[] }

type Kind = "single" | "grid" | "charuco";

/** One marker on the sheet: its rectangle (centre, size, mm) and its type. */
function sticker(n: number, kind: Kind, cx: number, cy: number, w: number, h: number): [Shape, Feature] {
  const rect = rectShape(`sheet-r${n}`, cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2);
  const f = newFeature(rect.id, null, `sheet-f${n}`);
  return [rect, kind === "single" ? f : setField(f, "marker.type", kind)];
}

// 240 × 180 mm, in reading order (top row first, left to right): the
// document order Re-ID numbers in. 9 singles, two 2 × 2 grids, one ChArUco.
const STICKERS: [Shape, Feature][] = [
  sticker(1, "single", 25, 150, 30, 30),
  sticker(2, "single", 65, 150, 30, 30),
  sticker(3, "grid", 120, 145, 50, 50),
  sticker(4, "single", 175, 150, 30, 30),
  sticker(5, "single", 215, 150, 30, 30),
  sticker(6, "charuco", 52.5, 85, 75, 60),
  sticker(7, "single", 115, 90, 30, 30),
  sticker(8, "grid", 165, 90, 50, 50),
  sticker(9, "single", 215, 90, 30, 30),
  sticker(10, "single", 25, 30, 30, 30),
  sticker(11, "single", 65, 30, 30, 30),
  sticker(12, "single", 105, 30, 30, 30),
];

export const EXAMPLES: Example[] = [
  ...FACES,
  {
    id: "sticker-sheet", name: "Sticker sheet — many markers (Re-ID)",
    note: "12 markers on a 240 × 180 mm sheet, ids scattered by auto id: Edit › Re-ID numbers them",
    shapes: [rectShape("sheet", 0, 0, 240, 180), ...STICKERS.map(([s]) => s)],
    features: STICKERS.map(([, f]) => f),
  },
];

export function example(id: string): Example | undefined {
  return EXAMPLES.find((e) => e.id === id);
}
