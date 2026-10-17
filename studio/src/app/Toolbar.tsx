// The top bar: the file (New, Open, Save as, Reveal: there is no Save, every
// change is written at once), edit (Undo, Redo, Rotate, Duplicate, Delete,
// Arrange), view (2D / 3D, quiet zones, axes, layer outlines, fit, the
// theme), Verify and Export (the sticker sheet, Print, Send to
// PrusaSlicer, the files). The tools are at the canvas's foot (BottomBar);
// S finds any command.
import { Glyph as Icon, IconButton, Menu, MenuItem, MenuSeparator, useTheme } from "@bam/ui";
import { madeBy, useStudio } from "../store";
import { printBlock, sendBlock } from "./Print";

/** How many tags of each kind the scene has (what Print and Send need). */
export function kinds(): { stickers: number; printed: number } {
  const tags = useStudio.getState().scene.tags.filter((t) => !t.hidden && t.plan?.ok);
  const stickers = tags.filter((t) => madeBy(t) === "sticker").length;
  return { stickers, printed: tags.length - stickers };
}

export function Toolbar() {
  const st = useStudio.getState();
  const view = useStudio((s) => s.view);
  const show = useStudio((s) => s.show);
  const sel = useStudio((s) => s.sel);
  const hist = useStudio((s) => s.hist);
  const busy = useStudio((s) => s.busy);
  const name = useStudio((s) => s.scene.name);
  const tags = useStudio((s) => s.scene.tags);
  const design = useStudio((s) => s.design);
  const shapes = useStudio((s) => s.shapeSel.length);
  const zScale = useStudio((s) => s.zScale);
  const [theme, setTheme] = useTheme();
  const none = !sel.length && !shapes;
  void tags;
  const k = kinds();
  const noPrint = printBlock(k.stickers, k.printed);
  const noSend = sendBlock(k.printed, k.stickers);
  return (
    <header className="toolbar" data-testid="toolbar">
      <div className="brand" title="ArUco Studio"><span className="logo"><Icon name="single" /></span>ArUco Studio</div>
      <Menu icon="file" label="File" testid="menu-file">
        <MenuItem icon="newdoc" label="New scene…" hint="a new file" onClick={() => st.setDialog({ kind: "new" })} testid="file-new" />
        <MenuItem icon="open" label="Open…" hint="Ctrl+O" onClick={() => st.setDialog({ kind: "open" })} testid="file-open" />
        <MenuItem icon="save" label="Save as…" hint="copy, then follow" onClick={() => st.setDialog({ kind: "save" })} testid="file-saveas" />
        <MenuItem icon="folder" label="Reveal the file" disabled={!design.path} onClick={() => st.reveal()} testid="file-reveal" />
        <MenuItem icon="file" label="File drawer (the text)" onClick={() => st.setDrawer("file")} testid="file-drawer-open" />
      </Menu>
      <span className={`scene-name st-${design.state}`} data-state={design.state} data-testid="scene-name"
        title={design.path ? `${design.path}: every change is written to it` : "in memory: Save as… gives it a file"}>{name}</span>
      <span className="sep" />
      <div className="group" aria-label="Edit">
        <IconButton icon="undo" title={`Undo (Ctrl+Z)${hist.undo.length ? "" : ": nothing to undo"}`} disabled={!hist.undo.length} onClick={() => st.undo()} testid="undo" />
        <IconButton icon="redo" title="Redo (Ctrl+Shift+Z)" disabled={!hist.redo.length} onClick={() => st.redo()} testid="redo" />
        <IconButton icon="rotate" title="Rotate 90° clockwise (]; [ the other way)" disabled={none} onClick={() => st.rotateSel(-90)} testid="rotate" />
        <IconButton icon="dup" title="Duplicate (Ctrl+D)" disabled={none} onClick={() => st.duplicateSel()} testid="duplicate" />
        <IconButton icon="trash" title="Delete (Del)" disabled={none} onClick={() => st.deleteSel()} testid="delete" />
        <IconButton icon="arrange" title="Arrange in a row, 10 mm apart (the selection, or every tag)" onClick={() => st.arrange()} testid="arrange" />
      </div>
      <span className="sep" />
      <div className="group" aria-label="View">
        <div className="kit-seg compact" role="radiogroup" aria-label="2D / 3D" data-testid="view-toggle">
          {(["2d", "3d"] as const).map((v) => (
            <button key={v} type="button" role="radio" aria-checked={view === v} className={`kit-seg-btn words${view === v ? " on" : ""}`}
              onClick={() => st.setView(v)} data-testid={`view-${v}`} title={`${v.toUpperCase()} (Tab toggles)`}>
              <Icon name={v === "2d" ? "view2d" : "view3d"} />&nbsp;{v.toUpperCase()}
            </button>
          ))}
        </div>
        <IconButton icon="quiet" title="Quiet zones" active={show.quiet} onClick={() => st.setShow("quiet", !show.quiet)} testid="show-quiet" />
        <IconButton icon="axes" title="OpenCV frame axes: x red, y green" active={show.axes} onClick={() => st.setShow("axes", !show.axes)} testid="show-axes" />
        <IconButton icon="outline" title="Layer outlines" active={show.outlines} onClick={() => st.setShow("outlines", !show.outlines)} testid="show-outlines" />
        <IconButton icon="fit" title="Zoom to fit (F)" onClick={() => st.zoomToFit(sel.length ? sel : undefined)} testid="fit" />
        {view === "3d" && (
          <select className="zsel" value={zScale} title="Height exaggeration in 3D" data-testid="zscale" onChange={(e) => st.setZScale(Number(e.target.value))}>
            {[1, 2, 5, 10].map((v) => <option key={v} value={v}>z ×{v}</option>)}
          </select>
        )}
      </div>
      <span className="grow" />
      {busy > 0 && <span className="spin" title="working" data-testid="busy" />}
      <div className="group">
        <Menu icon="verify" label="Verify" testid="menu-verify" align="end">
          <MenuItem icon="verify" label={!sel.length ? "Every tag (OpenCV)" : `Selected tag${sel.length > 1 ? "s" : ""} (OpenCV)`} hint="S › Verify" onClick={() => st.verifySel()} testid="verify-sel" />
          <MenuItem icon="sheet" label="The sheet (every marker in place)" onClick={() => st.verifyScene()} testid="verify-scene" />
        </Menu>
        <Menu icon="export" label="Export" testid="menu-export" align="end">
          <MenuItem icon="sticker" label="Sticker sheet…" hint={noPrint ?? "page, spaced / tight, preview"} disabled={!!noPrint} title={noPrint ?? undefined}
            onClick={() => st.setDialog({ kind: "sheet" })} testid="export-sheet" />
          <MenuItem icon="print" label="Print sticker sheet…" hint={noPrint ?? "at 100 %"} disabled={!!noPrint} title={noPrint ?? undefined}
            onClick={() => st.printSheet()} testid="export-print" />
          <MenuItem icon="send" label="Send to PrusaSlicer…" hint={noSend ?? "a 3MF with the colours"} disabled={!!noSend} title={noSend ?? undefined}
            onClick={() => st.setDialog({ kind: "send" })} testid="export-send" />
          <MenuSeparator />
          <MenuItem icon="sheet" label="Print sheet (SVG, 1:1)" onClick={() => st.exportScene("svg")} testid="export-svg" />
          <MenuItem icon="sheet" label="Print sheet (PNG, 10 px/mm)" onClick={() => st.exportScene("png")} testid="export-png" />
          <MenuItem icon="sheet" label="Old sticker sheet (PDF, A4, cut marks)" onClick={() => st.exportScene("pdf")} testid="export-pdf" />
          <MenuItem icon="cube" label="STL, every tag" onClick={() => st.exportScene("stl")} testid="export-stl" />
          <MenuItem icon="file" label="Plan JSON, every tag" onClick={() => st.exportScene("plan")} testid="export-plan" />
          <MenuItem icon="file" label="Scene file (.arucostudio.json)" onClick={() => st.exportScene("json")} testid="export-json" />
          <MenuSeparator />
          <MenuItem icon="single" label="Selected tag: SVG" disabled={sel.length !== 1} onClick={() => st.exportTag("svg")} testid="export-tag-svg" />
          <MenuItem icon="single" label="Selected tag: STL" disabled={sel.length !== 1} onClick={() => st.exportTag("stl")} testid="export-tag-stl" />
          <MenuItem icon="single" label="Selected tag: plan JSON" disabled={sel.length !== 1} onClick={() => st.exportTag("json")} testid="export-tag-json" />
        </Menu>
        <IconButton icon={theme === "dark" ? "sun" : "moon"} title={theme === "dark" ? "Light theme" : "Dark theme"}
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")} testid="theme" />
        <IconButton icon="help" title="Keyboard (?)" onClick={() => st.setDrawer(useStudio.getState().drawer === "messages" ? null : "messages")} testid="help" />
      </div>
    </header>
  );
}
