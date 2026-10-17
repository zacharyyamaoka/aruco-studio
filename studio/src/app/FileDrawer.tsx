// The File drawer (M8 §1.6): the design file's raw text, read only. The
// selection's JSON lines are lit; when the file on disk does not parse, the
// bar says where and the text shown is the last one that parsed. Editing
// stays in the editor of your choice; Reveal shows the file in Explorer.
import { useEffect, useMemo, useRef } from "react";
import { findShape } from "../model/design";
import { useStudio } from "../store";

export function FileDrawer() {
  const design = useStudio((s) => s.design);
  const spans = useStudio((s) => s.spans);
  const doc = useStudio((s) => s.doc);
  const shapeSel = useStudio((s) => s.shapeSel);
  const sel = useStudio((s) => s.sel);
  const tags = useStudio((s) => s.scene.tags);
  const st = useStudio.getState();
  const ref = useRef<HTMLPreElement>(null);
  const lines = useMemo(() => design.text.split("\n"), [design.text]);
  const lit = useMemo(() => {
    const out = new Set<number>();
    const paths: string[] = [];
    for (const k of shapeSel) { const i = findShape(doc, k); if (i) paths.push(i.path); }
    for (const t of tags) if (sel.includes(t.name) && typeof t.source?.feature === "number") paths.push(`features[${t.source.feature}]`);
    for (const p of paths) {
      const sp = spans.get(p);
      if (sp) for (let l = sp.line0; l <= sp.line1; l++) out.add(l);
    }
    return { lines: out, paths };
  }, [shapeSel, sel, tags, spans, doc]);
  useEffect(() => {
    const first = Math.min(...lit.lines);
    if (!Number.isFinite(first) || !ref.current) return;
    const el = ref.current.querySelector(`[data-line="${first}"]`) as HTMLElement | null;
    // the pre scrolls itself (scrollIntoView would move the page too)
    if (el) ref.current.scrollTop = Math.max(0, el.offsetTop - ref.current.clientHeight / 3);
  }, [lit]);
  const err = design.state === "broken" ? design.error : null;
  return (
    <div className="drawer-body file" data-testid="file-drawer">
      <div className="file-head">
        <span className="file-path" title={design.path ?? ""}>{design.path ?? "in memory: Save as… gives it a file"}</span>
        <span className={`file-state st-${design.state}`} data-state={design.state}>{design.state}</span>
        {lit.paths.length > 0 && <span className="muted" data-testid="file-lit">{lit.paths.join(", ")}</span>}
        <span className="grow" />
        <button className="btn small" disabled={!design.path} onClick={() => st.reveal()} data-testid="file-reveal">Reveal</button>
      </div>
      {err && <div className="issue lv-error" data-testid="file-error">line {err.line} col {err.col}: {err.message} (the file on disk; below is the last text that parsed)</div>}
      <pre ref={ref} className="file-text" data-testid="file-text">
        {lines.map((l, i) => (
          <div key={i} data-line={i + 1} className={`fl${lit.lines.has(i + 1) ? " lit" : ""}${err?.line === i + 1 ? " bad" : ""}`}>
            <span className="ln">{i + 1}</span>{l || " "}
          </div>
        ))}
      </pre>
    </div>
  );
}
