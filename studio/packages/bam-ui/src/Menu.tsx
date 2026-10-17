// A menu (base-ui Menu): a toolbar button that opens a list of commands.
import { Menu as M } from "@base-ui/react/menu";
import type { ReactNode } from "react";
import { cn } from "./cn";
import { Glyph } from "./Glyph";

export function Menu({ icon, label, children, testid, align = "start" }: { icon?: string; label: string; children: ReactNode; testid?: string; align?: "start" | "end" }) {
  return (
    <M.Root modal={false}>
      <M.Trigger className="kit-menu-trigger tb" data-testid={testid} title={label}>
        {icon && <Glyph name={icon} />}<span>{label}</span>
        <svg viewBox="0 0 16 16" width="10" height="10" aria-hidden="true" className="chev"><path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.6" /></svg>
      </M.Trigger>
      <M.Portal>
        <M.Positioner sideOffset={4} align={align} className="kit-menu-positioner">
          <M.Popup className="kit-menu-popup" data-kit-popup="menu">{children}</M.Popup>
        </M.Positioner>
      </M.Portal>
    </M.Root>
  );
}

export function MenuItem({ icon, label, hint, onClick, testid, disabled, title }: {
  icon?: string; label: ReactNode; hint?: string; onClick: () => void; testid?: string; disabled?: boolean; title?: string;
}) {
  return (
    <M.Item className={cn("kit-menu-item", disabled && "dis")} onClick={onClick} disabled={disabled} data-testid={testid} title={title}>
      {icon ? <Glyph name={icon} /> : <span className="ic" />}<span className="kit-menu-label">{label}</span>{hint && <span className="hint">{hint}</span>}
    </M.Item>
  );
}

export function MenuSeparator() {
  return <M.Separator className="kit-menu-sep" />;
}
