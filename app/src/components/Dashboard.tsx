// Full-screen dashboard — a single board that pulls together everything
// HAL already computes: a KPI strip, the price chart with indicators, the latest
// committee verdict, the backtest/optimizer equity curve, and live positions.
//
// Layout follows QuantDinger's "Live Overview" (a KPI card row over tiled
// panels), but the skin is pure HAL — red/amber, Share Tech Mono, the CRT grain
// the rest of the app wears. It's a useUi overlay (like CognitionStage), NOT an
// immersive source, because it COMPOSES several stores rather than being a single
// backdrop; it reads whatever's currently loaded and shows a "do X to populate"
// hint where a panel is empty, so it's useful before any data lands.

import { useEffect, useRef } from "react";
import {
  createChart,
  ColorType,
  LineStyle,
  type IChartApi,
  type UTCTimestamp,
} from "lightweight-charts";
import { useUi } from "@/stores/ui";
import { useConnection } from "@/stores/connection";
import { useImmersive } from "@/stores/immersive";
import { renderMessage } from "@/lib/markdown";
import { cn } from "@/lib/cn";
import type { BacktestPayload, ChartPayload, BrokerPosition, TradeIdea } from "@/types";

const UP = "#34d399"; // emerald — wins / bullish
const DOWN = "#ff3838"; // hal red-glow — losses / bearish
const AMBER = "#ffb300";

const REFRESH_MS = 5000;

function money(n: number | null | undefined, max = 0): string {
  if (n == null) return "—";
  return n.toLocaleString(undefined, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: max,
  });
}
function pct(frac: number | null | undefined): string {
  if (frac == null) return "—";
  const p = frac * 100;
  return `${p >= 0 ? "+" : ""}${p.toFixed(1)}%`;
}
function num(n: unknown): string {
  return typeof n === "number" ? String(n) : "—";
}

