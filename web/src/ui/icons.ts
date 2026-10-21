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

// The ArUco Extrude panel's row icons (Fusion's dialogs put a small icon
// before a row's name): lucide's line icons (ISC, lucide.dev), their 24 px
// markup scaled into the kit's 16 px glyph box, named "row-<lucide name>".
// WHY (Zach, 2026-10-20 night): "to give the more Fusion feel we should have
// icons next to the words in the fields where appropriate".
const LUCIDE: Record<string, string> = {
  "square-dashed-mouse-pointer": `<path d="M12.034 12.681a.498.498 0 0 1 .647-.647l9 3.5a.5.5 0 0 1-.033.943l-3.444 1.068a1 1 0 0 0-.66.66l-1.067 3.443a.5.5 0 0 1-.943.033z"/><path d="M5 3a2 2 0 0 0-2 2"/><path d="M19 3a2 2 0 0 1 2 2"/><path d="M5 21a2 2 0 0 1-2-2"/><path d="M9 3h1"/><path d="M9 21h2"/><path d="M14 3h1"/><path d="M3 9v1"/><path d="M21 9v2"/><path d="M3 14v1"/>`,
  scissors: `<circle cx="6" cy="6" r="3"/><path d="M8.12 8.12 12 12"/><path d="M20 4 8.12 15.88"/><circle cx="6" cy="18" r="3"/><path d="M14.8 14.8 20 20"/>`,
  "arrow-up-from-line": `<path d="m18 9-6-6-6 6"/><path d="M12 3v14"/><path d="M5 21h14"/>`,
  "flip-vertical": `<path d="M21 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v3"/><path d="M21 16v3a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-3"/><path d="M4 12H2"/><path d="M10 12H8"/><path d="M16 12h-2"/><path d="M22 12h-2"/>`,
  "grid-2x2": `<path d="M12 3v18"/><path d="M3 12h18"/><rect x="3" y="3" width="18" height="18" rx="2"/>`,
  "book-open": `<path d="M12 5v16"/><path d="M20.001 19A2 2 0 0022 17V5a2 2 0 00-1.999-2L16 3.002A5 5 0 0012 5a5 5 0 00-4-2H4a2 2 0 00-2 2v12a2 2 0 001.999 2H8a5 5 0 014 2 5 5 0 014-2z"/>`,
  hash: `<line x1="4" x2="20" y1="9" y2="9"/><line x1="4" x2="20" y1="15" y2="15"/><line x1="10" x2="8" y1="3" y2="21"/><line x1="16" x2="14" y1="3" y2="21"/>`,
  ruler: `<path d="M21.3 15.3a2.4 2.4 0 0 1 0 3.4l-2.6 2.6a2.4 2.4 0 0 1-3.4 0L2.7 8.7a2.41 2.41 0 0 1 0-3.4l2.6-2.6a2.41 2.41 0 0 1 3.4 0Z"/><path d="m14.5 12.5 2-2"/><path d="m11.5 9.5 2-2"/><path d="m8.5 6.5 2-2"/><path d="m17.5 15.5 2-2"/>`,
  "rotate-cw": `<path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/>`,
  "rotate-ccw": `<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>`,
  "square-square": `<rect x="3" y="3" width="18" height="18" rx="2"/><rect x="8" y="8" width="8" height="8" rx="1"/>`,
  type: `<path d="M12 4v16"/><path d="M4 7V5a1 1 0 0 1 1-1h14a1 1 0 0 1 1 1v2"/><path d="M9 20h6"/>`,
  "triangle-right": `<path d="M22 18a2 2 0 0 1-2 2H3c-1.1 0-1.3-.6-.4-1.3L20.4 4.3c.9-.7 1.6-.4 1.6.7Z"/>`,
  "key-round": `<path d="M2.586 17.414A2 2 0 0 0 2 18.828V21a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h.172a2 2 0 0 0 1.414-.586l.814-.814a6.5 6.5 0 1 0-4-4z"/><circle cx="16.5" cy="7.5" r=".5" fill="currentColor"/>`,
  "layers-2": `<path d="M13 13.74a2 2 0 0 1-2 0L2.5 8.87a1 1 0 0 1 0-1.74L11 2.26a2 2 0 0 1 2 0l8.5 4.87a1 1 0 0 1 0 1.74z"/><path d="m20 14.285 1.5.845a1 1 0 0 1 0 1.74L13 21.74a2 2 0 0 1-2 0l-8.5-4.87a1 1 0 0 1 0-1.74l1.5-.845"/>`,
  "wand-sparkles": `<path d="m21.64 3.64-1.28-1.28a1.21 1.21 0 0 0-1.72 0L2.36 18.64a1.21 1.21 0 0 0 0 1.72l1.28 1.28a1.2 1.2 0 0 0 1.72 0L21.64 5.36a1.2 1.2 0 0 0 0-1.72"/><path d="m14 7 3 3"/><path d="M5 6v4"/><path d="M19 14v4"/><path d="M10 2v2"/><path d="M7 8H3"/><path d="M21 16h-4"/><path d="M11 3H9"/>`,
  "move-horizontal": `<path d="m18 8 4 4-4 4"/><path d="M2 12h20"/><path d="m6 8-4 4 4 4"/>`,
  "move-vertical": `<path d="M12 2v20"/><path d="m8 18 4 4 4-4"/><path d="m8 6 4-4 4 4"/>`,
  "grid-3x3": `<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18"/><path d="M3 15h18"/><path d="M9 3v18"/><path d="M15 3v18"/>`,
  "map-pin": `<path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0"/><circle cx="12" cy="10" r="3"/>`,
  grip: `<circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/><circle cx="12" cy="5" r="1"/><circle cx="19" cy="5" r="1"/><circle cx="5" cy="5" r="1"/><circle cx="12" cy="19" r="1"/><circle cx="19" cy="19" r="1"/><circle cx="5" cy="19" r="1"/>`,
  "a-large-small": `<path d="m15 16 2.536-7.328a1.02 1.02 1 0 1 1.928 0L22 16"/><path d="M15.697 14h5.606"/><path d="m2 16 4.039-9.69a.5.5 0 0 1 .923 0L11 16"/><path d="M3.304 13h6.392"/>`,
};
for (const [name, svg] of Object.entries(LUCIDE)) {
  GLYPHS[`row-${name}`] = `<g transform="scale(${16 / 24})" fill="none" ${S} stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${svg}</g>`;
}

let done = false;
export function registerWebGlyphs(): void {
  if (done) return;
  done = true;
  registerGlyphs(GLYPHS);
}
