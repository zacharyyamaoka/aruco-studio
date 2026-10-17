// The print preset Library, like Fusion's Machine Library: collections on
// the left (Recent, This scene, My presets, PrusaSlicer profiles, Built-in),
// cards with the marker thumb, Filters | Info on the right, Select / Cancel.
// A React port of REF ArucoMarkers/resources/preset_library (library.js);
// its state is server/library.py's (REF aruco_preset_library.Library).
import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { LibraryCard, LibraryState } from "../api/types";
import { useStudio } from "../store";
import { Icon } from "../ui/controls";

const FILTERS: [string, string, (c: LibraryCard) => unknown, (v: any) => string][] = [
  ["nozzle", "Nozzle", (c) => c.nozzle, (v) => `${v} mm`],
  ["layer", "Layer", (c) => c.layer, (v) => `${v} mm`],
  ["dictionary", "Dictionary", (c) => c.dictionary, (v) => String(v).replace("DICT_", "")],
  ["mode", "Extrude", (c) => c.mode_words, (v) => String(v)],
];

function home(c: LibraryCard) {
  return c.in.filter((x) => x !== "recent")[0] || c.in[0];
}

export function Library() {
  const open = useStudio((s) => s.libraryOpen);
  const sel = useStudio((s) => s.sel);
  if (!open) return null;
  return <LibraryWindow tag={sel[sel.length - 1]} />;
}

