// The dock: Figma's bottom toolbar (V2 "Figma · Corner pills", Zach's pick on
// 2026-10-20 night: "For the design let's please follow Figma!"). The tools
// Select V, Rectangle R, Circle C, Dimension D (Fusion's Sketch Dimension),
// then ArUco Extrude A, Fit F with Layers beside it (what the canvas shows,
// ../overlays/LayersMenu.tsx; Zach 2026-10-21: in the dock, not a group of
// its own), and the 2D | 3D switch at its end (Figma's Dev Mode switch). Each
// tool is its icon; its name and key are in the tooltip. Verify and Print are
// the top-right pill's (./TopBar.tsx).
// The kit's ToolButton is icon-only with its own key badge, so this one is
// here, in its classes.
import { Glyph, cn, hasGlyph, registerGlyphs } from "@bam/ui";
import type { ReactNode } from "react";
import { LayersMenu } from "../overlays/LayersMenu";
import { useStudio } from "../store";
import { ViewToggle } from "../view3d/ViewToggle";

// a dimension: two extension lines and an arrowed line between them
if (!hasGlyph("dimension")) {
  registerGlyphs({
    dimension: '<path d="M2.5 3v10M13.5 3v10M2.5 8h11" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M2.5 8l2.5-2v4zM13.5 8l-2.5-2v4z" fill="currentColor"/>',
  });
}

function Tool({ icon, name, full, keys, active, onClick, testid }: {
  icon: ReactNode; name: string; full?: string; keys?: string; active?: boolean; onClick: () => void; testid: string;
}) {
  return (
    <button type="button" className={cn("tb-tool", active && "on")} title={keys ? `${full ?? name} (${keys})` : full ?? name} aria-label={name}
      aria-pressed={!!active} data-testid={testid} data-active={active ? "1" : "0"} data-key={keys} onClick={onClick}>
      {icon}
    </button>
  );
}

export function Toolbar() {
  const tool = useStudio((s) => s.tool);
  const panelOpen = useStudio((s) => s.panel.open);
  const st = useStudio.getState;
  return (
    <div className="toolbar" role="toolbar" aria-label="Tools" data-testid="toolbar">
      <Tool icon={<Glyph name="pointer" />} name="Select" keys="V" active={tool === "select"} onClick={() => st().setTool("select")} testid="tool-select" />
      <Tool icon={<Glyph name="rect" />} name="Rectangle" keys="R" active={tool === "rect"} onClick={() => st().setTool("rect")} testid="tool-rect" />
      <Tool icon={<Glyph name="circle" />} name="Circle" keys="C" active={tool === "circle"} onClick={() => st().setTool("circle")} testid="tool-circle" />
      <Tool icon={<Glyph name="dimension" />} name="Dimension" full="Dimension: click an edge, a circle, or two references, drag to place, type the value" keys="D"
        active={tool === "dim"} onClick={() => st().setTool("dim")} testid="tool-dim" />
      <span className="tb-sep" />
      <Tool icon={<Glyph name="extrude" />} name="ArUco Extrude" full="ArUco Extrude: the marker in the selected profile (click inside a region, or double-click a rectangle)" keys="A" active={panelOpen} onClick={() => void st().extrude()} testid="tool-extrude" />
      <span className="tb-sep" />
      <Tool icon={<Glyph name="fit" />} name="Fit" keys="F" onClick={() => st().fit()} testid="tool-fit" />
      <LayersMenu />
      <span className="tb-sep" />
      <ViewToggle />
    </div>
  );
}
