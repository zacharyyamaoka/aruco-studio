// Verify's range strip (V4 of verify-unit-test-proposals-2026-10-21): pick a
// camera from the library, and every marker shows the distances it reads at
// -- the markers along the top, a band under each on ONE shared axis -- with
// an optional required distance, batch-set on a selection, that turns each
// band into PASS / FAIL with what to change.
// WHY (Zach, 2026-10-21): "maybe I can just select the camera and then Verify
// can tell me what is a suitable range ... a view where I can quickly see all
// the markers along the top and underneath a line that represents the
// distance they can be viewed"; "some standard ones for RealSense etc. so I
// could search for them and just click it"; "batch set minimum and maximum
// viewing distance". The numbers are the core's (./range.ts runs it).
import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { Badge, NumberField } from "@bam/ui";
import type { Camera, CameraPreset, MarkerPlan, Polygon, RangeNeed, RangeVerdict, ReadingRange, Vec2 } from "../core/contract";
import { core } from "../coreSource";
import { MIXED, common } from "../model/batch";
import type { Doc, Feature } from "../model/doc";
import { labelInk } from "../sketch/Viewport";
import { useStudio } from "../store";
import {
  CUSTOM0, axisOf, fmtMm, judge, knownVerdict, loadCamera, needless, rangeCamera, rangeKey, ranges, saveCamera, searchCameras,
  tickText, ticksOf, verdictKey, xOf, type CameraPick, type RangeState, type RangeTask,
} from "./range";
import { markerName, type Item } from "./items";

/** the band's drawing, px: its width, the axis's ends inside it */
const BAND_W = 196, BAND_H = 46, AX0 = 10, AX1 = BAND_W - 10, AXY = 14;
/** the thumbnails' box, px: one mm-to-px scale for them all, so sizes compare */
const THUMB_W = 176, THUMB_H = 74;

let library: Promise<CameraPreset[]> | null = null;
function useLibrary(): { lib: CameraPreset[] | null; error: string | null } {
  const [lib, setLib] = useState<CameraPreset[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    library ??= core.cameras().catch((e: unknown) => { library = null; throw e; });
    library.then((l) => { if (live) setLib(l); }, (e: unknown) => { if (live) setError(e instanceof Error ? e.message : String(e)); });
    return () => { live = false; };
  }, []);
  return { lib, error };
}

/** "RealSense D435 · colour 1920×1080 · 69°" */
function cameraWords(p: CameraPick, lib: CameraPreset[] | null): { name: string; detail: string } {
  if ("custom" in p) return { name: "Custom camera", detail: `${p.custom.resolution[0]}×${p.custom.resolution[1]} · ${p.custom.hfov_deg}°` };
  const c = lib?.find((x) => x.id === p.id);
  return c ? { name: c.name, detail: `${c.stream} · ${c.hfov_deg}°` } : { name: p.id, detail: "" };
}

/** The bench's camera at a distance on the strip's camera. */
export function benchAt(p: CameraPick, lib: CameraPreset[] | null, distance_mm: number): Camera | null {
  if ("custom" in p) return { distance_mm, resolution: p.custom.resolution, hfov_deg: p.custom.hfov_deg };
  const c = lib?.find((x) => x.id === p.id);
  return c ? { distance_mm, resolution: c.resolution, hfov_deg: c.hfov_deg } : null;
}

