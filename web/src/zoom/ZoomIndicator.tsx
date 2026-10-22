// The zoom, Miro's (Zach, 2026-10-21, from Miro's own bottom-right control):
// the percent in the calm pill at the bottom right, beside ? (../app/TopBar.tsx
// HelpCorner); a hover lights it, a click opens Miro's zoom rows
// (./ZoomItems.tsx ZoomPillItems): Fit to screen, Zoom to selection, Actual
// size, Calibrate, then 50 / 100 / 200 / 400 %. No + / − buttons: the wheel,
// Ctrl+wheel and a pinch zoom (Viewport.tsx). 100 % is the browser's
// millimetre; at this screen's real millimetre the pill says "Actual size",
// and "estimated" beside it until the screen is calibrated (./scale.ts).
// WHY the words at Actual size, not a percent: a percent there would hide
// that it is the screen's own millimetre (the actualsize lane, Zach
// 2026-10-21: "When actual size it should determine my screen resolution
// etc and correctly display it"). The canvas's right-click menu keeps its own
// zoom rows (ZoomItems). Hidden in 3D (the 3D view zooms on its own).
import { Menu as M } from "@base-ui/react/menu";
import { useStudio } from "../store";
import "./zoom.css";
import { isActual, perInchOf, useScale, zoomPercent } from "./scale";
import { ZoomPillItems } from "./ZoomItems";

export function ZoomIndicator() {
  const zoom = useStudio((s) => s.camera.zoom);
  const view3d = useStudio((s) => s.view3d);
  const scale = useScale((s) => s.scale);
  if (view3d) return null;
  const actual = isActual(zoom, scale.pxPerMm);
  const scaleText = `${scale.pxPerMm.toFixed(2)} px/mm (${Math.round(perInchOf(scale.pxPerMm))} px/in), ${scale.basis}`;
  return (
    <>
      <span className="zoom-pill" data-testid="zoom-indicator" data-actual={actual ? "1" : "0"} data-calibrated={scale.calibrated ? "1" : "0"}
        data-zoom={zoom} data-px-per-mm={scale.pxPerMm} data-screen={scale.key}>
        <M.Root modal={false}>
          <M.Trigger className="zi-btn" data-testid="zoom-menu" aria-label="Zoom"
            title={actual ? `Actual size on this screen: ${scaleText}${scale.calibrated ? "" : ". A guess: calibrate it in this menu"}` : `Zoom: ${zoomPercent(zoom)}% of the browser's millimetre`}>
            <span className="zi-text" data-testid="zoom-text">{actual ? "Actual size" : `${zoomPercent(zoom)}%`}</span>
            {/* WHY said, not hidden (truthful rendering): an uncalibrated scale is a guess, and the pill never claims it as exact */}
            {actual && !scale.calibrated && " "}
            {actual && !scale.calibrated && <span className="zi-est" data-testid="zoom-estimated">estimated</span>}
          </M.Trigger>
          <M.Portal>
            <M.Positioner side="top" align="end" sideOffset={10} collisionPadding={8} className="kit-menu-positioner">
              <M.Popup className="kit-menu-popup mm-popup zm-popup" data-kit-popup="menu" data-testid="zoom-menu-popup">
                <ZoomPillItems />
              </M.Popup>
            </M.Positioner>
          </M.Portal>
        </M.Root>
      </span>
      <span className="cp-sep" aria-hidden="true" />
    </>
  );
}
