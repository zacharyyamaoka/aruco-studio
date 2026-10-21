// Calibrate actual size: hold a bank card (ISO/IEC 7810 ID-1, 85.60 x 53.98
// mm) against the screen and size the drawn one to it, or measure a line with
// a ruler and type its length. Either gives this screen's CSS px per mm,
// kept per screen in this browser (./scale.ts); Actual size follows it at
// once when it is showing (./zoom.ts followScale).
import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { Button, Dialog } from "@bam/ui";
import { useStudio } from "../store";
import "./zoom.css";
import { CARD_MM, MAX_PX_PER_MM, MIN_PX_PER_MM, clampScale, fromCard, fromRuler, perInchOf, useScale } from "./scale";

/** The ruler line's longest (CSS px): long enough to read to 0.5 % on a ruler. */
const LINE_MAX = 400;
/** One −/+ press: 0.2 % (0.17 mm on the card's long side). */
const STEP = 0.002;
const fmt1 = (v: number) => (Math.round(v * 10) / 10).toFixed(1);

export function CalibrateDialog() {
  const open = useScale((s) => s.calibrating);
  const scale = useScale((s) => s.scale);
  const [draft, setDraft] = useState(scale.pxPerMm);
  const [by, setBy] = useState<"card" | "ruler">("card");
  /** the ruler's box while it is being typed in (else it shows the draft's length) */
  const [typed, setTyped] = useState<string | null>(null);
  const [avail, setAvail] = useState(560);
  /** the scale the dialog opened on: the card's orientation is chosen for it, once */
  const [start, setStart] = useState(scale.pxPerMm);
  const drag = useRef<{ x: number; w: number } | null>(null);
  const ro = useRef<ResizeObserver | null>(null);

  // each opening starts from this screen's scale
  useEffect(() => {
    if (!open) return;
    const now = useScale.getState().scale.pxPerMm;
    setDraft(now);
    setStart(now);
    setBy("card");
    setTyped(null);
  }, [open]);
  useEffect(() => () => ro.current?.disconnect(), []);

  const close = () => useScale.getState().setCalibrating(false);
  const put = (v: number, how: "card" | "ruler") => { setDraft(clampScale(v)); setBy(how); };
  // the card on its side when its long side would not fit (a phone); chosen
  // for the scale it opened on, so a drag never turns it over under the hand
  const landscape = CARD_MM.w * start * 1.15 <= avail;
  const side = landscape ? CARD_MM.w : CARD_MM.h;
  const cw = side * draft, ch = (landscape ? CARD_MM.h : CARD_MM.w) * draft;
  const line = Math.max(120, Math.min(LINE_MAX, avail - 8));
  const measured = typed ?? fmt1(line / draft);

  const onGrip = (e: ReactPointerEvent) => {
    e.preventDefault();
    (e.currentTarget as Element).setPointerCapture?.(e.pointerId);
    drag.current = { x: e.clientX, w: cw };
  };
  const onGripMove = (e: ReactPointerEvent) => {
    if (!drag.current) return;
    put(fromCard(drag.current.w + (e.clientX - drag.current.x), side), "card");
  };
  const onGripUp = () => { drag.current = null; };
  const onRuler = (text: string) => {
    setTyped(text);
    const mm = Number(text.trim().replace(",", "."));
    if (Number.isFinite(mm) && mm > 0) put(fromRuler(line, mm), "ruler");
  };
  const save = () => {
    const kept = useScale.getState().calibrate(draft, by);
    close();
    if (!kept) useStudio.getState().say("This browser won't store the calibration: it holds until you reload.");
  };
  const forget = () => { useScale.getState().forget(); close(); };
  const bind = (el: HTMLDivElement | null) => {
    ro.current?.disconnect();
    if (!el) return;
    // its content box: the padding (16 px a side) is not room for the card
    const measure = () => setAvail(Math.max(200, el.clientWidth - 32));
    ro.current = new ResizeObserver(measure);
    ro.current.observe(el);
    measure();
  };

  const s = scale.screen;
  const when = scale.cal?.at ? new Date(scale.cal.at).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "";
  return (
    <Dialog open={open} onClose={close} title="Calibrate actual size" testid="calibrate-dialog" width="min(760px, calc(100vw - 16px))" className="cal-dialog"
      footer={<>
        {scale.calibrated && <Button testid="cal-forget" onClick={forget} title="Forget this screen's calibration: back to the estimate">Reset to estimate</Button>}
        <span className="grow" />
        <Button testid="cal-cancel" onClick={close}>Cancel</Button>
        <Button testid="cal-save" variant="primary" onClick={save}>Save</Button>
      </>}>
      <div className="cal-body" ref={bind}>
        <p className="cal-how">
          Hold a bank card (any ID card: 85.60 × 53.98 mm) flat against the screen, its corner on the outline's top-left corner,
          and drag the outline's edge (or the slider) until it matches the card.
        </p>
        <div className="cal-stage" style={{ height: ch }}>
          <div className="cal-card" data-testid="cal-card" data-landscape={landscape ? "1" : "0"}
            style={{ width: cw, height: ch, borderRadius: CARD_MM.r * draft }}>
            <span className="cal-chip" style={{ width: 11 * draft, height: 8.5 * draft, left: 10 * draft, top: (landscape ? 19 : 12) * draft }} />
            <span className="cal-card-text">85.60 × 53.98 mm</span>
            <span className="cal-grip" data-testid="cal-grip" role="slider" aria-label="The card's width" aria-valuenow={+draft.toFixed(3)}
              aria-valuemin={MIN_PX_PER_MM} aria-valuemax={MAX_PX_PER_MM}
              onPointerDown={onGrip} onPointerMove={onGripMove} onPointerUp={onGripUp} onPointerCancel={onGripUp} />
          </div>
        </div>
        <div className="cal-row">
          <button type="button" className="kit-btn s-sm cal-step" data-testid="cal-minus" aria-label="Smaller" onClick={() => put(draft * (1 - STEP), "card")}>−</button>
          <input type="range" className="cal-slider" data-testid="cal-slider" aria-label="Scale (px per mm)" min={2} max={10} step={0.001}
            value={draft} onChange={(e) => put(Number(e.target.value), "card")} />
          <button type="button" className="kit-btn s-sm cal-step" data-testid="cal-plus" aria-label="Larger" onClick={() => put(draft * (1 + STEP), "card")}>+</button>
          <span className="cal-value" data-testid="cal-value" data-px-per-mm={draft}>{draft.toFixed(3)} px/mm · {Math.round(perInchOf(draft))} px/in</span>
        </div>
        <div className="cal-ruler">
          <label className="cal-ruler-label">
            Or with a ruler: this line measures
            <input className="kit-text cal-mm" data-testid="cal-ruler-mm" inputMode="decimal" aria-label="The line's length on a ruler (mm)"
              value={measured} onChange={(e) => onRuler(e.target.value)} onBlur={() => setTyped(null)}
              onKeyDown={(e) => { if (e.key === "Enter") save(); }} />
            mm
          </label>
          <div className="cal-line" data-testid="cal-line" data-px={line} style={{ width: line }}><i /><i /></div>
        </div>
        <div className="cal-status" data-testid="cal-status">
          This screen: {s.w} × {s.h} px at ×{+s.dpr.toFixed(3)} ·{" "}
          {scale.calibrated ? `calibrated with a ${scale.cal?.by === "ruler" ? "ruler" : "bank card"}${when ? ` on ${when}` : ""}` : `not calibrated: estimated from ${scale.basis}`}.
          {" "}Kept in this browser for this screen only.
        </div>
      </div>
    </Dialog>
  );
}
