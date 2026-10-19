// The ArUco Extrude panel (Fusion's feature dialog) for the feature it
// edits. It opens beside the clicked marker (V1 "Click-to-inspect",
// 2026-10-18) and follows it; on a phone it docks to the bottom. The Preset
// and the Trim first (they describe the sticker), the selection rows
// (Profile, Rectangle), then Marker | Label. Every
// row shows its own issues from plan().warnings -- and the id's from auto
// id -- under it. Every value is driven (grey: the core's, a rule's, auto id's
// or the default) or set (typed: normal, with ↺); ../ui/DrivenField.tsx.
// Manual values always go through; the plan flags what does not fit, it
// never refuses.
// WHY words, not icons, on the segmented choices (Zach, 2026-10-18: "I like
// the use of text instead of icons here").
import { FieldRow, Glyph, Messages, NumberField, SegmentedRow, Select, Switch, Tabs, TextField, Button, type Issue as KitIssue, type Opt } from "@bam/ui";
import { X } from "lucide-react";
import type { Issue, MarkerParams, Trim } from "../core/contract";
import { DEFAULT_MARKER, DEFAULT_TRIM, effectiveTrim, featureNumber, featureRect, getFeature, idRange, isSet, typeCounts } from "../model/doc";
import { boxOf, toScreen } from "../model/geom";
import { samePreset, myPresets } from "../presets/local";
import { shapeLoop } from "../sketch/model";
import { useStudio } from "../store";
import type { Box } from "../ui/anchor";
import { DrivenChoice, DrivenField } from "../ui/DrivenField";
import { FloatingPanel } from "../ui/FloatingPanel";
import { TextArea } from "../ui/TextArea";
import { routeIssues, shownRows, tabLevel } from "./issues";
import { SuggestSelect } from "./SuggestSelect";

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
const NO_PROFILE = "Needs a profile: pick the face this rectangle was inscribed from (Profile)";
const trims = (hasProfile: boolean): Opt[] => [
  { value: "profile", label: "Profile", hint: hasProfile ? "The sticker is the whole profile (the face), its holes cut out" : NO_PROFILE, disabled: !hasProfile },
  { value: "rectangle", label: "Rectangle", hint: "The sticker is the marker rectangle" },
  { value: "marker", label: "Marker", hint: "The sticker is the marker and its quiet zone" },
];
const PLACEHOLDERS = "{id} {first} {last} {ids} {dict} {type}";
const SIDES: Opt[] = ["below", "above", "left", "right"].map((s) => ({ value: s, label: s[0].toUpperCase() + s.slice(1) }));
/** The core's issues in the kit's shape (an object literal per issue). */
const kit = (xs: Issue[] | undefined): KitIssue[] => (xs ?? []).map((i) => ({ field: i.field, level: i.level, text: i.text }));

const FALLBACK_DICTS = ["DICT_4X4_50", "DICT_4X4_100", "DICT_4X4_250", "DICT_5X5_50", "DICT_5X5_100", "DICT_6X6_50", "DICT_6X6_250"];

