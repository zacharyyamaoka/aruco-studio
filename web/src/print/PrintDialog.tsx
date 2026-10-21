// The Sheet dialog (V1 "Click-to-inspect", 2026-10-18: a dialog off the
// bottom toolbar's Sheet, modal "print"): every feature on the preset's page
// from core.sheet() (one sheet item per feature, model/doc.ts sheetItems),
// at true scale (CSS millimetres are real millimetres at 100 % zoom), with a
// 50 mm scale bar to measure on screen (the core's page carries its own bar
// for paper). Beside the page: the auto layout (Tight | Spaced, the gap,
// Optimize: Fewest cuts | Fewest sheets), the core's pages, cuts and fill,
// and Print / PDF / SVG. Every change lays the sheet out again. Print opens
// the browser's dialog on a print-only page (the sheet's SVGs at 100 %,
// @page sized to the paper); Download PDF / SVG save the core's own files.
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Button, Dialog, FieldRow, Messages, NumberField, Section, SegmentedRow } from "@bam/ui";
import type { Sheet, SheetMode, SheetRequest } from "../core/contract";
import { core } from "../coreSource";
import { downloadBase64, downloadText, slug } from "../io/files";
import { sheetItems } from "../model/doc";
import { CoreWait, WaitLine, useCallWait, useCoreWait } from "../panel/Waiting";
import { useStudio } from "../store";
import "./sheet.css";

const MM_PX = 96 / 25.4;
const GAP_MM = 4;              // core.sheet's SheetSettings.gap_mm, the field's first value
type Objective = NonNullable<SheetRequest["objective"]>;

/** The page size an SVG states in mm ("215.9mm"), else the fallback. */
export function svgSizeMm(svg: string, fallback: [number, number]): [number, number] {
  const head = svg.slice(0, 400);
  const w = /\swidth="([\d.]+)mm"/.exec(head), h = /\sheight="([\d.]+)mm"/.exec(head);
  return w && h ? [Number(w[1]), Number(h[1])] : fallback;
}

function ScaleBar() {
  return (
    <div className="scalebar" data-testid="scale-bar" style={{ width: "50mm" }}>
      <div className="scalebar-ticks">{Array.from({ length: 11 }, (_, i) => <i key={i} style={{ left: `${i * 5}mm` }} className={i % 2 ? "" : "major"} />)}</div>
      <div className="scalebar-text"><span>0</span><span>50 mm: measure it to check the print scale</span></div>
    </div>
  );
}

function Stat({ value, label, testid, raw }: { value: string; label: string; testid: string; raw: number | undefined }) {
  return <div data-testid={testid} data-value={raw ?? ""}><b>{value}</b><span>{label}</span></div>;
}