export default function Dashboard() {
  const open = useUi((s) => s.dashboardOpen);
  const toggle = useUi((s) => s.toggleDashboard);

  const positions = useConnection((s) => s.positions);
  const account = useConnection((s) => s.brokerAccount);
  const ready = useConnection((s) => s.brokerReady);
  const paper = useConnection((s) => s.brokerPaper);
  const mode = useConnection((s) => s.tradeMode);
  const risk = useConnection((s) => s.risk);
  const refresh = useConnection((s) => s.refreshPositions);
  const ideas = useConnection((s) => s.tradeIdeas);
  const recording = useConnection((s) => s.recording);
  const startRecording = useConnection((s) => s.startRecording);
  const stopRecording = useConnection((s) => s.stopRecording);

  const bt = useImmersive((s) => s.backtest);
  const chart = useImmersive((s) => s.chart);

  // Talk to HAL without leaving the dashboard. It covers the normal mic/input
  // bar (z-40 over z-20), so the board needs its own push-to-talk: click to
  // open the mic, click again to send. Commands ("backtest SPY", "deep dive on
  // AAPL"…) then populate the tiles in place — see the open_view dashboard guard.
  const onMic = () => {
    if (recording) stopRecording();
    else void startRecording(true);
  };

  // Poll positions while open (mirrors PositionsPanel).
  useEffect(() => {
    if (!open) return;
    refresh();
    const id = window.setInterval(refresh, REFRESH_MS);
    return () => window.clearInterval(id);
  }, [open, refresh]);

  // Esc closes (only when not typing in a field).
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return;
      if (e.key === "Escape") toggle();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, toggle]);

  if (!open) return null;

  const m = bt?.metrics ?? {};
  const openPl = positions.reduce((s, p) => s + (p.unrealized_pl ?? 0), 0);
  const gross = positions.reduce((s, p) => s + Math.abs(p.market_value ?? 0), 0);
  const latestVerdict = ideas[0] ?? null;

  return (
    <div className="fixed inset-0 z-40 flex flex-col bg-[#05070b] text-hal-text">
      {/* faint red radial wash, like CognitionStage */}
      <div
        className="pointer-events-none absolute inset-0 opacity-40"
        style={{ background: "radial-gradient(1200px 600px at 70% -10%, rgba(255,30,30,0.10), transparent 60%)" }}
        aria-hidden
      />

      {/* Header */}
      <header className="relative z-10 flex items-center justify-between border-b border-hal-red/20 bg-hal-red/[0.04] px-6 py-3">
        <div className="flex items-baseline gap-3">
          <span className="font-display text-[13px] uppercase tracking-[6px] text-hal-red-glow">HAL · Dashboard</span>
          <span className="text-[9px] uppercase tracking-[3px] text-hal-text-dim">clarity from uncertainty</span>
        </div>
        <div className="flex items-center gap-4 text-[9px] uppercase tracking-[2px]">
          <span
            className={cn(
              "border px-1.5 py-0.5 tracking-[2px]",
              paper ? "border-emerald-500/40 text-emerald-400" : "border-hal-red/60 text-hal-red-glow",
            )}
          >
            {paper ? "PAPER" : "LIVE"}
          </span>
          <span className="text-hal-text-dim">{mode === "autopilot" ? "AUTOPILOT" : "CONFIRM"}</span>
          <span className={cn(risk?.killed ? "text-hal-amber-bright" : "text-hal-text-dim")}>
            {risk?.killed ? "RISK · HALTED" : "RISK · ARMED"}
          </span>
          <button
            type="button"
            onClick={onMic}
            title={recording ? "Listening — click to send" : "Click to talk to HAL"}
            className={cn(
              "flex h-7 items-center gap-1.5 rounded-full border px-3 transition-all",
              recording
                ? "animate-pulse border-hal-red bg-hal-red/25 text-white shadow-[0_0_14px_rgba(255,30,30,0.5)]"
                : "border-hal-red/45 bg-hal-red/[0.08] text-hal-text hover:border-hal-red hover:text-white",
            )}
          >
            <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
              <rect x="9" y="3" width="6" height="11" rx="3" />
              <path d="M5 11a7 7 0 0 0 14 0" />
              <line x1="12" y1="18" x2="12" y2="22" />
            </svg>
            {recording ? "Listening…" : "Talk"}
          </button>
          <button type="button" onClick={refresh} className="text-hal-text-dim hover:text-hal-red-glow">
            Refresh
          </button>
          <button type="button" onClick={toggle} className="text-hal-text-dim hover:text-white">
            Close ✕
          </button>
        </div>
      </header>

      {/* Body */}
      <div className="relative z-10 flex-1 overflow-y-auto overflow-x-hidden p-4 [scrollbar-color:rgba(255,30,30,0.3)_transparent] [scrollbar-width:thin]">
        {/* KPI strip — backtest/optimizer metrics + live account */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <Kpi
            label="Total Equity"
            value={money(account?.equity ?? null)}
            sub={account ? `open P&L ${money(openPl)}` : "connect Alpaca"}
            subColor={openPl >= 0 ? UP : DOWN}
            highlight
          />
          <Kpi label="Win Rate" value={typeof m.win_rate === "number" ? pct(m.win_rate) : "—"} ring={typeof m.win_rate === "number" ? m.win_rate : null} />
          <Kpi
            label="Profit Factor"
            value={m.profit_factor == null ? "—" : String(m.profit_factor)}
            sub={typeof m.expectancy === "number" ? `avg ${money(m.expectancy)}` : undefined}
            valueColor={Number(m.profit_factor ?? 0) >= 1 ? UP : DOWN}
          />
          <Kpi
            label="Max Drawdown"
            value={typeof m.max_drawdown_pct === "number" ? pct(m.max_drawdown_pct) : money(m.max_drawdown ?? null)}
            valueColor={DOWN}
          />
          <Kpi label="Total Trades" value={num(m.trades)} sub={bt ? bt.underlying : "no backtest"} />
          <Kpi label="Open Positions" value={String(positions.length)} sub={`gross ${money(gross)}`} />
        </div>

        {/* Tiles: chart + verdict / equity + positions */}
        <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-2">
          <Tile title={chart ? `${chart.symbol} · ${chart.timeframe}` : "Price Chart"} hint='Ask HAL: "show me a chart of NVDA"'>
            {chart && chart.candles.length ? <CandleChart chart={chart} /> : <Empty text='No chart loaded. Say "show me a chart of SPY" — RSI / pivots overlay.' />}
          </Tile>

          <Tile title="Committee Verdict" hint='Ask HAL: "deep dive on AAPL"'>
            {latestVerdict ? <Verdict idea={latestVerdict} /> : <Empty text='No verdict yet. Say "what does the committee think about NVDA?"' />}
          </Tile>

          <Tile title={bt ? `Backtest · ${bt.underlying}` : "Backtest / Optimizer"} hint='Ask HAL: "optimize SPY" or "backtest QQQ"'>
            {bt ? <EquityPanel bt={bt} /> : <Empty text='No equity curve. Say "backtest SPY" or "optimize QQQ" to populate.' />}
          </Tile>

          <Tile title={`Positions · ${positions.length}`} hint="Live Alpaca account">
            <PositionsTable positions={positions} ready={ready} />
          </Tile>
        </div>
      </div>
    </div>
  );
}

