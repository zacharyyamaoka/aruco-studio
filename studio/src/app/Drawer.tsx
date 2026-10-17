// The bottom drawer: Verify (OpenCV's read of each tag, and of the sheet),
// Messages (every status line, errors included) and the keyboard map. The
// status bar above it always shows the last line.
import { Kbd } from "../kit";
import { isStale, useStudio } from "../store";
import { Icon, IconButton } from "../ui/controls";
import { commands } from "./commands";
import { FileDrawer } from "./FileDrawer";

const fmt = (v: unknown, d = 3) => (typeof v === "number" ? v.toFixed(d) : "–");

/** The keys table (the commands, then the mouse): docs/STUDIO.md has the same. */
export const MOUSE: [string, string][] = [
  ["Click, Shift+click", "select, add to the selection"],
  ["Drag on empty canvas", "marquee select (Shift adds)"],
  ["Drag a shape or a tag", "move it (0.5 mm snap; Alt: no snap)"],
  ["Drag a handle", "resize or turn the shape (0.5 mm / 15°); the markers re-place live"],
  ["Alt+click a polygon edge", "a new point there (Del removes the point just dragged)"],
  ["Drag a selected tag's label", "place the label by hand (0.25 mm steps)"],
  ["Arrows (Shift)", "nudge 0.5 mm (5 mm)"],
  ["Wheel", "zoom at the cursor (Shift+wheel pans)"],
  ["Space+drag, middle or right drag", "pan"],
  ["Double-click a tag or an IDs row", "zoom to it"],
];

export function StatusBar() {
  const status = useStudio((s) => s.status);
  const drawer = useStudio((s) => s.drawer);
  const n = useStudio((s) => s.scene.tags.length);
  const sel = useStudio((s) => s.sel.length);
  const camera = useStudio((s) => s.camera);
  const design = useStudio((s) => s.design);
  const st = useStudio.getState();
  const e = design.error;
  const fileText = design.state === "broken" ? `line ${e?.line} col ${e?.col}: ${e?.message} (writes wait until it parses)`
    : design.state === "missing" ? "the file is gone (Save as… writes it again)"
    : design.state === "memory" ? "in memory (Save as… gives it a file)" : (design.path ?? "").split(/[\/]/).pop();
  return (
    <div className="statusbar">
      <span className={`filebar st-${design.state}`} data-testid="file-bar" data-state={design.state} title={design.path ?? ""}
        onClick={() => st.setDrawer(drawer === "file" ? null : "file")}><Icon name="file" />{fileText}</span>
      <span className={`status lv-${status.level}`} data-testid="status" onClick={() => st.setDrawer(drawer === "messages" ? null : "messages")}>{status.text || "Ready"}</span>
      <span className="muted">{n} tag{n === 1 ? "" : "s"}{sel ? ` · ${sel} selected` : ""} · {camera.zoom.toFixed(2)} px/mm · centre {camera.cx.toFixed(1)}, {camera.cy.toFixed(1)} mm</span>
      <button className={`tb small${drawer === "verify" ? " on" : ""}`} onClick={() => st.setDrawer(drawer === "verify" ? null : "verify")} data-testid="sb-verify"><Icon name="verify" />Verify</button>
      <button className={`tb small${drawer === "messages" ? " on" : ""}`} onClick={() => st.setDrawer(drawer === "messages" ? null : "messages")} data-testid="sb-messages"><Icon name="doc" />Messages</button>
      <button className={`tb small${drawer === "file" ? " on" : ""}`} onClick={() => st.setDrawer(drawer === "file" ? null : "file")} data-testid="sb-file"><Icon name="file" />File</button>
    </div>
  );
}

