// The tools, each with its name and its key: Select V, Rectangle R, Circle
// C, ArUco Extrude A, then Sheet P (the print dialog) and Verify, then Fit F. WHY words beside the icons (Zach, 2026-10-18: "I like the use
// of text instead of icons here"); a phone keeps the icons only (styles.css).
// The kit's ToolButton is icon-only, so this one is here, in its classes.
import { Glyph, cn } from "@bam/ui";
import type { ReactNode } from "react";
import { useStudio } from "../store";
import { openPrint, openVerify } from "./commands";

function Tool({ icon, name, full, keys, active, onClick, testid }: {
  icon: ReactNode; name: string; full?: string; keys?: string; active?: boolean; onClick: () => void; testid: string;
}) {
  return (
    <button type="button" className={cn("tb-tool", active && "on")} title={keys ? `${full ?? name} (${keys})` : full ?? name} aria-label={full ?? name}
      aria-pressed={!!active} data-testid={testid} data-active={active ? "1" : "0"} onClick={onClick}>
      {icon}<span className="tb-name">{name}</span>{keys && <span className="tb-key" data-badge={keys}>{keys}</span>}
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
      <span className="tb-sep" />
      <Tool icon={<Glyph name="extrude" />} name="ArUco Extrude" full="ArUco Extrude: the marker in the selected rectangle or face" keys="A" active={panelOpen} onClick={() => void st().extrude()} testid="tool-extrude" />
      <span className="tb-sep" />
      <Tool icon={<Glyph name="print" />} name="Sheet" full="Sheet: print the stickers" keys="S" onClick={openPrint} testid="tool-sheet" />
      <Tool icon={<Glyph name="verify" />} name="Verify" full="Verify: a simulated camera reads the marker" keys="K" onClick={openVerify} testid="tool-verify" />
      <span className="tb-sep" />
      <Tool icon={<Glyph name="fit" />} name="Fit" keys="F" onClick={() => st().fit()} testid="tool-fit" />
    </div>
  );
}
