// The zoom group every menu shares, in the kit's menu rows: the canvas's
// right-click menu, the zoom indicator's, and View (which has its own Fit).
// Figma's keys: Shift+1 fit, Shift+2 selection; Shift+0 (Figma's 100 %) is
// Actual size here, the real millimetre, and Zoom 100 % is CSS's millimetre.
import { MenuItem } from "@bam/ui";
import type { Vec2 } from "../core/contract";
import { useStudio } from "../store";
import { useScale } from "./scale";
import { actualSize, openCalibrate, selectionBox, zoom100, zoomToFit, zoomToSelection } from "./zoom";

/** `at`: the view point (px) Actual size and 100 % zoom about (the right-click's; default the view's centre). */
export function ZoomItems({ prefix, at, fit = true }: { prefix: string; at?: Vec2; fit?: boolean }) {
  const calibrated = useScale((s) => s.scale.calibrated);
  const selected = useStudio((s) => !!selectionBox(s.doc, s.plans, s.sel, s.multi));
  return (
    <>
      {fit && <MenuItem label="Zoom to fit" hint="Shift+1" testid={`${prefix}-zoom-fit`} onClick={zoomToFit} />}
      <MenuItem label="Zoom to selection" hint="Shift+2" testid={`${prefix}-zoom-selection`} disabled={!selected}
        title={selected ? undefined : "Nothing is selected"} onClick={() => { zoomToSelection(); }} />
      {/* WHY "estimated" in the row (truthful rendering): until this screen is
          calibrated, Actual size is a guess, and the menu says so */}
      <MenuItem testid={`${prefix}-actual-size`} hint="Shift+0" onClick={() => actualSize(at)}
        label={calibrated ? "Actual size" : <>Actual size <span className="zm-est">estimated</span></>}
        title={calibrated ? "1 mm on the model is 1 mm on this screen (calibrated)" : "1 mm on the model is about 1 mm on this screen: a guess until you calibrate"} />
      <MenuItem label="Zoom 100 %" testid={`${prefix}-zoom-100`} onClick={() => zoom100(at)}
        title="The browser's millimetre: 96 px per inch, the size a print preview shows" />
      <MenuItem label={calibrated ? "Recalibrate actual size…" : "Calibrate actual size…"} testid={`${prefix}-calibrate`} onClick={openCalibrate} />
    </>
  );
}
