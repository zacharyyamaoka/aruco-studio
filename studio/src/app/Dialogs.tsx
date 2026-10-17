// New scene / Open / Save as: small dialogs over the canvas. Scenes live in
// the server's scenes folder as <name>.arucostudio.json.
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useStudio } from "../store";
import { Icon } from "../ui/controls";

export function Dialogs() {
  const d = useStudio((s) => s.dialog);
  const name = useStudio((s) => s.scene.name);
  const st = useStudio.getState();
  const [text, setText] = useState("");
  const [list, setList] = useState<{ name: string; modified: string; bytes: number }[] | null>(null);
  useEffect(() => {
    if (!d) return;
    setText(d.kind === "new" ? "scene" : name);
    if (d.kind === "open") api.scenes().then(setList).catch(() => setList([]));
  }, [d]);
  if (!d) return null;
  const close = () => st.setDialog(null);
  const ok = async () => {
    const v = text.trim();
    if (!v) return;
    close();
    if (d.kind === "new") await st.newScene(v);
    if (d.kind === "save") await st.saveScene(v);
  };
  return (
    <div className="modal-back" onMouseDown={(e) => e.target === e.currentTarget && close()}>
      <div className="dialog" role="dialog" data-testid={`dialog-${d.kind}`}>
        <div className="lib-title"><Icon name={d.kind === "open" ? "open" : d.kind === "new" ? "newdoc" : "save"} />
          {d.kind === "open" ? "Open a scene" : d.kind === "new" ? "New scene" : "Save the scene as"}</div>
        {d.kind !== "open" && (
          <div className="pad">
            <input autoFocus className="txt" value={text} data-testid="dialog-name" onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") ok(); if (e.key === "Escape") close(); e.stopPropagation(); }} />
            {d.kind === "new" && <div className="muted">The open scene is closed (save it first if you want to keep it).</div>}
          </div>
        )}
        {d.kind === "open" && (
          <div className="pad scenes">
            {list === null && <div className="muted">…</div>}
            {list && !list.length && <div className="muted">No saved scenes yet.</div>}
            {list && list.map((x) => (
              <button key={x.name} className="scene-item" data-scene={x.name} onClick={async () => { close(); await st.openScene(x.name); }}>
                <Icon name="file" /><span>{x.name}</span><span className="muted">{x.modified.replace("T", " ")} · {(x.bytes / 1024).toFixed(1)} kB</span>
              </button>
            ))}
          </div>
        )}
        <div className="prompt-buttons pad">
          <button className="btn" onClick={close}>Cancel</button>
          {d.kind !== "open" && <button className="btn primary" onClick={ok} data-testid="dialog-ok">{d.kind === "new" ? "Create" : "Save"}</button>}
        </div>
      </div>
    </div>
  );
}
