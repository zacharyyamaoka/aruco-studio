// A small pill: a kind (2D / 3D), a count, a state.
import type { ReactNode } from "react";
import { cn } from "./cn";

export function Badge({ children, tone = "neutral", title, testid, className }: {
  children: ReactNode; tone?: "neutral" | "accent" | "ok" | "warn" | "bad"; title?: string; testid?: string; className?: string;
}) {
  return <span className={cn("kit-pill", `t-${tone}`, className)} title={title} data-testid={testid}>{children}</span>;
}
