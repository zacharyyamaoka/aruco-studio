// The timeline (Fusion's, at the bottom): Sketch → ArUco Extrude → Joint
// Origin. A click selects; a double-click edits.
import { Glyph } from "@bam/ui";
import { useStudio } from "../store";

export function Timeline() {
  const sel = useStudio((s) => s.sel);
  const feature = useStudio((s) => s.doc.feature);
  const rectId = feature?.rectId;
  const panelOpen = useStudio((s) => s.panel.open);
  const st = useStudio.getState;
  const items = [
    { id: "sketch", name: "Sketch", glyph: "sketch", on: sel?.kind === "sketch", click: () => st().select({ kind: "sketch" }), dbl: () => { st().setTool("select"); st().fit(); } },
    ...(feature && (rectId || panelOpen) ? [
      { id: "extrude", name: "ArUco Extrude", glyph: "extrude", on: sel?.kind === "feature" || panelOpen, click: () => st().select({ kind: "feature" }), dbl: () => st().editFeature() },
      { id: "origin", name: "Joint Origin", glyph: "joint", on: sel?.kind === "origin", click: () => st().select({ kind: "origin" }), dbl: () => st().editFeature() },
    ] : []),
  ];
  return (
    <footer className="timeline" data-testid="timeline">
      <span className="tl-label">Timeline</span>
      <div className="tl-track">
        {items.map((it) => (
          <button type="button" key={it.id} className={`tl-item${it.on ? " on" : ""}`} data-tl={it.id} title={`${it.name} (double-click to edit)`}
            aria-label={it.name} onClick={it.click} onDoubleClick={it.dbl}>
            <Glyph name={it.glyph} /><span className="tl-name">{it.name}</span>
          </button>
        ))}
      </div>
    </footer>
  );
}
