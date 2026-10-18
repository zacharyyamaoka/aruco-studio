// The ArUco Extrude panel (Fusion's feature dialog): the selection rows
// (Profile, Rectangle), the Preset first, then Marker | Label. Every row
// shows its own issues from plan().warnings under it. Manual values always
// go through; the plan flags what does not fit, it never refuses.
import { FieldRow, Glyph, Messages, NumberField, SegmentedRow, Select, Switch, Tabs, TextField, Button, type Issue as KitIssue, type Opt } from "@bam/ui";
import { X } from "lucide-react";
import type { Issue, MarkerParams } from "../core/contract";
import { idRange } from "../model/doc";
import { samePreset, myPresets } from "../presets/local";
import { useStudio } from "../store";
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

export function ExtrudePanel() {
  const st = useStudio();
  const { doc, plan, panel, suggestions, info, builtins } = st;
  const f = doc.feature;
  if (!panel.open || !f) return null;
  const m = f.marker, l = f.label;
  const refFace = !!f.profile;
  const shown = shownRows(m, l.on, refFace);
  const routed = routeIssues(plan && f.rectId ? plan.warnings : [], shown);
  const iss = (p: string) => kit(routed[p]);
  const library = [...builtins, ...myPresets()].find((p) => p.id === doc.preset?.id);
  const modified = !!doc.preset && !!library && !samePreset(library, doc.preset);
  const dicts: Opt[] = (info?.dictionaries.map((d) => ({ value: d.name, label: d.name.replace("DICT_", ""), hint: `${d.capacity} ids` }))
    ?? FALLBACK_DICTS.map((d) => ({ value: d, label: d.replace("DICT_", "") })));
  const set = <K extends keyof MarkerParams>(k: K, v: MarkerParams[K]) => st.setMarker(k, v);
  const showPlan = plan && f.rectId;
  const profileHasHoles = !!f.profile?.holes.length;

  const markerTab = (
    <div data-tab-body="marker">
      <FieldRow path="marker.type" label="Type" issues={iss("marker.type")}>
        <SegmentedRow path="marker.type" value={m.type} options={TYPES} onChange={(v) => set("type", v as MarkerParams["type"])} />
      </FieldRow>
      <FieldRow path="marker.dictionary" label="Dictionary" issues={iss("marker.dictionary")}>
        <Select path="marker.dictionary" value={m.dictionary} options={dicts} onChange={(v) => set("dictionary", String(v))} />
      </FieldRow>
      <FieldRow path="marker.first_id" label={m.type === "single" ? "ID" : "First ID"} issues={iss("marker.first_id")}>
        <NumberField path="marker.first_id" value={m.first_id} int min={0} onCommit={(v) => set("first_id", v)} />
        <span className="range" data-testid="id-range">{idRange(m, showPlan ? plan.ids : undefined)}</span>
      </FieldRow>
      <FieldRow path="marker.marker_mm" label="Marker" issues={iss("marker.marker_mm")}>
        <NumberField path="marker.marker_mm" value={m.auto && showPlan ? plan.marker_mm : m.marker_mm} unit="mm" min={0.1} step={0.5}
          onCommit={(v) => set("marker_mm", v)} />
        <Switch path="marker.auto" value={m.auto} label="Auto" title="Auto: fill the rectangle" onChange={(v) => set("auto", v)} />
      </FieldRow>
      {m.type === "charuco" && (
        <FieldRow path="marker.checker_mm" label="Checker" issues={iss("marker.checker_mm")}>
          <NumberField path="marker.checker_mm" value={m.auto && showPlan ? plan.checker_mm : m.checker_mm} unit="mm" min={0} step={0.5}
            placeholder={showPlan ? String(plan.checker_mm) : "auto"} onCommit={(v) => set("checker_mm", v)} />
        </FieldRow>
      )}
      {m.type === "grid" && (
        <FieldRow path="marker.separation_mm" label="Separation" issues={iss("marker.separation_mm")}
          title="The gap between markers; 0 = the core's rule">
          <NumberField path="marker.separation_mm" value={m.separation_mm || null} unit="mm" min={0} step={0.5}
            placeholder={showPlan ? `${plan.separation_mm} (rule)` : "rule"} onCommit={(v) => set("separation_mm", v)} />
        </FieldRow>
      )}
      {m.type !== "single" && (
        <FieldRow path="marker.cols" label="Columns × Rows" issues={iss("marker.cols")}>
          <NumberField path="marker.cols" value={m.cols} int min={1} max={50} onCommit={(v) => set("cols", v)} />
          <span className="times">×</span>
          <NumberField path="marker.rows" value={m.rows} int min={1} max={50} onCommit={(v) => set("rows", v)} />
        </FieldRow>
      )}
      <div className="row kit-field suggest" data-row="marker.suggest">
        <div className="row-main kit-row"><label className="row-label"><span className="row-text">Suggest</span></label>
          <div className="row-ctl muted">{suggestions.length ? "pick one: Auto turns off" : f.rectId ? "…" : "needs a rectangle"}</div></div>
        <ul className="suggest-list" data-testid="suggestions">
          {suggestions.map((s, i) => {
            const now = !m.auto && s.params.cols === m.cols && s.params.rows === m.rows && Math.abs(s.params.marker_mm - m.marker_mm) < 1e-6;
            return (
              <li key={i}>
                <button type="button" className={`sugg${now ? " on" : ""}`} data-testid="suggestion" data-label={s.label} onClick={() => st.pick(s)}>
                  <span className="sugg-label">{s.label}</span><span className="sugg-reason">{s.reason}</span>
                </button>
              </li>
            );
          })}
        </ul>
        <Messages path="marker.suggest" issues={iss("marker.suggest")} />
      </div>
      <FieldRow path="marker.turn" label="Turn" issues={iss("marker.turn")}>
        <SegmentedRow path="marker.turn" compact value={m.turn} options={TURNS} onChange={(v) => set("turn", Number(v) as MarkerParams["turn"])} />
      </FieldRow>
      {!refFace && (
        <FieldRow path="marker.flip" label="Flip" issues={iss("marker.flip")} title="Mirror: no reference face sets which side is up">
          <Switch path="marker.flip" value={m.flip} onChange={(v) => set("flip", v)} />
        </FieldRow>
      )}
      <FieldRow path="marker.corner_mark" label="Corner mark" issues={iss("marker.corner_mark")}>
        <SegmentedRow path="marker.corner_mark" value={m.corner_mark} options={CORNERS} onChange={(v) => set("corner_mark", v as MarkerParams["corner_mark"])} />
      </FieldRow>
    </div>
  );

  const labelTab = (
    <div data-tab-body="label">
      <FieldRow path="label.on" label="On" issues={iss("label.on")}>
        <Switch path="label.on" value={l.on} onChange={(v) => st.setLabel("on", v)} />
      </FieldRow>
      {l.on && (
        <>
          <FieldRow path="label.text" label="Text" issues={iss("label.text")}>
            <TextField path="label.text" value={l.text} onCommit={(v) => st.setLabel("text", v)} placeholder="#{ids}" />
          </FieldRow>
          <div className="hint-line">{"{id} {first} {last} {ids} {dict} {type}"}{showPlan && plan.label ? ` → “${plan.label.text}”` : ""}</div>
          <FieldRow path="label.height_mm" label="Height" issues={iss("label.height_mm")} title="Cap height; 0 = from the rectangle">
            <NumberField path="label.height_mm" value={l.height_mm || null} unit="mm" min={0} step={0.5}
              placeholder={showPlan && plan.label ? `${plan.label.height_mm} (auto)` : "auto"} onCommit={(v) => st.setLabel("height_mm", v)} />
          </FieldRow>
          <FieldRow path="label.side" label="Side" issues={iss("label.side")}>
            <SegmentedRow path="label.side" compact value={l.side} options={SIDES} onChange={(v) => st.setLabel("side", v as typeof l.side)} />
          </FieldRow>
          <FieldRow path="label.gap_mm" label="Gap" issues={iss("label.gap_mm")}>
            <NumberField path="label.gap_mm" value={l.gap_mm} unit="mm" min={0} step={0.5} onCommit={(v) => st.setLabel("gap_mm", v)} />
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
    <FloatingPanel title="ArUco Extrude" icon={<Glyph name="extrude" />} collapsed={panel.collapsed} onCollapse={st.collapse} testid="extrude-panel"
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
        <div className="summary-line">{st.inscribing ? "Inscribing a rectangle…" : !f.rectId ? "Select a rectangle or a face" : showPlan ? plan.summary : st.planError ? `Plan failed: ${st.planError}` : "Planning…"}</div>
        <Messages path="summary" issues={kit(routed.summary)} />
      </div>
    </FloatingPanel>
  );
}
