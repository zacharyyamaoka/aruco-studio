// The ArUco Extrude panel (Fusion's feature dialog) for the feature it
// edits. It opens beside the clicked marker (V1 "Click-to-inspect",
// 2026-10-18) and follows it; on a phone it docks to the bottom. Three tabs
// and nothing above them but the title bar, in the skeleton's order
// (docs/design/panel_skeleton.md, one order for this panel and the Fusion
// add-in): Marker (Where: Profile, Holes; How: the Preset with what it makes as a
// grey line; Marker; Size, then Suggest; Orientation; Details: Quiet zone,
// Key), Label (Label, Corner mark), Make -- its icon the preset's method,
// an inkjet or a 3D printer (Size & cut: Size step, Trim; Heights; Outward
// side: Flip). A new feature opens on Marker. Every row of a tab is in view, each
// group under a small title and a thin rule; the footer is the summary line,
// then OK / Cancel. Every row shows
// its own issues from plan().warnings -- and the id's from auto id -- under it.
// Every value is driven (grey: the core's, a rule's, the preset's, auto id's or
// the default) or set (typed: normal, with ↺ inside the field);
// ../ui/DrivenField.tsx. Manual values always go through; the plan flags what
// does not fit, it never refuses.
// WHY three flat tabs (Zach, 2026-10-20 night, panel proposal V1 "Command
// Dialog", reports/media/panel-proposals-2026-10-20.html): "I like separating
// the concerns" -- and no row above the tabs, no Advanced fold.
// WHY words, not icons, on the segmented choices (Zach, 2026-10-18: "I like
// the use of text instead of icons here"; the Fusion skin's Type is icons, as
// Fusion's own dialog draws it) -- and a small icon beside a row's
// name, the groups and Suggest first in Size (Zach, 2026-10-20 night: "add
// more visual grouping to help the eye"; "change the order of where you have
// the suggestion drop down so it's more natural"; "icons next to the words in
// the fields where appropriate").
import { useLayoutEffect, type ReactNode } from "react";
import { FieldRow, Glyph, Messages, NumberField, SegmentedRow, Select, Switch, Tabs, Button, type Issue as KitIssue, type Opt } from "@bam/ui";
import { X } from "lucide-react";
import type { ExtrudeParams, Issue, LabelParams, MarkerParams, Trim } from "../core/contract";
import { DEFAULT_MARKER, DEFAULT_TRIM, featureNumber, featurePreset, featureRect, getFeature, idRange, isSet, referenceFace, typeCounts } from "../model/doc";
import { boxOf, rectCorners, toScreen } from "../model/geom";
import { presetStep, stepKey, stepLabel, stepOf, stepOptions } from "../presets/fields";
import { presetNumbers, samePreset, myPresets } from "../presets/local";
import { profileLoops } from "../sketch/model";
import { useSkin } from "../skins/skins";
import { useStudio, type Tab } from "../store";
import type { Box } from "../ui/anchor";
import { DrivenChoice, DrivenField, DrivenText } from "../ui/DrivenField";
import { FloatingPanel } from "../ui/FloatingPanel";
import { TextArea } from "../ui/TextArea";
import { routeIssues, tabLevel, tabRows } from "./issues";
import { SuggestSelect } from "./SuggestSelect";
import { PlanLine, PresetWait } from "./Waiting";
import "./panel.css";

const TYPES: Opt[] = [
  { value: "single", label: "Single", hint: "Single marker" },
  { value: "grid", label: "Grid", hint: "Grid of markers" },
  { value: "charuco", label: "ChArUco", hint: "ChArUco board" },
];
const TURNS: Opt[] = [0, 90, 180, 270].map((t) => ({ value: t, label: `${t}°`, hint: `Turn ${t}°` }));
const CORNERS: Opt[] = [
  { value: "none", label: "None", hint: "No corner mark" },
  { value: "triangle", label: "Triangle", hint: "A triangle in the quiet zone's top-left corner" },
];
const ORIGINS: Opt[] = [
  { value: "corner", label: "Board corner", hint: "The Joint Origin at OpenCV's board corner" },
  { value: "square", label: "Square", hint: "The Joint Origin at the centre of one board square" },
];
// WHY no Rectangle (Zach, 2026-10-20 evening): "If you want trim to rectangle
// then just make your profile a rectangle and trim to profile!"
const TRIM_OPTS: Opt[] = [
  { value: "profile", label: "Profile", hint: "The sticker is the whole profile, its holes cut out" },
  { value: "marker", label: "Marker", hint: "The sticker is the marker and its quiet zone" },
];
// WHY Black | White | Both with Auto as the driven value (contract barrier 10):
// Auto is black only on a reference face (the body is the white), both in open space
const MODES: Opt[] = [
  { value: "black", label: "Black", hint: "Only the black is made: into the body under it" },
  { value: "white", label: "White", hint: "Only the white is made: the pattern into a dark body" },
  { value: "both", label: "Both", hint: "A white tile with the black inlaid" },
];
/** A segmented row's choices as icons: the Fusion skin draws Type, Trim and
 *  Extrude as icon buttons, as Fusion's own dialog does (the hint is the
 *  tooltip); the other skins keep the words. */
