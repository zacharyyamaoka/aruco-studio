// Tabs (base-ui Tabs): icon + name, a dot in the worst message's colour.
// Test hooks: [role=tab][data-tab=<id>], `.on` on the open one.
import { Tabs as T } from "@base-ui/react/tabs";
import { cn } from "./cn";
import { Glyph } from "./Glyph";

export interface TabDef { id: string; name: string; icon?: string; level?: "error" | "warn" | "info" | null }

export function Tabs({ tabs, value, onChange, className }: { tabs: TabDef[]; value: string; onChange: (id: string) => void; className?: string }) {
  return (
    <T.Root value={value} onValueChange={(v) => onChange(String(v))} className={cn("kit-tabs", className)}>
      <T.List className="kit-tab-list tabs">
        {tabs.map((t) => (
          <T.Tab key={t.id} value={t.id} data-tab={t.id} className={cn("kit-tab tab", value === t.id && "on", t.level && `has-${t.level}`)} title={t.name}>
            {t.icon && <Glyph name={t.icon} />}<span>{t.name}</span>{t.level && t.level !== "info" && <i className="dot" />}
          </T.Tab>
        ))}
      </T.List>
    </T.Root>
  );
}
