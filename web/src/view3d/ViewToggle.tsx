// The 2D | 3D toggle (V3 "3D Toggle", Zach 2026-10-20 night: "as we are always
// going to be in a 3D modelling like that, to me it's the most natural"): a
// small segmented control at the end of the dock (../app/Toolbar.tsx), where
// Figma puts its Dev Mode switch (V2, picked 2026-10-20 night); 3 toggles it.
// The view state is the store's (view3d), not the document's.
import { SegmentedRow } from "@bam/ui";
import { useStudio } from "../store";
import "./view3d.css";

const OPTIONS = [
  { value: "2d", label: "2D", hint: "The sketch (3)" },
  { value: "3d", label: "3D", hint: "The model, with its heights (3)" },
];

export function ViewToggle() {
  const on = useStudio((s) => s.view3d);
  return (
    <div className="v3-toggle" data-testid="view-toggle" data-view={on ? "3d" : "2d"}>
      <SegmentedRow compact value={on ? "3d" : "2d"} options={OPTIONS} testid="view-seg"
        onChange={(v) => useStudio.getState().setView3d(v === "3d")} />
    </div>
  );
}