function SelRow({ path, label, count, active, onActivate, onClear, issues, icon, testid, emptyText }: {
  path: string; label: string; count: number; active: boolean; onActivate: () => void; onClear: () => void;
  issues: KitIssue[]; icon: string; testid: string; emptyText: string;
}) {
  return (
    <FieldRow path={path} label={label} issues={issues}>
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

/** What drives a field while it is driven (the tooltip). */
const DEFAULT = "default";

export function ExtrudePanel() {
  const st = useStudio();
  const { doc, plans, panel, suggestions, info, builtins } = st;
  const f = getFeature(doc, panel.featureId);
  if (!panel.open || !f) return null;
  const m = f.marker, l = f.label;
  const plan = plans[f.id] ?? null;
  const planError = st.planErrors[f.id] ?? null;
  const refFace = !!f.profile;
  const shown = shownRows(m, l.on, refFace);
  const issues: Issue[] = plan && f.rectId ? [...plan.warnings] : [];
  // WHY: the contract hands the core a typed checker only with a typed marker
  // size (web_api.spec_of), so say so rather than show a value that is not drawn
  if (m.type === "charuco" && isSet(f, "marker.checker_mm") && !isSet(f, "marker.marker_mm")) {
    issues.push({ field: "marker.checker_mm", level: "warn", text: "Used only with a set Marker size: the board fills the rectangle" });
  }
  // auto id's issues for this feature (Issue.key): a collision, a full dictionary
  for (const i of st.idIssues) if (i.key === f.key) issues.push({ ...i, field: "marker.first_id" });
  const routed = routeIssues(issues, shown);
  const iss = (p: string) => kit(routed[p]);
  const bad = (p: string) => !!routed[p]?.some((i) => i.level === "error");
  const library = [...builtins, ...myPresets()].find((p) => p.id === doc.preset?.id);
  const modified = !!doc.preset && !!library && !samePreset(library, doc.preset);
  const dicts: Opt[] = (info?.dictionaries.map((d) => ({ value: d.name, label: d.name.replace("DICT_", ""), hint: `${d.capacity} ids` }))
    ?? FALLBACK_DICTS.map((d) => ({ value: d, label: d.replace("DICT_", "") })));
  const showPlan = plan && f.rectId ? plan : null;
  const profileHasHoles = !!f.profile?.holes.length;
  /** The props every driven field shares: its state, set and reset. */
  const drv = (path: string) => ({ path, driven: !isSet(f, path), onSet: (v: unknown) => st.setField(path, v), onReset: () => st.resetField(path) });
  const fills = "fills the rectangle";
  const [dc, dr] = typeCounts(m.type);
  const counts = `default for ${m.type === "grid" ? "a grid" : "a ChArUco board"} (${dc} × ${dr})`;
  const square = m.origin_square ?? null;
  const offsetDriver = "the preset spot (Side); drag the text on the sketch to move it";

  // what the panel opens beside: the rectangle, the marker and its label
  // band, on screen; the other markers' boxes it keeps clear where it can
  const screenBox = (id: string): Box | null => {
    const g = getFeature(doc, id), rect = featureRect(doc, g), p = plans[id];
    if (!rect) return null;
    const pts = [...shapeLoop(rect), ...(p ? p.outer : []), ...(p?.label?.box ?? [])];
    return boxOf(pts.map((q) => toScreen(st.camera, st.view.w, st.view.h, q)));
  };
  const anchor = screenBox(f.id);
  const others = doc.features.filter((g) => g.id !== f.id).map((g) => screenBox(g.id)).filter((b): b is Box => !!b);

  const markerTab = (
    <div data-tab-body="marker">
      <FieldRow path="marker.type" label="Type" issues={iss("marker.type")}>
        <DrivenChoice {...drv("marker.type")} value={m.type} driver={`${DEFAULT} (single)`}>
          <SegmentedRow path="marker.type" value={m.type} options={TYPES} onChange={(v) => st.setField("marker.type", v as MarkerParams["type"])} />
        </DrivenChoice>
      </FieldRow>
      <FieldRow path="marker.dictionary" label="Dictionary" issues={iss("marker.dictionary")}>
        <DrivenChoice {...drv("marker.dictionary")} value={m.dictionary} driver={`${DEFAULT} (${DEFAULT_MARKER.dictionary.replace("DICT_", "")})`}>
          <Select path="marker.dictionary" value={m.dictionary} options={dicts} onChange={(v) => st.setField("marker.dictionary", String(v))} />
        </DrivenChoice>
      </FieldRow>
      <FieldRow path="marker.first_id" label={m.type === "single" ? "ID" : "First ID"} issues={iss("marker.first_id")}>
        <DrivenField {...drv("marker.first_id")} value={m.first_id} driver={`auto id: from the key "${f.key}", unique in this document`}
          int min={0} bad={bad("marker.first_id")} />
        <span className="range" data-testid="id-range">{idRange(m, showPlan ? showPlan.ids : undefined)}</span>
      </FieldRow>
      <FieldRow path="marker.marker_mm" label="Marker" issues={iss("marker.marker_mm")}>
        <DrivenField {...drv("marker.marker_mm")} value={!m.auto ? m.marker_mm : showPlan ? showPlan.marker_mm : m.marker_mm}
          driver={fills} unit="mm" min={0.1} step={0.5} bad={bad("marker.marker_mm")} />
      </FieldRow>
      {m.type === "charuco" && (
        <FieldRow path="marker.checker_mm" label="Checker" issues={iss("marker.checker_mm")}>
          <DrivenField {...drv("marker.checker_mm")} value={m.checker_mm > 0 ? m.checker_mm : showPlan ? showPlan.checker_mm : null}
            driver={m.auto ? fills : "core rule: the smallest 0.5 mm square that leaves the marker one module of white"}
            unit="mm" min={0} step={0.5} bad={bad("marker.checker_mm")} />
        </FieldRow>
      )}
      {m.type === "charuco" && (
        <FieldRow path="marker.origin_square" label="Origin" issues={iss("marker.origin_square")} title="Where the Joint Origin sits on the board">
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
      {m.type === "grid" && (
        <FieldRow path="marker.separation_mm" label="Separation" issues={iss("marker.separation_mm")} title="The gap between markers">
          <DrivenField {...drv("marker.separation_mm")} value={m.separation_mm > 0 ? m.separation_mm : showPlan ? showPlan.separation_mm : null}
            driver="core rule: the grid's gap rule, from the marker size" unit="mm" min={0} step={0.5} bad={bad("marker.separation_mm")} />
        </FieldRow>
      )}
      {m.type !== "single" && (
        <FieldRow path="marker.cols" label="Columns × Rows" issues={iss("marker.cols")}>
          <DrivenField {...drv("marker.cols")} value={m.cols} driver={counts} int min={1} max={50} bad={bad("marker.cols")} />
          <span className="times">×</span>
          <DrivenField {...drv("marker.rows")} value={m.rows} driver={counts} int min={1} max={50} bad={bad("marker.cols")} />
        </FieldRow>
      )}
      <FieldRow path="marker.suggest" label="Suggest" issues={iss("marker.suggest")} title="Good value sets for this rectangle: picking one sets them">
        <SuggestSelect suggestions={suggestions} empty={f.rectId ? "…" : "needs a rectangle"} onPick={st.pick}
          current={m.auto ? -1 : suggestions.findIndex((s) => s.params.cols === m.cols && s.params.rows === m.rows && Math.abs(s.params.marker_mm - m.marker_mm) < 1e-6)} />
      </FieldRow>
      <FieldRow path="marker.turn" label="Turn" issues={iss("marker.turn")}>
        <DrivenChoice {...drv("marker.turn")} value={m.turn} driver={`${DEFAULT} (0°)`}>
          <SegmentedRow path="marker.turn" compact value={m.turn} options={TURNS} onChange={(v) => st.setField("marker.turn", Number(v) as MarkerParams["turn"])} />
        </DrivenChoice>
      </FieldRow>
      {!refFace && (
        <FieldRow path="marker.flip" label="Flip" issues={iss("marker.flip")} title="Mirror: no reference face sets which side is up">
          <DrivenChoice {...drv("marker.flip")} value={m.flip} driver={`${DEFAULT} (off)`}>
            <Switch path="marker.flip" value={m.flip} onChange={(v) => st.setField("marker.flip", v)} />
          </DrivenChoice>
        </FieldRow>
      )}
      <FieldRow path="marker.corner_mark" label="Corner mark" issues={iss("marker.corner_mark")}>
        <DrivenChoice {...drv("marker.corner_mark")} value={m.corner_mark} driver={`${DEFAULT} (none)`}>
          <SegmentedRow path="marker.corner_mark" compact value={m.corner_mark} options={CORNERS} onChange={(v) => st.setField("marker.corner_mark", v as MarkerParams["corner_mark"])} />
        </DrivenChoice>
      </FieldRow>
      <details className="adv" data-testid="panel-advanced">
        <summary>Advanced</summary>
        <FieldRow path="feature.key" label="Key" title="Auto id hashes this stable key to the first id; keys are unique in the document">
          <TextField path="feature.key" value={f.key} onCommit={st.setKey} placeholder={f.id} />
        </FieldRow>
      </details>
    </div>
  );

  const labelTab = (
    <div data-tab-body="label">
      <FieldRow path="label.on" label="On" issues={iss("label.on")}>
        <DrivenChoice {...drv("label.on")} value={l.on} driver={`${DEFAULT} (on)`}>
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
          <FieldRow path="label.side" label="Side" issues={iss("label.side")}>
            <DrivenChoice {...drv("label.side")} value={l.side} driver={`${DEFAULT} (below)`}>
              <SegmentedRow path="label.side" compact value={l.side} options={SIDES} onChange={(v) => st.setField("label.side", v as typeof l.side)} />
            </DrivenChoice>
          </FieldRow>
          <FieldRow path="label.offset_mm" label="Offset X" issues={iss("label.offset_mm")} title="From the preset spot; drag the text on the sketch to move it">
            <DrivenField path="label.offset_mm.x" value={l.offset_mm[0]} driven={l.offset_mm[0] === 0} driver={offsetDriver} unit="mm" step={0.5}
              onSet={(v) => st.setLabel("offset_mm", [v, l.offset_mm[1]])} onReset={() => st.setLabel("offset_mm", [0, l.offset_mm[1]])} />
          </FieldRow>
          <FieldRow path="label.offset_mm.y" label="Offset Y" title="From the preset spot; drag the text on the sketch to move it">
            <DrivenField path="label.offset_mm.y" value={l.offset_mm[1]} driven={l.offset_mm[1] === 0} driver={offsetDriver} unit="mm" step={0.5}
              onSet={(v) => st.setLabel("offset_mm", [l.offset_mm[0], v])} onReset={() => st.setLabel("offset_mm", [l.offset_mm[0], 0])} />
          </FieldRow>
          <FieldRow path="label.height_mm" label="Height" issues={iss("label.height_mm")} title="Cap height">
            <DrivenField {...drv("label.height_mm")} value={l.height_mm > 0 ? l.height_mm : showPlan?.label ? showPlan.label.height_mm : null}
              driver="core rule: 0.12 × the rectangle's short side, 2.5 to 12 mm" unit="mm" min={0} step={0.5} bad={bad("label.height_mm")} />
          </FieldRow>
          <FieldRow path="label.gap_mm" label="Gap" issues={iss("label.gap_mm")}>
            <DrivenField {...drv("label.gap_mm")} value={l.gap_mm} driver={DEFAULT} unit="mm" min={0} step={0.5} bad={bad("label.gap_mm")} />
          </FieldRow>
        </>
      )}
    </div>
  );

  return (
    <FloatingPanel title={`ArUco Extrude ${featureNumber(doc, f.id)}`} icon={<Glyph name="extrude" />} collapsed={panel.collapsed} onCollapse={st.collapse} testid="extrude-panel"
      anchor={anchor} anchorKey={f.id} avoid={others} width={320}
      footer={
        <>
          <Button variant="primary" onClick={st.ok} testid="panel-ok" disabled={!f.rectId}>OK</Button>
          <Button onClick={st.cancel} testid="panel-cancel">Cancel</Button>
        </>
      }>
      <FieldRow path="preset" label="Preset" issues={iss("preset")}>
        <button type="button" className="preset-pick" data-testid="panel-preset" onClick={() => st.openModal("presets")}
          title="How it is made: open the presets">
          <Glyph name={doc.preset?.method === "print3d" ? "print3d" : "inkjet"} />
          <span className="preset-name">{doc.preset ? doc.preset.name : "Loading…"}{modified && <i className="modified"> (modified)</i>}</span>
        </button>
        <button type="button" className="kit-ib" title="Presets…" aria-label="Presets" data-testid="panel-preset-more" onClick={() => st.openModal("presets")}>
          <Glyph name="dots" />
        </button>
      </FieldRow>
      <FieldRow path="trim" label="Trim" title="What the sticker is cut to: everything inside the cut is white"
        issues={f.trim !== effectiveTrim(f)
          ? [...iss("trim"), { field: "trim", level: "info", text: "no profile now: cut to the rectangle until one is selected again" }]
          : iss("trim")}>
        <DrivenChoice {...drv("trim")} value={effectiveTrim(f)} driver={`${DEFAULT} (${DEFAULT_TRIM})`}>
          <SegmentedRow path="trim" compact value={effectiveTrim(f)} options={trims(refFace)} onChange={(v) => st.setField("trim", v as Trim)} />
        </DrivenChoice>
      </FieldRow>
      <SelRow path="profile" label="Profile" icon="profile" testid="sel-profile" count={f.profile ? 1 : 0} emptyText="None (optional)"
        active={panel.selector === "profile"} issues={iss("profile")}
        onActivate={() => st.setSelector(panel.selector === "profile" ? null : "profile")} onClear={st.clearProfile} />
      <SelRow path="rect" label="Rectangle" icon="rect" testid="sel-rect" count={f.rectId ? 1 : 0} emptyText="Select…"
        active={panel.selector === "rect" || st.inscribing} issues={iss("rect")}
        onActivate={() => st.setSelector(panel.selector === "rect" ? null : "rect")} onClear={st.clearRect} />
      {profileHasHoles && (
        <FieldRow path="holes" label="Holes" title="Inscribe the rectangle around the holes, or over them">
          <SegmentedRow path="holes" compact value={f.holes} options={[{ value: "avoid", label: "Avoid" }, { value: "ignore", label: "Ignore" }]}
            onChange={(v) => void st.setHoles(v as "avoid" | "ignore")} />
        </FieldRow>
      )}
      <Tabs value={panel.tab} onChange={(t) => st.setTab(t as "marker" | "label")}
        tabs={[
          { id: "marker", name: "Marker", level: tabLevel(routed, "marker.") },
          { id: "label", name: "Label", level: tabLevel(routed, "label.") },
        ]} />
      <div className="tab-body">{panel.tab === "marker" ? markerTab : labelTab}</div>
      <div className="summary" data-testid="plan-summary">
        <div className="summary-line">{st.inscribing ? "Inscribing a rectangle…" : !f.rectId ? "Select a rectangle or a face" : showPlan ? showPlan.summary : planError ? `Plan failed: ${planError}` : "Planning…"}</div>
        <Messages path="summary" issues={kit(routed.summary)} />
      </div>
    </FloatingPanel>
  );
}
