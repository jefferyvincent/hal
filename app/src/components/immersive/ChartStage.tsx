// Candlestick chart backdrop for immersive "chart" source. Renders the
// payload HAL pushes via show_chart using TradingView's lightweight-charts:
// dark theme, candles + volume, a SuperTrend overlay (green/red), and
// Buy/Sell flip markers. A TradingView-style OHLC legend tracks the
// crosshair in the top-left.

import { useEffect, useRef, useState } from "react";
import {
  createChart,
  ColorType,
  CrosshairMode,
  LineStyle,
  type IChartApi,
  type UTCTimestamp,
  type SeriesMarker,
  type Time,
  type CandlestickData,
} from "lightweight-charts";
import { useImmersive } from "@/stores/immersive";

const UP = "#26a69a";
const DOWN = "#ef5350";

interface Legend {
  open: number;
  high: number;
  low: number;
  close: number;
  up: boolean;
}

export default function ChartStage() {
  const chart = useImmersive((s) => s.chart);
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const chartZoom = useImmersive((s) => s.chartZoom);
  const [legend, setLegend] = useState<Legend | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || !chart || chart.candles.length === 0) return;

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
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: "#2a2e39" },
      timeScale: {
        borderColor: "#2a2e39",
        timeVisible: true,
        secondsVisible: false,
      },
      handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: true },
      handleScale: { mouseWheel: true, pinch: true, axisPressedMouseMove: true },
    });

    const candleSeries = c.addCandlestickSeries({
      upColor: UP,
      downColor: DOWN,
      borderUpColor: UP,
      borderDownColor: DOWN,
      wickUpColor: UP,
      wickDownColor: DOWN,
    });
    candleSeries.setData(
      chart.candles.map((b) => ({
        time: b.time as UTCTimestamp,
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
      })),
    );

    // HAL's detected support / resistance, drawn as dashed price lines.
    for (const lvl of chart.levels ?? []) {
      candleSeries.createPriceLine({
        price: lvl.price,
        color: lvl.kind === "resistance" ? DOWN : UP,
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: lvl.label,
      });
    }

    // Volume in the bottom ~22% of the pane (overlay price scale).
    const volSeries = c.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceScaleId: "",
    });
    volSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.78, bottom: 0 },
    });
    volSeries.setData(
      chart.volume.map((v) => ({
        time: v.time as UTCTimestamp,
        value: v.value,
        color: v.up ? "rgba(38,166,154,0.5)" : "rgba(239,83,80,0.5)",
      })),
    );

    // SuperTrend trailing stop, split into green (uptrend) / red (downtrend).
    const stUp = c.addLineSeries({ color: UP, lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
    stUp.setData(chart.supertrend_up.map((p) => ({ time: p.time as UTCTimestamp, value: p.value })));
    const stDown = c.addLineSeries({ color: DOWN, lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
    stDown.setData(chart.supertrend_down.map((p) => ({ time: p.time as UTCTimestamp, value: p.value })));

    // Buy/Sell flip markers (must be ascending by time).
    const markers: SeriesMarker<Time>[] = chart.markers
      .map((m) => ({
        time: m.time as UTCTimestamp,
        position: m.side === "buy" ? ("belowBar" as const) : ("aboveBar" as const),
        color: m.side === "buy" ? UP : DOWN,
        shape: m.side === "buy" ? ("arrowUp" as const) : ("arrowDown" as const),
        text: m.side === "buy" ? "Buy" : "Sell",
      }))
      .sort((a, b) => (a.time as number) - (b.time as number));
    candleSeries.setMarkers(markers);

    c.timeScale().fitContent();

    // OHLC legend follows the crosshair; default to the last bar.
    const last = chart.candles[chart.candles.length - 1];
    setLegend({ open: last.open, high: last.high, low: last.low, close: last.close, up: last.close >= last.open });
    c.subscribeCrosshairMove((param) => {
      const d = param.seriesData.get(candleSeries) as CandlestickData | undefined;
      if (!d) return;
      setLegend({ open: d.open, high: d.high, low: d.low, close: d.close, up: d.close >= d.open });
    });

    chartRef.current = c;
    return () => {
      c.remove();
      chartRef.current = null;
    };
  }, [chart]);

  // Apply HAL-driven zoom commands (voice: 'zoom in', 'zoom to the spike', ...).
  useEffect(() => {
    const c = chartRef.current;
    if (!c || !chartZoom) return;
    if (chartZoom.reset) {
      c.timeScale().fitContent();
    } else if (chartZoom.from != null && chartZoom.to != null) {
      c.timeScale().setVisibleRange({
        from: chartZoom.from as UTCTimestamp,
        to: chartZoom.to as UTCTimestamp,
      });
    }
  }, [chartZoom]);

  if (!chart) return null;

  const fmt = (n: number) => n.toFixed(2);
  const color = legend?.up ? UP : DOWN;

  return (
    <div className="absolute inset-0 bg-[#0c0e12]">
      <div ref={containerRef} className="absolute inset-0" />
      {/* TradingView-style header / OHLC legend */}
      <div className="pointer-events-none absolute left-3 top-2 z-10 flex flex-col gap-0.5 text-[13px] font-medium">
        <div className="flex items-center gap-2 text-white">
          <span className="text-[15px] font-semibold tracking-wide">{chart.symbol}</span>
          <span className="text-[#b2b5be]">· {chart.timeframe}</span>
        </div>
        {legend && (
          <div className="flex gap-3" style={{ color }}>
            <span>O {fmt(legend.open)}</span>
            <span>H {fmt(legend.high)}</span>
            <span>L {fmt(legend.low)}</span>
            <span>C {fmt(legend.close)}</span>
          </div>
        )}
      </div>
    </div>
  );
}
