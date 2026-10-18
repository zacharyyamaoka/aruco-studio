// Plans re-run live: every change to what plan() reads schedules one call
// (~30 ms after the last change, so a drag does not queue a call per
// pixel). The last plan stays drawn while the next one computes, and an
// answer for a request that is no longer current is dropped. Suggestions
// follow the same way while the panel is open.
import type { PlanRequest } from "./core/contract";
import { core, onCoreStatus, coreStatus } from "./coreSource";
import { planRequest } from "./model/doc";
import { useStudio } from "./store";

const PLAN_MS = 30;
const SUGGEST_MS = 120;

let planKey = "";
let planTimer: ReturnType<typeof setTimeout> | null = null;
let suggestKey = "";
let suggestTimer: ReturnType<typeof setTimeout> | null = null;
let running = 0;

/** True while a plan or suggestion is scheduled or running (the probe's idle). */
export function plannerBusy(): boolean {
  return !!planTimer || !!suggestTimer || running > 0;
}

function suggestInput(req: PlanRequest | null): string {
  if (!req) return "";
  // what the list depends on: not the size the list itself sets
  const { marker_mm: _m, checker_mm: _c, auto: _a, cols: _x, rows: _y, ...marker } = req.marker;
  return JSON.stringify({ rect: req.rect, marker, preset: req.preset, ref: req.reference_face });
}

async function runPlan(req: PlanRequest, key: string) {
  running += 1;
  try {
    const plan = await core.plan(req);
    if (key === planKey) useStudio.setState({ plan, planError: null });
  } catch (e) {
    if (key === planKey) useStudio.setState({ planError: (e as Error).message });
  } finally {
    running -= 1;
  }
}

async function runSuggest(req: PlanRequest, key: string) {
  running += 1;
  try {
    const suggestions = await core.suggest(req);
    if (key === suggestKey) useStudio.setState({ suggestions });
  } catch {
    if (key === suggestKey) useStudio.setState({ suggestions: [] });
  } finally {
    running -= 1;
  }
}

function schedule(force = false) {
  const s = useStudio.getState();
  const req = planRequest(s.doc);
  const key = req ? JSON.stringify(req) : "";
  if (key !== planKey || force) {
    planKey = key;
    if (planTimer) clearTimeout(planTimer);
    planTimer = null;
    if (!req) {
      if (s.plan) useStudio.setState({ plan: null });
    } else if (coreStatus().state === "ready") {
      planTimer = setTimeout(() => { planTimer = null; void runPlan(req, key); }, PLAN_MS);
    }
  }
  const sk = s.panel.open ? suggestInput(req) : "";
  if (sk !== suggestKey || force) {
    suggestKey = sk;
    if (suggestTimer) clearTimeout(suggestTimer);
    suggestTimer = null;
    if (!req || !sk) useStudio.setState({ suggestions: [] });
    else if (coreStatus().state === "ready") {
      suggestTimer = setTimeout(() => { suggestTimer = null; void runSuggest(req, sk); }, SUGGEST_MS);
    }
  }
}

export function startPlanner(): () => void {
  const un1 = useStudio.subscribe((s, prev) => {
    if (s.doc !== prev.doc || s.panel.open !== prev.panel.open) schedule();
  });
  let was = coreStatus().state;
  const un2 = onCoreStatus(() => {
    const now = coreStatus().state;
    if (now === "ready" && was !== "ready") schedule(true);
    was = now;
  });
  schedule(true);
  return () => { un1(); un2(); };
}
