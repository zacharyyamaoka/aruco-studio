// New scene / Open / Save as: small dialogs over the canvas. There is no
// Save: the open file is written on every change. A new scene is a new file
// in the scenes folder (<name>.arucostudio.json); Open takes a scene of the
// folder or a file anywhere (a path); Save as copies the design to a name or
// a path and follows that file from then on.
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useStudio } from "../store";
import { Icon } from "../ui/controls";

export function Dialogs() {
  const d = useStudio((s) => s.dialog);
  const name = useStudio((s) => s.scene.name);
  const st = useStudio.getState();
  const [text, setText] = useState("");
  const [path, setPath] = useState("");
  const [list, setList] = useState<{ name: string; modified: string; bytes: number }[] | null>(null);
  useEffect(() => {
    if (!d) return;
    setText(d.kind === "new" ? "scene" : name);
    setPath("");
    if (d.kind === "open") api.scenes().then(setList).catch(() => setList([]));
  }, [d]);
  if (!d) return null;
  const close = () => st.setDialog(null);
  const ok = async () => {
    const v = (d.kind === "open" ? path : text).trim();
    if (!v) return;
    close();
    if (d.kind === "new") await st.newScene(v);
    if (d.kind === "save") await st.saveAs(v);
    if (d.kind === "open") await st.openPath(v);
  };
  const keys = (e: React.KeyboardEvent) => { if (e.key === "Enter") ok(); if (e.key === "Escape") close(); e.stopPropagation(); };
  return (
    <div className="modal-back" onMouseDown={(e) => e.target === e.currentTarget && close()}>
      <div className="dialog" role="dialog" data-testid={`dialog-${d.kind}`}>
        <div className="lib-title"><Icon name={d.kind === "open" ? "open" : d.kind === "new" ? "newdoc" : "save"} />
          {d.kind === "open" ? "Open a design file" : d.kind === "new" ? "New scene (a new file)" : "Save the scene as"}</div>
        {d.kind !== "open" && (
          <div className="pad">
            <input autoFocus className="txt" value={text} data-testid="dialog-name" onChange={(e) => setText(e.target.value)} onKeyDown={keys} />
            <div className="muted">{d.kind === "new"
              ? "A name makes scenes/<name>.arucostudio.json; every change is written to it."
              : "A name (the scenes folder) or a whole path. The Studio then follows that file."}</div>
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
            <input className="txt" placeholder="or a file's path: C:\…\name.arucostudio.json" value={path} data-testid="dialog-path"
              onChange={(e) => setPath(e.target.value)} onKeyDown={keys} />
          </div>
        )}
        <div className="prompt-buttons pad">
          <button className="btn" onClick={close}>Cancel</button>
          <button className="btn primary" onClick={ok} data-testid="dialog-ok">{d.kind === "new" ? "Create" : d.kind === "open" ? "Open" : "Save as"}</button>
        </div>
      </div>
    </div>
  );
}