// --- KPI card ---------------------------------------------------------------

function Kpi({
  label,
  value,
  sub,
  subColor,
  valueColor,
  ring,
  highlight,
}: {
  label: string;
  value: string;
  sub?: string;
  subColor?: string;
  valueColor?: string;
  ring?: number | null;
  highlight?: boolean;
}) {
  return (
    <div
      className={cn(
        "relative flex flex-col gap-1 rounded-lg border p-3",
        highlight ? "border-hal-red/45 bg-hal-red/[0.10]" : "border-hal-red/20 bg-[rgba(12,12,16,0.55)]",
      )}
    >
      <span className="text-[9px] uppercase tracking-[2px] text-hal-text-dim">{label}</span>
      <div className="flex items-center justify-between gap-2">
        <span className="text-2xl font-bold leading-none" style={valueColor ? { color: valueColor } : undefined}>
          {value}
        </span>
        {ring != null ? <Ring value={ring} /> : null}
      </div>
      {sub ? (
        <span className="text-[10px] text-hal-text-dim" style={subColor ? { color: subColor } : undefined}>
          {sub}
        </span>
      ) : null}
    </div>
  );
}

// Small circular gauge (0..1), QuantDinger-style.
function Ring({ value, size = 30, color = AMBER }: { value: number; size?: number; color?: string }) {
  const r = (size - 5) / 2;
  const c = 2 * Math.PI * r;
  const v = Math.max(0, Math.min(1, value));
  return (
    <svg width={size} height={size} className="shrink-0 -rotate-90">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.10)" strokeWidth={3} />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth={3}
        strokeDasharray={c}
        strokeDashoffset={c * (1 - v)}
        strokeLinecap="round"
      />
    </svg>
  );
}

// --- Tile shell -------------------------------------------------------------

function Tile({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className="flex min-h-[300px] flex-col rounded-lg border border-hal-red/20 bg-[rgba(10,10,13,0.55)]">
      <header className="flex items-center justify-between border-b border-hal-red/15 px-3 py-2">
        <span className="text-[10px] font-bold uppercase tracking-[3px] text-hal-text">{title}</span>
        {hint ? <span className="truncate pl-3 text-[9px] text-hal-text-dim">{hint}</span> : null}
      </header>
      {/* The inner absolute box gives children a DEFINITE height — lightweight-
          charts (absolute inset-0) and the h-full panels need a real size, which
          a bare flex-1 doesn't guarantee for percentage-height descendants. */}
      <div className="relative flex-1">
        <div className="absolute inset-0">{children}</div>
      </div>
    </section>
  );
}

function Empty({ text }: { text: string }) {
  return (
    <div className="flex h-full items-center justify-center px-6 text-center">
      <span className="text-[12px] text-hal-text-dim">{text}</span>
    </div>
  );
}

// --- Candlestick chart (price + S/R + supertrend + buy/sell markers) --------

