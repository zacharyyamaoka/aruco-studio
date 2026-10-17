// Buttons: a text button (default / primary / ghost) and an icon button.
import type { ReactNode } from "react";
import { cn } from "./cn";
import { Glyph } from "./Glyph";

export function Button({ children, onClick, variant = "default", size = "md", disabled, testid, title, icon, className, type = "button" }: {
  children?: ReactNode; onClick?: () => void; variant?: "default" | "primary" | "ghost" | "danger"; size?: "sm" | "md";
  disabled?: boolean; testid?: string; title?: string; icon?: ReactNode; className?: string; type?: "button" | "submit";
}) {
  return (
    <button type={type} className={cn("kit-btn", `v-${variant}`, `s-${size}`, className)} onClick={onClick} disabled={disabled}
      data-testid={testid} title={title}>
      {typeof icon === "string" ? <Glyph name={icon} /> : icon}{children}
    </button>
  );
}

export function IconButton({ icon, title, onClick, active, disabled, testid, children, className }: {
  icon: ReactNode; title: string; onClick: () => void; active?: boolean; disabled?: boolean; testid?: string; children?: ReactNode; className?: string;
}) {
  return (
    <button type="button" className={cn("kit-ib", active && "on", className)} title={title} aria-label={title}
      aria-pressed={active ?? undefined} disabled={disabled} data-testid={testid} onClick={onClick}>
      {typeof icon === "string" ? <Glyph name={icon} /> : icon}{children}
    </button>
  );
}
