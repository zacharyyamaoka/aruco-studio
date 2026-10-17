// The bottom toolbar (MC-6): the tools with their keys on badges, the
// active one lit; what you type for it (80 50), what it waits for; S opens
// the command palette. The typed box takes keys (App.tsx), a paste (Ctrl+V
// of "80 50") and text from an input method (IME, insertText) through a
// hidden field of its own (lane polish, 2026-10-17).
import { ArrowUpFromLine, Circle, CircleDot, MousePointer2, Pentagon, Pill, QrCode, RectangleHorizontal, Search, SquareDot } from "lucide-react";
import { useEffect, useRef } from "react";
import type { KeyboardEvent as ReactKeyboardEvent, ReactNode } from "react";
import { Kbd, ToolButton } from "@bam/ui";
import { useStudio, TYPED_TOOLS, type ToolId } from "../store";
import { TOOLS } from "./commands";

export const TOOL_ICONS: Record<ToolId, ReactNode> = {
  select: <MousePointer2 size={16} />,
  rect: <RectangleHorizontal size={16} />,
  circle: <Circle size={16} />,
  polygon: <Pentagon size={16} />,
  slot: <Pill size={16} />,
  hole: <CircleDot size={16} />,
  rhole: <SquareDot size={16} />,
  extrude: <ArrowUpFromLine size={16} />,
  aruco: <QrCode size={16} />,
};

const ASK: Record<ToolId, string> = {
  select: "",
  rect: "drag a box, or type W H and Enter",
  circle: "drag a diameter, or type D and Enter",
  polygon: "click the points; Enter or the first point closes",
  slot: "drag the length, or type L W and Enter",
  hole: "click inside a shape, or type D and Enter (the selected shape's centre)",
  rhole: "click inside a shape, or type W H and Enter",
  extrude: "type the height, Enter (or drag the arrow in 3D)",
  aruco: "click a shape or a face (Shift+click more), then Enter",
};

/** What a paste or an input method hands the typed box, as the keys would
 *  have typed it: full-width digits, spaces and signs folded (NFKC, "−"),
 *  "×" / "X" / "*" as the "x" separator, lines and tabs as spaces; any other
 *  character dropped. "  ８０ × ５０
" -> " 80 x 50 " (addTyped drops a
 *  leading space where the box is empty or already ends in one). */
export function typedText(raw: string): string {
  return (raw || "").normalize("NFKC")
    .replace(/[−‒–—]/g, "-")
    .replace(/[×X*]/g, "x")
    .replace(/\s+/g, " ")
    .replace(/[^0-9.\- ,x]/g, "")
    .replace(/ +/g, " ");
}

const MAX_TYPED = 40;                    // the store's own cap (typeKey)

function editable(t: EventTarget | null): boolean {
  const el = t as HTMLElement | null;
  return !!el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || !!el.isContentEditable);
}

/** Add text to the typed box (paste, IME, insertText): the store's typed
 *  text plus the folded text, capped as typeKey caps it. */
function addTyped(raw: string): boolean {
  const st = useStudio.getState();
  const cur = st.typed;
  let add = typedText(raw);
  if (!cur || cur.endsWith(" ")) add = add.replace(/^ /, "");
  if (!add) return false;
  st.setTyped((cur + add).slice(0, MAX_TYPED));
  return true;
}

/** The typed box's own listeners while a typed tool is on: a paste
 *  anywhere but another field, a full-width digit key, and an input-method
 *  key (which moves focus to the hidden field so the composition lands
 *  there). */
function useTypedInput(on: boolean, sink: { current: HTMLInputElement | null }) {
  useEffect(() => {
    if (!on) return;
    const blocked = () => {
      const st = useStudio.getState();
      return st.libraryOpen || !!st.dialog || st.palette || !!document.querySelector("[data-kit-popup][data-open]");
    };
    const onPaste = (e: ClipboardEvent) => {
      if ((e.target !== sink.current && editable(e.target)) || blocked()) return;
      const text = e.clipboardData?.getData("text/plain") || e.clipboardData?.getData("text") || "";
      if (addTyped(text)) e.preventDefault();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.target === sink.current || editable(e.target) || blocked() || e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.isComposing || e.key === "Process" || e.keyCode === 229) {
        sink.current?.focus();            // the IME's text goes to the hidden field
        return;
      }
      // a full-width digit (an IME in full-width mode): App's keys take ASCII only
      if (e.key.length === 1 && e.key !== typedText(e.key) && typedText(e.key).length === 1) {
        e.preventDefault();
        addTyped(e.key);
      }
    };
    window.addEventListener("paste", onPaste);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("paste", onPaste);
      window.removeEventListener("keydown", onKey);
    };
  }, [on, sink]);
}

