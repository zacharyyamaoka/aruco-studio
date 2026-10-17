// The command palette (cmdk): every command by name with its key; typing
// filters, Enter runs the first, Esc closes.
import { Command } from "cmdk";
import type { ReactNode } from "react";
import { Kbd } from "./Kbd";

export interface PaletteItem { id: string; name: string; key: string; group: string; icon?: ReactNode; hint?: string; run: () => unknown }

export function CommandPalette({ items, onClose, placeholder = "Type a command…" }: { items: PaletteItem[]; onClose: () => void; placeholder?: string }) {
  const groups = [...new Set(items.map((i) => i.group))];
  return (
    <div className="kit-palette-back" onMouseDown={(e) => e.target === e.currentTarget && onClose()} data-testid="palette">
      <Command label="Commands" className="kit-palette" loop
        onKeyDown={(e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); onClose(); } }}>
        <Command.Input autoFocus placeholder={placeholder} data-testid="palette-input" />
        <Command.List>
          <Command.Empty>No command by that name.</Command.Empty>
          {groups.map((g) => (
            <Command.Group key={g} heading={g}>
              {items.filter((i) => i.group === g).map((i) => (
                <Command.Item key={i.id} value={`${i.name} ${i.id}`} keywords={[i.group]} data-command={i.name} data-command-id={i.id}
                  onSelect={() => { onClose(); i.run(); }}>
                  {i.icon}
                  <span className="kit-palette-name">{i.name}</span>
                  {i.hint && <span className="kit-palette-hint">{i.hint}</span>}
                  <Kbd keys={i.key} />
                </Command.Item>
              ))}
            </Command.Group>
          ))}
        </Command.List>
      </Command>
    </div>
  );
}
