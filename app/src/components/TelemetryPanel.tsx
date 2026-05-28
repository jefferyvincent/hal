import { useEffect, useRef } from "react";
import { useConnection } from "@/stores/connection";
import { useUi } from "@/stores/ui";
import { cn } from "@/lib/cn";

export default function TelemetryPanel() {
  const hidden = useUi((s) => s.telemetryHidden);
  const setHidden = useUi((s) => s.setTelemetryHidden);
  const telemetry = useConnection((s) => s.telemetry);
  const clear = useConnection((s) => s.clearTelemetry);

  const listRef = useRef<HTMLDivElement>(null);

  // Pin to bottom when new entries arrive.
  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [telemetry]);

  // Small floating tab to reopen the panel when hidden.
  if (hidden) {
    return (
      <button
        type="button"
        onClick={() => setHidden(false)}
        className={cn(
          "immersive-fade fixed right-0 top-[120px] z-30 border border-r-0 border-hal-red/30 bg-[rgba(8,8,11,0.85)] px-1.5 py-2 text-[9px] tracking-[2px] text-hal-red",
          "[writing-mode:vertical-rl] [text-orientation:mixed]",
          "hover:bg-hal-red/15 hover:text-white",
        )}
        title="Show telemetry"
      >
        TELEMETRY
      </button>
    );
  }

  return (
    <aside
      className={cn(
        "immersive-fade fixed right-5 top-[70px] z-30 flex w-[360px] flex-col font-mono",
        "max-h-[calc(100vh-220px)] border border-hal-red/25 bg-[rgba(8,8,11,0.9)] backdrop-blur-md",
        "shadow-[0_0_30px_rgba(0,0,0,0.6)]",
      )}
    >
      <header className="flex items-center justify-between border-b border-hal-red/20 bg-hal-red/[0.04] px-3 py-2.5 text-[9px] uppercase tracking-[4px] text-hal-red">
        <span>Telemetry · {telemetry.length}</span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={clear}
            className="text-[9px] uppercase tracking-[2px] text-hal-text-dim hover:text-hal-red-glow"
          >
            Clear
          </button>
          <button
            type="button"
            onClick={() => setHidden(true)}
            className="text-[9px] uppercase tracking-[2px] text-hal-text-dim hover:text-hal-red-glow"
          >
            Hide
          </button>
        </div>
      </header>

      <div
        ref={listRef}
        className="flex flex-col gap-3.5 overflow-y-auto p-3 [scrollbar-color:rgba(255,30,30,0.3)_transparent] [scrollbar-width:thin]"
      >
        {telemetry.length === 0 ? (
          <div className="text-center text-[11px] text-hal-text-dim">
            (no tool calls yet)
          </div>
        ) : null}

        {telemetry.map((t, i) => (
          <article
            key={i}
            className={cn(
              "border-l-2 pl-2.5",
              t.status === "error"
                ? "border-l-hal-amber"
                : t.status === "declined"
                  ? "border-l-hal-text-dim opacity-70"
                  : "border-l-hal-red/50",
            )}
          >
            <div
              className={cn(
                "mb-1 text-[9px] uppercase tracking-[3px]",
                t.status === "error" ? "text-hal-amber-bright" : "text-hal-amber",
              )}
            >
              {t.tool}
              {t.status && t.status !== "ok" ? ` · ${t.status}` : ""}
            </div>

            {t.input ? (
              <>
                <div className="mb-0.5 mt-1.5 text-[8px] uppercase tracking-[2px] text-hal-text-dim">
                  Input
                </div>
                <pre className="max-h-[220px] select-text overflow-y-auto whitespace-pre-wrap break-words border-l border-hal-amber/30 bg-black/35 px-2 py-1.5 text-[10.5px] leading-snug text-hal-text-dim">
                  {t.input}
                </pre>
              </>
            ) : null}

            {t.output ? (
              <>
                <div className="mb-0.5 mt-1.5 text-[8px] uppercase tracking-[2px] text-hal-text-dim">
                  Output
                </div>
                <pre className="max-h-[220px] select-text overflow-y-auto whitespace-pre-wrap break-words bg-black/35 px-2 py-1.5 text-[10.5px] leading-snug text-hal-text">
                  {t.output}
                </pre>
              </>
            ) : null}
          </article>
        ))}
      </div>
    </aside>
  );
}
