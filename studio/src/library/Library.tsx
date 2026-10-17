// The print preset Library, like Fusion's Machine Library: collections on
// the left (Recent, This scene, My presets, PrusaSlicer profiles, Built-in),
// cards with the marker thumb, Filters | Info on the right, Select / Cancel.
// A React port of REF ArucoMarkers/resources/preset_library (library.js);
// its state is server/library.py's (REF aruco_preset_library.Library).
import { useEffect, useMemo, useState } from "react";
import { ApiError, api, errorText } from "../api/client";
import type { LibraryCard, LibraryState } from "../api/types";
import { useStudio } from "../store";
import { Dropdown, Icon } from "../ui/controls";

/** A message for the Library's status line: the server's words, never its
 *  HTTP status code (audit F16). */
function msgOf(e: unknown): string {
  if (e instanceof ApiError) return errorText((e.detail as any)?.detail ?? e.detail);
  return e instanceof Error ? e.message : String(e);
}

/** "dictionary DICT_A → DICT_B" out of a card's "Changes the tag: ..." words. */
function dictionaryChange(differs: string | null | undefined): string | null {
  const m = /dictionary [^,;]+/.exec(differs || "");
  return m ? m[0] : null;
}

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
    const sc = selected ? d.cards.find((c) => c.id === selected) : undefined;
    setColl((c) => {
      // a card just made or picked is shown where it lives (REF onState)
      if (sc && !(c && sc.in.includes(c))) return home(sc);
      return c && d.collections.some((x) => x.id === c) ? c : (d.collections.find((x) => x.count > 0) ?? d.collections[0]).id;
    });
    if (selected !== undefined) { setPicked(selected); if (selected) setSide("info"); }
    await st.loadPresets();
  };
  useEffect(() => { load().catch((e) => setStatus({ text: String(e), kind: "bad" })); }, [tag]);

  const cards = data?.cards ?? [];
  const card = cards.find((c) => c.id === picked) ?? null;
  const visible = useMemo(() => cards.filter((c) => {
    const qq = q.trim().toLowerCase();
    // typing searches every collection, not just the open one (audit F16)
    if (coll && !qq && !c.in.includes(coll)) return false;
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
      setStatus({ text: msgOf(e), kind: "bad" });
    }
  };
  const close = () => st.setLibrary(false);
  const doSelect = async (confirmed = false) => {
    if (!card || card.unreadable) return;
    // a print preset that also changes the tag's ink (its dictionary) says so
    // before it is applied (audit F10)
    const dict = tag ? dictionaryChange(card.differs) : null;
    if (dict && !confirmed) {
      setAsk({ text: `'${card.name}' also changes this tag's ${dict}: its markers change. Apply it?`, value: "", confirm: true,
        ok: () => { void doSelect(true); } });
      return;
    }
    try {
      const r = await api.librarySelect(card.id);
      if (tag) await st.applyPreset(r.name, r.preset);
      else st.setNew("newPreset", r.name);
      await st.loadPresets();
      close();
    } catch (e) {
      setStatus({ text: msgOf(e), kind: "bad" });
    }
  };

  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (ask) return;
      const tagName = (e.target as HTMLElement)?.tagName ?? "";
      if (["INPUT", "SELECT", "TEXTAREA"].includes(tagName)) return;
      if (e.key === "Escape" && document.querySelector(".library .dd.open")) return;   // its list closes first (audit F3)
      if (e.key === "Escape") { e.stopPropagation(); close(); }
      if (e.key === "Enter") void doSelect();
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
  // a name prompt refuses an empty name itself (audit F16)
  const [askErr, setAskErr] = useState<string | null>(null);
  const okAsk = () => {
    if (!ask) return;
    if (!ask.confirm && !ask.value.trim()) { setAskErr("a preset needs a name"); return; }
    setAskErr(null);
    ask.ok(ask.value.trim());
    setAsk(null);
  };
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
            <span className="muted" data-testid="lib-count" data-scope={q.trim() ? "all" : "collection"}>{visible.length} of {cards.length}{q.trim() ? " · every collection" : ""}</span>
          </div>
          <div className="cards" role="listbox" aria-label="Presets">
            {!visible.length && <div className="empty">{cards.length ? "No preset here matches." : "No presets yet."}</div>}
            {visible.map((c) => {
              const h = home(c);
              return (
                <div key={c.id} className={`card${c.id === picked ? " on" : ""}${c.unreadable ? " bad" : ""}`} role="option" aria-selected={c.id === picked}
                  data-card={c.id} title={c.cells || ""}
                  onClick={() => { setPicked(c.id); setSide("info"); setEditing(false); }}
                  onDoubleClick={() => { setPicked(c.id); setTimeout(() => void doSelect(), 0); }}>
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
                  {data?.dialog && dictionaryChange(card.differs) && <div className="issue lv-warn" data-testid="lib-ink-warn">A print preset that changes the {dictionaryChange(card.differs)}: the tag's markers change too.</div>}
                  {card.info.map(([title, rows]) => (
                    <div className="isect" key={title}><h4>{title}</h4>
                      {rows.map(([k, v]) => <div className="irow" key={k}><span className="k">{k}</span><span className="v">{v}</span></div>)}
                    </div>
                  ))}
                </>
              )}
              {card && editing && <EditForm card={card} schema={data?.schema ?? []} limits={data?.limits ?? {}} onCancel={() => setEditing(false)}
                onStart={() => setStatus({ text: "…" })}
                onSaved={async (name) => { setEditing(false); await load(`user:${name}`); setStatus({ text: `saved '${name}'` }); }} />}
            </div>
          )}
        </aside>
        <footer className="lib-foot">
          <span className={`status ${status.kind ?? ""}`} role="status" data-testid="lib-status">{status.text}</span>
          <span className="grow" />
          <button className="btn" onClick={close} data-testid="lib-cancel">Cancel</button>
          <button className="btn primary" disabled={!card || card.unreadable} onClick={() => void doSelect()} data-testid="lib-select">Select</button>
        </footer>
        {ask && (
          <div className="prompt">
            <div className="prompt-box">
              <div>{ask.text}</div>
              {!ask.confirm && <input autoFocus value={ask.value} data-testid="prompt-input" onChange={(e) => setAsk({ ...ask, value: e.target.value })}
                onKeyDown={(e) => { if (e.key === "Enter") okAsk(); if (e.key === "Escape") setAsk(null); e.stopPropagation(); }} />}
              {askErr && <div className="lib-form-err" data-testid="prompt-error">{askErr}</div>}
              <div className="prompt-buttons">
                <button className="btn" onClick={() => setAsk(null)}>Cancel</button>
                <button className="btn primary" data-testid="prompt-ok" onClick={okAsk}>OK</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function EditForm({ card, schema, limits, onCancel, onStart, onSaved }: {
  card: LibraryCard; schema: LibraryState["schema"]; limits: Record<string, [number, number]>;
  onCancel: () => void; onStart: () => void; onSaved: (name: string) => void | Promise<void>;
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
  const [errs, setErrs] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  /** Each number inside the range a preset keeps (server/library.LIMITS). */
  const check = (): Record<string, string> => {
    const out: Record<string, string> = {};
    if (!name.trim()) out.name = "a preset needs a name";
    for (const [path, label, kind] of schema) {
      if (kind !== "number") continue;
      const raw = String(vals[path] ?? "").trim().replace(",", ".");
      const v = Number(raw);
      if (raw === "" || !Number.isFinite(v)) { out[path] = `${label}: '${vals[path] ?? ""}' is not a number`; continue; }
      const lim = limits[path];
      if (lim && (v < lim[0] || v > lim[1])) out[path] = `${label}: ${raw} is outside ${lim[0]} to ${lim[1]}`;
    }
    return out;
  };
  const save = async () => {
    const e = check();
    setErrs(e);
    if (Object.keys(e).length) return;
    setBusy(true);
    onStart();
    try {
      const r = await api.librarySave(card.id, name.trim(), vals);
      await onSaved(r.name);
    } catch (x) {
      const d = x instanceof ApiError ? ((x.detail as any)?.detail ?? x.detail) : null;
      if (Array.isArray(d)) setErrs(Object.fromEntries(d.map((i: any) => [i.path ?? "form", i.msg])));
      else setErrs({ form: msgOf(x) });
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="form" data-testid="lib-form">
      <label><span>Name</span><input value={name} onChange={(e) => setName(e.target.value)} data-path="name" /></label>
      {errs.name && <div className="lib-form-err" data-error-for="name">{errs.name}</div>}
      {schema.map(([path, label, kind, options]) => (
        <div key={path} className="form-row">
          <label><span>{label}</span>
            {kind === "select" ? (
              <Dropdown path={`lib:${path}`} value={String(vals[path] ?? "")} wide
                options={(options ?? []).map(([v, w]) => ({ value: v, label: w }))}
                onChange={(v) => setVals({ ...vals, [path]: String(v) })} />
            ) : kind === "bool" ? (
              <input type="checkbox" data-path={path} checked={Boolean(vals[path])} onChange={(e) => setVals({ ...vals, [path]: e.target.checked })} />
            ) : (
              <input data-path={path} value={String(vals[path] ?? "")} className={errs[path] ? "bad" : ""}
                title={limits[path] ? `${limits[path][0]} to ${limits[path][1]}` : undefined}
                onChange={(e) => setVals({ ...vals, [path]: e.target.value })} />
            )}
          </label>
          {errs[path] && <div className="lib-form-err" data-error-for={path}>{errs[path]}</div>}
        </div>
      ))}
      {errs.form && <div className="lib-form-err" data-error-for="form">{errs.form}</div>}
      <div className="row-btns">
        <button className="btn" onClick={onCancel}>Cancel</button>
        <button className="btn primary" data-testid="lib-save" disabled={busy} onClick={save}>Save</button>
      </div>
    </div>
  );
}
