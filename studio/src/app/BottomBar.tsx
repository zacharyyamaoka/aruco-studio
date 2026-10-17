// The bottom toolbar (MC-6): the tools with their keys on badges, the
// active one lit; what you type for it (80 50), what it waits for; S opens
// the command palette.
import { ArrowUpFromLine, Circle, CircleDot, MousePointer2, Pentagon, Pill, QrCode, RectangleHorizontal, Search, SquareDot } from "lucide-react";
import type { ReactNode } from "react";
import { Kbd, ToolButton } from "../kit";
import { useStudio, TYPED_TOOLS, type ToolId } from "../store";
import { TOOLS } from "./commands";

export const TOOL_ICONS: Record<ToolId, ReactNode> = {
  select: <MousePointer2 size={16} />,
  rect: <RectangleHorizontal size={16} />,
  circle: <Circle size={16} />,
  polygon: <Pentagon size={16} />,
  slot: <Pill size={16} />,
  hole: <CircleDot size={16} />,
  rhole: <SquareDot size={16} />,
  extrude: <ArrowUpFromLine size={16} />,
  aruco: <QrCode size={16} />,
};

const ASK: Record<ToolId, string> = {
  select: "",
  rect: "drag a box, or type W H and Enter",
  circle: "drag a diameter, or type D and Enter",
  polygon: "click the points; Enter or the first point closes",
  slot: "drag the length, or type L W and Enter",
  hole: "click inside a shape, or type D and Enter (the selected shape's centre)",
  rhole: "click inside a shape, or type W H and Enter",
  extrude: "type the height, Enter (or drag the arrow in 3D)",
  aruco: "click a shape or a face (Shift+click more), then Enter",
};

export function BottomBar() {
  const tool = useStudio((s) => s.tool);
  const typed = useStudio((s) => s.typed);
  const picks = useStudio((s) => s.picks);
  const draft = useStudio((s) => s.draft);
  const st = useStudio.getState();
  return (
    <div className="bottombar" data-testid="bottombar">
      {(tool !== "select") && (
        <div className="tool-ask" data-testid="tool-ask">
          <b>{TOOLS.find((t) => t.tool === tool)?.name}</b>
          <span className="muted">{ASK[tool]}</span>
          {TYPED_TOOLS.includes(tool) && <span className="typed" data-testid="typed">{typed || " "}<i className="caret" /></span>}
          {tool === "aruco" && <span className="picks" data-testid="picks" data-picks={picks.join(",")}>{picks.length ? picks.join(" · ") : "nothing picked"}</span>}
          {tool === "polygon" && <span className="picks" data-testid="draft-points">{draft.length} points</span>}
          <span className="keys"><Kbd keys="Enter" /> confirm <Kbd keys="Esc" /> cancel</span>
        </div>
      )}
      <div className="tools" role="toolbar" aria-label="Tools">
        {TOOLS.map((t) => (
          <ToolButton key={t.tool} icon={TOOL_ICONS[t.tool]} name={t.name} keys={t.key} active={tool === t.tool}
            testid={`tool-${t.tool}`} onClick={() => st.setTool(tool === t.tool && t.tool !== "select" ? "select" : t.tool)} />
        ))}
        <span className="tools-sep" />
        <ToolButton icon={<Search size={16} />} name="Search commands" keys="S" testid="tool-search" onClick={() => st.setPalette(true)} />
      </div>
    </div>
  );
}
