// The inspector of the selection. The tag's form is the kit's Form over
// GET /api/form (plan/fields.py, bam.form/1): its tabs, rows, icons, which
// rows show (show_when) and where a hidden row's messages go (anchor) all
// come from the server; this file holds no field list. What is the
// Studio's own: the header, the Preset row and its Made-by line, the
// ArUco Extrude's "On" rows, and the few controls that are more than a
// type (Size with its Auto, Columns x rows, Cells, Origin's turns, Trim /
// Perimeter, the Fit candidates). Several tags selected: one form for all,
// a change goes to every one of them (one undo step), a value that differs
// shows "—" until it is typed.
import {
  common, FieldRow, Form, getPath, Glyph as Icon, IconButton, NumberField, SegmentedRow, Select, Switch, TextField,
  type Cell, type ControlArgs, type FormCtx, type FormRow, type Issue as KitIssue, type Opt,
} from "@bam/ui";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "../api/client";
import type { FormDoc, FormField, Issue, SceneTag } from "../api/types";
import { idsText } from "../model/scene";
import { findShape } from "../model/design";
import { madeBy, useStudio } from "../store";
import { MadeByLine, PresetRow, StaleRows } from "./PresetRow";
import { ShapeInspector } from "./ShapeInspector";

export function Inspector() {
  const form = useStudio((s) => s.form);
  const scene = useStudio((s) => s.scene);
  const sel = useStudio((s) => s.sel);
  const shapeSel = useStudio((s) => s.shapeSel);
  const doc = useStudio((s) => s.doc);
  const [tab, setTab] = useState<string>("marker");
  const tags = scene.tags.filter((t) => sel.includes(t.name));
  const tag: SceneTag | undefined = tags[tags.length - 1];

  if (!form) return <aside className="inspector"><div className="muted pad">Loading…</div></aside>;
  if (!tag && shapeSel.length) {
    const info = findShape(doc, shapeSel[shapeSel.length - 1]);
    if (info) return <ShapeInspector key={info.key} info={info} />;
  }
  if (!tag) return <aside className="inspector" data-testid="inspector"><NewTagDefaults /></aside>;
  return <TagInspector key={tag.uid} tag={tag} tags={tags} form={form} tab={tab} setTab={setTab} />;
}

/** The facts show_when reads: the layout, how it is made, the target's. */
export function ctxOf(tag: SceneTag): FormCtx {
  const t = tag.spec.target;
  const flags: string[] = [t.kind, t.has_body ? "body" : "free"];
  if ((t.loops_mm ?? []).length > 1) flags.push("holes");
  return {
    get: (p) => getPath(tag.spec, p),
    layout: String(tag.spec.settings.layout ?? "single"),
    made_by: madeBy(tag),
    target: flags,
  };
}

/** A choice row's choices for this tag (choices_by_layout, choices_when). */
export function choicesFor(f: FormField, ctx: FormCtx): { value: string | number; label: string; icon?: string }[] {
  let out = f.choices ?? [];
  const byLayout = f.choices_by_layout?.[ctx.layout ?? "single"];
  if (byLayout) out = byLayout;
  for (const w of f.choices_when ?? []) {
    const hold = Object.entries(w.when).every(([p, v]) => {
      const now = ctx.get(p);
      if (p === "settings.make.by") return (ctx.made_by ?? "print3d") === v;
      return String(now ?? (typeof v === "number" ? 0 : "")) === String(v);
    });
    if (hold) out = w.choices;
  }
  return out;
}

