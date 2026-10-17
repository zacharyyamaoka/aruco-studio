// A row of buttons for one choice (Origin's four turns, All · 3D · 2D): one
// lit; icons or words.
import { cn } from "./cn";
import { Glyph } from "./Glyph";
import type { Opt } from "./Select";

export function SegmentedRow({ value, options, onChange, path, disabled, mixed, testid, compact }: {
  value: string | number | null | undefined; options: Opt[]; onChange: (v: string | number) => void; path?: string;
  disabled?: boolean; mixed?: boolean; testid?: string; compact?: boolean;
}) {
  return (
    <div className={cn("kit-seg", compact && "compact")} role="radiogroup" data-path={path} data-value={mixed ? "" : String(value ?? "")} data-testid={testid}>
      {options.map((o) => {
        const on = !mixed && String(o.value) === String(value);
        return (
          <button type="button" key={String(o.value)} role="radio" aria-checked={on} className={cn("kit-seg-btn", on && "on", !o.icon && "words")}
            title={o.hint ?? o.label} aria-label={o.hint ?? o.label} data-value={String(o.value)} disabled={disabled || o.disabled}
            onClick={() => (mixed || !on) && onChange(o.value)}>
            {o.icon ? <Glyph name={o.icon} /> : o.label}
          </button>
        );
      })}
    </div>
  );
}
