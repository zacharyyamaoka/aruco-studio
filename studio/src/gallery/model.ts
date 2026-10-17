// The gallery's pure parts (no DOM, no store): where a fresh window lands,
// and how many error-level messages a planned scene carries. Tested by
// model.test.ts.
import type { SceneDoc } from "../api/types";

/** What the window shows: the gallery (the landing page) or the Studio. */
export type Page = "gallery" | "studio";

/** Where a fresh window starts: the hash, else the gallery (the landing
 *  page) unless the dev flag draws or a file was opened on purpose (the
 *  server's --open, or Open… before a reload). */
export function landing(hash: string, path: string | null, galleryDir: string | null, draw: boolean): { page: Page; example: string | null } {
  const ex = /^#example=(.+)$/.exec(hash);
  if (ex) return { page: "studio", example: decodeURIComponent(ex[1]) };
  if (hash === "#gallery") return { page: "gallery", example: null };
  if (hash === "#studio" || draw) return { page: "studio", example: null };
  const norm = (p: string) => p.replace(/\\/g, "/").toLowerCase();
  const inGallery = !!path && !!galleryDir && norm(path).startsWith(norm(galleryDir) + "/");
  return { page: path && !inGallery ? "studio" : "gallery", example: null };
}

/** The error-level messages of a planned scene: the compile's, each tag's
 *  plan errors and its error-level warnings, a tag that does not plan. */
export function errorCount(scene: SceneDoc | null, issues: { level?: string }[] = []): number {
  let n = issues.filter((i) => i.level === "error").length;
  for (const t of scene?.tags ?? []) {
    if (!t.plan) { n++; continue; }
    if (!t.plan.ok) n++;
    n += (t.plan.errors ?? []).length;
    n += (t.plan.warnings ?? []).filter((w) => w.level === "error").length;
  }
  return n;
}
