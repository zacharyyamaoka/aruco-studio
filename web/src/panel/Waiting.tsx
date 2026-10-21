// What the Studio is waiting for, said plainly: the core starting (with the
// seconds once it takes a while), the core failed (its error, Reload), the
// presets not answered (Retry), a plan that is slow or failed (Retry). The
// panel's Preset row and footer, the top bar's chip and the dialogs that ask
// the core (Sheet, Verify, the presets, Re-ID) all say it the same way.
// WHY (Zach, 2026-10-20 night, "BUG: seems to be stuck loading?"): "Loading…"
// and "Planning…" read the same whether the core was starting, had failed or
// was stuck, so a wait that would never end looked like one that would.
import { useEffect, useState } from "react";
import { Button } from "@bam/ui";
import { coreElapsedMs, coreKind, useCoreStatus } from "../coreSource";
import { replan } from "../planner";
import { loadCoreFacts, useStudio } from "../store";
import "./waiting.css";

/** A starting core shows its seconds from here on (s). */
const SHOW_SECONDS = 3;
/** A plan out longer than this is slow: "Still planning…", with Retry (ms). */
export const SLOW_PLAN_MS = 8000;

export interface Wait {
  kind: "core-loading" | "core-error" | "facts-asking" | "facts-error" | "planning" | "plan-slow" | "plan-error" | "slow" | "error";
  /** a few words, for a row (the panel's Preset) */
  short: string;
  text: string;
  action?: { label: "Retry" | "Reload"; run: () => void };
}

export const reload = () => location.reload();

/** Re-render every `ms` while `on`. */
export function useTick(on: boolean, ms = 500): void {
  const [, setN] = useState(0);
  useEffect(() => {
    if (!on) return;
    const t = setInterval(() => setN((n) => n + 1), ms);
    return () => clearInterval(t);
  }, [on, ms]);
}

/** How long (ms) `on` has been true, ticking; 0 while it is false. */
export function useSince(on: boolean): number {
  const [at, setAt] = useState<number | null>(null);
  useEffect(() => { setAt(on ? performance.now() : null); }, [on]);
  useTick(on);
  return on && at !== null ? performance.now() - at : 0;
}

/** "Starting Python… (first load takes a few seconds) · 5 s". */
export function startingText(): string {
  const s = Math.floor(coreElapsedMs() / 1000);
  const what = coreKind === "mock" ? "the mock core" : "Python";
  return `Starting ${what}… (first load takes a few seconds)${s >= SHOW_SECONDS ? ` · ${s} s` : ""}`;
}

/** What waits on the core: its start, then (`needFacts`: the caller has no
 *  preset, or no built-ins) the dictionaries and presets; null when nothing does. */
export function useCoreWait(needFacts: boolean): Wait | null {
  const core = useCoreStatus();
  const facts = useStudio((s) => s.facts);
  useTick(core.state === "loading");
  if (core.state === "loading") {
    return { kind: "core-loading", short: coreKind === "mock" ? "Starting the mock core…" : "Starting Python…", text: startingText() };
  }
  if (core.state === "error") {
    return { kind: "core-error", short: "Core failed to start", text: `The Python core failed to start: ${core.detail ?? "no reason given"}`, action: { label: "Reload", run: reload } };
  }
  if (!needFacts || facts.state === "ok") return null;
  if (facts.state === "error") {
    return { kind: "facts-error", short: "Presets did not load", text: `The core didn't answer: ${facts.error ?? "no reason given"}`, action: { label: "Retry", run: () => void loadCoreFacts() } };
  }
  return { kind: "facts-asking", short: "Asking the core…", text: "Asking the core for its presets and dictionaries…" };
}

/** A wait as a line: its text and its action. */
export function WaitLine({ wait, testid = "core-wait" }: { wait: Wait; testid?: string }) {
  return (
    <span className={`wait-line wait-${wait.kind}`} data-testid={testid} data-wait={wait.kind}>
      <span className="wait-text">
        {(wait.kind === "core-loading" || wait.kind === "facts-asking" || wait.kind === "planning") && <i className="wait-spin" aria-hidden="true" />}
        {wait.text}
      </span>
      {wait.action && <Button size="sm" onClick={wait.action.run} testid={`${testid}-action`}>{wait.action.label}</Button>}
    </span>
  );
}

/** The core's wait for a dialog, or nothing once it is ready (and has its facts, with `needFacts`). */
export function CoreWait({ needFacts = false, testid = "core-wait" }: { needFacts?: boolean; testid?: string }) {
  const wait = useCoreWait(needFacts);
  return wait ? <div className="wait-block"><WaitLine wait={wait} testid={testid} /></div> : null;
}

/** The panel's Preset row while the document has no preset. */
export function PresetWait() {
  const wait = useCoreWait(true);
  return <span data-testid="preset-wait" data-wait={wait?.kind ?? "none"}>{wait?.short ?? "No preset: pick one"}</span>;
}

/** A call a dialog made that has not answered for `slowMs`: "Still … the core
 *  is busy", with Retry; the error, with Retry, once it failed. Null while it
 *  is young (the dialog's own words show) or done. */
export function useCallWait(pending: boolean, error: string | null, doing: string, retry: () => void, slowMs = SLOW_PLAN_MS): Wait | null {
  const since = useSince(pending && !error);
  if (error) return { kind: "error", short: "Failed", text: error, action: { label: "Retry", run: retry } };
  if (pending && since > slowMs) return { kind: "slow", short: `Still ${doing}…`, text: `Still ${doing}… the core is busy`, action: { label: "Retry", run: retry } };
  return null;
}

/** The panel's footer line: the instruction, the plan's summary, or what it waits for. */
export function PlanLine({ profile, summary, error }: { profile: boolean; summary: string | null; error: string | null }) {
  const hasPreset = useStudio((s) => !!s.doc.preset);
  const wait = useCoreWait(!hasPreset);
  const planning = profile && !summary && !error && !wait;
  const since = useSince(planning);
  if (wait?.kind === "core-error") return <WaitLine wait={wait} testid="plan-wait" />;
  if (!profile) return <>Select a profile: click inside a region, or double-click a rectangle</>;
  if (summary) return <>{summary}</>;
  if (wait) return <WaitLine wait={wait} testid="plan-wait" />;
  if (error) return <WaitLine wait={{ kind: "plan-error", short: "Plan failed", text: `Plan failed: ${error}`, action: { label: "Retry", run: replan } }} testid="plan-wait" />;
  if (since > SLOW_PLAN_MS) {
    return <WaitLine wait={{ kind: "plan-slow", short: "Still planning…", text: "Still planning… the core is busy", action: { label: "Retry", run: replan } }} testid="plan-wait" />;
  }
  return <WaitLine wait={{ kind: "planning", short: "Planning…", text: "Planning the marker…" }} testid="plan-wait" />;
}
