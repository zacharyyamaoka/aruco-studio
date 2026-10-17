// The IDs table: one row per scene tag (core.marker_table's columns: name,
// type, dictionary, ids, status), the typed first id (an override), and
// "Renumber all" (core.numbering through the scene's ledger). Click a row
// to select its tag; double-click zooms to it.
import { useMemo } from "react";
import { duplicates, idsText } from "../model/scene";
import { useStudio } from "../store";
import { Icon, IconButton, NumberInput } from "../ui/controls";

export function IdsTable() {
  const scene = useStudio((s) => s.scene);
  const sel = useStudio((s) => s.sel);
  const dicts = useStudio((s) => s.dictionaries);
  const report = useStudio((s) => s.renumberReport);
  const st = useStudio.getState();
  const familyOf = useMemo(() => {
    const m = Object.fromEntries(dicts.map((d) => [d.name, d.family]));
    return (d: string) => m[d] ?? d;
  }, [dicts]);
  const dup = duplicates(scene.tags, familyOf);
  const dupOf = (name: string) => Object.entries(dup).filter(([, v]) => v.includes(name)).map(([k]) => k);
  const changed = new Set((report?.changed ?? []).map((c) => c.tag));
  const nDup = Object.keys(dup).length;
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
              return (
                <tr key={t.uid} data-ids-row={t.name} className={`${sel.includes(t.name) ? "on" : ""}${d.length ? " dup" : ""}${t.hidden ? " hid" : ""}`}
                  onClick={(e) => st.select(t.name, e.shiftKey || e.ctrlKey)} onDoubleClick={() => st.zoomToFit([t.name])}>
                  <td className="nm"><Icon name={String(t.spec.settings.layout ?? "single")} />{t.name}</td>
                  <td className="muted">{m ? String(m.dictionary).replace("DICT_", "") : "–"}</td>
                  <td className="idc" data-ids={(t.plan?.ids ?? []).join(",")}>{t.plan?.ok ? idsText(t.plan.ids) : <span className="bad">not built</span>}{changed.has(t.name) && <i className="chg" title="changed by the last Renumber">•</i>}</td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <NumberInput int path={`override:${t.name}`} value={typed ?? null} placeholder="auto"
                      onCommit={(v) => st.override(t.name, v)} />
                    {typed !== undefined && <IconButton icon="close" title="Back to auto" onClick={() => st.override(t.name, null)} />}
                  </td>
                  <td className="st">
                    {t.locked && <span title="locked: a printed tag keeps its ids"><Icon name="lock" /></span>}
                    {d.length > 0 && <span className="warn" title={`also printed by ${d.map((k) => dup[k].filter((x) => x !== t.name).join(", ")).join("; ")}`}><Icon name="warn" /></span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!scene.tags.length && <div className="muted pad">No tags yet.</div>}
      </div>
      {report && (report.errors.length > 0 || report.warnings.length > 0) && (
        <div className="msgs" data-issues-for="renumber">
          {report.errors.map((e, i) => <div key={`e${i}`} className="issue lv-error">{e.replace(/\|tag/g, "")}</div>)}
          {report.warnings.map((e, i) => <div key={`w${i}`} className="issue lv-warn">{e.replace(/\|tag/g, "")}</div>)}
        </div>
      )}
    </aside>
  );
}
