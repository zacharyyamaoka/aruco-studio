// The inspector of a selected shape or hole (M8 §2.2): its place and turn,
// its size, its holes as rows, its Extrude's height, the tags on it. Enter
// commits a row (the file is written), Esc reverts it.
import { useState } from "react";
import { Field, FieldRow, IconButton, NumberField, Section } from "@bam/ui";
import { addHole, extrude, findShape, moveShapes, rotateShapes, setShape, type ShapeInfo } from "../model/design";
import { kindOf, sizeText } from "../model/shapes";
import { useStudio } from "../store";

const r3 = (v: number) => Math.round(v * 1000) / 1000;

export function ShapeInspector({ info }: { info: ShapeInfo }) {
  const st = useStudio.getState();
  const tags = useStudio((s) => s.scene.tags);
  const doc = useStudio((s) => s.doc);
  const [bad, setBad] = useState<string | null>(null);
  const k = kindOf(info.shape);
  const sh = info.shape;
  const key = info.key;
  const set = (label: string, next: any) => st.editDoc(`${key}: ${label}`, (d) => setShape(d, key, next));
  const put = (field: string, v: unknown) => {
    const next = JSON.parse(JSON.stringify(sh));
    next[field] = v;
    return set(`${field} ${JSON.stringify(v)}`, next);
  };
  const on = tags.filter((t) => t.source?.shape === (info.parent ?? key) && info.hk === null);
  const holes = info.hk === null ? (Array.isArray(sh.holes) ? sh.holes : []) : [];
  const isHole = info.hk !== null;
  return (
    <aside className="inspector" data-testid="inspector" data-shape-inspector={key}>
      <div className="insp-head">
        <b data-testid="shape-title">{isHole ? `hole ${info.hk} of ${info.parent}` : info.id ?? key}</b>
        <span className="muted">{k} · {sizeText(sh)}</span>
        <span className="grow" />
        <IconButton icon="trash" title="Delete (Del)" onClick={() => st.deleteSel()} testid="shape-delete" />
      </div>
      <Section title={isHole ? "Hole" : "Shape"} testid="shape-rows">
        <Field label="At (centre)" path="shape.at" msg={bad}>
          <span className="pair">
            <NumberField label="x" path="shape.x" value={r3(isHole ? (sh.at?.[0] ?? 0) : info.xf[0])} unit="mm" onBad={setBad}
              onCommit={(v) => isHole ? put("at", [v, sh.at?.[1] ?? 0]) : st.editDoc(`${key}: x ${v}`, (d) => moveShapes(d, [key], v - info.xf[0], 0))} />
            <NumberField label="y" path="shape.y" value={r3(isHole ? (sh.at?.[1] ?? 0) : info.xf[1])} unit="mm" onBad={setBad}
              onCommit={(v) => isHole ? put("at", [sh.at?.[0] ?? 0, v]) : st.editDoc(`${key}: y ${v}`, (d) => moveShapes(d, [key], 0, v - info.xf[1]))} />
          </span>
        </Field>
        <Field label="Turn" path="shape.rot">
          <NumberField path="shape.rot" value={r3(isHole ? (Number(sh.rot) || 0) : info.xf[2])} unit="°" onBad={setBad}
            onCommit={(v) => isHole ? put("rot", v || undefined) : st.editDoc(`${key}: turn ${v}°`, (d) => rotateShapes(d, [key], v - info.xf[2]))} />
        </Field>
        {k === "rect" && (
          <Field label="W × H" path="shape.rect">
            <span className="pair">
              <NumberField path="shape.w" value={sh.rect[0]} unit="" min={0.01} onBad={setBad} onCommit={(v) => put("rect", [v, sh.rect[1]])} />
              <span className="x">×</span>
              <NumberField path="shape.h" value={sh.rect[1]} unit="mm" min={0.01} onBad={setBad} onCommit={(v) => put("rect", [sh.rect[0], v])} />
            </span>
          </Field>
        )}
        {k === "circle" && (
          <Field label="Diameter" path="shape.circle">
            <NumberField path="shape.d" value={sh.circle} unit="mm" min={0.01} onBad={setBad} onCommit={(v) => put("circle", v)} />
          </Field>
        )}
        {k === "slot" && (
          <Field label="Length × width" path="shape.slot">
            <span className="pair">
              <NumberField path="shape.length" value={sh.slot[0]} unit="" min={0.01} onBad={setBad} onCommit={(v) => put("slot", [v, sh.slot[1]])} />
              <span className="x">×</span>
              <NumberField path="shape.width" value={sh.slot[1]} unit="mm" min={0.01} onBad={setBad} onCommit={(v) => put("slot", [sh.slot[0], v])} />
            </span>
          </Field>
        )}
        {k === "polygon" && (
          <Field label="Points" path="shape.polygon">
            <span className="ro">{sh.polygon.length} points: drag them; Alt+click an edge adds one</span>
          </Field>
        )}
        {k === "loops" && (
          <Field label="Loops" path="shape.loops"><span className="ro">{sh.loops.length} loops, as typed in the file</span></Field>
        )}
      </Section>
      {!isHole && (
        <Section title={`Holes (${holes.length})`} testid="shape-holes"
          right={<IconButton icon="plus" title="A round hole at the centre (H, or click with H)" testid="hole-add"
            onClick={() => st.editDoc(`${key}: a hole`, (d) => addHole(d, key, { circle: 5 }) !== null)} />}>
          {holes.map((h: any, i: number) => (
            <FieldRow sub key={i} path={`hole.${i}`} label={kindOf(h) === "circle" ? "⌀" : kindOf(h)} className="hole-row">
              <span className="pair" data-hole-row={i}>
                <NumberField path={`hole.${i}.x`} value={h.at?.[0] ?? 0} onBad={setBad}
                  onCommit={(v) => st.editDoc(`${key}: hole ${i} x ${v}`, (d) => setShape(d, `${key}/h${i}`, { ...h, at: [v, h.at?.[1] ?? 0] }))} />
                <NumberField path={`hole.${i}.y`} value={h.at?.[1] ?? 0} onBad={setBad}
                  onCommit={(v) => st.editDoc(`${key}: hole ${i} y ${v}`, (d) => setShape(d, `${key}/h${i}`, { ...h, at: [h.at?.[0] ?? 0, v] }))} />
                {kindOf(h) === "circle" && <NumberField path={`hole.${i}.d`} value={h.circle} unit="⌀" min={0.01} onBad={setBad}
                  onCommit={(v) => st.editDoc(`${key}: hole ${i} ⌀ ${v}`, (d) => setShape(d, `${key}/h${i}`, { ...h, circle: v }))} />}
                {kindOf(h) === "rect" && Array.isArray(h.rect) && <>
                  {/* a rectangular hole's W × H (audit 2026-10-17: only its x / y could be typed) */}
                  <NumberField path={`hole.${i}.w`} value={h.rect[0]} unit="W" min={0.01} onBad={setBad}
                    onCommit={(v) => st.editDoc(`${key}: hole ${i} W ${v}`, (d) => setShape(d, `${key}/h${i}`, { ...h, rect: [v, h.rect[1]] }))} />
                  <NumberField path={`hole.${i}.h`} value={h.rect[1]} unit="H" min={0.01} onBad={setBad}
                    onCommit={(v) => st.editDoc(`${key}: hole ${i} H ${v}`, (d) => setShape(d, `${key}/h${i}`, { ...h, rect: [h.rect[0], v] }))} />
                </>}
                <IconButton icon="close" title="Remove this hole" onClick={() => { st.setShapeSel([`${key}/h${i}`]); st.deleteSel(); }} />
              </span>
            </FieldRow>
          ))}
        </Section>
      )}
      {!isHole && (
        <Section title="Extrude" testid="shape-extrude">
          <Field label="Height" path="extrude.height">
            {info.body
              ? <NumberField path="extrude.height" value={info.body.height} unit="mm" onBad={setBad}
                  onCommit={(v) => v ? st.editDoc(`${info.body!.id}: height ${v} mm`, (d) => extrude(d, key, v) !== null) : setBad("a height other than 0")} />
              : <button className="btn small" data-testid="extrude-btn" onClick={() => st.setTool("extrude")}>Extrude… (E)</button>}
          </Field>
        </Section>
      )}
      {!isHole && (
        <Section title={`Tags on it (${on.length})`} testid="shape-tags"
          right={<button className="btn small" data-testid="aruco-btn" onClick={() => st.setTool("aruco")}>ArUco Extrude (A)</button>}>
          {on.map((t) => (
            <button key={t.name} className="link tag-link" data-tag-link={t.name} onClick={() => st.select(t.name)}>
              {t.name} <span className="muted">on {t.source?.ref}</span>
            </button>
          ))}
          {!on.length && <div className="muted pad">None yet: A, then Enter, puts a marker on it.</div>}
        </Section>
      )}
      <div className="summary lv-ok" data-testid="summary">{findShape(doc, key) ? "In the file: every change is written at once" : ""}</div>
    </aside>
  );
}
