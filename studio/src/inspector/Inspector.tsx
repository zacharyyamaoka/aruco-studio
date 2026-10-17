// The inspector of the selection. Built from /api/form (never a hand-written
// field list): every field's row, its control by type, and right under it
// the Issues the plan gives on that key path; one summary line is always
// shown. Tabs Marker · Heights · Print · Label · Advanced (REF's dialog v2).
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "../api/client";
import type { FormField, Issue, SceneTag } from "../api/types";
import { getPath, idsText, routeIssues, summaryLine, worst } from "../model/scene";
import { useStudio } from "../store";
import { ButtonRow, Dropdown, Icon, IconButton, NumberInput, TextInput, Toggle, type Opt } from "../ui/controls";
import { ICONS_OF, shown, TABS, TARGET_EDITOR, tabOf, turnIcons, type Tab } from "./layout";
import { PresetRow } from "./PresetRow";
import { TargetEditor } from "./TargetEditor";

function Msgs({ path, issues, local }: { path: string; issues: Issue[]; local?: string | null }) {
  if (!issues.length && !local) return null;
  return (
    <div className="msgs" data-issues-for={path}>
      {local && <div className="issue lv-error" data-level="error" data-local="1">{local}</div>}
      {issues.map((i, k) => (
        <div key={k} className={`issue lv-${i.level}`} data-level={i.level} data-field={i.field}>{i.text}</div>
      ))}
    </div>
  );
}

function Row({ f, label, children, issues, local, icon }: {
  f: { path: string }; label: ReactNode; children: ReactNode; issues: Issue[]; local?: string | null; icon?: string;
}) {
  const lv = worst(issues.filter((i) => i.level !== "info"));
  return (
    <div className={`row${lv ? " has-" + lv : ""}`} data-row={f.path}>
      <div className="row-main">
        <label className="row-label" title={f.path}>{icon && <Icon name={icon} />}{label}</label>
        <div className="row-ctl">{children}</div>
      </div>
      <Msgs path={f.path} issues={issues} local={local} />
    </div>
  );
}

const pathOf = (f: FormField) => f.path;
/** A row's label without what its control already says ("(0 = Auto size)"). */
const short = (label: string) => label.replace(/ \(0 = Auto size\)$/, "").replace(/ \(a typed size\)$/, "");

export function Inspector() {
  const form = useStudio((s) => s.form);
  const options = useStudio((s) => s.options);
  const scene = useStudio((s) => s.scene);
  const sel = useStudio((s) => s.sel);
  const [tab, setTab] = useState<Tab>("marker");
  const tags = scene.tags.filter((t) => sel.includes(t.name));
  const tag: SceneTag | undefined = tags[tags.length - 1];

  if (!form) return <aside className="inspector"><div className="muted pad">Loading…</div></aside>;
  if (!tag) return <aside className="inspector" data-testid="inspector"><NewTagDefaults /></aside>;
  return <TagInspector key={tag.uid} tag={tag} count={tags.length} form={form.fields} options={options} tab={tab} setTab={setTab} />;
}

