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
// Keys: a valid value sets as you type (~120 ms after the last keystroke, as
// the label's text does); Enter commits (an edited value is set, even when it
// equals the driven one); Esc puts back the value from when the field was
// focused; an empty field + Enter returns it to driven.
//
// WHY live (Zach, 2026-10-20): "when I manually edit the dimensions, they
// should update in real time!" -- the panel's rows as the canvas dimensions.
// ArrowUp / ArrowDown step (Shift: ten); a drag on the unit scrubs. The kit
// (studio/packages/bam-ui) is not edited: this uses its classes and tokens.
import { useEffect, useRef, useState, type ReactNode } from "react";
import { cn, fmtNumber } from "@bam/ui";

const LIVE_MS = 120;

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
  const input = useRef<HTMLInputElement>(null);
  /** the value and its state when the field was focused (Esc), and whether a typed value went out since */
  const start = useRef<{ value: number | null | undefined; driven: boolean; sent: boolean }>({ value, driven, sent: false });
  const pending = useRef<ReturnType<typeof setTimeout> | null>(null);
  /** this render's props, for a commit from outside it (a press elsewhere) */
  const now = useRef({ onSet, onReset, driven, shown });
  now.current = { onSet, onReset, driven, shown };
  useEffect(() => { if (!focus) setText(shown); }, [shown, focus]);
  const s = step ?? (int ? 1 : 0.1);

  const ok = (v: number) => Number.isFinite(v) && !(int && !Number.isInteger(v)) && !(min !== undefined && v < min) && !(max !== undefined && v > max);
  const cancel = () => { if (pending.current) clearTimeout(pending.current); pending.current = null; };
  const commit = () => {
    cancel();
    if (skip.current) { skip.current = false; return; }
    const t = (input.current?.value ?? text).trim().replace(",", ".");
    const was = dirty.current;
    dirty.current = false;
    if (!was) return;
    const p = now.current;
    if (t === "") { if (!p.driven) p.onReset(); else setText(p.shown); return; }
    const v = Number(t);
    if (!ok(v)) { setText(p.shown); return; }   // never sent: the field shows what holds
    p.onSet(v);
  };
  // WHY commit on a press anywhere else, before it acts: a press on another
  // marker opens its panel first and the blur comes after, so a commit at the
  // blur (or a live one still waiting) would land on that marker instead
  useEffect(() => {
    if (!focus) return;
    const down = (e: PointerEvent) => { if (e.target !== input.current) commit(); };
    window.addEventListener("pointerdown", down, true);
    return () => window.removeEventListener("pointerdown", down, true);
  }, [focus]);
  useEffect(() => cancel, []);
  const stepBy = (n: number) => {
    const base = Number(text.replace(",", ".")) || Number(value) || 0;
    const v = +(Math.round((base + n * s) / s) * s).toFixed(6);
    if (!ok(v)) return;
    cancel();
    setText(fmtNumber(v, int));
    dirty.current = false;
    onSet(v);
  };

  return (
    <>
      <span className={cn("kit-num drv", driven ? "driven" : "set", bad && "bad")} data-driven={driven ? "1" : "0"} data-drv={path}
        title={tip(driven, driver)}>
        <input ref={input} type="text" inputMode="decimal" value={text} data-path={path} aria-label={path}
          onFocus={() => { start.current = { value, driven, sent: false }; setFocus(true); }}
          onBlur={() => { setFocus(false); commit(); }}
          onChange={(e) => {
            const t = e.target.value;
            dirty.current = true;
            setText(t);
            cancel();
            const v = Number(t.trim().replace(",", "."));
            if (t.trim() === "" || !ok(v)) return;
            // WHY the onSet of THIS render, as ui/TextArea.tsx does
            const to = onSet;
            pending.current = setTimeout(() => { pending.current = null; start.current.sent = true; to(v); }, LIVE_MS);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") (e.target as HTMLInputElement).blur();
            if (e.key === "Escape") {
              cancel();
              skip.current = true;
              dirty.current = false;
              const s0 = start.current;
              setText(fmtNumber(s0.value, int));
              // what went out while typing is taken back
              if (s0.sent) { if (s0.driven) onReset(); else if (s0.value != null) onSet(Number(s0.value)); }
              (e.target as HTMLInputElement).blur();
            }
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
