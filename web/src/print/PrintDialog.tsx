// The Sheet dialog (V1 "Click-to-inspect", 2026-10-18: a dialog off Print,
// modal "print"): the inkjet features on their preset's page from
// core.sheet() (one sheet item per feature), one group per preset
// (model/doc.ts sheetGroups: each preset's page can differ), a section each
// when there are several; 3D-print features are not on paper, and a line says so.
// Every page is in one scroll, one under the other with "Page N of M", as a
// PDF viewer shows them; a page is drawn when it nears the view. The group
// in view (or whose heading was clicked) is the one the side's numbers, Print,
// PDF and SVG are for, and the page in view is SVG's.
// WHY one scroll (Zach, 2026-10-21): "make it just scroll down all in the
// main window, just like a normal PDF preview".
// Markers: All | Selected prints every marker or only the selected ones
// (app/commands.ts printSelection: it opens on Selected when 2+ are), with
// their ids as assigned.
// WHY per preset (Zach, 2026-10-20 night): "Preset shouldn't be on the file
// because it's applied on a per marker basis!"
// Each group's sheet is laid out at true scale (CSS millimetres are real millimetres at 100 % zoom), with a
// 50 mm scale bar to measure on screen (the core's page carries its own bar
// for paper, on the pages Scale bar says: Hide | First page | Every page, and
// the screen's follows the page). Beside the page: the auto layout (Tight | Spaced, the gap,
// Optimize: Fewest cuts | Fewest sheets), the core's pages, cuts and fill,
// and Print and Download (PDF / SVG). Every change lays the sheet out again. Print opens
// the browser's dialog on a print-only page (the sheet's SVGs at 100 %,
// @page sized to the paper); Download PDF / SVG save the core's own files.
import { useEffect, useRef, useState, type HTMLAttributes, type RefObject } from "react";
import { createPortal } from "react-dom";
import { Button, Dialog, FieldRow, Glyph, Menu, MenuItem, Messages, NumberField, Section, SegmentedRow } from "@bam/ui";
import type { Sheet, SheetMode, SheetRequest } from "../core/contract";
import { core } from "../coreSource";
import { downloadBase64, downloadText, slug } from "../io/files";
import { featurePreset, getFeature, presetKey, sheetGroups, withFeatures } from "../model/doc";
import { printSelection } from "../app/commands";
import { CoreWait, WaitLine, useCallWait, useCoreWait } from "../panel/Waiting";
import { activeFeatureId, selectedMarkerIds, useStudio } from "../store";
import "./sheet.css";

const MM_PX = 96 / 25.4;
const BAR_MARK = "must measure 100 mm";   // the caption core.sheet draws over the bar, on its pages only
const GAP_MM = 4;              // core.sheet's SheetSettings.gap_mm, the field's first value
const BAND_MM = 16;            // the screen's scale bar's band over a page that carries the bar
type Objective = NonNullable<SheetRequest["objective"]>;
type ScaleBarOption = NonNullable<SheetRequest["scale_bar"]>;
type Which = "all" | "selected";

/** The page size an SVG states in mm ("215.9mm"), else the fallback. */
export function svgSizeMm(svg: string, fallback: [number, number]): [number, number] {
  const head = svg.slice(0, 400);
  const w = /\swidth="([\d.]+)mm"/.exec(head), h = /\sheight="([\d.]+)mm"/.exec(head);
  return w && h ? [Number(w[1]), Number(h[1])] : fallback;
}

function ScaleBar({ onPage }: { onPage: boolean }) {
  // WHY (Zach, 2026-10-20 night): a page printed without the bar is previewed without it
  if (!onPage) return null;
  return (
    <div className="scalebar" data-testid="scale-bar" style={{ width: "50mm" }}>
      <div className="scalebar-ticks">{Array.from({ length: 11 }, (_, i) => <i key={i} style={{ left: `${i * 5}mm` }} className={i % 2 ? "" : "major"} />)}</div>
      <div className="scalebar-text"><span>0</span><span>50 mm: measure it to check the print scale</span></div>
    </div>
  );
}

