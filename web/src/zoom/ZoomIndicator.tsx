// The zoom indicator, bottom left of the 2D canvas: the zoom in percent (100 %
// is the browser's millimetre), or "Actual size" when the camera is at this
// screen's real millimetre; a click opens the zoom menu (./ZoomItems.tsx).
// WHY bottom left: the corner nothing else uses, by the canvas it measures,
// as tldraw and Excalidraw keep their zoom; its words change length (a
// percent, "Actual size (estimated — calibrate)") and there they move no
// other control (the dock is centred, the corner pills are anchored out).
import { Menu as M } from "@base-ui/react/menu";
import { useStudio } from "../store";
import "./zoom.css";
import { isActual, perInchOf, useScale, zoomPercent } from "./scale";
import { openCalibrate } from "./zoom";
import { ZoomItems } from "./ZoomItems";

export function ZoomIndicator() {
  const zoom = useStudio((s) => s.camera.zoom);
  const view3d = useStudio((s) => s.view3d);
  const scale = useScale((s) => s.scale);
  if (view3d) return null;
  const actual = isActual(zoom, scale.pxPerMm);
  const scaleText = `${scale.pxPerMm.toFixed(2)} px/mm (${Math.round(perInchOf(scale.pxPerMm))} px/in), ${scale.basis}`;
  return (
    <div className="zoom-pill" data-testid="zoom-indicator" data-actual={actual ? "1" : "0"} data-calibrated={scale.calibrated ? "1" : "0"}
      data-zoom={zoom} data-px-per-mm={scale.pxPerMm} data-screen={scale.key}>
      <M.Root modal={false}>
        <M.Trigger className="zi-btn" data-testid="zoom-menu" aria-label="Zoom"
          title={actual ? `Actual size on this screen: ${scaleText}` : `Zoom: ${zoomPercent(zoom)} % of the browser's millimetre`}>
          <span className="zi-text" data-testid="zoom-text">{actual ? "Actual size" : `${zoomPercent(zoom)} %`}</span>
        </M.Trigger>
        <M.Portal>
          <M.Positioner side="top" align="start" sideOffset={8} className="kit-menu-positioner">
            <M.Popup className="kit-menu-popup mm-popup" data-kit-popup="menu" data-testid="zoom-menu-popup">
              <ZoomItems prefix="zm" />
            </M.Popup>
          </M.Positioner>
        </M.Portal>
      </M.Root>
      {/* WHY said, not hidden (truthful rendering): an uncalibrated scale is a
          guess, and the indicator never claims it as exact */}
      {actual && !scale.calibrated && " "}
      {actual && !scale.calibrated && (
        <span className="zi-est" data-testid="zoom-estimated">
          (estimated — <button type="button" className="zi-cal" data-testid="zoom-calibrate" title={`A guess: ${scaleText}. Calibrate with a bank card or a ruler.`}
            onClick={openCalibrate}>calibrate</button>)
        </span>
      )}
    </div>
  );
}
