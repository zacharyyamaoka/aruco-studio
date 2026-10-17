// A modal dialog (base-ui Dialog): a title bar with an icon, the body, a
// footer with the buttons. Esc and a click outside close it.
import { Dialog as D } from "@base-ui/react/dialog";
import type { ReactNode } from "react";
import { cn } from "./cn";
import { Glyph } from "./Glyph";

export function Dialog({ open, onClose, title, icon, children, footer, testid, width, className }: {
  open: boolean; onClose: () => void; title: ReactNode; icon?: string; children: ReactNode; footer?: ReactNode;
  testid?: string; width?: number | string; className?: string;
}) {
  return (
    <D.Root open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <D.Portal>
        <D.Backdrop className="kit-backdrop" />
        <D.Popup className={cn("kit-dialog", className)} data-testid={testid} data-kit-popup="dialog" style={width ? { width } : undefined}>
          <D.Title className="kit-dialog-title">
            {icon && <Glyph name={icon} />}<span className="grow">{title}</span>
            <D.Close className="kit-ib kit-dialog-x" aria-label="Close">
              <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M3.5 3.5l9 9M12.5 3.5l-9 9" stroke="currentColor" strokeWidth="1.5" /></svg>
            </D.Close>
          </D.Title>
          <div className="kit-dialog-body">{children}</div>
          {footer && <div className="kit-dialog-foot">{footer}</div>}
        </D.Popup>
      </D.Portal>
    </D.Root>
  );
}
