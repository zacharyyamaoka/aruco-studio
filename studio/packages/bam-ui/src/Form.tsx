// Form: renders a bam.form/1 field list (M8 4.3). Rows above the tabs
// (`tab: root`), the tabs that have a shown row, each tab's rows; each row's
// control by its type (a tool may give its own for some paths); every
// message under the row its key path names, or under its anchor while that
// row is hidden; one summary line. Several things at once: a value that
// differs between them shows "—" until it is typed.
import { useMemo, type ReactNode } from "react";
import { Messages, FieldRow } from "./Field";
import { NumberField } from "./NumberField";
import { Select, type Opt } from "./Select";
import { Switch } from "./Switch";
import { Tabs } from "./Tabs";
import { TextField } from "./TextField";
import { cn } from "./cn";
import { routeIssues, summaryLine, visibleRows, worst, type FormCtx, type FormRow, type FormTab, type Issue } from "./formModel";

export interface Cell { value: unknown; mixed: boolean }

export interface ControlArgs {
  row: FormRow; value: unknown; mixed: boolean; disabled: boolean;
  set: (v: unknown) => void; bad: (msg: string | null) => void;
}

export interface FormProps {
  rows: FormRow[];
  tabs: FormTab[];
  ctx: FormCtx;
  issues: Issue[];
  /** the tool's own rows that messages may anchor to (always drawn) */
  outside?: string[];
  tab: string;
  onTab: (id: string) => void;
  value: (path: string) => Cell;
  onChange: (path: string, value: unknown) => void;
  /** a control of the tool's own for a path (undefined: the type's) */
  control?: (a: ControlArgs) => ReactNode | undefined;
  /** a row's words (e.g. another word on a sticker) */
  labelOf?: (row: FormRow) => string;
  /** extra content by place: "root:before", "root:after", "<tab>:before", "<tab>:after"; given the routed messages */
  slots?: Record<string, (routed: Record<string, Issue[]>) => ReactNode>;
  disabled?: boolean;
  /** local refusals per path (text typed that is not a number, ...) */
  local?: Record<string, string | null>;
  onLocal?: (path: string, msg: string | null) => void;
  okText?: string;
  where?: (field: string) => string;
  extraErrors?: string[];
  className?: string;
}

const UNIT: Record<string, string> = { deg: "°", modules: "mod" };

function readOnly(row: FormRow, v: unknown): string {
  if (v === undefined || v === null) return row.type === "rule" || row.type === "object" ? "absent (rule 1)" : "–";
  if (typeof v === "object" && v && "rule" in (v as any)) return `rule ${(v as any).rule}`;
  if (row.type === "rule") return `rule ${String(v)}`;
  const c = row.choices?.find((x) => String(x.value) === String(v));
  return c ? c.label : typeof v === "object" ? JSON.stringify(v) : String(v);
}

/** The control a row's type gives. */
export function typeControl({ row, value, mixed, disabled, set, bad }: ControlArgs): ReactNode {
  const p = row.path;
  if (row.read_only || row.type === "rule") return <span className="ro" data-path={p}>{mixed ? "—" : readOnly(row, value)}</span>;
  switch (row.type) {
    case "choice": {
      const opts: Opt[] = (row.choices ?? []).map((c) => ({ value: c.value, label: c.label, icon: c.icon || undefined }));
      return <Select disabled={disabled} path={p} value={value as any} mixed={mixed} options={opts}
        onChange={(x) => set(typeof row.default === "number" ? Number(x) : x)} />;
    }
    case "bool":
      return <Switch disabled={disabled} path={p} value={Boolean(value)} mixed={mixed} onChange={(x) => set(x)} />;
    case "int":
      return <NumberField disabled={disabled} int path={p} value={value as number} mixed={mixed} onBad={bad} onCommit={(x) => set(x)} />;
    case "number":
    case "mm":
      return <NumberField disabled={disabled} path={p} value={value as number} mixed={mixed} step={row.step} onBad={bad}
        unit={row.unit ? (UNIT[row.unit] ?? row.unit) : undefined} onCommit={(x) => set(x)} />;
    case "text":
      return <TextField disabled={disabled} path={p} value={String(value ?? "")} mixed={mixed} onCommit={(x) => set(x)} />;
    default:
      return <span className="ro" data-path={p}>{mixed ? "—" : JSON.stringify(value)}</span>;
  }
}