function TagInspector({ tag, tags, form, tab, setTab }: {
  tag: SceneTag; tags: SceneTag[]; form: FormDoc; tab: string; setTab: (t: string) => void;
}) {
  const st = useStudio.getState();
  const options = useStudio((s) => s.options);
  const s = tag.spec.settings as Record<string, any>;
  const n = tag.spec.numbers as Record<string, any>;
  const plan = tag.plan;
  const [autoNote, setAutoNote] = useState("");
  // Auto size at creation (plan.auto, REF _check_auto): a tag stored with
  // Auto AND a number (made before 2026-10-13) says when Auto would build
  // another tag here now (audit C5)
  const autoKey = s.size_auto && Number(n.size) > 0 ? JSON.stringify(tag.spec) : "";
  useEffect(() => {
    let live = true;
    if (!autoKey) { setAutoNote(""); return; }
    api.autoCheck(tag.spec as any).then((r) => live && setAutoNote(r.auto ? "" : r.note)).catch(() => live && setAutoNote(""));
    return () => { live = false; };
  }, [autoKey]);
  const planIssues: Issue[] = (plan?.warnings as Issue[]) ?? [];
  const issues = useMemo(() => autoNote ? [...planIssues, { field: "numbers.size", level: "info", text: autoNote } as Issue] : planIssues,
    [planIssues, autoNote]);
  const [bad, setBad] = useState<Record<string, string | null>>({});
  const ctx = useMemo(() => ctxOf(tag), [tag]);
  const sticker = ctx.made_by === "sticker";
  const layout = ctx.layout ?? "single";
  const value = (p: string): Cell => tags.length > 1 ? common(tags.map((t) => getPath(t.spec, p))) : { value: getPath(tag.spec, p), mixed: false };
  const edit = (path: string, v: unknown, extra?: Record<string, unknown>) => st.edit(path, v, extra);
  const local = (path: string) => (m: string | null) => setBad((b) => ({ ...b, [path]: m }));
  const dis = Boolean(tag.locked);
  const m = plan?.marker as any;

  // the controls that are more than their type
  const control = ({ row, value: v, mixed, disabled }: ControlArgs): ReactNode | undefined => {
    const f = row as FormField;
    const p = f.path;
    if (p === "numbers.size" || p === "numbers.square") {
      // ONE Auto for the size and the checker (REF's dialog: values() types
      // both or neither); off, the fields start at what Auto built
      const autoCell = value("numbers.size");
      const auto = !autoCell.mixed && !Number(autoCell.value);
      const builtSize = Number(m?.marker_length_m || 0) * 1000;
      const builtSquare = Number(m?.square_length_m || 0) * 1000;
      const built = p === "numbers.size" ? builtSize : builtSquare;
      const shownV = auto ? (built || null) : (Number(v) || built || null);
      return (
        <span className="pair">
          {p === "numbers.size" && (
            <Switch disabled={disabled} value={auto} mixed={autoCell.mixed} label="Auto" path={`${p}:auto`}
              onChange={(a) => edit(p, a ? 0 : +(builtSize || 20).toFixed(3), {
                "settings.size_auto": a,
                ...(layout === "charuco" ? { "numbers.square": a ? 0 : +(builtSquare || 0).toFixed(3) } : {}),
                ...(a ? { "settings.force": null } : {}),
              })} />
          )}
          <NumberField value={shownV} path={p} unit="mm" step={f.step} mixed={mixed && !auto} disabled={auto || disabled} onBad={local(p)}
            onCommit={(x) => edit(p, x, p === "numbers.size" ? { "settings.size_auto": x === 0 } : undefined)} />
        </span>
      );
    }
    if (p === "settings.force") {
      const cur = (v as number[] | null) ?? null;
      const cols = cur?.[0] ?? m?.cols ?? 1, rows = cur?.[1] ?? m?.rows ?? 1;
      if (tag.spec.target.kind === "face") {
        // REF evaluate(): on a face the fit lays out as many as fit; only a
        // sketch profile takes a typed count (Advanced > Target kind)
        return <span className="ro" data-path={p} title="On a face the fit lays out as many as fit; a sketch profile (Advanced › Target) takes a typed count">{m?.cols ?? "–"} × {m?.rows ?? "–"} (as many as fit on a face)</span>;
      }
      return (
        <span className="pair">
          <NumberField disabled={disabled} int value={cols} path={`${p}[0]`} onBad={local(p)} onCommit={(x) => edit(p, [x, rows])} />
          <span className="x">×</span>
          <NumberField disabled={disabled} int value={rows} path={`${p}[1]`} onBad={local(p)} onCommit={(x) => edit(p, [cols, x])} />
          {cur && <IconButton icon="close" title="Back to the fit's count" onClick={() => edit(p, null)} />}
        </span>
      );
    }
    if (p === "settings.turn") {
      const icons = f.icons_by_layout?.[layout] ?? {};
      const opts: Opt[] = (options?.origin?.[layout] ?? f.choices ?? []).map((c: any) => ({ value: c.value, label: c.label, hint: c.label, icon: icons[String(c.value)] }));
      return <SegmentedRow disabled={disabled} path={p} value={Number(v ?? 0)} mixed={mixed} options={opts} onChange={(x) => edit(p, Number(x))} />;
    }
    if (p === "settings.cells") return <CellsEditor disabled={disabled} value={v as any} mixed={mixed} f={f} onChange={(x) => edit(p, x)} onBad={local(p)} />;
    if (p === "settings.trim") {
      const cur = v as any;
      const opts: Opt[] = (options?.trim ?? [{ value: "off", label: "Off" }]).map((c: any) => ({ value: c.value, label: c.label }));
      return (
        <span className="pair">
          <Select disabled={disabled} path={p} value={cur && cur.rule === 1 ? cur.axes : "off"} mixed={mixed} options={opts}
            onChange={(x) => edit(p, x === "off" ? null : { rule: 1, axes: x, margin_mm: cur?.margin_mm ?? 0, force: Boolean(cur?.force) })} />
          {cur && cur.rule === 1 && <Switch disabled={disabled} value={Boolean(cur.force)} label="Cut anyway" path={`${p}.force`} onChange={(x) => edit(p, { ...cur, force: x })} />}
        </span>
      );
    }
    if (p === "settings.make.perimeter" && !sticker) {
      // on a 3D tag Perimeter IS Trim excess (M6 d): Marker = trimmed to
      // the tag's outline (both axes), Profile = the body keeps its outline
      const trim = value("settings.trim");
      const t = trim.value as any;
      const on = t && t.rule === 1;
      const val = trim.mixed ? null : !on ? "profile" : t.axes === "both" ? "marker" : `marker-${t.axes}`;
      const opts: Opt[] = [{ value: "marker", label: "Marker", hint: "the body is trimmed to the tag's outline (Trim excess, both)" },
        { value: "profile", label: "Profile", hint: "the body keeps its outline (Trim excess off)" }];
      if (on && t.axes !== "both") opts.push({ value: `marker-${t.axes}`, label: `Marker (${t.axes} only)` });
      return <Select disabled={disabled} path={p} value={val} mixed={trim.mixed} options={opts}
        onChange={(x) => edit("settings.trim", x === "profile" ? null : { rule: 1, axes: "both", margin_mm: t?.margin_mm ?? 0, force: Boolean(t?.force) })} />;
    }
    if (f.type === "choice" && !f.read_only && (f.choices_by_layout || f.choices_when)) {
      const opts: Opt[] = choicesFor(f, ctx).map((c: any) => ({ value: c.value, label: c.label, icon: c.icon || undefined }));
      return <Select disabled={disabled} path={p} value={v as any} mixed={mixed} options={opts} onChange={(x) => edit(p, x)} />;
    }
    if (p === "settings.mode") {
      const opts: Opt[] = (f.choices ?? []).map((c) => ({ value: c.value, label: c.label, icon: c.icon || undefined }));
      return <Select disabled={disabled} path={p} value={v as any} mixed={mixed} options={opts} onChange={(x) => st.setMode(String(x))} />;
    }
    if (p === "settings.make.by") return null;          // drawn as the Made-by line under the Preset
    return undefined;
  };

  // every row a sticker words otherwise (label_2d); Perimeter on a 3D tag
  const labelOf = (r: FormRow) => {
    const f = r as FormField;
    if (sticker && f.label_2d) return f.label_2d;
    return f.label;
  };
  const rows = useMemo(() => form.fields.filter((f) => f.path !== "settings.make.by"), [form]);
  const errors = plan && !plan.ok ? plan.errors.filter((e) => !issues.some((i) => i.text === e)) : [];

  return (
    <aside className="inspector" data-testid="inspector" data-tag={tag.name} data-made-by={ctx.made_by} data-count={tags.length}>
      <div className="insp-head">
        <Icon name={layout} />
        {tags.length > 1
          ? <b className="grow" data-testid="insp-multi">{tags.length} tags</b>
          : <TextField value={tag.name} path="name" onCommit={(x) => st.rename(tag.name, x)} />}
        <span className="ids" data-testid="insp-ids" title="the ids this tag prints">#{idsText(plan?.ids ?? [])}</span>
        <IconButton icon={tag.locked ? "lock" : "unlock"} title={tag.locked ? "Locked: a printed tag (its ink cannot change)" : "Lock: mark as printed"}
          active={tag.locked} onClick={() => st.setFlag(tag.name, "locked", !tag.locked)} testid="lock" />
        <IconButton icon={tag.hidden ? "eyeoff" : "eye"} title={tag.hidden ? "Hidden" : "Hide"} onClick={() => st.setFlag(tag.name, "hidden", !tag.hidden)} />
      </div>
      {tags.length > 1 && <div className="multi" data-testid="multi-note">{tags.length} tags selected: a change goes to every one of them; "—" where they differ.</div>}
      <div className="insp-sub">
        {m ? `${m.dictionary} · ${m.layout === "single" ? `${(m.marker_length_m * 1000).toFixed(2)} mm` : `${m.cols} × ${m.rows}, marker ${(m.marker_length_m * 1000).toFixed(2)} mm`}` : "not built"}
      </div>
      {tag.locked && <div className="locked-note" data-testid="locked-note"><Icon name="lock" />Locked: a printed tag. Unlock it to change its ink; its name and place can still change.</div>}
      <Form rows={rows} tabs={form.tabs} ctx={ctx} issues={issues as KitIssue[]} outside={form.outside} tab={tab} onTab={setTab}
        value={value} onChange={(p, v) => edit(p, v)} control={control} labelOf={labelOf} disabled={dis}
        local={bad} onLocal={(p, msg) => setBad((b) => ({ ...b, [p]: msg }))}
        okText={plan?.ok ? "Ready: the plan is built" : "Not built"} extraErrors={errors}
        slots={{
          "root:before": (routed) => (
            <>
              <PresetRow tag={tag} issues={routed["preset"] ?? []} />
              <MadeByLine tag={tag} />
              <StaleRows names={tags.map((t) => t.name)} />
              <ArucoRows tag={tag} issues={routed["target"] ?? []} />
            </>
          ),
          "marker:before": () => <Candidates tag={tag} />,
          "print:after": () => <PrintInfo tag={tag} />,
        }} />
    </aside>
  );
}

