// What Print and Export may put out: never a marker whose ids auto id
// refused (a full dictionary: its first id is someone else's), and the id
// warnings said beside the output. WHY (review finding #5, 2026-10-21): 51
// singles in DICT_4X4_50 printed 51 stickers with 50 ids, without a word.
import type { Issue } from "../core/contract";
import { featureNumber, type Doc } from "../model/doc";

/** Auto id's warnings as Print and Export show them, each naming its marker
 *  ("ArUco Extrude 51 isn't printed: DICT_4X4_50 is full ..."); refused ones first. */
export function idLines(doc: Doc, issues: Issue[], refused: readonly string[]): Issue[] {
  const name = (key: string | undefined) => {
    const f = doc.features.find((x) => x.key === key);
    return f ? `ArUco Extrude ${featureNumber(doc, f.id)}` : null;
  };
  const lines = issues.map((i) => {
    const who = name(i.key);
    const out = !!i.key && refused.includes(i.key);
    return { ...i, level: out ? "error" as const : i.level, text: who ? `${who}${out ? " has no ids, so it isn't printed" : ""}: ${i.text}` : i.text, out };
  });
  // a refusal the warnings did not explain still says so
  for (const key of refused) {
    if (!lines.some((l) => l.key === key)) lines.push({ field: "marker.first_id", level: "error", key, text: `${name(key) ?? key} has no ids, so it isn't printed`, out: true });
  }
  return [...lines.filter((l) => l.out), ...lines.filter((l) => !l.out)].map(({ out: _o, ...i }) => i);
}
