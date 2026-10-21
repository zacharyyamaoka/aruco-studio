// Verify accuracy (CoreApi.verify / readable): the simulated camera bench,
// V1 of ui-proposals-2026-10-18. Left, the bench's view of one marker as
// OpenCV read it; right, its sliders, the angle sweep of every marker and
// the camera calculator.
// WHY a hand sweep beside the automatic one (Zach, 2026-10-18): "I like how
// I can sweep the verify marker myself… Of course it should automatically
// calculate it … but it's nice being able to look at it myself." So Tilt
// re-renders while it is dragged, and the chart's columns drive it too.
import { useEffect, useMemo, useRef, useState } from "react";
import { Badge, Dialog, NumberField, SegmentedRow, Select, registerGlyphs, type Opt } from "@bam/ui";
import type { Camera, PlanRequest, Readability, VerifyResult } from "../core/contract";
import { core } from "../coreSource";
import { featureNumber, featurePreset, getFeature, planRequest, type Doc } from "../model/doc";
import { CoreWait, WaitLine, useCallWait, useCoreWait } from "../panel/Waiting";
import { activeFeatureId, useStudio } from "../store";
import {
  KNOBS0, SWEEP_TILTS, benchCamera, calcCamera, loadCalc, readsTo, saveCalc, share, viewOf, type CalcCamera, type Knobs,
} from "./bench";
import { items, markerName, type Item } from "./items";
import { ranges } from "./range";
import { RangeView } from "./RangeView";
import { SweepChart, type Series } from "./SweepChart";
import "./verify.css";

registerGlyphs({
  eye: '<path d="M1.5 8s2.4-4.5 6.5-4.5S14.5 8 14.5 8 12.1 12.5 8 12.5 1.5 8 1.5 8z" fill="none" stroke="currentColor" stroke-width="1.2"/><circle cx="8" cy="8" r="2.2" fill="currentColor"/>',
});

/** OpenCV has answered once (the worker keeps it loaded for the visit). */
let warm = false;
/** The sweep of a request, by its JSON: reopening the dialog does not redo it. */
const sweeps = new Map<string, (number | null)[]>();
/** sweep points in flight ("<request>|<tilt index>"), so a restarted sweep does not ask twice */
const pending = new Set<string>();

const KNOB_ROWS: { key: keyof Knobs; label: string; min: number; max: number; step: number; fmt: (v: number) => string }[] = [
  { key: "tilt_deg", label: "Tilt", min: 0, max: 85, step: 1, fmt: (v) => `${v}°` },
  { key: "yaw_deg", label: "Yaw", min: 0, max: 85, step: 1, fmt: (v) => `${v}°` },
  { key: "blur_px", label: "Blur", min: 0, max: 4, step: 0.1, fmt: (v) => `${v.toFixed(1)} px` },
  { key: "noise", label: "Noise", min: 0, max: 1, step: 0.05, fmt: (v) => `${Math.round(v * 100)} %` },
  { key: "glare", label: "Glare", min: 0, max: 1, step: 0.05, fmt: (v) => `${Math.round(v * 100)} %` },
  { key: "occlusion", label: "Occlusion", min: 0, max: 1, step: 0.05, fmt: (v) => `${Math.round(v * 100)} %` },
];

export { markerName } from "./items";

const errText = (e: unknown) => (e instanceof Error ? e.message : String(e));

export type VerifyView = "range" | "bench";
/** The view the next open shows (the e2e hook's open() asks for the bench; the Verify button and K, the range). */
let nextView: VerifyView = "range";
const VIEWS: Opt[] = [
  { value: "range", label: "Range", hint: "Every marker's reading range on a camera" },
  { value: "bench", label: "Bench", hint: "One marker under your own tilt, blur and glare" },
];

