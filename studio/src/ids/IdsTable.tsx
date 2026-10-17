// The IDs table: one row per scene tag (core.marker_table's columns: name,
// type, dictionary, ids, status), the typed first id (an override), and
// "Renumber all" (core.numbering through the scene's ledger). Click a row
// to select its tag; double-click zooms to it.
import { Fragment, useMemo } from "react";
import { duplicates, idsText, rowMessages } from "../model/scene";
import { useStudio } from "../store";
import { Icon, IconButton, NumberInput } from "../ui/controls";

export function IdsTable() {
  const scene = useStudio((s) => s.scene);
  const sel = useStudio((s) => s.sel);
  const dicts = useStudio((s) => s.dictionaries);
  const report = useStudio((s) => s.renumberReport);
  const idErrors = useStudio((s) => s.idErrors);
  const st = useStudio.getState();
  const familyOf = useMemo(() => {
    const m = Object.fromEntries(dicts.map((d) => [d.name, d.family]));
    return (d: string) => m[d] ?? d;
  }, [dicts]);
  const dup = duplicates(scene.tags, familyOf);
  const dupOf = (name: string) => Object.entries(dup).filter(([, v]) => v.includes(name)).map(([k]) => k);
  const changed = new Set((report?.changed ?? []).map((c) => c.tag));
  const nDup = Object.keys(dup).length;
  // Renumber's messages, each on its tag's row ("board1|tag: ..." -> board1)
  // and the rest below the table (audit F15)
  const names = scene.tags.map((t) => t.name);
  const errs = rowMessages(report?.errors ?? [], names);
  const warns = rowMessages(report?.warnings ?? [], names);
  return (
    <aside className="ids-panel" data-testid="ids">
      <div className="panel-head">
        <Icon name="ids" /><b>IDs</b>
        <span className={`muted${nDup ? " warn" : ""}`} data-testid="dup-count" data-dups={nDup}
          title={nDup ? `${nDup} id${nDup === 1 ? " is" : "s are"} printed by more than one tag` : "every id is printed once"}>{nDup ? `${nDup} dup.` : "unique"}</span>
        <span className="grow" />
        <button className="btn small" data-testid="renumber" title="Renumber all: unique ids per dictionary family; printed (locked) tags and typed ids are kept"
          onClick={() => st.renumber()} disabled={!scene.tags.length}><Icon name="renumber" /> Renumber all</button>
      </div>
      <div className="ids-scroll">
        <table className="ids-table">
          <thead><tr><th>Tag</th><th>Dict</th><th>IDs</th><th title="a typed first id (empty = auto)">First</th><th /></tr></thead>
          <tbody>
            {scene.tags.map((t) => {
              const m = t.plan?.marker as any;
              const d = dupOf(t.name);
              const typed = scene.overrides[t.name];
              const rowErr = [idErrors[t.name], ...(errs.byTag[t.name] ?? [])].filter(Boolean) as string[];
              const rowWarn = warns.byTag[t.name] ?? [];
              return (
                <Fragment key={t.uid}>
                <tr data-ids-row={t.name} className={`${sel.includes(t.name) ? "on" : ""}${d.length ? " dup" : ""}${t.hidden ? " hid" : ""}${rowErr.length ? " bad" : ""}`}
                  onClick={(e) => st.select(t.name, e.shiftKey || e.ctrlKey)} onDoubleClick={() => st.zoomToFit([t.name])}>
                  <td className="nm"><Icon name={String(t.spec.settings.layout ?? "single")} />{t.name}</td>
                  <td className="muted">{m ? String(m.dictionary).replace("DICT_", "") : "–"}</td>
                  <td className="idc" data-ids={(t.plan?.ids ?? []).join(",")}>{t.plan?.ok ? idsText(t.plan.ids) : <span className="bad">not built</span>}{changed.has(t.name) && <i className="chg" title="changed by the last Renumber">•</i>}</td>
                  <td onClick={(e) => e.stopPropagation()} className={idErrors[t.name] ? "first bad" : "first"}
                    title={t.locked ? "locked: a printed tag keeps its ids" : "a typed first id: used at once, kept by Renumber all"}>
                    <NumberInput int path={`override:${t.name}`} value={typed ?? null} placeholder="auto" disabled={t.locked}
                      onCommit={(v) => st.override(t.name, v)} />
                    {typed !== undefined && !t.locked && <IconButton icon="close" title="Back to auto" onClick={() => st.override(t.name, null)} />}
                  </td>
                  <td className="st">
                    {t.locked && <span title="locked: a printed tag keeps its ids"><Icon name="lock" /></span>}
                    {d.length > 0 && <span className="warn" title={`also printed by ${d.map((k) => dup[k].filter((x) => x !== t.name).join(", ")).join("; ")}`}><Icon name="warn" /></span>}
                  </td>
                </tr>
                {(rowErr.length > 0 || rowWarn.length > 0) && (
                  <tr className="row-msg" data-ids-msg={t.name}>
                    <td colSpan={5}>
                      {rowErr.map((m, i) => <div key={`e${i}`} className="issue lv-error" data-level="error">{m}</div>)}
                      {rowWarn.map((m, i) => <div key={`w${i}`} className="issue lv-warn" data-level="warn">{m}</div>)}
                    </td>
                  </tr>
                )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
        {!scene.tags.length && <div className="muted pad">No tags yet.</div>}
      </div>
      {(errs.rest.length > 0 || warns.rest.length > 0) && (
        <div className="msgs" data-issues-for="renumber">
          {errs.rest.map((e, i) => <div key={`e${i}`} className="issue lv-error">{e}</div>)}
          {warns.rest.map((e, i) => <div key={`w${i}`} className="issue lv-warn">{e}</div>)}
        </div>
      )}
    </aside>
  );
}
