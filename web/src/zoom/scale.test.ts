// Actual size's arithmetic: the px/mm a calibration gives, the per-screen
// key, the estimate's rules, what storage keeps (and survives without).
import { describe, expect, it } from "vitest";
import {
  CARD_MM, CSS_PX_PER_MM, STORAGE_KEY, estimate, fromCard, fromRuler, isActual, loadCalibrations, perInchOf, scaleFor, screenKey, storeCalibration,
  zoomPercent, type ScreenInfo,
} from "./scale";

const LINUX = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36";
const WIN = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36";
const MAC = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36";
const IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1";
const ANDROID = "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36";
const scr = (w: number, h: number, dpr: number, ua = LINUX, touch = 0): ScreenInfo => ({ w, h, dpr, ua, touch });

/** A Storage on a Map (what localStorage does), and one that refuses every call. */
function memory(): Storage {
  const m = new Map<string, string>();
  return {
    get length() { return m.size; }, clear: () => m.clear(), key: (i) => [...m.keys()][i] ?? null,
    getItem: (k) => m.get(k) ?? null, setItem: (k, v) => { m.set(k, String(v)); }, removeItem: (k) => { m.delete(k); },
  };
}
const blocked = new Proxy({}, { get: () => () => { throw new Error("SecurityError: storage is blocked"); } }) as Storage;

describe("the px/mm arithmetic", () => {
  it("a card drawn W px wide that matches the real one is W / 85.60 px per mm; a ruler line L px that measures m mm is L / m", () => {
    expect(CARD_MM).toEqual({ w: 85.6, h: 53.98, r: 3.18 });
    expect(fromCard(428)).toBeCloseTo(5, 12);
    expect(fromCard(53.98 * 4, CARD_MM.h)).toBeCloseTo(4, 12);
    expect(fromRuler(400, 80)).toBe(5);
    expect(perInchOf(5)).toBeCloseTo(127, 12);
  });

  it("100 % is CSS's millimetre: 96 px per inch", () => {
    expect(CSS_PX_PER_MM).toBeCloseTo(3.779527559, 9);
    expect(zoomPercent(CSS_PX_PER_MM)).toBe(100);
    expect(zoomPercent(CSS_PX_PER_MM * 2.5)).toBe(250);
    expect(zoomPercent(4)).toBe(106);
  });

  it("the camera is at a scale only when set to it (to a millionth), not near it", () => {
    expect(isActual(5, 5)).toBe(true);
    expect(isActual(5 * (1 + 1e-9), 5)).toBe(true);
    expect(isActual(5.001, 5)).toBe(false);
    expect(isActual(4.999, 5)).toBe(false);
  });
});

describe("the key a calibration is kept under", () => {
  it("is screen.width x height @ devicePixelRatio (three decimals)", () => {
    expect(screenKey(scr(3840, 2160, 1))).toBe("3840x2160@1");
    expect(screenKey(scr(1536, 864, 1.25))).toBe("1536x864@1.25");
    expect(screenKey(scr(1280, 800, 4 / 3))).toBe("1280x800@1.333");
    expect(screenKey(scr(1080, 1920, 1))).toBe("1080x1920@1");
  });

  it("another monitor, an OS scale or a page zoom is another key: never shown at a scale measured elsewhere", () => {
    const cals = { "3840x2160@1": { pxPerMm: 5.51, by: "card" as const, at: "2026-10-21" } };
    expect(scaleFor(scr(3840, 2160, 1), cals)).toMatchObject({ key: "3840x2160@1", pxPerMm: 5.51, calibrated: true });
    // the portrait monitor beside it, the same monitor at 125 % page zoom: their estimates, said to be estimates
    for (const s of [scr(1080, 1920, 1), scr(3840, 2160, 1.25)]) {
      const got = scaleFor(s, cals);
      expect(got.calibrated, got.key).toBe(false);
      expect(got.pxPerMm, got.key).toBe(estimate(s).pxPerMm);
    }
  });
});

