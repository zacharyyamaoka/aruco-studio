// The canvas's right-click menu, Figma's (Zach, 2026-10-21: "Please add a
// right click menu ... I want the option to scale to actual size, vs fit").
// It opens where a right-click that did not move was released (a right-drag
// is the selection box: Viewport.tsx, ./click.ts) and holds what applies to
// what was under the pointer, every row an existing command with its key:
// - a marker: Edit ArUco Extrude (A), Copy, Paste here, Duplicate, Delete,
//   Turn 90°, Export SVG;
// - a shape, several, a profile: ArUco Extrude (A), Copy, Paste here,
//   Duplicate, Delete;
// - empty canvas: Paste here;
// - always: the zoom group (../zoom/ZoomItems.tsx), about the click's point.
// The kit's menu rows and popup (the logo's menu's look), on a point anchor.
import { useMemo } from "react";
import { Menu as M } from "@base-ui/react/menu";
import { MenuItem, MenuSeparator } from "@bam/ui";
import type { Vec2 } from "../core/contract";
import { exportSvg } from "../app/commands";
import { useStudio } from "../store";
import { ZoomItems } from "../zoom/ZoomItems";

/** What the right-click was on (already selected as a left-click would select it). */
export type MenuTarget = { kind: "canvas" } | { kind: "marker"; fid: string } | { kind: "shapes" };

export interface MenuAt {
  /** client px: where the menu hangs */
  client: Vec2;
  /** view px: where a zoom from it is about */
  local: Vec2;
  /** mm: where Paste here puts the copy */
  world: Vec2;
  target: MenuTarget;
}

export function CanvasMenu({ at, onClose }: { at: MenuAt | null; onClose: () => void }) {
  // a point: the menu's corner just off it, as a system menu opens
  const anchor = useMemo(() => {
    if (!at) return null;
    const [x, y] = at.client;
    return { getBoundingClientRect: () => DOMRect.fromRect({ x, y, width: 0, height: 0 }) };
  }, [at]);
  return (
    <M.Root open={!!at} onOpenChange={(o) => { if (!o) onClose(); }} modal={false}>
      <M.Portal>
        <M.Positioner anchor={anchor} side="bottom" align="start" sideOffset={2} alignOffset={2} collisionPadding={8} className="kit-menu-positioner">
          <M.Popup className="kit-menu-popup mm-popup" data-kit-popup="menu" data-testid="canvas-menu" data-target={at?.target.kind}>
            {at && <Items at={at} />}
          </M.Popup>
        </M.Positioner>
      </M.Portal>
    </M.Root>
  );
}

function Items({ at }: { at: MenuAt }) {
  const st = useStudio.getState;
  const s = st();
  const t = at.target;
  const ids = s.selectedShapeIds();
  // what Del would delete: a sketch dim, shapes, a marker (a profile alone is not deleted)
  const deletes = !!s.dimSel || s.multi.length > 1 || s.sel?.kind === "shape" || s.sel?.kind === "feature" || s.sel?.kind === "origin";
  const editing = t.kind === "marker" && s.panel.open && s.panel.featureId === t.fid && !s.panel.featureIds.length;
  return (
    <>
      {t.kind === "marker" && (
        <MenuItem icon="extrude" label="Edit ArUco Extrude" hint="A" testid="cm-edit" disabled={editing}
          title={editing ? "Its panel is open" : undefined} onClick={() => void st().extrude()} />
      )}
      {t.kind === "shapes" && <MenuItem icon="extrude" label="ArUco Extrude" hint="A" testid="cm-extrude" onClick={() => void st().extrude()} />}
      {t.kind !== "canvas" && (
        <>
          <MenuSeparator />
          <MenuItem label="Copy" hint="Ctrl+C" testid="cm-copy" disabled={!ids.length} onClick={() => st().copy()} />
        </>
      )}
      <MenuItem label="Paste here" hint="Ctrl+V" testid="cm-paste" disabled={!s.canPaste()} title={s.canPaste() ? undefined : "Nothing copied yet"}
        onClick={() => st().paste(at.world)} />
      {t.kind !== "canvas" && (
        <>
          <MenuItem label="Duplicate" hint="Ctrl+D" testid="cm-duplicate" disabled={!ids.length} onClick={() => st().duplicate()} />
          <MenuItem label="Delete" hint="Del" testid="cm-delete" disabled={!deletes} title={deletes ? undefined : "Select its shapes to delete them"}
            onClick={() => st().deleteSelection()} />
        </>
      )}
      {t.kind === "marker" && (
        <>
          <MenuSeparator />
          <MenuItem label="Turn 90°" testid="cm-turn" onClick={() => st().turn(t.fid)} />
          <MenuItem label="Export SVG" hint="the marker, true size" testid="cm-svg" onClick={() => void exportSvg()} />
        </>
      )}
      <MenuSeparator />
      <ZoomItems prefix="cm" at={at.local} />
    </>
  );
}
