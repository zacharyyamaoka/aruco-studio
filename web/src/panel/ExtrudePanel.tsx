// The ArUco Extrude panel (Fusion's feature dialog) for the feature it
// edits: the selection rows (Profile, Rectangle), the Preset first, then
// Marker | Label. Every row shows its own issues from plan().warnings under
// it. Every value is driven (grey: the core's, a rule's or the default) or
// set (typed: normal, with ↺); ../ui/DrivenField.tsx. Manual values always
// go through; the plan flags what does not fit, it never refuses.
import { FieldRow, Glyph, Messages, SegmentedRow, Select, Switch, Tabs, TextField, Button, type Issue as KitIssue, type Opt } from "@bam/ui";
import { X } from "lucide-react";
import type { Issue, MarkerParams } from "../core/contract";
import { DEFAULT_MARKER, featureNumber, getFeature, idRange, isSet, typeCounts } from "../model/doc";
import { samePreset, myPresets } from "../presets/local";
import { useStudio } from "../store";
import { DrivenChoice, DrivenField } from "../ui/DrivenField";
import { FloatingPanel } from "../ui/FloatingPanel";
import { routeIssues, shownRows, tabLevel } from "./issues";

const TYPES: Opt[] = [
  { value: "single", label: "Single", icon: "single", hint: "Single marker" },
  { value: "grid", label: "Grid", icon: "grid", hint: "Grid of markers" },
  { value: "charuco", label: "ChArUco", icon: "charuco", hint: "ChArUco board" },
];
const TURNS: Opt[] = [0, 90, 180, 270].map((t) => ({ value: t, label: `${t}°`, hint: `Turn ${t}°` }));
const CORNERS: Opt[] = [
  { value: "none", label: "None", icon: "cm-none", hint: "No corner mark" },
  { value: "triangle", label: "Triangle", icon: "cm-tri", hint: "A triangle in the quiet zone's top-left corner" },
];
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
        <DrivenField {...drv("marker.first_id")} value={m.first_id} driver={DEFAULT} int min={0} bad={bad("marker.first_id")} />
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
      <div className="row kit-field suggest" data-row="marker.suggest">
        <div className="row-main kit-row"><label className="row-label"><span className="row-text">Suggest</span></label>
          <div className="row-ctl muted">{suggestions.length ? "pick one: it sets the size" : f.rectId ? "…" : "needs a rectangle"}</div></div>
        <ul className="suggest-list" data-testid="suggestions">
          {suggestions.map((s, i) => {
            const now = !m.auto && s.params.cols === m.cols && s.params.rows === m.rows && Math.abs(s.params.marker_mm - m.marker_mm) < 1e-6;
            return (
              <li key={i}>
                <button type="button" className={`sugg${now ? " on" : ""}`} data-testid="suggestion" data-label={s.label} title={`${s.label}: ${s.reason}`}
                  onClick={() => st.pick(s)}>
                  <span className="sugg-label">{s.label}</span><span className="sugg-reason" data-testid="suggestion-reason">{s.reason}</span>
                </button>
              </li>
            );
          })}
        </ul>
        <Messages path="marker.suggest" issues={iss("marker.suggest")} />
      </div>
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
          <SegmentedRow path="marker.corner_mark" value={m.corner_mark} options={CORNERS} onChange={(v) => st.setField("marker.corner_mark", v as MarkerParams["corner_mark"])} />
        </DrivenChoice>
      </FieldRow>
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
          <FieldRow path="label.text" label="Text" issues={iss("label.text")}>
            <TextField path="label.text" value={l.text} onCommit={(v) => st.setField("label.text", v)} placeholder="#{ids}" />
          </FieldRow>
          <div className="hint-line">{"{id} {first} {last} {ids} {dict} {type}"}{showPlan && showPlan.label ? ` → “${showPlan.label.text}”` : ""}</div>
          <FieldRow path="label.height_mm" label="Height" issues={iss("label.height_mm")} title="Cap height">
            <DrivenField {...drv("label.height_mm")} value={l.height_mm > 0 ? l.height_mm : showPlan?.label ? showPlan.label.height_mm : null}
              driver="core rule: 0.12 × the rectangle's short side, 2.5 to 12 mm" unit="mm" min={0} step={0.5} bad={bad("label.height_mm")} />
          </FieldRow>
          <FieldRow path="label.side" label="Side" issues={iss("label.side")}>
            <DrivenChoice {...drv("label.side")} value={l.side} driver={`${DEFAULT} (below)`}>
              <SegmentedRow path="label.side" compact value={l.side} options={SIDES} onChange={(v) => st.setField("label.side", v as typeof l.side)} />
            </DrivenChoice>
          </FieldRow>
          <FieldRow path="label.gap_mm" label="Gap" issues={iss("label.gap_mm")}>
            <DrivenField {...drv("label.gap_mm")} value={l.gap_mm} driver={DEFAULT} unit="mm" min={0} step={0.5} bad={bad("label.gap_mm")} />
          </FieldRow>
          <FieldRow path="label.offset_mm" label="Offset" issues={iss("label.offset_mm")} title="Drag the text on the sketch to move it">
            <span className="muted" data-testid="label-offset">{l.offset_mm[0]}, {l.offset_mm[1]} mm</span>
            {(l.offset_mm[0] !== 0 || l.offset_mm[1] !== 0) && (
              <Button size="sm" variant="ghost" onClick={() => st.setLabel("offset_mm", [0, 0])}>Reset</Button>
            )}
          </FieldRow>
        </>
      )}
    </div>
  );

  return (
    <FloatingPanel title={`ArUco Extrude ${featureNumber(doc, f.id)}`} icon={<Glyph name="extrude" />} collapsed={panel.collapsed} onCollapse={st.collapse} testid="extrude-panel"
      footer={
        <>
          <Button variant="primary" onClick={st.ok} testid="panel-ok" disabled={!f.rectId}>OK</Button>
          <Button onClick={st.cancel} testid="panel-cancel">Cancel</Button>
        </>
      }>
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
      <Tabs value={panel.tab} onChange={(t) => st.setTab(t as "marker" | "label")}
        tabs={[
          { id: "marker", name: "Marker", icon: "marker", level: tabLevel(routed, "marker.") },
          { id: "label", name: "Label", icon: "label", level: tabLevel(routed, "label.") },
        ]} />
      <div className="tab-body">{panel.tab === "marker" ? markerTab : labelTab}</div>
      <div className="summary" data-testid="plan-summary">
        <div className="summary-line">{st.inscribing ? "Inscribing a rectangle…" : !f.rectId ? "Select a rectangle or a face" : showPlan ? showPlan.summary : planError ? `Plan failed: ${planError}` : "Planning…"}</div>
        <Messages path="summary" issues={kit(routed.summary)} />
      </div>
    </FloatingPanel>
  );
}
