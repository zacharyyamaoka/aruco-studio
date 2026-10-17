// A number field: typed text, Enter commits, Esc reverts, blur commits; a
// unit; text that is not a number is never sent (it says so).
import { useEffect, useState } from "react";
import { cn } from "./cn";

export function NumberField({ value, onCommit, path, unit, disabled, step, min, label, onBad }: {
  value: number | null | undefined; onCommit: (v: number) => void; path?: string; unit?: string;
  disabled?: boolean; step?: number; min?: number; label?: string; onBad?: (msg: string | null) => void;
}) {
  const shown = value === null || value === undefined || Number.isNaN(value) ? "" : String(+Number(value).toFixed(4));
  const [text, setText] = useState(shown);
  const [focus, setFocus] = useState(false);
  useEffect(() => { if (!focus) setText(shown); }, [shown, focus]);
  const commit = () => {
    const t = text.trim().replace(",", ".");
    if (t === shown) { onBad?.(null); return; }
    const v = Number(t);
    if (t === "" || !Number.isFinite(v)) { onBad?.(`'${text}' is not a number`); return; }
    if (min !== undefined && v < min) { onBad?.(`${v}: ${min} or more`); return; }
    onBad?.(null);
    onCommit(step ? Math.round(v / step) * step : v);
  };
  return (
    <span className={cn("kit-num num inline-flex items-center", disabled && "dis")} title={label}>
      {label && <span className="kit-num-label">{label}</span>}
      <input type="text" inputMode="decimal" value={text} disabled={disabled} data-path={path}
        onFocus={() => setFocus(true)}
        onBlur={() => { setFocus(false); commit(); }}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") (e.target as HTMLInputElement).blur();
          if (e.key === "Escape") { setText(shown); onBad?.(null); (e.target as HTMLInputElement).blur(); }
          e.stopPropagation();
        }} />
      {unit && <span className="unit">{unit}</span>}
    </span>
  );
}
