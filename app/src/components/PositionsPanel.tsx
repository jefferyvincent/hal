import { useEffect, useState } from "react";
import { useConnection } from "@/stores/connection";
import { useUi } from "@/stores/ui";
import { cn } from "@/lib/cn";
import type { BrokerPosition } from "@/types";

const REFRESH_MS = 5000;

// Adjustable text size for the positions list. Base px is scaled by `scale`;
// row text uses em units so everything tracks one knob. Persisted per browser.
const FONT_KEY = "hal.positions.fontScale";
const BASE_PX = 13;
const SCALE_MIN = 0.9;
const SCALE_MAX = 2.0;
const SCALE_STEP = 0.15;

function money(n: number | null | undefined): string {
  if (n == null) return "—";
  return n.toLocaleString(undefined, { style: "currency", currency: "USD" });
}

function pct(frac: number | null | undefined): string {
  if (frac == null) return "—";
  const p = frac * 100;
  return `${p >= 0 ? "+" : ""}${p.toFixed(2)}%`;
}

function qtyLabel(p: BrokerPosition): string {
  const unit = p.asset_class.includes("option") ? "ct" : "sh";
  return `${p.side.toUpperCase()} ${p.qty} ${unit}`;
}

// OCC option symbol = underlying + YYMMDD + C/P + strike×1000 (8 digits),
// e.g. "QQQ260626P00719000". Pull out call/put + strike + expiry for a chip.
const OCC_RE = /^(.+?)(\d{2})(\d{2})(\d{2})([CP])(\d{8})$/;
function parseOption(
  symbol: string,
): { type: "C" | "P"; strike: number; expiry: string } | null {
  const m = OCC_RE.exec(symbol);
  if (!m) return null;
  const [, , yy, mm, dd, cp, strike] = m;
  return {
    type: cp as "C" | "P",
    strike: Number(strike) / 1000,
    expiry: `${Number(mm)}/${Number(dd)}/${yy}`, // M/D/YY
  };
}

function clampScale(v: number): number {
  return Math.round(Math.min(SCALE_MAX, Math.max(SCALE_MIN, v)) * 100) / 100;
}