export function VerifyDialog() {
  const open = useStudio((s) => s.modal === "verify");
  const close = () => useStudio.getState().openModal(null);
  const doc = useStudio((s) => s.doc);
  const plans = useStudio((s) => s.plans);
  const all = useMemo(() => items(doc, plans), [doc, plans]);
  const [pick, setPick] = useState<string | null>(null);
  const [view, setView] = useState<VerifyView>("range");
  /** the bench opened at a band's end: that camera at that distance, until "the bench camera" */
  const [at, setAt] = useState<{ fid: string; camera: Camera; words: string } | null>(null);
  // the selected feature each time it opens; the picker for the rest
  useEffect(() => {
    if (open) { setPick(activeFeatureId(useStudio.getState())); setView(nextView); setAt(null); nextView = "range"; }
    // WHY cancel on close: a range runs in the core's one worker, a slice at a
    // time; nothing is left running behind a closed dialog (finished ones are kept)
    else ranges.cancelAll();
  }, [open]);
  const it = all.find((x) => x.f.id === pick) ?? all[all.length - 1] ?? null;
  const title = view === "range" ? `Verify · ${all.length === 1 ? "1 marker" : `${all.length} markers`}` : it ? `Verify · ${markerName(it.f, it.plan)}` : "Verify";
  return (
    <Dialog open={open} onClose={close} icon="eye" testid="verify-dialog" className="verify-dialog" title={title}>
      {open && (it
        ? (
          <div className="vf-wrap">
            <div className="vf-views">
              <SegmentedRow value={view} options={VIEWS} onChange={(v) => setView(v as VerifyView)} testid="verify-view" />
            </div>
            {view === "range"
              ? <RangeView all={all} doc={doc} onBench={(fid, camera, words) => { setPick(fid); setAt({ fid, camera, words }); setView("bench"); }} />
              : <Bench all={all} it={it} onPick={(id) => { setPick(id); setAt(null); }} doc={doc}
                at={at && at.fid === it.f.id ? at : null} onBenchCamera={() => setAt(null)} />}
          </div>)
        // features but no preset: they plan once the core's presets are in
        : doc.features.some((f) => !featurePreset(doc, f)) ? <CoreWait needFacts testid="verify-wait" />
        : <div className="pad muted">Nothing to verify yet: make an ArUco Extrude (A) first.</div>)}
    </Dialog>
  );
}

