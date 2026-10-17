// The command palette (cmdk): every command by name with its key; typing
// filters (by the name first: paletteRank.ts), Enter runs the first, Esc
// closes. The kit ranks and orders the list itself (cmdk's own sort lags a
// keystroke when hidden items come back, so "Slot" selected "Select /
// move": the 2026-10-17 audit) and selects the first item on every change.
import { Command } from "cmdk";
import { useMemo, useState, type ReactNode } from "react";
import { Kbd } from "./Kbd";
import { rankCommand } from "./paletteRank";

export interface PaletteItem { id: string; name: string; key: string; group: string; icon?: ReactNode; hint?: string; disabled?: boolean; run: () => unknown }

/** The items that match `search`, best first, kept in their groups (a group
 *  ranks by its best item): -> [[group, items]]. */
export function rankedGroups(items: PaletteItem[], search: string): [string, PaletteItem[]][] {
  const scored = items.map((i, k) => ({ i, k, s: rankCommand(i.name, search, [i.group, i.hint ?? ""]) }))
    .filter((x) => x.s > 0);
  const groups = new Map<string, { best: number; first: number; list: typeof scored }>();
  for (const x of scored) {
    const g = groups.get(x.i.group) ?? { best: 0, first: x.k, list: [] };
    g.best = Math.max(g.best, x.s);
    g.list.push(x);
    groups.set(x.i.group, g);
  }
  const order = [...groups.entries()].sort((a, b) => (b[1].best - a[1].best) || (a[1].first - b[1].first));
  return order.map(([name, g]) => [name, [...g.list].sort((a, b) => (b.s - a.s) || (a.k - b.k)).map((x) => x.i)]);
}

export function CommandPalette({ items, onClose, placeholder = "Type a command…" }: { items: PaletteItem[]; onClose: () => void; placeholder?: string }) {
  const [search, setSearch] = useState("");
  const groups = useMemo(() => rankedGroups(items, search), [items, search]);
  const firstId = groups.flatMap(([, list]) => list).find((i) => !i.disabled)?.id ?? "";
  const [picked, setPicked] = useState<{ search: string; id: string } | null>(null);
  // the arrows move the selection; a new search starts again at the first
  const value = picked && picked.search === search ? picked.id : firstId;
  return (
    <div className="kit-palette-back" onMouseDown={(e) => e.target === e.currentTarget && onClose()} data-testid="palette">
      <Command label="Commands" className="kit-palette" loop shouldFilter={false} value={value}
        onValueChange={(v) => setPicked({ search, id: v })}
        onKeyDown={(e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); onClose(); } }}>
        <Command.Input autoFocus placeholder={placeholder} data-testid="palette-input" value={search} onValueChange={setSearch} />
        <Command.List>
          <Command.Empty>No command by that name.</Command.Empty>
          {groups.map(([g, list]) => (
            <Command.Group key={g} heading={g}>
              {list.map((i) => (
                <Command.Item key={i.id} value={i.id} data-command={i.name} data-command-id={i.id}
                  disabled={i.disabled} onSelect={() => { onClose(); i.run(); }}>
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
