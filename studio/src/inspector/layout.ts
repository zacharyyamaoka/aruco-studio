// Where each /api/form field sits in the inspector (REF aruco_extrude_ui's
// TABS / ROUTE: Marker · Heights · Print · Label · Advanced), the icons of
// its choices (REF's LAYOUT_ICONS, MODE_ICONS, OP_ICONS, MARK_ICONS,
// UP_ICONS, CORNER_ICONS) and when a field is shown. The fields themselves
// (paths, types, defaults, limits, choices, words) come from /api/form.
import type { FormField } from "../api/types";

export type Tab = "marker" | "heights" | "print" | "label" | "advanced";

export const TABS: { id: Tab; name: string; icon: string }[] = [
  { id: "marker", name: "Marker", icon: "t-marker" },
  { id: "heights", name: "Heights", icon: "t-heights" },
  { id: "print", name: "Print", icon: "t-print" },
  { id: "label", name: "Label", icon: "t-label" },
  { id: "advanced", name: "Advanced", icon: "gear" },
];

const BY_GROUP: Record<string, Tab | "root"> = {
  Target: "root", Marker: "marker", Size: "marker", Origin: "marker", "Corner mark": "marker",
  Layers: "heights", Pins: "heights", Label: "label", Trim: "advanced", Tag: "advanced",
};

const BY_PATH: Record<string, Tab | "root"> = {
  "settings.quiet_modules": "print", "settings.grow": "print", "settings.cells": "print",
  "settings.origin_v": "advanced", "target.kind": "advanced", "target.z_sign": "advanced",
  "settings.label.rule": "advanced",
};

export function tabOf(f: FormField): Tab | "root" {
  return BY_PATH[f.path] ?? BY_GROUP[f.group] ?? "advanced";
}

/** The fields the target editor draws itself (its own block above the tabs). */
export const TARGET_EDITOR = new Set(["target.w_mm", "target.h_mm", "target.loops_mm", "target.body_mm"]);

export const ICONS_OF: Record<string, Record<string, string>> = {
  "settings.layout": { single: "single", grid: "grid", charuco: "charuco" },
  "settings.mode": { auto: "m-auto", both: "m-wb", black: "m-black", white: "m-white" },
  "settings.op": { join: "join", new: "newbody" },
  "settings.corner_mark": { none: "cm-none", cut: "cm-cut", triangle: "cm-tri" },
  "settings.pin": { none: "blank", triangle: "pin", round: "pin" },
};

/** The Origin row's icons (REF UP_ICONS / CORNER_ICONS, TURNS_CW order 0, 270, 180, 90). */
export function turnIcons(layout: string): Record<string, string> {
  return layout === "single"
    ? { "0": "up-t", "270": "up-r", "180": "up-b", "90": "up-l" }
    : { "0": "o-tl", "270": "o-tr", "180": "o-br", "90": "o-bl" };
}

/** Is a field shown for this tag (its layout, its mode, the label on, ...)? */
export function shown(f: FormField, s: Record<string, any>, n: Record<string, any>): boolean {
  const layout = s.layout ?? "single";
  if (f.layouts && !f.layouts.includes(layout)) return false;
  const p = f.path;
  const mode = s.mode ?? "black";
  if (p === "numbers.white_offset" || p === "numbers.white_height") return mode === "both" || mode === "white" || mode === "auto";
  if (p === "numbers.black_offset" || p === "numbers.black_height") return mode === "both" || mode === "black" || mode === "auto";
  if (p === "settings.op") return mode === "both";
  if (p.startsWith("numbers.pin_")) return (s.pin ?? "none") !== "none";
  if (p === "settings.force") return Number(n.size || 0) > 0;
  const lab = s.label ?? {};
  if (p.startsWith("settings.label.") && p !== "settings.label.on" && p !== "settings.label.rule") {
    if (!lab.on) return false;
    if (p === "settings.label.text") return lab.content === "custom";
    if (p === "settings.label.x_mm" || p === "settings.label.y_mm") return lab.position === "manual";
    // the legacy nudge (before 2026-10-13): shown only on a tag that has one
    if (p === "settings.label.offset_x_mm" || p === "settings.label.offset_y_mm") return Boolean(lab.offset_x_mm || lab.offset_y_mm);
  }
  if (p === "settings.trim.margin_mm") return Boolean(s.trim && s.trim.rule === 1);
  if (p === "name") return false;                     // the header holds the name
  return true;
}
