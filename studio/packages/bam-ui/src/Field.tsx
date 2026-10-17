// One row of a panel (24 px at the default density): a label and its
// controls, the messages under it; a section with a title.
import type { ReactNode } from "react";
import { cn } from "./cn";
import { Glyph } from "./Glyph";
import { shortText, worst, type Issue } from "./formModel";

/** A row's messages: one short line each (the whole text in its tooltip and
 *  data-text), the same line never twice. */
export function Messages({ path, issues, local }: { path: string; issues: Issue[]; local?: string | null }) {
  if (!issues.length && !local) return null;
  const seen = new Set<string>();
  const shown = issues.filter((i) => {
    const k = `${i.level}|${shortText(i.text)}`;
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
  return (
    <div className="msgs kit-msgs" data-issues-for={path}>
      {local && <div className="issue lv-error" data-level="error" data-local="1" data-text={local}>{local}</div>}
      {shown.map((i, k) => (
        <div key={k} className={`issue lv-${i.level}`} data-level={i.level} data-field={i.field} data-text={i.text}
          title={shortText(i.text) !== i.text ? i.text : undefined}>{shortText(i.text)}</div>
      ))}
    </div>
  );
}

export function FieldRow({ path, label, children, issues = [], local, icon, title, className, sub }: {
  path: string; label: ReactNode; children: ReactNode; issues?: Issue[]; local?: string | null; icon?: string; title?: string;
  className?: string; sub?: boolean;
}) {
  const lv = local ? "error" : worst(issues.filter((i) => i.level !== "info"));
  return (
    <div className={cn("row kit-field", lv && `has-${lv}`, className)} data-row={path}>
      <div className={cn("row-main kit-row", sub && "sub")}>
        <label className="row-label" title={title ?? path}>{icon && <Glyph name={icon} />}<span className="row-text">{label}</span></label>
        <div className="row-ctl">{children}</div>
      </div>
      <Messages path={path} issues={issues} local={local} />
    </div>
  );
}

/** A row with one message (the shape inspector's rows). */
export function Field({ label, children, path, msg, level }: {
  label: ReactNode; children: ReactNode; path: string; msg?: string | null; level?: "error" | "warn" | "info";
}) {
  return (
    <FieldRow path={path} label={label} issues={msg ? [{ field: path, level: level ?? "error", text: msg }] : []}>{children}</FieldRow>
  );
}

export function Section({ title, children, testid, right }: { title: ReactNode; children: ReactNode; testid?: string; right?: ReactNode }) {
  return (
    <section className="kit-section" data-testid={testid}>
      <div className="kit-section-head">{title}<span className="grow" />{right}</div>
      {children}
    </section>
  );
}
