import { useConnection } from "@/stores/connection";
import { useImmersive } from "@/stores/immersive";
import { renderMessage } from "@/lib/markdown";
import { cn } from "@/lib/cn";

function fmtTime(t: number): string {
  return new Date(t * 1000).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

// Full-screen trade-ideas pane: a running list of trade recommendations and
// hold/exit reads (newest first). Driven by the immersive "trade_ideas" source
// but rendered as its OWN high-z overlay (not inside the z-3 immersive backdrop)
// so its Clear/Close controls sit above the HUD and are actually clickable.
export default function TradeIdeasStage() {
  const active = useImmersive((s) => s.active && s.source === "trade_ideas");
  const exit = useImmersive((s) => s.exit);
  const ideas = useConnection((s) => s.tradeIdeas);
  const clear = useConnection((s) => s.clearTradeIdeas);
  const placeTrade = useConnection((s) => s.placeTrade);
  const placements = useConnection((s) => s.tradePlacements);

  if (!active) return null;

  return (
    <div className="fixed inset-0 z-[90] flex flex-col bg-black/95 pt-[60px] pb-[24px] backdrop-blur-sm">
      <header className="mx-auto flex w-[min(900px,92vw)] items-center justify-between border-b border-hal-amber/25 pb-2 text-[10px] uppercase tracking-[5px] text-hal-amber">
        <span>Trade Ideas · {ideas.length}</span>
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={clear}
            className="border border-hal-amber/30 px-2 py-1 uppercase tracking-[2px] text-hal-text-dim hover:border-hal-amber hover:text-hal-amber"
          >
            Clear
          </button>
          <button
            type="button"
            onClick={exit}
            className="border border-hal-amber/30 px-2 py-1 uppercase tracking-[2px] text-hal-text-dim hover:border-hal-amber hover:text-hal-amber"
          >
            Close
          </button>
        </div>
      </header>

      <div className="mx-auto mt-3 flex w-[min(900px,92vw)] flex-1 flex-col gap-3 overflow-y-auto px-1 [scrollbar-color:rgba(255,176,0,0.3)_transparent] [scrollbar-width:thin]">
        {ideas.length === 0 ? (
          <div className="mt-10 text-center text-[12px] text-hal-text-dim">
            (no ideas yet — ask HAL for a trade or a hold read)
          </div>
        ) : null}

        {ideas.map((idea) => (
          <article
            key={idea.id}
            className="border-l-2 border-l-hal-amber/40 bg-hal-amber/[0.04] px-4 py-3 font-mono"
          >
            <div className="mb-1.5 flex items-center justify-between text-[10px] uppercase tracking-[2px]">
              <span className="font-bold text-hal-amber">
                {idea.symbol} · {idea.kind === "hold" ? "Hold/Exit" : "Trade"}
              </span>
              <span className="text-hal-text-dim/70">{fmtTime(idea.ts)}</span>
            </div>
            <div
              className="md max-w-full select-text whitespace-pre-wrap break-words text-[13px] leading-[1.55] text-hal-text"
              dangerouslySetInnerHTML={{
                __html: renderMessage(idea.markdown).html,
              }}
            />
            {idea.placeable ? (
              (() => {
                const state = placements[idea.id]; // undefined | placing | placed | failed
                const label =
                  state === "placed"
                    ? "✓ Placed on Alpaca"
                    : state === "placing"
                      ? "Placing…"
                      : state === "failed"
                        ? "✕ Failed — see chat"
                        : "▸ Place it on Alpaca";
                return (
                  <button
                    type="button"
                    disabled={state !== undefined}
                    onClick={() => placeTrade(idea.id)}
                    className={cn(
                      "mt-3 border px-3 py-1.5 text-[11px] uppercase tracking-[2px] disabled:cursor-not-allowed",
                      state === "placed"
                        ? "border-emerald-400/60 bg-emerald-400/15 text-emerald-300"
                        : state === "failed"
                          ? "border-hal-red/60 bg-hal-red/15 text-hal-red"
                          : "border-hal-amber/50 bg-hal-amber/10 text-hal-amber hover:bg-hal-amber/20 hover:text-white disabled:opacity-50",
                    )}
                  >
                    {label}
                  </button>
                );
              })()
            ) : null}
          </article>
        ))}
      </div>
    </div>
  );
}
