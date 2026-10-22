// The zoom group the menus share, in the kit's menu rows: the canvas's
// right-click menu and View (which has its own Fit); the zoom pill has
// Miro's rows (ZoomPillItems, below). Figma's keys: Shift+1 fit, Shift+2
// selection; Shift+0 (Figma's 100 %) is Actual size here, the real
// millimetre, and Zoom 100 % is CSS's millimetre.
import { MenuItem, MenuSeparator } from "@bam/ui";
import type { Vec2 } from "../core/contract";
import { useStudio } from "../store";
import { useScale } from "./scale";
import { actualSize, openCalibrate, selectionBox, zoom100, ZOOM_STEPS, zoomToFit, zoomToPercent, zoomToSelection } from "./zoom";

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

/** The zoom pill's menu, Miro's (Zach, 2026-10-21, from Miro's zoom menu):
 *  Fit to screen, Zoom to selection, Actual size ("estimated" until this
 *  screen is calibrated), Calibrate, then the steps 50 / 100 / 200 / 400 %
 *  (100 % is the browser's millimetre), each about the view's centre. */
export function ZoomPillItems() {
  const calibrated = useScale((s) => s.scale.calibrated);
  const selected = useStudio((s) => !!selectionBox(s.doc, s.plans, s.sel, s.multi));
  return (
    <>
      <MenuItem label="Fit to screen" hint="Shift+1" testid="zm-zoom-fit" onClick={zoomToFit} />
      <MenuItem label="Zoom to selection" hint="Shift+2" testid="zm-zoom-selection" disabled={!selected}
        title={selected ? undefined : "Nothing is selected"} onClick={() => { zoomToSelection(); }} />
      {/* WHY "estimated" in the row (truthful rendering): until this screen is calibrated, Actual size is a guess */}
      <MenuItem testid="zm-actual-size" hint="Shift+0" onClick={() => actualSize()}
        label={calibrated ? "Actual size" : <>Actual size <span className="zm-est">estimated</span></>}
        title={calibrated ? "1 mm on the model is 1 mm on this screen (calibrated)" : "1 mm on the model is about 1 mm on this screen: a guess until you calibrate"} />
      <MenuItem label={calibrated ? "Recalibrate actual size…" : "Calibrate actual size…"} testid="zm-calibrate" onClick={openCalibrate} />
      <MenuSeparator />
      {ZOOM_STEPS.map((p) => (
        <MenuItem key={p} label={`${p}%`} testid={`zm-zoom-${p}`} onClick={() => zoomToPercent(p)}
          title={p === 100 ? "The browser's millimetre: 96 px per inch, the size a print preview shows" : undefined} />
      ))}
    </>
  );
}
