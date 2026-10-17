// The Studio's dialogs, on the kit's Dialog:
// * New scene / Open / Save as. There is no Save: the open file is written on
//   every change. A new scene is a new file in the scenes folder; Open takes
//   a scene of the folder or a file anywhere (a path); Save as copies the
//   design and follows that file from then on.
// * Sticker sheet… (M6b): page, landscape, Spaced / Tight, the margin; the
//   preview is the server's own sheet.svg (the same layout as the PDF), the
//   rejected stickers with their reasons; Print and Export (sheet.pdf,
//   sheet.svg, sheet.json and the rest of the print bundle).
// * Send to PrusaSlicer… (M8c's route): the physical printer (the current
//   one first), a print preset that fits it, the white and black slots.
// * Print's fallback (M6c): Open the PDF, then Ctrl+P at Actual size.
import { Badge, Button, Dialog, FieldRow, NumberField, Select, SegmentedRow, Switch, Glyph as Icon } from "@bam/ui";
import { useEffect, useMemo, useState } from "react";
import { api, errorText, ApiError } from "../api/client";
import type { PrusaPrinter, SheetJson } from "../api/types";
import { useStudio } from "../store";
import { printBlock, sendBlock } from "./Print";
import { kinds } from "./Toolbar";

export function Dialogs() {
  const d = useStudio((s) => s.dialog);
  if (!d) return null;
  if (d.kind === "sheet") return <SheetDialog />;
  if (d.kind === "send") return <SendDialog />;
  if (d.kind === "print") return <PrintFallback url={d.url} why={d.why} />;
  return <FileDialog kind={d.kind} />;
}

function FileDialog({ kind }: { kind: "new" | "open" | "save" }) {
  const name = useStudio((s) => s.scene.name);
  const st = useStudio.getState();
  const [text, setText] = useState(kind === "new" ? "scene" : name);
  const [path, setPath] = useState("");
  const [list, setList] = useState<{ name: string; modified: string; bytes: number }[] | null>(null);
  useEffect(() => { if (kind === "open") api.scenes().then(setList).catch(() => setList([])); }, [kind]);
  const close = () => st.setDialog(null);
  const ok = async () => {
    const v = (kind === "open" ? path : text).trim();
    if (!v) return;
    close();
    if (kind === "new") await st.newScene(v);
    if (kind === "save") await st.saveAs(v);
    if (kind === "open") await st.openPath(v);
  };
  const keys = (e: React.KeyboardEvent) => { if (e.key === "Enter") ok(); e.stopPropagation(); };
  return (
    <Dialog open onClose={close} testid={`dialog-${kind}`} icon={kind === "open" ? "open" : kind === "new" ? "newdoc" : "save"}
      title={kind === "open" ? "Open a design file" : kind === "new" ? "New scene (a new file)" : "Save the scene as"}
      footer={<>
        <Button onClick={close}>Cancel</Button>
        <Button variant="primary" onClick={ok} testid="dialog-ok">{kind === "new" ? "Create" : kind === "open" ? "Open" : "Save as"}</Button>
      </>}>
      {kind !== "open" && (
        <div className="dlg-pad" onKeyDown={keys}>
          <input autoFocus className="kit-text" value={text} data-testid="dialog-name" onChange={(e) => setText(e.target.value)} />
          <div className="muted" style={{ marginTop: 6 }}>{kind === "new"
            ? "A name makes scenes/<name>.arucostudio.json; every change is written to it."
            : "A name (the scenes folder) or a whole path. The Studio then follows that file."}</div>
        </div>
      )}
      {kind === "open" && (
        <>
          <div className="scenes">
            {list === null && <div className="muted">…</div>}
            {list && !list.length && <div className="muted">No saved scenes yet.</div>}
            {list && list.map((x) => (
              <button key={x.name} className="scene-item" data-scene={x.name} onClick={async () => { close(); await st.openScene(x.name); }}>
                <Icon name="file" /><span>{x.name}</span><span className="muted">{x.modified.replace("T", " ")} · {(x.bytes / 1024).toFixed(1)} kB</span>
              </button>
            ))}
          </div>
          <div className="dlg-pad" onKeyDown={keys}>
            <input className="kit-text" placeholder="or a file's path: C:\…\name.arucostudio.json" value={path} data-testid="dialog-path"
              onChange={(e) => setPath(e.target.value)} />
          </div>
        </>
      )}
    </Dialog>
  );
}