/** Cells (CELL_RULE): absent = the legacy 0.5 mm marker steps; "marker":
 *  the marker size in mm steps; "cell": every cell a multiple of mm. One
 *  24 px row: the kind, then its mm and its smallest cell. */
function CellsEditor({ value, f, onChange, onBad, disabled, mixed }: { value: any; f: FormField; onChange: (v: any) => void; onBad: (m: string | null) => void; disabled?: boolean; mixed?: boolean }) {
  const of = value?.of ?? "legacy";
  const opts: Opt[] = [
    { value: "legacy", label: "Legacy 0.5 mm", icon: "r-mm", hint: "a tag made before cell multiples: absent" },
    { value: "marker", label: "Marker in mm", icon: "r-mm", hint: "the marker size in mm steps" },
    { value: "cell", label: "Cell multiple", icon: "r-lines", hint: "every cell a multiple of a line" },
  ];
  return (
    <span className="pair">
      <Select disabled={disabled} path={f.path} value={of} mixed={mixed} options={opts}
        onChange={(x) => onChange(x === "legacy" ? null : { rule: f.rule ?? 1, of: x, mm: value?.mm ?? (x === "cell" ? 0.45 : 0.5), min_mm: value?.min_mm ?? 2.0 })} />
      {value && !mixed && (
        <>
          <NumberField className="narrow" disabled={disabled} path={`${f.path}.mm`} value={value.mm} title="the step (mm)" onBad={onBad}
            onCommit={(x) => {
              // the form's limits (/api/form: 0.01 to 20 mm): outside them a cell is
              // refused here, never sent to be read as the legacy steps (audit F8)
              const lo = Number(f.min_mm ?? 0.01), hi = Number(f.max_mm ?? 20);
              if (!(x >= lo && x <= hi)) { onBad(`cell ${x} mm: ${lo} to ${hi} mm`); return; }
              onChange({ ...value, mm: x });
            }} />
          <NumberField className="narrow" disabled={disabled} path={`${f.path}.min_mm`} value={value.min_mm} title="the smallest cell (mm)" onBad={onBad}
            onCommit={(x) => {
              if (!(x >= 0)) { onBad(`smallest cell ${x} mm: 0 or more`); return; }
              onChange({ ...value, min_mm: x });
            }} />
        </>
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
    <FieldRow path="fit" label="Fit">
      <Select disabled={tag.locked} path="fit" value={null} placeholder={`${list.length} layouts fit`} options={opts} wide
        onChange={(i) => {
          const c = list[Number(i)];
          const extra: Record<string, unknown> = { "settings.size_auto": false };
          if (s.layout !== "single") extra["settings.force"] = [c.cols, c.rows];
          if (s.layout === "charuco") extra["numbers.square"] = +c.square_mm.toFixed(3);
          st.edit("numbers.size", +c.marker_mm.toFixed(3), extra);
        }} />
    </FieldRow>
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
      <FieldRow path="printinfo.preset" label="Preset"><span className="ro">{info.matches ?? "This tag (custom)"}</span></FieldRow>
      <FieldRow path="printinfo.nozzle" label={pr.kind === "sticker" ? "Printer" : "Nozzle"}>
        <span className="ro">{pr.kind === "sticker" ? `${pr.dpi ?? "?"} dpi · ${String(pr.page ?? "").toUpperCase()}` : `${pr.nozzle_mm ? `${pr.nozzle_mm} mm` : "–"}${pr.line_mm ? ` · lines ${pr.line_mm} mm` : ""}`}</span>
      </FieldRow>
    </div>
  );
}

/** ArUco Extrude's first rows: what the tag stands on (its feature's
 *  reference: a shape or a body's face) and the shape, a click away. */
function ArucoRows({ tag, issues }: { tag: SceneTag; issues: KitIssue[] }) {
  const st = useStudio.getState();
  const src = tag.source;
  const tags = useStudio((s) => s.scene.tags);
  const mates = src ? tags.filter((t) => t.source?.feature === src.feature && t.name !== tag.name) : [];
  return (
    <div className="aruco-rows" data-testid="aruco-rows">
      <FieldRow path="target" label="On" title="the ArUco Extrude's reference in the file" issues={issues}>
        <span className="ro" data-testid="aruco-on">{src?.ref ?? "–"}{src?.face && src.face !== "top" ? ` (${src.face})` : ""}</span>
        {src?.shape && <button className="link" data-testid="aruco-shape" title="select the shape" onClick={() => st.selectShape(src.shape!)}>{src.shape}</button>}
      </FieldRow>
      {mates.length > 0 && (
        <FieldRow path="aruco.list" label="Face list">
          <span className="ro" title="one feature, one tag per face: an edit to one face that the others do not share splits the list">
            with {mates.map((m) => m.name).join(", ")}</span>
        </FieldRow>
      )}
    </div>
  );
}

/** Nothing selected: the preset new tags get first (both kinds), what it
 *  makes, and how to make a tag. */
function NewTagDefaults() {
  const scene = useStudio((s) => s.scene);
  return (
    <div className="newtag">
      <div className="insp-head"><Icon name="plus" /><b>New tag</b></div>
      <PresetRow tag={null} issues={[]} />
      <MadeByLine tag={null} />
      <div className="muted pad">Draw a shape (R, C, P, O), then A puts a tag on it with this preset; E extrudes it, so a tag can go on a face.
        {scene.tags.length ? ` ${scene.tags.length} tag(s) in '${scene.name}'.` : ""}</div>
      <div className="keys muted pad">
        Keys: <b>V</b> select · <b>R</b> rectangle · <b>C</b> circle · <b>P</b> polygon · <b>O</b> slot · <b>H</b> hole · <b>E</b> extrude · <b>A</b> ArUco Extrude · <b>S</b> search · <b>?</b> all keys
      </div>
    </div>
  );
}
