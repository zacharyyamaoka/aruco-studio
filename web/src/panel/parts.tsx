// The ArUco Extrude panel's shared parts: the choices its rows offer, a
// group's title, the grey note under a row. One set for the panel on one
// feature (./ExtrudePanel.tsx) and on several (./BatchPanel.tsx), so both
// draw the same skeleton (docs/design/panel_skeleton.md).
import type { ReactNode } from "react";
import type { Issue as KitIssue, Opt } from "@bam/ui";
import type { Issue } from "../core/contract";

export const TYPES: Opt[] = [
  { value: "single", label: "Single", hint: "Single marker" },
  { value: "grid", label: "Grid", hint: "Grid of markers" },
  { value: "charuco", label: "ChArUco", hint: "ChArUco board" },
];
export const TURNS: Opt[] = [0, 90, 180, 270].map((t) => ({ value: t, label: `${t}°`, hint: `Turn ${t}°` }));
export const CORNERS: Opt[] = [
  { value: "none", label: "None", hint: "No corner mark" },
  { value: "triangle", label: "Triangle", hint: "A triangle in the quiet zone's top-left corner" },
];
export const ORIGINS: Opt[] = [
  { value: "corner", label: "Board corner", hint: "The Joint Origin at OpenCV's board corner" },
  { value: "square", label: "Square", hint: "The Joint Origin at the centre of one board square" },
];
// WHY no Rectangle (Zach, 2026-10-20 evening): "If you want trim to rectangle
// then just make your profile a rectangle and trim to profile!"
export const TRIM_OPTS: Opt[] = [
  { value: "profile", label: "Profile", hint: "The sticker is the whole profile, its holes cut out" },
  { value: "marker", label: "Marker", hint: "The sticker is the marker and its quiet zone" },
];
// WHY Black | White | Both with Auto as the driven value (contract barrier 10):
// Auto is black only on a reference face (the body is the white), both in open space
export const MODES: Opt[] = [
  { value: "black", label: "Black", hint: "Only the black is made: into the body under it" },
  { value: "white", label: "White", hint: "Only the white is made: the pattern into a dark body" },
  { value: "both", label: "Both", hint: "A white tile with the black inlaid" },
];
/** A segmented row's choices as icons: the Fusion skin draws Type, Trim and
 *  Extrude as icon buttons, as Fusion's own dialog does (the hint is the
 *  tooltip); the other skins keep the words. */
export const asIcons = (opts: Opt[], prefix = "") => opts.map((o) => ({ ...o, icon: `${prefix}${o.value}` }));
export const TYPE_ICONS = asIcons(TYPES), TRIM_ICONS = asIcons(TRIM_OPTS, "trim-"), MODE_ICONS = asIcons(MODES, "mode-");
export const PLACES: Opt[] = [
  { value: "on_marker", label: "On marker", hint: "In the marker's border: the black row or the white quiet zone" },
  { value: "outside", label: "Outside", hint: "In a band beside the marker" },
];
export const SURFACES: Opt[] = [
  { value: "black", label: "Black", hint: "Knocked out of the black border row" },
  { value: "white", label: "White", hint: "Black text in the white quiet zone" },
];
export const PLACEHOLDERS = "{id} {first} {last} {ids} {dict} {type}";
export const SIDES: Opt[] = ["below", "above", "left", "right"].map((s) => ({ value: s, label: s[0].toUpperCase() + s.slice(1) }));
/** The core's issues in the kit's shape (an object literal per issue). */
export const kit = (xs: Issue[] | undefined): KitIssue[] => (xs ?? []).map((i) => ({ field: i.field, level: i.level, text: i.text }));

export const FALLBACK_DICTS = ["DICT_4X4_50", "DICT_4X4_100", "DICT_4X4_250", "DICT_5X5_50", "DICT_5X5_100", "DICT_6X6_50", "DICT_6X6_250"];

/** A group's small title and thin rule, over its rows (Fusion's command dialog). */
export const Group = ({ title }: { title: string }) => (
  <div className="xp-group" data-group-title={title} role="presentation"><span className="xp-group-title">{title}</span></div>
);

/** An angle into [0, 360). */
export const deg360 = (a: number) => +((((a % 360) + 360) % 360).toFixed(6));

/** A grey line under a row: what the value means (no issue, never red). */
export const Note = ({ children, testid }: { children: ReactNode; testid?: string }) => <div className="hint-line" data-testid={testid}>{children}</div>;
