// The ArUco Extrude panel on several features at once (batch mode: A on a
// selection naming 2 or more; store.ts PanelState.featureIds). The same
// skeleton as one feature's panel (docs/design/panel_skeleton.md, the tabs
// and rows of ./ExtrudePanel.tsx); which rows it may set comes from ONE rule,
// ../model/batch.ts batchRows. A batchable row shows the value they share,
// or "Mixed" (grey, italic) where they differ; setting it sets every
// selected feature that has the row, and ↺ (while any of them is set) makes
// it driven on them all -- each one undo step (store setFieldMany /
// resetFieldMany). The rest read "—", the reason in their tooltip. Each
// feature plans on its own through the core, as one feature does.
//
// WHY (Zach, 2026-10-21): "add the ability to do batch editing of multiple
// markers ... I want to be able to turn the triangle on on many of them".
import type { ReactNode } from "react";
import { Button, FieldRow, Glyph, NumberField, SegmentedRow, Select, Switch, Tabs, type Opt } from "@bam/ui";
import { RotateCcw } from "lucide-react";
import { MIXED, batchRows, batchSummary, type BatchRow } from "../model/batch";
import { DEFAULT_MARKER, DEFAULT_TRIM, featureRect, getFeature, type Feature } from "../model/doc";
import { boxOf, rectCorners, toScreen } from "../model/geom";
import { presetStep, stepOf, stepOptions } from "../presets/fields";
import { profileLoops } from "../sketch/model";
import { useSkin } from "../skins/skins";
import { useStudio, type Tab } from "../store";
import type { Box } from "../ui/anchor";
import { DrivenChoice, DrivenField } from "../ui/DrivenField";
import { FloatingPanel } from "../ui/FloatingPanel";
import { TextArea } from "../ui/TextArea";
import {
  CORNERS, FALLBACK_DICTS, Group, MODE_ICONS, MODES, Note, PLACEHOLDERS, PLACES, SIDES, SURFACES, TRIM_ICONS, TRIM_OPTS, TURNS,
} from "./parts";
import "./panel.css";

const DEFAULT = "default";

/** "Mixed": the selected markers' values differ. */
const Mixed = ({ path }: { path: string }) => <span className="batch-mixed" data-mixed-for={path}>Mixed</span>;
/** The same, as a grey line under a segmented row (beside it, a wide row would wrap). */
const MixedLine = ({ path }: { path: string }) => <div className="hint-line batch-mixed-line" data-mixed-for={path}>Mixed</div>;

