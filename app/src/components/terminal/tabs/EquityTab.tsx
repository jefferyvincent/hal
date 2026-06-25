// F4 EQUITY — a FinceptTerminal-style Equity Research dashboard plus an
// interactive DCF. Fundamentals come from the server (hal/sensory/fundamentals.py,
// Nasdaq keyless) keyed by symbol: today's trading, valuation, analyst coverage,
// company profile and annual statements. Margins and growth rates are derived
// here from the statements; the DCF runs here too so the assumptions (growth,
// discount, terminal growth, horizon) recalc instantly as you drag the sliders.
//
// The DCF model: project the latest free cash flow forward N years at `growth`,
// discount each year at `discount`, add a Gordon-growth terminal value, then
// bridge enterprise → equity value with net cash and divide by shares.

import { useEffect, useMemo, useState } from "react";
import { useConnection } from "@/stores/connection";
import { useTerminal } from "@/stores/terminal";
import { Panel, Stat, Empty, money, pct, compact, num, POS, NEG, AMBER } from "@/components/terminal/primitives";
import CoverageGraph from "@/components/terminal/CoverageGraph";
import TerminalChart from "@/components/terminal/TerminalChart";
import { DragHandle, clamp } from "@/components/terminal/resize";
import type { EquityFundamentals } from "@/types";

/** True when the viewport is wide enough for the side-by-side three-column
 *  layout (and thus for the draggable column dividers). */
function useWideLayout(): boolean {
  const [wide, setWide] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 1280px)");
    const on = () => setWide(mq.matches);
    on();
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return wide;
}

// --- derived metrics --------------------------------------------------------

/** Ratio of two statement lines, null-safe (denominator must be non-zero). */
function ratio(numer: number | null | undefined, denom: number | null | undefined): number | null {
  return numer != null && denom != null && denom !== 0 ? numer / denom : null;
}

/** Year-over-year growth, null-safe. Uses |prev| as the base so a sign flip
 *  doesn't invert the direction of the change. */
function growth(curr: number | null | undefined, prev: number | null | undefined): number | null {
  return curr != null && prev != null && prev !== 0 ? curr / Math.abs(prev) - 1 : null;
}

interface Assumptions {
  growth: number; // annual FCF growth, fraction
  discount: number; // WACC / discount rate, fraction
  terminal: number; // perpetual growth, fraction
  years: number; // explicit projection horizon
}

const DEFAULTS: Assumptions = { growth: 0.08, discount: 0.09, terminal: 0.025, years: 10 };

function baseFcf(eq: EquityFundamentals): number | null {
  const a = eq.annual[0];
  if (!a) return null;
  if (a.free_cash_flow != null) return a.free_cash_flow;
  if (a.operating_cash_flow != null && a.capex != null) return a.operating_cash_flow - a.capex;
  return null;
}

function runDcf(eq: EquityFundamentals, asm: Assumptions) {
  const fcf0 = baseFcf(eq);
  const shares = eq.shares_outstanding;
  if (fcf0 == null || !shares || shares <= 0) return null;
  // Terminal growth must stay below the discount rate or the Gordon formula
  // blows up / goes negative.
  const tg = Math.min(asm.terminal, asm.discount - 0.005);

  let pv = 0;
  let fcf = fcf0;
  for (let y = 1; y <= asm.years; y++) {
    fcf = fcf * (1 + asm.growth);
    pv += fcf / Math.pow(1 + asm.discount, y);
  }
  const terminalValue = (fcf * (1 + tg)) / (asm.discount - tg);
  const pvTerminal = terminalValue / Math.pow(1 + asm.discount, asm.years);
  const enterprise = pv + pvTerminal;

  const a = eq.annual[0];
  const netCash = (a?.cash ?? 0) - (a?.total_debt ?? 0);
  const equityValue = enterprise + netCash;
  const fairValue = equityValue / shares;
  const upside = eq.price ? fairValue / eq.price - 1 : null;
  return { fcf0, enterprise, equityValue, fairValue, upside, pvTerminal, netCash };
}

