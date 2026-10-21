// File › Examples…: the golden faces as cards; a click opens one.
import { Dialog } from "@bam/ui";
import { loopD } from "../model/geom";
import { EXAMPLES } from "../model/examples";
import { shapeLoop, sketchBox, type Shape } from "../sketch/model";
import { useStudio } from "../store";
import { leaveFile } from "../hosted/hosted";
import { useExampleMarks, type Mark } from "./thumbs";

// WHY inline (the stylesheet is not this lane's): a marker's white and black, the canvas's
const MARK_WHITE = { fill: "var(--t-white, #fff)", stroke: "none" };
const MARK_BLACK = { fill: "var(--t-black, #111)", stroke: "none" };

/** An empty document: the sketch's own grid and its origin, faint -- a calm
 *  empty canvas (Zach, 2026-10-21: an empty file's card is not the file icon). */
function EmptyCanvas() {
  const lines: string[] = [], major: string[] = [];
  for (let x = 10; x < 160; x += 10) if (x !== 80) (x % 40 === 0 ? major : lines).push(`M${x} 0V100`);
  for (let y = 10; y < 100; y += 10) if (y !== 50) (y % 40 === 10 ? major : lines).push(`M0 ${y}H160`);
  return (
    <svg viewBox="0 0 160 100" preserveAspectRatio="xMidYMid slice" className="ex-thumb ex-empty" data-thumb="empty" aria-label="Empty">
      <path d={lines.join("")} className="ex-grid" />
      <path d={major.join("")} className="ex-grid major" />
      <path d="M80 0V100M0 50H160" className="ex-axis" />
    </svg>
  );
}

/** Shapes as a small picture, y up (the examples' cards, Home's cards), and
 *  the markers on them when known (./thumbs.ts): each outline white, its black over it. */
export function ShapesThumb({ shapes, marks = [] }: { shapes: Shape[]; marks?: Mark[] }) {
  const b = sketchBox(shapes);
  if (!b) return <EmptyCanvas />;
  const pad = 4;
  return (
    <svg className="ex-thumb" viewBox={`${b.x0 - pad} ${-b.y1 - pad} ${b.x1 - b.x0 + 2 * pad} ${b.y1 - b.y0 + 2 * pad}`}>
      <g transform="scale(1 -1)">
        <path d={shapes.map((s) => loopD(shapeLoop(s))).join("")} fillRule="evenodd" className="ex-fill" />
        {marks.length > 0 && (
          <g data-thumb-marks={marks.length}>
            {marks.map((m, i) => (
              <g key={i}>
                <path d={loopD(m.outer)} style={MARK_WHITE} />
                <path d={m.black.map((p) => loopD(p.outer) + p.holes.map(loopD).join("")).join("")} fillRule="evenodd" style={MARK_BLACK} data-thumb-black="1" />
              </g>
            ))}
          </g>
        )}
      </g>
    </svg>
  );
}

/** An example's picture: its shapes, and its markers once planned (Home plans them). */
export function ExampleThumb({ id }: { id: string }) {
  const marks = useExampleMarks(id);
  return <ShapesThumb shapes={EXAMPLES.find((e) => e.id === id)!.shapes} marks={marks} />;
}

/** An example into the editor: the cloud file open is left first (its changes saved). */
export function openExample(id: string): Promise<void> {
  return leaveFile().then((left) => { if (left) useStudio.getState().newDoc(id); });
}

export function ExamplesDialog() {
  const open = useStudio((s) => s.modal === "examples");
  const close = () => useStudio.getState().openModal(null);
  return (
    <Dialog open={open} onClose={close} title="Examples" icon="library" testid="examples-dialog" width={620}>
      <div className="ex-grid">
        {EXAMPLES.map((e) => (
          <button type="button" key={e.id} className="ex-card" data-example={e.id}
            onClick={() => { close(); void openExample(e.id); }}>
            <ExampleThumb id={e.id} />
            <span className="ex-name">{e.name}</span>
            <span className="ex-note">{e.note}</span>
          </button>
        ))}
      </div>
    </Dialog>
  );
}
