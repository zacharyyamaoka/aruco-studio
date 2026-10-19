// The online Studio's own 16 px glyphs, registered into the kit's Glyph
// registry once (lucide-react covers the general ones). Accent parts use
// var(--accent) so they follow the theme and a host's restyle.
import { registerGlyphs } from "@bam/ui";

const S = 'stroke="currentColor"';
const A = 'var(--accent)';

export const GLYPHS: Record<string, string> = {
  single: `<path fill-rule="evenodd" fill="currentColor" d="M2.5 2.5h11v11h-11zM5 5h2.5v2.5H5zM8.5 7.5H11V10H8.5zM5 9.5h2v1.5H5z"/>`,
  grid: `<path fill="currentColor" d="M1.5 1.5h5.5v5.5H1.5zM9 1.5h5.5v5.5H9zM1.5 9h5.5v5.5H1.5zM9 9h5.5v5.5H9z"/><path fill="var(--field)" d="M3.5 3.5h1.5v1.5H3.5zM11 4h1.5v1.5H11zM4 11h1.5v1.5H4zM11.5 11h1.5v1.5h-1.5z"/>`,
  charuco: `<path fill="none" ${S} d="M1.5 1.5h13v13h-13z"/><path fill="currentColor" d="M1.5 1.5h4.3v4.3H1.5zM10.2 1.5h4.3v4.3h-4.3zM5.8 5.8h4.4v4.4H5.8zM1.5 10.2h4.3v4.3H1.5zM10.2 10.2h4.3v4.3h-4.3z"/>`,
  // a sketch, the ArUco Extrude, the Joint Origin
  sketch: `<path d="M2.5 4.5h11v8h-11z" fill="none" stroke="${A}" stroke-width="1.2"/><path d="M5 2v2.5M11 2v2.5" ${S}/><circle cx="2.5" cy="12.5" r="1.2" fill="${A}"/>`,
  extrude: `<path d="M2 11.5l6 3 6-3-6-3z" fill="${A}" fill-opacity=".35" stroke="${A}"/><path d="M5 2.5h6v6H5z" fill="currentColor"/><path d="M6.5 4h1.5v1.5H6.5zM8.5 6h1v1h-1z" fill="var(--panel)"/><path d="M8 8.5v3" ${S}/>`,
  joint: `<circle cx="8" cy="8" r="5.5" fill="none" ${S}/><circle cx="8" cy="8" r="2" fill="${A}"/><path d="M8 2.5v3M8 10.5v3M2.5 8h3M10.5 8h3" ${S}/>`,
  inkjet: `<path d="M4.5 1.5h7v4h-7zM4.5 10h7v4.5h-7z" fill="none" ${S}/><path d="M4.5 12H2V5.5h12V12h-2.5" fill="none" ${S}/><circle cx="12" cy="7.5" r=".8" fill="${A}"/>`,
  print3d: `<path d="M4.5 1.5h7v4.5L9.4 9H6.6L4.5 6z" fill="currentColor"/><path d="M8 9v2.6" ${S} stroke-width="1.3"/><path d="M3 14h10" stroke="${A}" stroke-width="1.6"/>`,
  rect: `<path d="M2.5 3.5h11v9h-11z" fill="none" ${S} stroke-width="1.3"/><circle cx="2.5" cy="3.5" r="1.1" fill="${A}"/><circle cx="13.5" cy="12.5" r="1.1" fill="${A}"/>`,
  circle: `<circle cx="8" cy="8" r="5.5" fill="none" ${S} stroke-width="1.3"/><circle cx="8" cy="8" r="1" fill="${A}"/><path d="M8 8h5.5" stroke="${A}"/>`,
  pointer: `<path d="M3.5 2l9 5-4 1.2 2.6 4.3-1.6.9-2.6-4.3L4 11.8z" fill="currentColor"/>`,
  fit: `<path d="M1.5 5V1.5H5M11 1.5h3.5V5M14.5 11v3.5H11M5 14.5H1.5V11" fill="none" ${S} stroke-width="1.3"/><rect x="5" y="5" width="6" height="6" fill="currentColor" opacity=".6"/>`,
  verify: `<path d="M1.5 8s2.4-4.5 6.5-4.5S14.5 8 14.5 8 12.1 12.5 8 12.5 1.5 8 1.5 8z" fill="none" ${S} stroke-width="1.2"/><circle cx="8" cy="8" r="2.2" fill="${A}"/>`,
  print: `<path d="M4.5 1.5h7v4h-7zM4.5 10h7v4.5h-7z" fill="none" ${S}/><path d="M4.5 12H2V5.5h12V12h-2.5" fill="none" ${S}/>`,
  "cm-none": `<path d="M2.5 2.5h11v11h-11z" fill="none" ${S}/>`,
  "cm-tri": `<path d="M2.5 2.5h11v11h-11z" fill="none" ${S}/><path d="M3.5 3.5h4l-4 4z" fill="currentColor"/>`,
  profile: `<path d="M2 3h12v10H2z" fill="${A}" fill-opacity=".25" stroke="currentColor"/><circle cx="6" cy="8" r="2" fill="var(--panel)" ${S}/>`,
  dots: `<circle cx="3.5" cy="8" r="1.3" fill="currentColor"/><circle cx="8" cy="8" r="1.3" fill="currentColor"/><circle cx="12.5" cy="8" r="1.3" fill="currentColor"/>`,
  library: `<path d="M2 2.5h2.6v11H2zM5.5 2.5h2.6v11H5.5z" fill="currentColor"/><path d="M9.4 3.4l2.5-.7 2.6 10.2-2.5.7z" fill="${A}"/>`,
  clock: `<circle cx="8" cy="8" r="6" fill="none" ${S} stroke-width="1.3"/><path d="M8 4.5V8l2.5 1.5" fill="none" ${S} stroke-width="1.3"/>`,
  star: `<path d="M8 1.6l1.9 4 4.4.5-3.3 3 .9 4.3L8 11.2l-3.9 2.2.9-4.3-3.3-3 4.4-.5z" fill="${A}"/>`,
  cube: `<path d="M8 1.5l6 3v7l-6 3-6-3v-7zM2 4.5l6 3 6-3M8 7.5v7" fill="none" ${S}/>`,
  // a tray with a down arrow: "Download for CAD" (WHY not the cube: the brand mark is a cube now)
  download: `<path d="M8 2v8M4.5 6.5L8 10l3.5-3.5M2.5 11v2.5h11V11" fill="none" ${S}/>`,
  label: `<path d="M1.5 4.5h9l4 3.5-4 3.5h-9z" fill="none" ${S}/><path d="M4 9.5 5.6 6h.8L8 9.5M4.5 8.5h3" fill="none" stroke="${A}" stroke-width="1.2"/>`,
  marker: `<path fill-rule="evenodd" fill="currentColor" d="M2 2h12v12H2zM4.5 4.5H7V7H4.5zM9 7h2.5v2.5H9zM4.5 9H7v2.5H4.5z"/>`,
};

let done = false;
export function registerWebGlyphs(): void {
  if (done) return;
  done = true;
  registerGlyphs(GLYPHS);
}
