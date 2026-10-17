// An on / off switch (base-ui Switch). Test hooks: the root's data-path and
// role="switch" (aria-checked); `mixed` shows a half state until clicked.
import { Switch as S } from "@base-ui/react/switch";
import { cn } from "./cn";

export function Switch({ value, onChange, path, label, disabled, mixed, title }: {
  value: boolean; onChange: (v: boolean) => void; path?: string; label?: string; disabled?: boolean; mixed?: boolean; title?: string;
}) {
  return (
    <label className={cn("kit-switch", value && !mixed && "on", disabled && "dis", mixed && "mixed")} title={title}>
      <S.Root checked={mixed ? false : value} disabled={disabled} onCheckedChange={(c) => onChange(mixed ? true : c)}
        className="kit-switch-root" data-path={path} data-mixed={mixed ? "1" : undefined}>
        <S.Thumb className="kit-switch-thumb" />
      </S.Root>
      {label && <span className="kit-switch-label">{label}</span>}
    </label>
  );
}