const asIcons = (opts: Opt[], prefix = "") => opts.map((o) => ({ ...o, icon: `${prefix}${o.value}` }));
const TYPE_ICONS = asIcons(TYPES), TRIM_ICONS = asIcons(TRIM_OPTS, "trim-"), MODE_ICONS = asIcons(MODES, "mode-");
const PLACES: Opt[] = [
  { value: "on_marker", label: "On marker", hint: "In the marker's border: the black row or the white quiet zone" },
  { value: "outside", label: "Outside", hint: "In a band beside the marker" },
];
const SURFACES: Opt[] = [
  { value: "black", label: "Black", hint: "Knocked out of the black border row" },
  { value: "white", label: "White", hint: "Black text in the white quiet zone" },
];
const PLACEHOLDERS = "{id} {first} {last} {ids} {dict} {type}";
const SIDES: Opt[] = ["below", "above", "left", "right"].map((s) => ({ value: s, label: s[0].toUpperCase() + s.slice(1) }));
/** The core's issues in the kit's shape (an object literal per issue). */
const kit = (xs: Issue[] | undefined): KitIssue[] => (xs ?? []).map((i) => ({ field: i.field, level: i.level, text: i.text }));

const FALLBACK_DICTS = ["DICT_4X4_50", "DICT_4X4_100", "DICT_4X4_250", "DICT_5X5_50", "DICT_5X5_100", "DICT_6X6_50", "DICT_6X6_250"];

function SelRow({ path, label, count, active, onActivate, onClear, issues, icon, rowIcon, testid, emptyText }: {
  path: string; label: string; count: number; active: boolean; onActivate: () => void; onClear: () => void;
  issues: KitIssue[]; icon: string; rowIcon?: string; testid: string; emptyText: string;
}) {
  return (
    <FieldRow path={path} label={label} icon={rowIcon} issues={issues}>
      <button type="button" className={`selrow${active ? " active" : ""}${count ? " filled" : ""}`} data-testid={testid}
        data-count={count} data-active={active ? "1" : "0"} onClick={onActivate}>
        <Glyph name={icon} />
        <span className="selrow-text">{count ? `${count} selected` : active ? "Select…" : emptyText}</span>
      </button>
      {count > 0 && (
        <button type="button" className="kit-ib" title={`Clear ${label}`} aria-label={`Clear ${label}`} data-testid={`${testid}-clear`} onClick={onClear}>
          <X size={13} />
        </button>
      )}
    </FieldRow>
  );
}

/** A group's small title and thin rule, over its rows (Fusion's command dialog). */
const Group = ({ title }: { title: string }) => (
  <div className="xp-group" data-group-title={title} role="presentation"><span className="xp-group-title">{title}</span></div>
);

/** An angle into [0, 360). */
const deg360 = (a: number) => +((((a % 360) + 360) % 360).toFixed(6));

/** A grey line under a row: what the value means (no issue, never red). */
const Note = ({ children, testid }: { children: ReactNode; testid?: string }) => <div className="hint-line" data-testid={testid}>{children}</div>;

/** What drives a field while it is driven (the tooltip). */
const DEFAULT = "default";