export default function EquityTab() {
  const symbol = useTerminal((s) => s.symbol);
  const equity = useConnection((s) => s.equity);
  const loading = useConnection((s) => s.equityLoading);
  const loadEquity = useConnection((s) => s.loadEquity);
  const equityChart = useConnection((s) => s.equityChart);
  const chartLoading = useConnection((s) => s.equityChartLoading);
  const loadEquityChart = useConnection((s) => s.loadEquityChart);
  const [asm, setAsm] = useState<Assumptions>(DEFAULTS);

  // Side-column widths (px), user-draggable at xl. Column A flexes to fill.
  const wide = useWideLayout();
  const [colW, setColW] = useState({ b: 330, c: 280 });

  const eq = equity[symbol] ?? null;
  const chart = equityChart[symbol] ?? null;

  // Fetch fundamentals + the daily chart for the active symbol once each (both
  // caches keyed by symbol so switching tickers back doesn't refetch).
  useEffect(() => {
    if (!equity[symbol] && loading !== symbol) loadEquity(symbol);
    if (!equityChart[symbol] && chartLoading !== symbol) loadEquityChart(symbol);
  }, [symbol, equity, loading, loadEquity, equityChart, chartLoading, loadEquityChart]);

  const dcf = useMemo(() => (eq ? runDcf(eq, asm) : null), [eq, asm]);

  if (!eq) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-center text-[11px] uppercase tracking-[2px] text-term-text-dim">
          {loading === symbol ? `Loading ${symbol} fundamentals…` : `No data for ${symbol}`}
          <div className="mt-2 text-[9px] text-term-muted">
            Type a ticker in the command line (e.g. <span className="text-term-amber">AAPL</span>) to load.
          </div>
        </div>
      </div>
    );
  }

  if (eq.error) {
    return <Empty text={`${symbol}: ${eq.error}`} />;
  }

  const s = eq.summary;
  const latest = eq.annual[0];
  const prior = eq.annual[1];

  const grossMargin = ratio(latest?.gross_profit, latest?.revenue);
  const opMargin = ratio(latest?.operating_income, latest?.revenue);
  const netMargin = ratio(latest?.net_income, latest?.revenue);
  const revGrowth = growth(latest?.revenue, prior?.revenue);
  const niGrowth = growth(latest?.net_income, prior?.net_income);
  const fcfGrowth = growth(latest?.free_cash_flow, prior?.free_cash_flow);

  // Upside implied by the consensus 1y target vs the live price.
  const targetUpside = eq.target_price && eq.price ? eq.target_price / eq.price - 1 : null;
  const changePos = (s.change_pct ?? 0) >= 0;

  return (
    <div className="flex h-full flex-col gap-2 overflow-auto p-2">
      {/* Header / quote */}
      <div className="flex flex-wrap items-baseline justify-between gap-2 border border-term-border bg-term-panel px-3 py-2">
        <div className="flex flex-col">
          <div>
            <span className="text-[18px] font-bold text-term-amber">{eq.symbol}</span>
            <span className="ml-2 text-[12px] text-term-text">{eq.name ?? ""}</span>
          </div>
          {(eq.sector || eq.industry) && (
            <span className="text-[9px] uppercase tracking-[2px] text-term-text-dim">
              {[eq.sector, eq.industry].filter(Boolean).join(" · ")}
            </span>
          )}
        </div>
        <div className="text-right">
          <span className="text-[20px] font-bold text-term-text">{money(eq.price, 2)}</span>
          <span className="ml-2 text-[12px] font-bold" style={{ color: changePos ? POS : NEG }}>
            {s.change == null ? "" : `${changePos ? "+" : ""}${s.change.toFixed(2)}`} {pct(s.change_pct, 2)}
          </span>
          <span className="ml-2 text-[9px] text-term-text-dim">{eq.currency ?? "USD"}</span>
        </div>
      </div>

      {/* Today's trading strip */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
        <Stat label="Day High" value={money(s.day_high, 2)} />
        <Stat label="Day Low" value={money(s.day_low, 2)} />
        <Stat label="Prev Close" value={money(s.prev_close, 2)} />
        <Stat label="Volume" value={s.volume == null ? "—" : compact(s.volume).replace("$", "")} />
        <Stat label="Avg Vol" value={s.avg_volume == null ? "—" : compact(s.avg_volume).replace("$", "")} />
        <Stat label="Market Cap" value={compact(eq.market_cap)} />
      </div>

      {/* Three-region research layout: financials · valuation/DCF · coverage.
          At xl it's a flex row with draggable dividers; below xl it stacks. */}
      <div className="flex flex-col gap-2 xl:flex-row">
        {/* Column A — chart + fundamentals (flexes to fill) */}
        <div className="flex min-w-0 flex-1 flex-col gap-2">
          <Panel title="Price · Daily" resizable defaultHeight={280} minHeight={180} bodyClassName="p-0">
            {chart && !chart.error && chart.candles?.length ? (
              <TerminalChart chart={chart} />
            ) : (
              <Empty
                text={
                  chart?.error
                    ? `chart unavailable: ${chart.error}`
                    : chartLoading === symbol
                      ? "Loading chart…"
                      : "No chart"
                }
              />
            )}
          </Panel>

          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat label="P/E" value={num(s.pe, 1)} />
            <Stat label="EPS" value={s.eps == null ? "—" : money(s.eps, 2)} />
            <Stat label="Div Yield" value={pct(s.dividend_yield, 2)} />
            <Stat label="Beta" value={num(s.beta, 2)} />
          </div>

          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <Panel title="Profitability">
              <div className="flex flex-col">
                <MetricRow label="Gross Margin" value={pct(grossMargin, 1)} />
                <MetricRow label="Operating Margin" value={pct(opMargin, 1)} />
                <MetricRow label="Net Margin" value={pct(netMargin, 1)} />
              </div>
            </Panel>
            <Panel title="Growth (YoY)">
              <div className="flex flex-col">
                <MetricRow label="Revenue" value={pct(revGrowth, 1)} signed={revGrowth} />
                <MetricRow label="Net Income" value={pct(niGrowth, 1)} signed={niGrowth} />
                <MetricRow label="Free Cash Flow" value={pct(fcfGrowth, 1)} signed={fcfGrowth} />
              </div>
            </Panel>
          </div>

          {/* Financial history */}
          <Panel title="Annual Financials" bodyClassName="p-0">
            {eq.annual.length === 0 ? (
              <Empty text="(no statements available)" />
            ) : (
              <table className="w-full text-[11px]">
                <thead className="sticky top-0 bg-term-panel-2 text-[9px] uppercase tracking-[1px] text-term-text-dim">
                  <tr>
                    <th className="px-2 py-1.5 text-left">Metric</th>
                    {eq.annual.map((y) => (
                      <th key={y.year} className="px-2 py-1.5 text-right">
                        {y.year}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(
                    [
                      ["Revenue", "revenue"],
                      ["Gross Profit", "gross_profit"],
                      ["Operating Income", "operating_income"],
                      ["Net Income", "net_income"],
                      ["Operating CF", "operating_cash_flow"],
                      ["CapEx", "capex"],
                      ["Free Cash Flow", "free_cash_flow"],
                      ["Total Debt", "total_debt"],
                      ["Cash", "cash"],
                    ] as const
                  ).map(([label, key]) => (
                    <tr key={key} className="border-t border-term-border/50">
                      <td className="px-2 py-1.5 text-term-text-dim">{label}</td>
                      {eq.annual.map((y) => (
                        <td key={y.year} className="px-2 py-1.5 text-right text-term-text">
                          {compact(y[key])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Panel>

          {eq.description && (
            <Panel title="Company Overview">
              <p className="p-3 text-[11px] leading-relaxed text-term-text-dim">{eq.description}</p>
            </Panel>
          )}
        </div>

        {/* Divider A│B */}
        <DragHandle
          axis="x"
          onDrag={(dx) => setColW((w) => ({ ...w, b: clamp(w.b - dx, 240, 620) }))}
          className="hidden xl:block"
        />

        {/* Column B — targets, range, profile, DCF */}
        <div className="flex flex-col gap-2 xl:shrink-0" style={wide ? { width: colW.b } : undefined}>
          <Panel title="Analyst Targets">
            <div className="flex flex-col gap-2 p-3">
              <div className="flex items-end justify-between">
                <div>
                  <div className="text-[9px] uppercase tracking-[2px] text-term-text-dim">1Y Target</div>
                  <div className="text-[20px] font-bold text-term-amber">{money(eq.target_price, 2)}</div>
                </div>
                <div className="text-right">
                  <div className="text-[9px] uppercase tracking-[2px] text-term-text-dim">Upside</div>
                  <div className="text-[16px] font-bold" style={{ color: (targetUpside ?? 0) >= 0 ? POS : NEG }}>
                    {pct(targetUpside, 1)}
                  </div>
                </div>
              </div>
              <div className="flex items-center justify-between border-t border-term-border pt-2 text-[10px]">
                <span className="uppercase tracking-[2px] text-term-text-dim">Consensus</span>
                <span className="font-bold text-term-amber">
                  {eq.analyst?.rating ?? "—"}
                  {eq.analyst?.count ? ` · ${eq.analyst.count} analysts` : ""}
                </span>
              </div>
            </div>
          </Panel>

          <Panel title="52-Week Range">
            <div className="p-3">
              <RangeBar low={s.week52_low} high={s.week52_high} value={eq.price} />
            </div>
          </Panel>

          <Panel title="Company Info">
            <div className="flex flex-col">
              <MetricRow label="Sector" value={eq.sector ?? "—"} />
              <MetricRow label="Industry" value={eq.industry ?? "—"} />
              <MetricRow label="Region" value={eq.region ?? "—"} />
              <MetricRow label="Shares Out" value={compact(eq.shares_outstanding).replace("$", "")} />
            </div>
          </Panel>

          {/* DCF panel */}
          <Panel title="DCF Valuation">
            <div className="flex flex-col gap-3 p-3">
          {dcf ? (
            <>
              <div className="flex items-end justify-between border border-term-border bg-term-panel-2 px-3 py-2">
                <div>
                  <div className="text-[9px] uppercase tracking-[2px] text-term-text-dim">Fair Value / Share</div>
                  <div className="text-[22px] font-bold text-term-amber">{money(dcf.fairValue, 2)}</div>
                </div>
                <div className="text-right">
                  <div className="text-[9px] uppercase tracking-[2px] text-term-text-dim">Upside</div>
                  <div
                    className="text-[18px] font-bold"
                    style={{ color: (dcf.upside ?? 0) >= 0 ? POS : NEG }}
                  >
                    {pct(dcf.upside, 1)}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 text-[10px]">
                <Bridge label="Base FCF (TTM)" value={compact(dcf.fcf0)} />
                <Bridge label="Net Cash" value={compact(dcf.netCash)} />
                <Bridge label="Enterprise Value" value={compact(dcf.enterprise)} />
                <Bridge label="Equity Value" value={compact(dcf.equityValue)} />
              </div>
            </>
          ) : (
            <div className="border border-term-amber-dim bg-term-amber/10 px-3 py-2 text-[10px] text-term-amber-bright">
              Not enough data for a DCF — need free cash flow and shares outstanding.
            </div>
          )}

          <div className="flex flex-col gap-2.5 border-t border-term-border pt-3">
            <Slider
              label="FCF Growth"
              value={asm.growth}
              min={-0.05}
              max={0.3}
              step={0.005}
              fmt={(v) => pct(v, 1)}
              onChange={(growth) => setAsm((a) => ({ ...a, growth }))}
            />
            <Slider
              label="Discount Rate (WACC)"
              value={asm.discount}
              min={0.04}
              max={0.18}
              step={0.0025}
              fmt={(v) => pct(v, 2)}
              onChange={(discount) => setAsm((a) => ({ ...a, discount }))}
            />
            <Slider
              label="Terminal Growth"
              value={asm.terminal}
              min={0}
              max={0.05}
              step={0.0025}
              fmt={(v) => pct(v, 2)}
              onChange={(terminal) => setAsm((a) => ({ ...a, terminal }))}
            />
            <Slider
              label="Projection Years"
              value={asm.years}
              min={5}
              max={15}
              step={1}
              fmt={(v) => String(v)}
              onChange={(years) => setAsm((a) => ({ ...a, years }))}
            />
            <button
              type="button"
              onClick={() => setAsm(DEFAULTS)}
              className="mt-1 self-start text-[9px] uppercase tracking-[2px] text-term-text-dim hover:text-term-amber"
            >
              Reset assumptions
            </button>
          </div>
        </div>
          </Panel>
        </div>

        {/* Divider B│C */}
        <DragHandle
          axis="x"
          onDrag={(dx) => setColW((w) => ({ ...w, c: clamp(w.c - dx, 220, 560) }))}
          className="hidden xl:block"
        />

        {/* Column C — analyst coverage network */}
        <div className="flex flex-col xl:shrink-0" style={wide ? { width: colW.c } : undefined}>
          <Panel title="Analyst Coverage" resizable defaultHeight={420} minHeight={240}>
            <CoverageGraph
              symbol={eq.symbol}
              brokers={eq.analyst?.brokers ?? []}
              rating={eq.analyst?.rating ?? null}
              count={eq.analyst?.count ?? null}
            />
          </Panel>
        </div>
      </div>
    </div>
  );
}

function MetricRow({
  label,
  value,
  signed,
}: {
  label: string;
  value: string;
  signed?: number | null;
}) {
  const color = signed == null ? undefined : signed >= 0 ? POS : NEG;
  return (
    <div className="flex items-center justify-between border-b border-term-border/50 px-2.5 py-1.5 last:border-b-0">
      <span className="text-[10px] uppercase tracking-[1px] text-term-text-dim">{label}</span>
      <span className="text-[11px] font-bold text-term-text" style={color ? { color } : undefined}>
        {value}
      </span>
    </div>
  );
}

function RangeBar({
  low,
  high,
  value,
}: {
  low: number | null;
  high: number | null;
  value: number | null;
}) {
  if (low == null || high == null || value == null || high <= low) {
    return <div className="text-[10px] uppercase tracking-[2px] text-term-muted">—</div>;
  }
  const pos = Math.min(1, Math.max(0, (value - low) / (high - low)));
  return (
    <div className="flex flex-col gap-1.5">
      <div className="relative h-1.5 rounded bg-term-border">
        <div className="absolute inset-y-0 left-0 rounded bg-term-amber-dim" style={{ width: `${pos * 100}%` }} />
        <div
          className="absolute top-1/2 h-3 w-1 -translate-x-1/2 -translate-y-1/2 rounded bg-term-amber"
          style={{ left: `${pos * 100}%` }}
        />
      </div>
      <div className="flex justify-between text-[10px] font-bold text-term-text-dim">
        <span>{money(low, 2)}</span>
        <span className="text-term-amber">{money(value, 2)}</span>
        <span>{money(high, 2)}</span>
      </div>
    </div>
  );
}

function Bridge({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-term-border bg-term-panel px-2 py-1.5">
      <div className="text-[8px] uppercase tracking-[1px] text-term-text-dim">{label}</div>
      <div className="text-[12px] font-bold text-term-text">{value}</div>
    </div>
  );
}

function Slider({
  label,
  value,
  min,
  max,
  step,
  fmt,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  fmt: (v: number) => string;
  onChange: (v: number) => void;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="flex items-center justify-between text-[10px] uppercase tracking-[1px] text-term-text-dim">
        {label}
        <span className="font-bold text-term-amber">{fmt(value)}</span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="h-1 w-full cursor-pointer appearance-none rounded bg-term-border [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-term-amber"
        style={{ accentColor: AMBER }}
      />
    </label>
  );
}
