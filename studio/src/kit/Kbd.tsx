// A key badge: "Ctrl+D" drawn as two caps.
import { cn } from "./cn";

export function Kbd({ keys, className }: { keys: string; className?: string }) {
  if (!keys) return null;
  return (
    <span className={cn("kit-kbd inline-flex items-center gap-0.5", className)} data-key={keys}>
      {keys.split("+").map((k, i) => <kbd key={i}>{k}</kbd>)}
    </span>
  );
}