function Bench({ all, it, onPick, doc, at, onBenchCamera }: {
  all: Item[]; it: Item; onPick: (id: string) => void; doc: Doc;
  /** a band's end: the strip's camera at that distance instead of the bench camera */
  at: { camera: Camera; words: string } | null; onBenchCamera: () => void;
}) {
  const [knobs, setKnobs] = useState<Knobs>(KNOBS0);
  const [shot, setShot] = useState<{ r: VerifyResult; key: string; n: number } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);

  // ---- the live view: at most one verify in flight; the newest view wins
  const want = useRef<{ req: PlanRequest; key: string; view: ReturnType<typeof viewOf>; job: string } | null>(null);
  const running = useRef(false);
  const done = useRef<string | null>(null);
  const pump = async () => {
    if (running.current) return;
    running.current = true;
    setBusy(true);
    while (alive.current && want.current && want.current.job !== done.current) {
      const w = want.current;
      try {
        const r = await core.verify(w.req, w.view);
        warm = true;
        if (alive.current) { setShot((s) => ({ r, key: w.key, n: (s?.n ?? 0) + 1 })); setError(null); }
      } catch (e) {
        if (alive.current) setError(errText(e));
      }
      done.current = w.job;
    }
    running.current = false;
    if (alive.current) setBusy(false);
  };
  const cam = at ? at.camera : it.plan ? benchCamera(it.plan) : null;
  useEffect(() => {
    if (!cam) return;
    const view = viewOf(cam, knobs);
    const job = JSON.stringify([it.key, view]);
    // WHY 30 ms, not more: Tilt is dragged to watch it change, so the next
    // render starts as soon as the last one is back (pump), the debounce
    // only folds the burst of one drag step's events
    const t = setTimeout(() => { want.current = { req: it.req, key: it.key, view, job }; void pump(); }, 30);
    return () => clearTimeout(t);
  }, [it.key, JSON.stringify(cam), knobs]);

  // ---- the automatic sweep: every marker, tilt 0 → 85°, one call at a time
  const [sweepTick, setSweepTick] = useState(0);
  const order = useMemo(() => [it, ...all.filter((x) => x !== it)], [all]);
  useEffect(() => {
    let stop = false;
    (async () => {
      for (const x of order) {
        if (!x.plan) continue;
        const row = sweeps.get(x.key) ?? SWEEP_TILTS.map(() => null);
        sweeps.set(x.key, row);
        const camX = benchCamera(x.plan);
        for (let k = 0; k < SWEEP_TILTS.length; k++) {
          const slot = `${x.key}|${k}`;
          if (row[k] !== null || pending.has(slot)) continue;
          if (stop || !alive.current) return;
          pending.add(slot);
          try {
            const r = await core.verify(x.req, viewOf(camX, { ...KNOBS0, tilt_deg: SWEEP_TILTS[k] }));
            warm = true;
            row[k] = share(r.found.length, r.missing.length);
          } catch {
            row[k] = 0;
          }
          pending.delete(slot);
          if (alive.current) setSweepTick((n) => n + 1);
        }
      }
    })();
    return () => { stop = true; };
  }, [order]);
  const series: Series[] = all.map((x) => {
    const shares = sweeps.get(x.key) ?? SWEEP_TILTS.map(() => null);
    return { id: x.f.id, name: markerName(x.f, x.plan), slot: x.slot, shares, readsTo: readsTo(SWEEP_TILTS, shares) };
  });
  void sweepTick;

  const set = (k: keyof Knobs, v: number) => setKnobs((o) => ({ ...o, [k]: v }));
  const options: Opt[] = all.map((x) => ({ value: x.f.id, label: `ArUco Extrude ${featureNumber(doc, x.f.id)} · ${markerName(x.f, x.plan)}`, icon: x.f.marker.type }));
  const r = shot?.r ?? null;
  // the last image stays while the next renders; another marker's never shows
  const fresh = shot?.key === it.key;
  // the core's own start first: OpenCV loads only once Python is up
  const coreWait = useCoreWait(false);
  const loading = busy && !warm && !coreWait;
  const retry = () => { done.current = null; setError(null); void pump(); };
  const callWait = useCallWait(busy && warm, error, "rendering", retry);
  return (
    <div className="vf">
      <div className="vf-cam">
        <div className="vf-frame" data-busy={busy ? "1" : "0"}>
          {r?.image_png_base64 && fresh
            ? <img data-testid="verify-image" data-renders={shot!.n} src={`data:image/png;base64,${r.image_png_base64}`} alt="The bench camera's view, with OpenCV's detections drawn" />
            : <div className="vf-empty muted">{coreWait ? <WaitLine wait={coreWait} testid="verify-wait" /> : it.plan ? "" : "Planning the marker…"}</div>}
          {loading && <div className="vf-loading" data-testid="verify-loading"><span className="vf-spin" />Loading OpenCV (13 MB)…</div>}
          {busy && !loading && <div className="vf-busy">Rendering…</div>}
        </div>
        {callWait && <div className="vf-error" data-testid="verify-error"><WaitLine wait={callWait} testid="verify-retry" /></div>}
        {r && fresh && <Verdict r={r} />}
      </div>
      <div className="vf-side">
        <section className="vf-sec">
          <div className="vf-h">Simulated camera</div>
          <div className="vf-pick"><Select value={it.f.id} options={options} onChange={(v) => onPick(String(v))} path="verify.feature" testid="verify-marker" wide /></div>
          {KNOB_ROWS.map((k) => (
            <label key={k.key} className={`vf-slider${knobs[k.key] === 0 ? " zero" : ""}`}>
              <span className="lab">{k.label}</span>
              <input type="range" min={k.min} max={k.max} step={k.step} value={knobs[k.key]} data-knob={k.key}
                onChange={(e) => set(k.key, Number(e.target.value))} />
              <output data-testid={`knob-${k.key}`}>{k.fmt(knobs[k.key])}</output>
            </label>
          ))}
          <div className="vf-note" data-testid="bench-note">
            {at ? <>On the {at.words}: </> : "The bench: "}{r && fresh ? `${r.px_per_cell.toFixed(1)}` : "…"} px per cell head on, a {cam ? `${cam.resolution[0]} × ${cam.resolution[1]} px, ${cam.hfov_deg}°` : ""} camera
            {cam ? ` ${Math.round(cam.distance_mm)} mm away` : ""}; noise, glare and dirt repeat (seed 0).
            {at && <> <button type="button" className="vr-link" data-testid="bench-camera" onClick={onBenchCamera}>Back to the bench camera</button></>}
          </div>
        </section>
        <section className="vf-sec">
          <div className="vf-h">Angle sweep · every marker</div>
          <SweepChart tilts={SWEEP_TILTS} series={series} tilt={knobs.tilt_deg} active={it.f.id}
            onTilt={(t) => set("tilt_deg", t)} onPick={(id, t) => { onPick(id); set("tilt_deg", t); }} />
        </section>
        <Calculator it={it} />
      </div>
    </div>
  );
}

function Verdict({ r }: { r: VerifyResult }) {
  const want = [...r.found, ...r.missing].sort((a, b) => a - b);
  const range = want.length === 1 ? `#${want[0]}` : want.length ? `#${want[0]}–${want[want.length - 1]}` : "";
  const head = r.wrong.length ? "Wrong id read"
    : r.ok ? (want.length === 1 ? `Reads ${range}` : `Reads all ${want.length}: ${range}`)
      : r.found.length ? `Reads ${r.found.length} of ${want.length}` : `${range} not found`;
  const ids = [
    ...want.map((id) => ({ id, st: r.found.includes(id) ? "found" : "missing" })),
    ...r.wrong.map((id) => ({ id, st: "wrong" })),
  ];
  const pose = r.pose_error_mm !== null && r.pose_error_deg !== null ? `pose off by ${r.pose_error_mm.toFixed(2)} mm, ${r.pose_error_deg.toFixed(2)}°` : null;
  return (
    <div className="vf-verdict" data-testid="verify-verdict" data-ok={r.ok ? "1" : "0"}>
      <div className="vf-head"><span className={`dot ${r.ok ? "ok" : "bad"}`} />{head}<Badge tone={r.ok ? "ok" : "bad"}>OpenCV</Badge></div>
      <div className="vf-ids" data-testid="verify-ids">
        {ids.map(({ id, st }) => (
          <span key={`${st}${id}`} className={`vf-id ${st}`} data-id={id} data-state={st}
            title={st === "found" ? "found" : st === "missing" ? "printed, not found" : "read, but this marker never prints it"}>
            #{id}{st === "missing" ? " missing" : st === "wrong" ? " wrong" : ""}
          </span>
        ))}
      </div>
      <div className="vf-notes muted">{[pose, ...r.notes.slice(1)].filter(Boolean).join(" · ")}</div>
    </div>
  );
}

