// The Studio's dev flags, read once from the page's URL.
//
// DRAW (`?draw=1`): the shape-drawing tools (Rectangle, Circle, Polygon,
// Slot, Hole, Rectangular hole), their keys (R C P O H Shift+H), their
// buttons and their palette rows. Off by default since Zach's note of
// 2026-10-17 (CF-12, N-3): the Studio stops being a sketcher; its inputs
// are drawn for the user in the gallery's examples, and sketches will come
// from other programs. The code stays, frozen; `?draw=1` brings it back
// (the older e2e tests run that way), and it also starts on the canvas
// instead of the gallery.
const params = typeof window !== "undefined" ? new URLSearchParams(window.location.search) : new URLSearchParams();

export const DRAW = params.get("draw") === "1";

/** The tools that draw geometry: hidden unless DRAW. */
export const DRAW_TOOLS = ["rect", "circle", "polygon", "slot", "hole", "rhole"] as const;

export function drawTool(tool: string): boolean {
  return (DRAW_TOOLS as readonly string[]).includes(tool);
}

/** Is this tool offered now? */
export function toolOn(tool: string): boolean {
  return DRAW || !drawTool(tool);
}
