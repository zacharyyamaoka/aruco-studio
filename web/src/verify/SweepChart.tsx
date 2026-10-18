// The angle sweep (Verify dialog): one line per marker, the share of its ids
// OpenCV found at each tilt of the bench, 0 → 85°. A column under the
// pointer sets the Tilt slider there (hover or click); a click on a point
// also picks that line's marker. The legend says how far each one reads.

export interface Series {
  id: string;
  name: string;
  /** the categorical slot (0-based), fixed per feature */
  slot: number;
  /** per tilt: the share found, null = not measured yet */
  shares: (number | null)[];
  readsTo: number | null | undefined;
}

const W = 316, H = 112, L = 30, R = 8, T = 8, B = 18;

export function SweepChart({ tilts, series, tilt, active, onTilt, onPick }: {
  tilts: number[]; series: Series[]; tilt: number; active: string | null;
  onTilt: (t: number) => void; onPick: (id: string, t: number) => void;
}) {
  const t1 = tilts[tilts.length - 1];
  const X = (t: number) => L + (t / t1) * (W - L - R);
  const Y = (s: number) => T + (1 - s) * (H - T - B);
  const step = tilts.length > 1 ? tilts[1] - tilts[0] : t1;
  // WHY a 1.5 px offset per line: markers that all read fully would draw one
  // on top of the other at "all"; the offset keeps each visible (the gallery's)
  const off = (i: number) => (i - (series.length - 1) / 2) * 1.5;
  const near = tilts.reduce((a, b) => (Math.abs(b - tilt) < Math.abs(a - tilt) ? b : a), tilts[0]);
  const at = tilts.indexOf(near);
  // the marker in the dialog draws its points last, on top: its own are the ones a click finds
  const top = series.map((_, i) => i).sort((a, b) => Number(series[a].id === active) - Number(series[b].id === active));
  return (
    <div className="vf-sweep">
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} data-testid="sweep-chart" role="img" aria-label="Share of ids read against tilt, per marker">
        <path className="vf-axis" d={`M${L} ${Y(1)}H${W - R}M${L} ${Y(0)}H${W - R}`} />
        <text className="vf-tick" x={L - 4} y={Y(1) + 3} textAnchor="end">all</text>
        <text className="vf-tick" x={L - 4} y={Y(0) + 3} textAnchor="end">none</text>
        {[0, 30, 60, t1].map((t) => <text key={t} className="vf-tick" x={X(t)} y={H - 4} textAnchor="middle">{t}°</text>)}
        <line className="vf-cursor" x1={X(Math.min(tilt, t1))} x2={X(Math.min(tilt, t1))} y1={T - 4} y2={Y(0)} />
        {series.map((s, i) => {
          const pts = s.shares.map((v, k) => (v === null ? null : [X(tilts[k]), Y(v) + off(i)] as const)).filter((p): p is readonly [number, number] => !!p);
          const d = pts.map(([x, y], k) => `${k ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join("");
          return (
            <g key={s.id} data-series={s.id} className={`vf-series s${s.slot % 8}${s.id === active ? " on" : ""}`}>
              <path className="vf-ring" d={d} />
              <path className="vf-line" d={d} />
            </g>
          );
        })}
        {tilts.map((t) => (
          <rect key={t} className="vf-col" data-tilt={t} x={X(t) - (X(step) - X(0)) / 2} y={0} width={X(step) - X(0)} height={Y(0)}
            onMouseEnter={() => onTilt(t)} onClick={() => onTilt(t)}>
            <title>{`${t}°`}</title>
          </rect>
        ))}
        {top.map((i) => {
          const s = series[i];
          return s.shares.map((v, k) => v === null ? null : (
            <circle key={`${s.id}-${k}`} className={`vf-pt s${s.slot % 8}${k === at ? " at" : ""}`} data-point={`${s.id}@${tilts[k]}`}
              cx={X(tilts[k])} cy={Y(v) + off(i)} r={k === at ? 4 : 2.5}
              onMouseEnter={() => onTilt(tilts[k])} onClick={() => onPick(s.id, tilts[k])}>
              <title>{`${s.name} at ${tilts[k]}°: ${Math.round(v * 100)} % of its ids`}</title>
            </circle>
          ));
        })}
      </svg>
      <div className="vf-readout muted" data-testid="sweep-readout">
        {near}°: {series.map((s) => `${s.name} ${s.shares[at] === null ? "…" : `${Math.round(s.shares[at]! * 100)} %`}`).join(" · ")}
      </div>
      <div className="vf-legend">
        {series.map((s) => (
          <button type="button" key={s.id} className={`vf-key s${s.slot % 8}${s.id === active ? " on" : ""}`} data-testid="sweep-legend" data-feature={s.id}
            data-reads-to={s.readsTo ?? ""} onClick={() => onPick(s.id, tilt)} title={`Verify ${s.name}`}>
            <span className="sw" />{s.name}: {s.readsTo === undefined ? "sweeping…" : s.readsTo === null ? "does not read head on" : `reads to ${s.readsTo}°`}
          </button>
        ))}
      </div>
    </div>
  );
}
