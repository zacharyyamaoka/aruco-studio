// What the Studio is waiting for, said plainly: starting up (with the seconds
// once it takes a while), it couldn't start (Reload), the presets not loaded
// (Retry), a plan that is slow or failed (Retry). Only what is actually
// waiting says it -- the panel's Preset row and footer, and the dialogs that
// ask the core (Sheet, Verify, the presets, Re-ID) -- and the help popover's
// status line; the technical reason (Python, which file) is behind Details.
// WHY (Zach, 2026-10-20 night, "BUG: seems to be stuck loading?"): "Loading…"
// and "Planning…" read the same whether the core was starting, had failed or
// was stuck, so a wait that would never end looked like one that would.
// WHY user words and no chip (Zach, 2026-10-20 night): "for me that's back end
// details, no need to show me that on the front end in a visible place ...
// it shouldn't clutter the main viewer."
import { useEffect, useState } from "react";
import { Button } from "@bam/ui";
import { coreElapsedMs, coreKind, useCoreStatus } from "../coreSource";
import { featurePreset, getFeature } from "../model/doc";
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
  /** the technical reason, behind a small Details disclosure */
  detail?: string;
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

/** "Starting up…", then "Starting up… 5 s". */
export function startingText(): string {
  const s = Math.floor(coreElapsedMs() / 1000);
  return `Starting up…${s >= SHOW_SECONDS ? ` ${s} s` : ""}`;
}

/** The technical reason the core failed to start (the Details disclosure). */
export function failedDetail(detail: string | undefined): string {
  return `The ${coreKind === "mock" ? "mock" : "Python"} core failed to start: ${detail ?? "no reason given"}`;
}

/** What waits on the core: its start, then (`needFacts`: the caller has no
 *  preset, or no built-ins) the dictionaries and presets; null when nothing does. */
export function useCoreWait(needFacts: boolean): Wait | null {
  const core = useCoreStatus();
  const facts = useStudio((s) => s.facts);
  useTick(core.state === "loading");
  if (core.state === "loading") return { kind: "core-loading", short: "Starting up…", text: startingText() };
  if (core.state === "error") {
    return { kind: "core-error", short: "Couldn't start", text: "Couldn't start", detail: failedDetail(core.detail), action: { label: "Reload", run: reload } };
  }
  if (!needFacts || facts.state === "ok") return null;
  if (facts.state === "error") {
    return { kind: "facts-error", short: "Couldn't load the presets", text: "Couldn't load the presets",
      detail: `The core didn't answer: ${facts.error ?? "no reason given"}`, action: { label: "Retry", run: () => void loadCoreFacts() } };
  }
  return { kind: "facts-asking", short: "Loading the presets…", text: "Loading the presets…" };
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
      {wait.detail && (
        <details className="wait-details" data-testid={`${testid}-details`}>
          <summary>Details</summary>
          <span className="wait-detail" data-testid={`${testid}-detail`}>{wait.detail}</span>
        </details>
      )}
    </span>
  );
}

/** The core's wait for a dialog, or nothing once it is ready (and has its facts, with `needFacts`). */
export function CoreWait({ needFacts = false, testid = "core-wait" }: { needFacts?: boolean; testid?: string }) {
  const wait = useCoreWait(needFacts);
  return wait ? <div className="wait-block"><WaitLine wait={wait} testid={testid} /></div> : null;
}

/** The panel's Preset row while its marker has no preset yet. */
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
  const hasPreset = useStudio((s) => !!featurePreset(s.doc, getFeature(s.doc, s.panel.featureId)));
  const wait = useCoreWait(!hasPreset);
  const planning = profile && !summary && !error && !wait;
  const since = useSince(planning);
  if (wait?.kind === "core-error") return <WaitLine wait={wait} testid="plan-wait" />;
  if (!profile) return <>Select a profile: click inside a region, or double-click a rectangle</>;
  // a planned marker: the skins may mark it (Fusion: the green "✓ …" line)
  if (summary) return <span className="plan-ok" data-testid="plan-ok">{summary}</span>;
  if (wait) return <WaitLine wait={wait} testid="plan-wait" />;
  if (error) return <WaitLine wait={{ kind: "plan-error", short: "Plan failed", text: `Plan failed: ${error}`, action: { label: "Retry", run: replan } }} testid="plan-wait" />;
  if (since > SLOW_PLAN_MS) {
    return <WaitLine wait={{ kind: "plan-slow", short: "Still planning…", text: "Still planning… the core is busy", action: { label: "Retry", run: replan } }} testid="plan-wait" />;
  }
  return <WaitLine wait={{ kind: "planning", short: "Planning…", text: "Planning the marker…" }} testid="plan-wait" />;
}
