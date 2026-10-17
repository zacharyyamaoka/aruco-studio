// The Preset row, first (M6 a: the preset is the machine): [preset ▾]
// [library]. The list: the recent presets, then the 3D printers, then the
// sticker printers (GET /api/presets' collections). It shows the preset
// the tag's print settings equal, or "This tag (modified)". With no tag it
// is the new-tag preset. Under it, read only, the Made-by line ("Made by:
// Printed sticker · 600 dpi · Letter"), and when a PrusaSlicer profile a
// tag's preset came from has changed, the info and an Apply button
// (GET /api/prusa/stale; nothing is applied without the click).
import { Button, FieldRow, IconButton, Select, type Issue, type Opt } from "@bam/ui";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { Preset, PresetItem, SceneTag } from "../api/types";
import { madeBy, useStudio } from "../store";

const THIS = "\u0000this";

/** The preset list, grouped: Recent, then each collection. */
export function presetOptions(presets: PresetItem[], recent: string[], collections: { id: string; title: string; names: string[] }[]): Opt[] {
  const names = presets.map((p) => p.name);
  const opts: Opt[] = [];
  const icon = (p: PresetItem) => p.made_by === "sticker" ? "sticker" : p.kind === "user" ? "star" : "cube";
  for (const r of recent) {
    const p = presets.find((x) => x.name === r);
    if (p) opts.push({ value: `recent:${r}`, label: r, icon: "clock", group: "Recent" });
  }
  const placed = new Set<string>();
  for (const c of collections) {
    for (const nm of c.names) {
      const p = presets.find((x) => x.name === nm);
      if (!p || placed.has(nm)) continue;
      placed.add(nm);
      opts.push({ value: nm, label: nm, icon: icon(p), group: c.title });
    }
  }
  for (const nm of names) {
    if (placed.has(nm)) continue;
    const p = presets.find((x) => x.name === nm)!;
    opts.push({ value: nm, label: nm, icon: icon(p), group: p.made_by === "sticker" ? "Sticker printers" : "3D printers" });
  }
  return opts;
}

export function PresetRow({ tag, issues }: { tag: SceneTag | null; issues: Issue[] }) {
  const presets = useStudio((s) => s.presets);
  const recent = useStudio((s) => s.recent);
  const collections = useStudio((s) => s.presetCollections);
  const newPreset = useStudio((s) => s.newPreset);
  const [match, setMatch] = useState<string | null | undefined>(undefined);
  const key = tag ? JSON.stringify([tag.spec.settings, tag.spec.numbers, presets.length]) : "";
  useEffect(() => {
    if (!tag) return;
    let live = true;
    api.presetOf(tag.spec as any).then((r) => live && setMatch(r.matches)).catch(() => live && setMatch(null));
    return () => { live = false; };
  }, [key]);
  const st = useStudio.getState();
  const opts = presetOptions(presets, recent, collections);
  const cur = tag ? match : newPreset;
  if (tag && !match) opts.unshift({ value: THIS, label: match === undefined ? "…" : "This tag (modified)", icon: "doc" });
  const pick = (v: string | number) => {
    const name = String(v).replace(/^recent:/, "");
    if (v === THIS) return;
    if (tag) void st.applyPreset(name);
    else st.setNew("newPreset", name);
  };
  return (
    <FieldRow path="preset" label="Preset" issues={issues} className="preset-row">
      <span className="pair">
        <Select path={tag ? "preset" : "new.preset"} value={tag ? (match ?? THIS) : cur} options={opts} onChange={pick} wide />
        <IconButton icon="library" title="Preset library: 3D printers, sticker printers, PrusaSlicer's printers" onClick={() => st.setLibrary(true)} testid="library-btn" />
      </span>
    </FieldRow>
  );
}

const PAGE_WORDS: Record<string, string> = { letter: "Letter", a4: "A4", a3: "A3", a5: "A5", legal: "Legal", tabloid: "Tabloid" };

/** "Printed sticker · 600 dpi · Letter" / "3D printed · nozzle 0.6 mm · lines 0.68 mm". */
export function madeByWords(by: "print3d" | "sticker", profile: Record<string, any> | null | undefined): [string, string] {
  const p = profile ?? {};
  if (by === "sticker") {
    const bits = [p.dpi ? `${p.dpi} dpi` : "", p.page ? PAGE_WORDS[String(p.page)] ?? String(p.page) : ""].filter(Boolean);
    return ["Printed sticker", bits.join(" · ")];
  }
  const bits = [p.nozzle_mm ? `nozzle ${p.nozzle_mm} mm` : "", p.line_mm ? `lines ${p.line_mm} mm` : ""].filter(Boolean);
  return ["3D printed", bits.join(" · ")];
}

/** The Made-by line (read only: the preset decides). */
export function MadeByLine({ tag }: { tag: SceneTag | null }) {
  const presets = useStudio((s) => s.presets);
  const newPreset = useStudio((s) => s.newPreset);
  const [prof, setProf] = useState<Record<string, any> | null>(null);
  const key = tag ? JSON.stringify([tag.spec.settings, tag.spec.numbers]) : newPreset;
  useEffect(() => {
    let live = true;
    if (!tag) {
      const p: Preset | undefined = presets.find((x) => x.name === newPreset)?.preset;
      setProf((p?.profile as any) ?? null);
      return;
    }
    api.presetOf(tag.spec as any).then((r) => live && setProf(r.preset?.profile ?? null)).catch(() => live && setProf(null));
    return () => { live = false; };
  }, [key, presets.length]);
  const by: "print3d" | "sticker" = tag ? madeBy(tag) : (presets.find((x) => x.name === newPreset)?.made_by === "sticker" ? "sticker" : "print3d");
  const [words, detail] = madeByWords(by, prof);
  return (
    <FieldRow path="settings.make.by" label="Made by" title="the preset decides how a tag is made">
      <span className="ro made-by" data-testid="made-by" data-made-by={by} title={`Made by: ${words}${detail ? " · " + detail : ""}`}>
        {words}{detail && <span className="mb-detail"> · {detail}</span>}
      </span>
    </FieldRow>
  );
}

/** A changed PrusaSlicer profile under a tag's preset: the info and Apply. */
export function StaleRows({ names }: { names: string[] }) {
  const stale = useStudio((s) => s.stale);
  const st = useStudio.getState();
  const mine = stale.filter((x) => names.includes(x.tag));
  if (!mine.length) return null;
  return (
    <>
      {mine.map((x) => (
        <div key={`${x.tag}|${x.preset}`} className="stale-row" data-testid="stale" data-stale-tag={x.tag}>
          <span className="grow" title={x.text}>{names.length > 1 ? `${x.tag}: ` : ""}{x.text}</span>
          <Button size="sm" variant="primary" testid="stale-apply" onClick={async () => {
            const keep = useStudio.getState().sel;
            useStudio.setState({ sel: [x.tag] });
            await st.applyPreset(x.preset);
            useStudio.setState({ sel: keep });
            await st.loadStale();
          }}>Apply</Button>
        </div>
      ))}
    </>
  );
}
