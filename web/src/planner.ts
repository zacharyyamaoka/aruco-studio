// Plans re-run live, each feature on its own (keyed by the feature's id):
// every change to what plan() reads for a feature schedules one call for it
// (~30 ms after the last change, so a drag does not queue a call per pixel).
// A feature's last plan stays drawn while its next one computes, and an
// answer for a request that is no longer current is dropped. Suggestions
// follow the same way for the feature the panel edits.
// WHY one running and one latest per feature (review finding #10,
// 2026-10-21): the core is one worker, so every call sent runs; six edits
// to an expensive profile queued seven plans, the current one last. A call
// made while that feature's (or the suggestions') is running waits as the
// one latest, replaced by any newer, and goes when the running one returns.
//
// Auto id runs first: every feature's ids are assigned together
// (core.assign_ids, with the document's ledger) whenever what they depend on
// changes -- a feature added or removed, a type, count, dictionary, key or
// typed id -- and the plans wait for the answer, so a marker is never drawn
// with an id it is about to lose. The answer's driven ids and ledger go into
// the document (model/doc.ts applyIds), so the plans, the sheet and the saved
// file all carry them.
import type { IdRequest, PlanRequest } from "./core/contract";
import { core, onCoreStatus, coreStatus } from "./coreSource";
import { applyIds, getFeature, idRequest, planRequest, refusedKeys } from "./model/doc";
import { useStudio } from "./store";

const PLAN_MS = 30;
const SUGGEST_MS = 120;

const planKeys = new Map<string, string>();
const planTimers = new Map<string, ReturnType<typeof setTimeout>>();
let suggestKey = "";
let suggestTimer: ReturnType<typeof setTimeout> | null = null;
let running = 0;
/** per feature, the call running (a token: Retry sends past a call that never answers) */
const inflight = new Map<string, object>();
/** per feature, the latest plan waiting for its running one */
const waiting = new Map<string, { req: PlanRequest; key: string }>();
let suggesting: object | null = null;
let suggestNext: { req: PlanRequest; key: string } | null = null;
/** the id request whose answer is in the document, and the one last sent */
let idSettled = "";
let idSent = "";

/** True while a plan or suggestion is scheduled or running (the probe's idle). */
export function plannerBusy(): boolean {
  return planTimers.size > 0 || !!suggestTimer || running > 0 || !!idSent || waiting.size > 0 || !!suggestNext;
}

function suggestInput(id: string, req: PlanRequest | null): string {
  if (!req) return "";
  // what the list depends on: not the size the list itself sets
  const { marker_mm: _m, checker_mm: _c, auto: _a, cols: _x, rows: _y, ...marker } = req.marker;
  return JSON.stringify({ id, profile: req.profile, holes: req.holes, marker, preset: req.preset, ref: req.reference_face });
}

/** A feature's plan now, or (one running) as its one latest. */
function startPlan(id: string, req: PlanRequest, key: string) {
  if (inflight.has(id)) waiting.set(id, { req, key });
  else void runPlan(id, req, key);
}

async function runPlan(id: string, req: PlanRequest, key: string) {
  running += 1;
  const mine = {};
  inflight.set(id, mine);
  try {
    const plan = await core.plan(req);
    if (planKeys.get(id) === key) {
      const { planErrors } = useStudio.getState();
      const { [id]: _e, ...rest } = planErrors;
      useStudio.setState({ plans: { ...useStudio.getState().plans, [id]: plan }, planErrors: rest });
    }
  } catch (e) {
    if (planKeys.get(id) === key) useStudio.setState({ planErrors: { ...useStudio.getState().planErrors, [id]: (e as Error).message } });
  } finally {
    running -= 1;
    // (not when Retry sent another meanwhile: that one carries on)
    if (inflight.get(id) === mine) {
      inflight.delete(id);
      const next = waiting.get(id);
      waiting.delete(id);
      // still the feature's current request (a newer one replaced it, a removed feature dropped it)
      if (next && planKeys.get(id) === next.key) void runPlan(id, next.req, next.key);
    }
  }
}

function startSuggest(req: PlanRequest, key: string) {
  if (suggesting) suggestNext = { req, key };
  else void runSuggest(req, key);
}

async function runSuggest(req: PlanRequest, key: string) {
  running += 1;
  const mine = {};
  suggesting = mine;
  try {
    const suggestions = await core.suggest(req);
    if (key === suggestKey) useStudio.setState({ suggestions });
  } catch {
    if (key === suggestKey) useStudio.setState({ suggestions: [] });
  } finally {
    running -= 1;
    if (suggesting === mine) {
      suggesting = null;
      const next = suggestNext;
      suggestNext = null;
      if (next && next.key === suggestKey) void runSuggest(next.req, next.key);
    }
  }
}