export function BatchPanel() {
  const st = useStudio();
  const { doc, plans, panel, info } = st;
  const [skin] = useSkin();
  const features = panel.featureIds.map((id) => getFeature(doc, id)).filter((f): f is Feature => !!f);
  if (!panel.open || features.length < 2) return null;
  const fusion = skin.id === "fusion";
  const rows = batchRows(features, { plans, rect: (f) => !!featureRect(doc, f) });
  const byPath = new Map(rows.map((r) => [r.path, r]));
  const row = (p: string) => byPath.get(p);
  const isMixed = (r: BatchRow) => r.value === MIXED;
  const setRow = (r: BatchRow, v: unknown) => st.setFieldMany(r.ids, r.path, v);
  const resetRow = (r: BatchRow) => st.resetFieldMany(r.ids, r.path);
  const methods = new Set(features.map((f) => f.preset?.method ?? "inkjet"));
  const methodIcon = methods.size === 1 && methods.has("print3d") ? "print3d" : "inkjet";
  const dicts: Opt[] = (info?.dictionaries.map((d) => ({ value: d.name, label: d.name.replace("DICT_", ""), hint: `${d.capacity} ids` }))
    ?? FALLBACK_DICTS.map((d) => ({ value: d, label: d.replace("DICT_", "") })));

  /** A row a batch does not set: "—", why in its tooltip. */
  const readOnly = (path: string, label: string, icon?: string, extra?: ReactNode) => {
    const r = row(path);
    if (!r) return null;
    return (
      <FieldRow path={path} label={label} icon={icon} title={r.reason}>
        <span className="batch-ro" data-batch-ro={path} title={r.reason}>—</span>
        {extra}
      </FieldRow>
    );
  };

  /** A segmented choice for them all (driven / set, Mixed). */
  const choice = (path: string, label: string, opts: Opt[], driver: string, icon?: string, compact = true, as: (v: string | number) => unknown = (v) => v) => {
    const r = row(path);
    if (!r) return null;
    const mixed = isMixed(r);
    return (<>
      <FieldRow path={path} label={label} icon={icon}>
        <span className="batch-ctl" data-batch={path} data-mixed={mixed ? "1" : "0"}>
          <DrivenChoice path={path} driven={r.driven === true} value={mixed ? "" : (r.value as string | number)} driver={driver}
            onSet={(v) => setRow(r, as(v as string | number))} onReset={() => resetRow(r)}>
            <SegmentedRow path={path} compact={compact} value={mixed ? null : (r.value as string | number)} mixed={mixed} options={opts}
              onChange={(v) => setRow(r, as(v))} />
          </DrivenChoice>
        </span>
      </FieldRow>
      {mixed && <MixedLine path={path} />}
    </>);
  };

  /** A switch for them all. */
  const toggle = (path: string, label: string, driver: string, icon?: string) => {
    const r = row(path);
    if (!r) return null;
    const mixed = isMixed(r);
    return (
      <FieldRow path={path} label={label} icon={icon}>
        <span className="batch-ctl" data-batch={path} data-mixed={mixed ? "1" : "0"}>
          <DrivenChoice path={path} driven={r.driven === true} value={mixed ? false : !!r.value} driver={driver}
            onSet={(v) => setRow(r, v)} onReset={() => resetRow(r)}>
            <Switch path={path} value={mixed ? false : !!r.value} mixed={mixed} onChange={(v) => setRow(r, v)} />
          </DrivenChoice>
          {mixed && <Mixed path={path} />}
        </span>
      </FieldRow>
    );
  };

  /** A list for them all; Mixed is its placeholder. */
  const list = (path: string, label: string, opts: Opt[], driver: string, icon?: string, as: (v: string | number) => unknown = (v) => v) => {
    const r = row(path);
    if (!r) return null;
    const mixed = isMixed(r);
    return (
      <FieldRow path={path} label={label} icon={icon}>
        <span className="batch-ctl" data-batch={path} data-mixed={mixed ? "1" : "0"}>
          <DrivenChoice path={path} driven={r.driven === true} value={mixed ? "" : (r.value as string)} driver={driver}
            onSet={(v) => setRow(r, as(v as string))} onReset={() => resetRow(r)}>
            <Select path={path} value={mixed ? undefined : (r.value as string)} placeholder="Mixed" className={mixed ? "batch-mixed-sel" : undefined}
              options={opts} onChange={(v) => setRow(r, as(v))} />
          </DrivenChoice>
        </span>
      </FieldRow>
    );
  };

  /** A number for them all: the shared value (driven grey or set), or an empty field reading Mixed. */
  const number = (path: string, label: string, driver: string, o: { icon?: string; unit?: string; min?: number; step?: number; int?: boolean; title?: string }) => {
    const r = row(path);
    if (!r) return null;
    const mixed = isMixed(r);
    return (
      <FieldRow path={path} label={label} icon={o.icon} title={o.title}>
        <span className="batch-ctl" data-batch={path} data-mixed={mixed ? "1" : "0"}>
          {mixed ? (
            <>
              <NumberField path={path} value={null} placeholder="Mixed" className={`drv batch-mixed-num ${r.driven === true ? "driven" : "set"}`}
                unit={o.unit} min={o.min} step={o.step} int={o.int} title={`The selected markers differ (${driver} where driven). Type a value to set it on all.`}
                onCommit={(v) => setRow(r, v)} />
              {r.driven !== true && (
                <button type="button" className="kit-ib drv-reset batch-reset" data-reset={path} title={`Back to driven on all: ${driver}`}
                  aria-label={`Reset ${path} to driven`} onClick={() => resetRow(r)}>
                  <RotateCcw size={11} strokeWidth={2.2} aria-hidden="true" />
                </button>
              )}
            </>
          ) : (
            <DrivenField path={path} value={r.value as number | null} driven={r.driven === true} driver={driver} unit={o.unit} min={o.min} step={o.step} int={o.int}
              onSet={(v) => setRow(r, v)} onReset={() => resetRow(r)} />
          )}
        </span>
      </FieldRow>
    );
  };

  // the preset: one name, or Mixed; the presets dialog sets it on them all (store.setPreset)
  const presetRow = row("preset");
  const preset = presetRow && !isMixed(presetRow) ? features[0].preset : null;
  const markerTab = (
    <div data-tab-body="marker">
      <Group title="Where" />
      {readOnly("profile", "Profile", "row-square-dashed-mouse-pointer")}
      {row("holes") && (() => {
        const r = row("holes")!, mixed = isMixed(r);
        return (<>
          <FieldRow path="holes" label="Holes" title="Place the marker clear of the holes, or over them">
            <span className="batch-ctl" data-batch="holes" data-mixed={mixed ? "1" : "0"}>
              <SegmentedRow path="holes" compact value={mixed ? null : (r.value as string)} mixed={mixed}
                options={[{ value: "avoid", label: "Avoid" }, { value: "ignore", label: "Ignore" }]} onChange={(v) => setRow(r, v)} />
            </span>
          </FieldRow>
          {mixed && <MixedLine path="holes" />}
        </>);
      })()}
      <Group title="How" />
      <FieldRow path="preset" label="Preset">
        <button type="button" className="preset-pick" data-testid="panel-preset" data-method={methodIcon} onClick={() => st.openModal("presets")}
          title="How these markers are made: open the presets (a pick sets it on every selected marker)">
          <Glyph name={methodIcon} />
          <span className="preset-name">{preset ? preset.name : <Mixed path="preset" />}</span>
        </button>
      </FieldRow>
      <Group title="Marker" />
      {readOnly("marker.type", "Type", "row-grid-2x2")}
      {list("marker.dictionary", "Dictionary", dicts, `${DEFAULT} (${DEFAULT_MARKER.dictionary.replace("DICT_", "")})`, "row-book-open")}
      {readOnly("marker.first_id", "ID", "row-hash",
        <Button size="sm" onClick={() => st.openModal("reid")} testid="batch-reid" title="Number only the selected markers">Re-ID…</Button>)}
      <Group title="Size" />
      {number("marker.marker_mm", "Marker size", "fills the profile", { icon: "row-ruler", unit: "mm", min: 0.1, step: 0.5 })}
      {readOnly("marker.cols", "Columns × Rows", "row-grid-3x3")}
      {readOnly("marker.separation_mm", "Separation", "row-move-horizontal")}
      {readOnly("marker.checker_mm", "Checker", "row-ruler")}
      {readOnly("marker.origin_square", "Origin", "joint")}
      {readOnly("marker.suggest", "Suggest", "row-wand-sparkles")}
      <Group title="Orientation" />
      {choice("marker.turn", "Turn", TURNS, `${DEFAULT} (0°)`, "row-rotate-cw", true, Number)}
      {readOnly("profile.angle_deg", "Rotation", "row-rotate-ccw")}
      <Group title="Details" />
      {number("marker.quiet_modules", "Quiet zone", `${DEFAULT} (${DEFAULT_MARKER.quiet_modules} cell)`,
        { icon: "row-square-square", unit: "cells", min: 0, step: 1, title: "The white border round the marker, in cells" })}
      {readOnly("feature.key", "Key", "row-key-round")}
    </div>
  );

  const anyLabel = !!row("label.text");
  const labelTab = (
    <div data-tab-body="label">
      <Group title="Label" />
      {toggle("label.on", "On", `${DEFAULT} (off)`, "row-type")}
      {anyLabel && (() => {
        const r = row("label.text")!, mixed = isMixed(r);
        return (
          <>
            <FieldRow path="label.text" label="Text" className="tall">
              <span className="batch-ctl" data-batch="label.text" data-mixed={mixed ? "1" : "0"}>
                <TextArea path="label.text" value={mixed ? "" : String(r.value)} placeholder={mixed ? "Mixed" : "#{ids}"}
                  className={mixed ? "batch-mixed-text" : undefined} onCommit={(v) => setRow(r, v)} />
              </span>
            </FieldRow>
            <div className="hint-line" data-testid="label-placeholders">{PLACEHOLDERS} · each marker fills in its own</div>
          </>
        );
      })()}
      {choice("label.place", "Place", PLACES, `${DEFAULT} (on marker)`, "row-map-pin")}
      {choice("label.surface", "Surface", SURFACES, `${DEFAULT} (black)`)}
      {choice("label.side", "Side", SIDES, `${DEFAULT} (below)`)}
      {number("label.height_mm", "Height", "core rule: 0.12 × the rectangle's short side, 2.5 to 12 mm",
        { icon: "row-a-large-small", unit: "mm", min: 0, step: 0.5, title: "Cap height" })}
      {number("label.gap_mm", "Gap", DEFAULT, { unit: "mm", min: 0, step: 0.5 })}
      {readOnly("label.offset_mm", "Offset X", "row-move-horizontal")}
      {row("label.offset_mm") && <FieldRow path="label.offset_mm.y" label="Offset Y" icon="row-move-vertical" title={row("label.offset_mm")!.reason}>
        <span className="batch-ro" data-batch-ro="label.offset_mm.y" title={row("label.offset_mm")!.reason}>—</span>
      </FieldRow>}
      <Group title="Corner mark" />
      {choice("marker.corner_mark", "Corner mark", CORNERS, `${DEFAULT} (none)`, "row-triangle-right")}
    </div>
  );

  // the size step's choices: the first selected preset's (they are all one kind, else the row is read-only)
  const stepRow = row("marker.size_step");
  const firstPreset = features.find((f) => f.preset)?.preset ?? null;
  const stepNow = stepRow && !isMixed(stepRow) && stepRow.value ? stepOf(String(stepRow.value)) : firstPreset ? presetStep(firstPreset) : null;
  const makeTab = (
    <div data-tab-body="make">
      <Group title="Size & cut" />
      {stepRow && (stepRow.editable && stepNow
        ? list("marker.size_step", "Size step", stepOptions(stepNow, firstPreset), "the preset", "row-grip", (k) => stepOf(String(k)))
        : readOnly("marker.size_step", "Size step", "row-grip"))}
      {choice("trim", "Trim", fusion ? TRIM_ICONS : TRIM_OPTS, `${DEFAULT} (${DEFAULT_TRIM})`, "row-scissors")}
      <Group title="Heights" />
      {choice("extrude.mode", "Extrude", fusion ? MODE_ICONS : MODES, "auto: black only on a reference face, both in open space", "row-layers-2")}
      {number("extrude.white_mm", "White height", "the preset: whole layers", { icon: "row-arrow-up-from-line", unit: "mm", min: 0, step: 0.1 })}
      {number("extrude.black_mm", "Black height", "the preset: whole layers", { icon: "row-arrow-up-from-line", unit: "mm", min: 0, step: 0.1 })}
      {row("extrude.black_mm") && <Note testid="black-from">from the white's outer face</Note>}
      {number("extrude.paper_mm", "Paper thickness", "the preset's thickness", { icon: "row-arrow-up-from-line", unit: "mm", min: 0, step: 0.01 })}
      <Group title="Outward side" />
      {toggle("marker.flip", "Flip", `${DEFAULT} (off)`, "row-flip-vertical")}
    </div>
  );

  // what the panel opens beside: every selected marker's box, on screen; the other markers' it keeps clear of
  const screenBox = (g: Feature): Box | null => {
    const p = plans[g.id];
    const pr = g.profile ? profileLoops(doc.shapes, g.profile) : null;
    if (!pr) return null;
    const pts = p ? [...(p.fit_rect ? rectCorners(p.fit_rect) : []), ...p.outer, ...(p.label?.box ?? [])] : pr.loops[0];
    return boxOf(pts.map((q) => toScreen(st.camera, st.view.w, st.view.h, q)));
  };
  const boxes = features.map(screenBox).filter((b): b is Box => !!b);
  const anchor = boxes.length ? boxOf(boxes.flatMap((b) => [[b.x0, b.y0], [b.x1, b.y1]] as [number, number][])) : null;
  const others = doc.features.filter((g) => !panel.featureIds.includes(g.id)).map(screenBox).filter((b): b is Box => !!b);

  const body: Record<Tab, ReactNode> = { make: makeTab, marker: markerTab, label: labelTab };
  const title = (
    <><span className="xp-title-edit">Edit </span>ArUco Extrude<span className="xp-title-batch" data-testid="batch-title"> · {features.length} markers</span></>
  );
  return (
    <FloatingPanel title={title} icon={<Glyph name="extrude" />} collapsed={panel.collapsed} onCollapse={st.collapse} testid="extrude-panel"
      anchor={anchor} anchorKey={`batch:${panel.featureIds.join(",")}`} avoid={others} width={320} className="xpanel batch"
      footer={
        <>
          <div className="summary" data-testid="plan-summary">
            <div className="summary-line" data-testid="batch-summary">{batchSummary(features, plans)}</div>
          </div>
          <div className="xp-actions">
            <Button variant="primary" onClick={st.ok} testid="panel-ok">OK</Button>
            <Button onClick={st.cancel} testid="panel-cancel">Cancel</Button>
          </div>
        </>
      }>
      <Tabs value={panel.tab} onChange={(t) => st.setTab(t as Tab)}
        tabs={[
          { id: "marker", name: "Marker", icon: "tab-marker" },
          { id: "label", name: "Label", icon: "tab-label" },
          { id: "make", name: "Make", icon: `tab-${methodIcon}` },
        ]} />
      <div className="tab-body">{body[panel.tab] ?? markerTab}</div>
    </FloatingPanel>
  );
}
