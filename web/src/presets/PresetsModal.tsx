// The presets modal (Fusion's "ArUco print presets"): the kit's LibraryShell
// with Recent / My presets / Built-in, a search, cards with key numbers,
// Filters and Info on the side, New / Duplicate / Edit / Delete, Import and
// Export as JSON, Cancel / Select. Built-ins come from core.presets(); my
// presets live in this browser (./local.ts).
import { useMemo, useRef, useState } from "react";
import { Button, Dialog, FieldRow, Glyph, LibraryShell, NumberField, SegmentedRow, Select, TextField, type LibCard } from "@bam/ui";
import { Copy, Download, Pencil, Plus, Trash2, Upload } from "lucide-react";
import type { Preset, Vec2 } from "../core/contract";
import { downloadText } from "../io/files";
import { useStudio } from "../store";
import { blankPreset, exportJson, importJson, myPresets, presetNumbers, recentIds, saveMine } from "./local";

const PAGES: Record<string, Vec2> = { Letter: [215.9, 279.4], A4: [210, 297], A3: [297, 420], A5: [148, 210], Legal: [215.9, 355.6] };

function thumb(p: Preset): string {
  const mk = `<path fill-rule="evenodd" fill="#111" d="M0 0h24v24H0zM4 4h5v5H4zM13 9h5v5h-5zM4 14h4v4H4z"/>`;
  if (p.method === "inkjet") {
    const [w, h] = p.page_mm ?? [216, 279];
    const s = 76 / Math.max(w, h);
    return `<svg viewBox="0 0 ${w * s + 4} ${h * s + 4}" width="${w * s + 4}" height="${h * s + 4}"><rect x="2" y="2" width="${w * s}" height="${h * s}" fill="#fff" stroke="#9aa3ae"/>`
      + `<g transform="translate(${2 + (w * s) / 2 - 12} 12)">${mk}</g><text x="${2 + (w * s) / 2}" y="${h * s - 6}" font-size="8" text-anchor="middle" fill="#6b7480" font-family="sans-serif">${p.page ?? ""}</text></svg>`;
  }
  const lines = Array.from({ length: 6 }, (_, i) => `<path d="M${60 + i * 4} 14v52" stroke="#2f6fed" stroke-width="1.2"/>`).join("");
  return `<svg viewBox="0 0 96 80" width="96" height="80"><rect x="6" y="14" width="44" height="52" fill="#fff"/><g transform="translate(10 22) scale(1.5)">${mk}</g>`
    + `<rect x="58" y="14" width="26" height="52" fill="none" stroke="#9aa3ae"/>${lines}<text x="71" y="76" font-size="7" text-anchor="middle" fill="#6b7480" font-family="sans-serif">${p.line_mm ?? ""} mm</text></svg>`;
}

function Chips({ title, values, on, toggle }: { title: string; values: string[]; on: string[]; toggle: (v: string) => void }) {
  if (!values.length) return null;
  return (
    <div className="chips">
      <div className="chips-title">{title}</div>
      <div className="chips-row">
        {values.map((v) => (
          <button type="button" key={v} className={`chip${on.includes(v) ? " on" : ""}`} data-chip={v} onClick={() => toggle(v)}>{v}</button>
        ))}
      </div>
    </div>
  );
}