async function runAssign(req: IdRequest, key: string) {
  running += 1;
  try {
    const res = await core.assign_ids(req);
    if (key !== JSON.stringify(idRequest(useStudio.getState().doc))) return;   // the document moved on: its own call follows
    const doc = applyIds(useStudio.getState().doc, res);
    // WHY settled on the new ledger without a second call: with the ledger the
    // core just returned, the same items keep the same ids (core/autoid.py)
    idSettled = JSON.stringify(idRequest(doc));
    useStudio.setState({ doc, idIssues: res.warnings, idRefused: refusedKeys(res), idSettledKey: idSettled });
  } catch (e) {
    // no auto id (the mock core, or a refused request): the typed / default ids plan as they are
    if (key === JSON.stringify(idRequest(useStudio.getState().doc))) {
      idSettled = key;
      useStudio.setState({ idIssues: [{ field: "marker.first_id", level: "warn", text: `Auto id failed: ${(e as Error).message}` }], idRefused: [], idSettledKey: key });
    }
  } finally {
    running -= 1;
    if (idSent === key) idSent = "";
    schedule();
  }
}

/** True when the document's ids are the ones auto id gave out; else asks for them. */
function idsSettled(ready: boolean): boolean {
  const s = useStudio.getState();
  const req = idRequest(s.doc);
  const key = JSON.stringify(req);
  if (key === idSettled) return true;
  if (!req.items.length) {
    // nothing to number: the core would answer an empty ledger
    if (Object.keys(s.doc.id_ledger).length || s.idIssues.length || s.idRefused.length) {
      useStudio.setState({ doc: { ...s.doc, id_ledger: {} }, idIssues: [], idRefused: [] });
      return false;
    }
    idSettled = key;
    if (s.idSettledKey !== key) useStudio.setState({ idSettledKey: key });
    return true;
  }
  if (ready && key !== idSent) {
    idSent = key;
    void runAssign(req, key);
  }
  return false;
}

function clearTimer(id: string) {
  const t = planTimers.get(id);
  if (t) clearTimeout(t);
  planTimers.delete(id);
}

function schedule(force = false) {
  const s = useStudio.getState();
  const ready = coreStatus().state === "ready";
  const live = new Set(s.doc.features.map((f) => f.id));
  // a removed feature: its call is dropped and its plan is no longer drawn
  for (const id of [...planKeys.keys()]) if (!live.has(id)) { clearTimer(id); planKeys.delete(id); waiting.delete(id); }
  const plans = { ...s.plans };
  let dropped = false;
  for (const id of Object.keys(plans)) if (!live.has(id)) { delete plans[id]; dropped = true; }

  const idsReady = idsSettled(ready);
  for (const f of idsReady ? s.doc.features : []) {
    const req = planRequest(s.doc, f);
    const key = req ? JSON.stringify(req) : "";
    // unchanged, and drawn (or on its way, or failed): nothing to do. A plan
    // dropped from the store (a document loaded anew) is asked for again.
    const settled = !req || !!s.plans[f.id] || planTimers.has(f.id) || inflight.has(f.id) || !!s.planErrors[f.id];
    if (key === planKeys.get(f.id) && !force && settled) continue;
    planKeys.set(f.id, key);
    clearTimer(f.id);
    if (!req) {
      if (plans[f.id]) { delete plans[f.id]; dropped = true; }
    } else if (ready) {
      planTimers.set(f.id, setTimeout(() => { planTimers.delete(f.id); startPlan(f.id, req, key); }, PLAN_MS));
    }
  }
  if (dropped) useStudio.setState({ plans });

  const ef = s.panel.open ? getFeature(s.doc, s.panel.featureId) : null;
  const ereq = ef ? planRequest(s.doc, ef) : null;
  const sk = ef ? suggestInput(ef.id, ereq) : "";
  if (sk !== suggestKey || force) {
    suggestKey = sk;
    if (suggestTimer) clearTimeout(suggestTimer);
    suggestTimer = null;
    if (!ereq || !sk) { suggestNext = null; useStudio.setState({ suggestions: [] }); }
    else if (ready) {
      suggestTimer = setTimeout(() => { suggestTimer = null; startSuggest(ereq, sk); }, SUGGEST_MS);
    }
  }
}

/** Ask again for auto id and every feature's plan, failed or still out: the
 *  panel's Retry (a plan that failed is otherwise asked again only when its
 *  request changes; one that never answers, never). */
export function replan(): void {
  idSent = "";
  // a call that never answers no longer holds its feature's next one back
  inflight.clear();
  waiting.clear();
  suggesting = null;
  suggestNext = null;
  useStudio.setState({ planErrors: {} });
  schedule(true);
}

export function startPlanner(): () => void {
  const un1 = useStudio.subscribe((s, prev) => {
    if (s.doc !== prev.doc || s.panel.open !== prev.panel.open || s.panel.featureId !== prev.panel.featureId) schedule();
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
