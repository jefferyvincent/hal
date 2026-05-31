// Quick-backtest buttons for the major index options. Each chip fires the
// existing "backtest <symbol>" command through the chat pipeline, hitting the
// same deterministic backtest route HAL uses for typed/spoken requests.
// A subtle top-center strip; hidden in immersive mode (SourceBar owns that
// strip) and dimmed while a turn is in flight.

import { useConnection } from "@/stores/connection";
import { useImmersive } from "@/stores/immersive";
import { cn } from "@/lib/cn";

// Index roots (SPX/NDX/RUT/VIX) backtest the cash-settled index; the rest are
// liquid ETF proxies. All run the 12-month quick window server-side.
const INDEXES = ["SPX", "SPY", "QQQ", "NDX", "DIA", "IWM", "RUT", "VIX"];

export default function IndexButtons() {
  const sendText = useConnection((s) => s.sendText);
  const mode = useConnection((s) => s.mode);
  const immersive = useImmersive((s) => s.active);

  // The SourceBar owns the top strip in immersive mode — don't overlap it.
  if (immersive) return null;

  const busy = mode === "processing" || mode === "speaking";

  return (
    <div className="immersive-fade fixed left-1/2 top-3.5 z-[40] flex -translate-x-1/2 items-center gap-1.5 border border-hal-red/35 bg-[rgba(8,8,11,0.6)] p-1.5 opacity-30 backdrop-blur-md transition-opacity duration-500 hover:opacity-100 hover:duration-200">
      <span className="px-1 font-display text-[8px] uppercase tracking-[2px] text-hal-red">
        Backtest
      </span>
      {INDEXES.map((sym) => (
        <button
          key={sym}
          type="button"
          disabled={busy}
          onClick={() => void sendText(`backtest ${sym}`)}
          className={cn(
            "border border-hal-red/30 bg-hal-red/[0.06] px-2.5 py-1.5 font-display text-[9px] uppercase tracking-[2px] text-hal-text transition-all",
            "hover:bg-hal-red/20 hover:text-white",
            busy && "cursor-not-allowed opacity-40 hover:bg-hal-red/[0.06] hover:text-hal-text",
          )}
          title={`Backtest ${sym}`}
        >
          {sym}
        </button>
      ))}
    </div>
  );
}
