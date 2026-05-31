// Position-sizing panel: HAL-themed card that turns an account size + risk
// rules into a contract quantity. Sizing is risk-based — qty is capped so a
// stop-out loses no more than maxRisk% of the account. Mirrors the
// TelemetryPanel floating-tab pattern (tab when closed, panel when open).

import { useState } from "react";
import { usePositionSizing, sizePosition, BROKERS } from "@/stores/positionSizing";
import { useUi } from "@/stores/ui";
import { cn } from "@/lib/cn";

const usd = (n: number) =>
  n.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 2 });

const commas = (n: number) =>
  n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

// Dollar field that shows a formatted amount ($11,000.00) when idle and the
// raw number while focused, so it stays easy to edit.
function CurrencyField({
  label,
  value,
  onCommit,
}: {
  label: string;
  value: number;
  onCommit: (v: number) => void;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[8px] uppercase tracking-[2px] text-hal-text-dim">{label}</span>
      <div className="flex items-center gap-1 border border-hal-red/30 bg-black/35 px-2 py-1.5 focus-within:border-hal-red/70">
        <span className="text-[12px] text-hal-text-dim">$</span>
        <input
          type="text"
          inputMode="decimal"
          defaultValue={value ? commas(value) : ""}
          onFocus={(e) => {
            e.target.value = value ? String(value) : "";
            e.target.select();
          }}
          onBlur={(e) => {
            const parsed = parseFloat(e.target.value.replace(/[^0-9.]/g, ""));
            const clean = Number.isFinite(parsed) ? parsed : 0;
            onCommit(clean);
            e.target.value = clean ? commas(clean) : "";
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") (e.target as HTMLInputElement).blur();
          }}
          className="w-full bg-transparent text-[14px] text-hal-text outline-none"
        />
      </div>
    </label>
  );
}

function NumberField({
  label,
  value,
  onCommit,
  prefix,
  suffix,
  step = "any",
}: {
  label: string;
  value: number;
  onCommit: (v: number) => void;
  prefix?: string;
  suffix?: string;
  step?: string;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[8px] uppercase tracking-[2px] text-hal-text-dim">{label}</span>
      <div className="flex items-center gap-1 border border-hal-red/30 bg-black/35 px-2 py-1.5 focus-within:border-hal-red/70">
        {prefix ? <span className="text-[12px] text-hal-text-dim">{prefix}</span> : null}
        <input
          type="number"
          step={step}
          defaultValue={value || ""}
          onBlur={(e) => onCommit(parseFloat(e.target.value))}
          onKeyDown={(e) => {
            if (e.key === "Enter") (e.target as HTMLInputElement).blur();
          }}
          className="w-full bg-transparent text-[14px] text-hal-text outline-none [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none"
        />
        {suffix ? <span className="text-[12px] text-hal-text-dim">{suffix}</span> : null}
      </div>
    </label>
  );
}

