// A text field: Enter or blur commits, Esc reverts.
import { useEffect, useState } from "react";
import { cn } from "./cn";

export function TextField({ value, onCommit, path, placeholder, disabled, mixed, className, autoFocus, testid }: {
  value: string; onCommit: (v: string) => void; path?: string; placeholder?: string; disabled?: boolean; mixed?: boolean;
  className?: string; autoFocus?: boolean; testid?: string;
}) {
  const shown = mixed ? "" : value;
  const [text, setText] = useState(shown);
  const [focus, setFocus] = useState(false);
  useEffect(() => { if (!focus) setText(shown); }, [shown, focus]);
  return (
    <input type="text" className={cn("kit-text txt", className)} value={text} data-path={path} placeholder={mixed ? "—" : placeholder}
      disabled={disabled} autoFocus={autoFocus} data-testid={testid}
      onFocus={() => setFocus(true)}
      onBlur={() => { setFocus(false); if (text !== shown && !(mixed && text === "")) onCommit(text); }}
      onChange={(e) => setText(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === "Enter") (e.target as HTMLInputElement).blur();
        if (e.key === "Escape") { setText(shown); (e.target as HTMLInputElement).blur(); }
        e.stopPropagation();
      }} />
  );
}