function PresetForm({ draft, onChange }: { draft: Preset; onChange: (p: Preset) => void }) {
  const num = (k: keyof Preset, label: string, unit = "mm", int = false) => (
    <FieldRow path={`preset.${k}`} label={label}>
      <NumberField path={`preset.${k}`} value={(draft[k] as number | undefined) ?? null} unit={unit} int={int} min={0}
        step={int ? 1 : 0.05} onCommit={(v) => onChange({ ...draft, [k]: v })} />
    </FieldRow>
  );
  const pair = (k: "page_mm" | "bed_mm", label: string) => {
    const v = draft[k] ?? [0, 0];
    return (
      <FieldRow path={`preset.${k}`} label={label}>
        <NumberField path={`preset.${k}.0`} value={v[0]} unit="mm" min={1} onCommit={(x) => onChange({ ...draft, [k]: [x, v[1]] })} />
        <span className="times">×</span>
        <NumberField path={`preset.${k}.1`} value={v[1]} unit="mm" min={1} onCommit={(y) => onChange({ ...draft, [k]: [v[0], y] })} />
      </FieldRow>
    );
  };
  return (
    <div className="preset-form" data-testid="preset-form">
      <FieldRow path="preset.name" label="Name">
        <TextField path="preset.name" value={draft.name} onCommit={(v) => onChange({ ...draft, name: v || draft.name })} />
      </FieldRow>
      <FieldRow path="preset.method" label="Method">
        <SegmentedRow path="preset.method" value={draft.method} compact
          options={[{ value: "inkjet", label: "Inkjet", icon: "inkjet" }, { value: "print3d", label: "3D print", icon: "print3d" }]}
          onChange={(m) => onChange({ ...blankPreset(m as Preset["method"]), id: draft.id, name: draft.name })} />
      </FieldRow>
      {draft.method === "inkjet" ? (
        <>
          <FieldRow path="preset.page" label="Paper">
            <Select path="preset.page" value={draft.page ?? "Custom"}
              options={[...Object.keys(PAGES), "Custom"].map((p) => ({ value: p, label: p }))}
              onChange={(p) => onChange({ ...draft, page: String(p), page_mm: PAGES[String(p)] ?? draft.page_mm })} />
          </FieldRow>
          {pair("page_mm", "Page")}
          {num("margin_mm", "Margin")}
          {num("thickness_mm", "Thickness")}
          {num("dpi", "Resolution", "dpi", true)}
        </>
      ) : (
        <>
          {num("nozzle_mm", "Nozzle")}
          {num("line_mm", "Line width")}
          {num("first_line_mm", "First line")}
          {num("layer_mm", "Layer")}
          {num("first_layer_mm", "First layer")}
          {pair("bed_mm", "Bed")}
        </>
      )}
      {num("min_cell_mm", "Min cell")}
      {num("cell_step_mm", "Cell step")}
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
  const current = useStudio((s) => s.doc.preset);
  const setPreset = useStudio((s) => s.setPreset);
  const close = () => useStudio.getState().openModal(null);
  const [mine, setMine] = useState<Preset[]>(myPresets());
  const [coll, setColl] = useState<string>("builtin");
  const [search, setSearch] = useState("");
  const [picked, setPicked] = useState<string | null>(current?.id ?? null);
  const [side, setSide] = useState<"filters" | "info">("filters");
  const [filters, setFilters] = useState<{ method: string[]; paper: string[]; nozzle: string[] }>({ method: [], paper: [], nozzle: [] });
  const [editing, setEditing] = useState<{ draft: Preset; isNew: boolean } | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const file = useRef<HTMLInputElement>(null);

  const all = useMemo(() => [...builtins, ...mine], [builtins, mine]);
  const recent = recentIds().map((id) => all.find((p) => p.id === id)).filter((p): p is Preset => !!p);
  const base = coll === "recent" ? recent : coll === "mine" ? mine : builtins;
  const methodName = (m: string) => (m === "inkjet" ? "Inkjet" : "3D print");
  const list = base.filter((p) => {
    if (search && !`${p.name} ${presetNumbers(p)}`.toLowerCase().includes(search.toLowerCase())) return false;
    if (filters.method.length && !filters.method.includes(methodName(p.method))) return false;
    if (filters.paper.length && !(p.page && filters.paper.includes(p.page))) return false;
    if (filters.nozzle.length && !(p.nozzle_mm && filters.nozzle.includes(`${p.nozzle_mm} mm`))) return false;
    return true;
  });
  const sel = all.find((p) => p.id === picked) ?? null;
  const cards: LibCard[] = list.map((p) => ({
    id: p.id, name: p.name, subtitle: presetNumbers(p), thumb: thumb(p),
    where: <><Glyph name={p.builtin ? "cube" : "star"} size={12} />{p.builtin ? "Built-in" : "My preset"}</>,
    mark: p.id === current?.id ? "current" : undefined,
  }));
  const toggle = (k: keyof typeof filters) => (v: string) =>
    setFilters((f) => ({ ...f, [k]: f[k].includes(v) ? f[k].filter((x) => x !== v) : [...f[k], v] }));
  const nFilters = filters.method.length + filters.paper.length + filters.nozzle.length;
  const uniq = (xs: (string | undefined)[]) => [...new Set(xs.filter((x): x is string => !!x))];

  const storeMine = (next: Preset[]) => { setMine(next); saveMine(next); };
  const choose = (id: string | null) => {
    const p = all.find((x) => x.id === id);
    if (!p) return;
    setPreset(p);
    close();
  };

  const info = sel && (
    <dl className="preset-info" data-testid="preset-info">
      <div className="kv"><dt>Name</dt><dd>{sel.name}</dd></div>
      <div className="kv"><dt>Method</dt><dd>{methodName(sel.method)}</dd></div>
      {Object.entries(sel).filter(([k]) => !["id", "name", "method", "builtin"].includes(k)).map(([k, v]) => (
        <div key={k} className="kv"><dt>{k.replace(/_mm$/, " (mm)").replace(/_/g, " ")}</dt><dd>{Array.isArray(v) ? v.join(" × ") : String(v)}</dd></div>
      ))}
    </dl>
  );

  return (
    <>
      <LibraryShell
        testid="presets-modal"
        title={<><Glyph name="library" />ArUco print presets</>}
        collections={[
          { id: "recent", name: "Recent", icon: "clock", count: recent.length },
          { id: "mine", name: "My presets", icon: "star", count: mine.length },
          { id: "builtin", name: "Built-in", icon: "cube", count: builtins.length },
        ]}
        coll={coll} onColl={setColl} search={search} onSearch={setSearch}
        cards={cards} picked={picked} onPick={setPicked} onOpen={(id) => choose(id)}
        empty={coll === "mine" ? "No presets of your own yet: New, or Duplicate a built-in." : builtins.length ? "Nothing matches." : "Loading the core's presets…"}
        notes={note}
        tools={
          <>
            <Button variant="ghost" size="sm" icon={<Plus size={13} />} testid="preset-new"
              onClick={() => setEditing({ draft: blankPreset(filters.method.includes("3D print") ? "print3d" : "inkjet"), isNew: true })}>New</Button>
            <Button variant="ghost" size="sm" icon={<Copy size={13} />} testid="preset-dup" disabled={!sel}
              onClick={() => sel && setEditing({ draft: blankPreset(sel.method, sel), isNew: true })}>Duplicate</Button>
            <Button variant="ghost" size="sm" icon={<Pencil size={13} />} testid="preset-edit" disabled={!sel || sel.builtin}
              title={sel?.builtin ? "Built-ins are fixed: Duplicate it" : undefined}
              onClick={() => sel && setEditing({ draft: { ...sel }, isNew: false })}>Edit</Button>
            <Button variant="ghost" size="sm" icon={<Trash2 size={13} />} testid="preset-delete" disabled={!sel || sel.builtin}
              onClick={() => { if (sel) { storeMine(mine.filter((p) => p.id !== sel.id)); setPicked(null); } }}>Delete</Button>
            <span className="tool-sep" />
            <Button variant="ghost" size="sm" icon={<Upload size={13} />} testid="preset-import" onClick={() => file.current?.click()}>Import</Button>
            <Button variant="ghost" size="sm" icon={<Download size={13} />} testid="preset-export" disabled={!mine.length}
              onClick={() => downloadText("my-aruco-presets.json", exportJson(mine), "application/json")}>Export</Button>
            {nFilters > 0 && <Button variant="ghost" size="sm" onClick={() => setFilters({ method: [], paper: [], nozzle: [] })}>Clear filters</Button>}
          </>
        }
        count={<span className="muted">{list.length} of {base.length}</span>}
        side={
          <>
            <div className="side-tabs">
              <button type="button" className={side === "filters" ? "on" : ""} onClick={() => setSide("filters")}>Filters</button>
              <button type="button" className={side === "info" ? "on" : ""} onClick={() => setSide("info")}>Info</button>
            </div>
            <div className="side-body">
              {side === "filters" ? (
                <>
                  <Chips title="Method" values={uniq(all.map((p) => methodName(p.method)))} on={filters.method} toggle={toggle("method")} />
                  <Chips title="Paper" values={uniq(all.map((p) => p.page))} on={filters.paper} toggle={toggle("paper")} />
                  <Chips title="Nozzle" values={uniq(all.map((p) => (p.nozzle_mm ? `${p.nozzle_mm} mm` : undefined)))} on={filters.nozzle} toggle={toggle("nozzle")} />
                </>
              ) : info ?? <div className="muted pad">Pick a preset to see its numbers.</div>}
            </div>
          </>
        }
        foot={
          <>
            <span className="muted">{sel ? sel.name : "No preset picked"}</span>
            <span className="grow" />
            <Button onClick={close} testid="presets-cancel">Cancel</Button>
            <Button variant="primary" onClick={() => choose(picked)} disabled={!sel} testid="presets-select">Select</Button>
          </>
        }
        onClose={close}
      />
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
      <Dialog open={!!editing} onClose={() => setEditing(null)} title={editing?.isNew ? "New preset" : "Edit preset"} icon="library"
        testid="preset-dialog" width={380}
        footer={
          <>
            <Button onClick={() => setEditing(null)}>Cancel</Button>
            <Button variant="primary" testid="preset-save" onClick={() => {
              if (!editing) return;
              const d = { ...editing.draft, builtin: false };
              storeMine(editing.isNew ? [...mine, d] : mine.map((p) => (p.id === d.id ? d : p)));
              setColl("mine");
              setPicked(d.id);
              if (current?.id === d.id) setPreset(d);
              setEditing(null);
            }}>Save</Button>
          </>
        }>
        {editing && <PresetForm draft={editing.draft} onChange={(draft) => setEditing({ ...editing, draft })} />}
      </Dialog>
    </>
  );
}
