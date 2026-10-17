// The top bar: file (New / Open / Save / Save as), add a tag (Single, Grid,
// ChArUco), edit (Undo, Redo, Rotate, Duplicate, Delete), view (2D / 3D,
// quiet zones, axes, layer outlines, fit), Verify and Export.
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useStudio } from "../store";
import { Icon, IconButton } from "../ui/controls";

function Menu({ icon, label, children, testid }: { icon: string; label: string; children: (close: () => void) => ReactNode; testid?: string }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    window.addEventListener("mousedown", close);
    return () => window.removeEventListener("mousedown", close);
  }, [open]);
  return (
    <div className={`menu${open ? " open" : ""}`} ref={ref}>
      <button type="button" className="tb" onClick={() => setOpen(!open)} data-testid={testid} title={label}>
        <Icon name={icon} /><span>{label}</span><Icon name="chevron" className="chev" />
      </button>
      {open && <div className="menu-list">{children(() => setOpen(false))}</div>}
    </div>
  );
}

function Item({ icon, label, hint, onClick, testid, disabled }: { icon: string; label: string; hint?: string; onClick: () => void; testid?: string; disabled?: boolean }) {
  return (
    <button type="button" className="menu-item" onClick={onClick} data-testid={testid} disabled={disabled}>
      <Icon name={icon} /><span>{label}</span>{hint && <span className="hint">{hint}</span>}
    </button>
  );
}

