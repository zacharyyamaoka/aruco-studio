// The selected shape's typed size: W × H for a rectangle (about its
// centre), Ø for a circle; a selected feature's rectangle too. Lives in the
// viewport's bottom-left corner.
import { NumberField } from "@bam/ui";
import { featureRect, getFeature } from "../model/doc";
import { useStudio } from "../store";

export function ShapeDims() {
  const sel = useStudio((s) => s.sel);
  const doc = useStudio((s) => s.doc);
  const update = useStudio((s) => s.updateShape);
  const s = sel?.kind === "shape" ? doc.shapes.find((x) => x.id === sel.id)
    : sel?.kind === "feature" ? featureRect(doc, getFeature(doc, sel.id)) ?? undefined : undefined;
  if (!s || s.kind === "poly") return null;
  return (
    <div className="dims-box" data-testid="shape-dims" data-shape-kind={s.kind}>
      {s.kind === "rect" ? (
        <>
          <span className="dims-name">Rectangle</span>
          <NumberField label="W" value={s.w} unit="mm" path="shape.w" min={0.5} step={0.5}
            onCommit={(v) => update({ ...s, w: v })} />
          <span className="dims-x">×</span>
          <NumberField label="H" value={s.h} unit="mm" path="shape.h" min={0.5} step={0.5}
            onCommit={(v) => update({ ...s, h: v })} />
        </>
      ) : (
        <>
          <span className="dims-name">Circle</span>
          <NumberField label="Ø" value={s.r * 2} unit="mm" path="shape.d" min={1} step={0.5}
            onCommit={(v) => update({ ...s, r: v / 2 })} />
        </>
      )}
    </div>
  );
}