export function Form(props: FormProps) {
  const { rows, tabs, ctx, issues, outside = [], tab, onTab, value, onChange, control, labelOf, slots = {}, disabled = false,
    local = {}, onLocal, okText = "Ready", where, extraErrors = [] } = props;
  const visible = useMemo(() => visibleRows(rows, ctx), [rows, ctx]);
  const shownPaths = useMemo(() => visible.filter((r) => r.tab !== "header").map((r) => r.path), [visible]);
  const routed = useMemo(() => routeIssues(issues, rows, shownPaths, outside), [issues, rows, shownPaths, outside]);
  const tabOf = (r: FormRow) => r.tab ?? "advanced";
  const tabRows = (t: string) => visible.filter((r) => tabOf(r) === t);
  const shownTabs = tabs.filter((t) => tabRows(t.id).length > 0 || slots[`${t.id}:before`] || slots[`${t.id}:after`]);
  const open = shownTabs.some((t) => t.id === tab) ? tab : (shownTabs[0]?.id ?? "");
  const level = (t: string) => worst(tabRows(t).flatMap((r) => routed[r.path] ?? []).filter((i) => i.level !== "info"));
  const tabName = (field: string) => {
    const r = rows.find((x) => x.path === field) ?? rows.find((x) => field.startsWith(x.path + "."));
    if (!r) return field === "tag" ? "Tag" : field;
    const t = tabs.find((x) => x.id === tabOf(r));
    return t ? `${labelOf ? labelOf(r) : r.label} (${t.name})` : (labelOf ? labelOf(r) : r.label);
  };
  const summary = summaryLine(issues, where ?? tabName, okText);
  const row = (r: FormRow) => {
    const cell = value(r.path);
    const args: ControlArgs = {
      row: r, value: cell.value, mixed: cell.mixed, disabled,
      set: (v) => onChange(r.path, v), bad: (m) => onLocal?.(r.path, m),
    };
    const c = control?.(args);
    const words = (labelOf ? labelOf(r) : r.label).replace(/ \(0 = Auto size\)$/, "").replace(/ \(a typed size\)$/, "");
    return (
      <FieldRow key={r.path} path={r.path} label={words} issues={routed[r.path] ?? []} local={local[r.path]}>
        {c === undefined ? typeControl(args) : c}
      </FieldRow>
    );
  };
  const general = routed["tag"] ?? [];
  return (
    <div className={cn("kit-form", props.className)} data-contract="bam.form/1">
      <fieldset className="ink kit-form-root" disabled={disabled} data-ink-locked={disabled ? "1" : "0"}>
        {slots["root:before"]?.(routed)}
        {tabRows("root").map(row)}
        {slots["root:after"]?.(routed)}
      </fieldset>
      {shownTabs.length > 0 && (
        <Tabs tabs={shownTabs.map((t) => ({ ...t, level: level(t.id) }))} value={open} onChange={onTab} />
      )}
      <fieldset className="ink tab-body" data-tab-body={open} disabled={disabled}>
        {slots[`${open}:before`]?.(routed)}
        {tabRows(open).map(row)}
        {slots[`${open}:after`]?.(routed)}
      </fieldset>
      {general.length > 0 && <Messages path="tag" issues={general} />}
      {extraErrors.length > 0 && (
        <div className="msgs" data-issues-for="errors">
          {extraErrors.map((e, i) => <div key={i} className="issue lv-error">{e}</div>)}
        </div>
      )}
      <div className={`summary lv-${summary.level}`} data-testid="summary">{summary.text}</div>
    </div>
  );
}
