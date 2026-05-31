// Equity-curve backdrop for the immersive "backtest" source. Renders the
// payload backtest.py pushes via open_view(kind="backtest") using
// lightweight-charts: a single cumulative-P&L line plus a stats overlay
// (win rate, total P&L, profit factor, max drawdown) and the by-vol-regime
// split. Mirrors ChartStage's setup so the look matches HAL's chart view.

import { useEffect, useRef } from "react";
import {
  createChart,
  ColorType,
  LineStyle,
  type IChartApi,
  type UTCTimestamp,
} from "lightweight-charts";
import { useImmersive } from "@/stores/immersive";

const UP = "#26a69a";
const DOWN = "#ef5350";
const LINE = "#ffb300"; // HAL amber for the equity line

export default function BacktestStage() {
  const bt = useImmersive((s) => s.backtest);
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || !bt || bt.equity.length === 0) return;

    const c: IChartApi = createChart(el, {
      width: el.clientWidth,
      height: el.clientHeight,
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "#0c0e12" },
        textColor: "#b2b5be",
        fontSize: 12,
      },
      grid: {
        vertLines: { color: "#1b1f2a" },
        horzLines: { color: "#1b1f2a" },
      },
      rightPriceScale: { borderColor: "#2a2e39" },
      timeScale: { borderColor: "#2a2e39", timeVisible: false, secondsVisible: false },
      handleScroll: { mouseWheel: true, pressedMouseMove: true },
      handleScale: { mouseWheel: true, pinch: true, axisPressedMouseMove: true },
    });

    const series = c.addLineSeries({ color: LINE, lineWidth: 2 });
    // lightweight-charts REQUIRES strictly-ascending times or setData throws
    // (which blanks the whole chart). The equity array is in trade-append
    // order, which is NOT guaranteed sorted — an earlier-entered trade can
    // exit after a later one. So sort by time first, THEN nudge any ties.
    const sorted = [...bt.equity].sort((a, b) => (a.t as number) - (b.t as number));
    const data: { time: UTCTimestamp; value: number }[] = [];
    let last = -Infinity;
    for (const p of sorted) {
      let t = p.t as number;
      if (t <= last) t = last + 1; // keep strictly increasing
      last = t;
      data.push({ time: t as UTCTimestamp, value: p.value });
    }
    series.setData(data);

    // Break-even line at 0.
    series.createPriceLine({
      price: 0,
      color: "#6a6a72",
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      axisLabelVisible: true,
      title: "B/E",
    });

    c.timeScale().fitContent();
    chartRef.current = c;
    return () => {
      c.remove();
      chartRef.current = null;
    };
  }, [bt]);

  if (!bt) return null;

  const m = bt.metrics || {};
  const total = Number(m.total_pnl ?? 0);
  const fmtPct = (v: unknown) =>
    typeof v === "number" ? `${Math.round(v * 100)}%` : "—";
  const fmtUsd = (v: unknown) =>
    typeof v === "number"
      ? v.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 })
      : "—";

  const noCurve = !bt.equity || bt.equity.length === 0;

  return (
    <div className="absolute inset-0 bg-[#0c0e12]">
      <div ref={containerRef} className="absolute inset-0" />

      {/* Empty-state: payload arrived but no equity points to plot. */}
      {noCurve ? (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <span className="font-mono text-[13px] text-hal-text-dim">
            {bt.underlying}: no trades to chart for this window.
          </span>
        </div>
      ) : null}

      {/* Header + stat overlay (top-left, like ChartStage's OHLC legend). */}
      <div className="pointer-events-none absolute left-3 top-2 z-10 flex flex-col gap-1 font-mono text-[13px]">
        <div className="flex items-center gap-2 text-white">
          <span className="text-[15px] font-semibold tracking-wide">
            {bt.underlying} backtest
          </span>
        </div>
        <div className="text-[11px] text-hal-text-dim">{bt.strategy}</div>
        <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5">
          <Stat label="Trades" value={String(m.trades ?? "—")} />
          <Stat label="Win rate" value={fmtPct(m.win_rate)} />
          <Stat
            label="Total P&L"
            value={fmtUsd(m.total_pnl)}
            color={total >= 0 ? UP : DOWN}
          />
          <Stat label="Profit factor" value={m.profit_factor == null ? "—" : String(m.profit_factor)} />
          <Stat label="Max DD" value={fmtUsd(m.max_drawdown)} color={DOWN} />
        </div>
        {bt.by_regime && Object.keys(bt.by_regime).length > 0 ? (
          <div className="mt-1 flex flex-wrap gap-x-4 text-[10px] text-hal-text-dim">
            {Object.entries(bt.by_regime).map(([k, v]) => (
              <span key={k}>
                {k}: {Math.round(v.win_rate * 100)}% ({v.trades})
              </span>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <span className="flex items-baseline gap-1">
      <span className="text-[9px] uppercase tracking-[1px] text-hal-text-dim">{label}</span>
      <span style={color ? { color } : undefined} className="text-hal-text">
        {value}
      </span>
    </span>
  );
}