const PAGES = [
  { value: "letter", label: "Letter (216 × 279 mm)" }, { value: "a4", label: "A4 (210 × 297 mm)" },
  { value: "legal", label: "Legal (216 × 356 mm)" }, { value: "a3", label: "A3 (297 × 420 mm)" },
  { value: "tabloid", label: "Tabloid (279 × 432 mm)" }, { value: "a5", label: "A5 (148 × 210 mm)" },
];

const msgOf = (e: unknown) => e instanceof ApiError ? errorText((e.detail as any)?.detail ?? e.detail) : String(e);

/** The sticker sheet dialog (M6b.6): the preview is the server's SVG. */
function SheetDialog() {
  const st = useStudio.getState();
  const sheet = useStudio((s) => s.sheet);
  const rev = useStudio((s) => s.sceneRev);
  const [svg, setSvg] = useState<string>("");
  const [json, setJson] = useState<SheetJson | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [files, setFiles] = useState<string[] | null>(null);
  const [busy, setBusy] = useState(false);
  const key = JSON.stringify(sheet);
  useEffect(() => {
    let live = true;
    setErr(null);
    Promise.all([api.sheetSvg(sheet), api.sheetJson(sheet)])
      .then(([s, j]) => { if (live) { setSvg(s); setJson(j); } })
      .catch((e) => { if (live) { setErr(msgOf(e)); setSvg(""); setJson(null); } });
    return () => { live = false; };
  }, [key, rev]);
  const noPrint = printBlock(kinds().stickers);
  const close = () => st.setDialog(null);
  const stickers = json?.stickers ?? [];
  return (
    <Dialog open onClose={close} testid="dialog-sheet" icon="sticker" title="Sticker sheet" width={860}
      footer={<>
        <span className="muted grow">{noPrint ?? "Print at 100 % (Actual size): the 100 mm bar says so."}</span>
        <Button onClick={close} testid="sheet-close">Close</Button>
        <Button icon="print" disabled={!!noPrint || busy} onClick={() => st.printSheet()} testid="sheet-print">Print…</Button>
        <Button variant="primary" icon="export" disabled={!!noPrint || busy} testid="sheet-export"
          onClick={async () => { setBusy(true); try { setFiles(await st.exportSheet()); } finally { setBusy(false); } }}>Export</Button>
      </>}>
      <div className="sheet-dlg">
        <div className="sheet-side">
          <FieldRow path="sheet.page" label="Page">
            <Select path="sheet.page" value={sheet.page} options={PAGES} onChange={(v) => st.setSheet({ page: String(v) })} />
          </FieldRow>
          <FieldRow path="sheet.landscape" label="Landscape">
            <Switch path="sheet.landscape" value={sheet.landscape} onChange={(v) => st.setSheet({ landscape: v })} />
          </FieldRow>
          <FieldRow path="sheet.mode" label="Layout">
            <SegmentedRow path="sheet.mode" compact value={sheet.mode} onChange={(v) => st.setSheet({ mode: v as "spaced" | "tight" })}
              options={[{ value: "spaced", label: "Spaced", hint: "gaps between stickers, a caption under each, crop marks" },
                { value: "tight", label: "Tight", hint: "no gaps: neighbours share a cut line (fewer cuts)" }]} />
          </FieldRow>
          <FieldRow path="sheet.margin_mm" label="Margin">
            <NumberField path="sheet.margin_mm" value={sheet.margin_mm} unit="mm" step={1} min={0} max={50} onCommit={(v) => st.setSheet({ margin_mm: v })} />
          </FieldRow>
          <div className="sheet-stats" data-testid="sheet-stats" data-stickers={stickers.length} data-pages={json?.pages ?? 0} data-cuts={json?.cuts ?? ""}>
            <Badge tone="accent">{stickers.length} sticker{stickers.length === 1 ? "" : "s"}</Badge>
            <Badge>{json?.pages ?? 0} page{json?.pages === 1 ? "" : "s"}</Badge>
            {sheet.mode === "tight" && json && <Badge>{json.cuts} cuts · {json.shelves.length} shelves</Badge>}
          </div>
          {err && <div className="msgs dlg-pad"><div className="issue lv-error">{err}</div></div>}
          {(json?.rejected ?? []).length > 0 && (
            <div className="sheet-rejected msgs" data-testid="sheet-rejected">
              {json!.rejected.map((r, i) => <div key={i} className="issue lv-warn">{String(r.name ?? r.key ?? "")}: {String(r.reason ?? "")}</div>)}
            </div>
          )}
          {files && (
            <div className="sheet-files" data-testid="sheet-files">
              {files.map((f) => <div key={f}>{f}</div>)}
            </div>
          )}
          <div className="dlg-note">Spaced puts the id and name under each sticker and crop marks at its corners. Tight packs the
            stickers in shelves that share their cut lines. The grey lines are the cut lines, holes included.</div>
        </div>
        <div className="sheet-preview" data-testid="sheet-preview" data-mode={sheet.mode} dangerouslySetInnerHTML={{ __html: svg }} />
      </div>
    </Dialog>
  );
}

