// Skins (Zach, 2026-10-20: "quickly select between different skins for aruco
// studio, like fusion360, onshape, etc., and then it will make it feel like
// you are kind of in that CAD program"). A skin is only a set of the kit's
// tokens and this app's (styles.css), switched by `data-skin` on <html>:
// it never changes layout or behaviour, so it carries over to any panel.
// Unstyled is the base the CAD skins extend; Studio is the current look and
// the default. Some CAD programs have one theme only: their skin pins
// `data-theme` while it is on, without forgetting the viewer's own choice.
// The choice is remembered per browser (a convenience: it never matters
// when the storage is blocked).
import { useSyncExternalStore } from "react";
import { initTheme, registerGlyphs, setTheme, type Theme } from "@bam/ui";
import "./unstyled.css";
import "./fusion.css";
import "./onshape.css";

export type SkinId = "studio" | "unstyled" | "fusion" | "onshape";
export interface Skin { id: SkinId; name: string; theme?: Theme }

export const SKINS: Skin[] = [
  { id: "studio", name: "Studio" },
  { id: "unstyled", name: "Unstyled" },
  { id: "fusion", name: "Fusion 360", theme: "dark" },
  { id: "onshape", name: "Onshape", theme: "light" },
];

const KEY = "aruco-studio.skin";
const subs = new Set<() => void>();

function find(id: string | null | undefined): Skin | undefined {
  return SKINS.find((s) => s.id === id);
}

function stored(): SkinId | null {
  try {
    return find(window.localStorage.getItem(KEY))?.id ?? null;
  } catch {
    return null;
  }
}

export function getSkin(): Skin {
  if (typeof document === "undefined") return SKINS[0];
  return find(document.documentElement.dataset.skin) ?? SKINS[0];
}

export function setSkin(id: SkinId, remember = true): void {
  if (typeof document === "undefined") return;
  const skin = find(id) ?? SKINS[0];
  const was = getSkin();
  document.documentElement.dataset.skin = skin.id;
  // a one-theme skin pins it (not remembered); leaving one restores the viewer's theme
  if (skin.theme) setTheme(skin.theme, false);
  else if (was.theme || remember === false) initTheme();
  if (remember) {
    try { window.localStorage.setItem(KEY, skin.id); } catch { /* storage blocked: the page still works */ }
  }
  for (const f of subs) f();
}

/** At start, after initTheme(): the remembered skin, else Studio. */
export function initSkin(): Skin {
  registerGlyphs({
    skin: `<path d="M8 1.8a6.2 6.2 0 1 0 0 12.4c1 0 1.5-.6 1.5-1.3 0-.8-.6-1-.6-1.7 0-.7.5-1.2 1.3-1.2h1.5a2.6 2.6 0 0 0 2.6-2.6C14.3 4.3 11.5 1.8 8 1.8z" fill="none" stroke="currentColor" stroke-width="1.2"/><circle cx="4.8" cy="7.4" r="1" fill="var(--accent)"/><circle cx="7" cy="4.6" r="1" fill="currentColor"/><circle cx="10.4" cy="5" r="1" fill="var(--accent)"/>`,
  });
  setSkin(stored() ?? "studio", false);
  return getSkin();
}

export function useSkin(): [Skin, (id: SkinId) => void] {
  const s = useSyncExternalStore((f) => { subs.add(f); return () => { subs.delete(f); }; }, getSkin, () => SKINS[0]);
  return [s, setSkin];
}