function CandleChart({ chart }: { chart: ChartPayload }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || !chart.candles.length) return;
    const c: IChartApi = createChart(el, {
      width: el.clientWidth,
      height: el.clientHeight,
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: "#0a0a0d" }, textColor: "#b2b5be", fontSize: 11 },
      grid: { vertLines: { color: "#1b1f2a" }, horzLines: { color: "#1b1f2a" } },
      rightPriceScale: { borderColor: "#2a2e39" },
      timeScale: { borderColor: "#2a2e39", timeVisible: false },
    });
    const candles = c.addCandlestickSeries({
      upColor: UP, downColor: DOWN, borderVisible: false, wickUpColor: UP, wickDownColor: DOWN,
    });
    candles.setData(
      chart.candles.map((b) => ({ time: b.time as UTCTimestamp, open: b.open, high: b.high, low: b.low, close: b.close })),
    );
    // Supertrend overlays (the "indicators on chart" feel).
    if (chart.supertrend_up.length) {
      c.addLineSeries({ color: UP, lineWidth: 1 }).setData(
        chart.supertrend_up.map((p) => ({ time: p.time as UTCTimestamp, value: p.value })),
      );
    }
    if (chart.supertrend_down.length) {
      c.addLineSeries({ color: DOWN, lineWidth: 1 }).setData(
        chart.supertrend_down.map((p) => ({ time: p.time as UTCTimestamp, value: p.value })),
      );
    }
    // Support / resistance lines.
    for (const lvl of chart.levels ?? []) {
      candles.createPriceLine({
        price: lvl.price,
        color: lvl.kind === "resistance" ? DOWN : UP,
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: lvl.label,
      });
    }
    // Buy / sell markers.
    if (chart.markers?.length) {
      candles.setMarkers(
        chart.markers.map((mk) => ({
          time: mk.time as UTCTimestamp,
          position: mk.side === "buy" ? ("belowBar" as const) : ("aboveBar" as const),
          color: mk.side === "buy" ? UP : DOWN,
          shape: mk.side === "buy" ? ("arrowUp" as const) : ("arrowDown" as const),
          text: mk.side === "buy" ? "Buy" : "Sell",
        })),
      );
    }
    c.timeScale().fitContent();
    return () => c.remove();
  }, [chart]);
  return <div ref={ref} className="absolute inset-0" />;
}

// --- Equity curve + tearsheet ----------------------------------------------

function EquityPanel({ bt }: { bt: BacktestPayload }) {
  const m = bt.metrics ?? {};
  const total = Number(m.total_pnl ?? 0);
  return (
    <div className="flex h-full flex-col">
      <div className="relative flex-1">
        {bt.equity?.length ? <EquityChart bt={bt} /> : <Empty text={`${bt.underlying}: no trades to chart for this window.`} />}
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-0.5 border-t border-hal-red/15 px-3 py-2 font-mono text-[11px]">
        <Stat label="Trades" value={num(m.trades)} />
        <Stat label="Win" value={typeof m.win_rate === "number" ? pct(m.win_rate) : "—"} />
        <Stat label="Total" value={money(m.total_pnl ?? null)} color={total >= 0 ? UP : DOWN} />
        <Stat label="PF" value={m.profit_factor == null ? "—" : String(m.profit_factor)} />
        <Stat label="Sharpe" value={num(m.sharpe_per_trade)} />
        <Stat label="Payoff" value={m.payoff_ratio == null ? "—" : `${m.payoff_ratio}:1`} />
      </div>
    </div>
  );
}

function EquityChart({ bt }: { bt: BacktestPayload }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || !bt.equity.length) return;
    const c: IChartApi = createChart(el, {
      width: el.clientWidth,
      height: el.clientHeight,
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: "#0a0a0d" }, textColor: "#b2b5be", fontSize: 11 },
      grid: { vertLines: { color: "#1b1f2a" }, horzLines: { color: "#1b1f2a" } },
      rightPriceScale: { borderColor: "#2a2e39" },
      timeScale: { borderColor: "#2a2e39", timeVisible: false },
    });
    const s = c.addLineSeries({ color: AMBER, lineWidth: 2 });
    // lightweight-charts requires strictly-ascending times (else setData throws
    // and blanks the chart). Sort, then nudge ties — same guard as BacktestStage.
    const sorted = [...bt.equity].sort((a, b) => a.t - b.t);
    const data: { time: UTCTimestamp; value: number }[] = [];
    let last = -Infinity;
    for (const p of sorted) {
      let t = p.t;
      if (t <= last) t = last + 1;
      last = t;
      data.push({ time: t as UTCTimestamp, value: p.value });
    }
    s.setData(data);
    s.createPriceLine({ price: 0, color: "#6a6a72", lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: true, title: "B/E" });
    c.timeScale().fitContent();
    return () => c.remove();
  }, [bt]);
  return <div ref={ref} className="absolute inset-0" />;
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

