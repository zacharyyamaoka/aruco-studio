// The design file's text, read and written the way the server does
// (scene/file.dumps_design: json.dumps(indent=1, sort_keys=True,
// ensure_ascii=False) + "\n"), so a Studio write changes only the bytes the
// action changed and Undo (a text history) restores a file byte for byte.
//
// JSON.parse loses how a number was written (Python's 80.0 and 80 are both
// 80 in JS). This parser keeps each number's literal beside its container,
// and the writer gives an unchanged number its literal back. It also keeps
// where every value sits in the text (lines), for the File drawer.

/** container -> key (or index) -> the number's literal as typed */
const LITERALS = new WeakMap<object, Map<string | number, string>>();

export interface Span { line0: number; line1: number }

export interface Parsed {
  value: any;
  /** JSON path ("sketches[0].shapes[1]") -> the lines it spans (1-based) */
  spans: Map<string, Span>;
}

export class JsonError extends Error {
  line: number;
  col: number;
  constructor(line: number, col: number, msg: string) {
    super(`line ${line} col ${col}: ${msg}`);
    this.line = line;
    this.col = col;
  }
}

const childPath = (path: string, key: string | number) =>
  typeof key === "number" ? `${path}[${key}]` : path ? `${path}.${key}` : key;

export function parse(text: string): Parsed {
  let i = 0;
  let line = 1;
  let lineStart = 0;
  const spans = new Map<string, Span>();
  const fail = (msg: string): never => { throw new JsonError(line, i - lineStart + 1, msg); };
  const ws = () => {
    for (;;) {
      const c = text.charCodeAt(i);
      if (c === 10) { i++; line++; lineStart = i; }
      else if (c === 32 || c === 9 || c === 13) i++;
      else return;
    }
  };
  const str = (): string => {
    if (text[i] !== '"') fail("expecting '\"'");
    const start = i;
    i++;
    let esc = false;
    for (; i < text.length; i++) {
      const ch = text[i];
      if (esc) { esc = false; continue; }
      if (ch === "\\") { esc = true; continue; }
      if (ch === '"') { i++; return JSON.parse(text.slice(start, i)); }
      if (ch === "\n") fail("unterminated string");
    }
    return fail("unterminated string");
  };
  const num = (): [number, string] => {
    const m = /^-?(0|[1-9]\d*)(\.\d+)?([eE][+-]?\d+)?/.exec(text.slice(i, i + 64));
    if (!m) fail("expecting a value");
    i += m![0].length;
    return [Number(m![0]), m![0]];
  };
  const value = (path: string): any => {
    ws();
    const l0 = line;
    let v: any;
    const c = text[i];
    if (c === "{") {
      i++;
      v = {};
      const lits = new Map<string | number, string>();
      ws();
      if (text[i] === "}") i++;
      else {
        for (;;) {
          ws();
          const k = str();
          ws();
          if (text[i] !== ":") fail("expecting ':'");
          i++;
          ws();
          if (text[i] === "-" || (text[i] >= "0" && text[i] <= "9")) {
            const l = line;
            const [n, raw] = num();
            v[k] = n;
            lits.set(k, raw);
            spans.set(childPath(path, k), { line0: l, line1: l });
          } else v[k] = value(childPath(path, k));
          ws();
          if (text[i] === ",") { i++; continue; }
          if (text[i] === "}") { i++; break; }
          fail("expecting ',' or '}'");
        }
      }
      if (lits.size) LITERALS.set(v, lits);
    } else if (c === "[") {
      i++;
      v = [];
      const lits = new Map<string | number, string>();
      ws();
      if (text[i] === "]") i++;
      else {
        for (let k = 0; ; k++) {
          ws();
          if (text[i] === "-" || (text[i] >= "0" && text[i] <= "9")) {
            const l = line;
            const [n, raw] = num();
            v.push(n);
            lits.set(k, raw);
            spans.set(childPath(path, k), { line0: l, line1: l });
          } else v.push(value(childPath(path, k)));
          ws();
          if (text[i] === ",") { i++; continue; }
          if (text[i] === "]") { i++; break; }
          fail("expecting ',' or ']'");
        }
      }
      if (lits.size) LITERALS.set(v, lits);
    } else if (c === '"') v = str();
    else if (text.startsWith("true", i)) { i += 4; v = true; }
    else if (text.startsWith("false", i)) { i += 5; v = false; }
    else if (text.startsWith("null", i)) { i += 4; v = null; }
    else if (c === "-" || (c >= "0" && c <= "9")) v = num()[0];
    else fail("expecting a value");
    spans.set(path, { line0: l0, line1: line });
    return v;
  };
  const v = value("");
  ws();
  if (i < text.length) fail("extra data after the document");
  return { value: v, spans };
}

/** A new number as Python writes it (an int has no ".0"; -0 is 0). */
export function numText(v: number): string {
  if (!Number.isFinite(v)) throw new Error(`not a number: ${v}`);
  if (Object.is(v, -0)) return "0";
  return String(v);
}

function numberAt(holder: object, key: string | number, v: number): string {
  const raw = LITERALS.get(holder)?.get(key);
  if (raw !== undefined && Number(raw) === v && !(Object.is(v, -0))) return raw;
  return numText(v);
}

const strText = (s: string) => JSON.stringify(s);

/** Python's sort_keys order: by code point. */
const byKey = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);

/** The text of a value: json.dumps(indent=1, sort_keys=True,
 *  ensure_ascii=False) + "\n", numbers as they were typed when unchanged. */
export function dump(v: unknown): string {
  return write(v, null, "", "") + "\n";
}

function write(v: unknown, holder: object | null, key: string | number, ind: string): string {
  if (v === null || v === undefined) return "null";
  if (typeof v === "number") return holder ? numberAt(holder, key, v) : numText(v);
  if (typeof v === "boolean") return v ? "true" : "false";
  if (typeof v === "string") return strText(v);
  const inner = ind + " ";
  if (Array.isArray(v)) {
    if (!v.length) return "[]";
    return "[\n" + v.map((x, k) => inner + write(x, v, k, inner)).join(",\n") + "\n" + ind + "]";
  }
  if (typeof v === "object") {
    const keys = Object.keys(v as object).filter((k) => (v as any)[k] !== undefined).sort(byKey);
    if (!keys.length) return "{}";
    return "{\n" + keys.map((k) => inner + strText(k) + ": " + write((v as any)[k], v as object, k, inner)).join(",\n") + "\n" + ind + "}";
  }
  throw new Error(`cannot write ${typeof v}`);
}
