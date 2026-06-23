// Broker picker: the one position-related setting that still lives in the UI.
// Account total comes from Alpaca and risk policy (per-trade %, stop %,
// concurrent cap) from the vault trading rules — HAL reads both server-side, so
// they're not duplicated here. Mirrors the TelemetryPanel floating-tab pattern
// (tab when closed, panel when open).

import { usePositionSizing, BROKERS } from "@/stores/positionSizing";
import { useUi } from "@/stores/ui";
import { cn } from "@/lib/cn";

export default function PositionSizing() {
  const open = useUi((s) => s.positionSizingOpen);
  const toggle = useUi((s) => s.togglePositionSizing);

  const broker = usePositionSizing((s) => s.broker);
  const setBroker = usePositionSizing((s) => s.setBroker);

  if (!open) {
    return (
      <button
        type="button"
        onClick={toggle}
        className={cn(
          "immersive-fade fixed left-0 top-[120px] z-30 border border-l-0 border-hal-red/30 bg-[rgba(8,8,11,0.85)] px-1.5 py-2 text-[9px] tracking-[2px] text-hal-red",
          "[writing-mode:vertical-rl] [text-orientation:mixed]",
          "hover:bg-hal-red/15 hover:text-white",
        )}
        title="Show broker"
      >
        BROKER
      </button>
    );
  }

  return (
    <aside
      className={cn(
        "immersive-fade fixed left-5 top-[70px] z-30 flex w-[360px] flex-col font-mono",
        "border border-hal-red/25 bg-[rgba(8,8,11,0.9)] backdrop-blur-md",
        "shadow-[0_0_30px_rgba(0,0,0,0.6)]",
      )}
    >
      <header className="flex items-center justify-between border-b border-hal-red/20 bg-hal-red/[0.04] px-3 py-2.5 text-[9px] uppercase tracking-[4px] text-hal-red">
        <span>Broker</span>
        <button
          type="button"
          onClick={toggle}
          className="text-[9px] uppercase tracking-[2px] text-hal-text-dim hover:text-hal-red-glow"
        >
          Hide
        </button>
      </header>

      <div className="flex flex-col gap-4 p-3.5">
        <p className="text-[10px] leading-relaxed text-hal-text-dim">
          Account total comes from your Alpaca balance; risk rules (max risk per
          trade, stop, account cap) live in your vault trading rules. This just
          picks which broker HAL tailors order steps to.
        </p>

        {/* Broker — HAL tailors order instructions to this. */}
        <label className="flex flex-col gap-1">
          <span className="text-[8px] uppercase tracking-[2px] text-hal-text-dim">Broker</span>
          <select
            value={broker}
            onChange={(e) => setBroker(e.target.value as typeof broker)}
            className="border border-hal-red/30 bg-black/35 px-2 py-1.5 text-[14px] text-hal-text outline-none focus:border-hal-red/70"
          >
            {BROKERS.map((b) => (
              <option key={b} value={b} className="bg-[#0a0a0d] text-hal-text">
                {b}
              </option>
            ))}
          </select>
        </label>
      </div>
    </aside>
  );
}