describe("the estimate (a guess until calibrated)", () => {
  const ppi = (s: ScreenInfo) => +perInchOf(estimate(s).pxPerMm).toFixed(6);

  it("CSS's 96 px per inch, unless the screen says more", () => {
    expect(ppi(scr(1920, 1080, 1))).toBe(96);
    expect(ppi(scr(1080, 1920, 1))).toBe(96);
    expect(ppi(scr(1536, 864, 1.25, WIN))).toBe(96);
    expect(ppi(scr(2560, 1440, 1.5, WIN))).toBe(96);
    expect(estimate(scr(1920, 1080, 1)).basis).toBe("CSS's 96 px per inch");
  });

  it("a screen at exactly x1 shows every panel pixel: 4K ~150, 5K 218, 1440p 109 px per inch (portrait too)", () => {
    expect(ppi(scr(3840, 2160, 1))).toBe(150);
    expect(ppi(scr(2160, 3840, 1))).toBe(150);
    expect(ppi(scr(5120, 2880, 1))).toBe(218);
    expect(ppi(scr(2560, 1440, 1))).toBe(109);
    expect(ppi(scr(3440, 1440, 1))).toBe(109);
    expect(estimate(scr(3840, 2160, 1)).basis).toMatch(/4K/);
  });

  it("Apple's Retina sizes, phones and tablets by their platform's density", () => {
    expect(ppi(scr(1512, 982, 2, MAC))).toBe(127);
    expect(ppi(scr(2560, 1440, 2, MAC))).toBe(109);
    expect(ppi(scr(2560, 1440, 1, MAC))).toBe(109);
    expect(ppi(scr(393, 852, 3, IPHONE))).toBe(163);
    expect(ppi(scr(1024, 1366, 2, MAC, 5))).toBe(132);
    expect(ppi(scr(412, 915, 2.625, ANDROID))).toBe(160);
  });
});

describe("what this browser keeps", () => {
  it("a calibration round-trips per screen; forgetting one keeps the others", () => {
    const m = memory();
    expect(loadCalibrations(m)).toEqual({});
    expect(storeCalibration("3840x2160@1", { pxPerMm: 5.51, by: "card", at: "t1" }, m)).toBe(true);
    expect(storeCalibration("1080x1920@1", { pxPerMm: 3.64, by: "ruler", at: "t2" }, m)).toBe(true);
    expect(loadCalibrations(m)).toEqual({ "3840x2160@1": { pxPerMm: 5.51, by: "card", at: "t1" }, "1080x1920@1": { pxPerMm: 3.64, by: "ruler", at: "t2" } });
    expect(JSON.parse(m.getItem(STORAGE_KEY)!)).toMatchObject({ v: 1 });
    storeCalibration("3840x2160@1", null, m);
    expect(Object.keys(loadCalibrations(m))).toEqual(["1080x1920@1"]);
  });

  it("junk is ignored, never shown as a scale: bad JSON, a non-number, a scale no screen has", () => {
    const m = memory();
    m.setItem(STORAGE_KEY, "{not json");
    expect(loadCalibrations(m)).toEqual({});
    m.setItem(STORAGE_KEY, JSON.stringify({ v: 1, screens: { a: { pxPerMm: "5" }, b: { pxPerMm: 0.2 }, c: { pxPerMm: 500 }, d: { pxPerMm: 4.2, by: "card", at: "t" } } }));
    expect(loadCalibrations(m)).toEqual({ d: { pxPerMm: 4.2, by: "card", at: "t" } });
  });

  it("works without storage (blocked, private): nothing kept, nothing thrown, the estimate stands", () => {
    expect(loadCalibrations(blocked)).toEqual({});
    expect(loadCalibrations(null)).toEqual({});
    expect(storeCalibration("k", { pxPerMm: 5, by: "card", at: "t" }, blocked)).toBe(false);
    expect(storeCalibration("k", { pxPerMm: 5, by: "card", at: "t" }, null)).toBe(false);
    expect(scaleFor(scr(1920, 1080, 1), loadCalibrations(blocked))).toMatchObject({ calibrated: false, pxPerMm: CSS_PX_PER_MM });
  });
});
