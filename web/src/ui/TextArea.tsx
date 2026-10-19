// A multi-line text field (the label's text: "\n" breaks lines, contract
// LabelParams.text). Enter adds a line; every edit commits ~120 ms after the
// last keystroke, so the sketch follows as you type; Esc reverts to the text
// from when the field was focused. The kit's TextField is one line, so this
// is here, in its classes and tokens.
//
// WHY live (Zach, 2026-10-18): "As you type in the text please make it update
// in realtime on the drawing."
import { useEffect, useRef, useState } from "react";
import { cn } from "@bam/ui";

const LIVE_MS = 120;

export function TextArea({ value, onCommit, path, placeholder, rows = 2, testid, className }: {
  value: string; onCommit: (v: string) => void; path?: string; placeholder?: string; rows?: number; testid?: string; className?: string;
}) {
  const [text, setText] = useState(value);
  const [focus, setFocus] = useState(false);
  const start = useRef(value);
  const pending = useRef<{ t: ReturnType<typeof setTimeout>; v: string } | null>(null);
  const commit = useRef(onCommit);
  commit.current = onCommit;
  const cancel = () => { if (pending.current) clearTimeout(pending.current.t); pending.current = null; };
  /** commit what is waiting now (leaving the field) */
  const flush = () => { const p = pending.current; cancel(); if (p) commit.current(p.v); };
  useEffect(() => { if (!focus) setText(value); }, [value, focus]);
  useEffect(() => flush, []);
  return (
    <textarea className={cn("kit-text txt kit-textarea", className)} value={text} data-path={path} placeholder={placeholder} rows={rows}
      data-testid={testid} aria-label={path} spellCheck={false}
      onFocus={() => { start.current = value; setFocus(true); }}
      onBlur={() => { flush(); setFocus(false); }}
      onChange={(e) => {
        const v = e.target.value;
        setText(v);
        cancel();
        pending.current = { t: setTimeout(() => { pending.current = null; commit.current(v); }, LIVE_MS), v };
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) (e.target as HTMLTextAreaElement).blur();
        if (e.key === "Escape") {
          cancel();
          setText(start.current);
          if (start.current !== value) commit.current(start.current);
          (e.target as HTMLTextAreaElement).blur();
        }
        e.stopPropagation();
      }} />
  );
}