function TagInspector({ tag, count, form, options, tab, setTab }: {
  tag: SceneTag; count: number; form: FormField[]; options: Record<string, any> | null; tab: Tab; setTab: (t: Tab) => void;
}) {
  const st = useStudio.getState();
  const s = tag.spec.settings as Record<string, any>;
  const n = tag.spec.numbers as Record<string, any>;
  const plan = tag.plan;
  const issues: Issue[] = (plan?.warnings as Issue[]) ?? [];
  const [bad, setBad] = useState<Record<string, string | null>>({});
  const fields = useMemo(() => form.filter((f) => !TARGET_EDITOR.has(f.path)), [form]);
  const visible = fields.filter((f) => shown(f, s, n));
  const routed = useMemo(() => routeIssues(issues, [...visible.map(pathOf), "target"]), [issues, visible]);
  const layout = String(s.layout ?? "single");
  const labelOf = (field: string) => {
    const f = form.find((x) => x.path === field) ?? form.find((x) => field.startsWith(x.path + "."));
    if (!f) return field === "tag" ? "Tag" : field;
    const t = tabOf(f);
    return t === "root" ? f.label : `${f.label} (${TABS.find((x) => x.id === t)!.name})`;
  };
  const summary = summaryLine(issues, labelOf, plan?.ok ? "Ready: the plan is built" : "Not built");
  const tabWorst = (t: Tab) => worst(visible.filter((f) => tabOf(f) === t).flatMap((f) => routed[f.path] ?? []).filter((i) => i.level !== "info"));
  const edit = (path: string, v: unknown, extra?: Record<string, unknown>) => st.edit(path, v, extra);
  const setLocal = (path: string) => (m: string | null) => setBad((b) => ({ ...b, [path]: m }));

  const control = (f: FormField): ReactNode => {
    const v = getPath(tag.spec, f.path);
    const p = f.path;
    if (f.read_only || f.type === "rule") {
      return <span className="ro" data-path={p}>{v === undefined || v === null ? `absent (rule 1)` : `rule ${String(v)}`}</span>;
    }
    if (p === "numbers.size" || p === "numbers.square") {
      const auto = !Number(v);
      const built = p === "numbers.size" ? Number((plan?.marker as any)?.marker_length_m || 0) * 1000
        : Number((plan?.marker as any)?.square_length_m || 0) * 1000;
      return (
        <span className="pair">
          <Toggle value={auto} label="Auto" path={`${p}:auto`}
            onChange={(a) => edit(p, a ? 0 : +(built || 20).toFixed(2), { "settings.size_auto": a, ...(a ? { "settings.force": null } : {}) })} />
          <NumberInput value={auto ? (built || null) : Number(v)} path={p} unit="mm" disabled={auto} onBad={setLocal(p)}
            onCommit={(x) => edit(p, x, { "settings.size_auto": x === 0 })} />
        </span>
      );
    }
    if (p === "settings.force") {
      const cur = (v as number[] | null) ?? null;
      const m = plan?.marker as any;
      const cols = cur?.[0] ?? m?.cols ?? 1, rows = cur?.[1] ?? m?.rows ?? 1;
      return (
        <span className="pair">
          <NumberInput int value={cols} path={`${p}[0]`} onBad={setLocal(p)} onCommit={(x) => edit(p, [x, rows])} />
          <span className="x">×</span>
          <NumberInput int value={rows} path={`${p}[1]`} onBad={setLocal(p)} onCommit={(x) => edit(p, [cols, x])} />
          {cur && <IconButton icon="close" title="Back to the fit's count" onClick={() => edit(p, null)} />}
        </span>
      );
    }
    if (p === "settings.turn") {
      const icons = turnIcons(layout);
      const opts: Opt[] = (options?.origin?.[layout] ?? f.choices ?? []).map((c: any) => ({ value: c.value, label: c.label, hint: c.label, icon: icons[String(c.value)] }));
      return <ButtonRow path={p} value={Number(v ?? 0)} options={opts} onChange={(x) => edit(p, Number(x))} />;
    }
    if (p === "settings.cells") return <CellsEditor value={v as any} f={f} onChange={(x) => edit(p, x)} onBad={setLocal(p)} />;
    if (p === "settings.trim") {
      const cur = v as any;
      const opts: Opt[] = (options?.trim ?? [{ value: "off", label: "Off" }]).map((c: any) => ({ value: c.value, label: c.label }));
      return (
        <span className="pair">
          <Dropdown path={p} value={cur && cur.rule === 1 ? cur.axes : "off"} options={opts}
            onChange={(x) => edit(p, x === "off" ? null : { rule: 1, axes: x, margin_mm: cur?.margin_mm ?? 0, force: Boolean(cur?.force) })} />
          {cur && cur.rule === 1 && <Toggle value={Boolean(cur.force)} label="Cut anyway" path={`${p}.force`} onChange={(x) => edit(p, { ...cur, force: x })} />}
        </span>
      );
    }
    switch (f.type) {
      case "choice": {
        const icons = ICONS_OF[p] ?? {};
        const opts: Opt[] = (f.choices ?? []).map((c) => ({ value: c.value, label: c.label, icon: icons[String(c.value)] }));
        return <Dropdown path={p} value={v as any} options={opts} onChange={(x) => edit(p, typeof f.default === "number" ? Number(x) : x)} />;
      }
      case "bool":
        return <Toggle path={p} value={Boolean(v)} onChange={(x) => edit(p, x)} />;
      case "int":
        return <NumberInput int path={p} value={v as number} onBad={setLocal(p)} onCommit={(x) => edit(p, x)} />;
      case "number":
        return <NumberInput path={p} value={v as number} onBad={setLocal(p)} onCommit={(x) => edit(p, x)} />;
      case "mm":
        return <NumberInput path={p} value={v as number} unit="mm" onBad={setLocal(p)} onCommit={(x) => edit(p, x)} />;
      case "text":
        return <TextInput path={p} value={String(v ?? "")} onCommit={(x) => edit(p, x)} />;
      default:
        return <span className="ro" data-path={p}>{JSON.stringify(v)}</span>;
    }
  };

  const rows = (t: Tab | "root") => visible.filter((f) => tabOf(f) === t).map((f) => (
    <Row key={f.path} f={f} label={short(f.label)} issues={routed[f.path] ?? []} local={bad[f.path]}>{control(f)}</Row>
  ));
  const general = routed["tag"] ?? [];
  const m = plan?.marker as any;

  return (
    <aside className="inspector" data-testid="inspector" data-tag={tag.name}>
      <div className="insp-head">
        <Icon name={layout} />
        <TextInput value={tag.name} path="name" onCommit={(x) => st.rename(tag.name, x)} />
        <span className="ids" data-testid="insp-ids" title="the ids this tag prints">#{idsText(plan?.ids ?? [])}</span>
        <IconButton icon={tag.locked ? "lock" : "unlock"} title={tag.locked ? "Locked: a printed tag (its ink cannot change)" : "Lock: mark as printed"}
          active={tag.locked} onClick={() => st.setFlag(tag.name, "locked", !tag.locked)} testid="lock" />
        <IconButton icon={tag.hidden ? "eyeoff" : "eye"} title={tag.hidden ? "Hidden" : "Hide"} onClick={() => st.setFlag(tag.name, "hidden", !tag.hidden)} />
      </div>
      {count > 1 && <div className="multi">{count} tags selected: a change goes to every one of them.</div>}
      <div className="insp-sub muted">
        {m ? `${m.dictionary} · ${m.layout === "single" ? `${(m.marker_length_m * 1000).toFixed(2)} mm` : `${m.cols} × ${m.rows}, marker ${(m.marker_length_m * 1000).toFixed(2)} mm`}` : "not built"}
      </div>
      <PresetRow tag={tag} />
      <TargetEditor tag={tag} issues={routed["target"] ?? []} />
      {rows("root")}
      <div className="tabs" role="tablist">
        {TABS.map((t) => {
          const w = tabWorst(t.id);
          return (
            <button key={t.id} role="tab" type="button" aria-selected={tab === t.id} data-tab={t.id}
              className={`tab${tab === t.id ? " on" : ""}${w ? " has-" + w : ""}`} onClick={() => setTab(t.id)} title={t.name}>
              <Icon name={t.icon} /><span>{t.name}</span>{w && <i className="dot" />}
            </button>
          );
        })}
      </div>
      <div className="tab-body" data-tab-body={tab}>
        {tab === "marker" && <Candidates tag={tag} />}
        {rows(tab)}
        {tab === "print" && <PrintInfo tag={tag} />}
      </div>
      {general.length > 0 && <Msgs path="tag" issues={general} />}
      {plan && !plan.ok && <div className="msgs" data-issues-for="errors">{plan.errors.map((e, i) => <div key={i} className="issue lv-error">{e}</div>)}</div>}
      <div className={`summary lv-${summary.level}`} data-testid="summary">{summary.text}</div>
    </aside>
  );
}

