// Every command of the Studio, once: its name, its key, its group and what
// it runs. The bottom toolbar, the command palette (S), the key handler and
// the keys table of docs/STUDIO.md are all this list (the e2e test diffs
// the palette with the doc's table).
import { useStudio, type ToolId } from "../store";

export interface Command {
  id: string;
  name: string;
  /** what to press; "" when only the palette runs it */
  key: string;
  group: "Tools" | "Edit" | "View" | "Tag" | "File" | "Export";
  icon: string;
  run: () => unknown;
  /** a tool: lit in the bottom bar while it is the active one */
  tool?: ToolId;
  hint?: string;
}

const st = () => useStudio.getState();

export const TOOLS: { tool: ToolId; name: string; key: string; icon: string; hint: string }[] = [
  { tool: "select", name: "Select / move", key: "V", icon: "pointer", hint: "click, Shift+click, marquee; drag moves (0.5 mm); handles on the selection" },
  { tool: "rect", name: "Rectangle", key: "R", icon: "rect", hint: "drag a box (Alt from the centre, Shift square), or type 80 50 Enter" },
  { tool: "circle", name: "Circle", key: "C", icon: "circle", hint: "drag a diameter, or type 50 Enter" },
  { tool: "polygon", name: "Polygon", key: "P", icon: "polygon", hint: "click the points; Enter or the first point closes" },
  { tool: "slot", name: "Slot", key: "O", icon: "slot", hint: "drag the length, or type 40 12 Enter" },
  { tool: "hole", name: "Hole", key: "H", icon: "hole", hint: "click inside a shape (type the diameter first), or type 18 Enter for the selection's centre" },
  { tool: "rhole", name: "Rectangular hole", key: "Shift+H", icon: "rhole", hint: "click inside a shape, or type 10 6 Enter" },
  { tool: "extrude", name: "Extrude", key: "E", icon: "extrude", hint: "the selected shape: type the height, Enter; or drag the arrow in 3D" },
  { tool: "aruco", name: "ArUco Extrude", key: "A", icon: "arucoext", hint: "click a shape or a face; Shift+click more; Enter" },
];

export function commands(): Command[] {
  const tools: Command[] = TOOLS.map((t) => ({
    id: `tool.${t.tool}`, name: t.name, key: t.key, group: "Tools", icon: t.icon, tool: t.tool, hint: t.hint,
    run: () => st().setTool(t.tool),
  }));
  return [
    ...tools,
    { id: "edit.rotcw", name: "Rotate 90° clockwise", key: "]", group: "Edit", icon: "rotate", run: () => st().rotateSel(-90) },
    { id: "edit.rotccw", name: "Rotate 90° counter-clockwise", key: "[", group: "Edit", icon: "rotate", run: () => st().rotateSel(90) },
    { id: "edit.palette", name: "Search commands", key: "S", group: "Edit", icon: "search", run: () => st().setPalette(true) },
    { id: "edit.dup", name: "Duplicate", key: "Ctrl+D", group: "Edit", icon: "dup", run: () => st().duplicateSel() },
    { id: "edit.del", name: "Delete", key: "Del", group: "Edit", icon: "trash", run: () => st().deleteSel() },
    { id: "edit.undo", name: "Undo", key: "Ctrl+Z", group: "Edit", icon: "undo", run: () => st().undo() },
    { id: "edit.redo", name: "Redo", key: "Ctrl+Y", group: "Edit", icon: "redo", run: () => st().redo() },
    { id: "edit.all", name: "Select all", key: "Ctrl+A", group: "Edit", icon: "pointer", run: () => st().selectAll() },
    { id: "edit.cancel", name: "Cancel", key: "Esc", group: "Edit", icon: "close", run: () => st().cancel() },
    { id: "edit.confirm", name: "Confirm", key: "Enter", group: "Edit", icon: "check", run: () => st().confirm() },
    { id: "edit.arrange", name: "Arrange in a row", key: "", group: "Edit", icon: "arrange", run: () => st().arrange() },
    { id: "view.fit", name: "Zoom to fit", key: "F", group: "View", icon: "fit", run: () => st().zoomToFit(st().sel.length ? st().sel : undefined) },
    { id: "view.toggle", name: "2D / 3D", key: "Tab", group: "View", icon: "view3d", run: () => st().toggleView() },
    { id: "view.keys", name: "Keys", key: "?", group: "View", icon: "help", run: () => st().setDrawer(st().drawer === "messages" ? null : "messages") },
    { id: "view.quiet", name: "Quiet zones", key: "", group: "View", icon: "quiet", run: () => st().setShow("quiet", !st().show.quiet) },
    { id: "view.axes", name: "Frame axes", key: "", group: "View", icon: "axes", run: () => st().setShow("axes", !st().show.axes) },
    { id: "view.outlines", name: "Layer outlines", key: "", group: "View", icon: "outline", run: () => st().setShow("outlines", !st().show.outlines) },
    { id: "view.file", name: "File drawer", key: "", group: "View", icon: "file", run: () => st().setDrawer(st().drawer === "file" ? null : "file") },
    { id: "tag.verify", name: "Verify", key: "", group: "Tag", icon: "verify", run: () => st().verifySel() },
    { id: "tag.verifysheet", name: "Verify the sheet", key: "", group: "Tag", icon: "sheet", run: () => st().verifyScene() },
    { id: "tag.renumber", name: "Renumber all", key: "", group: "Tag", icon: "renumber", run: () => st().renumber() },
    { id: "tag.single", name: "ArUco: single", key: "", group: "Tag", icon: "single", run: () => st().addTag("single") },
    { id: "tag.grid", name: "ArUco: grid", key: "", group: "Tag", icon: "grid", run: () => st().addTag("grid") },
    { id: "tag.charuco", name: "ArUco: ChArUco", key: "", group: "Tag", icon: "charuco", run: () => st().addTag("charuco") },
    { id: "tag.library", name: "Preset library", key: "", group: "Tag", icon: "library", run: () => st().setLibrary(true) },
    { id: "file.new", name: "New scene", key: "", group: "File", icon: "newdoc", run: () => st().setDialog({ kind: "new" }) },
    { id: "file.open", name: "Open", key: "Ctrl+O", group: "File", icon: "open", run: () => st().setDialog({ kind: "open" }) },
    { id: "file.saveas", name: "Save as", key: "", group: "File", icon: "save", run: () => st().setDialog({ kind: "save" }) },
    { id: "file.reveal", name: "Reveal the file", key: "", group: "File", icon: "folder", run: () => st().reveal() },
    { id: "export.svg", name: "Export: print sheet SVG", key: "", group: "Export", icon: "sheet", run: () => st().exportScene("svg") },
    { id: "export.pdf", name: "Export: sticker sheet PDF", key: "", group: "Export", icon: "sheet", run: () => st().exportScene("pdf") },
    { id: "export.stl", name: "Export: STL of every tag", key: "", group: "Export", icon: "cube", run: () => st().exportScene("stl") },
  ];
}

/** "Ctrl+D" -> ["Ctrl", "D"] for the badges. */
export function keyParts(key: string): string[] {
  return key ? key.split("+") : [];
}
