// Home ("Back to files", ./Home.tsx) is a view, not a route: an entry in the
// browser's history (history.state), so Back from the editor returns Home and
// Back from Home returns to the editor. Its own module, not the store's: the
// document and the editor stay as they are under it.
// WHY history.state, not a #hash: the hosted sign-in returns its token in the
// hash (hosted/core shf_token) and rewrites it.
import { useSyncExternalStore } from "react";
import { saveDocMarks } from "./thumbs";

const KEY = "arucoView";
const listeners = new Set<() => void>();
const read = (): boolean => typeof history !== "undefined" && (history.state as Record<string, unknown> | null)?.[KEY] === "home";
let home = read();

function set(on: boolean): void {
  if (on === home) return;
  home = on;
  for (const fn of listeners) fn();
}

if (typeof window !== "undefined") window.addEventListener("popstate", () => set(read()));

/** Back to files: Home, a new history entry. */
export function openHome(): void {
  if (home) return;
  // the editor's markers, for its card (a page opened straight on Home draws them before the core is up)
  saveDocMarks();
  history.pushState({ ...(history.state ?? {}), [KEY]: "home" }, "");
  set(true);
}

/** To the editor (a file, an example, New opened from Home): a new history
 *  entry, so Back returns Home. */
export function leaveHome(): void {
  if (!home) return;
  history.pushState({ ...(history.state ?? {}), [KEY]: "editor" }, "");
  set(false);
}

export const isHome = (): boolean => home;

export function useHome(): boolean {
  return useSyncExternalStore((fn) => { listeners.add(fn); return () => { listeners.delete(fn); }; }, () => home, () => false);
}