function Calculator({ it }: { it: Item }) {
  const [c, setC] = useState<CalcCamera>(loadCalc);
  const [out, setOut] = useState<{ r: Readability; job: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const seq = useRef(0);
  const job = JSON.stringify([it.key, c]);
  useEffect(() => {
    const n = ++seq.current;
    const t = setTimeout(() => {
      setBusy(true);
      core.readable(it.req, calcCamera(c)).then(
        (r) => { warm = true; if (n === seq.current) { setOut({ r, job }); setError(null); } },
        (e) => { if (n === seq.current) setError(errText(e)); },
      ).finally(() => { if (n === seq.current) setBusy(false); });
    }, 250);
    return () => clearTimeout(t);
  }, [job]);
  const edit = (k: keyof CalcCamera, v: number) => { const next = { ...c, [k]: v }; setC(next); saveCalc(next); };
  const r = out?.r;
  const tone = r?.verdict === "good" ? "ok" : r?.verdict === "marginal" ? "warn" : "bad";
  return (
    <section className="vf-sec vf-calc" data-testid="verify-calc">
      <div className="vf-h">Camera calculator · {markerName(it.f, it.plan)}</div>
      <div className="vf-row"><span className="lab">Distance</span>
        <NumberField value={c.distance_mm} unit="mm" path="verify.distance_mm" min={1} step={10} onCommit={(v) => edit("distance_mm", v)} /></div>
      <div className="vf-row"><span className="lab">Sensor width</span>
        <NumberField value={c.width_px} unit="px" path="verify.width_px" int min={16} step={10} onCommit={(v) => edit("width_px", v)} /></div>
      <div className="vf-row"><span className="lab">Horizontal FOV</span>
        <NumberField value={c.hfov_deg} unit="°" path="verify.hfov_deg" min={1} max={170} step={1} onCommit={(v) => edit("hfov_deg", v)} /></div>
      <div className="vf-out" data-busy={busy ? "1" : "0"} data-job={out?.job === job ? "current" : "stale"}>
        {r ? (
          <>
            <div className="vf-out-head">
              <Badge tone={tone} testid="calc-verdict" className={`v-${r.verdict}`}>{r.verdict}</Badge>
              <b data-testid="calc-ppc" data-value={r.px_per_cell}>{r.px_per_cell.toFixed(1)} px per cell</b>
              {busy && <span className="muted">measuring…</span>}
            </div>
            <div className="muted" data-testid="calc-text">{r.text}</div>
          </>
        ) : <div className="muted">{error ?? (warm ? "Measuring…" : "Measuring (OpenCV loads first)…")}</div>}
        {r && error && <div className="vf-error">{error}</div>}
      </div>
    </section>
  );
}

// ------------------------------------------------------------ the e2e's hook
// WHY here: the store probe (web/src/probe.ts) cannot open a modal or ask the
// core, and this lane owns only web/src/verify. Opens the dialog on a
// feature; asks the core's readable for a feature directly (the oracle the
// calculator's numbers are checked against).
if (typeof window !== "undefined") {
  (window as unknown as { __arucoVerify: unknown }).__arucoVerify = {
    // WHY the bench by default here: the bench's e2e (verify.spec.ts) opens it
    // by this hook; the Verify button and K open the range strip
    open: (featureId?: string, view: VerifyView = "bench") => {
      const st = useStudio.getState();
      if (featureId) st.select({ kind: "feature", id: featureId });
      nextView = view;
      st.openModal("verify");
    },
    readable: (featureId: string, camera: CalcCamera) => {
      const doc = useStudio.getState().doc;
      const req = planRequest(doc, getFeature(doc, featureId));
      return req ? core.readable(req, calcCamera(camera)) : Promise.reject(new Error(`no feature ${featureId}`));
    },
  };
}
