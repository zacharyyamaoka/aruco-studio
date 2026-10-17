// A library window (M8 4.2: the Library renders any {collections, cards,
// form}): collections on the left with a search, cards with a thumb in the
// middle, a side panel (Filters | Info), a footer with the buttons. What a
// card means and what Select does is the tool's.
import type { ReactNode } from "react";
import { cn } from "./cn";
import { Glyph } from "./Glyph";

export interface LibCollection { id: string; name: string; icon?: string; count: number }

export interface LibCard {
  id: string;
  name: string;
  subtitle?: string;
  /** SVG markup of the thumb */
  thumb?: string;
  where?: ReactNode;
  badge?: ReactNode;
  /** a mark in the corner: "current", ... */
  mark?: string;
  disabled?: boolean;
  title?: string;
}

export function LibraryShell({ title, collections, coll, onColl, search, onSearch, cards, picked, onPick, onOpen, tools, count,
  side, foot, notes, onClose, empty, overlay, testid = "library" }: {
  title: ReactNode; collections: LibCollection[]; coll: string | null; onColl: (id: string) => void;
  search: string; onSearch: (q: string) => void; cards: LibCard[]; picked: string | null;
  onPick: (id: string) => void; onOpen?: (id: string) => void; tools?: ReactNode; count?: ReactNode;
  side?: ReactNode; foot?: ReactNode; notes?: ReactNode; onClose: () => void; empty?: ReactNode; overlay?: ReactNode; testid?: string;
}) {
  return (
    <div className="modal-back kit-backdrop-solid" data-testid={testid} onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="library kit-library" role="dialog" aria-label={typeof title === "string" ? title : "Library"}>
        <div className="lib-title">{title}
          <button className="kit-ib close" title="Close" aria-label="Close" onClick={onClose}><Glyph name="close" /></button></div>
        <aside className="lib-nav">
          <label className="search"><Glyph name="search" /><input value={search} onChange={(e) => onSearch(e.target.value)} placeholder="Search" data-testid="lib-search" /></label>
          <ul className="colls">
            {collections.map((c) => (
              <li key={c.id} className={c.id === coll ? "on" : ""} data-coll={c.id} onClick={() => onColl(c.id)}>
                {c.icon && <Glyph name={c.icon} />}<span>{c.name}</span><span className="n">{c.count}</span>
              </li>
            ))}
          </ul>
          <div className="notes">{notes}</div>
        </aside>
        <main className="lib-main">
          <div className="lib-tools">{tools}<span className="grow" />{count}</div>
          <div className="cards" role="listbox" aria-label="Cards">
            {!cards.length && <div className="empty">{empty ?? "Nothing here."}</div>}
            {cards.map((c) => (
              <div key={c.id} className={cn("card", c.id === picked && "on", c.disabled && "bad")} role="option" aria-selected={c.id === picked}
                data-card={c.id} data-mark={c.mark} title={c.title}
                onClick={() => onPick(c.id)} onDoubleClick={() => onOpen?.(c.id)}>
                {c.badge}
                {c.mark && <span className="card-mark" data-testid="card-mark">{c.mark}</span>}
                <div className="thumb" dangerouslySetInnerHTML={{ __html: c.thumb || "" }} />
                <div className="name">{c.name}</div>
                {c.subtitle && <div className="sub">{c.subtitle}</div>}
                {c.where && <div className="where">{c.where}</div>}
              </div>
            ))}
          </div>
        </main>
        <aside className="lib-side">{side}</aside>
        <footer className="lib-foot">{foot}</footer>
        {overlay}
      </div>
    </div>
  );
}
