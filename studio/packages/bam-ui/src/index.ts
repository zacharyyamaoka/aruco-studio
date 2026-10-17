// @bam/ui: BAM's compact UI kit (ArUco Studio M8b2; docs/KIT.md). Born as
// studio/src/kit/ in M8b1, extracted here; cad-exporter's app/ gets a copy
// in M8d. Import "@bam/ui/tokens.css" once (the tokens, light and dark, and
// every kit-* class).
export { cn } from "./cn";
export { getTheme, initTheme, setTheme, token, useTheme, type Theme } from "./theme";
export { Glyph, hasGlyph, registerGlyphs, themed } from "./Glyph";
export { Kbd } from "./Kbd";
export { ToolButton } from "./ToolButton";
export { Button, IconButton } from "./Button";
export { Badge } from "./Badge";
export { NumberField, fmtNumber } from "./NumberField";
export { TextField } from "./TextField";
export { Switch } from "./Switch";
export { Select, type Opt } from "./Select";
export { SegmentedRow } from "./SegmentedRow";
export { Tabs, type TabDef } from "./Tabs";
export { Tooltip, TooltipProvider } from "./Tooltip";
export { Dialog } from "./Dialog";
export { Menu, MenuItem, MenuSeparator } from "./Menu";
export { Field, FieldRow, Messages, Section } from "./Field";
export { CommandPalette, type PaletteItem } from "./CommandPalette";
export { LibraryShell, type LibCard, type LibCollection } from "./Library";
export { Form, typeControl, type Cell, type ControlArgs, type FormProps } from "./Form";
export {
  common, getPath, routeIssues, shortText, shows, summaryLine, visibleRows, worst,
  type Choice, type FormCtx, type FormDoc, type FormRow, type FormTab, type Issue, type ShowWhen,
} from "./formModel";
