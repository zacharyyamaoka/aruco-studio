// The UI kit: compact, Fusion-native controls (icon, icon dropdown, number
// field that commits on Enter / blur, toggle, icon button).
import { useEffect, useRef, useState, type ReactNode } from "react";
import { ICONS } from "./icons";

export function Icon({ name, className }: { name: string; className?: string }) {
  return <svg viewBox="0 0 16 16" className={`ic ${className ?? ""}`} aria-hidden="true" dangerouslySetInnerHTML={{ __html: ICONS[name] ?? "" }} />;
}

export function IconButton({ icon, title, onClick, active, disabled, testid, children, className }: {
  icon: string; title: string; onClick: () => void; active?: boolean; disabled?: boolean; testid?: string; children?: ReactNode; className?: string;
}) {
  return (
    <button type="button" className={`ib${active ? " on" : ""}${className ? " " + className : ""}`} title={title} aria-label={title}
      aria-pressed={active ?? undefined} disabled={disabled} data-testid={testid} onClick={onClick}>
      <Icon name={icon} />{children}
    </button>
  );
}

export interface Opt { value: string | number; label: string; icon?: string; hint?: string }

export function Dropdown({ value, options, onChange, path, disabled, title, placeholder, wide }: {
  value: string | number | null | undefined; options: Opt[]; onChange: (v: string | number) => void;
  path?: string; disabled?: boolean; title?: string; placeholder?: string; wide?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    // Escape closes the open list and goes no further: the app's own Escape
    // (select none) must not run as well (audit F3). Capture phase, so it is
    // seen before the app's window listener; preventDefault marks it taken.
    const key = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      e.preventDefault();
      e.stopPropagation();
      setOpen(false);
    };
    window.addEventListener("mousedown", close);
    window.addEventListener("keydown", key, true);
    return () => { window.removeEventListener("mousedown", close); window.removeEventListener("keydown", key, true); };
  }, [open]);
  const cur = options.find((o) => String(o.value) === String(value));
  return (
    <div className={`dd${open ? " open" : ""}${wide ? " wide" : ""}`} ref={ref} data-path={path} data-value={cur ? String(cur.value) : ""}>
      <button type="button" className="dd-btn" disabled={disabled} title={title ?? cur?.hint ?? cur?.label}
        onClick={() => setOpen(!open)} data-testid={path ? `dd:${path}` : undefined}>
        {cur?.icon && <Icon name={cur.icon} />}
        <span className="dd-label">{cur ? cur.label : (placeholder ?? "–")}</span>
        <Icon name="chevron" className="chev" />
      </button>
      {open && (
        <div className="dd-list" role="listbox">
          {options.map((o) => (
            <button type="button" key={String(o.value)} role="option" aria-selected={String(o.value) === String(value)}
              className={`dd-opt${String(o.value) === String(value) ? " on" : ""}`} data-value={String(o.value)} title={o.hint}
              onClick={() => { setOpen(false); if (String(o.value) !== String(value)) onChange(o.value); }}>
              {o.icon ? <Icon name={o.icon} /> : <span className="ic" />}
              <span>{o.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/** A number field: typed text, committed on Enter or blur; Escape reverts.
 *  Text that is not a number is never sent: it shows its own error. */
export function NumberInput({ value, onCommit, path, unit, disabled, int, placeholder, onBad }: {
  value: number | null | undefined; onCommit: (v: number) => void; path?: string; unit?: string;
  disabled?: boolean; int?: boolean; placeholder?: string; onBad?: (msg: string | null) => void;
}) {
  const shown = value === null || value === undefined || Number.isNaN(value) ? "" : String(+Number(value).toFixed(int ? 0 : 4));
  const [text, setText] = useState(shown);
  const [focus, setFocus] = useState(false);
  useEffect(() => { if (!focus) setText(shown); }, [shown, focus]);
  const commit = () => {
    const t = text.trim().replace(",", ".");
    if (t === shown) { onBad?.(null); return; }
    const v = Number(t);
    if (t === "" || !Number.isFinite(v)) { onBad?.(`'${text}' is not a number`); return; }
    if (int && !Number.isInteger(v)) { onBad?.(`'${text}' is not a whole number`); return; }
    onBad?.(null);
    onCommit(v);
  };
  return (
    <span className={`num${disabled ? " dis" : ""}`}>
      <input type="text" inputMode="decimal" value={text} disabled={disabled} data-path={path} placeholder={placeholder}
        onFocus={() => setFocus(true)}
        onBlur={() => { setFocus(false); commit(); }}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") { (e.target as HTMLInputElement).blur(); }
          if (e.key === "Escape") { setText(shown); onBad?.(null); (e.target as HTMLInputElement).blur(); }
          e.stopPropagation();
        }} />
      {unit && <span className="unit">{unit}</span>}
    </span>
  );
}

export function TextInput({ value, onCommit, path, placeholder, disabled }: {
  value: string; onCommit: (v: string) => void; path?: string; placeholder?: string; disabled?: boolean;
}) {
  const [text, setText] = useState(value);
  const [focus, setFocus] = useState(false);
  useEffect(() => { if (!focus) setText(value); }, [value, focus]);
  return (
    <input type="text" className="txt" value={text} data-path={path} placeholder={placeholder} disabled={disabled}
      onFocus={() => setFocus(true)}
      onBlur={() => { setFocus(false); if (text !== value) onCommit(text); }}
      onChange={(e) => setText(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === "Enter") (e.target as HTMLInputElement).blur();
        if (e.key === "Escape") { setText(value); (e.target as HTMLInputElement).blur(); }
        e.stopPropagation();
      }} />
  );
}

export function Toggle({ value, onChange, path, label, disabled }: {
  value: boolean; onChange: (v: boolean) => void; path?: string; label?: string; disabled?: boolean;
}) {
  return (
    <label className={`tog${value ? " on" : ""}${disabled ? " dis" : ""}`}>
      <input type="checkbox" checked={value} data-path={path} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
      <span className="knob" />
      {label && <span className="tog-label">{label}</span>}
    </label>
  );
}

/** A row of icon buttons for one choice (the dialog's Origin row). */
export function ButtonRow({ value, options, onChange, path, disabled }: {
  value: string | number; options: Opt[]; onChange: (v: string | number) => void; path?: string; disabled?: boolean;
}) {
  return (
    <div className="brow" data-path={path} data-value={String(value)}>
      {options.map((o) => (
        <button type="button" key={String(o.value)} className={`ib${String(o.value) === String(value) ? " on" : ""}`}
          title={o.hint ?? o.label} aria-label={o.hint ?? o.label} data-value={String(o.value)} disabled={disabled}
          onClick={() => String(o.value) !== String(value) && onChange(o.value)}>
          {o.icon ? <Icon name={o.icon} /> : o.label}
        </button>
      ))}
    </div>
  );
}
