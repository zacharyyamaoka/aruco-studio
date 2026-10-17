// The command palette's ranking (audit 2026-10-17: "send" Enter ran Search
// commands). A command is found by its NAME first: the exact name, then a
// prefix of it, then a word of it starting with what was typed, then the
// typed text inside the name; cmdk's fuzzy score of the name (and, much
// lower, its group and hint) only after those.
import { defaultFilter } from "cmdk";

const norm = (s: string) => s.toLowerCase().replace(/\s+/g, " ").trim();

/** 0 (hidden) .. 1 (the exact name) for `search` against a command. */
export function rankCommand(name: string, search: string, extra: string[] = []): number {
  const q = norm(search);
  if (!q) return 1;
  const n = norm(name);
  if (n === q) return 1;
  if (n.startsWith(q)) return 0.95 - Math.min(n.length - q.length, 40) * 0.001;
  const words = n.split(/[\s:/·…,()-]+/).filter(Boolean);
  if (words.some((w) => w.startsWith(q))) return 0.85;
  if (n.includes(q)) return 0.75;
  const fuzzy = defaultFilter(n, q);
  if (fuzzy > 0) return 0.2 + 0.4 * Math.min(fuzzy, 1);
  const other = Math.max(0, ...extra.map((x) => defaultFilter(norm(x), q)));
  return other > 0 ? 0.05 * Math.min(other, 1) : 0;
}
