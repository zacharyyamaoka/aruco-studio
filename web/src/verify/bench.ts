// The Verify dialog's numbers (./VerifyDialog.tsx): the bench camera the
// sliders and the angle sweep look through, the sweep's tilts and its
// "reads to N°", and the calculator's camera, remembered per viewer. Pure
// but for the wrapped localStorage; vitest covers it (bench.test.ts).
import type { Camera, MarkerPlan, ViewConditions } from "../core/contract";

/** The knobs a slider sets (ViewConditions without the camera and the seed). */
export interface Knobs { tilt_deg: number; yaw_deg: number; blur_px: number; noise: number; glare: number; occlusion: number }

export const KNOBS0: Knobs = { tilt_deg: 0, yaw_deg: 0, blur_px: 0, noise: 0, glare: 0, occlusion: 0 };

// WHY a bench at a fixed px per cell, not the calculator's camera (the V1
// design, ui-proposals-2026-10-18 "Simulated camera"): the sliders show what
// tilt, blur and dirt do to the marker itself, the same for every marker,
// while the calculator answers "will my camera read it at this distance".
export const BENCH_RES: [number, number] = [1280, 960];
export const BENCH_HFOV = 60;
export const BENCH_PX_PER_CELL = 16;
/** the outline never spans more than this share of the sensor's short side */
export const BENCH_FILL = 0.8;

export function focalPx(width: number, hfovDeg: number): number {
  return width / 2 / Math.tan((hfovDeg * Math.PI) / 360);
}

/** The bench camera for a plan: BENCH_PX_PER_CELL on its cells head on, set
 *  back further when that would not fit the whole outline on the sensor. */
export function benchCamera(plan: Pick<MarkerPlan, "cell_mm" | "outer_mm">): Camera {
  const f = focalPx(BENCH_RES[0], BENCH_HFOV);
  const byCell = (plan.cell_mm * f) / BENCH_PX_PER_CELL;
  const byFit = (Math.max(plan.outer_mm[0], plan.outer_mm[1]) * f) / (BENCH_FILL * Math.min(...BENCH_RES));
  return { distance_mm: Math.max(byCell, byFit), resolution: BENCH_RES, hfov_deg: BENCH_HFOV };
}

export function viewOf(camera: Camera, k: Knobs): ViewConditions {
  return { camera, ...k, seed: 0 };
}

/** The automatic sweep: tilt 0 → 85° in 5° steps. */
export const SWEEP_TILTS: number[] = Array.from({ length: 18 }, (_, i) => i * 5);

/** The share of a marker's ids found (missing counts against it; a wrong id
 *  is never one of its own, so it does not). */
export function share(found: number, missing: number): number {
  const n = found + missing;
  return n ? found / n : 0;
}

/** The last tilt read in full, counting up from 0° without a gap; null when
 *  even head on misses an id; undefined while that is not known yet (the
 *  sweep has not reached the first miss or the end). */
export function readsTo(tilts: number[], shares: (number | null)[]): number | null | undefined {
  let last: number | null = null;
  for (let i = 0; i < tilts.length; i++) {
    const s = shares[i];
    if (s === null || s === undefined) return undefined;
    if (s < 1) return last;
    last = tilts[i];
  }
  return last;
}

// ------------------------------------------------------------ the calculator's camera

export interface CalcCamera { distance_mm: number; width_px: number; hfov_deg: number }

export const CALC0: CalcCamera = { distance_mm: 1500, width_px: 1920, hfov_deg: 70 };

/** The calculator's camera: the sensor's height at 16:9 (only clipping
 *  depends on it; OpenCV's perimeter limit takes the longer side). */
export function calcCamera(c: CalcCamera): Camera {
  return { distance_mm: c.distance_mm, resolution: [c.width_px, Math.round((c.width_px * 9) / 16)], hfov_deg: c.hfov_deg };
}

const CALC_KEY = "aruco-web.verify.camera";

export function loadCalc(): CalcCamera {
  try {
    const v = JSON.parse(window.localStorage.getItem(CALC_KEY) ?? "null") as Partial<CalcCamera> | null;
    const ok = (x: unknown): x is number => typeof x === "number" && Number.isFinite(x) && x > 0;
    if (v && ok(v.distance_mm) && ok(v.width_px) && ok(v.hfov_deg)) return { distance_mm: v.distance_mm, width_px: v.width_px, hfov_deg: v.hfov_deg };
  } catch { /* storage blocked or garbled: the defaults */ }
  return CALC0;
}

export function saveCalc(c: CalcCamera): void {
  try { window.localStorage.setItem(CALC_KEY, JSON.stringify(c)); } catch { /* storage blocked: kept for this visit only */ }
}
