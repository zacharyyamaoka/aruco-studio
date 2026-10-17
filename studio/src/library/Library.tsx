// The Library, like Fusion's Machine Library, on the kit's LibraryShell:
// collections on the left (Recent, This scene, My presets, PrusaSlicer
// profiles, Built-in, Printers, Inkjet printers), cards with the marker
// thumb, Filters | Info on the right, Select / Cancel. Its state is
// server/library.py's (REF aruco_preset_library.Library).
//
// Printers (M8c, M8b2.4): one card per PrusaSlicer physical printer, its
// fitting print presets as the card's choices (the "Aruco" ones first,
// PrusaSlicer's current pair marked). Select makes an ArUco preset from the
// printer and the chosen print: the printer's nozzle, the print's line and
// layers (saved as one of yours).
import { Button, Glyph as Icon, LibraryShell, Select, type LibCard } from "@bam/ui";
import { useEffect, useMemo, useState } from "react";
import { ApiError, api, errorText } from "../api/client";
import type { LibraryCard, LibraryState } from "../api/types";
import { useStudio } from "../store";

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
  ["nozzle", "Nozzle", (c) => c.nozzle ?? c.printer?.nozzle_mm, (v) => `${v} mm`],
  ["layer", "Layer", (c) => c.layer, (v) => `${v} mm`],
  ["dictionary", "Dictionary", (c) => c.dictionary, (v) => String(v).replace("DICT_", "")],
  ["mode", "Extrude", (c) => c.mode_words, (v) => String(v)],
];

function home(c: LibraryCard) {
  return c.in.filter((x) => x !== "recent")[0] || c.in[0];
}

const HOME_ICON: Record<string, string> = { prusa: "import", mine: "star", document: "doc", printers: "printer", stickers: "sticker" };