export function RangeView({ all, doc, onBench }: {
  all: Item[]; doc: Doc;
  /** open the bench on a marker at this camera (a band's end) */
  onBench: (featureId: string, camera: Camera, words: string) => void;
}) {
  const { lib, error: libError } = useLibrary();
  const [pick, setPickState] = useState<CameraPick>(loadCamera);
  const [picker, setPicker] = useState(false);
  const [sel, setSel] = useState<string[]>([]);
  const coreVersion = useStudio((s) => s.info?.core_version ?? null);
  useSyncExternalStore(ranges.subscribe, ranges.version);
  const setPick = (p: CameraPick) => { setPickState(p); saveCamera(p); setPicker(false); };

  const cam = rangeCamera(pick);
  // the selected markers first (what he is looking at), then the document's order
  const tasks: (RangeTask & { item: Item })[] = useMemo(() => {
    if (!coreVersion) return [];
    const rows = all.map((it) => ({ key: rangeKey(it.req, cam, coreVersion), req: it.req, camera: cam, item: it }));
    return [...rows.filter((t) => sel.includes(t.item.f.id)), ...rows.filter((t) => !sel.includes(t.item.f.id))];
  }, [all, JSON.stringify(cam), coreVersion, sel.join(",")]);
  useEffect(() => { ranges.want(tasks); }, [tasks]);
  // WHY pause, not cancel, on leaving the strip: the bench is one click away
  // and back; a part-done marker resumes where it was (the dialog's close cancels)
  useEffect(() => () => ranges.want([]), []);

  const byId = new Map(tasks.map((t) => [t.item.f.id, t]));
  const states = new Map(tasks.map((t) => [t.item.f.id, ranges.state(t.key)]));
  const results = all.map((it) => { const s = states.get(it.f.id); return s?.state === "done" ? s.result : null; });
  const needs = all.map((it) => it.f.verify ?? null);
  const [lo, hi] = axisOf(results, needs);
  const scale = stripScale(all.map((it) => it.plan));

  const done = [...states.values()].filter((s) => s.state === "done").length;
  const running = [...states.values()].find((s) => s.state === "running") as Extract<RangeState, { state: "running" }> | undefined;

  const click = (fid: string, e: React.MouseEvent) => {
    if (e.shiftKey || e.metaKey || e.ctrlKey) setSel((xs) => (xs.includes(fid) ? xs.filter((x) => x !== fid) : [...xs, fid]));
    else setSel((xs) => (xs.length === 1 && xs[0] === fid ? [] : [fid]));
  };
  const words = cameraWords(pick, lib);

  return (
    <div className="vr" data-testid="range-view">
      <div className="vr-top">
        <div className="vr-campick">
          <button type="button" className="vr-chip cam" data-testid="camera-chip" data-camera={"id" in pick ? pick.id : "custom"}
            aria-expanded={picker} onClick={() => setPicker((o) => !o)} title="The camera the markers are read with: pick one from the library">
            <CamGlyph /><b>{words.name}</b><span>{words.detail}</span><i aria-hidden="true">⌄</i>
          </button>
          {picker && <CameraPicker lib={lib} error={libError} pick={pick} onPick={setPick} onClose={() => setPicker(false)} />}
        </div>
        <span className="vr-chip" title="Every id must read in 95 % of 48 cameras drawn from this budget, at every distance in the band">
          Field: tilt ≤ 45° · blur ≤ 1.5 px · grain ≤ 0.2 · glare ≤ 0.5
        </span>
        <span className="vr-status muted" data-testid="range-status">
          {!coreVersion ? "Waiting for the core…"
            : running ? `Measuring ${done + 1} of ${all.length} · ${Math.round(running.fraction * 100)} %`
              : done === all.length ? summary(all, states, byId) : `${done} of ${all.length} measured`}
        </span>
      </div>
      <div className="vr-strip" data-testid="range-strip">
        {all.map((it) => {
          const t = byId.get(it.f.id);
          return (
            <Column key={it.f.id} it={it} task={t} state={t ? ranges.state(t.key) : { state: "queued" }} lo={lo} hi={hi} scale={scale}
              selected={sel.includes(it.f.id)} onClick={(e) => click(it.f.id, e)}
              onEnd={(mm, end) => {
                const c = benchAt(pick, lib, mm);
                if (c) onBench(it.f.id, c, `${words.name} at ${fmtMm(mm)} (the range's ${end} end)`);
              }} />
          );
        })}
      </div>
      <Requirement doc={doc} all={all} sel={sel} onSelectAll={() => setSel(all.map((x) => x.f.id))} onClear={() => setSel([])} />
      <div className="vr-foot muted" data-testid="range-foot">
        Each band: the nearest and farthest distance at which every id reads in 95 % of 48 seeded cameras from the budget
        (6+ distances, fitted; the pale end is the far end's 90 % interval), {opencvWords(results)}.
        Click a band's end to open the bench there.
      </div>
    </div>
  );
}

/** Which OpenCV drew and read the views (its warps differ between releases: a
 *  CPython table states its own, so the two can be compared). */
function opencvWords(results: (ReadingRange | null)[]): string {
  const r = results.find((x) => x);
  if (!r) return "OpenCV reading the marker as planned";
  return r.measured ? `OpenCV ${r.opencv ?? ""} reading the marker as planned, in this browser` : "the pinhole model (OpenCV did not load)";
}

function summary(all: Item[], states: Map<string, RangeState>, byId: Map<string, RangeTask>): string {
  const judged = all.filter((it) => !needless(it.f.verify));
  if (!judged.length) return `${all.length} measured`;
  let pass = 0, fail = 0;
  for (const it of judged) {
    const s = states.get(it.f.id), t = byId.get(it.f.id);
    if (s?.state !== "done" || !t) continue;
    const v = knownVerdict(verdictKey(t.key, it.f.verify!));
    if (v?.verdict === "pass") pass++;
    else if (v?.verdict === "fail") fail++;
  }
  return `${pass} pass · ${fail} fail${judged.length < all.length ? ` · ${all.length - judged.length} with no requirement` : ""}`;
}

// ------------------------------------------------------------ one marker's column

function useVerdict(task: RangeTask | undefined, result: ReadingRange | null, need: RangeNeed | undefined): RangeVerdict | null {
  const k = task && result && !needless(need) ? verdictKey(task.key, need!) : null;
  const [v, setV] = useState<{ k: string; v: RangeVerdict } | null>(null);
  useEffect(() => {
    if (!k || !result) return;
    let live = true;
    judge(k, result, need!).then((r) => { if (live) setV({ k, v: r }); }, () => undefined);
    return () => { live = false; };
  }, [k]);
  if (!k) return null;
  return v?.k === k ? v.v : knownVerdict(k);
}

function Column({ it, task, state, lo, hi, scale, selected, onClick, onEnd }: {
  it: Item; task: RangeTask | undefined; state: RangeState; lo: number; hi: number; scale: number; selected: boolean;
  onClick: (e: React.MouseEvent) => void; onEnd: (mm: number, end: "near" | "far") => void;
}) {
  const r = state.state === "done" ? state.result : null;
  const need = it.f.verify;
  const v = useVerdict(task, r, need);
  const tone = !r || !r.far_mm ? "bad" : v?.verdict === "pass" ? "ok" : v?.verdict === "fail" ? "bad" : "plain";
  const lint = (it.plan?.warnings ?? []).filter((w) => w.level !== "info" && /^(label|marker)/.test(w.field)).slice(0, 2);
  return (
    <div className={`vr-col${selected ? " on" : ""}`} data-testid="range-col" data-feature={it.f.id} data-state={state.state}
      data-near={r?.near_mm ?? ""} data-far={r?.far_mm ?? ""} data-verdict={v?.verdict ?? ""} data-selected={selected ? "1" : "0"}
      data-renders={r?.renders ?? ""} onClick={onClick} role="button" aria-pressed={selected}
      title="Click to select, Shift- or Ctrl-click to add: the required distance below sets the selection">
      <div className="vr-thumb">{it.plan ? <MarkerThumb f={it.f} plan={it.plan} scale={scale} /> : <span className="muted">Planning…</span>}</div>
      <div className="vr-name"><b>{markerName(it.f, it.plan)}</b>{it.plan ? ` · ${+it.plan.marker_mm.toFixed(2)} mm` : ""}</div>
      <Band r={r} need={need} lo={lo} hi={hi} tone={tone} state={state} onEnd={onEnd} />
      {state.state === "done" && r && (r.far_mm
        ? <div className={`vr-num ${tone}`} data-testid="range-num">{fmtMm(r.near_mm)} – <b>{fmtMm(r.far_mm)}</b>
          {r.pm != null && <small> ± {Math.round(r.pm * 100)} %</small>}</div>
        : <div className="vr-num bad" data-testid="range-num"><b>Reads nowhere</b> on this camera</div>)}
      {state.state === "running" && (
        <div className="vr-prog" data-testid="range-progress">
          <span style={{ width: `${Math.round(state.fraction * 100)}%` }} />
          <small className="muted">measuring · {Math.round(state.fraction * 100)} % · {state.renders} views</small>
        </div>)}
      {state.state === "queued" && <div className="vr-num muted">waiting…</div>}
      {state.state === "error" && (
        <div className="vr-num bad" data-testid="range-error">{state.error}{" "}
          <button type="button" className="vr-link" onClick={(e) => { e.stopPropagation(); if (task) ranges.retry(task.key); }}>Retry</button></div>)}
      {v?.verdict && (
        <div className={`vr-verdict ${v.verdict}`} data-testid="range-verdict">
          <Badge tone={v.verdict === "pass" ? "ok" : "bad"}>{v.verdict === "pass" ? "PASS" : "FAIL"}</Badge>
          <span>{needWords(need!)}</span>
        </div>)}
      {v?.verdict === "fail" && v.hints.map((h, k) => <div key={k} className="vr-hint" data-testid="range-hint">{h}</div>)}
      {r && r.far_mm && r.weakest_id != null && r.geometry.ids.length > 1 && (
        <div className="vr-note muted">#{r.weakest_id} drops first{r.far_limit === "outline" ? " · limited by OpenCV's minimum outline" : ""}</div>)}
      {r && r.far_mm && r.far_limit === "outline" && r.geometry.ids.length === 1 && <div className="vr-note muted">limited by OpenCV's minimum outline</div>}
      {lint.map((w, k) => <div key={`l${k}`} className="vr-note warn" title={w.text}>{w.text}</div>)}
    </div>
  );
}

function needWords(n: RangeNeed): string {
  if (n.min_mm != null && n.max_mm != null) return `needs ${fmtMm(n.min_mm)} – ${fmtMm(n.max_mm)}`;
  if (n.max_mm != null) return `needs out to ${fmtMm(n.max_mm)}`;
  return `needs from ${fmtMm(n.min_mm!)}`;
}

function Band({ r, need, lo, hi, tone, state, onEnd }: {
  r: ReadingRange | null; need: RangeNeed | undefined; lo: number; hi: number; tone: string; state: RangeState;
  onEnd: (mm: number, end: "near" | "far") => void;
}) {
  const X = (mm: number) => xOf(mm, lo, hi, AX0, AX1);
  const ticks = ticksOf(lo, hi);
  const reqLo = need?.min_mm ?? null, reqHi = need?.max_mm ?? null;
  const has = !needless(need);
  return (
    <svg className={`vr-band ${tone}`} width={BAND_W} height={BAND_H} viewBox={`0 0 ${BAND_W} ${BAND_H}`} data-testid="range-band"
      data-lo={lo} data-hi={hi} data-x0={AX0} data-x1={AX1} role="img"
      aria-label={r?.far_mm ? `reads ${fmtMm(r.near_mm)} to ${fmtMm(r.far_mm)}` : "no range yet"}>
      {has && (
        <rect className="vr-req" data-testid="range-req" x={X(reqLo ?? lo)} y={AXY - 8} width={Math.max(1, X(reqHi ?? hi) - X(reqLo ?? lo))} height={16} rx={2} />
      )}
      <line className="vr-axis" x1={AX0} x2={AX1} y1={AXY} y2={AXY} />
      {r?.far_mm && r.near_mm && r.band_mm && (
        <line className="vr-fuzz" x1={X(r.band_mm[0])} x2={X(r.band_mm[1])} y1={AXY} y2={AXY} />
      )}
      {r?.far_mm && r.near_mm && (<>
        <line className="vr-bar" data-testid="range-bar" x1={X(r.near_mm)} x2={X(r.far_mm)} y1={AXY} y2={AXY} />
        <circle className="vr-cap" data-end="near" cx={X(r.near_mm)} cy={AXY} r={4.2}
          onClick={(e) => { e.stopPropagation(); onEnd(r.near_mm!, "near"); }}><title>{`near end ${fmtMm(r.near_mm)}: open the bench here`}</title></circle>
        <circle className="vr-cap" data-end="far" cx={X(r.far_mm)} cy={AXY} r={4.2}
          onClick={(e) => { e.stopPropagation(); onEnd(r.far_mm!, "far"); }}><title>{`far end ${fmtMm(r.far_mm)}: open the bench here`}</title></circle>
      </>)}
      {state.state !== "done" && <line className="vr-wait" x1={AX0} x2={AX1} y1={AXY} y2={AXY} />}
      {ticks.map((t, k) => (
        <g key={t}>
          <line className="vr-tick" x1={X(t)} x2={X(t)} y1={AXY + 9} y2={AXY + 12} />
          <text className="vr-ticktext" x={X(t)} y={AXY + 24} textAnchor="middle">{tickText(t, k === ticks.length - 1)}</text>
        </g>
      ))}
    </svg>
  );
}

// ------------------------------------------------------------ the thumbnail: the marker as planned

function bbox(pts: Vec2[]): [number, number, number, number] {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const [x, y] of pts) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }
  return [x0, y0, x1, y1];
}

/** What the thumbnail shows: the marker (its quiet zone's edge) and its
 *  label, not the whole sticker it is cut from (a plate's face would dwarf it). */
function planBox(plan: MarkerPlan): [number, number, number, number] {
  const pts: Vec2[] = [...plan.outer];
  if (plan.label?.box) pts.push(...plan.label.box);
  return bbox(pts);
}

/** px per mm that fits this marker in the thumbnail's box. */
function fitScale(plan?: MarkerPlan): number {
  if (!plan) return Infinity;
  const [x0, y0, x1, y1] = planBox(plan);
  return Math.min(THUMB_W / Math.max(1e-6, x1 - x0), THUMB_H / Math.max(1e-6, y1 - y0));
}

/** The strip's one mm-to-px scale (sizes compare at a glance), raised until
 *  the smallest marker is MIN_THUMB px across; a big one is fitted down to its box. */
const MIN_THUMB = 34;
function stripScale(plans: (MarkerPlan | undefined)[]): number {
  const ps = plans.filter((p): p is MarkerPlan => !!p);
  if (!ps.length) return 1;
  const common = Math.min(...ps.map(fitScale));
  const smallest = Math.min(...ps.map((p) => { const [x0, y0, x1, y1] = planBox(p); return Math.max(x1 - x0, y1 - y0); }));
  return Math.max(common, MIN_THUMB / Math.max(1e-6, smallest));
}

const LINE_GAP = 0.4;   // the core's label line pitch (rect_fill LINE_GAP), as the canvas draws it

function MarkerThumb({ f, plan, scale: strip }: { f: Feature; plan: MarkerPlan; scale: number }) {
  const scale = Math.min(strip, fitScale(plan));
  const [x0, y0, x1, y1] = planBox(plan);
  const w = Math.max(4, (x1 - x0) * scale), h = Math.max(4, (y1 - y0) * scale);
  // sketch mm (y up) -> thumbnail px (y down)
  const P = (p: Vec2) => `${((p[0] - x0) * scale).toFixed(2)} ${((y1 - p[1]) * scale).toFixed(2)}`;
  const loop = (l: Vec2[]) => (l.length ? `M${l.map(P).join("L")}Z` : "");
  const poly = (p: Polygon) => loop(p.outer) + p.holes.map(loop).join("");
  const pl = plan.label;
  const ink = labelInk(f) === "white" ? "var(--t-white)" : "var(--t-black)";
  let label = null;
  if (pl && pl.text) {
    if (pl.font === "pixel" && pl.polygons?.length) label = <path d={pl.polygons.map(poly).join("")} fillRule="evenodd" style={{ fill: ink }} />;
    else {
      const lines = pl.lines?.length ? pl.lines : pl.text.split("\n");
      const cap = pl.height_mm * scale, pitch = (1 + LINE_GAP) * cap;
      const [ax, ay] = [(pl.at[0] - x0) * scale, (y1 - pl.at[1]) * scale];
      label = (
        <g transform={pl.angle_deg ? `rotate(${-pl.angle_deg} ${ax} ${ay})` : undefined}>
          {lines.map((t, k) => (
            <text key={k} x={ax} y={ay - ((lines.length - 1) / 2 - k) * pitch + cap / 2} fontSize={Math.max(2, cap / 0.7)} textAnchor="middle" style={{ fill: ink }}>{t}</text>
          ))}
        </g>);
    }
  }
  return (
    <svg className="vr-mark" width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true">
      <path d={loop(plan.outer)} className="vr-paper" />
      <path d={plan.black.map(poly).join("")} fillRule="evenodd" className="vr-ink" />
      {label}
    </svg>
  );
}

// ------------------------------------------------------------ the required distance, batch-set (model/batch.ts's pattern)

function Requirement({ doc, all, sel, onSelectAll, onClear }: {
  doc: Doc; all: Item[]; sel: string[]; onSelectAll: () => void; onClear: () => void;
}) {
  const st = useStudio.getState();
  const fs = sel.map((id) => doc.features.find((f) => f.id === id)).filter((f): f is Feature => !!f);
  if (!fs.length) {
    return (
      <div className="vr-req-bar" data-testid="range-req-bar" data-selected="0">
        <span className="vr-h">Required distance</span>
        <span className="muted">Optional: click markers (Shift-click for more) to set the distance they must read at.</span>
        {all.length > 1 && <button type="button" className="vr-link" data-testid="range-select-all" onClick={onSelectAll}>Select all {all.length}</button>}
      </div>
    );
  }
  const ids = fs.map((f) => f.id);
  const mins = common(fs.map((f) => f.verify?.min_mm ?? null));
  const maxs = common(fs.map((f) => f.verify?.max_mm ?? null));
  const any = fs.some((f) => !needless(f.verify));
  return (
    <div className="vr-req-bar" data-testid="range-req-bar" data-selected={fs.length}>
      <span className="vr-h">Required distance</span>
      <span className="vr-req-who">{fs.length === 1 ? markerName(fs[0], undefined) : `${fs.length} markers`}</span>
      <label className="vr-req-field"><span>from</span>
        <NumberField value={mins === MIXED ? null : (mins as number | null)} mixed={mins === MIXED} unit="mm" min={0} step={50}
          path="verify.min_mm" placeholder="—" onCommit={(v) => st.setFieldMany(ids, "verify.min_mm", v)} /></label>
      <label className="vr-req-field"><span>to</span>
        <NumberField value={maxs === MIXED ? null : (maxs as number | null)} mixed={maxs === MIXED} unit="mm" min={0} step={50}
          path="verify.max_mm" placeholder="—" onCommit={(v) => st.setFieldMany(ids, "verify.max_mm", v)} /></label>
      {(mins === MIXED || maxs === MIXED) && <span className="batch-mixed" data-mixed-for="verify">Mixed</span>}
      {any && <button type="button" className="vr-link" data-testid="range-req-clear" onClick={() => st.setFieldMany(ids, "verify", null)}>Clear</button>}
      <span className="grow" />
      {all.length > fs.length && <button type="button" className="vr-link" onClick={onSelectAll}>Select all {all.length}</button>}
      <button type="button" className="vr-link" onClick={onClear}>Deselect</button>
    </div>
  );
}

// ------------------------------------------------------------ the camera library

function CamGlyph() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
      <rect x="1.5" y="4" width="13" height="9" rx="1.6" fill="none" stroke="currentColor" strokeWidth="1.2" />
      <path d="M5.5 4l1-1.6h3L10.5 4" fill="none" stroke="currentColor" strokeWidth="1.2" />
      <circle cx="8" cy="8.5" r="2.4" fill="none" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

function CameraPicker({ lib, error, pick, onPick, onClose }: {
  lib: CameraPreset[] | null; error: string | null; pick: CameraPick; onPick: (p: CameraPick) => void; onClose: () => void;
}) {
  const [q, setQ] = useState("");
  const [at, setAt] = useState(0);
  const [custom, setCustom] = useState("custom" in pick ? pick.custom : CUSTOM0);
  const input = useRef<HTMLInputElement>(null);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => { input.current?.focus(); }, []);
  // a click outside closes it (the chip toggles it itself)
  useEffect(() => {
    const down = (e: PointerEvent) => {
      const t = e.target as Node;
      if (box.current && !box.current.contains(t) && !(t as Element).closest?.('[data-testid="camera-chip"]')) onClose();
    };
    document.addEventListener("pointerdown", down, true);
    return () => document.removeEventListener("pointerdown", down, true);
  }, [onClose]);
  const rows = lib ? searchCameras(lib, q) : [];
  useEffect(() => { setAt(0); }, [q]);
  const current = "id" in pick ? pick.id : "custom";
  return (
    <div className="vr-picker" data-testid="camera-picker" ref={box}
      onKeyDown={(e) => {
        if (e.key === "Escape") { e.stopPropagation(); onClose(); }
        else if (e.key === "ArrowDown") { e.preventDefault(); setAt((a) => Math.min(rows.length - 1, a + 1)); }
        else if (e.key === "ArrowUp") { e.preventDefault(); setAt((a) => Math.max(0, a - 1)); }
        else if (e.key === "Enter" && rows[at] && (e.target as HTMLElement).tagName === "INPUT" && e.target === input.current) { e.preventDefault(); onPick({ id: rows[at].id }); }
      }}>
      <div className="vr-search">
        <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><circle cx="5" cy="5" r="3.6" fill="none" stroke="currentColor" strokeWidth="1.2" /><path d="M7.7 7.7l3 3" stroke="currentColor" strokeWidth="1.3" /></svg>
        <input ref={input} data-testid="camera-search" value={q} placeholder="Search cameras (RealSense, OAK, ZED, 4K…)" onChange={(e) => setQ(e.target.value)} />
        <small className="muted">{lib ? `${rows.length} of ${lib.length}` : ""}</small>
      </div>
      <div className="vr-lib-head"><span>Camera</span><span>Stream</span><span>Pixels</span><span>HFOV</span><span>Focus from</span><span>Source</span></div>
      <div className="vr-lib" role="listbox">
        {error && <div className="vr-num bad">{error}</div>}
        {!lib && !error && <div className="muted vr-lib-row">Loading the library…</div>}
        {rows.map((c, k) => (
          <button type="button" key={c.id} role="option" aria-selected={c.id === current} className={`vr-lib-row${c.id === current ? " on" : ""}${k === at ? " at" : ""}`}
            data-testid="camera-row" data-camera={c.id} onClick={() => onPick({ id: c.id })} onMouseEnter={() => setAt(k)}
            title={c.note + (c.derived ? ` · HFOV derived: ${c.derived}` : "")}>
            <b>{c.name}</b><span>{c.stream}</span><span>{c.resolution[0]}×{c.resolution[1]}</span>
            <span>{c.hfov_deg}°{c.derived ? "*" : ""}</span><span>{c.focus_mm ? fmtMm(c.focus_mm) : "—"}</span>
            <span className="vr-src">{c.sources.map((s, i) => (
              <a key={i} href={s.url} target="_blank" rel="noreferrer noopener" title={`${s.title} (accessed ${s.accessed})`} onClick={(e) => e.stopPropagation()}>[{i + 1}]</a>
            ))}</span>
          </button>
        ))}
        {lib && !rows.length && <div className="muted vr-lib-row">No camera matches “{q}”: use Custom below.</div>}
      </div>
      <div className={`vr-custom${current === "custom" ? " on" : ""}`} data-testid="camera-custom">
        <b>Custom</b>
        <NumberField value={custom.resolution[0]} unit="px" int min={16} step={10} path="verify.custom.w" title="sensor width"
          onCommit={(v) => setCustom((c) => ({ ...c, resolution: [v, c.resolution[1]] }))} />
        <span className="muted">×</span>
        <NumberField value={custom.resolution[1]} unit="px" int min={16} step={10} path="verify.custom.h" title="sensor height"
          onCommit={(v) => setCustom((c) => ({ ...c, resolution: [c.resolution[0], v] }))} />
        <NumberField value={custom.hfov_deg} unit="°" min={1} max={170} step={1} path="verify.custom.hfov" title="horizontal field of view"
          onCommit={(v) => setCustom((c) => ({ ...c, hfov_deg: v }))} />
        <NumberField value={custom.focus_mm} unit="mm" min={0} step={10} path="verify.custom.focus" title="the nearest it focuses at (optional)" placeholder="focus"
          onCommit={(v) => setCustom((c) => ({ ...c, focus_mm: v > 0 ? v : null }))} />
        <button type="button" className="vr-btn" data-testid="camera-custom-use" onClick={() => onPick({ custom })}>Use</button>
      </div>
      <div className="vr-lib-foot muted">From the makers' own documents (the numbers in brackets link them; * the HFOV is worked out from what the maker states: hover a row).</div>
    </div>
  );
}