/** Send to PrusaSlicer… (M8b2.3): the physical printer, a print that fits. */
function SendDialog() {
  const st = useStudio.getState();
  const printers = useStudio((s) => s.printers);
  const last = useStudio((s) => s.lastSend);
  const [printer, setPrinter] = useState<string | null>(null);
  const [print, setPrint] = useState<string | null>(null);
  const [white, setWhite] = useState(1);
  const [black, setBlack] = useState(2);
  const [open, setOpen] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { useStudio.setState({ lastSend: null }); void st.loadPrinters(); }, []);
  const list = useMemo(() => {
    const ps = printers?.printers ?? [];
    return [...ps.filter((p) => p.current), ...ps.filter((p) => !p.current)];
  }, [printers]);
  useEffect(() => { if (list.length && printer === null) setPrinter(list[0].name); }, [list]);
  const cur: PrusaPrinter | undefined = list.find((p) => p.name === printer);
  useEffect(() => {
    if (!cur) return;
    const want = cur.current_print && cur.prints.some((x) => x.name === cur.current_print) ? cur.current_print
      : (cur.prints.find((x) => x.aruco) ?? cur.prints[0])?.name ?? null;
    setPrint(want);
  }, [cur?.name]);
  const k = kinds();
  const noSend = sendBlock(k.printed, k.stickers);
  const close = () => st.setDialog(null);
  const send = async () => {
    if (!cur) return;
    setBusy(true);
    setErr(null);
    try {
      // the tests keep PrusaSlicer closed (window.__studio.sendOpen = false)
      const allowOpen = (window as any).__studio?.sendOpen !== false;
      const a = await api.sendPrusa({ printer: cur.name, ...(print ? { print } : {}), white_slot: white, black_slot: black, open: open && allowOpen });
      useStudio.setState({ lastSend: a });
      st.say(`Send to PrusaSlicer: ${a.project}${a.opened ? " (opened in PrusaSlicer)" : ""}`);
    } catch (e) {
      setErr(msgOf(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open onClose={close} testid="dialog-send" icon="send" title="Send to PrusaSlicer" width={480}
      footer={<>
        <Button onClick={close} testid="send-close">{last ? "Close" : "Cancel"}</Button>
        <Button variant="primary" icon="send" disabled={!!noSend || !cur || busy || white === black} onClick={send} testid="send-go">Send</Button>
      </>}>
      {!printers && <div className="dlg-pad muted">Reading PrusaSlicer's printers…</div>}
      {printers && !printers.found && <div className="dlg-pad muted" data-testid="send-none">PrusaSlicer's folder was not found: {(printers.notes ?? []).join(" ")}</div>}
      {printers?.found && (
        <>
          <FieldRow path="send.printer" label="Printer">
            <Select path="send.printer" value={printer} wide onChange={(v) => setPrinter(String(v))}
              options={list.map((p) => ({ value: p.name, label: `${p.name}${p.current ? " (current)" : ""}`, icon: "printer", hint: `${p.printer.model} ${p.printer.variant} · nozzle ${p.printer.nozzle_mm} mm` }))} />
          </FieldRow>
          {cur && <div className="dlg-note" data-testid="send-printer-info">{cur.printer.preset} · nozzle {cur.printer.nozzle_mm} mm · bed {cur.printer.bed_mm?.join(" × ")} mm</div>}
          <FieldRow path="send.print" label="Print preset">
            <Select path="send.print" value={print} wide onChange={(v) => setPrint(String(v))} placeholder={cur && !cur.prints.length ? "none fits this printer" : "–"}
              options={(cur?.prints ?? []).map((x) => ({ value: x.name, label: `${x.name}${x.current ? " (current)" : ""}`, icon: x.aruco ? "star" : "t-print",
                hint: `layer ${x.layer_mm} mm · line ${x.line_mm} mm${x.fits === "maybe" ? " · may fit (the nozzle fits)" : ""}` }))} />
          </FieldRow>
          <FieldRow path="send.white" label="White on extruder">
            <NumberField path="send.white" int min={1} max={16} value={white} onCommit={setWhite} />
          </FieldRow>
          <FieldRow path="send.black" label="Black on extruder" issues={white === black ? [{ field: "send.black", level: "error", text: "the black and the white on one extruder" }] : []}>
            <NumberField path="send.black" int min={1} max={16} value={black} onCommit={setBlack} />
          </FieldRow>
          <FieldRow path="send.open" label="Open PrusaSlicer">
            <Switch path="send.open" value={open} onChange={setOpen} label="the project, as a project" />
          </FieldRow>
        </>
      )}
      {noSend && <div className="msgs dlg-pad"><div className="issue lv-warn">{noSend}</div></div>}
      {err && <div className="msgs dlg-pad" data-testid="send-error"><div className="issue lv-error">{err}</div></div>}
      {last && (
        <div className="send-answer" data-testid="send-answer" data-project={last.project}>
          <div><b>Written:</b> <span className="path">{last.project}</span></div>
          <div className="muted">{Array.isArray(last.parts) ? last.parts.length : last.parts} part(s) · {Array.isArray(last.beds) ? last.beds.length : last.beds} bed(s) · {last.print} · {last.opened ? "opened in PrusaSlicer" : "not opened"}</div>
          {(last.warnings ?? []).map((w, i) => <div key={i} className="issue lv-warn">{w}</div>)}
        </div>
      )}
    </Dialog>
  );
}

/** Print's fallback (M6c.3): the PDF in a new tab, then Ctrl+P. */
function PrintFallback({ url, why }: { url: string; why: string }) {
  const st = useStudio.getState();
  const close = () => st.setDialog(null);
  return (
    <Dialog open onClose={close} testid="dialog-print" icon="print" title="Print the sticker sheet"
      footer={<>
        <Button onClick={close}>Close</Button>
        <Button variant="primary" icon="open" testid="print-open" onClick={() => { window.open(url, "_blank", "noopener"); }}>Open the PDF</Button>
      </>}>
      <div className="print-note" data-testid="print-note">
        <div>{why}</div>
        <div><b>Open the PDF</b>, press <kbd>Ctrl</kbd>+<kbd>P</kbd> and choose <b>Actual size (100 %)</b>.</div>
        <div className="muted">The 100 mm bar on the page measures 100 mm when the scale is right.</div>
      </div>
    </Dialog>
  );
}

