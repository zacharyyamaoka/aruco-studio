import { describe, expect, it } from "vitest";
import { placeBeside } from "./anchor";

const host = { w: 1280, h: 760 };
const panel = { w: 300, h: 500 };

describe("a panel beside the box it edits", () => {
  it("to the right, top-aligned, clear of the box", () => {
    const p = placeBeside({ x0: 500, y0: 200, x1: 700, y1: 400 }, panel, host);
    expect(p).toMatchObject({ side: "right", x: 756, y: 200 });
    expect(p.x).toBeGreaterThan(700);
  });

  it("to the left when the right has no room", () => {
    const p = placeBeside({ x0: 900, y0: 200, x1: 1100, y1: 400 }, panel, host);
    expect(p.side).toBe("left");
    expect(p.x + panel.w).toBeLessThanOrEqual(900);
  });

  it("the side that keeps a neighbour clear, even a little over its own box", () => {
    // the right side would cover the neighbour; the left has 24 px too little room
    const p = placeBeside({ x0: 286, y0: 200, x1: 522, y1: 436 }, panel, host, {}, [{ x0: 758, y0: 200, x1: 994, y1: 436 }]);
    expect(p.x).toBe(10);
    expect(p.x + panel.w).toBeLessThan(758);
    expect(p.side).toBe("over");
    // with no neighbour it stays to the right
    expect(placeBeside({ x0: 286, y0: 200, x1: 522, y1: 436 }, panel, host).side).toBe("right");
  });

  it("over the box, on screen, when neither side has room", () => {
    const p = placeBeside({ x0: 100, y0: 100, x1: 1180, y1: 600 }, panel, host);
    expect(p.side).toBe("over");
    expect(p.x).toBeGreaterThanOrEqual(10);
    expect(p.x + panel.w).toBeLessThanOrEqual(1270);
  });

  it("stays above the toolbar strip and below the ruler", () => {
    const low = placeBeside({ x0: 500, y0: 650, x1: 600, y1: 700 }, panel, host);
    expect(low.y + panel.h).toBeLessThanOrEqual(760 - 60);
    const high = placeBeside({ x0: 500, y0: -300, x1: 600, y1: 10 }, panel, host);
    expect(high.y).toBe(26);
    expect(high.y + high.maxH).toBe(700);
  });

  it("a panel taller than the room: at the top, its height capped", () => {
    const p = placeBeside({ x0: 500, y0: 300, x1: 600, y1: 400 }, { w: 300, h: 900 }, host);
    expect(p.y).toBe(26);
    expect(p.maxH).toBe(760 - 60 - 26);
  });
});