// Live brokerage positions (Alpaca). The user can close any position directly
// here — a manual override that bypasses HAL's confirm/autopilot gate and
// submits an offsetting market order immediately (server: position_close).
export default function PositionsPanel() {
  const open = useUi((s) => s.positionsOpen);
  const toggle = useUi((s) => s.togglePositions);
  const positions = useConnection((s) => s.positions);
  const account = useConnection((s) => s.brokerAccount);
  const ready = useConnection((s) => s.brokerReady);
  const paper = useConnection((s) => s.brokerPaper);
  const mode = useConnection((s) => s.tradeMode);
  const error = useConnection((s) => s.positionsError);
  const refresh = useConnection((s) => s.refreshPositions);
  const closePosition = useConnection((s) => s.closePosition);
  const scalePosition = useConnection((s) => s.scalePosition);

  // Two-click confirm so a close is always deliberate.
  const [confirming, setConfirming] = useState<string | null>(null);

  // Adjustable text size (persisted).
  const [scale, setScale] = useState<number>(() => {
    const v = parseFloat(localStorage.getItem(FONT_KEY) || "");
    return Number.isFinite(v) ? clampScale(v) : 1.15;
  });
  useEffect(() => {
    try {
      localStorage.setItem(FONT_KEY, String(scale));
    } catch {
      /* ignore unavailable storage */
    }
  }, [scale]);
  const bump = (d: number) => setScale((s) => clampScale(s + d));
  const sizeStyle = { fontSize: `${BASE_PX * scale}px` } as const;

  // Poll while open; refresh immediately on open.
  useEffect(() => {
    if (!open) return;
    refresh();
    const id = window.setInterval(refresh, REFRESH_MS);
    return () => window.clearInterval(id);
  }, [open, refresh]);

  // Drop a stale confirm prompt if that position is gone.
  useEffect(() => {
    if (confirming && !positions.some((p) => p.symbol === confirming)) {
      setConfirming(null);
    }
  }, [positions, confirming]);

  if (!open) return null;

  const onClose = (symbol: string) => {
    closePosition(symbol);
    setConfirming(null);
  };

  return (
    <div
      className="fixed inset-0 z-40 flex items-start justify-center bg-black/60 backdrop-blur-sm"
      onClick={toggle}
    >
      <aside
        onClick={(e) => e.stopPropagation()}
        className={cn(
          "mt-[56px] flex max-h-[calc(100vh-92px)] w-[min(960px,94vw)] flex-col font-mono",
          "border border-hal-red/25 bg-[rgba(8,8,11,0.96)] shadow-[0_0_40px_rgba(0,0,0,0.7)]",
        )}
      >
        <header className="flex items-center justify-between border-b border-hal-red/20 bg-hal-red/[0.04] px-3 py-2.5 text-[9px] uppercase tracking-[4px] text-hal-red">
          <span>Positions · {positions.length}</span>
          <div className="flex items-center gap-3">
            <span
              className={cn(
                "border px-1.5 py-0.5 text-[8px] tracking-[2px]",
                paper
                  ? "border-emerald-500/40 text-emerald-400"
                  : "border-hal-red/60 text-hal-red-glow",
              )}
            >
              {paper ? "PAPER" : "LIVE"}
            </span>
            <span className="text-[8px] tracking-[2px] text-hal-text-dim">
              {mode === "autopilot" ? "AUTOPILOT" : "CONFIRM"}
            </span>
            {/* Text-size control */}
            <div className="flex items-center gap-0.5" title="Text size">
              <button
                type="button"
                onClick={() => bump(-SCALE_STEP)}
                disabled={scale <= SCALE_MIN}
                className="px-1 text-[12px] leading-none text-hal-text-dim hover:text-hal-red-glow disabled:opacity-30"
              >
                A−
              </button>
              <button
                type="button"
                onClick={() => bump(SCALE_STEP)}
                disabled={scale >= SCALE_MAX}
                className="px-1 text-[15px] leading-none text-hal-text-dim hover:text-hal-red-glow disabled:opacity-30"
              >
                A+
              </button>
            </div>
            <button
              type="button"
              onClick={refresh}
              className="text-[9px] uppercase tracking-[2px] text-hal-text-dim hover:text-hal-red-glow"
            >
              Refresh
            </button>
            <button
              type="button"
              onClick={toggle}
              className="text-[9px] uppercase tracking-[2px] text-hal-text-dim hover:text-hal-red-glow"
            >
              Close
            </button>
          </div>
        </header>

        {account ? (
          <div
            style={sizeStyle}
            className="flex items-center justify-between gap-4 border-b border-hal-red/15 px-3 py-2 text-[0.82em] text-hal-text-dim"
          >
            <span>
              Equity{" "}
              <span className="text-hal-text">{money(account.equity)}</span>
            </span>
            <span>
              Buying power{" "}
              <span className="text-hal-text">{money(account.buying_power)}</span>
            </span>
            <span>
              Options BP{" "}
              <span className="text-hal-text">
                {money(account.options_buying_power)}
              </span>
            </span>
          </div>
        ) : null}

        {error ? (
          <div className="border-b border-hal-amber/30 bg-hal-amber/[0.06] px-3 py-2 text-[11px] text-hal-amber-bright">
            {error}
          </div>
        ) : null}

        <div
          style={sizeStyle}
          className="flex flex-col overflow-y-auto [scrollbar-color:rgba(255,30,30,0.3)_transparent] [scrollbar-width:thin]"
        >
          {!ready ? (
            <div className="px-3 py-6 text-center text-[0.85em] text-hal-text-dim">
              Alpaca isn't configured. Set ALPACA_API_KEY and ALPACA_SECRET_KEY
              in .env to trade.
            </div>
          ) : positions.length === 0 ? (
            <div className="px-3 py-6 text-center text-[0.85em] text-hal-text-dim">
              (no open positions)
            </div>
          ) : (
            positions.map((p) => {
              const pl = p.unrealized_pl ?? 0;
              const up = pl >= 0;
              return (
                <article
                  key={p.symbol}
                  className="flex items-center justify-between gap-3 border-b border-hal-red/10 px-3 py-2.5"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-[1.05em] font-bold text-hal-text">
                        {p.symbol}
                      </span>
                      {(() => {
                        const opt = parseOption(p.symbol);
                        if (!opt) return null;
                        const isCall = opt.type === "C";
                        return (
                          <span
                            className={cn(
                              "shrink-0 border px-1.5 py-0.5 text-[0.66em] font-bold uppercase tracking-[1px]",
                              isCall
                                ? "border-emerald-500/50 bg-emerald-500/10 text-emerald-300"
                                : "border-hal-red/50 bg-hal-red/10 text-hal-red-glow",
                            )}
                          >
                            {opt.strike}
                            {isCall ? " Call" : " Put"} · {opt.expiry}
                          </span>
                        );
                      })()}
                      <span className="text-[0.72em] uppercase tracking-[1px] text-hal-text-dim">
                        {qtyLabel(p)}
                      </span>
                    </div>
                    <div className="mt-0.5 text-[0.72em] text-hal-text-dim">
                      entry {money(p.avg_entry_price)} · last{" "}
                      {money(p.current_price)} · {money(p.market_value)}
                    </div>
                  </div>

                  <div className="min-w-[6em] shrink-0 text-right">
                    <div
                      className={cn(
                        "text-[1.05em] font-bold",
                        up ? "text-emerald-400" : "text-hal-red-glow",
                      )}
                    >
                      {up ? "+" : ""}
                      {money(pl)}
                    </div>
                    <div
                      className={cn(
                        "text-[0.72em]",
                        up ? "text-emerald-400/70" : "text-hal-red-glow/70",
                      )}
                    >
                      {pct(p.unrealized_plpc)}
                    </div>
                  </div>

                  <ScaleControls p={p} onScale={scalePosition} />

                  {confirming === p.symbol ? (
                    <div className="flex shrink-0 items-center gap-1">
                      <button
                        type="button"
                        onClick={() => onClose(p.symbol)}
                        className="border border-hal-red/60 bg-hal-red/15 px-2 py-1 text-[0.78em] uppercase tracking-[1px] text-hal-red-glow hover:bg-hal-red/30"
                      >
                        Sell now
                      </button>
                      <button
                        type="button"
                        onClick={() => setConfirming(null)}
                        className="px-1.5 py-1 text-[0.78em] uppercase tracking-[1px] text-hal-text-dim hover:text-hal-text"
                      >
                        ✕
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setConfirming(p.symbol)}
                      title={`Close entire ${p.symbol} position at market`}
                      className="shrink-0 border border-hal-red/35 px-2.5 py-1 text-[0.78em] uppercase tracking-[2px] text-hal-text-dim transition-colors hover:border-hal-red hover:text-hal-red-glow"
                    >
                      Close
                    </button>
                  )}
                </article>
              );
            })
          )}
        </div>

        <footer className="border-t border-hal-red/15 px-3 py-2 text-[8px] uppercase tracking-[2px] text-hal-text-dim">
          Add / Trim / Close submit market orders immediately — overrides HAL.
        </footer>
      </aside>
    </div>
  );
}

