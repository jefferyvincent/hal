// A compact candlestick chart for the terminal, skinned amber-on-black to match
// the FinceptTerminal look. Reuses the same ChartPayload the rest of HAL already
// builds server-side (charting.py) and renders it with lightweight-charts —
// candles, a volume histogram, the SuperTrend overlay, and support/resistance
// level lines. Kept self-contained so any terminal tab can drop in a chart.

import { useEffect, useRef } from "react";
import {
  createChart,
  ColorType,
  LineStyle,
  type IChartApi,
  type UTCTimestamp,
} from "lightweight-charts";
import type { ChartPayload } from "@/types";

const UP = "#2ecc71";
const DOWN = "#ff453a";
const AMBER = "#ffb000";

export default function TerminalChart({ chart }: { chart: ChartPayload }) {
  const ref = useRef<HTMLDivElement>(null);
  const apiRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const api = createChart(el, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#8a8470",
        fontFamily: '"Share Tech Mono", monospace',
        fontSize: 10,
      },
      grid: {
        vertLines: { color: "rgba(255,176,0,0.05)" },
        horzLines: { color: "rgba(255,176,0,0.05)" },
      },
      rightPriceScale: { borderColor: "#1d2026" },
      timeScale: { borderColor: "#1d2026", timeVisible: true, secondsVisible: false },
      crosshair: { mode: 0 },
      autoSize: true,
    });
    apiRef.current = api;

    const candles = api.addCandlestickSeries({
      upColor: UP,
      downColor: DOWN,
      borderUpColor: UP,
      borderDownColor: DOWN,
      wickUpColor: UP,
      wickDownColor: DOWN,
    });
    candles.setData(
      chart.candles.map((c) => ({
        time: c.time as UTCTimestamp,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      })),
    );

    const vol = api.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
    });
    api.priceScale("vol").applyOptions({
      scaleMargins: { top: 0.82, bottom: 0 },
    });
    vol.setData(
      chart.volume.map((v) => ({
        time: v.time as UTCTimestamp,
        value: v.value,
        color: v.up ? "rgba(46,204,113,0.4)" : "rgba(255,69,58,0.4)",
      })),
    );

    if (chart.supertrend_up.length) {
      const up = api.addLineSeries({ color: UP, lineWidth: 1 });
      up.setData(chart.supertrend_up.map((p) => ({ time: p.time as UTCTimestamp, value: p.value })));
    }
    if (chart.supertrend_down.length) {
      const dn = api.addLineSeries({ color: DOWN, lineWidth: 1 });
      dn.setData(chart.supertrend_down.map((p) => ({ time: p.time as UTCTimestamp, value: p.value })));
    }

    for (const lvl of chart.levels) {
      candles.createPriceLine({
        price: lvl.price,
        color: lvl.kind === "resistance" ? "rgba(255,69,58,0.55)" : "rgba(46,204,113,0.55)",
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: lvl.label,
      });
    }

    if (chart.markers.length) {
      candles.setMarkers(
        chart.markers.map((m) => ({
          time: m.time as UTCTimestamp,
          position: m.side === "buy" ? "belowBar" : "aboveBar",
          color: m.side === "buy" ? UP : DOWN,
          shape: m.side === "buy" ? "arrowUp" : "arrowDown",
        })),
      );
    }

    api.timeScale().fitContent();
    return () => {
      api.remove();
      apiRef.current = null;
    };
  }, [chart]);

  return (
    <div className="relative h-full w-full">
      <div className="absolute left-2 top-1.5 z-10 flex items-baseline gap-2 text-term-amber">
        <span className="text-[12px] font-bold tracking-[2px]">{chart.symbol}</span>
        <span className="text-[9px] uppercase tracking-[2px] text-term-text-dim">
          {chart.timeframe} · {chart.bar_count} bars
        </span>
      </div>
      <div ref={ref} className="h-full w-full" style={{ accentColor: AMBER }} />
    </div>
  );
}
