// WHY: an estimate first, calibrated per screen key and never scaled across DPR -- docs/peps/0002-actual-size-per-screen.md
// Actual size: 1 mm on the model is 1 mm on the glass (Zach, 2026-10-21: "I
// want the option to scale to actual size, vs fit. When actual size it should
// determine my screen resolution etc and correctly display it so I can see
// the things to scale"). The camera's zoom is CSS px per mm (model/geom.ts),
// so actual size is a zoom of this screen's CSS px per physical mm.
//
// WHY a guess, then a calibration: no browser says how big its screen is.
// devicePixelRatio, screen.width / height and the user agent give a best
// guess (estimate()); holding a bank card against the screen (or measuring a
// line with a ruler) makes it exact. The calibration is kept per screen in
// this browser, keyed by screen.width x height @ devicePixelRatio, so another
// monitor, a changed OS scale or a page zoom (each changes the key) is never
// shown at a scale measured on another one: it falls back to its estimate,
// and says so (ZoomIndicator: "Actual size (estimated — calibrate)").
import { create } from "zustand";

/** CSS's reference pixel is 1/96 in, so CSS's own millimetre (what "100 %" is) is 96 / 25.4 px. */
export const CSS_PX_PER_MM = 96 / 25.4;
/** ISO/IEC 7810 ID-1, every bank card: 85.60 x 53.98 mm, corners r 3.18 mm. */
export const CARD_MM = { w: 85.6, h: 53.98, r: 3.18 } as const;
/** A scale outside this (px/mm) is not a screen: refused when typed, ignored when read back. */
export const MIN_PX_PER_MM = 1.5;
export const MAX_PX_PER_MM = 20;
/** Where the calibrations are kept (this browser only). */
export const STORAGE_KEY = "arucoStudio.actualSize";

/** What the page can see of the screen it is on. */
export interface ScreenInfo { w: number; h: number; dpr: number; ua: string; touch: number }
export interface Calibration { pxPerMm: number; by: "card" | "ruler"; at: string }
export type Calibrations = Record<string, Calibration>;
/** This screen's scale: calibrated (exact for this key) or estimated (a guess, `basis` says from what). */
export interface Scale { key: string; pxPerMm: number; calibrated: boolean; basis: string; screen: ScreenInfo; cal: Calibration | null }

export function readScreen(): ScreenInfo {
  if (typeof window === "undefined") return { w: 0, h: 0, dpr: 1, ua: "", touch: 0 };
  return { w: window.screen?.width ?? 0, h: window.screen?.height ?? 0, dpr: window.devicePixelRatio || 1, ua: navigator.userAgent ?? "", touch: navigator.maxTouchPoints ?? 0 };
}

/** The key a calibration is kept under: screen.width x height @ devicePixelRatio ("3840x2160@1", "1536x864@1.25"). */
export function screenKey(s: Pick<ScreenInfo, "w" | "h" | "dpr">): string {
  return `${Math.round(s.w)}x${Math.round(s.h)}@${+s.dpr.toFixed(3)}`;
}

const perInch = (ppi: number, basis: string) => ({ pxPerMm: ppi / 25.4, basis });

/** The best guess of this screen's CSS px per physical mm, and what it rests on.
 *  WHY these numbers (CSS px per inch = the panel's pixels per inch / its scale):
 *  - phones and tablets: their platform's own density: an iPhone 163 (326 ppi
 *    at x2, 460 at x3 is 153), an iPad 132 (264 at x2), Android 160 (its dp);
 *  - a Mac at x2 (Retina, Apple's default "looks like" sizes): its laptops
 *    127 (3024 px over 302.4 mm shown as 1512, the 14 in; the 13 and 16 in
 *    agree), its desktop screens 109 (5120 over 596.7 mm shown as 2560);
 *  - a screen at exactly x1 shows every panel pixel, so a dense panel is
 *    dense in CSS px too: 4K ~150 (27 in 163, 32 in 140), 5K 218, 1440p 109 (27 in);
 *  - otherwise CSS's own 96 per inch (Windows' 100 %, a 24 in 1080p is 92).
 *  A guess on every count: the indicator says so until it is calibrated. */
export function estimate(s: ScreenInfo): { pxPerMm: number; basis: string } {
  const long = Math.max(s.w, s.h);
  const mac = /Macintosh|Mac OS X/.test(s.ua);
  if (/iPhone|iPod/.test(s.ua)) return perInch(163, "an iPhone's 163 px per inch");
  if (/iPad/.test(s.ua) || (mac && s.touch > 1)) return perInch(132, "an iPad's 132 px per inch");
  if (/Android/.test(s.ua)) return perInch(160, "Android's 160 px per inch");
  if (mac && s.dpr >= 2) return long <= 1800 ? perInch(127, "a MacBook Retina screen's 127 px per inch") : perInch(109, "an Apple Retina display's 109 px per inch");
  if (Math.abs(s.dpr - 1) < 0.01) {
    if (long >= 5000) return perInch(218, "a 5K screen at 100 %: about 218 px per inch");
    if (long >= 3800) return perInch(150, "a 4K screen at 100 %: about 150 px per inch");
    if (long >= 2500) return perInch(109, "a 1440p screen at 100 %: about 109 px per inch");
  }
  return perInch(96, "CSS's 96 px per inch");
}

const valid = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v) && v >= MIN_PX_PER_MM && v <= MAX_PX_PER_MM;

/** The scale of a screen: its calibration when there is one for its key, else its estimate. */
export function scaleFor(s: ScreenInfo, cals: Calibrations): Scale {
  const key = screenKey(s);
  const cal = cals[key];
  if (cal && valid(cal.pxPerMm)) return { key, pxPerMm: cal.pxPerMm, calibrated: true, basis: `calibrated with a ${cal.by === "card" ? "bank card" : "ruler"}`, screen: s, cal };
  const e = estimate(s);
  return { key, pxPerMm: e.pxPerMm, calibrated: false, basis: e.basis, screen: s, cal: null };
}

