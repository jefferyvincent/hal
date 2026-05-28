import { useEffect, useRef } from "react";
import { useImmersive } from "@/stores/immersive";
import { cn } from "@/lib/cn";

function shortTime(ts: number): string {
  const d = new Date(ts);
  const m = String(d.getMinutes()).padStart(2, "0");
  const s = String(d.getSeconds()).padStart(2, "0");
  return `${d.getHours()}:${m}:${s}`;
}

export default function ThoughtsPanel() {
  const active = useImmersive((s) => s.active);
  const thoughts = useImmersive((s) => s.thoughts);
  const bodyRef = useRef<HTMLDivElement>(null);

  // Pin to bottom on new thoughts.
  useEffect(() => {
    const el = bodyRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [thoughts]);

  if (!active) return null;

  return (
    <aside
      className={cn(
        "fixed left-[18px] top-[70px] z-[55] flex w-[min(360px,32vw)] flex-col font-mono",
        "max-h-[60vh] border-l-2 border-hal-amber/50 bg-[rgba(8,8,11,0.4)] px-3 py-2.5",
        "opacity-30 transition-all duration-500",
        "hover:bg-[rgba(8,8,11,0.85)] hover:opacity-100 hover:duration-200",
      )}
    >
      <header className="mb-2 font-display text-[9px] uppercase tracking-[3px] text-hal-amber">
        HAL · Live Cognition
      </header>

      <div
        ref={bodyRef}
        className="overflow-y-auto text-[11px] leading-[1.5] text-hal-text [scrollbar-color:rgba(255,179,0,0.35)_transparent] [scrollbar-width:thin]"
      >
        {thoughts.length === 0 ? (
          <div className="italic text-hal-text-dim">(silent)</div>
        ) : null}

        {thoughts.map((t) => (
          <div
            key={t.id}
            className={cn(
              "mb-2 select-text whitespace-pre-wrap break-words border-l border-hal-amber/25 pl-2",
              t.kind === "tool" && "text-[10px] tracking-[1px] text-hal-amber",
              t.kind === "note" && "italic text-hal-text-dim",
              t.kind === "hal" && "text-hal-text",
            )}
          >
            <span className="mr-1.5 text-[9px] text-hal-text-dim">
              {shortTime(t.ts)}
            </span>
            {t.text}
          </div>
        ))}
      </div>
    </aside>
  );
}
