// S: the command palette. Every command of commands.ts by name, with its
// key; typing filters, Enter runs it.
import { CommandPalette } from "@bam/ui";
import { Glyph as Icon } from "@bam/ui";
import { useStudio } from "../store";
import { TOOL_ICONS } from "./BottomBar";
import { commands } from "./commands";

export function Palette() {
  const open = useStudio((s) => s.palette);
  if (!open) return null;
  const items = commands().map((c) => ({ ...c, icon: c.tool ? TOOL_ICONS[c.tool] : <Icon name={c.icon} /> }));
  return <CommandPalette items={items} onClose={() => useStudio.getState().setPalette(false)} />;
}
