// Light by default, dark as a toggle (M8 4.1). The theme is the
// `data-theme` attribute on <html>; every colour is a token of tokens.css.
// The choice is remembered per browser (a convenience: it never matters
// when the storage is blocked).
import { useSyncExternalStore } from "react";

export type Theme = "light" | "dark";
const KEY = "bam-ui.theme";
const subs = new Set<() => void>();

function stored(): Theme | null {
  try {
    const v = window.localStorage.getItem(KEY);
    return v === "dark" || v === "light" ? v : null;
  } catch {
    return null;
  }
}

export function getTheme(): Theme {
  if (typeof document === "undefined") return "light";
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

export function setTheme(t: Theme, remember = true): void {
  if (typeof document === "undefined") return;
  document.documentElement.dataset.theme = t;
  document.documentElement.style.colorScheme = t;
  if (remember) {
    try { window.localStorage.setItem(KEY, t); } catch { /* storage blocked: the page still works */ }
  }
  for (const f of subs) f();
}

/** At start: the remembered theme, else light. */
export function initTheme(): Theme {
  const t = stored() ?? "light";
  setTheme(t, false);
  return t;
}

export function useTheme(): [Theme, (t: Theme) => void] {
  const t = useSyncExternalStore((f) => { subs.add(f); return () => { subs.delete(f); }; }, getTheme, () => "light" as Theme);
  return [t, setTheme];
}

/** A token's value now ("--canvas" -> "#eceff3"), for canvases that cannot use CSS (three.js). */
export function token(name: string, fallback = "#000000"): string {
  if (typeof document === "undefined") return fallback;
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}
