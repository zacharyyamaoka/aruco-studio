// The bottom drawer: Verify (OpenCV's read of each tag, and of the sheet),
// Messages (every status line, errors included) and the keyboard map. The
// status bar above it always shows the last line.
import { useStudio } from "../store";
import { Icon, IconButton } from "../ui/controls";

const fmt = (v: unknown, d = 3) => (typeof v === "number" ? v.toFixed(d) : "–");

export const KEYS: [string, string][] = [
  ["S / G / C", "add a single marker / a grid board / a ChArUco board"],
  ["Click, Shift+click", "select, add to the selection"],
  ["Drag on empty canvas", "marquee select (Shift adds)"],
  ["Drag a tag", "move (0.5 mm snap)"],
  ["Arrows (Shift)", "nudge 0.5 mm (5 mm)"],
  ["Wheel", "zoom at the cursor (Shift+wheel pans)"],
  ["Space+drag, middle or right drag", "pan"],
  ["R / Shift+R", "rotate 90° clockwise / counter-clockwise"],
  ["Ctrl+D", "duplicate"],
  ["Shift+A", "arrange in a row, 10 mm apart"],
  ["Del / Backspace", "delete"],
  ["Ctrl+Z, Ctrl+Shift+Z or Ctrl+Y", "undo, redo"],
  ["Ctrl+A / Esc", "select all / none"],
  ["Tab", "2D / 3D"],
  ["F", "zoom to fit (the selection, or everything)"],
  ["Q / A / L", "quiet zones / frame axes / layer outlines"],
  ["V", "verify the selection with OpenCV"],
  ["Ctrl+S / Ctrl+O", "save / open"],
  ["Double-click a tag or an IDs row", "zoom to it"],
];

export function StatusBar() {
  const status = useStudio((s) => s.status);
  const drawer = useStudio((s) => s.drawer);
  const n = useStudio((s) => s.scene.tags.length);
  const sel = useStudio((s) => s.sel.length);
  const camera = useStudio((s) => s.camera);
  const st = useStudio.getState();
  return (
    <div className="statusbar">
      <span className={`status lv-${status.level}`} data-testid="status" onClick={() => st.setDrawer(drawer === "messages" ? null : "messages")}>{status.text || "Ready"}</span>
      <span className="grow" />
      <span className="muted">{n} tag{n === 1 ? "" : "s"}{sel ? ` · ${sel} selected` : ""} · {camera.zoom.toFixed(2)} px/mm · centre {camera.cx.toFixed(1)}, {camera.cy.toFixed(1)} mm</span>
      <button className={`tb small${drawer === "verify" ? " on" : ""}`} onClick={() => st.setDrawer(drawer === "verify" ? null : "verify")} data-testid="sb-verify"><Icon name="verify" />Verify</button>
      <button className={`tb small${drawer === "messages" ? " on" : ""}`} onClick={() => st.setDrawer(drawer === "messages" ? null : "messages")} data-testid="sb-messages"><Icon name="doc" />Messages</button>
    </div>
  );
}

export function Drawer() {
  const drawer = useStudio((s) => s.drawer);
  const verify = useStudio((s) => s.verify);
  const sv = useStudio((s) => s.sceneVerify);
  const log = useStudio((s) => s.log);
  const tags = useStudio((s) => s.scene.tags);
  const st = useStudio.getState();
  if (!drawer) return null;
  return (
    <section className="drawer" data-testid={`drawer-${drawer}`}>
      <div className="drawer-head">
        <b>{drawer === "verify" ? "Verify: OpenCV reads the plans" : "Messages and keys"}</b>
        <span className="grow" />
        <IconButton icon="close" title="Close" onClick={() => st.setDrawer(null)} />
      </div>
      {drawer === "verify" && (
        <div className="drawer-body verify">
          {!Object.keys(verify).length && !sv && <div className="muted">Verify a tag (V) or the sheet: each tag is rendered from its layers and read by OpenCV's own detector, and its pose is solved 25° off.</div>}
          {Object.keys(verify).length > 0 && (
            <table className="vt" data-testid="verify-table">
              <thead><tr><th>Tag</th><th>OK</th><th>IDs planned</th><th>IDs read</th><th>Missing</th><th>Extra</th><th>Corner err</th><th>ChArUco</th><th>PnP err</th><th>Read</th></tr></thead>
              <tbody>
                {Object.entries(verify).filter(([k]) => tags.some((t) => t.name === k)).map(([k, r]) => (
                  <tr key={k} data-verify-row={k} className={r.ok ? "ok" : "bad"}>
                    <td>{k}</td>
                    <td data-ok={r.ok ? "1" : "0"}>{r.ok ? "✓" : "✗"}</td>
                    <td>{(r.ids_expected || []).join(" ")}</td>
                    <td data-ids-read={(r.ids_read || []).join(",")}>{(r.ids_read || []).join(" ")}</td>
                    <td>{(r.missing || []).join(" ") || "–"}</td>
                    <td>{(r.extra || []).join(" ") || "–"}</td>
                    <td>{fmt(r.corner_err_mm)} mm</td>
                    <td>{r.charuco_expected ? `${r.charuco_read}/${r.charuco_expected}` : "–"}</td>
                    <td data-pnp-mm={r.pnp_err_mm ?? ""}>{fmt(r.pnp_err_mm)} mm · {fmt(r.pnp_err_deg)}°</td>
                    <td>{r.image_png ? <img className="vimg" alt={`what OpenCV read for ${k}`} src={`data:image/png;base64,${r.image_png}`} /> : "–"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {sv && (
            <div className="sv" data-testid="verify-scene-report">
              <b>Sheet:</b> {sv.ok ? "every marker found where the scene puts it" : "not every marker found"} · <span data-found={sv.found}>{sv.found} of {sv.markers} markers</span> · worst centre {fmt(sv.worst_err_mm, 3)} mm
              {(sv.missing || []).length > 0 && <> · missing {(sv.missing || []).map((m: any) => `${m[0]} #${m[1]}`).join(", ")}</>}
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
          <table className="keys"><tbody>{KEYS.map(([k, v]) => <tr key={k}><td><kbd>{k}</kbd></td><td>{v}</td></tr>)}</tbody></table>
        </div>
      )}
    </section>
  );
}
