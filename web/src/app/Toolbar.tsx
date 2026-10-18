// The tools, each with its key: Select V, Rectangle R, Circle C, ArUco
// Extrude A, Fit F, Print P.
import { Glyph, ToolButton } from "@bam/ui";
import { useStudio } from "../store";
import { openPrint } from "./commands";

export function Toolbar() {
  const tool = useStudio((s) => s.tool);
  const panelOpen = useStudio((s) => s.panel.open);
  const st = useStudio.getState;
  return (
    <div className="toolbar" role="toolbar" aria-label="Tools" data-testid="toolbar">
      <ToolButton icon={<Glyph name="pointer" />} name="Select" keys="V" active={tool === "select"} onClick={() => st().setTool("select")} testid="tool-select" />
      <ToolButton icon={<Glyph name="rect" />} name="Rectangle" keys="R" active={tool === "rect"} onClick={() => st().setTool("rect")} testid="tool-rect" />
      <ToolButton icon={<Glyph name="circle" />} name="Circle" keys="C" active={tool === "circle"} onClick={() => st().setTool("circle")} testid="tool-circle" />
      <span className="tb-sep" />
      <ToolButton icon={<Glyph name="extrude" />} name="ArUco Extrude" keys="A" active={panelOpen} onClick={() => void st().extrude()} testid="tool-extrude" />
      <span className="tb-sep" />
      <ToolButton icon={<Glyph name="fit" />} name="Fit" keys="F" onClick={() => st().fit()} testid="tool-fit" />
      <ToolButton icon={<Glyph name="print" />} name="Print" keys="P" onClick={openPrint} testid="tool-print" />
    </div>
  );
}
