// The target editor: the Studio's stand-in for the face Fusion clicks. Pick
// a target from /api/targets (a box, a disc, REF's ten gallery faces) or
// type a box / disc, a thickness (0 = no body under it) and round holes. The
// server makes the outline (POST /api/target); the app never does.
import { useState } from "react";
import { api } from "../api/client";
import type { Issue, SceneTag } from "../api/types";
import { useStudio } from "../store";
import { Dropdown, IconButton, NumberInput, type Opt } from "../ui/controls";

type Hole = [number, number, number];
interface Recipe { shape: "box" | "disc" | "face"; key?: string; w: number; h: number; d: number; holes: Hole[] }

// the holes typed in this session, per tag (the Target keeps them only as loops)
const typed: Record<string, Recipe> = {};

function recipeOf(tag: SceneTag, palette: { key: string; title: string }[]): Recipe {
  const t = tag.spec.target;
  if (typed[tag.uid]) return typed[tag.uid];
  const hit = palette.find((p) => p.title === t.name);
  if (hit) return { shape: "face", key: hit.key, w: t.w_mm, h: t.h_mm, d: t.w_mm, holes: [] };
  if ((t.name || "").startsWith("Disc")) return { shape: "disc", w: t.w_mm, h: t.h_mm, d: Math.round(t.w_mm * 100) / 100, holes: [] };
  return { shape: "box", w: t.w_mm, h: t.h_mm, d: t.w_mm, holes: [] };
}

export function TargetEditor({ tag, issues }: { tag: SceneTag; issues: Issue[] }) {
  const palette = useStudio((s) => s.targets);
  const [bad, setBad] = useState<string | null>(null);
  const st = useStudio.getState();
  const t = tag.spec.target;
  const r = recipeOf(tag, palette);
  const thick = t.body_mm ? Math.round((t.body_mm.z1 - t.body_mm.z0) * 1000) / 1000 : 0;
  const custom = r.shape !== "face" ? r.shape : r.key!;
  const opts: Opt[] = [
    { value: "box", label: "Box (typed)", icon: "target" },
    { value: "disc", label: "Disc (typed)", icon: "target" },
    ...palette.map((p) => ({ value: p.key, label: p.title, icon: "target" })),
  ];
  // every change starts from the newest recipe (two quick edits must not
  // undo each other), and the server makes the outline inside the store's
  // queue, so the next change waits for it
  const apply = async (change: Partial<Recipe> | ((r: Recipe) => Recipe), thickness: number) => {
    const cur = typed[tag.uid] ?? r;
    const next = typeof change === "function" ? change(cur) : { ...cur, ...change };
    typed[tag.uid] = next;
    setBad(null);
    await st.editTarget(async () => {
      try {
        const tgt = await api.makeTarget({
          shape: next.shape, key: next.key, w_mm: next.w, h_mm: next.h, r_mm: next.d / 2, holes: next.holes, thickness_mm: thickness,
        });
        return { ...tgt, kind: t.kind, z_sign: t.z_sign } as any;
      } catch (e) {
        setBad(String((e as Error).message));
        throw e;
      }
    });
  };
  return (
    <div className="target-ed" data-testid="target-editor">
      <div className="row" data-row="target">
        <div className="row-main">
          <label className="row-label">Target</label>
          <div className="row-ctl">
            <Dropdown path="target" value={custom} options={opts} wide
              onChange={(v) => {
                const k = String(v);
                if (k === "box") apply({ shape: "box", key: undefined }, thick);
                else if (k === "disc") apply((c) => ({ ...c, shape: "disc", key: undefined, d: Math.max(c.w, c.h) }), thick);
                else apply({ shape: "face", key: k }, thick);
              }} />
          </div>
        </div>
      </div>
      <div className="row" data-row="target.size">
        <div className="row-main">
          <label className="row-label">{r.shape === "disc" ? "Diameter" : r.shape === "box" ? "W × H" : "Size"}</label>
          <div className="row-ctl">
            {r.shape === "box" && (
              <span className="pair">
                <NumberInput path="target.w_mm" value={t.w_mm} unit="" onBad={setBad} onCommit={(v) => apply({ w: v }, thick)} />
                <span className="x">×</span>
                <NumberInput path="target.h_mm" value={t.h_mm} unit="mm" onBad={setBad} onCommit={(v) => apply({ h: v }, thick)} />
              </span>
            )}
            {r.shape === "disc" && <NumberInput path="target.d_mm" value={r.d} unit="mm" onBad={setBad} onCommit={(v) => apply({ d: v }, thick)} />}
            {r.shape === "face" && <span className="ro">{t.w_mm.toFixed(1)} × {t.h_mm.toFixed(1)} mm</span>}
          </div>
        </div>
      </div>
      <div className="row" data-row="target.thickness">
        <div className="row-main">
          <label className="row-label" title="the body under the face: 0 = nothing under it">Thickness</label>
          <div className="row-ctl">
            <NumberInput path="target.thickness" value={thick} unit="mm" onBad={setBad} onCommit={(v) => apply({}, Math.max(0, v))} />
          </div>
        </div>
      </div>
      <div className="row" data-row="target.holes">
        <div className="row-main">
          <label className="row-label">Holes</label>
          <div className="row-ctl">
            <span className="muted">{Math.max(0, (t.loops_mm?.length ?? 1) - 1)}</span>
            <IconButton icon="plus" title="Add a round hole (x, y, diameter)" testid="hole-add"
              onClick={() => apply((c) => ({ ...c, holes: [...c.holes, [0, 0, 5]] }), thick)} />
          </div>
        </div>
        {r.holes.map((hh, i) => (
          <div className="row-main sub" key={i} data-hole={i}>
            <span className="row-label">⌀ at</span>
            <span className="row-ctl pair">
              <NumberInput path={`hole.${i}.x`} value={hh[0]} onBad={setBad} onCommit={(v) => apply((c) => ({ ...c, holes: c.holes.map((x, j) => j === i ? [v, x[1], x[2]] : x) }), thick)} />
              <NumberInput path={`hole.${i}.y`} value={hh[1]} onBad={setBad} onCommit={(v) => apply((c) => ({ ...c, holes: c.holes.map((x, j) => j === i ? [x[0], v, x[2]] : x) }), thick)} />
              <NumberInput path={`hole.${i}.d`} value={hh[2]} unit="⌀" onBad={setBad} onCommit={(v) => apply((c) => ({ ...c, holes: c.holes.map((x, j) => j === i ? [x[0], x[1], v] : x) }), thick)} />
              <IconButton icon="close" title="Remove this hole" onClick={() => apply((c) => ({ ...c, holes: c.holes.filter((_x, j) => j !== i) }), thick)} />
            </span>
          </div>
        ))}
      </div>
      {(issues.length > 0 || bad) && (
        <div className="msgs" data-issues-for="target">
          {bad && <div className="issue lv-error" data-level="error">{bad}</div>}
          {issues.map((i, k) => <div key={k} className={`issue lv-${i.level}`} data-level={i.level} data-field={i.field}>{i.text}</div>)}
        </div>
      )}
    </div>
  );
}
