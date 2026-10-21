// A preset card's thumbnail: an inkjet's page with a marker on it, or a 3D
// printer's marker beside its lines. WHY React elements, not an SVG string
// (review finding #1, 2026-10-21): a preset's fields come from shared files,
// and a string put through dangerouslySetInnerHTML ran their markup.
import type { Preset } from "../core/contract";

const MARK = "M0 0h24v24H0zM4 4h5v5H4zM13 9h5v5h-5zM4 14h4v4H4z";
const finite = (v: unknown, or: number) => (typeof v === "number" && Number.isFinite(v) && v > 0 ? v : or);

export function Thumb({ p }: { p: Preset }) {
  const mk = <path fillRule="evenodd" fill="#111" d={MARK} />;
  if (p.method === "inkjet") {
    const w = finite(p.page_mm?.[0], 216), h = finite(p.page_mm?.[1], 279);
    const s = 76 / Math.max(w, h);
    return (
      <svg viewBox={`0 0 ${w * s + 4} ${h * s + 4}`} width={w * s + 4} height={h * s + 4}>
        <rect x="2" y="2" width={w * s} height={h * s} fill="#fff" stroke="#9aa3ae" />
        <g transform={`translate(${2 + (w * s) / 2 - 12} 12)`}>{mk}</g>
        <text x={2 + (w * s) / 2} y={h * s - 6} fontSize="8" textAnchor="middle" fill="#6b7480" fontFamily="sans-serif">{String(p.page ?? "")}</text>
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 96 80" width="96" height="80">
      <rect x="6" y="14" width="44" height="52" fill="#fff" />
      <g transform="translate(10 22) scale(1.5)">{mk}</g>
      <rect x="58" y="14" width="26" height="52" fill="none" stroke="#9aa3ae" />
      {Array.from({ length: 6 }, (_, i) => <path key={i} d={`M${60 + i * 4} 14v52`} stroke="#2f6fed" strokeWidth="1.2" />)}
      <text x="71" y="76" fontSize="7" textAnchor="middle" fill="#6b7480" fontFamily="sans-serif">{`${String(p.line_mm ?? "")} mm`}</text>
    </svg>
  );
}