// --- Committee verdict ------------------------------------------------------

function parseVerdict(idea: TradeIdea): { decision: string; score: number | null; color: string } {
  const md = idea.markdown || "";
  const sm = md.match(/score\s+(\d+)\s*\/\s*100/i);
  const score = sm ? Number(sm[1]) : null;
  let decision: string;
  if (idea.kind === "hold") decision = "HOLD";
  else if (/DO NOT TRADE|🔴|\bPASS\b/i.test(md)) decision = "PASS";
  else if (/PUT ON THE TRADE|🟢|\bTRADE\b/i.test(md)) decision = "TRADE";
  else decision = idea.kind.toUpperCase();
  const color = decision === "TRADE" ? UP : decision === "PASS" ? DOWN : AMBER;
  return { decision, score, color };
}

function Verdict({ idea }: { idea: TradeIdea }) {
  const { decision, score, color } = parseVerdict(idea);
  const ringValue = score != null ? score / 100 : decision === "TRADE" ? 0.7 : 0.4;
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between gap-3 border-b border-hal-red/15 px-4 py-3">
        <div className="flex flex-col">
          <span className="text-2xl font-bold leading-none" style={{ color }}>
            {decision}
          </span>
          <span className="mt-1 text-[11px] uppercase tracking-[2px] text-hal-text-dim">{idea.symbol}</span>
        </div>
        <div className="flex flex-col items-center">
          <Ring value={ringValue} size={48} color={color} />
          <span className="mt-1 text-[9px] uppercase tracking-[1px] text-hal-text-dim">
            {score != null ? `${score}/100` : "conf"}
          </span>
        </div>
      </div>
      <div
        className="md flex-1 select-text overflow-y-auto whitespace-pre-wrap break-words px-4 py-3 text-[12px] leading-[1.55] text-hal-text [scrollbar-color:rgba(255,30,30,0.3)_transparent] [scrollbar-width:thin]"
        dangerouslySetInnerHTML={{ __html: renderMessage(idea.markdown).html }}
      />
    </div>
  );
}

// --- Positions table --------------------------------------------------------

function PositionsTable({ positions, ready }: { positions: BrokerPosition[]; ready: boolean }) {
  if (!ready) return <Empty text="Alpaca isn't configured. Set ALPACA_API_KEY / ALPACA_SECRET_KEY in .env." />;
  if (positions.length === 0) return <Empty text="(no open positions)" />;
  return (
    <div className="h-full overflow-y-auto [scrollbar-color:rgba(255,30,30,0.3)_transparent] [scrollbar-width:thin]">
      {positions.map((p) => {
        const pl = p.unrealized_pl ?? 0;
        const up = pl >= 0;
        return (
          <div key={p.symbol} className="flex items-center justify-between gap-3 border-b border-hal-red/10 px-3 py-2 font-mono">
            <div className="min-w-0">
              <div className="truncate text-[13px] font-bold text-hal-text">{p.symbol}</div>
              <div className="text-[10px] text-hal-text-dim">
                {p.side.toUpperCase()} {p.qty} · entry {money(p.avg_entry_price, 2)} · last {money(p.current_price, 2)}
              </div>
            </div>
            <div className="shrink-0 text-right">
              <div className="text-[13px] font-bold" style={{ color: up ? UP : DOWN }}>
                {up ? "+" : ""}
                {money(pl, 2)}
              </div>
              <div className="text-[10px]" style={{ color: up ? UP : DOWN }}>
                {pct(p.unrealized_plpc)}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