/** Cells (CELL_RULE): absent = the legacy 0.5 mm marker steps; "marker":
 *  the marker size in mm steps; "cell": every cell a multiple of mm. */
function CellsEditor({ value, f, onChange, onBad }: { value: any; f: FormField; onChange: (v: any) => void; onBad: (m: string | null) => void }) {
  const of = value?.of ?? "legacy";
  const opts: Opt[] = [
    { value: "legacy", label: "Legacy (0.5 mm steps)", icon: "r-mm", hint: "a tag made before cell multiples: absent" },
    { value: "marker", label: "Marker in mm steps", icon: "r-mm" },
    { value: "cell", label: "Each cell a multiple", icon: "r-lines" },
  ];
  return (
    <span className="col">
      <Dropdown path={f.path} value={of} options={opts}
        onChange={(x) => onChange(x === "legacy" ? null : { rule: f.rule ?? 1, of: x, mm: value?.mm ?? (x === "cell" ? 0.45 : 0.5), min_mm: value?.min_mm ?? 2.0 })} />
      {value && (
        <span className="pair">
          <NumberInput path={`${f.path}.mm`} value={value.mm} unit="mm" onBad={onBad} onCommit={(x) => onChange({ ...value, mm: x })} />
          <span className="x" title="the smallest cell">min</span>
          <NumberInput path={`${f.path}.min_mm`} value={value.min_mm} unit="mm" onBad={onBad} onCommit={(x) => onChange({ ...value, min_mm: x })} />
        </span>
      )}
    </span>
  );
}

/** The Layout candidates for this tag's target (/api/candidates): picking
 *  one types its size and its cols x rows. */
