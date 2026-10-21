// "sonner" for the copied React bindings (../react/provider.tsx calls toast()
// and toast.error()): the same calls, shown by the Studio's own toast
// (../ui/HostedToast.tsx). WHY not the package: the Studio's UI is its kit,
// and this is all the bindings use of it.
import { useSyncExternalStore } from "react";

export interface Toast {
  id: number;
  message: string;
  description?: string;
  action?: { label: string; onClick: () => void };
  error?: boolean;
}
type Options = { description?: string; action?: { label: string; onClick: () => void } };

let current: Toast | null = null;
let seq = 0;
const listeners = new Set<() => void>();
function show(next: Toast | null): void {
  current = next;
  for (const fn of listeners) fn();
}

export const toast = Object.assign(
  (message: string, opts: Options = {}) => show({ id: ++seq, message, ...opts }),
  { error: (message: string, opts: Options = {}) => show({ id: ++seq, message, ...opts, error: true }) },
);

export function dismissToast(id: number): void {
  if (current?.id === id) show(null);
}

export function useToast(): Toast | null {
  return useSyncExternalStore((fn) => { listeners.add(fn); return () => { listeners.delete(fn); }; }, () => current);
}
