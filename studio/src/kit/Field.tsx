// One row of a panel: a label and its controls, a message slot under it.
import type { ReactNode } from "react";
import { cn } from "./cn";

export function Field({ label, children, path, msg, level }: {
  label: ReactNode; children: ReactNode; path: string; msg?: string | null; level?: "error" | "warn" | "info";
}) {
  return (
    <div className={cn("row kit-field", level && `has-${level}`)} data-row={path}>
      <div className="row-main">
        <label className="row-label">{label}</label>
        <div className="row-ctl">{children}</div>
      </div>
      {msg && <div className="msgs" data-issues-for={path}><div className={`issue lv-${level ?? "error"}`} data-level={level ?? "error"}>{msg}</div></div>}
    </div>
  );
}

export function Section({ title, children, testid, right }: { title: ReactNode; children: ReactNode; testid?: string; right?: ReactNode }) {
  return (
    <section className="kit-section" data-testid={testid}>
      <div className="kit-section-head flex items-center gap-1.5">{title}<span className="grow" />{right}</div>
      {children}
    </section>
  );
}
