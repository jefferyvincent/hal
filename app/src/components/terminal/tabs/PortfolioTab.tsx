// F2 PORTFOLIO — a dense Bloomberg-style blotter of the live Alpaca account:
// account summary, risk posture, and a positions table with inline close. All
// data + actions already exist in useConnection (mirrors PositionsPanel), just
// laid out as a terminal grid rather than a modal.

import { useEffect, useState } from "react";
import { useConnection } from "@/stores/connection";
import { Panel, Stat, Empty, money, pct, POS, NEG } from "@/components/terminal/primitives";
import type { BrokerPosition } from "@/types";

const REFRESH_MS = 5000;

// OCC option symbol → readable chip (shared shape with PositionsPanel).
const OCC_RE = /^(.+?)(\d{2})(\d{2})(\d{2})([CP])(\d{8})$/;
function optionChip(symbol: string): string | null {
  const m = OCC_RE.exec(symbol);
  if (!m) return null;
  const [, , yy, mm, dd, cp, strike] = m;
  return `${Number(strike) / 1000}${cp === "C" ? "C" : "P"} ${Number(mm)}/${Number(dd)}/${yy}`;
}

export default function PortfolioTab() {
  const positions = useConnection((s) => s.positions);
  const account = useConnection((s) => s.brokerAccount);
  const ready = useConnection((s) => s.brokerReady);
  const paper = useConnection((s) => s.brokerPaper);
  const mode = useConnection((s) => s.tradeMode);
  const risk = useConnection((s) => s.risk);
  const error = useConnection((s) => s.positionsError);
  const refresh = useConnection((s) => s.refreshPositions);
  const closePosition = useConnection((s) => s.closePosition);
  const [confirming, setConfirming] = useState<string | null>(null);

  useEffect(() => {
    refresh();
    const id = window.setInterval(refresh, REFRESH_MS);
    return () => window.clearInterval(id);
  }, [refresh]);

  useEffect(() => {
    if (confirming && !positions.some((p) => p.symbol === confirming)) setConfirming(null);
  }, [positions, confirming]);

  const openPl = positions.reduce((s, p) => s + (p.unrealized_pl ?? 0), 0);
  const gross = positions.reduce((s, p) => s + Math.abs(p.market_value ?? 0), 0);
  const exposurePct = account?.equity ? gross / account.equity : null;

  return (
    <div className="flex h-full flex-col gap-2 p-2">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
        <Stat label="Equity" value={money(account?.equity ?? null)} sub={paper ? "PAPER" : ready ? "LIVE" : ""} />
        <Stat label="Cash" value={money(account?.cash ?? null)} />
        <Stat label="Buying Power" value={money(account?.buying_power ?? null)} />
        <Stat label="Options BP" value={money(account?.options_buying_power ?? null)} />
        <Stat label="Open P&L" value={money(openPl)} color={openPl >= 0 ? POS : NEG} />
        <Stat
          label="Gross Exposure"
          value={money(gross)}
          sub={exposurePct != null ? pct(exposurePct, 0) : undefined}
        />
      </div>

      {error ? (
        <div className="border border-term-amber-dim bg-term-amber/10 px-3 py-2 text-[11px] text-term-amber-bright">
          {error}
        </div>
      ) : null}

      <Panel
        title={`Positions · ${positions.length}`}
        className="min-h-0 flex-1"
        right={
          <>
            <span className="text-[9px] uppercase tracking-[2px] text-term-text-dim">
              {mode === "autopilot" ? "AUTOPILOT" : "CONFIRM"}
            </span>
            <span
              className="text-[9px] uppercase tracking-[2px]"
              style={{ color: risk?.killed ? "#ffd166" : "#8a8470" }}
            >
              {risk?.killed ? "RISK · HALTED" : "RISK · ARMED"}
            </span>
            <button
              type="button"
              onClick={refresh}
              className="text-[9px] uppercase tracking-[2px] text-term-text-dim hover:text-term-amber"
            >
              Refresh
            </button>
          </>
        }
      >
        {!ready ? (
          <Empty text="Alpaca isn't configured — set ALPACA_API_KEY and ALPACA_SECRET_KEY in .env" />
        ) : positions.length === 0 ? (
          <Empty text="(no open positions)" />
        ) : (
          <table className="w-full text-[11px]">
            <thead className="sticky top-0 bg-term-panel-2 text-[9px] uppercase tracking-[1px] text-term-text-dim">
              <tr>
                <th className="px-2 py-1.5 text-left">Symbol</th>
                <th className="px-2 py-1.5 text-left">Side</th>
                <th className="px-2 py-1.5 text-right">Entry</th>
                <th className="px-2 py-1.5 text-right">Last</th>
                <th className="px-2 py-1.5 text-right">Value</th>
                <th className="px-2 py-1.5 text-right">Unreal. P&L</th>
                <th className="px-2 py-1.5 text-right">%</th>
                <th className="px-2 py-1.5 text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((p) => (
                <Row
                  key={p.symbol}
                  p={p}
                  confirming={confirming === p.symbol}
                  onAskClose={() => setConfirming(p.symbol)}
                  onCancel={() => setConfirming(null)}
                  onConfirm={() => {
                    closePosition(p.symbol);
                    setConfirming(null);
                  }}
                />
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  );
}

function Row({
  p,
  confirming,
  onAskClose,
  onCancel,
  onConfirm,
}: {
  p: BrokerPosition;
  confirming: boolean;
  onAskClose: () => void;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const up = (p.unrealized_pl ?? 0) >= 0;
  const chip = optionChip(p.symbol);
  return (
    <tr className="border-t border-term-border/50 hover:bg-term-panel-2/60">
      <td className="px-2 py-1.5">
        <span className="font-bold text-term-text">{p.symbol}</span>
        {chip ? <span className="ml-1.5 text-[9px] text-term-cyan">{chip}</span> : null}
      </td>
      <td className="px-2 py-1.5 uppercase text-term-text-dim">
        {p.side} {p.qty}
      </td>
      <td className="px-2 py-1.5 text-right text-term-text-dim">{money(p.avg_entry_price, 2)}</td>
      <td className="px-2 py-1.5 text-right text-term-text-dim">{money(p.current_price, 2)}</td>
      <td className="px-2 py-1.5 text-right text-term-text-dim">{money(p.market_value)}</td>
      <td className="px-2 py-1.5 text-right font-bold" style={{ color: up ? POS : NEG }}>
        {money(p.unrealized_pl)}
      </td>
      <td className="px-2 py-1.5 text-right" style={{ color: up ? POS : NEG }}>
        {pct(p.unrealized_plpc)}
      </td>
      <td className="px-2 py-1.5 text-right">
        {confirming ? (
          <span className="inline-flex items-center gap-1">
            <button
              type="button"
              onClick={onConfirm}
              className="border border-term-red/60 bg-term-red/15 px-2 py-0.5 text-[10px] uppercase tracking-[1px] text-term-red hover:bg-term-red/30"
            >
              Sell now
            </button>
            <button type="button" onClick={onCancel} className="px-1 text-[10px] text-term-text-dim hover:text-term-text">
              ✕
            </button>
          </span>
        ) : (
          <button
            type="button"
            onClick={onAskClose}
            title={`Close ${p.symbol} at market`}
            className="border border-term-border px-2 py-0.5 text-[10px] uppercase tracking-[1px] text-term-text-dim hover:border-term-red hover:text-term-red"
          >
            Close
          </button>
        )}
      </td>
    </tr>
  );
}
