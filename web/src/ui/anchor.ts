// Where a floating panel opens beside what it edits (V1 "Click-to-inspect",
// 2026-10-18): to the right of the box or to its left, top-aligned with it,
// always inside its container and clear of the toolbar strip at the bottom.
// Of the two sides it takes the one that covers the least marker -- the
// other markers' boxes, and its own box counted twice -- so a neighbour
// stays clickable (V1's known weak spot: "the panel covers the neighbours");
// a tie goes right. Pixels in the container's frame. Pure: vitest covers it.

export interface Box { x0: number; y0: number; x1: number; y1: number }

export interface Placement {
  x: number;
  y: number;
  /** the height the panel may take from y (its body scrolls past it) */
  maxH: number;
  /** "over": no side had room, so it covers part of its own box */
  side: "right" | "left" | "over";
}

export interface PlaceOptions {
  /** the gap on the right: room for the outer dimension drawn there */
  gapRight?: number;
  gapLeft?: number;
  /** kept clear at the top (the ruler) and the sides */
  top?: number;
  margin?: number;
  /** kept clear at the bottom (the toolbar) */
  bottom?: number;
}

const area = (a: Box, b: Box) =>
  Math.max(0, Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0)) * Math.max(0, Math.min(a.y1, b.y1) - Math.max(a.y0, b.y0));

export function placeBeside(box: Box, panel: { w: number; h: number }, host: { w: number; h: number }, o: PlaceOptions = {},
  others: Box[] = []): Placement {
  const gapR = o.gapRight ?? 56, gapL = o.gapLeft ?? 16, top = o.top ?? 26, m = o.margin ?? 10, bottom = o.bottom ?? 60;
  const floor = Math.max(top + 120, host.h - bottom);   // a short screen still shows a usable panel
  const y = Math.max(top, Math.min(box.y0, floor - panel.h));
  const maxH = Math.max(120, floor - y);
  const h = Math.min(panel.h, maxH);
  const onScreen = (x: number) => Math.max(m, Math.min(x, host.w - panel.w - m));
  const sides = [
    { side: "right" as const, x: onScreen(box.x1 + gapR) },
    { side: "left" as const, x: onScreen(box.x0 - gapL - panel.w) },
  ].map((c) => {
    const p = { x0: c.x, y0: y, x1: c.x + panel.w, y1: y + h };
    const own = area(p, box);
    return { ...c, own, cost: others.reduce((s, b) => s + area(p, b), 0) + 2 * own };
  });
  const best = sides[1].cost < sides[0].cost ? sides[1] : sides[0];
  return { x: best.x, y, maxH, side: best.own > 0 ? "over" : best.side };
}
