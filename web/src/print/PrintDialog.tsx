// Export › Print…: every feature on the preset's page from core.sheet() (one
// sheet item per feature, model/doc.ts sheetItems), at true scale (CSS
// millimetres are real millimetres at 100 % zoom), with a 50 mm scale bar
// to measure on screen (the core's page carries its own bar for paper). Print opens the browser's dialog on a print-only page (the
// sheet's SVG at 100 %, @page sized to the paper); Download PDF / SVG save
// the core's own files.
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Button, Dialog, Messages, SegmentedRow } from "@bam/ui";
import type { Sheet } from "../core/contract";
import { core } from "../coreSource";
import { downloadBase64, downloadText, slug } from "../io/files";
import { sheetItems } from "../model/doc";
import { useStudio } from "../store";

const MM_PX = 96 / 25.4;

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

export function PrintDialog() {
  const open = useStudio((s) => s.modal === "print");
  const doc = useStudio((s) => s.doc);
  const [sheet, setSheet] = useState<Sheet | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"actual" | "fit">("actual");
  const [printing, setPrinting] = useState(false);
  const items = open ? sheetItems(doc) : [];
  const key = JSON.stringify(items);

  useEffect(() => {
    if (!open) { setSheet(null); setError(null); return; }
    if (!items.length) { setError("Nothing to print yet: make an ArUco Extrude (A) first."); return; }
    let live = true;
    setSheet(null);
    setError(null);
    core.sheet({ items, cut_lines: true }).then((s) => { if (live) setSheet(s); }).catch((e) => { if (live) setError((e as Error).message); });
    return () => { live = false; };
  }, [open, key]);

  const page = sheet?.svg[0] ?? "";
  const fallback = (doc.preset?.page_mm ?? [215.9, 279.4]) as [number, number];
  const [pw, ph] = page ? svgSizeMm(page, fallback) : fallback;
  const fitK = Math.min(1, 560 / (pw * MM_PX), 520 / (ph * MM_PX));
  const k = mode === "fit" ? fitK : 1;
  const name = slug(doc.name);

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
      <Dialog open={open} onClose={() => useStudio.getState().openModal(null)} title="Print" icon="print" testid="print-dialog" width={860}
        footer={
          <>
            <SegmentedRow compact value={mode} onChange={(v) => setMode(v as "actual" | "fit")} testid="print-mode"
              options={[{ value: "actual", label: "Actual size" }, { value: "fit", label: "Fit" }]} />
            <span className="grow" />
            <Button onClick={() => sheet && downloadText(`${name}-page.svg`, page, "image/svg+xml")} disabled={!sheet} testid="print-svg">Download SVG</Button>
            <Button onClick={() => sheet && downloadBase64(`${name}.pdf`, sheet.pdf_base64, "application/pdf")} disabled={!sheet?.pdf_base64} testid="print-pdf">Download PDF</Button>
            <Button variant="primary" onClick={doPrint} disabled={!sheet} testid="print-go">Print</Button>
          </>
        }>
        <div className="print-head">
          <span>{doc.preset ? `${doc.preset.name} · ${pw} × ${ph} mm` : ""}</span>
          <span className="muted">Print at 100 % (Scale: Default / Actual size). “Fit to page” changes the marker’s size.</span>
        </div>
        {error && <div className="print-error">{error}</div>}
        {sheet && <Messages path="sheet" issues={sheet.warnings.map((i) => ({ field: i.field, level: i.level, text: i.text }))} />}
        <div className="print-stage" data-testid="print-stage" data-mode={mode}>
          {!sheet && !error && <div className="muted pad">Laying out the page…</div>}
          {sheet && (
            <div className="print-scaled" style={{ width: pw * MM_PX * k, height: (ph + 16) * MM_PX * k }}>
              <div style={{ transform: `scale(${k})`, transformOrigin: "0 0", width: `${pw}mm` }}>
                  <ScaleBar />
                <div className="print-page" data-testid="print-page" data-page-mm={`${pw}x${ph}`} style={{ width: `${pw}mm`, height: `${ph}mm` }}
                  dangerouslySetInnerHTML={{ __html: page }} />
              </div>
            </div>
          )}
        </div>
        {sheet && sheet.pages > 1 && <div className="muted pad">{sheet.pages} pages: the first is shown; Print and PDF have them all.</div>}
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
