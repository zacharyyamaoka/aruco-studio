// One scene tag on the 2D canvas, drawn from its TagPlan only: the target's
// outline, the plan's top view (what prints, seen from above), every layer
// as an outline path (data-layer), the guides, the OpenCV frame's axes.
import { memo } from "react";
import type { SceneTag } from "../api/types";
import { boxOf, layerD, loopD, loopsD, poseOf, rectLoop, svgMatrix, targetLoops, topD } from "../model/geom";
import type { Show } from "../store";

const AXIS_FRACTION = 0.42;

function axes(m: number[], len: number) {
  const o = [m[3], m[7]];
  return (
    <g data-guide="axes" className="axes">
      <line data-axis="x" x1={o[0]} y1={o[1]} x2={o[0] + m[0] * len} y2={o[1] + m[4] * len} className="ax-x" />
      <line data-axis="y" x1={o[0]} y1={o[1]} x2={o[0] + m[1] * len} y2={o[1] + m[5] * len} className="ax-y" />
      <circle cx={o[0]} cy={o[1]} r={len * 0.08} className={m[10] < 0 ? "ax-z-in" : "ax-z-out"} />
    </g>
  );
}

/** Where a selected tag's label can be grabbed: each label part's box (the
 *  plan's label parts, or the refused preview's box). */
function labelHits(p: NonNullable<SceneTag["plan"]>): number[][] {
  const parts = ((p.label as any)?.parts ?? []) as { rect: number[] }[];
  if (parts.length) return parts.map((x) => x.rect);
  const prev = (p.guides?.label_preview ?? []) as unknown as [number, number][][];
  const b = boxOf(prev.flat());
  return b ? [[b.x0, b.y0, b.x1, b.y1]] : [];
}

export const TagSvg = memo(function TagSvg({ tag, show, selected, labelShift }: { tag: SceneTag; show: Show; selected: boolean; labelShift?: [number, number] }) {
  const p = tag.plan;
  const pose = poseOf(tag.x_mm, tag.y_mm, tag.rotation_deg);
  const t = tag.spec.target;
  const tl = targetLoops(t);
  const marker = (p?.marker as any) || null;
  const markerMm = marker ? Number(marker.marker_length_m || 0) * 1000 : 10;
  const g = p?.guides;
  const labelOn = Boolean((tag.spec.settings.label as any)?.on);
  return (
    <g data-tag={tag.name} data-uid={tag.uid} data-ok={p?.ok ? "1" : "0"} data-locked={tag.locked ? "1" : "0"}
      transform={svgMatrix(pose)} className={`tag${selected ? " sel" : ""}${tag.locked ? " locked" : ""}`}>
      <path data-layer="target" className={t.has_body ? "target body" : "target free"} fillRule="evenodd" d={loopsD(tl)} />
      {p && p.ok && p.frames && (
        <g data-frame="pattern" transform={svgMatrix(p.frames.pattern_in_target)}>
          <g data-view="top">
            {p.top?.body && <path data-top="body" className="top-body" fillRule="evenodd" d={topD(p.top, "body")} />}
            {p.top?.white && <path data-top="white" className="top-white" fillRule="evenodd" d={topD(p.top, "white")} />}
            {p.top?.black && <path data-top="black" className="top-black" fillRule="evenodd" d={topD(p.top, "black")} />}
          </g>
          <g data-view="layers" className={show.outlines ? "layers on" : "layers"}>
            {p.layers.map((L, i) => (
              <path key={i} data-layer={L.name} data-part={L.part} data-op={L.op} data-colour={L.colour}
                data-label-drag={L.name.startsWith("label") && selected ? "1" : undefined}
                data-z={`${L.z[0]},${L.z[1]}`} className={`layer op-${L.op} c-${L.colour}${L.step === "sub" ? " sub" : ""}`}
                fillRule="evenodd" d={layerD(L)} />
            ))}
          </g>
          {g && (
            <g data-view="guides">
              {show.quiet && <path data-guide="quiet_ring" className="g-quiet" d={loopD(rectLoop(g.quiet_ring))} />}
              {show.quiet && labelOn && g.clear_preferred && <path data-guide="clear_preferred" className="g-clear" d={loopD(rectLoop(g.clear_preferred))} />}
              {(g.keepouts || []).map((k, i) => <path key={`k${i}`} data-guide="keepout" className="g-keepout" d={loopD(k as any)} />)}
              {(g.label_preview || []).length > 0 && (
                <path data-layer="label_preview" data-state="refused" className="g-refused" fillRule="nonzero" data-label-drag={selected ? "1" : undefined}
                  d={(g.label_preview || []).map((b) => loopD(b as any)).join("")} />
              )}
              {g.trim && (g.trim as any).outline && <path data-guide="trim" className="g-trim" d={loopD(rectLoop((g.trim as any).outline))} />}
            </g>
          )}
          {selected && labelHits(p).map((r, i) => (
            <path key={`h${i}`} data-label-hit={i} data-label-drag="1" className="label-hit" d={loopD(rectLoop(r))} />
          ))}
          {show.axes && axes(p.frames.opencv, Math.max(2, markerMm * AXIS_FRACTION))}
          {labelShift && (
            <g data-ghost="label" transform={`translate(${labelShift[0]} ${labelShift[1]})`} className="label-ghost">
              {p.layers.filter((L) => L.name.startsWith("label")).map((L, i) => <path key={i} d={layerD(L)} fillRule="evenodd" />)}
              {(g?.label_preview || []).map((b, i) => <path key={`p${i}`} d={loopD(b as any)} />)}
            </g>
          )}
        </g>
      )}
      {p && !p.ok && <path data-state="error" className="g-error" d={loopsD(tl)} />}
    </g>
  );
});