/** One page in the scroll: drawn once it nears the view (a long sheet stays
 *  smooth), and kept drawn after. */
function PageSvg({ svg, root, ...attrs }: { svg: string; root: RefObject<HTMLDivElement | null> } & HTMLAttributes<HTMLDivElement> & Record<`data-${string}`, string | number>) {
  const ref = useRef<HTMLDivElement>(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || seen) return;
    const io = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) setSeen(true); },
      { root: root.current, rootMargin: "100% 0px" });
    io.observe(el);
    return () => io.disconnect();
  }, [seen]);
  return <div ref={ref} {...attrs} data-drawn={seen ? "1" : "0"} dangerouslySetInnerHTML={seen ? { __html: svg } : undefined} />;
}

function Stat({ value, label, testid, raw }: { value: string; label: string; testid: string; raw: number | undefined }) {
  return <div data-testid={testid} data-value={raw ?? ""}><b>{value}</b><span>{label}</span></div>;
}

export function PrintDialog() {
  const open = useStudio((s) => s.modal === "print");
  const doc = useStudio((s) => s.doc);
  const sel = useStudio((s) => s.sel);
  const multi = useStudio((s) => s.multi);
  // the sheets on screen, one per group (by its preset's key), and the request each was laid out from
  const [laidAll, setLaidAll] = useState<Record<string, { key: string; sheet: Sheet }>>({});
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"actual" | "fit">("actual");
  const [layout, setLayout] = useState<SheetMode>("spaced");
  const [gap, setGap] = useState(GAP_MM);
  const [objective, setObjective] = useState<Objective>("fewest_sheets");
  // WHY first (Zach, 2026-10-20 night): a printer's scale is the same for a whole job, and a bar on every page costs sticker area
  const [scaleBar, setScaleBar] = useState<ScaleBarOption>("first");
  /** the page in view, in the group in focus */
  const [shown, setShown] = useState(0);
  const [printing, setPrinting] = useState(false);
  /** the group in focus (its preset's key): the marker in focus's when it opens, then the one in view */
  const [groupKey, setGroupKey] = useState<string | null>(null);
  /** Markers: All | Selected, once chosen here; until then the selection decides (printSelection) */
  const [which, setWhich] = useState<Which | null>(null);
  /** Retry's count: a new one lays the sheet out again */
  const [tries, setTries] = useState(0);
  const stage = useRef<HTMLDivElement>(null);
  /** the group the view is being taken to: until it is in view, the scroll leaves the focus alone */
  const aim = useRef<string | null>(null);
  const [room, setRoom] = useState<[number, number]>([820, 600]);
  // the markers selected on the canvas (the dialog is modal: they hold while it is open)
  const picked = open ? selectedMarkerIds(doc, sel, multi) : [];
  const choice: Which = picked.length ? which ?? (printSelection() ? "selected" : "all") : "all";
  // the features that go into the requests: every one, or only the selected ones
  const source = choice === "selected" ? withFeatures(doc, picked) : doc;
  const groups = open ? sheetGroups(source) : [];
  const group = groups.find((g) => g.key === groupKey) ?? groups[0] ?? null;
  const items = group?.items ?? [];
  // the features without a preset yet (the core's presets have not arrived), and the 3D-printed ones
  const unset = source.features.filter((f) => !featurePreset(doc, f)).length;
  const printed3d = source.features.filter((f) => featurePreset(doc, f)?.method === "print3d").length;
  const settings: Omit<SheetRequest, "items"> = { cut_lines: true, mode: layout, objective, scale_bar: scaleBar, ...(layout === "spaced" ? { gap_mm: gap } : {}) };
  const req: SheetRequest = { items, ...settings };
  const key = JSON.stringify(req);
  // every group's request: each is laid out, the group in focus's first
  const reqs: SheetRequest[] = groups.map((g) => ({ items: g.items, ...settings }));
  const keys = reqs.map((r) => JSON.stringify(r));
  const allKey = JSON.stringify(keys);
  const laid = group ? laidAll[group.key] ?? null : null;

  // opening: the group of the marker in focus
  useEffect(() => {
    if (!open) { setGroupKey(null); setWhich(null); aim.current = null; return; }
    const s = useStudio.getState();
    const own = featurePreset(s.doc, getFeature(s.doc, activeFeatureId(s)));
    setGroupKey(own ? presetKey(own) : null);
    aim.current = own ? presetKey(own) : null;
  }, [open]);

  useEffect(() => {
    if (!open) { setLaidAll({}); setError(null); setShown(0); return; }
    // features but no preset yet: they plan once the core's presets are in (CoreWait says which wait)
    if (!groups.length && source.features.length && unset) { setError(null); return; }
    if (!groups.length) {
      setError(printed3d ? "Nothing on paper: every marker here is 3D printed." : "Nothing to print yet: make an ArUco Extrude (A) first.");
      return;
    }
    let live = true;
    // the last layout stays on screen while the next one is worked out
    setError(null);
    const first = groups.indexOf(group!);
    for (const i of [first, ...groups.keys()].filter((j, n, all) => all.indexOf(j) === n)) {
      const gk = groups[i].key;
      core.sheet(reqs[i]).then((s) => { if (live) setLaidAll((m) => ({ ...m, [gk]: { key: keys[i], sheet: s } })); })
        .catch((e) => {
          if (!live) return;
          setLaidAll((m) => Object.fromEntries(Object.entries(m).filter(([k]) => k !== gk)));
          setError((e as Error).message);
        });
    }
    return () => { live = false; };
  }, [open, allKey, tries]);

  // Fit: the page and its scale bar inside the stage as it is now
  useEffect(() => {
    const el = stage.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setRoom([el.clientWidth - 32, el.clientHeight - 32]));
    ro.observe(el);
    return () => ro.disconnect();
  }, [open]);

  /** Scroll the stage to group `i`'s heading. */
  const goTo = (i: number) => {
    const el = stage.current, sec = el?.querySelector<HTMLElement>(`[data-group-index="${i}"]`);
    if (el && sec) el.scrollTop += sec.getBoundingClientRect().top - el.getBoundingClientRect().top - 12;
  };
  // opening on another group than the first: the view goes to it once the pages above it are laid out
  useEffect(() => {
    if (!open || !aim.current) return;
    const i = groups.findIndex((g) => g.key === aim.current);
    if (i <= 0) { aim.current = null; return; }
    if (groups.slice(0, i + 1).every((g) => laidAll[g.key])) requestAnimationFrame(() => goTo(i));
  }, [open, laidAll]);

  /** The page a third of the way down the stage (the last one at the bottom)
   *  is the page in view, and its group is the group in focus. */
  const onScroll = () => {
    const el = stage.current;
    if (!el) return;
    const pages = [...el.querySelectorAll<HTMLElement>("[data-sheet-page]")];
    const line = el.getBoundingClientRect().top + el.clientHeight / 3;
    const atEnd = el.scrollTop + el.clientHeight >= el.scrollHeight - 1;
    const at = atEnd ? pages[pages.length - 1] : pages.filter((p) => p.getBoundingClientRect().top <= line).pop() ?? pages[0];
    const g = at ? groups[Number(at.dataset.group)] : null;
    if (!at || !g) return;
    if (aim.current) {
      if (g.key !== aim.current) return;
      aim.current = null;
    }
    setGroupKey(g.key);
    setShown(Number(at.dataset.page) - 1);
  };
  // a scroll by hand ends a pending go-to
  const byHand = () => { aim.current = null; };

  const sheet = laid?.sheet ?? null;
  const busy = !!laid && laid.key !== key && !error;
  const coreWait = useCoreWait(open && unset > 0);
  const callWait = useCallWait(open && !coreWait && !!items.length && laid?.key !== key, items.length ? error : null, "laying out the page", () => setTries((n) => n + 1));

  const pageIndex = sheet ? Math.min(shown, sheet.svg.length - 1) : 0;
  const page = sheet?.svg[pageIndex] ?? "";
  const fallback = (group?.preset.page_mm ?? [215.9, 279.4]) as [number, number];
  const [pw, ph] = page ? svgSizeMm(page, fallback) : fallback;
  /** a page's scale on screen: 1, or (Fit) the page and the bar's band inside the stage */
  const scaleOf = (w: number, h: number) => (mode === "fit" ? Math.max(0.1, Math.min(1, room[0] / (w * MM_PX), room[1] / ((h + BAND_MM) * MM_PX))) : 1);
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
      <Dialog open={open} onClose={() => useStudio.getState().openModal(null)} title={group ? `Sheet · ${group.preset.name}` : "Sheet"}
        icon="print" testid="print-dialog" width={1180} className="sheet-dialog">
        <div className="sheet-body" data-busy={busy ? "1" : "0"}>
          <div className="sheet-view">
            {printed3d > 0 && (
              <div className="sheet-3d muted" data-testid="sheet-3d-note">
                {printed3d === 1 ? "1 marker is 3D printed: it isn't on the paper sheet." : `${printed3d} markers are 3D printed: they aren't on the paper sheet.`}
              </div>
            )}
            <div className="sheet-view-head">
              <span className="muted sheet-paper">{`${pw} × ${ph} mm`}</span>
              <span className="grow" />
              <SegmentedRow compact value={mode} onChange={(v) => setMode(v as "actual" | "fit")} testid="print-mode"
                options={[{ value: "actual", label: "Actual size" }, { value: "fit", label: "Fit" }]} />
            </div>
            {coreWait ? <CoreWait needFacts={unset > 0} testid="print-wait" />
              : callWait ? <div className="print-error"><WaitLine wait={callWait} testid="print-wait" /></div>
              : error && <div className="print-error">{error}</div>}
            <div className="print-stage sheet-stage" data-testid="print-stage" data-mode={mode} ref={stage}
              onScroll={onScroll} onWheel={byHand} onPointerDown={byHand} onKeyDown={byHand}>
              {!sheet && groups.length <= 1 && !error && !coreWait && !callWait && <div className="muted pad">Laying out the page…</div>}
              {groups.map((g, gi) => {
                const got = laidAll[g.key];
                const fb = g.preset.page_mm as [number, number];
                const [gw, gh] = got ? svgSizeMm(got.sheet.svg[0] ?? "", fb) : fb;
                const k = scaleOf(gw, gh);
                const n = got?.sheet.svg.length ?? 0;
                return (
                  <section key={g.key} className="sheet-section" data-testid="sheet-section" data-group-index={gi} data-sheet-group={g.preset.id}
                    data-busy={got && got.key !== keys[gi] && !error ? "1" : "0"}>
                    {groups.length > 1 && (
                      <button type="button" className={g === group ? "sheet-section-head on" : "sheet-section-head"} aria-current={g === group ? "true" : undefined}
                        data-sheet-group={g.preset.id} data-testid="sheet-group" onClick={() => { aim.current = g.key; setGroupKey(g.key); setShown(0); goTo(gi); }}>
                        <Glyph name="inkjet" /><span>{g.preset.name}</span><span className="sheet-group-n">{g.items.length}</span>
                      </button>
                    )}
                    {!got && groups.length > 1 && <div className="muted pad">Laying out the page…</div>}
                    {got?.sheet.svg.map((svg, i) => {
                      // the core's page carries its bar as a text run; the screen's 50 mm bar follows it
                      const bar = svg.includes(BAR_MARK);
                      const [w, h] = svgSizeMm(svg, [gw, gh]);
                      return (
                        <div key={i} className="sheet-page" data-sheet-page="" data-testid="sheet-page" data-group={gi} data-page={i + 1}>
                          <div className="sheet-page-label muted" data-testid="sheet-page-label">{`Page ${i + 1} of ${n}`}</div>
                          <div className="print-scaled" style={{ width: w * MM_PX * k, height: (h + (bar ? BAND_MM : 0)) * MM_PX * k }}>
                            <div style={{ transform: `scale(${k})`, transformOrigin: "0 0", width: `${w}mm` }}>
                              <ScaleBar onPage={bar} />
                              <PageSvg svg={svg} root={stage} className="print-page" data-testid="print-page" data-page={i + 1} data-scale-bar={bar ? "1" : "0"}
                                data-page-mm={`${w}x${h}`} style={{ width: `${w}mm`, height: `${h}mm` }} />
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </section>
                );
              })}
            </div>
          </div>
          <div className="sheet-side" data-testid="sheet-side" data-request={laid?.key ?? ""}>
            <Section title="Print" testid="sheet-markers">
              <FieldRow path="sheet.markers" label="Markers">
                <SegmentedRow compact value={choice} onChange={(v) => setWhich(v as Which)} testid="sheet-which"
                  options={[{ value: "all", label: `All (${doc.features.length})` }, { value: "selected", label: `Selected (${picked.length})`, disabled: !picked.length }]} />
              </FieldRow>
              <div className="sheet-note muted">{picked.length ? `${picked.length} selected on the canvas, with their ids` : "select markers on the canvas (right-drag, Shift+click) to print only those"}</div>
            </Section>
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
              <FieldRow path="sheet.scale_bar" label="Scale bar">
                <SegmentedRow compact value={scaleBar} onChange={(v) => setScaleBar(v as ScaleBarOption)} testid="sheet-scale-bar"
                  options={[{ value: "hide", label: "Hide" }, { value: "first", label: "First page" }, { value: "every", label: "Every page" }]} />
              </FieldRow>
              <div className="sheet-note muted">{scaleBar === "hide" ? "no bar: measure a marker to check the print" : scaleBar === "first" ? "pages 2+ give the bar's band to stickers" : "the bar takes a band on every page"}</div>
            </Section>
            <div className="sheet-stats" data-testid="sheet-stats" data-placed={sheet?.placements?.length ?? ""}>
              <Stat testid="sheet-pages" raw={sheet?.pages} value={sheet ? String(sheet.pages) : "–"} label={sheet?.pages === 1 ? "page" : "pages"} />
              <Stat testid="sheet-cuts" raw={sheet?.cuts} value={sheet?.cuts !== undefined ? String(sheet.cuts) : "–"} label="straight cuts" />
              <Stat testid="sheet-fill" raw={sheet?.fill} value={sheet?.fill !== undefined ? `${Math.round(sheet.fill * 100)}%` : "–"} label="fill" />
            </div>
            {sheet && <Messages path="sheet" issues={sheet.warnings.map((i) => ({ field: i.field, level: i.level, text: i.text }))} />}
            <div className="sheet-note muted">Print at 100 % (Scale: Default / Actual size): “Fit to page” changes the marker’s size. The grey lines are the cuts.</div>
            {/* WHY one row (Zach, 2026-10-21: the third button wrapped to a line of
                its own): Print, and one Download menu for the files, as Figma's and Canva's */}
            <div className="sheet-actions">
              <Button variant="primary" icon="print" onClick={doPrint} disabled={!sheet} testid="print-go" className="sheet-print">Print</Button>
              <Menu icon="download" label="Download" testid="print-download" align="end">
                <MenuItem icon="download" label="PDF" hint={sheet ? `${sheet.svg.length} page${sheet.svg.length === 1 ? "" : "s"}` : undefined} testid="print-pdf"
                  onClick={() => sheet && downloadBase64(`${name}.pdf`, sheet.pdf_base64, "application/pdf")} disabled={!sheet?.pdf_base64} />
                <MenuItem icon="download" label="SVG" hint={many ? `page ${pageIndex + 1}` : undefined} testid="print-svg"
                  onClick={() => sheet && downloadText(many ? `${name}-page-${pageIndex + 1}.svg` : `${name}-page.svg`, page, "image/svg+xml")} disabled={!sheet} />
              </Menu>
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
