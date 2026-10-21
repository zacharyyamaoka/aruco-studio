// The presets modal (Fusion's "ArUco print presets"; Zach's 2026-10-18
// review, laid out as V1 "Command Dialog"'s library dialog, 2026-10-20 night):
// the left bar finds (search, the Method / Paper / Nozzle chips, Recent / My
// presets / Built-in), the middle lists the presets by method, the right is
// the picked preset's Info, always open. A click picks a card and shows its
// Info; a double-click or Select uses it. My presets are edited in place in
// Info and saved in this browser (./local.ts); a built-in is read-only:
// Duplicate to edit. New / Duplicate / Delete, Import and Export as JSON.
// Use applies the preset to the marker the panel is open on (and a new marker
// starts with it); with no panel open it is only the new markers' default, and
// the footer says which. WHY per marker (Zach, 2026-10-20 night): "Preset
// shouldn't be on the file because it's applied on a per marker basis!"
import { useMemo, useRef, useState, type ReactNode } from "react";
import { Button, FieldRow, Glyph, NumberField, SegmentedRow, Select, TextField } from "@bam/ui";
import { Copy, Download, Plus, Trash2, Upload } from "lucide-react";
import type { Preset } from "../core/contract";
import { downloadText } from "../io/files";
import { CoreWait } from "../panel/Waiting";
import { featureNumber, featurePreset, getFeature } from "../model/doc";
import { useStudio } from "../store";
import { chipValues, filterPresets, infoRows, methodName, NO_FILTERS, PAGES, presetStep, stepKey, stepLabel, stepOf, stepOptions, withField, type Filters, type InfoRow } from "./fields";
import { blankPreset, exportJson, importJson, myPresets, presetNumbers, recentIds, saveMine } from "./local";
import { Thumb } from "./Thumb";
import "./presets.css";

const METHODS: Preset["method"][] = ["inkjet", "print3d"];

function Chips({ title, values, on, toggle }: { title: string; values: string[]; on: string[]; toggle: (v: string) => void }) {
  if (!values.length) return null;
  return (
    <div className="pl-chips" data-chips={title}>
      <div className="pl-chips-title">{title}</div>
      <div className="pl-chips-row">
        {values.map((v) => (
          <button type="button" key={v} className={`pl-chip${on.includes(v) ? " on" : ""}`} data-chip={v} aria-pressed={on.includes(v)}
            onClick={() => toggle(v)}>{v}</button>
        ))}
      </div>
    </div>
  );
}

/** The picked preset's every field, one row each: editable for my presets
 *  (each commit saves), disabled for a built-in. */
function PresetInfo({ p, onChange, onDuplicate }: { p: Preset; onChange: (p: Preset) => void; onDuplicate: () => void }) {
  const ro = p.builtin;
  const row = (r: InfoRow): ReactNode => {
    if (r.kind === "page") {
      return (
        <FieldRow key={r.key} path="preset.page" label={r.label}>
          <Select path="preset.page" value={p.page ?? "Custom"} disabled={ro} testid="preset-page"
            options={[...Object.keys(PAGES), "Custom"].map((x) => ({ value: x, label: x }))}
            onChange={(x) => onChange(withField(p, "page", String(x)))} />
        </FieldRow>
      );
    }
    if (r.kind === "pair") {
      const v = p[r.key] ?? [0, 0];
      return (
        <FieldRow key={r.key} path={`preset.${r.key}`} label={r.label}>
          <NumberField path={`preset.${r.key}.0`} value={p[r.key]?.[0]} unit={r.unit} min={1} disabled={ro} placeholder="—"
            onCommit={(x) => onChange(withField(p, r.key, [x, v[1]]))} />
          <span className="times">×</span>
          <NumberField path={`preset.${r.key}.1`} value={p[r.key]?.[1]} unit={r.unit} min={1} disabled={ro} placeholder="—"
            onCommit={(y) => onChange(withField(p, r.key, [v[0], y]))} />
        </FieldRow>
      );
    }
    return (
      <FieldRow key={r.key} path={`preset.${r.key}`} label={r.label} title={r.hint}>
        <NumberField path={`preset.${r.key}`} value={p[r.key] ?? null} unit={r.unit} int={r.int} min={0} step={r.step} disabled={ro} placeholder="—"
          onCommit={(v) => onChange(withField(p, r.key, v))} />
      </FieldRow>
    );
  };
  return (
    <div className="pl-info" data-testid="preset-info" data-preset={p.id} data-readonly={ro ? "1" : undefined}>
      <div className="pl-info-head">
        <span className="pl-info-where"><Glyph name={p.builtin ? "cube" : "star"} size={12} />{p.builtin ? "Built-in" : "My preset"}</span>
        {ro && (
          <Button size="sm" variant="primary" icon={<Copy size={13} />} testid="preset-dup-edit" onClick={onDuplicate}
            title="Built-ins are fixed: edit a copy of it in My presets">Duplicate to edit</Button>
        )}
      </div>
      <FieldRow path="preset.name" label="Name">
        <TextField path="preset.name" value={p.name} disabled={ro} testid="preset-name"
          onCommit={(v) => onChange({ ...p, name: v.trim() || p.name })} />
      </FieldRow>
      <FieldRow path="preset.method" label="Method">
        <SegmentedRow path="preset.method" value={p.method} compact disabled={ro}
          options={[{ value: "inkjet", label: "Inkjet", icon: "inkjet" }, { value: "print3d", label: "3D print", icon: "print3d" }]}
          onChange={(m) => m !== p.method && onChange({ ...blankPreset(m as Preset["method"]), id: p.id, name: p.name })} />
      </FieldRow>
      {infoRows(p.method).map(row)}
      {/* barrier 11: what driven sizes round to; a 3D printer's is its line */}
      <FieldRow path="preset.size_step" label="Size step" title="What driven sizes round to; typed sizes are never rounded">
        {p.method === "inkjet" ? (
          <Select path="preset.size_step" value={stepKey(presetStep(p))} disabled={ro} testid="preset-size-step"
            options={stepOptions(presetStep(p), p)} onChange={(k) => onChange({ ...p, size_step: stepOf(String(k)) })} />
        ) : <span className="muted" data-testid="preset-size-step">{stepLabel(presetStep(p), p)}</span>}
      </FieldRow>
      {ro && <div className="pl-info-note muted">Built-in presets are fixed.</div>}
    </div>
  );
}