export function PrintDialog() {
  const open = useStudio((s) => s.modal === "print");
  const doc = useStudio((s) => s.doc);
  // the sheet on screen and the request it was laid out from
  const [laid, setLaid] = useState<{ key: string; sheet: Sheet } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"actual" | "fit">("actual");
  const [layout, setLayout] = useState<SheetMode>("spaced");
  const [gap, setGap] = useState(GAP_MM);
  const [objective, setObjective] = useState<Objective>("fewest_sheets");
  const [shown, setShown] = useState(0);
  const [printing, setPrinting] = useState(false);
  /** Retry's count: a new one lays the sheet out again */
  const [tries, setTries] = useState(0);
  const stage = useRef<HTMLDivElement>(null);
  const [room, setRoom] = useState<[number, number]>([820, 600]);
  const items = open ? sheetItems(doc) : [];
  const req: SheetRequest = { items, cut_lines: true, mode: layout, objective, ...(layout === "spaced" ? { gap_mm: gap } : {}) };
  const key = JSON.stringify(req);

  useEffect(() => {
    if (!open) { setLaid(null); setError(null); setShown(0); return; }
    // features but no preset yet: they plan once the core's presets are in (CoreWait says which wait)
    if (!items.length && doc.features.length && !doc.preset) { setError(null); return; }
    if (!items.length) { setError("Nothing to print yet: make an ArUco Extrude (A) first."); return; }
    let live = true;
    // the last layout stays on screen while the next one is worked out
    setError(null);
    core.sheet(req).then((s) => { if (live) setLaid({ key, sheet: s }); })
      .catch((e) => { if (live) { setLaid(null); setError((e as Error).message); } });
    return () => { live = false; };
  }, [open, key, tries]);

  // Fit: the page and its scale bar inside the stage as it is now
  useEffect(() => {
    const el = stage.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setRoom([el.clientWidth - 32, el.clientHeight - 32]));
    ro.observe(el);
    return () => ro.disconnect();
  }, [open]);

  const sheet = laid?.sheet ?? null;
  const busy = !!laid && laid.key !== key && !error;
  const coreWait = useCoreWait(open && !doc.preset);
  const callWait = useCallWait(open && !coreWait && !!items.length && laid?.key !== key, items.length ? error : null, "laying out the page", () => setTries((n) => n + 1));

  const pageIndex = sheet ? Math.min(shown, sheet.svg.length - 1) : 0;
  const page = sheet?.svg[pageIndex] ?? "";
  const fallback = (doc.preset?.page_mm ?? [215.9, 279.4]) as [number, number];
  const [pw, ph] = page ? svgSizeMm(page, fallback) : fallback;
  const fitK = Math.max(0.1, Math.min(1, room[0] / (pw * MM_PX), room[1] / ((ph + 16) * MM_PX)));
  const k = mode === "fit" ? fitK : 1;
  const name = slug(doc.name);
  const many = (sheet?.svg.length ?? 0) > 1;

  const doPrint = () => {
    setPrinting(true);
    // the print-only page mounts first, then the browser's dialog opens
    requestAnimationFrame(() => requestAnimationFrame(() => {
      const hook = (window as unknown as { __aruco?: { printHook?: (() => void) | null } }).__aruco?.printHook;
      if (hook) hook(); else window.print();
      setPrinting(false);
    }));
  };

  return (
    <>
      <Dialog open={open} onClose={() => useStudio.getState().openModal(null)} title={doc.preset ? `Sheet · ${doc.preset.name}` : "Sheet"}
        icon="print" testid="print-dialog" width={1180} className="sheet-dialog">
        <div className="sheet-body" data-busy={busy ? "1" : "0"}>
          <div className="sheet-view">
            <div className="sheet-view-head">
              {many && sheet && (
                <div className="sheet-tabs" role="tablist" data-testid="sheet-page-tabs">
                  {sheet.svg.map((_, i) => (
                    <button key={i} type="button" role="tab" aria-selected={i === pageIndex} className={i === pageIndex ? "on" : ""}
                      data-page={i + 1} data-testid="sheet-page-tab" onClick={() => setShown(i)}>Page {i + 1}</button>
                  ))}
                </div>
              )}
              <span className="muted sheet-paper">{`${pw} × ${ph} mm`}</span>
              <span className="grow" />
              <SegmentedRow compact value={mode} onChange={(v) => setMode(v as "actual" | "fit")} testid="print-mode"
                options={[{ value: "actual", label: "Actual size" }, { value: "fit", label: "Fit" }]} />
            </div>
            {coreWait ? <CoreWait needFacts={!doc.preset} testid="print-wait" />
              : callWait ? <div className="print-error"><WaitLine wait={callWait} testid="print-wait" /></div>
              : error && <div className="print-error">{error}</div>}
            <div className="print-stage sheet-stage" data-testid="print-stage" data-mode={mode} ref={stage}>
              {!sheet && !error && !coreWait && !callWait && <div className="muted pad">Laying out the page…</div>}
              {sheet && (
                <div className="print-scaled" style={{ width: pw * MM_PX * k, height: (ph + 16) * MM_PX * k }}>
                  <div style={{ transform: `scale(${k})`, transformOrigin: "0 0", width: `${pw}mm` }}>
                    <ScaleBar />
                    <div className="print-page" data-testid="print-page" data-page={pageIndex + 1} data-page-mm={`${pw}x${ph}`} style={{ width: `${pw}mm`, height: `${ph}mm` }}
                      dangerouslySetInnerHTML={{ __html: page }} />
                  </div>
                </div>
              )}
            </div>
          </div>
          <div className="sheet-side" data-testid="sheet-side" data-request={laid?.key ?? ""}>
            <Section title="Auto layout" testid="sheet-layout">
              <FieldRow path="sheet.mode" label="Layout">
                <SegmentedRow compact value={layout} onChange={(v) => setLayout(v as SheetMode)} testid="sheet-mode"
                  options={[{ value: "tight", label: "Tight" }, { value: "spaced", label: "Spaced" }]} />
              </FieldRow>
              <div className="sheet-note muted">{layout === "tight" ? "edge to edge: neighbours share cut lines" : "a gap round every sticker"}</div>
              {layout === "spaced" && (
                <FieldRow path="sheet.gap_mm" label="Gap">
                  <span data-testid="sheet-gap"><NumberField value={gap} unit="mm" min={0} step={0.5} path="sheet.gap_mm" onCommit={setGap} /></span>
                </FieldRow>
              )}
              <FieldRow path="sheet.objective" label="Optimize">
                <SegmentedRow compact value={objective} onChange={(v) => setObjective(v as Objective)} testid="sheet-objective"
                  options={[{ value: "fewest_cuts", label: "Fewest cuts" }, { value: "fewest_sheets", label: "Fewest sheets" }]} />
              </FieldRow>
            </Section>
            <div className="sheet-stats" data-testid="sheet-stats">
              <Stat testid="sheet-pages" raw={sheet?.pages} value={sheet ? String(sheet.pages) : "–"} label={sheet?.pages === 1 ? "page" : "pages"} />
              <Stat testid="sheet-cuts" raw={sheet?.cuts} value={sheet?.cuts !== undefined ? String(sheet.cuts) : "–"} label="straight cuts" />
              <Stat testid="sheet-fill" raw={sheet?.fill} value={sheet?.fill !== undefined ? `${Math.round(sheet.fill * 100)}%` : "–"} label="fill" />
            </div>
            {sheet && <Messages path="sheet" issues={sheet.warnings.map((i) => ({ field: i.field, level: i.level, text: i.text }))} />}
            <div className="sheet-note muted">Print at 100 % (Scale: Default / Actual size): “Fit to page” changes the marker’s size. The grey lines are the cuts.</div>
            <div className="sheet-actions">
              <Button variant="primary" icon="print" onClick={doPrint} disabled={!sheet} testid="print-go">Print</Button>
              <Button onClick={() => sheet && downloadBase64(`${name}.pdf`, sheet.pdf_base64, "application/pdf")} disabled={!sheet?.pdf_base64} testid="print-pdf">Download PDF</Button>
              <Button onClick={() => sheet && downloadText(many ? `${name}-page-${pageIndex + 1}.svg` : `${name}-page.svg`, page, "image/svg+xml")} disabled={!sheet} testid="print-svg">Download SVG</Button>
            </div>
          </div>
        </div>
      </Dialog>
      {open && sheet && createPortal(
        <div id="print-root" data-printing={printing ? "1" : "0"}>
          <style>{`@page { size: ${pw}mm ${ph}mm; margin: 0; }`}</style>
          {sheet.svg.map((s, i) => (
            <div key={i} className="print-sheet" style={{ width: `${pw}mm`, height: `${ph}mm` }}>
              <div dangerouslySetInnerHTML={{ __html: s }} />
            </div>
          ))}
        </div>,
        document.body,
      )}
    </>
  );
}