export default function PositionSizing() {
  const open = useUi((s) => s.positionSizingOpen);
  const toggle = useUi((s) => s.togglePositionSizing);

  const accountSize = usePositionSizing((s) => s.accountSize);
  const maxRiskPct = usePositionSizing((s) => s.maxRiskPct);
  const stopLossPct = usePositionSizing((s) => s.stopLossPct);
  const broker = usePositionSizing((s) => s.broker);
  const setAccountSize = usePositionSizing((s) => s.setAccountSize);
  const setMaxRiskPct = usePositionSizing((s) => s.setMaxRiskPct);
  const setStopLossPct = usePositionSizing((s) => s.setStopLossPct);
  const setBroker = usePositionSizing((s) => s.setBroker);

  const [price, setPrice] = useState<number>(NaN);

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
        title="Show position sizing"
      >
        POSITION
      </button>
    );
  }

  const riskBudget = accountSize * (maxRiskPct / 100);
  const hasPrice = Number.isFinite(price) && price > 0;
  const sized = hasPrice ? sizePosition(accountSize, maxRiskPct, stopLossPct, price) : null;
  const riskOfAccount = sized && accountSize > 0 ? (sized.totalRisk / accountSize) * 100 : 0;

  return (
    <aside
      className={cn(
        "immersive-fade fixed left-5 top-[70px] z-30 flex w-[360px] flex-col font-mono",
        "border border-hal-red/25 bg-[rgba(8,8,11,0.9)] backdrop-blur-md",
        "shadow-[0_0_30px_rgba(0,0,0,0.6)]",
      )}
    >
      <header className="flex items-center justify-between border-b border-hal-red/20 bg-hal-red/[0.04] px-3 py-2.5 text-[9px] uppercase tracking-[4px] text-hal-red">
        <span>Position Sizing</span>
        <button
          type="button"
          onClick={toggle}
          className="text-[9px] uppercase tracking-[2px] text-hal-text-dim hover:text-hal-red-glow"
        >
          Hide
        </button>
      </header>

      <div className="flex flex-col gap-4 p-3.5">
        {/* Account size + computed risk budget */}
        <div className="grid grid-cols-2 gap-3">
          <CurrencyField label="Account Size" value={accountSize} onCommit={setAccountSize} />
          <div className="flex flex-col gap-1">
            <span className="text-[8px] uppercase tracking-[2px] text-hal-text-dim">
              Max Risk / Trade ({maxRiskPct}%)
            </span>
            <div className="flex items-center border border-hal-amber/20 bg-hal-amber/[0.04] px-2 py-1.5">
              <span className="text-[14px] font-semibold text-hal-amber-bright">{usd(riskBudget)}</span>
            </div>
          </div>
        </div>

        {/* Risk parameters */}
        <div className="grid grid-cols-2 gap-3">
          <NumberField label="Max Risk %" value={maxRiskPct} onCommit={setMaxRiskPct} suffix="%" />
          <NumberField label="Stop Loss %" value={stopLossPct} onCommit={setStopLossPct} suffix="%" />
        </div>

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

        <div className="h-px bg-hal-red/15" />

        {/* Contract calculator */}
        <div className="flex flex-col gap-2">
          <span className="text-[9px] uppercase tracking-[3px] text-hal-amber">Contract Calculator</span>
          <NumberField
            label="Option Price (per share)"
            value={price}
            onCommit={setPrice}
            prefix="$"
          />

          {!hasPrice ? (
            <div className="border border-hal-red/15 bg-black/25 px-3 py-2.5 text-center text-[11px] text-hal-text-dim">
              Enter a price to calculate position size
            </div>
          ) : stopLossPct <= 0 ? (
            <div className="border border-hal-amber/30 bg-hal-amber/[0.04] px-3 py-2.5 text-center text-[11px] text-hal-amber">
              Set a stop loss above 0% to size by risk
            </div>
          ) : (
            <div className="flex flex-col gap-2 border border-hal-red/20 bg-black/25 px-3 py-3">
              <div className="flex items-baseline justify-between">
                <span className="text-[10px] uppercase tracking-[2px] text-hal-text-dim">Contracts</span>
                <span className="text-[22px] font-bold leading-none text-hal-amber-bright">
                  {sized!.qty}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px]">
                <Stat label="Cost / contract" value={usd(sized!.costPerContract)} />
                <Stat label="Risk / contract" value={usd(sized!.riskPerContract)} />
                <Stat label="Total deployed" value={usd(sized!.totalCost)} />
                <Stat
                  label="Total at risk"
                  value={`${usd(sized!.totalRisk)} · ${riskOfAccount.toFixed(1)}%`}
                />
              </div>
              {sized!.qty === 0 ? (
                <div className="text-[10px] text-hal-amber">
                  Risk budget ({usd(riskBudget)}) is below one contract's risk ({usd(sized!.riskPerContract)}).
                </div>
              ) : null}
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-[8px] uppercase tracking-[1px] text-hal-text-dim">{label}</span>
      <span className="text-hal-text">{value}</span>
    </div>
  );
}