function LibraryWindow({ tag }: { tag?: string }) {
  const st = useStudio.getState();
  const [data, setData] = useState<LibraryState | null>(null);
  const [coll, setColl] = useState<string | null>(null);
  const [picked, setPicked] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [side, setSide] = useState<"filters" | "info">("filters");
  const [filters, setFilters] = useState<Record<string, Set<string>>>({ nozzle: new Set(), layer: new Set(), dictionary: new Set(), mode: new Set() });
  const [status, setStatus] = useState<{ text: string; kind?: string }>({ text: "" });
  const [editing, setEditing] = useState(false);
  const [ask, setAsk] = useState<null | { text: string; value: string; confirm?: boolean; ok: (v: string) => void }>(null);

  const load = async (selected?: string | null) => {
    const d = await api.library(tag);
    setData(d);
    setColl((c) => (c && d.collections.some((x) => x.id === c) ? c : (d.collections.find((x) => x.count > 0) ?? d.collections[0]).id));
    if (selected !== undefined) setPicked(selected);
    await st.loadPresets();
  };
  useEffect(() => { load().catch((e) => setStatus({ text: String(e), kind: "bad" })); }, [tag]);

  const cards = data?.cards ?? [];
  const card = cards.find((c) => c.id === picked) ?? null;
  const visible = useMemo(() => cards.filter((c) => {
    if (coll && !c.in.includes(coll)) return false;
    const qq = q.trim().toLowerCase();
    if (qq && !`${c.name} ${c.profile || ""} ${c.subtitle}`.toLowerCase().includes(qq)) return false;
    for (const [k, , get] of FILTERS) if (filters[k].size && !filters[k].has(String(get(c)))) return false;
    return true;
  }), [cards, coll, q, filters]);

  const act = async (label: string, fn: () => Promise<string | null | void>) => {
    setStatus({ text: "…" });
    try {
      const sel = await fn();
      await load(sel === undefined ? picked : sel);
      setStatus({ text: label });
    } catch (e) {
      setStatus({ text: String((e as Error).message), kind: "bad" });
    }
  };
  const close = () => st.setLibrary(false);
  const doSelect = async () => {
    if (!card || card.unreadable) return;
    try {
      const r = await api.librarySelect(card.id);
      if (tag) await st.applyPreset(r.name, r.preset);
      else st.setNew("newPreset", r.name);
      await st.loadPresets();
      close();
    } catch (e) {
      setStatus({ text: String((e as Error).message), kind: "bad" });
    }
  };

  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (ask) return;
      const tagName = (e.target as HTMLElement)?.tagName ?? "";
      if (["INPUT", "SELECT", "TEXTAREA"].includes(tagName)) return;
      if (e.key === "Escape") { e.stopPropagation(); close(); }
      if (e.key === "Enter") doSelect();
      if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
        const i = visible.findIndex((c) => c.id === picked);
        const j = Math.max(0, Math.min(visible.length - 1, i + (e.key === "ArrowRight" ? 1 : -1)));
        if (visible[j]) { setPicked(visible[j].id); setSide("info"); }
      }
    };
    window.addEventListener("keydown", key, true);
    return () => window.removeEventListener("keydown", key, true);
  });

  const collName = (id: string) => data?.collections.find((c) => c.id === id)?.name ?? id;
  const anyFilter = Object.values(filters).some((s) => s.size) || q;

  return (
    <div className="modal-back" data-testid="library" onMouseDown={(e) => e.target === e.currentTarget && close()}>
      <div className="library" role="dialog" aria-label="Print presets">
        <div className="lib-title"><Icon name="library" /> Print presets {tag ? <span className="muted">· for {tag}</span> : <span className="muted">· for new tags</span>}
          <button className="ib close" title="Close" onClick={close}><Icon name="close" /></button></div>
        <aside className="lib-nav">
          <label className="search"><Icon name="search" /><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search presets" data-testid="lib-search" /></label>
          <ul className="colls">
            {(data?.collections ?? []).map((c) => (
              <li key={c.id} className={c.id === coll ? "on" : ""} data-coll={c.id} onClick={() => setColl(c.id)}>
                <Icon name={c.icon} /><span>{c.name}</span><span className="n">{c.count}</span>
              </li>
            ))}
          </ul>
          <div className="notes">{(data?.notes ?? []).join(" · ")}</div>
        </aside>
        <main className="lib-main">
          <div className="lib-tools">
            <button className="tb" disabled={!tag} title="New: the tag's print settings as a preset of yours" data-testid="lib-new"
              onClick={() => setAsk({ text: "A name for a new preset made of the tag's print settings:", value: "My preset", ok: (name) => act(`saved '${name}'`, async () => {
                const t = st.scene.tags.find((x) => x.name === tag)!;
                const p = await api.presetOf(t.spec as any);
                const r = await api.presetSaveAs(name, p.preset);
                return `user:${r.name}`;
              }) })}><Icon name="plus" /><span>New</span></button>
            <button className="tb" disabled={!card?.preset} title="Duplicate the selected preset as one of yours" data-testid="lib-dup"
              onClick={() => card && setAsk({ text: "A name for the copy:", value: `${card.name} copy`, ok: (name) => act(`saved '${name}'`, async () => {
                const r = await api.presetSaveAs(name, card.preset!);
                return `user:${r.name}`;
              }) })}><Icon name="dup" /><span>Duplicate</span></button>
            <button className="tb" disabled={!card?.editable} title="Edit the selected preset (yours only)" data-testid="lib-edit"
              onClick={() => { setEditing(true); setSide("info"); }}><Icon name="pencil" /><span>Edit</span></button>
            <button className="tb" disabled={!card || card.kind !== "prusa" || card.unreadable} title="Import the selected PrusaSlicer profile as a preset of yours" data-testid="lib-import"
              onClick={() => card && act(`imported '${card.name}'`, async () => `user:${(await api.librarySelect(card.id)).name}`)}><Icon name="import" /><span>Import</span></button>
            <button className="tb" disabled={!card?.editable} title="Delete the selected preset (yours only)" data-testid="lib-delete"
              onClick={() => card && setAsk({ text: `Delete the preset '${card.name}'?`, value: "", confirm: true, ok: () => act(`deleted '${card.name}'`, async () => { await api.presetDelete(card.name); return null; }) })}>
              <Icon name="trash" /><span>Delete</span></button>
            <span className="sep" />
            <button className="link" disabled={!anyFilter} onClick={() => { setFilters({ nozzle: new Set(), layer: new Set(), dictionary: new Set(), mode: new Set() }); setQ(""); }}>Clear filters</button>
            <span className="grow" />
            <span className="muted" data-testid="lib-count">{visible.length} of {cards.length}</span>
          </div>
          <div className="cards" role="listbox" aria-label="Presets">
            {!visible.length && <div className="empty">{cards.length ? "No preset here matches." : "No presets yet."}</div>}
            {visible.map((c) => {
              const h = home(c);
              return (
                <div key={c.id} className={`card${c.id === picked ? " on" : ""}${c.unreadable ? " bad" : ""}`} role="option" aria-selected={c.id === picked}
                  data-card={c.id} title={c.cells || ""}
                  onClick={() => { setPicked(c.id); setSide("info"); setEditing(false); }}
                  onDoubleClick={() => { setPicked(c.id); setTimeout(doSelect, 0); }}>
                  {c.used > 0 && <span className="badge" title={`used by ${c.used} tag(s) in this scene`}>{c.used}</span>}
                  <div className="thumb" dangerouslySetInnerHTML={{ __html: c.thumb || "" }} />
                  <div className="name">{c.name}</div>
                  <div className="sub">{c.subtitle}</div>
                  <div className="where"><Icon name={h === "prusa" ? "import" : h === "mine" ? "star" : h === "document" ? "doc" : "cube"} />{collName(h)}</div>
                </div>
              );
            })}
          </div>
        </main>
        <aside className="lib-side">
          <div className="tabs2" role="tablist">
            <button className={`tab${side === "filters" ? " on" : ""}`} onClick={() => setSide("filters")} data-side="filters">Filters</button>
            <button className={`tab${side === "info" ? " on" : ""}`} onClick={() => setSide("info")} data-side="info">Info</button>
          </div>
          {side === "filters" && (
            <div className="panel">
              {FILTERS.map(([k, title, get, words]) => {
                const vals = [...new Set(cards.map((c) => get(c)).filter((v) => v !== null && v !== undefined && v !== ""))].sort((a: any, b: any) => (a > b ? 1 : a < b ? -1 : 0));
                if (!vals.length) return null;
                return (
                  <div className="fgroup" key={k}><h4>{title}</h4><div className="chips">
                    {vals.map((v) => (
                      <button key={String(v)} className={`chip${filters[k].has(String(v)) ? " on" : ""}`} data-filter={`${k}:${v}`}
                        onClick={() => setFilters((f) => { const s = new Set(f[k]); if (s.has(String(v))) s.delete(String(v)); else s.add(String(v)); return { ...f, [k]: s }; })}>
                        {words(v)}
                      </button>
                    ))}
                  </div></div>
                );
              })}
            </div>
          )}
          {side === "info" && (
            <div className="panel" data-testid="lib-info">
              {!card && <div className="muted">Select a preset to see its values.</div>}
              {card && !editing && (
                <>
                  <div className="isect"><h4 className="title">{card.name}</h4><div className="muted">{card.cells}</div></div>
                  {data?.dialog && <div className="differs">{card.differs ? `Changes the tag: ${card.differs}` : "The same as the tag's settings."}</div>}
                  {card.info.map(([title, rows]) => (
                    <div className="isect" key={title}><h4>{title}</h4>
                      {rows.map(([k, v]) => <div className="irow" key={k}><span className="k">{k}</span><span className="v">{v}</span></div>)}
                    </div>
                  ))}
                </>
              )}
              {card && editing && <EditForm card={card} schema={data?.schema ?? []} onCancel={() => setEditing(false)}
                onSave={(name, values) => act(`saved '${name || card.name}'`, async () => { const r = await api.librarySave(card.id, name, values); setEditing(false); return `user:${r.name}`; })} />}
            </div>
          )}
        </aside>
        <footer className="lib-foot">
          <span className={`status ${status.kind ?? ""}`} role="status" data-testid="lib-status">{status.text}</span>
          <span className="grow" />
          <button className="btn" onClick={close} data-testid="lib-cancel">Cancel</button>
          <button className="btn primary" disabled={!card || card.unreadable} onClick={doSelect} data-testid="lib-select">Select</button>
        </footer>
        {ask && (
          <div className="prompt">
            <div className="prompt-box">
              <div>{ask.text}</div>
              {!ask.confirm && <input autoFocus value={ask.value} data-testid="prompt-input" onChange={(e) => setAsk({ ...ask, value: e.target.value })}
                onKeyDown={(e) => { if (e.key === "Enter") { ask.ok(ask.value); setAsk(null); } if (e.key === "Escape") setAsk(null); e.stopPropagation(); }} />}
              <div className="prompt-buttons">
                <button className="btn" onClick={() => setAsk(null)}>Cancel</button>
                <button className="btn primary" data-testid="prompt-ok" onClick={() => { ask.ok(ask.value); setAsk(null); }}>OK</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function EditForm({ card, schema, onCancel, onSave }: {
  card: LibraryCard; schema: LibraryState["schema"]; onCancel: () => void; onSave: (name: string, values: Record<string, unknown>) => void;
}) {
  const [name, setName] = useState(card.name);
  const [vals, setVals] = useState<Record<string, unknown>>(() => {
    const out: Record<string, unknown> = {};
    for (const [path] of schema) {
      const [a, b] = path.split(".");
      out[path] = (card.preset as any)?.[a]?.[b];
    }
    return out;
  });
  return (
    <div className="form" data-testid="lib-form">
      <label><span>Name</span><input value={name} onChange={(e) => setName(e.target.value)} data-path="name" /></label>
      {schema.map(([path, label, kind, options]) => (
        <label key={path}><span>{label}</span>
          {kind === "select" ? (
            <select data-path={path} value={String(vals[path] ?? "")} onChange={(e) => setVals({ ...vals, [path]: e.target.value })}>
              {(options ?? []).map(([v, w]) => <option key={v} value={v}>{w}</option>)}
            </select>
          ) : kind === "bool" ? (
            <input type="checkbox" data-path={path} checked={Boolean(vals[path])} onChange={(e) => setVals({ ...vals, [path]: e.target.checked })} />
          ) : (
            <input data-path={path} value={String(vals[path] ?? "")} onChange={(e) => setVals({ ...vals, [path]: e.target.value })} />
          )}
        </label>
      ))}
      <div className="row-btns">
        <button className="btn" onClick={onCancel}>Cancel</button>
        <button className="btn primary" data-testid="lib-save" onClick={() => onSave(name, vals)}>Save</button>
      </div>
    </div>
  );
}
