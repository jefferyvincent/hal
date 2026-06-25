// F1 OVERVIEW — the terminal's at-a-glance board. Composes data HAL already
// streams: live account + positions, the loaded price chart, the latest
// committee verdict, and the most recent backtest. Everything here is
// read-only and reuses existing stores, so it works the moment the WS connects.

import { useEffect } from "react";
import { useConnection } from "@/stores/connection";
import { useImmersive } from "@/stores/immersive";
import { renderMessage } from "@/lib/markdown";
import TerminalChart from "@/components/terminal/TerminalChart";
import { Panel, Stat, Empty, money, pct, POS, NEG } from "@/components/terminal/primitives";

const REFRESH_MS = 5000;

export default function OverviewTab() {
  const positions = useConnection((s) => s.positions);
  const account = useConnection((s) => s.brokerAccount);
  const ready = useConnection((s) => s.brokerReady);
  const ideas = useConnection((s) => s.tradeIdeas);
  const refresh = useConnection((s) => s.refreshPositions);
  const chart = useImmersive((s) => s.chart);
  const bt = useImmersive((s) => s.backtest);

  useEffect(() => {
    refresh();
    const id = window.setInterval(refresh, REFRESH_MS);
    return () => window.clearInterval(id);
  }, [refresh]);

  const openPl = positions.reduce((s, p) => s + (p.unrealized_pl ?? 0), 0);
  const gross = positions.reduce((s, p) => s + Math.abs(p.market_value ?? 0), 0);
  const m = bt?.metrics ?? {};
  const verdict = ideas[0] ?? null;

  return (
    <div className="flex h-full flex-col gap-2 p-2">
      {/* KPI strip */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
        <Stat
          label="Equity"
          value={money(account?.equity ?? null)}
          sub={ready ? `open P&L ${money(openPl)}` : "connect Alpaca"}
        />
        <Stat label="Open P&L" value={money(openPl)} color={openPl >= 0 ? POS : NEG} />
        <Stat label="Positions" value={String(positions.length)} sub={`gross ${money(gross)}`} />
        <Stat
          label="Win Rate"
          value={typeof m.win_rate === "number" ? pct(m.win_rate, 1) : "—"}
          sub={bt ? `bt ${bt.underlying}` : "no backtest"}
        />
        <Stat
          label="Profit Factor"
          value={m.profit_factor == null ? "—" : String(m.profit_factor)}
          color={Number(m.profit_factor ?? 0) >= 1 ? POS : NEG}
        />
        <Stat
          label="Buying Power"
          value={money(account?.buying_power ?? null)}
          sub={account?.paper ? "paper" : ready ? "live" : ""}
        />
      </div>

      {/* Chart + verdict / equity + positions */}
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-2 lg:grid-cols-2">
        <Panel title={chart ? `${chart.symbol} · ${chart.timeframe}` : "Price Chart"} bodyClassName="p-0">
          {chart && chart.candles.length ? (
            <TerminalChart chart={chart} />
          ) : (
            <Empty text='No chart loaded — type "CHART SPY" or ask HAL "show me a chart of NVDA"' />
          )}
        </Panel>

        <Panel title="Committee Verdict">
          {verdict ? (
            <div
              className="prose-invert max-w-none px-3 py-2 text-[11px] leading-relaxed text-term-text [&_table]:w-full [&_th]:text-term-amber [&_td]:border-term-border"
              dangerouslySetInnerHTML={{ __html: renderMessage(verdict.markdown).html }}
            />
          ) : (
            <Empty text='No verdict yet — type "COMMITTEE AAPL" or ask "what does the committee think about NVDA?"' />
          )}
        </Panel>

        <Panel title={bt ? `Backtest · ${bt.underlying}` : "Backtest"} bodyClassName="p-0">
          {bt ? <EquityCurve points={bt.equity} /> : <Empty text='No equity curve — type "BACKTEST SPY"' />}
        </Panel>

        <Panel title={`Positions · ${positions.length}`}>
          {positions.length === 0 ? (
            <Empty text={ready ? "(no open positions)" : "Alpaca not configured"} />
          ) : (
            <table className="w-full text-[11px]">
              <thead className="sticky top-0 bg-term-panel-2 text-[9px] uppercase tracking-[1px] text-term-text-dim">
                <tr>
                  <th className="px-2 py-1 text-left">Symbol</th>
                  <th className="px-2 py-1 text-right">Qty</th>
                  <th className="px-2 py-1 text-right">Value</th>
                  <th className="px-2 py-1 text-right">P&L</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((p) => {
                  const up = (p.unrealized_pl ?? 0) >= 0;
                  return (
                    <tr key={p.symbol} className="border-t border-term-border/50">
                      <td className="px-2 py-1 font-bold text-term-text">{p.symbol}</td>
                      <td className="px-2 py-1 text-right text-term-text-dim">
                        {p.side === "short" ? "-" : ""}
                        {p.qty}
                      </td>
                      <td className="px-2 py-1 text-right text-term-text-dim">{money(p.market_value)}</td>
                      <td className="px-2 py-1 text-right font-bold" style={{ color: up ? POS : NEG }}>
                        {money(p.unrealized_pl)} ({pct(p.unrealized_plpc)})
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </Panel>
      </div>
    </div>
  );
}

// Minimal inline equity-curve sparkline — avoids spinning up a second chart for
// a glance. Scales the value series to the panel box.
function EquityCurve({ points }: { points: { t: number; value: number }[] }) {
  if (!points.length) return <Empty text="(empty curve)" />;
  const W = 600;
  const H = 180;
  const vals = points.map((p) => p.value);
  const lo = Math.min(...vals);
  const hi = Math.max(...vals);
  const span = hi - lo || 1;
  const last = vals[vals.length - 1];
  const first = vals[0];
  const up = last >= first;
  const d = points
    .map((p, i) => {
      const x = (i / (points.length - 1 || 1)) * W;
      const y = H - ((p.value - lo) / span) * H;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <div className="relative h-full w-full p-2">
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="h-full w-full">
        <path d={d} fill="none" stroke={up ? POS : NEG} strokeWidth={1.5} />
      </svg>
      <div className="absolute right-3 top-2 text-[11px] font-bold" style={{ color: up ? POS : NEG }}>
        {money(last)} ({pct((last - first) / (first || 1), 1)})
      </div>
    </div>
  );
}
