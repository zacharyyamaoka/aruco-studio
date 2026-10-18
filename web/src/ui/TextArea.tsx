// A multi-line text field (the label's text: "\n" breaks lines, contract
// LabelParams.text). Enter adds a line; blur or Ctrl / Cmd + Enter commits;
// Esc reverts. The kit's TextField is one line, so this is here, in its
// classes and tokens.
import { useEffect, useRef, useState } from "react";
import { cn } from "@bam/ui";

export function TextArea({ value, onCommit, path, placeholder, rows = 2, testid, className }: {
  value: string; onCommit: (v: string) => void; path?: string; placeholder?: string; rows?: number; testid?: string; className?: string;
}) {
  const [text, setText] = useState(value);
  const [focus, setFocus] = useState(false);
  const skip = useRef(false);
  useEffect(() => { if (!focus) setText(value); }, [value, focus]);
  return (
    <textarea className={cn("kit-text txt kit-textarea", className)} value={text} data-path={path} placeholder={placeholder} rows={rows}
      data-testid={testid} aria-label={path} spellCheck={false}
      onFocus={() => setFocus(true)}
      onBlur={() => {
        setFocus(false);
        if (skip.current) { skip.current = false; return; }
        if (text !== value) onCommit(text);
      }}
      onChange={(e) => setText(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) (e.target as HTMLTextAreaElement).blur();
        if (e.key === "Escape") { skip.current = true; setText(value); (e.target as HTMLTextAreaElement).blur(); }
        e.stopPropagation();
      }} />
  );
}