export function PresetsModal() {
  const open = useStudio((s) => s.modal === "presets");
  if (!open) return null;
  return <PresetsLibrary />;
}

function PresetsLibrary() {
  const builtins = useStudio((s) => s.builtins);
  // the open marker's preset, else the one a new marker starts with
  const target = useStudio((s) => (s.panel.open ? getFeature(s.doc, s.panel.featureId) : null));
  const current = useStudio((s) => (target ? featurePreset(s.doc, target) : s.doc.default_preset));
  const targetName = useStudio((s) => (target ? `ArUco Extrude ${featureNumber(s.doc, target.id)}` : null));
  const setPreset = useStudio((s) => s.setPreset);
  const close = () => useStudio.getState().openModal(null);
  const [mine, setMine] = useState<Preset[]>(myPresets());
  const [coll, setColl] = useState<string>("builtin");
  const [search, setSearch] = useState("");
  const [picked, setPicked] = useState<string | null>(current?.id ?? null);
  const [filters, setFilters] = useState<Filters>(NO_FILTERS);
  const [note, setNote] = useState<string | null>(null);
  const file = useRef<HTMLInputElement>(null);

  const all = useMemo(() => [...builtins, ...mine], [builtins, mine]);
  const recent = recentIds().map((id) => all.find((p) => p.id === id)).filter((p): p is Preset => !!p);
  const base = coll === "recent" ? recent : coll === "mine" ? mine : builtins;
  const list = filterPresets(base, search, filters);
  const chips = chipValues(all);
  const sel = all.find((p) => p.id === picked) ?? null;
  const toggle = (k: keyof Filters) => (v: string) =>
    setFilters((f) => ({ ...f, [k]: f[k].includes(v) ? f[k].filter((x) => x !== v) : [...f[k], v] }));
  const nFilters = filters.method.length + filters.paper.length + filters.nozzle.length;

  const storeMine = (next: Preset[]) => { setMine(next); saveMine(next); };
  const add = (p: Preset) => { storeMine([...mine, p]); setColl("mine"); setPicked(p.id); };
  const edit = (p: Preset) => {
    const d = { ...p, builtin: false };
    storeMine(mine.map((x) => (x.id === d.id ? d : x)));
    if (current?.id === d.id) setPreset(d);
  };
  const duplicate = () => sel && add(blankPreset(sel.method, sel));
  const choose = (id: string | null) => {
    const p = all.find((x) => x.id === id);
    if (!p) return;
    setPreset(p);
    close();
  };
  const colls = [
    { id: "recent", name: "Recent", icon: "clock", count: recent.length },
    { id: "mine", name: "My presets", icon: "star", count: mine.length },
    { id: "builtin", name: "Built-in", icon: "cube", count: builtins.length },
  ];

  return (
    <div className="modal-back kit-backdrop-solid" data-testid="presets-modal" onMouseDown={(e) => e.target === e.currentTarget && close()}>
      <div className="library kit-library presets-lib" role="dialog" aria-label="ArUco print presets">
        <div className="lib-title"><Glyph name="library" />ArUco print presets
          <button className="kit-ib close" title="Close" aria-label="Close" onClick={close}><Glyph name="close" /></button></div>
        <aside className="lib-nav" data-testid="presets-nav">
          <label className="search"><Glyph name="search" />
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search" data-testid="lib-search" /></label>
          <div className="pl-filters" data-testid="preset-filters">
            <Chips title="Method" values={chips.method} on={filters.method} toggle={toggle("method")} />
            <Chips title="Paper" values={chips.paper} on={filters.paper} toggle={toggle("paper")} />
            <Chips title="Nozzle" values={chips.nozzle} on={filters.nozzle} toggle={toggle("nozzle")} />
            {nFilters > 0 && <button type="button" className="pl-clear" data-testid="preset-clear-filters" onClick={() => setFilters(NO_FILTERS)}>Clear filters</button>}
          </div>
          <ul className="colls">
            {colls.map((c) => (
              <li key={c.id} className={c.id === coll ? "on" : ""} data-coll={c.id} onClick={() => setColl(c.id)}>
                <Glyph name={c.icon} /><span>{c.name}</span><span className="n">{c.count}</span>
              </li>
            ))}
          </ul>
          <div className="notes">{note}</div>
        </aside>
        <main className="lib-main">
          <div className="lib-tools">
            <Button variant="ghost" size="sm" icon={<Plus size={13} />} testid="preset-new"
              onClick={() => add(blankPreset(filters.method.length === 1 && filters.method[0] === "3D print" ? "print3d" : "inkjet"))}>New</Button>
            <Button variant="ghost" size="sm" icon={<Copy size={13} />} testid="preset-dup" disabled={!sel} onClick={duplicate}>Duplicate</Button>
            <Button variant="ghost" size="sm" icon={<Trash2 size={13} />} testid="preset-delete" disabled={!sel || sel.builtin}
              title={sel?.builtin ? "Built-ins are fixed" : undefined}
              onClick={() => { if (sel) { storeMine(mine.filter((p) => p.id !== sel.id)); setPicked(null); } }}>Delete</Button>
            <span className="tool-sep" />
            <Button variant="ghost" size="sm" icon={<Upload size={13} />} testid="preset-import" onClick={() => file.current?.click()}>Import</Button>
            <Button variant="ghost" size="sm" icon={<Download size={13} />} testid="preset-export" disabled={!mine.length}
              onClick={() => downloadText("my-aruco-presets.json", exportJson(mine), "application/json")}>Export</Button>
            <span className="grow" />
            <span className="muted">{list.length} of {base.length}</span>
          </div>
          {/* WHY a list by method (V1 Command Dialog, 2026-10-20 night): how it is made is the first thing to decide */}
          <div className="pl-list" role="listbox" aria-label="Presets" data-testid="preset-list">
            {!list.length && (
              <div className="empty">{coll === "mine" && !mine.length ? "No presets of your own yet: New, or Duplicate a built-in."
                : builtins.length ? "Nothing matches." : <CoreWait needFacts testid="presets-wait" />}</div>
            )}
            {METHODS.map((method) => {
              const group = list.filter((p) => p.method === method);
              if (!group.length) return null;
              return (
                <div key={method} className="pl-group" role="group" aria-label={methodName(method)} data-group={method}>
                  {/* WHY the printer drawn beside each (Zach, 2026-10-21: "You need a better icon for ink jet vs 3D printer") */}
                  <div className="pl-group-head"><Glyph name={method} size={14} />{methodName(method)}</div>
                  {group.map((p) => (
                    <div key={p.id} className={`card pl-item${p.id === picked ? " on" : ""}`} role="option" aria-selected={p.id === picked}
                      data-card={p.id} data-mark={p.id === current?.id ? "current" : undefined}
                      onClick={() => setPicked(p.id)} onDoubleClick={() => choose(p.id)}>
                      <div className="thumb"><Thumb p={p} /></div>
                      <div className="pl-text">
                        <div className="name"><Glyph name={p.method} size={12} className="pl-method" /><span className="pl-name">{p.name}</span></div>
                        <div className="sub">{presetNumbers(p)}</div>
                      </div>
                      <div className="where"><Glyph name={p.builtin ? "cube" : "star"} size={12} />{p.builtin ? "Built-in" : "My preset"}</div>
                      {p.id === current?.id && <span className="card-mark" data-testid="card-mark">current</span>}
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        </main>
        <aside className="lib-side" data-testid="presets-side">
          <div className="pl-side-title">Info</div>
          <div className="pl-side-body">
            {sel ? <PresetInfo key={sel.id} p={sel} onChange={edit} onDuplicate={duplicate} />
              : <div className="muted pl-pad">Pick a preset to see its numbers.</div>}
          </div>
        </aside>
        <footer className="lib-foot">
          <span className="muted">{sel ? sel.name : "No preset picked"}</span>
          <span className="grow" />
          <span className="pl-target" data-testid="presets-target" data-target={target ? target.id : "new"}>
            {targetName ? <>Use applies to <b>{targetName}</b> and the next new marker</> : <>No marker open: Use sets the preset <b>new markers</b> start with</>}
          </span>
          <Button onClick={close} testid="presets-cancel">Cancel</Button>
          <Button variant="primary" onClick={() => choose(picked)} disabled={!sel} testid="presets-select">Use</Button>
        </footer>
      </div>
      <input ref={file} type="file" accept="application/json,.json" hidden data-testid="preset-import-file"
        onChange={async (e) => {
          const fl = e.target.files?.[0];
          e.target.value = "";
          if (!fl) return;
          try {
            const got = importJson(await fl.text());
            storeMine([...mine, ...got]);
            setColl("mine");
            setNote(`Imported ${got.length} preset${got.length === 1 ? "" : "s"}.`);
          } catch (err) {
            setNote(`Import failed: ${(err as Error).message}`);
          }
        }} />
    </div>
  );
}
