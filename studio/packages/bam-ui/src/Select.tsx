// A choice (base-ui Select): its options' icons and hints, optional groups
// (an option's `group`), a placeholder, a mixed state ("—" while several
// selected values differ). Test hooks: the root's data-path / data-value /
// data-open, the trigger's data-testid "dd:<path>", each option's
// data-value inside `.kit-select-popup[data-for=<path>]`.
import { Select as S } from "@base-ui/react/select";
import { useState, type ReactNode } from "react";
import { cn } from "./cn";
import { Glyph } from "./Glyph";

export interface Opt { value: string | number; label: string; icon?: string; hint?: string; group?: string; disabled?: boolean; badge?: ReactNode }

export function Select({ value, options, onChange, path, disabled, title, placeholder, mixed, wide, className, testid }: {
  value: string | number | null | undefined; options: Opt[]; onChange: (v: string | number) => void;
  path?: string; disabled?: boolean; title?: string; placeholder?: string; mixed?: boolean; wide?: boolean; className?: string; testid?: string;
}) {
  const [open, setOpen] = useState(false);
  const cur = mixed ? undefined : options.find((o) => String(o.value) === String(value));
  const groups: (string | undefined)[] = [];
  for (const o of options) if (!groups.includes(o.group)) groups.push(o.group);
  const item = (o: Opt) => (
    <S.Item key={String(o.value)} value={String(o.value)} disabled={o.disabled} className="kit-select-item" data-value={String(o.value)} title={o.hint}>
      {o.icon ? <Glyph name={o.icon} /> : <span className="ic" />}
      <S.ItemText className="kit-select-text">{o.label}</S.ItemText>
      {o.badge}
      <S.ItemIndicator className="kit-select-check">✓</S.ItemIndicator>
    </S.Item>
  );
  return (
    <div className={cn("kit-select", wide && "wide", className)} data-path={path} data-value={cur ? String(cur.value) : ""}
      data-open={open ? "1" : "0"} data-mixed={mixed ? "1" : undefined} data-testid={testid}>
      <S.Root value={cur ? String(cur.value) : null} disabled={disabled} modal={false} open={open}
        onOpenChange={(o) => setOpen(o)}
        onValueChange={(v) => {
          if (v === null || v === undefined) return;
          const o = options.find((x) => String(x.value) === String(v));
          if (o && (mixed || String(o.value) !== String(value))) onChange(o.value);
        }}>
        <S.Trigger className="kit-select-trigger" data-testid={path ? `dd:${path}` : undefined} title={title ?? cur?.hint ?? cur?.label}
          onKeyDown={(e) => {
            // a closed list never picks by typing: a tool's single-letter keys
            // (R, C, A ...) reach the tool, not this list (they bubble on)
            if (!open && e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey && e.key !== " ") {
              (e as unknown as { preventBaseUIHandler?: () => void }).preventBaseUIHandler?.();
            }
          }}>
          {cur?.icon && <Glyph name={cur.icon} />}
          <span className="kit-select-label" data-placeholder={cur ? undefined : "1"}>{cur ? cur.label : mixed ? "—" : (placeholder ?? "–")}</span>
          <S.Icon className="kit-select-chev">
            <svg viewBox="0 0 16 16" width="10" height="10" aria-hidden="true"><path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.6" /></svg>
          </S.Icon>
        </S.Trigger>
        <S.Portal>
          <S.Positioner className="kit-select-positioner" sideOffset={2} alignItemWithTrigger={false} align="start">
            <S.Popup className={cn("kit-select-popup", wide && "wide")} data-for={path} data-kit-popup="select">
              <S.List className="kit-select-list">
                {groups.map((g) => g === undefined ? options.filter((o) => o.group === undefined).map(item) : (
                  <S.Group key={g} className="kit-select-group">
                    <S.GroupLabel className="kit-select-group-label">{g}</S.GroupLabel>
                    {options.filter((o) => o.group === g).map(item)}
                  </S.Group>
                ))}
              </S.List>
            </S.Popup>
          </S.Positioner>
        </S.Portal>
      </S.Root>
    </div>
  );
}
