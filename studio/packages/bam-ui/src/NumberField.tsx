// A number field (M8 4.2): typed text, Enter commits, Esc reverts, blur
// commits; a unit; ArrowUp / ArrowDown step it (Shift: ten steps); a drag
// on its unit scrubs it in steps. Text that is not a number is never sent:
// it says so through onBad. `mixed`: several values differ ("—" until typed).
import { useEffect, useRef, useState } from "react";
import { cn } from "./cn";

export function fmtNumber(v: number | null | undefined, int?: boolean): string {
  return v === null || v === undefined || Number.isNaN(v) ? "" : String(+Number(v).toFixed(int ? 0 : 4));
}

export function NumberField({ value, onCommit, path, unit, disabled, int, step, min, max, placeholder, onBad, label, mixed, title, className }: {
  value: number | null | undefined; onCommit: (v: number) => void; path?: string; unit?: string; disabled?: boolean;
  int?: boolean; step?: number; min?: number; max?: number; placeholder?: string; onBad?: (msg: string | null) => void;
  label?: string; mixed?: boolean; title?: string; className?: string;
}) {
  const shown = mixed ? "" : fmtNumber(value, int);
  const [text, setText] = useState(shown);
  const [focus, setFocus] = useState(false);
  const scrub = useRef<{ x: number; v: number; last: number } | null>(null);
  useEffect(() => { if (!focus) setText(shown); }, [shown, focus]);
  const s = step ?? (int ? 1 : 0.1);
  const check = (v: number): string | null => {
    if (int && !Number.isInteger(v)) return `'${v}' is not a whole number`;
    if (min !== undefined && v < min) return `${v}: ${min} or more`;
    if (max !== undefined && v > max) return `${v}: ${max} or less`;
    return null;
  };
  const send = (v: number) => {
    const bad = check(v);
    if (bad) { onBad?.(bad); return; }
    onBad?.(null);
    onCommit(v);
  };
  const commit = () => {
    const t = text.trim().replace(",", ".");
    if (t === shown) { onBad?.(null); return; }
    if (mixed && t === "") { onBad?.(null); return; }
    const v = Number(t);
    if (t === "" || !Number.isFinite(v)) { onBad?.(`'${text}' is not a number`); return; }
    send(v);
  };
  const stepBy = (n: number) => {
    const base = Number(text.replace(",", ".")) || Number(value) || 0;
    const v = +(Math.round((base + n * s) / s) * s).toFixed(6);
    setText(fmtNumber(v, int));
    send(v);
  };
  return (
    <span className={cn("kit-num", disabled && "dis", mixed && "mixed", className)} title={title ?? label} data-mixed={mixed ? "1" : undefined}>
      {label && <span className="kit-num-label">{label}</span>}
      <input type="text" inputMode="decimal" value={text} disabled={disabled} data-path={path}
        placeholder={mixed ? "—" : placeholder}
        onFocus={() => setFocus(true)}
        onBlur={() => { setFocus(false); commit(); }}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") (e.target as HTMLInputElement).blur();
          if (e.key === "Escape") { setText(shown); onBad?.(null); (e.target as HTMLInputElement).blur(); }
          if (e.key === "ArrowUp" || e.key === "ArrowDown") { e.preventDefault(); stepBy((e.key === "ArrowUp" ? 1 : -1) * (e.shiftKey ? 10 : 1)); }
          e.stopPropagation();
        }} />
      {unit && (
        <span className="unit" title={disabled ? undefined : `drag to change in ${s} ${unit} steps`}
          onPointerDown={(e) => {
            if (disabled) return;
            (e.target as Element).setPointerCapture?.(e.pointerId);
            scrub.current = { x: e.clientX, v: Number(value) || 0, last: Number(value) || 0 };
          }}
          onPointerMove={(e) => {
            const sc = scrub.current;
            if (!sc) return;
            const n = Math.round((e.clientX - sc.x) / 4);
            const v = +(Math.round((sc.v + n * s) / s) * s).toFixed(6);
            if (v !== sc.last) { sc.last = v; setText(fmtNumber(v, int)); }
          }}
          onPointerUp={() => {
            const sc = scrub.current;
            scrub.current = null;
            if (sc && sc.last !== sc.v) send(sc.last);
          }}>{unit}</span>
      )}
    </span>
  );
}
