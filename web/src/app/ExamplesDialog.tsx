// File › Examples…: the golden faces as cards; a click opens one.
import { Dialog } from "@bam/ui";
import { loopD } from "../model/geom";
import { EXAMPLES } from "../model/examples";
import { shapeLoop, sketchBox } from "../sketch/model";
import { useStudio } from "../store";
import { leaveFile } from "../hosted/hosted";

function Thumb({ id }: { id: string }) {
  const ex = EXAMPLES.find((e) => e.id === id)!;
  const b = sketchBox(ex.shapes);
  if (!b) return <svg viewBox="0 0 10 10" className="ex-thumb"><path d="M1 1h8v8H1z" fill="none" stroke="currentColor" strokeDasharray="1 1" strokeWidth=".2" /></svg>;
  const pad = 4;
  return (
    <svg className="ex-thumb" viewBox={`${b.x0 - pad} ${-b.y1 - pad} ${b.x1 - b.x0 + 2 * pad} ${b.y1 - b.y0 + 2 * pad}`}>
      <g transform="scale(1 -1)">
        <path d={ex.shapes.map((s) => loopD(shapeLoop(s))).join("")} fillRule="evenodd" className="ex-fill" />
      </g>
    </svg>
  );
}

export function ExamplesDialog() {
  const open = useStudio((s) => s.modal === "examples");
  const close = () => useStudio.getState().openModal(null);
  return (
    <Dialog open={open} onClose={close} title="Examples" icon="library" testid="examples-dialog" width={620}>
      <div className="ex-grid">
        {EXAMPLES.map((e) => (
          <button type="button" key={e.id} className="ex-card" data-example={e.id}
            onClick={() => { close(); void leaveFile().then((left) => { if (left) useStudio.getState().newDoc(e.id); }); }}>
            <Thumb id={e.id} />
            <span className="ex-name">{e.name}</span>
            <span className="ex-note">{e.note}</span>
          </button>
        ))}
      </div>
    </Dialog>
  );
}
