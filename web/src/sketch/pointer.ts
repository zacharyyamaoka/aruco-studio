// Where the pointer is over the sketch (mm), or null when it is off the
// canvas: Ctrl+V pastes there. Not state: nothing redraws when it moves.
import type { Vec2 } from "../core/contract";

export const pointer: { at: Vec2 | null } = { at: null };