/** The hidden field's keys: focus is in an input, so App's key handler
 *  skips them; Enter, Esc and Backspace are the typed box's, a paste and
 *  copy stay the field's, and any other key goes back to the page (a tool
 *  key, Ctrl+Z, Tab) with the field left. */
function sinkKey(e: ReactKeyboardEvent<HTMLInputElement>) {
  const st = useStudio.getState();
  const n = e.nativeEvent;
  if (n.isComposing || e.key === "Process" || n.keyCode === 229) return;
  const ctrl = e.ctrlKey || e.metaKey;
  if (ctrl && ["v", "c", "x"].includes(e.key.toLowerCase())) return;
  if (!ctrl && !e.altKey && e.key.length === 1 && typedText(e.key).length === 1) return;   // the input event adds it
  e.preventDefault();
  if (e.key === "Enter") { void st.confirm(); return; }
  if (e.key === " ") { addTyped(" "); return; }
  if (e.key === "Backspace") { st.typeKey("Backspace"); return; }
  const el = e.currentTarget;
  el.blur();
  if (e.key === "Escape") { st.cancel(); return; }
  window.dispatchEvent(new KeyboardEvent("keydown", {
    key: e.key, code: e.code, shiftKey: e.shiftKey, ctrlKey: e.ctrlKey, metaKey: e.metaKey, altKey: e.altKey,
    bubbles: true, cancelable: true,
  }));
}

const SINK_STYLE = { position: "absolute", width: 1, height: 1, opacity: 0, border: 0, padding: 0, pointerEvents: "none" } as const;

export function BottomBar() {
  const tool = useStudio((s) => s.tool);
  const typed = useStudio((s) => s.typed);
  const picks = useStudio((s) => s.picks);
  const draft = useStudio((s) => s.draft);
  const st = useStudio.getState();
  const sink = useRef<HTMLInputElement | null>(null);
  const takesTyped = TYPED_TOOLS.includes(tool);
  useTypedInput(takesTyped, sink);
  return (
    <div className="bottombar" data-testid="bottombar">
      {(tool !== "select") && (
        <div className="tool-ask" data-testid="tool-ask">
          <b>{TOOLS.find((t) => t.tool === tool)?.name}</b>
          <span className="muted">{ASK[tool]}</span>
          {takesTyped && (
            <span className="typed" data-testid="typed" title="Type, paste (Ctrl+V) or use an input method"
              onMouseDown={(e) => { e.preventDefault(); sink.current?.focus(); }}>
              {typed || " "}<i className="caret" />
              <input ref={sink} data-testid="typed-input" aria-label="The numbers for this tool" autoComplete="off"
                spellCheck={false} inputMode="decimal" style={SINK_STYLE} defaultValue=""
                onKeyDown={sinkKey}
                onInput={(e) => {
                  const el = e.currentTarget;
                  if ((e.nativeEvent as InputEvent).isComposing) return;     // compositionend takes it
                  addTyped(el.value);
                  el.value = "";
                }}
                onCompositionEnd={(e) => {
                  const el = e.currentTarget;
                  addTyped(el.value || e.data || "");
                  el.value = "";
                }} />
            </span>
          )}
          {tool === "aruco" && <span className="picks" data-testid="picks" data-picks={picks.join(",")}>{picks.length ? picks.join(" · ") : "nothing picked"}</span>}
          {tool === "polygon" && <span className="picks" data-testid="draft-points">{draft.length} points</span>}
          <span className="keys"><Kbd keys="Enter" /> confirm <Kbd keys="Esc" /> cancel</span>
        </div>
      )}
      <div className="tools" role="toolbar" aria-label="Tools">
        {TOOLS.map((t) => (
          <ToolButton key={t.tool} icon={TOOL_ICONS[t.tool]} name={t.name} keys={t.key} active={tool === t.tool}
            testid={`tool-${t.tool}`} onClick={() => st.setTool(tool === t.tool && t.tool !== "select" ? "select" : t.tool)} />
        ))}
        <span className="tools-sep" />
        <ToolButton icon={<Search size={16} />} name="Search commands" keys="S" testid="tool-search" onClick={() => st.setPalette(true)} />
      </div>
    </div>
  );
}