function storage(): Storage | null {
  try { return window.localStorage; } catch { return null; }
}

/** The calibrations kept in this browser ({} when storage is blocked or holds junk). */
export function loadCalibrations(store: Storage | null = storage()): Calibrations {
  try {
    const raw = store?.getItem(STORAGE_KEY);
    const screens = raw ? (JSON.parse(raw) as { screens?: Record<string, Partial<Calibration>> }).screens : null;
    const out: Calibrations = {};
    for (const [k, c] of Object.entries(screens ?? {})) {
      if (c && valid(c.pxPerMm)) out[k] = { pxPerMm: c.pxPerMm, by: c.by === "ruler" ? "ruler" : "card", at: typeof c.at === "string" ? c.at : "" };
    }
    return out;
  } catch {
    return {};
  }
}

/** Keep (or with null, forget) a screen's calibration; false when this browser will not store it
 *  (the app works on: the scale is then this visit's only). */
export function storeCalibration(key: string, cal: Calibration | null, store: Storage | null = storage()): boolean {
  try {
    if (!store) return false;
    const screens = { ...loadCalibrations(store) };
    if (cal) screens[key] = cal;
    else delete screens[key];
    store.setItem(STORAGE_KEY, JSON.stringify({ v: 1, screens }));
    return true;
  } catch {
    return false;
  }
}

/** The calibrations: a card drawn `widthPx` wide that matches a real one, a line `linePx` long that a ruler says is `mm`. */
export const fromCard = (widthPx: number, side: number = CARD_MM.w): number => widthPx / side;
export const fromRuler = (linePx: number, mm: number): number => linePx / mm;
export const perInchOf = (pxPerMm: number): number => pxPerMm * 25.4;
export const clampScale = (v: number): number => Math.min(MAX_PX_PER_MM, Math.max(MIN_PX_PER_MM, v));

/** The zoom indicator's percent: 100 % is CSS's millimetre (the browser's, 96 px per inch). */
export const zoomPercent = (zoom: number): number => Math.round((zoom / CSS_PX_PER_MM) * 100);
/** The camera is at this scale (a set zoom, not a coincidence of the wheel). */
export const isActual = (zoom: number, pxPerMm: number): boolean => Math.abs(zoom / pxPerMm - 1) < 1e-6;

// ---------------------------------------------------------------- the live scale

interface ScaleStore {
  scale: Scale;
  /** the calibration dialog is open */
  calibrating: boolean;
  /** the screen or the stored calibrations may have changed: read them again */
  refresh: () => void;
  setCalibrating: (on: boolean) => void;
  /** this screen's calibration (false: not stored, this visit only) */
  calibrate: (pxPerMm: number, by: Calibration["by"]) => boolean;
  /** forget this screen's calibration: back to the estimate */
  forget: () => void;
}

/** Calibrations this visit could not store (storage blocked): still used until a reload. */
const session: Calibrations = {};
const current = (): Scale => scaleFor(readScreen(), { ...loadCalibrations(), ...session });

export const useScale = create<ScaleStore>((set, get) => ({
  scale: current(),
  calibrating: false,
  refresh: () => {
    const next = current(), now = get().scale;
    if (next.key !== now.key || next.pxPerMm !== now.pxPerMm || next.calibrated !== now.calibrated || next.basis !== now.basis) set({ scale: next });
  },
  setCalibrating: (calibrating) => set({ calibrating }),
  calibrate: (pxPerMm, by) => {
    const key = get().scale.key;
    const cal: Calibration = { pxPerMm: clampScale(pxPerMm), by, at: new Date().toISOString() };
    const kept = storeCalibration(key, cal);
    if (kept) delete session[key];
    else session[key] = cal;
    get().refresh();
    return kept;
  },
  forget: () => {
    const key = get().scale.key;
    delete session[key];
    storeCalibration(key, null);
    get().refresh();
  },
}));

/** Follow the screen: a move to another monitor (its own DPR, or the same
 *  DPR at another size), an OS scale or page zoom change, another tab's
 *  calibration. Returns the unsubscribe. */
export function watchScreen(): () => void {
  const refresh = () => useScale.getState().refresh();
  let mq: MediaQueryList | null = null;
  const onDpr = () => { refresh(); listen(); };
  // WHY re-armed each time: the query names the DPR it was made for
  const listen = () => {
    mq?.removeEventListener("change", onDpr);
    mq = window.matchMedia?.(`(resolution: ${window.devicePixelRatio || 1}dppx)`) ?? null;
    mq?.addEventListener("change", onDpr);
  };
  listen();
  const onStorage = (e: StorageEvent) => { if (e.key === STORAGE_KEY || e.key === null) refresh(); };
  const scr = window.screen as Screen & Partial<EventTarget>;
  window.addEventListener("resize", refresh);
  window.addEventListener("focus", refresh);
  window.addEventListener("storage", onStorage);
  scr.addEventListener?.("change", refresh);
  // WHY a 1 s look as well: on X11 every monitor shares one DPR, and a window
  // dragged onto a monitor of another size changes screen.width with no event
  const poll = window.setInterval(() => { if (!document.hidden) refresh(); }, 1000);
  refresh();
  return () => {
    mq?.removeEventListener("change", onDpr);
    window.removeEventListener("resize", refresh);
    window.removeEventListener("focus", refresh);
    window.removeEventListener("storage", onStorage);
    scr.removeEventListener?.("change", refresh);
    window.clearInterval(poll);
  };
}
