// A value that is either driven or set (the driven / driving pattern:
// Fusion's and SolidWorks' driven dimensions, Figma's Hug, Blender's driven
// fields). Driven: the ACTUAL value -- the core's, a rule's or the default --
// in muted grey, its driver in the tooltip; it follows its driver. Set: the
// typed value in normal text with a ↺ that returns it to driven; it never
// changes on its own, and goes red when the core flags it (`bad`).
//
// WHY (Zach, 2026-10-18): "instead of showing like auto, just show the actual
// value but make it kinda like grey outed that indicates that its like being
// driven as supposed to having been set". No Auto switch: typing sets.
//
// Keys: Enter commits (an edited value is set, even when it equals the driven
// one); Esc reverts the edit; an empty field + Enter returns it to driven.
// ArrowUp / ArrowDown step (Shift: ten); a drag on the unit scrubs. The kit
// (studio/packages/bam-ui) is not edited: this uses its classes and tokens.
import { useEffect, useRef, useState, type ReactNode } from "react";
import { cn, fmtNumber } from "@bam/ui";

/** The ↺ beside a set value. Its space is kept while driven, so rows line up. */
function ResetButton({ path, driven, driver, onReset }: { path: string; driven: boolean; driver: string; onReset: () => void }) {
  return (
    <button type="button" className="kit-ib drv-reset" data-reset={path} title={`Back to driven: ${driver}`}
      aria-label={`Reset ${path} to driven`} aria-hidden={driven} tabIndex={driven ? -1 : 0}
      style={driven ? { visibility: "hidden" } : undefined} onClick={onReset}>↺</button>
  );
}

const tip = (driven: boolean, driver: string) =>
  driven ? `Driven: ${driver}. Type a value to set it.` : `Set by hand. Empty + Enter or ↺: back to driven (${driver}).`;

export function DrivenField({ path, value, driven, driver, onSet, onReset, unit, int, min, max, step, bad }: {
  path: string;
  /** the value shown: the actual one, driven or set */
  value: number | null | undefined;
  driven: boolean;
  /** what drives it, for the tooltip: "fills the rectangle", "core rule: …", "default" */
  driver: string;
  onSet: (v: number) => void;
  onReset: () => void;
  unit?: string; int?: boolean; min?: number; max?: number; step?: number;
  /** the core flags this value (red) */
  bad?: boolean;
}) {
  const shown = fmtNumber(value, int);
  const [text, setText] = useState(shown);
  const [focus, setFocus] = useState(false);
  const dirty = useRef(false);
  const skip = useRef(false);
  const scrub = useRef<{ x: number; v: number; last: number } | null>(null);
  useEffect(() => { if (!focus) setText(shown); }, [shown, focus]);
  const s = step ?? (int ? 1 : 0.1);

  const ok = (v: number) => Number.isFinite(v) && !(int && !Number.isInteger(v)) && !(min !== undefined && v < min) && !(max !== undefined && v > max);
  const commit = () => {
    if (skip.current) { skip.current = false; return; }
    const t = text.trim().replace(",", ".");
    const was = dirty.current;
    dirty.current = false;
    if (!was) return;
    if (t === "") { if (!driven) onReset(); else setText(shown); return; }
    const v = Number(t);
    if (!ok(v)) { setText(shown); return; }   // never sent: the field shows what holds
    onSet(v);
  };
  const stepBy = (n: number) => {
    const base = Number(text.replace(",", ".")) || Number(value) || 0;
    const v = +(Math.round((base + n * s) / s) * s).toFixed(6);
    if (!ok(v)) return;
    setText(fmtNumber(v, int));
    dirty.current = false;
    onSet(v);
  };

  return (
    <>
      <span className={cn("kit-num drv", driven ? "driven" : "set", bad && "bad")} data-driven={driven ? "1" : "0"} data-drv={path}
        title={tip(driven, driver)}>
        <input type="text" inputMode="decimal" value={text} data-path={path} aria-label={path}
          onFocus={() => setFocus(true)}
          onBlur={() => { setFocus(false); commit(); }}
          onChange={(e) => { dirty.current = true; setText(e.target.value); }}
          onKeyDown={(e) => {
            if (e.key === "Enter") (e.target as HTMLInputElement).blur();
            if (e.key === "Escape") { skip.current = true; dirty.current = false; setText(shown); (e.target as HTMLInputElement).blur(); }
            if (e.key === "ArrowUp" || e.key === "ArrowDown") { e.preventDefault(); stepBy((e.key === "ArrowUp" ? 1 : -1) * (e.shiftKey ? 10 : 1)); }
            e.stopPropagation();
          }} />
        {unit && (
          <span className="unit" title={`drag to change in ${s} ${unit} steps`}
            onPointerDown={(e) => {
              (e.target as Element).setPointerCapture?.(e.pointerId);
              scrub.current = { x: e.clientX, v: Number(value) || 0, last: Number(value) || 0 };
            }}
            onPointerMove={(e) => {
              const sc = scrub.current;
              if (!sc) return;
              const v = +(Math.round((sc.v + Math.round((e.clientX - sc.x) / 4) * s) / s) * s).toFixed(6);
              if (v !== sc.last && ok(v)) { sc.last = v; setText(fmtNumber(v, int)); }
            }}
            onPointerUp={() => {
              const sc = scrub.current;
              scrub.current = null;
              if (sc && sc.last !== sc.v) onSet(sc.last);
            }}>{unit}</span>
        )}
      </span>
      <ResetButton path={path} driven={driven} driver={driver} onReset={onReset} />
    </>
  );
}

/** A choice (segmented row, select, switch) that is driven or set: the
 *  control is muted while driven. Picking the lit option of a driven choice
 *  sets it (the kit's segmented row ignores a click on its lit option). */
export function DrivenChoice({ path, value, driven, driver, onSet, onReset, children }: {
  path: string; value: string | number | boolean; driven: boolean; driver: string;
  onSet: (v: string | number | boolean) => void; onReset: () => void; children: ReactNode;
}) {
  return (
    <>
      <span className={cn("drv-choice", driven ? "driven" : "set")} data-driven={driven ? "1" : "0"} data-drv={path} title={tip(driven, driver)}
        onClickCapture={(e) => {
          const b = (e.target as Element).closest?.(".kit-seg-btn[data-value]");
          if (driven && b && b.getAttribute("data-value") === String(value)) onSet(value);
        }}>
        {children}
      </span>
      <ResetButton path={path} driven={driven} driver={driver} onReset={onReset} />
    </>
  );
}