function Candidates({ tag }: { tag: SceneTag }) {
  const [list, setList] = useState<any[] | null>(null);
  const s = tag.spec.settings as Record<string, any>;
  const key = JSON.stringify([s.layout, s.dictionary, s.quiet_modules, s.cells, tag.spec.target]);
  useEffect(() => {
    let live = true;
    api.candidates({ layout: s.layout ?? "single", dictionary: s.dictionary ?? "DICT_4X4_50", quiet_modules: Number(s.quiet_modules ?? 1), cells: s.cells ?? null, target: tag.spec.target, limit: 8 })
      .then((r) => { if (live) setList(r); }).catch(() => live && setList([]));
    return () => { live = false; };
  }, [key]);
  if (!list || !list.length) return null;
  const opts: Opt[] = list.map((c, i) => ({
    value: i,
    label: c.kind === "single" || (c.cols === 1 && c.rows === 1) ? `${c.marker_mm.toFixed(1)} mm marker` : `${c.cols} × ${c.rows} · ${c.marker_mm.toFixed(1)} mm${c.square_mm ? ` / ${c.square_mm.toFixed(1)}` : ""}`,
    hint: [...(c.badges || []), ...(c.notes || [])].join(" · "),
    icon: c.ok === false ? "warn" : undefined,
  }));
  const st = useStudio.getState();
  return (
    <div className="row" data-row="fit">
      <div className="row-main">
        <label className="row-label">Fit</label>
        <div className="row-ctl">
          <Dropdown path="fit" value={null} placeholder={`${list.length} layouts fit`} options={opts}
            onChange={(i) => {
              const c = list[Number(i)];
              const extra: Record<string, unknown> = { "settings.size_auto": false };
              if (s.layout !== "single") extra["settings.force"] = [c.cols, c.rows];
              if (s.layout === "charuco") extra["numbers.square"] = +c.square_mm.toFixed(3);
              st.edit("numbers.size", +c.marker_mm.toFixed(3), extra);
            }} />
        </div>
      </div>
    </div>
  );
}

/** The print preset this tag's settings equal, and its printer profile. */
function PrintInfo({ tag }: { tag: SceneTag }) {
  const [info, setInfo] = useState<{ preset: any; matches: string | null } | null>(null);
  const key = JSON.stringify([tag.spec.settings, tag.spec.numbers]);
  useEffect(() => {
    let live = true;
    api.presetOf(tag.spec as any).then((r) => live && setInfo(r)).catch(() => undefined);
    return () => { live = false; };
  }, [key]);
  if (!info) return null;
  const pr = info.preset.profile || {};
  return (
    <div className="printinfo" data-testid="printinfo">
      <div className="row-main"><span className="row-label">Preset</span><span className="row-ctl">{info.matches ?? "This tag (custom)"}</span></div>
      <div className="row-main"><span className="row-label">Nozzle</span><span className="row-ctl">{pr.nozzle_mm ? `${pr.nozzle_mm} mm` : "–"}{pr.line_mm ? ` · lines ${pr.line_mm} mm` : ""}</span></div>
    </div>
  );
}

/** Nothing selected: what a new tag gets (the toolbar adds it). */
function NewTagDefaults() {
  const targets = useStudio((s) => s.targets);
  const newTarget = useStudio((s) => s.newTarget);
  const newThickness = useStudio((s) => s.newThickness);
  const newPreset = useStudio((s) => s.newPreset);
  const presets = useStudio((s) => s.presets);
  const scene = useStudio((s) => s.scene);
  const st = useStudio.getState();
  return (
    <div className="newtag">
      <div className="insp-head"><Icon name="plus" /><b>New tags</b></div>
      <div className="muted pad">Nothing selected. A tag added from the toolbar gets these. {scene.tags.length ? `${scene.tags.length} tag(s) in '${scene.name}'.` : ""}</div>
      <div className="row"><div className="row-main"><label className="row-label">Target</label><div className="row-ctl">
        <Dropdown path="new.target" value={newTarget} options={targets.map((t) => ({ value: t.key, label: t.title, icon: "target" }))} onChange={(v) => st.setNew("newTarget", String(v))} />
      </div></div></div>
      <div className="row"><div className="row-main"><label className="row-label">Thickness</label><div className="row-ctl">
        <NumberInput path="new.thickness" value={newThickness} unit="mm" onCommit={(v) => st.setNew("newThickness", Math.max(0, v))} />
      </div></div></div>
      <div className="row"><div className="row-main"><label className="row-label">Preset</label><div className="row-ctl">
        <span className="pair">
          <Dropdown path="new.preset" value={newPreset} options={presets.map((p) => ({ value: p.name, label: p.name, icon: p.kind === "user" ? "star" : "cube" }))} onChange={(v) => st.setNew("newPreset", String(v))} />
          <IconButton icon="library" title="Preset library" onClick={() => st.setLibrary(true)} testid="library-btn" />
        </span>
      </div></div></div>
      <div className="keys muted pad">
        Keys: <b>S</b> single · <b>G</b> grid · <b>C</b> ChArUco · <b>R</b> rotate · <b>Ctrl+D</b> duplicate · <b>Del</b> delete · <b>Ctrl+Z</b> undo · <b>Tab</b> 2D / 3D · <b>F</b> fit · <b>?</b> all keys
      </div>
    </div>
  );
}
