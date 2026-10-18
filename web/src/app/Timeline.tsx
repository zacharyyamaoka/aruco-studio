// The timeline (Fusion's, at the bottom): Sketch, then for each feature its
// ArUco Extrude N and Joint Origin N. A click selects; a double-click edits;
// Delete removes the selected feature (its rectangle stays in the sketch).
import { Glyph } from "@bam/ui";
import { useStudio } from "../store";

export function Timeline() {
  const sel = useStudio((s) => s.sel);
  const features = useStudio((s) => s.doc.features);
  const panel = useStudio((s) => s.panel);
  const st = useStudio.getState;
  const items = [
    { id: "sketch", tl: "sketch", fid: undefined as string | undefined, name: "Sketch", glyph: "sketch", on: sel?.kind === "sketch",
      click: () => st().select({ kind: "sketch" }), dbl: () => { st().setTool("select"); st().fit(); } },
    ...features.flatMap((f, i) => {
      const editing = panel.open && panel.featureId === f.id;
      // a feature still waiting for its rectangle shows only while its panel is open
      if (!f.rectId && !editing) return [];
      const n = i + 1;
      return [
        { id: `extrude-${f.id}`, tl: "extrude", fid: f.id, name: `ArUco Extrude ${n}`, glyph: "extrude",
          on: (sel?.kind === "feature" && sel.id === f.id) || editing,
          click: () => st().select({ kind: "feature", id: f.id }), dbl: () => st().editFeature(f.id) },
        { id: `origin-${f.id}`, tl: "origin", fid: f.id, name: `Joint Origin ${n}`, glyph: "joint", on: sel?.kind === "origin" && sel.id === f.id,
          click: () => st().select({ kind: "origin", id: f.id }), dbl: () => st().editFeature(f.id) },
      ];
    }),
  ];
  return (
    <footer className="timeline" data-testid="timeline">
      <span className="tl-label">Timeline</span>
      <div className="tl-track">
        {items.map((it) => (
          <button type="button" key={it.id} className={`tl-item${it.on ? " on" : ""}`} data-tl={it.tl} data-feature={it.fid}
            title={`${it.name} (double-click to edit)`} aria-label={it.name} onClick={it.click} onDoubleClick={it.dbl}>
            <Glyph name={it.glyph} /><span className="tl-name">{it.name}</span>
          </button>
        ))}
      </div>
    </footer>
  );
}