export function Drawer() {
  const drawer = useStudio((s) => s.drawer);
  const verify = useStudio((s) => s.verify);
  const verifySpec = useStudio((s) => s.verifySpec);
  const progress = useStudio((s) => s.verifyProgress);
  const sv = useStudio((s) => s.sceneVerify);
  const log = useStudio((s) => s.log);
  const tags = useStudio((s) => s.scene.tags);
  const st = useStudio.getState();
  if (!drawer) return null;
  // a tag changed since it was verified: its row is stale, never a green tick (audit F4)
  const stale = (k: string) => isStale({ scene: { tags } as any, verifySpec }, k);
  const nStale = Object.keys(verify).filter((k) => tags.some((t) => t.name === k) && stale(k)).length;
  return (
    <section className="drawer" data-testid={`drawer-${drawer}`}>
      <div className="drawer-head">
        <b>{drawer === "verify" ? "Verify: OpenCV reads the plans" : drawer === "file" ? "File: the design file as it is on disk" : "Messages and keys"}</b>
        <span className="grow" />
        <IconButton icon="close" title="Close" onClick={() => st.setDrawer(null)} />
      </div>
      {drawer === "verify" && (
        <div className="drawer-body verify">
          {!Object.keys(verify).length && !sv && <div className="muted">Verify a tag (V) or the sheet: each tag is rendered from its layers and read by OpenCV's own detector, and its pose is solved 25° off.</div>}
          {progress && (
            <div className="vprog" data-testid="verify-progress" data-done={progress.done} data-total={progress.total}>
              Verifying {progress.done} of {progress.total}…
              <span className="bar"><i style={{ width: `${(100 * progress.done) / Math.max(1, progress.total)}%` }} /></span>
            </div>
          )}
          {nStale > 0 && !progress && (
            <div className="vstale" data-testid="verify-stale">
              {nStale} tag{nStale === 1 ? " has" : "s have"} changed since it was verified.
              <button className="btn small" data-testid="reverify" onClick={() => st.verifySel()}>Verify again</button>
            </div>
          )}
          {Object.keys(verify).length > 0 && (
            <table className="vt" data-testid="verify-table">
              <thead><tr><th>Tag</th><th>OK</th><th>IDs planned</th><th>IDs read</th><th>Missing</th><th>Extra</th><th>Corner err</th><th>ChArUco</th><th>PnP err</th><th>Read</th></tr></thead>
              <tbody>
                {Object.entries(verify).filter(([k]) => tags.some((t) => t.name === k)).map(([k, r]) => {
                  const old = stale(k);
                  return (
                  <tr key={k} data-verify-row={k} data-stale={old ? "1" : "0"} className={old ? "stale" : r.ok ? "ok" : "bad"}
                    title={old ? "changed since it was verified: not verified since the change" : undefined}>
                    <td>{k}</td>
                    <td data-ok={old ? "stale" : r.ok ? "1" : "0"}>{old ? "not verified since the change" : r.ok ? "✓" : "✗"}</td>
                    <td>{(r.ids_expected || []).join(" ")}</td>
                    <td data-ids-read={(r.ids_read || []).join(",")}>{(r.ids_read || []).join(" ")}</td>
                    <td>{(r.missing || []).join(" ") || "–"}</td>
                    <td>{(r.extra || []).join(" ") || "–"}</td>
                    <td>{fmt(r.corner_err_mm)} mm</td>
                    <td>{r.charuco_expected ? `${r.charuco_read}/${r.charuco_expected}` : "–"}</td>
                    <td data-pnp-mm={r.pnp_err_mm ?? ""}>{fmt(r.pnp_err_mm)} mm · {fmt(r.pnp_err_deg)}°</td>
                    <td>{r.image_png ? <img className="vimg" alt={`what OpenCV read for ${k}`} src={`data:image/png;base64,${r.image_png}`} /> : "–"}</td>
                  </tr>
                  );
                })}
              </tbody>
            </table>
          )}
          {sv && (
            <div className="sv" data-testid="verify-scene-report">
              <b>Sheet:</b> {(sv.markers_ok ?? sv.ok) ? "every marker found where the scene puts it" : "not every marker found"} · <span data-found={sv.found}>{sv.found} of {sv.markers} markers</span> · worst centre {fmt(sv.worst_err_mm, 3)} mm
              {(sv.missing || []).length > 0 && <> · missing {(sv.missing || []).map((m: any) => `${m[0]} #${m[1]}`).join(", ")}</>}
              {(sv.overlaps || []).length > 0 && (
                <div className="issue lv-warn" data-testid="verify-overlaps" data-overlaps={(sv.overlaps || []).length}>
                  Not as planned: {(sv.overlaps || []).map((o: any) => `${o.tags[1]} overlaps ${o.tags[0]} (${Number(o.mm2).toFixed(1)} mm²)`).join("; ")}
                </div>
              )}
            </div>
          )}
        </div>
      )}
      {drawer === "messages" && (
        <div className="drawer-body two">
          <div className="log" data-testid="log">
            {!log.length && <div className="muted">Nothing yet.</div>}
            {[...log].reverse().map((l, i) => <div key={i} className={`logline lv-${l.level}`}><span className="t">{l.t}</span>{l.text}</div>)}
          </div>
          <div className="keymap" data-testid="keymap">
            <table className="keys"><tbody>
              {commands().map((c) => <tr key={c.id} data-key-row={c.name}><td>{c.key ? <Kbd keys={c.key} /> : <span className="muted">S</span>}</td><td>{c.name}</td></tr>)}
              {MOUSE.map(([k, v]) => <tr key={k}><td><kbd>{k}</kbd></td><td>{v}</td></tr>)}
            </tbody></table>
          </div>
        </div>
      )}
      {drawer === "file" && <FileDrawer />}
    </section>
  );
}
