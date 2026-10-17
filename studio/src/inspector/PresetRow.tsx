// The Preset row: [preset ▾][library] (REF aruco_extrude_ui._make_preset_row).
// The list: the recent presets first, then every preset; it shows the one
// the tag's print settings equal, or "This tag (modified)".
import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { SceneTag } from "../api/types";
import { useStudio } from "../store";
import { Dropdown, IconButton, type Opt } from "../ui/controls";

export function PresetRow({ tag }: { tag: SceneTag }) {
  const presets = useStudio((s) => s.presets);
  const recent = useStudio((s) => s.recent);
  const [match, setMatch] = useState<string | null | undefined>(undefined);
  const key = JSON.stringify([tag.spec.settings, tag.spec.numbers, presets.length]);
  useEffect(() => {
    let live = true;
    api.presetOf(tag.spec as any).then((r) => live && setMatch(r.matches)).catch(() => live && setMatch(null));
    return () => { live = false; };
  }, [key]);
  const st = useStudio.getState();
  const names = presets.map((p) => p.name);
  const order = [...recent.filter((r) => names.includes(r)), ...names.filter((n) => !recent.includes(n))];
  const opts: Opt[] = order.map((n) => {
    const p = presets.find((x) => x.name === n)!;
    return { value: n, label: n, icon: recent.includes(n) ? "clock" : p.kind === "user" ? "star" : "cube" };
  });
  const THIS = "\u0000this";
  if (!match) opts.unshift({ value: THIS, label: match === undefined ? "…" : "This tag (modified)", icon: "doc" });
  return (
    <div className="row preset-row" data-row="preset">
      <div className="row-main">
        <label className="row-label">Preset</label>
        <div className="row-ctl">
          <span className="pair">
            <Dropdown path="preset" value={match ?? THIS} options={opts} onChange={(v) => v !== THIS && st.applyPreset(String(v))} />
            <IconButton icon="library" title="Preset library: browse, make, edit and import print presets" onClick={() => st.setLibrary(true)} testid="library-btn" />
          </span>
        </div>
      </div>
    </div>
  );
}
