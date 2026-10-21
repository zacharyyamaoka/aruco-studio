// A press that travels more than DRAG_PX (view px) is a drag; less is a click.
// One threshold for every gesture the canvas tells apart: the selection box
// (left or right button), a clicked rectangle's first corner, D's placing, the
// turn arc -- and the right button's menu, which opens only on a right-click
// that did not move (a right-drag is the selection box, Viewport.tsx).
import type { Vec2 } from "../core/contract";

export const DRAG_PX = 4;

export const isDrag = (a: Vec2, b: Vec2, px: number = DRAG_PX): boolean => Math.hypot(b[0] - a[0], b[1] - a[1]) > px;
