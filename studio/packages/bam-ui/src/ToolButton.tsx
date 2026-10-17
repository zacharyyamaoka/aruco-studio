// A tool of a toolbar: its icon, its name in the tooltip, its key on a
// badge; lit while it is the active tool.
import type { ReactNode } from "react";
import { cn } from "./cn";

export function ToolButton({ icon, name, keys, active, onClick, testid, disabled }: {
  icon: ReactNode; name: string; keys: string; active?: boolean; onClick: () => void; testid?: string; disabled?: boolean;
}) {
  return (
    <button type="button" className={cn("kit-tool", active && "on")}
      title={`${name} (${keys})`} aria-label={name} aria-pressed={!!active} data-testid={testid} data-active={active ? "1" : "0"}
      disabled={disabled} onClick={onClick}>
      {icon}
      <span className="kit-badge" data-badge={keys}>{keys.replace("Shift+", "⇧")}</span>
    </button>
  );
}