/** A printer card's thumb: the printer glyph, its nozzle. */
function printerThumb(c: LibraryCard): string {
  const nz = c.printer?.nozzle_mm ? `${c.printer.nozzle_mm}` : "?";
  return `<svg viewBox="0 0 64 56" width="96" height="84"><rect x="10" y="4" width="44" height="30" rx="3" fill="none" stroke="#5b6573" stroke-width="2"/><path d="M18 34h28v5H18z" fill="#5b6573"/><path d="M28 11h8v8l-4 5-4-5z" fill="#2f6fed"/><text x="32" y="52" font-size="8" text-anchor="middle" fill="#3b4350" font-family="sans-serif">nozzle ${nz} mm</text></svg>`;
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
  const [choice, setChoice] = useState<Record<string, string>>({});
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
  /** The id Select sends: a printer card's chosen print, else the card. */
  const selectId = (c: LibraryCard) => c.kind === "printer" ? (choice[c.id] ?? c.default ?? c.choices?.[0]?.id ?? c.id) : c.id;
  const doSelect = async (confirmed = false) => {
    if (!card || card.unreadable) return;
    if (card.kind === "printer" && !(card.choices ?? []).length) { setStatus({ text: `no print preset fits '${card.name}'`, kind: "bad" }); return; }
    // a print preset that also changes the tag's ink (its dictionary) says so
    // before it is applied (audit F10)
    const dict = tag ? dictionaryChange(card.differs) : null;
    if (dict && !confirmed) {
      setAsk({ text: `'${card.name}' also changes this tag's ${dict}: its markers change. Apply it?`, value: "", confirm: true,
        ok: () => { void doSelect(true); } });
      return;
    }
    try {
      const r = await api.librarySelect(selectId(card));
      if (tag) await st.applyPreset(r.name, r.preset);
      else st.setNew("newPreset", r.name);
      await st.loadPresets();
      st.say(`preset '${r.name}'${card.kind === "printer" ? ` (from the printer ${card.name})` : ""}`);
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
      if (document.querySelector("[data-kit-popup][data-open]")) return;   // its list closes first (audit F3)
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
  const shellCards: LibCard[] = visible.map((c) => {
    const h = home(c);
    return {
      id: c.id, name: c.name, subtitle: c.subtitle, title: c.cells || c.subtitle,
      thumb: c.kind === "printer" ? printerThumb(c) : c.thumb, disabled: c.unreadable,
      mark: c.kind === "printer" && c.current ? "current" : undefined,
      badge: c.used > 0 ? <span className="badge" title={`used by ${c.used} tag(s) in this scene`}>{c.used}</span> : undefined,
      where: <><Icon name={HOME_ICON[h] ?? "cube"} />{collName(h)}</>,
    };
  });

  return (
    <LibraryShell
      title={<><Icon name="library" /> Presets {tag ? <span className="muted">· for {tag}</span> : <span className="muted">· for new tags</span>}</>}
      collections={data?.collections ?? []} coll={coll} onColl={setColl} search={q} onSearch={setQ}
      cards={shellCards} picked={picked} empty={cards.length ? "No preset here matches." : "No presets yet."}
      onPick={(id) => { setPicked(id); setSide("info"); setEditing(false); }}
      onOpen={(id) => { setPicked(id); setTimeout(() => void doSelect(), 0); }}
      onClose={close}
      notes={(data?.notes ?? []).join(" · ")}
      count={<span className="muted" data-testid="lib-count" data-scope={q.trim() ? "all" : "collection"}>{visible.length} of {cards.length}{q.trim() ? " · every collection" : ""}</span>}
      tools={<>
        <Button variant="ghost" icon="plus" disabled={!tag} title="New: the tag's print settings as a preset of yours" testid="lib-new"
          onClick={() => setAsk({ text: "A name for a new preset made of the tag's print settings:", value: "My preset", ok: (name) => act(`saved '${name}'`, async () => {
            const t = st.scene.tags.find((x) => x.name === tag)!;
            const p = await api.presetOf(t.spec as any);
            const r = await api.presetSaveAs(name, p.preset);
            return `user:${r.name}`;
          }) })}>New</Button>
        <Button variant="ghost" icon="dup" disabled={!card?.preset} title="Duplicate the selected preset as one of yours" testid="lib-dup"
          onClick={() => card && setAsk({ text: "A name for the copy:", value: `${card.name} copy`, ok: (name) => act(`saved '${name}'`, async () => {
            const r = await api.presetSaveAs(name, card.preset!);
            return `user:${r.name}`;
          }) })}>Duplicate</Button>
        <Button variant="ghost" icon="pencil" disabled={!card?.editable} title="Edit the selected preset (yours only)" testid="lib-edit"
          onClick={() => { setEditing(true); setSide("info"); }}>Edit</Button>
        <Button variant="ghost" icon="import" disabled={!card || card.kind !== "prusa" || card.unreadable} title="Import the selected PrusaSlicer profile as a preset of yours" testid="lib-import"
          onClick={() => card && act(`imported '${card.name}'`, async () => `user:${(await api.librarySelect(card.id)).name}`)}>Import</Button>
        <Button variant="ghost" icon="trash" disabled={!card?.editable} title="Delete the selected preset (yours only)" testid="lib-delete"
          onClick={() => card && setAsk({ text: `Delete the preset '${card.name}'?`, value: "", confirm: true, ok: () => act(`deleted '${card.name}'`, async () => { await api.presetDelete(card.name); return null; }) })}>Delete</Button>
        <span className="sep" />
        <button className="link" disabled={!anyFilter} onClick={() => { setFilters({ nozzle: new Set(), layer: new Set(), dictionary: new Set(), mode: new Set() }); setQ(""); }}>Clear filters</button>
      </>}
      side={<>
        <div className="tabs2" role="tablist">
          <button className={`tab2${side === "filters" ? " on" : ""}`} onClick={() => setSide("filters")} data-side="filters">Filters</button>
          <button className={`tab2${side === "info" ? " on" : ""}`} onClick={() => setSide("info")} data-side="info">Info</button>
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
            {!card && <div className="muted">Select a card to see its values.</div>}
            {card && card.kind === "printer" && <PrinterInfo card={card} chosen={selectId(card)} onChoose={(id) => setChoice((c) => ({ ...c, [card.id]: id }))} />}
            {card && card.kind !== "printer" && !editing && (
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
            {card && card.kind !== "printer" && editing && <EditForm card={card} schema={(card.edit === "2d" ? data?.schema_2d : data?.schema) ?? data?.schema ?? []} limits={data?.limits ?? {}} onCancel={() => setEditing(false)}
              onStart={() => setStatus({ text: "…" })}
              onSaved={async (name) => { setEditing(false); await load(`user:${name}`); setStatus({ text: `saved '${name}'` }); }} />}
          </div>
        )}
      </>}
      foot={<>
        <span className={`status ${status.kind ?? ""}`} role="status" data-testid="lib-status">{status.text}</span>
        <span className="grow" />
        <Button onClick={close} testid="lib-cancel">Cancel</Button>
        <Button variant="primary" disabled={!card || card.unreadable} onClick={() => void doSelect()} testid="lib-select">Select</Button>
      </>}
      overlay={ask && (
        <div className="prompt">
          <div className="prompt-box">
            <div>{ask.text}</div>
            {!ask.confirm && <input autoFocus className="kit-text" value={ask.value} data-testid="prompt-input" onChange={(e) => setAsk({ ...ask, value: e.target.value })}
              onKeyDown={(e) => { if (e.key === "Enter") okAsk(); if (e.key === "Escape") setAsk(null); e.stopPropagation(); }} />}
            {askErr && <div className="lib-form-err" data-testid="prompt-error">{askErr}</div>}
            <div className="prompt-buttons">
              <Button onClick={() => setAsk(null)}>Cancel</Button>
              <Button variant="primary" testid="prompt-ok" onClick={okAsk}>OK</Button>
            </div>
          </div>
        </div>
      )}
    />
  );
}

/** A Printers card's Info: the printer, then its fitting prints to choose. */
function PrinterInfo({ card, chosen, onChoose }: { card: LibraryCard; chosen: string; onChoose: (id: string) => void }) {
  const p = card.printer ?? {};
  const rows: [string, string][] = [
    ["Printer preset", String(p.preset ?? "–")], ["Model", `${p.model ?? "–"} ${p.variant ?? ""}`],
    ["Nozzle", p.nozzle_mm ? `${p.nozzle_mm} mm` : "–"], ["Bed", Array.isArray(p.bed_mm) ? `${p.bed_mm.join(" × ")} mm` : "–"],
    ["Extruders", String(p.extruders ?? "–")], ["From", p.source === "user" ? "your printer preset" : "PrusaSlicer's bundle"],
  ];
  return (
    <div data-testid="printer-info" data-printer={card.name}>
      <div className="isect"><h4 className="title">{card.name}{card.current && <span className="muted"> · PrusaSlicer's current printer</span>}</h4>
        <div className="muted">{card.subtitle}</div></div>
      <div className="isect"><h4>Printer</h4>
        {rows.map(([k, v]) => <div className="irow" key={k}><span className="k">{k}</span><span className="v">{v}</span></div>)}
      </div>
      <div className="isect"><h4>Print presets that fit ({(card.choices ?? []).length})</h4>
        {!(card.choices ?? []).length && <div className="muted">None of your print presets fits this printer.</div>}
        <div className="choice-list" role="radiogroup">
          {(card.choices ?? []).map((c) => (
            <div key={c.id} role="radio" aria-checked={c.id === chosen} className={`choice${c.id === chosen ? " on" : ""}`} data-choice={c.id}
              data-current={c.current ? "1" : "0"} title={`layer ${c.layer} mm · line ${c.line} mm · first layer ${c.first_layer} mm`} onClick={() => onChoose(c.id)}>
              <Icon name={c.aruco ? "star" : "t-print"} /><span className="nm">{c.name}</span>
              {c.current && <span className="kit-pill t-ok">current</span>}
              {c.fits === "maybe" && <span className="kit-pill t-warn" title="its condition could not be read: the nozzle fits">maybe</span>}
            </div>
          ))}
        </div>
      </div>
      <div className="muted" style={{ marginTop: 6 }}>Select makes an ArUco preset of yours: this printer's nozzle, the print's line and layers.</div>
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
      <div className="kit-field row" data-row="name"><div className="kit-row row-main"><label className="row-label">Name</label>
        <div className="row-ctl"><input className="kit-text" value={name} onChange={(e) => setName(e.target.value)} data-path="name" /></div></div></div>
      {errs.name && <div className="lib-form-err" data-error-for="name">{errs.name}</div>}
      {schema.map(([path, label, kind, options]) => (
        <div key={path} className="form-row">
          <div className="kit-field row" data-row={path}><div className="kit-row row-main"><label className="row-label" title={label}><span className="row-text">{label}</span></label>
            <div className="row-ctl">
              {kind === "select" ? (
                <Select path={`lib:${path}`} value={String(vals[path] ?? "")} wide
                  options={(options ?? []).map(([v, w]) => ({ value: v, label: w }))}
                  onChange={(v) => setVals({ ...vals, [path]: String(v) })} />
              ) : kind === "bool" ? (
                <input type="checkbox" data-path={path} checked={Boolean(vals[path])} onChange={(e) => setVals({ ...vals, [path]: e.target.checked })} />
              ) : (
                <input className={`kit-text${errs[path] ? " bad" : ""}`} data-path={path} value={String(vals[path] ?? "")}
                  title={limits[path] ? `${limits[path][0]} to ${limits[path][1]}` : undefined}
                  onChange={(e) => setVals({ ...vals, [path]: e.target.value })} />
              )}
            </div></div></div>
          {errs[path] && <div className="lib-form-err" data-error-for={path}>{errs[path]}</div>}
        </div>
      ))}
      {errs.form && <div className="lib-form-err" data-error-for="form">{errs.form}</div>}
      <div className="row-btns">
        <Button onClick={onCancel}>Cancel</Button>
        <Button variant="primary" testid="lib-save" disabled={busy} onClick={save}>Save</Button>
      </div>
    </div>
  );
}
