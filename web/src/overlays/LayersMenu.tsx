// The Layers menu (V8 "Overlays menu", Zach's pick 2026-10-21): one button
// in the dock (../app/Toolbar.tsx, beside Fit: not a group of its own) opens
// every setting of what the 2D canvas shows (./overlays.ts). First the
// background, Miro's View › Grid: Dots | Grid | Blank; then one switch per
// layer, as Miro's View menu shows its toggles ("Object dimensions"): the name,
// a switch at the row's end, and the menu stays open so several are set in
// one go. Marker info is the same switch as View › Marker info.
import { Menu as M } from "@base-ui/react/menu";
import { Check, ChevronRight, Layers } from "lucide-react";
import type { ReactNode } from "react";
import { useStudio } from "../store";
import { BACKGROUNDS, useOverlays, type Background, type OverlayKey } from "./overlays";
import "./overlays.css";

const BACKGROUND_NAMES: Record<Background, string> = { dots: "Dots", grid: "Grid", blank: "Blank" };

/** The switches, in the menu's order (Marker info, the store's, between the guides and the rulers). */
const ROWS: { key: OverlayKey | "markerInfo"; label: ReactNode }[] = [
  { key: "dims", label: "Sketch dimensions" },
  { key: "origins", label: "Joint Origins" },
  { key: "edges", label: "Profile edges" },
  { key: "guides", label: "Quiet-zone guides" },
  { key: "markerInfo", label: <>Marker info <span className="hint">id · dictionary · size</span></> },
  { key: "rulers", label: "Rulers" },
];

/** A layer's row: its name, and a switch at the end that says whether it is drawn. */
function SwitchRow({ on, label, testid, onClick }: { on: boolean; label: ReactNode; testid: string; onClick: () => void }) {
  return (
    <M.Item className="kit-menu-item lm-row" data-testid={testid} role="menuitemcheckbox" aria-checked={on} closeOnClick={false} onClick={onClick}>
      <span className="kit-menu-label">{label}</span>
      <span className="lm-switch" data-checked={on ? "" : undefined} aria-hidden="true"><span className="lm-thumb" /></span>
    </M.Item>
  );
}

export function LayersMenu() {
  const o = useOverlays((s) => s.overlays);
  const markerInfo = useStudio((s) => s.markerInfo);
  const { setBackground, setOverlay } = useOverlays.getState();
  return (
    <M.Root modal={false}>
      <M.Trigger className="tb-tool" data-testid="tool-layers" title="Layers: what the canvas shows" aria-label="Layers">
        <Layers size={18} strokeWidth={1.75} />
      </M.Trigger>
      <M.Portal>
        <M.Positioner side="top" align="center" sideOffset={12} collisionPadding={8} className="kit-menu-positioner">
          <M.Popup className="kit-menu-popup mm-popup lm-popup" data-kit-popup="menu" data-testid="layers-menu">
            <M.SubmenuRoot>
              <M.SubmenuTrigger className="kit-menu-item mm-sub lm-row" data-testid="layers-grid">
                <span className="kit-menu-label">Grid</span>
                <span className="hint" data-testid="layers-grid-value">{BACKGROUND_NAMES[o.background]}</span>
                <ChevronRight size={14} className="mm-chev" />
              </M.SubmenuTrigger>
              <M.Portal>
                <M.Positioner side="right" align="start" sideOffset={4} alignOffset={-5} collisionPadding={8} className="kit-menu-positioner">
                  <M.Popup className="kit-menu-popup mm-popup lm-sub" data-kit-popup="menu" data-testid="layers-grid-popup">
                    {BACKGROUNDS.map((b) => (
                      <M.Item key={b} className="kit-menu-item" data-testid={`layers-bg-${b}`} role="menuitemradio" aria-checked={o.background === b}
                        closeOnClick={false} onClick={() => setBackground(b)}>
                        <span className="ic">{o.background === b && <Check size={14} />}</span><span className="kit-menu-label">{BACKGROUND_NAMES[b]}</span>
                      </M.Item>
                    ))}
                  </M.Popup>
                </M.Positioner>
              </M.Portal>
            </M.SubmenuRoot>
            <M.Separator className="kit-menu-sep" />
            {ROWS.map(({ key, label }) => key === "markerInfo"
              ? <SwitchRow key={key} on={markerInfo} label={label} testid="layers-marker-info" onClick={() => useStudio.getState().setMarkerInfo(!markerInfo)} />
              : <SwitchRow key={key} on={o[key]} label={label} testid={`layers-${key}`} onClick={() => setOverlay(key, !o[key])} />)}
          </M.Popup>
        </M.Positioner>
      </M.Portal>
    </M.Root>
  );
}
