// A tooltip (base-ui Tooltip) for an icon-only control: its words after a
// short hover. The control keeps its own aria-label and title.
import { Tooltip as T } from "@base-ui/react/tooltip";
import type { ReactElement, ReactNode } from "react";

export function TooltipProvider({ children }: { children: ReactNode }) {
  return <T.Provider delay={450}>{children}</T.Provider>;
}

export function Tooltip({ text, children }: { text: string; children: ReactElement }) {
  return (
    <T.Root>
      <T.Trigger render={children} />
      <T.Portal>
        <T.Positioner sideOffset={6}>
          <T.Popup className="kit-tooltip">{text}</T.Popup>
        </T.Positioner>
      </T.Portal>
    </T.Root>
  );
}
