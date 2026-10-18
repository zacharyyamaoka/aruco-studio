// Suggest: one compact dropdown (Zach, 2026-10-18: "Suggestions should be in
// a drop down menu to be more compact"). Each option is its numbers
// ("3×1 @ 22.35 mm") and its reason; the reason wraps, so it is shown whole,
// never cut. Picking one sets those fields. base-ui's Select, as the kit's
// Select is, with option rows that may take two lines (the kit's are one).
import { Select as S } from "@base-ui/react/select";
import { useState } from "react";
import type { Suggestion } from "../core/contract";

export function SuggestSelect({ suggestions, current, empty, onPick }: {
  suggestions: Suggestion[];
  /** the option the feature's numbers match now, or -1 */
  current: number;
  /** the trigger's words while there is nothing to pick */
  empty: string;
  onPick: (s: Suggestion) => void;
}) {
  const [open, setOpen] = useState(false);
  const cur = current >= 0 ? suggestions[current] : undefined;
  return (
    <div className="kit-select sugg-select" data-path="marker.suggest" data-open={open ? "1" : "0"} data-count={suggestions.length}>
      <S.Root value={cur ? String(current) : null} disabled={!suggestions.length} modal={false} open={open} onOpenChange={setOpen}
        onValueChange={(v) => {
          const s = v === null || v === undefined ? undefined : suggestions[Number(v)];
          if (s) onPick(s);
        }}>
        <S.Trigger className="kit-select-trigger" data-testid="suggest-trigger" title={cur ? `${cur.label}: ${cur.reason}` : undefined}
          onKeyDown={(e) => {
            // as the kit's: a closed list never picks by typing; tool keys bubble on
            if (!open && e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey && e.key !== " ") {
              (e as unknown as { preventBaseUIHandler?: () => void }).preventBaseUIHandler?.();
            }
          }}>
          <span className="kit-select-label" data-placeholder={cur ? undefined : "1"}>
            {cur ? cur.label : suggestions.length ? `${suggestions.length} suggestion${suggestions.length === 1 ? "" : "s"}…` : empty}
          </span>
          <S.Icon className="kit-select-chev">
            <svg viewBox="0 0 16 16" width="10" height="10" aria-hidden="true"><path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.6" /></svg>
          </S.Icon>
        </S.Trigger>
        <S.Portal>
          <S.Positioner className="kit-select-positioner" sideOffset={2} alignItemWithTrigger={false} align="end">
            <S.Popup className="kit-select-popup sugg-popup" data-kit-popup="select" data-testid="suggestions">
              <S.List className="kit-select-list">
                {suggestions.map((s, i) => (
                  <S.Item key={i} value={String(i)} className="sugg-item" data-testid="suggestion" data-label={s.label} title={`${s.label}: ${s.reason}`}>
                    <S.ItemText className="sugg-label">{s.label}</S.ItemText>
                    <span className="sugg-reason" data-testid="suggestion-reason">{s.reason}</span>
                  </S.Item>
                ))}
              </S.List>
            </S.Popup>
          </S.Positioner>
        </S.Portal>
      </S.Root>
    </div>
  );
}
