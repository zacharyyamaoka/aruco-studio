// What Print and Export may put out: only a document whose ids are auto id's
// answer for it, never a marker whose ids auto id refused (a full
// dictionary: its first id is someone else's), and the id warnings said
// beside the output.
// WHY (review findings #5, #6, 2026-10-21): 51 singles in DICT_4X4_50
// printed 51 stickers with 50 ids, without a word; and a copy of marker #7
// exported as #7 when Export came before auto id's answer.
import type { Issue } from "../core/contract";
import { featureNumber, idRequest, type Doc } from "../model/doc";
import { useStudio, type Studio } from "../store";

/** The document's ids are auto id's answer for it (planner.ts idSettledKey). */
export function idsReady(s: Pick<Studio, "doc" | "idSettledKey">): boolean {
  return JSON.stringify(idRequest(s.doc)) === s.idSettledKey;
}

/** The document as soon as its ids are settled (at once when they are): the
 *  revision output is made of. An edit meanwhile is waited out too. */
export function settledDoc(): Promise<Doc> {
  return new Promise((resolve) => {
    let done = false;
    let un: (() => void) | null = null;
    const check = () => {
      const s = useStudio.getState();
      if (done || !idsReady(s)) return;
      done = true;
      un?.();
      resolve(s.doc);
    };
    un = useStudio.subscribe(check);
    check();
    if (done) un();
  });
}

/** Make output of a settled revision: `build` the request from it (null:
 *  nothing to make), `run` it; when the document's request moved on while
 *  the core worked, start again on the new revision (at most `tries` times). */
export async function settledOutput<R, T>(build: (doc: Doc) => R | null, run: (req: R, doc: Doc) => Promise<T>, tries = 8): Promise<{ req: R; doc: Doc; out: T } | null> {
  for (let i = 0; ; i++) {
    const doc = await settledDoc();
    const req = build(doc);
    if (req === null) return null;
    const out = await run(req, doc);
    const now = useStudio.getState();
    if (i + 1 >= tries || (idsReady(now) && JSON.stringify(build(now.doc)) === JSON.stringify(req))) return { req, doc, out };
  }
}

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