export function Toolbar() {
  const st = useStudio.getState();
  const view = useStudio((s) => s.view);
  const show = useStudio((s) => s.show);
  const sel = useStudio((s) => s.sel);
  const hist = useStudio((s) => s.hist);
  const busy = useStudio((s) => s.busy);
  const name = useStudio((s) => s.scene.name);
  const zScale = useStudio((s) => s.zScale);
  const none = !sel.length;
  return (
    <header className="toolbar" data-testid="toolbar">
      <div className="brand" title="ArUco Studio"><Icon name="single" /><b>ArUco Studio</b></div>
      <Menu icon="file" label="File" testid="menu-file">
        {(close) => (
          <>
            <Item icon="newdoc" label="New scene…" onClick={() => { close(); st.setDialog({ kind: "new" }); }} testid="file-new" />
            <Item icon="open" label="Open…" hint="Ctrl+O" onClick={() => { close(); st.setDialog({ kind: "open" }); }} testid="file-open" />
            <Item icon="save" label={`Save '${name}'`} hint="Ctrl+S" onClick={() => { close(); st.saveScene(); }} testid="file-save" />
            <Item icon="save" label="Save as…" onClick={() => { close(); st.setDialog({ kind: "save" }); }} testid="file-saveas" />
          </>
        )}
      </Menu>
      <span className="scene-name" title="the open scene" data-testid="scene-name">{name}</span>
      <span className="sep" />
      <div className="group" aria-label="Add a tag">
        <button type="button" className="tb" onClick={() => st.addTag("single")} data-testid="add-single" title="Add a single marker (S)"><Icon name="single" /><span>Single</span></button>
        <button type="button" className="tb" onClick={() => st.addTag("grid")} data-testid="add-grid" title="Add a grid board (G)"><Icon name="grid" /><span>Grid</span></button>
        <button type="button" className="tb" onClick={() => st.addTag("charuco")} data-testid="add-charuco" title="Add a ChArUco board (C)"><Icon name="charuco" /><span>ChArUco</span></button>
      </div>
      <span className="sep" />
      <div className="group" aria-label="Edit">
        <IconButton icon="undo" title={`Undo (Ctrl+Z)${hist.undo.length ? "" : ": nothing to undo"}`} disabled={!hist.undo.length} onClick={() => st.undo()} testid="undo" />
        <IconButton icon="redo" title="Redo (Ctrl+Shift+Z)" disabled={!hist.redo.length} onClick={() => st.redo()} testid="redo" />
        <IconButton icon="rotate" title="Rotate 90° (R; Shift+R the other way)" disabled={none} onClick={() => st.rotateSel(-90)} testid="rotate" />
        <IconButton icon="dup" title="Duplicate (Ctrl+D)" disabled={none} onClick={() => st.duplicateSel()} testid="duplicate" />
        <IconButton icon="trash" title="Delete (Del)" disabled={none} onClick={() => st.deleteSel()} testid="delete" />
        <IconButton icon="arrange" title="Arrange in a row, 10 mm apart (the selection, or every tag) (Shift+A)" onClick={() => st.arrange()} testid="arrange" />
      </div>
      <span className="sep" />
      <div className="group" aria-label="View">
        <div className="seg" role="radiogroup" aria-label="2D / 3D" data-testid="view-toggle">
          <button type="button" role="radio" aria-checked={view === "2d"} className={view === "2d" ? "on" : ""} onClick={() => st.setView("2d")} data-testid="view-2d" title="2D (Tab toggles)"><Icon name="view2d" />2D</button>
          <button type="button" role="radio" aria-checked={view === "3d"} className={view === "3d" ? "on" : ""} onClick={() => st.setView("3d")} data-testid="view-3d" title="3D (Tab toggles)"><Icon name="view3d" />3D</button>
        </div>
        <IconButton icon="quiet" title="Quiet zones (Q)" active={show.quiet} onClick={() => st.setShow("quiet", !show.quiet)} testid="show-quiet" />
        <IconButton icon="axes" title="OpenCV frame axes: x red, y green (A)" active={show.axes} onClick={() => st.setShow("axes", !show.axes)} testid="show-axes" />
        <IconButton icon="outline" title="Layer outlines (L)" active={show.outlines} onClick={() => st.setShow("outlines", !show.outlines)} testid="show-outlines" />
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
        <Menu icon="verify" label="Verify" testid="menu-verify">
          {(close) => (
            <>
              <Item icon="verify" label={none ? "Every tag (OpenCV)" : `Selected tag${sel.length > 1 ? "s" : ""} (OpenCV)`} hint="V" onClick={() => { close(); st.verifySel(); }} testid="verify-sel" />
              <Item icon="sheet" label="The sheet (every marker in place)" onClick={() => { close(); st.verifyScene(); }} testid="verify-scene" />
            </>
          )}
        </Menu>
        <Menu icon="export" label="Export" testid="menu-export">
          {(close) => (
            <>
              <Item icon="sheet" label="Print sheet (SVG, 1:1)" onClick={() => { close(); st.exportScene("svg"); }} testid="export-svg" />
              <Item icon="sheet" label="Print sheet (PNG, 10 px/mm)" onClick={() => { close(); st.exportScene("png"); }} testid="export-png" />
              <Item icon="cube" label="STL, every tag" onClick={() => { close(); st.exportScene("stl"); }} testid="export-stl" />
              <Item icon="file" label="Plan JSON, every tag" onClick={() => { close(); st.exportScene("plan"); }} testid="export-plan" />
              <Item icon="file" label="Scene file (.arucostudio.json)" onClick={() => { close(); st.exportScene("json"); }} testid="export-json" />
              <div className="menu-sep" />
              <Item icon="single" label="Selected tag: SVG" disabled={sel.length !== 1} onClick={() => { close(); st.exportTag("svg"); }} testid="export-tag-svg" />
              <Item icon="single" label="Selected tag: STL" disabled={sel.length !== 1} onClick={() => { close(); st.exportTag("stl"); }} testid="export-tag-stl" />
              <Item icon="single" label="Selected tag: plan JSON" disabled={sel.length !== 1} onClick={() => { close(); st.exportTag("json"); }} testid="export-tag-json" />
            </>
          )}
        </Menu>
        <IconButton icon="help" title="Keyboard (?)" onClick={() => st.setDrawer(useStudio.getState().drawer === "messages" ? null : "messages")} testid="help" />
      </div>
    </header>
  );
}
