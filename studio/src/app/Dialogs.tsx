// New scene / Open / Save as: small dialogs over the canvas. Scenes live in
// the server's scenes folder as <name>.arucostudio.json.
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { isDirty, useStudio } from "../store";
import { Icon } from "../ui/controls";

export function Dialogs() {
  const d = useStudio((s) => s.dialog);
  const name = useStudio((s) => s.scene.name);
  const dirty = useStudio((s) => isDirty(s));
  const st = useStudio.getState();
  const [text, setText] = useState("");
  const [list, setList] = useState<{ name: string; modified: string; bytes: number }[] | null>(null);
  // New / Open over unsaved changes ask first (audit F12)
  const [asked, setAsked] = useState(false);
  useEffect(() => {
    if (!d) return;
    setAsked(false);
    setText(d.kind === "new" ? "scene" : name);
    if (d.kind === "open") api.scenes().then(setList).catch(() => setList([]));
  }, [d]);
  if (!d) return null;
  const close = () => st.setDialog(null);
  if (d.kind !== "save" && dirty && !asked) {
    return (
      <div className="modal-back" onMouseDown={(e) => e.target === e.currentTarget && close()}>
        <div className="dialog" role="dialog" data-testid="dialog-unsaved">
          <div className="lib-title"><Icon name="save" />Save changes to '{name}'?</div>
          <div className="pad muted">The scene has changes that are not saved. {d.kind === "new" ? "A new scene" : "Opening another scene"} closes it.</div>
          <div className="prompt-buttons pad">
            <button className="btn" onClick={close} data-testid="unsaved-cancel">Cancel</button>
            <button className="btn" onClick={() => setAsked(true)} data-testid="unsaved-discard">Don't save</button>
            <button className="btn primary" data-testid="unsaved-save" onClick={async () => { await st.saveScene(); setAsked(true); }}>Save</button>
          </div>
        </div>
      </div>
    );
  }
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
            {d.kind === "new" && <div className="muted">The open scene is closed{dirty ? "" : " (it has no unsaved changes)"}.</div>}
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