export function ExtrudePanel() {
  const st = useStudio();
  const { doc, plans, panel, suggestions, info, builtins } = st;
  const f = getFeature(doc, panel.featureId);
  const [skin] = useSkin();
  // a feature made by this opening (not in the document before it) starts on
  // Marker (the skeleton); a reopened one keeps the tab the panel last had
  const fresh = panel.open && !!f && !!panel.backup && !getFeature(panel.backup, f.id);
  useLayoutEffect(() => {
    if (fresh) useStudio.getState().setTab("marker");
  }, [panel.featureId, fresh]);
  if (!panel.open || !f) return null;
  const m = f.marker, l = f.label;
  const plan = plans[f.id] ?? null;
  const planError = st.planErrors[f.id] ?? null;
  const refFace = referenceFace(doc, f);
  // this marker's own preset (Zach, 2026-10-20 night: "applied on a per marker basis")
  const preset = featurePreset(doc, f);
  const method = preset?.method ?? "inkjet";
  // the Make tab's icon, the Preset row and the presets dialog name and draw the method alike
  const methodName = method === "print3d" ? "3D print" : "Inkjet";
  const methodIcon = method === "print3d" ? "print3d" : "inkjet";
  const fusion = skin.id === "fusion";
  const rows = tabRows(m, l, method);
  const issues: Issue[] = plan && f.profile ? [...plan.warnings] : [];
  // auto id's issues for this feature (Issue.key): a collision, a full dictionary
  for (const i of st.idIssues) if (i.key === f.key) issues.push({ ...i, field: "marker.first_id" });
  const routed = routeIssues(issues, [...rows.make, ...rows.marker, ...rows.label]);
  const iss = (p: string) => kit(routed[p]);
  const bad = (p: string) => !!routed[p]?.some((i) => i.level === "error");
  const library = [...builtins, ...myPresets()].find((p) => p.id === preset?.id);
  const modified = !!preset && !!library && !samePreset(library, preset);
  const dicts: Opt[] = (info?.dictionaries.map((d) => ({ value: d.name, label: d.name.replace("DICT_", ""), hint: `${d.capacity} ids` }))
    ?? FALLBACK_DICTS.map((d) => ({ value: d, label: d.replace("DICT_", "") })));
  const showPlan = plan && f.profile ? plan : null;
  const profileHasHoles = !!f.profile?.holes.length;
  /** The props every driven field shares: its state, set and reset. */
  const drv = (path: string) => ({ path, driven: !isSet(f, path), onSet: (v: unknown) => st.setField(path, v), onReset: () => st.resetField(path) });
  const fills = "fills the profile";
  const [dc, dr] = typeCounts(m.type);
  const counts = `default for ${m.type === "grid" ? "a grid" : "a ChArUco board"} (${dc} × ${dr})`;
  const square = m.origin_square ?? null;
  const offsetDriver = "the preset spot (Side); drag the text on the sketch to move it";
  // the heights as planned (barrier 10): the core's MarkerPlan.extrude, driven or set
  const ex = showPlan?.extrude ?? null;
  const height = (k: keyof ExtrudeParams & `${string}_mm`, fallback: number | null = null): number | null =>
    isSet(f, `extrude.${k}`) ? (f.extrude[k] as number) : ex ? ex[k] : fallback;
  const mode = isSet(f, "extrude.mode") && f.extrude.mode !== "auto" ? f.extrude.mode! : ex?.mode ?? (refFace ? "black" : "both");
  const layer = preset?.layer_mm || 0.1;
  // a rectangle profile (the custom placement) turns on the sketch; a face's box is the core's
  const rect = featureRect(doc, f);
  // barrier 11: the marker's size step, else its preset's (driven)
  const presetSize = preset ? presetStep(preset) : null;
  const sizeStep = m.size_step ?? presetSize;
  const outward = refFace ? (m.flip ? "into the face (flipped)" : "out of the face") : (m.flip ? "down (flipped)" : "up");

  // what the panel opens beside: the box the marker was placed in, the marker
  // and its label band, on screen (the profile until it plans); the other
  // markers' boxes it keeps clear where it can
  const screenBox = (id: string): Box | null => {
    const g = getFeature(doc, id), p = plans[id];
    const pr = g?.profile ? profileLoops(doc.shapes, g.profile) : null;
    if (!pr) return null;
    const pts = p ? [...(p.fit_rect ? rectCorners(p.fit_rect) : []), ...p.outer, ...(p.label?.box ?? [])] : pr.loops[0];
    return boxOf(pts.map((q) => toScreen(st.camera, st.view.w, st.view.h, q)));
  };
  const anchor = screenBox(f.id);
  const others = doc.features.filter((g) => g.id !== f.id).map((g) => screenBox(g.id)).filter((b): b is Box => !!b);

  // WHY Profile then Preset first, on Marker (docs/design/panel_skeleton.md; Zach,
  // 2026-10-21): "The first thing you do is select the profile then second in
  // your mind you need to decide how to manufacture it ... now I want to be
  // thinking about the marker."
  const markerTab = (
    <div data-tab-body="marker">
      <Group title="Where" />
      <SelRow path="profile" label="Profile" icon="profile" rowIcon="row-square-dashed-mouse-pointer" testid="sel-profile" count={f.profile ? 1 : 0} emptyText="Select…"
        active={panel.selector === "profile"} issues={iss("profile")}
        onActivate={() => st.setSelector(panel.selector === "profile" ? null : "profile")} onClear={st.clearProfile} />
      {profileHasHoles && (
        <FieldRow path="holes" label="Holes" title="Place the marker clear of the holes, or over them">
          <SegmentedRow path="holes" compact value={f.holes} options={[{ value: "avoid", label: "Avoid" }, { value: "ignore", label: "Ignore" }]}
            onChange={(v) => void st.setHoles(v as "avoid" | "ignore")} />
        </FieldRow>
      )}
      <Group title="How" />
      <FieldRow path="preset" label="Preset" issues={iss("preset")}>
        <button type="button" className="preset-pick" data-testid="panel-preset" data-method={method} onClick={() => st.openModal("presets")}
          title="How this marker is made: open the presets (the next new marker starts with it too)">
          <Glyph name={methodIcon} />
          <span className="preset-name">{preset ? preset.name : <PresetWait />}{modified && <i className="modified"> (modified)</i>}</span>
        </button>
        <button type="button" className="kit-ib" title="Presets…" aria-label="Presets" data-testid="panel-preset-more" onClick={() => st.openModal("presets")}>
          <Glyph name="dots" />
        </button>
      </FieldRow>
      {preset && <Note testid="preset-lines">{methodName} · {presetNumbers(preset)}</Note>}
      <Group title="Marker" />
      <FieldRow path="marker.type" label="Type" icon="row-grid-2x2" issues={iss("marker.type")}>
        <DrivenChoice {...drv("marker.type")} value={m.type} driver={`${DEFAULT} (single)`}>
          <SegmentedRow path="marker.type" value={m.type} options={fusion ? TYPE_ICONS : TYPES} onChange={(v) => st.setField("marker.type", v as MarkerParams["type"])} />
        </DrivenChoice>
      </FieldRow>
      <FieldRow path="marker.dictionary" label="Dictionary" icon="row-book-open" issues={iss("marker.dictionary")}>
        <DrivenChoice {...drv("marker.dictionary")} value={m.dictionary} driver={`${DEFAULT} (${DEFAULT_MARKER.dictionary.replace("DICT_", "")})`}>
          <Select path="marker.dictionary" value={m.dictionary} options={dicts} onChange={(v) => st.setField("marker.dictionary", String(v))} />
        </DrivenChoice>
      </FieldRow>
      <FieldRow path="marker.first_id" label={m.type === "single" ? "ID" : "First ID"} icon="row-hash" issues={iss("marker.first_id")}>
        <DrivenField {...drv("marker.first_id")} value={m.first_id} driver={`auto id: from the key "${f.key}", unique in this document`}
          int min={0} bad={bad("marker.first_id")} />
        <span className="range" data-testid="id-range">{idRange(m, showPlan ? showPlan.ids : undefined)}</span>
      </FieldRow>
      <Group title="Size" />
      <FieldRow path="marker.marker_mm" label="Marker size" icon="row-ruler" issues={iss("marker.marker_mm")}>
        <DrivenField {...drv("marker.marker_mm")} value={!m.auto ? m.marker_mm : showPlan ? showPlan.marker_mm : m.marker_mm}
          driver={fills} unit="mm" min={0.1} step={0.5} bad={bad("marker.marker_mm")} />
      </FieldRow>
      {m.type !== "single" && (
        <FieldRow path="marker.cols" label="Columns × Rows" icon="row-grid-3x3" issues={iss("marker.cols")}>
          <DrivenField {...drv("marker.cols")} value={m.cols} driver={counts} int min={1} max={50} bad={bad("marker.cols")} />
          <span className="times">×</span>
          <DrivenField {...drv("marker.rows")} value={m.rows} driver={counts} int min={1} max={50} bad={bad("marker.cols")} />
        </FieldRow>
      )}
      {m.type === "grid" && (
        <FieldRow path="marker.separation_mm" label="Separation" icon="row-move-horizontal" issues={iss("marker.separation_mm")} title="The gap between markers">
          <DrivenField {...drv("marker.separation_mm")} value={m.separation_mm > 0 ? m.separation_mm : showPlan ? showPlan.separation_mm : null}
            driver="core rule: the grid's gap rule, from the marker size" unit="mm" min={0} step={0.5} bad={bad("marker.separation_mm")} />
        </FieldRow>
      )}
      {m.type === "charuco" && (
        <FieldRow path="marker.checker_mm" label="Checker" icon="row-ruler" issues={iss("marker.checker_mm")}>
          <DrivenField {...drv("marker.checker_mm")} value={m.checker_mm > 0 ? m.checker_mm : showPlan ? showPlan.checker_mm : null}
            driver={m.auto ? fills : "core rule: the smallest 0.5 mm square that leaves the marker one module of white"}
            unit="mm" min={0} step={0.5} bad={bad("marker.checker_mm")} />
        </FieldRow>
      )}
      {m.type === "charuco" && (
        <FieldRow path="marker.origin_square" label="Origin" icon="joint" issues={iss("marker.origin_square")} title="Where the Joint Origin sits on the board">
          <DrivenChoice path="marker.origin_square" driven={!isSet(f, "marker.origin_square")} value={square ? "square" : "corner"}
            driver={`${DEFAULT} (OpenCV's board corner)`} onReset={() => st.resetField("marker.origin_square")}
            onSet={(v) => (v === "square" ? st.setField("marker.origin_square", square ?? [0, 0]) : st.resetField("marker.origin_square"))}>
            <SegmentedRow path="marker.origin_square" compact value={square ? "square" : "corner"} options={ORIGINS}
              onChange={(v) => (v === "square" ? st.setField("marker.origin_square", [0, 0]) : st.resetField("marker.origin_square"))} />
          </DrivenChoice>
        </FieldRow>
      )}
      {m.type === "charuco" && square && (
        <FieldRow path="marker.origin_square.at" label="Column, row" title="The square, 0-based from OpenCV's origin corner">
          <NumberField path="marker.origin_square.col" value={square[0]} int min={0} onCommit={(v) => st.setField("marker.origin_square", [v, square[1]])} />
          <span className="times">,</span>
          <NumberField path="marker.origin_square.row" value={square[1]} int min={0} onCommit={(v) => st.setField("marker.origin_square", [square[0], v])} />
        </FieldRow>
      )}
      {/* Suggest after the size rows: picking one sets them */}
      <FieldRow path="marker.suggest" label="Suggest" icon="row-wand-sparkles" issues={iss("marker.suggest")} title="Good value sets for this rectangle: picking one sets the size rows above">
        <SuggestSelect suggestions={suggestions} empty={f.profile ? "…" : "needs a profile"} onPick={st.pick}
          current={m.auto ? -1 : suggestions.findIndex((s) => s.params.cols === m.cols && s.params.rows === m.rows && Math.abs(s.params.marker_mm - m.marker_mm) < 1e-6)} />
      </FieldRow>
      <Group title="Orientation" />
      <FieldRow path="marker.turn" label="Turn" icon="row-rotate-cw" issues={iss("marker.turn")}>
        <DrivenChoice {...drv("marker.turn")} value={m.turn} driver={`${DEFAULT} (0°)`}>
          <SegmentedRow path="marker.turn" compact value={m.turn} options={TURNS} onChange={(v) => st.setField("marker.turn", Number(v) as MarkerParams["turn"])} />
        </DrivenChoice>
      </FieldRow>
      {/* WHY (Zach, 2026-10-20 night): "I like how previously there was the ability to rotate the marker on the page";
          a rectangle profile turns about its centre (the arc on the sketch drags it); the skeleton shows
          Rotation for a rectangle profile only (a face's box is the core's: Turn it) */}
      {rect && (
        <FieldRow path="profile.angle_deg" label="Rotation" icon="row-rotate-ccw"
          title="The rectangle profile's angle, counter-clockwise: drag the arc over the marker, or type it">
          <NumberField path="profile.angle_deg" value={rect.angle_deg} unit="°" step={15}
            onCommit={(v) => st.updateShape({ ...rect, angle_deg: deg360(v) })} />
        </FieldRow>
      )}
      <Group title="Details" />
      {/* the quiet zone has no driven record in the document: its default (1) is the driven value */}
      <FieldRow path="marker.quiet_modules" label="Quiet zone" icon="row-square-square" issues={iss("marker.quiet_modules")} title="The white border round the marker, in cells">
        <DrivenField path="marker.quiet_modules" value={m.quiet_modules} driven={m.quiet_modules === DEFAULT_MARKER.quiet_modules}
          driver={`${DEFAULT} (${DEFAULT_MARKER.quiet_modules} cell)`} unit="cells" min={0} step={1} bad={bad("marker.quiet_modules")}
          onSet={(v) => st.setField("marker.quiet_modules", v)} onReset={() => st.resetField("marker.quiet_modules")} />
      </FieldRow>
      {/* WHY driven (Zach, 2026-10-21: "The key should be grey outed I think beacuse its being automtically set"):
          a feature's key is its id until typed; empty + Enter or ↺ gives the id back */}
      <FieldRow path="feature.key" label="Key" icon="row-key-round" title="Auto id keeps the first id under this stable key; keys are unique in the document">
        <DrivenText path="feature.key" value={f.key} driven={f.key === f.id} driver={`the feature's own id (${f.id})`}
          onSet={st.setKey} onReset={() => st.setKey("")} />
      </FieldRow>
    </div>
  );

  // WHY tuned last (docs/design/panel_skeleton.md; Zach, 2026-10-21): "if its a
  // good preset right then the defaults should be good"
  const makeTab = (
    <div data-tab-body="make">
      <Group title="Size & cut" />
      {preset && sizeStep && presetSize && (
        <FieldRow path="marker.size_step" label="Size step" icon="row-grip" issues={iss("marker.size_step")} title="What driven sizes round to; typed sizes are never rounded">
          {method === "inkjet" || isSet(f, "marker.size_step") ? (
            <DrivenChoice {...drv("marker.size_step")} value={stepKey(sizeStep)} driver={`the preset (${stepLabel(presetSize, preset)})`}>
              <Select path="marker.size_step" value={stepKey(sizeStep)} options={stepOptions(sizeStep, preset)}
                onChange={(k) => st.setField("marker.size_step", stepOf(String(k)))} />
            </DrivenChoice>
          ) : <span className="xp-grey" data-testid="size-step-line">{stepLabel(presetSize, preset)}</span>}
        </FieldRow>
      )}
      <FieldRow path="trim" label="Trim" icon="row-scissors" title="What the sticker is cut to: everything inside the cut is white" issues={iss("trim")}>
        <DrivenChoice {...drv("trim")} value={f.trim} driver={`${DEFAULT} (${DEFAULT_TRIM})`}>
          <SegmentedRow path="trim" compact value={f.trim} options={fusion ? TRIM_ICONS : TRIM_OPTS} onChange={(v) => st.setField("trim", v as Trim)} />
        </DrivenChoice>
      </FieldRow>
      <Group title="Heights" />
      {method === "print3d" ? (
        <>
          <FieldRow path="extrude.mode" label="Extrude" icon="row-layers-2" issues={iss("extrude.mode")} title="Which colours are made">
            <DrivenChoice {...drv("extrude.mode")} value={mode}
              driver={`auto: ${refFace ? "black only, on a reference face (the body is the white)" : "both, in open space"}`}>
              <SegmentedRow path="extrude.mode" compact value={mode} options={fusion ? MODE_ICONS : MODES} onChange={(v) => st.setField("extrude.mode", v)} />
            </DrivenChoice>
          </FieldRow>
          <FieldRow path="extrude.white_mm" label="White height" icon="row-arrow-up-from-line" issues={iss("extrude.white_mm")} title="The white tile, from the face to its outer face">
            <DrivenField {...drv("extrude.white_mm")} value={height("white_mm")} driver="the preset: whole layers"
              unit="mm" min={0} step={layer} bad={bad("extrude.white_mm")} />
          </FieldRow>
          <FieldRow path="extrude.black_mm" label="Black height" icon="row-arrow-up-from-line" issues={iss("extrude.black_mm")} title="The black, measured from the white's outer face into it">
            <DrivenField {...drv("extrude.black_mm")} value={height("black_mm")} driver="the preset: whole layers"
              unit="mm" min={0} step={layer} bad={bad("extrude.black_mm")} />
          </FieldRow>
          {/* WHY (Zach, 2026-10-20 night): "black height is always measured from the outer face of the white" */}
          <Note testid="black-from">from the white's outer face</Note>
        </>
      ) : (
        <FieldRow path="extrude.paper_mm" label="Paper thickness" icon="row-arrow-up-from-line" issues={iss("extrude.paper_mm")} title="The paper / vinyl the sticker is printed on">
          <DrivenField {...drv("extrude.paper_mm")} value={height("paper_mm", preset?.thickness_mm ?? null)}
            driver={`the preset's thickness${preset?.thickness_mm != null ? ` (${preset.thickness_mm} mm)` : ""}`}
            unit="mm" min={0} step={0.01} bad={bad("extrude.paper_mm")} />
        </FieldRow>
      )}
      <Group title="Outward side" />
      {/* WHY always (Zach, 2026-10-20 night): "in all cases you get the option to just flip it from what it currently is" */}
      <FieldRow path="marker.flip" label="Flip" icon="row-flip-vertical" issues={iss("marker.flip")}
        title={refFace ? "Turn it over: the reference face picks the starting side" : "Turn it over: no reference face, so up is the starting side"}>
        <DrivenChoice {...drv("marker.flip")} value={m.flip} driver={`${DEFAULT} (off)`}>
          <Switch path="marker.flip" value={m.flip} onChange={(v) => st.setField("marker.flip", v)} />
        </DrivenChoice>
      </FieldRow>
      <Note testid="flip-out">Outward side: {outward}</Note>
    </div>
  );

  const place = l.place ?? "on_marker";
  const labelTab = (
    <div data-tab-body="label">
      <Group title="Label" />
      {/* WHY off by default (Zach, 2026-10-20 night): "Label by default should be off" */}
      <FieldRow path="label.on" label="On" icon="row-type" issues={iss("label.on")}>
        <DrivenChoice {...drv("label.on")} value={l.on} driver={`${DEFAULT} (off)`}>
          <Switch path="label.on" value={l.on} onChange={(v) => st.setField("label.on", v)} />
        </DrivenChoice>
      </FieldRow>
      {l.on && (
        <>
          <FieldRow path="label.text" label="Text" issues={iss("label.text")} className="tall">
            <TextArea path="label.text" value={l.text} onCommit={(v) => st.setLabel("text", v, f.id)} placeholder="#{ids}" />
          </FieldRow>
          <div className="hint-line" data-testid="label-placeholders">
            {PLACEHOLDERS} · Enter: a new line{showPlan?.label ? ` → “${(showPlan.label.lines ?? [showPlan.label.text]).join(" / ")}”` : ""}
          </div>
          {/* Place and Surface: absent = driven (the contract's defaults), so their own value says it */}
          <FieldRow path="label.place" label="Place" icon="row-map-pin" issues={iss("label.place")}>
            <DrivenChoice path="label.place" driven={l.place === undefined} value={place} driver={`${DEFAULT} (on marker)`}
              onSet={(v) => st.setField("label.place", v)} onReset={() => st.resetField("label.place")}>
              <SegmentedRow path="label.place" compact value={place} options={PLACES} onChange={(v) => st.setField("label.place", v as LabelParams["place"])} />
            </DrivenChoice>
          </FieldRow>
          {place === "on_marker" && (
            <FieldRow path="label.surface" label="Surface" issues={iss("label.surface")}>
              <DrivenChoice path="label.surface" driven={l.surface === undefined} value={l.surface ?? "black"} driver={`${DEFAULT} (black)`}
                onSet={(v) => st.setField("label.surface", v)} onReset={() => st.resetField("label.surface")}>
                <SegmentedRow path="label.surface" compact value={l.surface ?? "black"} options={SURFACES}
                  onChange={(v) => st.setField("label.surface", v as LabelParams["surface"])} />
              </DrivenChoice>
            </FieldRow>
          )}
          <FieldRow path="label.side" label="Side" issues={iss("label.side")}>
            <DrivenChoice {...drv("label.side")} value={l.side} driver={`${DEFAULT} (below)`}>
              <SegmentedRow path="label.side" compact value={l.side} options={SIDES} onChange={(v) => st.setField("label.side", v as typeof l.side)} />
            </DrivenChoice>
          </FieldRow>
          <FieldRow path="label.height_mm" label="Height" icon="row-a-large-small" issues={iss("label.height_mm")} title="Cap height">
            <DrivenField {...drv("label.height_mm")} value={l.height_mm > 0 ? l.height_mm : showPlan?.label ? showPlan.label.height_mm : null}
              driver="core rule: 0.12 × the rectangle's short side, 2.5 to 12 mm" unit="mm" min={0} step={0.5} bad={bad("label.height_mm")} />
          </FieldRow>
          {place === "outside" && (
            <FieldRow path="label.gap_mm" label="Gap" issues={iss("label.gap_mm")}>
              <DrivenField {...drv("label.gap_mm")} value={l.gap_mm} driver={DEFAULT} unit="mm" min={0} step={0.5} bad={bad("label.gap_mm")} />
            </FieldRow>
          )}
          <FieldRow path="label.offset_mm" label="Offset X" icon="row-move-horizontal" issues={iss("label.offset_mm")} title="From the preset spot; drag the text on the sketch to move it">
            <DrivenField path="label.offset_mm.x" value={l.offset_mm[0]} driven={l.offset_mm[0] === 0} driver={offsetDriver} unit="mm" step={0.5}
              onSet={(v) => st.setLabel("offset_mm", [v, l.offset_mm[1]])} onReset={() => st.setLabel("offset_mm", [0, l.offset_mm[1]])} />
          </FieldRow>
          <FieldRow path="label.offset_mm.y" label="Offset Y" icon="row-move-vertical" title="From the preset spot; drag the text on the sketch to move it">
            <DrivenField path="label.offset_mm.y" value={l.offset_mm[1]} driven={l.offset_mm[1] === 0} driver={offsetDriver} unit="mm" step={0.5}
              onSet={(v) => st.setLabel("offset_mm", [l.offset_mm[0], v])} onReset={() => st.setLabel("offset_mm", [l.offset_mm[0], 0])} />
          </FieldRow>
        </>
      )}
      {/* WHY on Label (Zach, 2026-10-20): the corner mark reads as a mark, beside the text; its own
          group (Zach, 2026-10-20 night: "there should be a dividing line between the label and corner mark section") */}
      <Group title="Corner mark" />
      <FieldRow path="marker.corner_mark" label="Corner mark" icon="row-triangle-right" issues={iss("marker.corner_mark")}>
        <DrivenChoice {...drv("marker.corner_mark")} value={m.corner_mark} driver={`${DEFAULT} (none)`}>
          <SegmentedRow path="marker.corner_mark" compact value={m.corner_mark} options={CORNERS} onChange={(v) => st.setField("marker.corner_mark", v as MarkerParams["corner_mark"])} />
        </DrivenChoice>
      </FieldRow>
    </div>
  );

  const body: Record<Tab, ReactNode> = { make: makeTab, marker: markerTab, label: labelTab };
  // Fusion's title: "ARUCO EXTRUDE" for a new feature, "EDIT ARUCO EXTRUDE" for one
  // being edited (the skin shows "Edit" and hides the number; ../skins/fusion.css)
  const title = (
    <>{!fresh && <span className="xp-title-edit">Edit </span>}ArUco Extrude<span className="xp-title-num"> {featureNumber(doc, f.id)}</span></>
  );
  return (
    <FloatingPanel title={title} icon={<Glyph name="extrude" />} collapsed={panel.collapsed} onCollapse={st.collapse} testid="extrude-panel"
      anchor={anchor} anchorKey={f.id} avoid={others} width={320} className="xpanel"
      footer={
        <>
          <div className="summary" data-testid="plan-summary">
            <div className="summary-line"><PlanLine profile={!!f.profile} summary={showPlan?.summary ?? null} error={planError} /></div>
            <Messages path="summary" issues={kit(routed.summary)} />
          </div>
          <div className="xp-actions">
            <Button variant="primary" onClick={st.ok} testid="panel-ok" disabled={!f.profile}>OK</Button>
            <Button onClick={st.cancel} testid="panel-cancel">Cancel</Button>
          </div>
        </>
      }>
      <Tabs value={panel.tab} onChange={(t) => st.setTab(t as Tab)}
        tabs={[
          { id: "marker", name: "Marker", icon: "tab-marker", level: tabLevel(routed, rows.marker) },
          { id: "label", name: "Label", icon: "tab-label", level: tabLevel(routed, rows.label) },
          // WHY always "Make", the method as its icon (Zach, 2026-10-21: "keep it just Make so we always know where we should go looking")
          { id: "make", name: "Make", icon: `tab-${methodIcon}`, level: tabLevel(routed, rows.make) },
        ]} />
      <div className="tab-body">{body[panel.tab] ?? markerTab}</div>
    </FloatingPanel>
  );
}
