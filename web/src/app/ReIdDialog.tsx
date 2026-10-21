// Edit › ArUco Re-ID… (modal "reid"): give every driven marker new ids
// at once, Sequential (document order from Start, each grid / board a
// contiguous block) or a fresh hash. The table previews what the core would
// give out -- core.assign_ids({items, mode, start, fresh: true}), not applied
// -- with its collisions and capacity warnings; Apply puts that answer's ids
// and ledger into the document as one undo step (store.reId), Cancel
// changes nothing.
// WHY (Zach, 2026-10-20): "we should be able to have lots of the markers on a
// page and then re-id them". Typed ids always win (core/autoid.py rule 2).
import { useEffect, useState } from "react";
import { Badge, Button, Dialog, FieldRow, Glyph, Messages, NumberField, SegmentedRow, Switch } from "@bam/ui";
import type { IdAssignment, IdRequest, IdResult, Issue } from "../core/contract";
import { core } from "../coreSource";
import { featureNumber, idItems, idRange, isSet, type Feature } from "../model/doc";
import { WaitLine, useCallWait, useCoreWait } from "../panel/Waiting";
import { useStudio } from "../store";
import "./reid.css";

type How = "sequential" | "hash";

/** "#4" / "#4–7" from the ids given out; "—" when none could be. */
function newRange(a: IdAssignment | undefined): string {
  if (!a || !a.ids.length) return "—";
  return a.ids.length === 1 ? `#${a.ids[0]}` : `#${a.ids[0]}–${a.ids[a.ids.length - 1]}`;
}

function typeText(f: Feature): string {
  const m = f.marker;
  return m.type === "single" ? "Single" : `${m.type === "grid" ? "Grid" : "ChArUco"} ${m.cols}×${m.rows}`;
}

export function ReIdDialog() {
  const open = useStudio((s) => s.modal === "reid");
  const doc = useStudio((s) => s.doc);
  const [how, setHow] = useState<How>("sequential");
  const [start, setStart] = useState(0);
  // the preview on screen and the request it answers
  const [got, setGot] = useState<{ key: string; res: IdResult } | null>(null);
  const [error, setError] = useState<string | null>(null);
  /** Retry's count: a new one asks again */
  const [tries, setTries] = useState(0);
  const close = () => useStudio.getState().openModal(null);
  const items = open ? idItems(doc) : [];
  const req: IdRequest = { items, mode: how, fresh: true, ...(how === "sequential" ? { start } : {}) };
  const key = JSON.stringify(req);

  useEffect(() => {
    if (!open) { setGot(null); setError(null); return; }
    if (!items.length) { setGot(null); setError("No markers yet: make an ArUco Extrude (A) first."); return; }
    let live = true;
    setError(null);
    core.assign_ids(req).then((res) => { if (live) setGot({ key, res }); })
      .catch((e) => { if (live) { setGot(null); setError((e as Error).message); } });
    return () => { live = false; };
  }, [open, key, tries]);

  const res = got?.key === key ? got.res : null;
  // what the preview waits for: the core's start, else this call when it is slow or failed
  const coreWait = useCoreWait(false);
  const callWait = useCallWait(open && !coreWait && !!items.length && !res, items.length ? error : null, "working it out", () => setTries((n) => n + 1));
  const wait = open ? coreWait ?? callWait : null;
  // the kit's Messages take {field, level, text}
  const plain = (is: Issue[]) => is.map((i) => ({ field: i.field, level: i.level, text: i.text }));
  const byKey = (k: string) => plain((res?.warnings ?? []).filter((i) => i.key === k));
  const general = plain((res?.warnings ?? []).filter((i) => !i.key));
  const moved = res ? doc.features.filter((f, i) => newRange(res.items[i]) !== idRange(f.marker)).length : 0;
  const apply = () => {
    if (!res) return;
    useStudio.getState().reId(res);
    close();
  };

  return (
    <Dialog open={open} onClose={close} title="ArUco Re-ID" icon="marker" testid="reid-dialog" width={640} className="reid-dialog"
      footer={<>
        <span className="reid-sum muted" data-testid="reid-summary">
          {res ? `${moved} of ${doc.features.length} marker${doc.features.length === 1 ? "" : "s"} change` : wait ? <WaitLine wait={wait} testid="reid-wait" /> : error ? "" : "Working it out…"}
        </span>
        <span className="grow" />
        <Button onClick={close} testid="reid-cancel">Cancel</Button>
        <Button variant="primary" onClick={apply} disabled={!res} testid="reid-apply">Apply</Button>
      </>}>
      <div className="reid-form">
        <FieldRow path="reid.mode" label="How">
          <SegmentedRow compact value={how} onChange={(v) => setHow(v as How)} testid="reid-mode"
            options={[{ value: "sequential", label: "Sequential" }, { value: "hash", label: "Fresh hash" }]} />
        </FieldRow>
        <FieldRow path="reid.start" label="Start at">
          <span data-testid="reid-start"><NumberField value={start} int min={0} step={1} path="reid.start" disabled={how !== "sequential"}
            title={how === "sequential" ? "the first id given out (each dictionary family counts from here)" : "Sequential only"}
            onCommit={setStart} /></span>
        </FieldRow>
        <FieldRow path="reid.typed" label="Keep typed ids">
          <span className="reid-typed"><Switch value disabled onChange={() => {}} path="reid.typed" />
            <span className="muted">typed ids always win; untype them first to renumber them</span></span>
        </FieldRow>
        <div className="reid-issues" data-testid="reid-issues">
          {error && !wait && <Messages path="reid" issues={[{ field: "reid", level: "error", text: error }]} />}
          <Messages path="reid" issues={general} />
        </div>
      </div>
      <table className="reid-table" data-testid="reid-table">
        <thead><tr><th>Marker</th><th>Type</th><th>Old ids</th><th>New ids</th></tr></thead>
        <tbody>
          {doc.features.map((f, i) => {
            const a = res?.items[i];
            const typed = isSet(f, "marker.first_id");
            const iss = byKey(f.key);
            const was = idRange(f.marker), now = res ? newRange(a) : "…";
            return (
              <tr key={f.id} data-reid-row={f.id} data-old={was} data-new={now} data-typed={typed ? "1" : "0"}
                className={res && now !== was ? "changed" : undefined}>
                <td><b>ArUco Extrude {featureNumber(doc, f.id)}</b><span className="reid-key muted" title="the stable key auto id hashes">{f.key}</span></td>
                <td><span className="reid-type"><Glyph name={f.marker.type} />{typeText(f)}</span></td>
                <td className="num">{was}</td>
                <td className="num">
                  {now}{typed && <Badge tone="accent" title="typed by hand: kept as typed">typed</Badge>}
                  {iss.length > 0 && <Messages path={`reid.${f.key}`} issues={iss} />}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Dialog>
  );
}
