// The kit's glyphs: 16 px line icons by name. lucide-react gives the
// general ones; a tool registers its own CAD glyphs (marker, grid, ChArUco,
// extrude, ArUco Extrude, hole, slot, ...) as SVG inner markup once.
import { cn } from "./cn";

// a few every tool needs; a tool's own set may replace them
const S = 'stroke="currentColor"';
const GLYPHS: Record<string, string> = {
  close: `<path d="M3.5 3.5l9 9M12.5 3.5l-9 9" ${S} stroke-width="1.5"/>`,
  search: `<circle cx="6.8" cy="6.8" r="4.3" fill="none" ${S} stroke-width="1.4"/><path d="M10 10l4 4" ${S} stroke-width="1.6"/>`,
  check: `<path d="M2.5 8.5 6 12l7.5-8" fill="none" ${S} stroke-width="1.8"/>`,
  chevron: `<path d="M4 6l4 4 4-4" fill="none" ${S} stroke-width="1.5"/>`,
  sun: `<circle cx="8" cy="8" r="3" fill="none" ${S} stroke-width="1.3"/><path d="M8 1v2M8 13v2M1 8h2M13 8h2M3 3l1.4 1.4M11.6 11.6 13 13M3 13l1.4-1.4M11.6 4.4 13 3" ${S} stroke-width="1.3"/>`,
  moon: `<path d="M13 9.5A5.5 5.5 0 0 1 6.5 3a5.5 5.5 0 1 0 6.5 6.5z" fill="none" ${S} stroke-width="1.3"/>`,
};

/** Old icon sets with fixed colours: those named in `map` become tokens, so
 *  a glyph follows the theme (one style attribute per element). */
export function themed(svg: string, map: Record<string, string>): string {
  return svg.replace(/<([a-zA-Z]+)([^<>]*?)(\/?)>/g, (_m, tag: string, attrs: string, close: string) => {
    const style: string[] = [];
    const rest = attrs.replace(/\s(fill|stroke)="(#[0-9a-fA-F]{6})"/g, (m: string, k: string, c: string) => {
      const v = map[c.toLowerCase()];
      if (!v) return m;
      style.push(`${k}:${v}`);
      return "";
    });
    return `<${tag}${rest}${style.length ? ` style="${style.join(";")}"` : ""}${close}>`;
  });
}

export function registerGlyphs(map: Record<string, string>): void {
  Object.assign(GLYPHS, map);
}

export function hasGlyph(name: string): boolean {
  return name in GLYPHS;
}

export function Glyph({ name, className, size = 16 }: { name: string; className?: string; size?: number }) {
  return (
    <svg viewBox="0 0 16 16" width={size} height={size} className={cn("ic kit-glyph", className)} aria-hidden="true" data-icon={name}
      dangerouslySetInnerHTML={{ __html: GLYPHS[name] ?? "" }} />
  );
}
