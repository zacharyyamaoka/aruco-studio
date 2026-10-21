// The click-or-drag threshold: the right button's menu opens only on a press
// that did not move past it; past it, the press is the selection box.
import { describe, expect, it } from "vitest";
import { DRAG_PX, isDrag } from "./click";

describe("a drag or a click", () => {
  it("is a drag only past DRAG_PX (4 view px), measured as a distance, either way", () => {
    expect(DRAG_PX).toBe(4);
    expect(isDrag([100, 100], [100, 100])).toBe(false);
    expect(isDrag([100, 100], [104, 100])).toBe(false);
    expect(isDrag([100, 100], [104.01, 100])).toBe(true);
    expect(isDrag([100, 100], [96, 100])).toBe(false);
    expect(isDrag([100, 100], [100, 95.9])).toBe(true);
    // 3 and 3 is 4.24 apart: a drag, though neither axis passed 4
    expect(isDrag([0, 0], [3, 3])).toBe(true);
    expect(isDrag([0, 0], [2.8, 2.8])).toBe(false);
  });
});
