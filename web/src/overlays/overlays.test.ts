// The Layers menu's choices, as this browser keeps them: every field checked
// on the way in, the defaults for junk, and a blocked storage never throws.
import { describe, expect, it } from "vitest";
import { OVERLAYS_DEFAULT, OVERLAYS_KEY, parseOverlays, readOverlays, writeOverlays, type Overlays } from "./overlays";

/** A storage that remembers, or one that throws on every call (a blocked one). */
function memory(): Storage {
  const m = new Map<string, string>();
  return {
    get length() { return m.size; },
    clear: () => m.clear(),
    getItem: (k) => m.get(k) ?? null,
    key: (i) => [...m.keys()][i] ?? null,
    removeItem: (k) => { m.delete(k); },
    setItem: (k, v) => { m.set(k, String(v)); },
  };
}
const blocked = { getItem: () => { throw new Error("SecurityError"); }, setItem: () => { throw new Error("QuotaExceededError"); } };

describe("the Layers menu's choices", () => {
  it("default to everything shown on the Grid (Zach: see the axes at a glance)", () => {
    expect(OVERLAYS_DEFAULT).toEqual({ background: "grid", dims: true, origins: true, edges: true, guides: true, rulers: true });
    expect(parseOverlays(null)).toEqual(OVERLAYS_DEFAULT);
    expect(parseOverlays("")).toEqual(OVERLAYS_DEFAULT);
  });

  it("read back what was written", () => {
    const store = memory();
    const o: Overlays = { background: "dots", dims: false, origins: true, edges: false, guides: true, rulers: false };
    expect(writeOverlays(o, store)).toBe(true);
    expect(JSON.parse(store.getItem(OVERLAYS_KEY)!)).toMatchObject({ v: 1, ...o });
    expect(readOverlays(store)).toEqual(o);
    expect(readOverlays(memory()), "nothing kept yet").toEqual(OVERLAYS_DEFAULT);
  });

  it("take each field on its own: junk, a missing field or an unknown value is that field's default", () => {
    expect(parseOverlays("not json")).toEqual(OVERLAYS_DEFAULT);
    expect(parseOverlays("[1,2]")).toEqual(OVERLAYS_DEFAULT);
    expect(parseOverlays(JSON.stringify({ background: "lines", dims: "no", origins: false, extra: 1 })))
      .toEqual({ ...OVERLAYS_DEFAULT, origins: false });
    expect(parseOverlays(JSON.stringify({ background: "blank" }))).toEqual({ ...OVERLAYS_DEFAULT, background: "blank" });
  });

  it("never throw on a blocked storage: the defaults in, false out (kept for the visit only)", () => {
    expect(readOverlays(blocked)).toEqual(OVERLAYS_DEFAULT);
    expect(writeOverlays(OVERLAYS_DEFAULT, blocked)).toBe(false);
    expect(readOverlays(null)).toEqual(OVERLAYS_DEFAULT);
    expect(writeOverlays(OVERLAYS_DEFAULT, null)).toBe(false);
  });
});