// Per-position scale controls: a quantity stepper plus Add (buy more) and Trim
// (sell some) — both fire a market order immediately. Trim is capped at the
// held size; Add is bounded only by buying power (Alpaca rejects if short).
function ScaleControls({
  p,
  onScale,
}: {
  p: BrokerPosition;
  onScale: (symbol: string, delta: number) => void;
}) {
  const [qty, setQty] = useState(1);
  const held = Math.abs(Number(p.qty)) || 0;
  return (
    <div className="flex shrink-0 items-center gap-1">
      <div className="flex items-center border border-hal-text-dim/25">
        <button
          type="button"
          onClick={() => setQty((q) => Math.max(1, q - 1))}
          className="px-1.5 text-[0.85em] leading-none text-hal-text-dim hover:text-hal-text"
        >
          −
        </button>
        <input
          type="number"
          min={1}
          value={qty}
          onChange={(e) => setQty(Math.max(1, Math.floor(Number(e.target.value) || 1)))}
          className="w-7 bg-transparent text-center text-[0.72em] text-hal-text outline-none [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none"
        />
        <button
          type="button"
          onClick={() => setQty((q) => q + 1)}
          className="px-1.5 text-[0.85em] leading-none text-hal-text-dim hover:text-hal-text"
        >
          +
        </button>
      </div>
      <button
        type="button"
        onClick={() => setQty(Math.max(1, held))}
        title="Use the full position"
        className="text-[0.62em] uppercase tracking-[1px] text-hal-text-dim hover:text-hal-text"
      >
        of {held}
      </button>
      <button
        type="button"
        onClick={() => onScale(p.symbol, qty)}
        title={`Buy ${qty} more at market`}
        className="border border-emerald-500/40 bg-emerald-500/10 px-2 py-1 text-[0.72em] uppercase tracking-[1px] text-emerald-300 hover:bg-emerald-500/20"
      >
        + Add
      </button>
      <button
        type="button"
        onClick={() => onScale(p.symbol, -Math.min(qty, held))}
        disabled={held === 0}
        title={`Sell ${Math.min(qty, held)} at market`}
        className="border border-hal-amber/40 bg-hal-amber/10 px-2 py-1 text-[0.72em] uppercase tracking-[1px] text-hal-amber hover:bg-hal-amber/20 disabled:cursor-not-allowed disabled:opacity-40"
      >
        − Trim
      </button>
    </div>
  );
}
