// F6 HEATMAP — "what's trending" across the whole market. A Finviz-style grid of
// the day's biggest movers (top gainers, losers and most-active names), each tile
// colour-coded green→red by its % move and ordered biggest move first. Data is a
// fixed market-wide board from the server (hal/sensory/movers.py, Nasdaq keyless)
// — not the personal watch list — refreshed on a timer. Click a tile to centre
// the terminal on that symbol and jump to its Equity research tab.

import { useEffect } from "react";
import { useConnection } from "@/stores/connection";
import { useTerminal } from "@/stores/terminal";
import { Empty, money, POS, NEG } from "@/components/terminal/primitives";
import type { MoversRow } from "@/types";

const REFRESH_MS = 30000;
// % move that saturates a tile's colour; bigger moves all read full-strength.
const FULL_SCALE = 5;

/** change_pct arrives already in percent units (e.g. 4.82 = +4.82%), so format
 *  it directly rather than through the fraction-based pct() helper. */
function chg(p: number): string {
  return `${p >= 0 ? "+" : ""}${p.toFixed(2)}%`;
}

/** Tile background: green for up, red for down, intensity scaled by the size of
 *  the move (capped at FULL_SCALE). */
function tileColor(p: number): string {
  const mag = Math.min(Math.abs(p) / FULL_SCALE, 1);
  const alpha = 0.12 + mag * 0.78; // 0.12 (flat) → 0.90 (big move)
  const [r, g, b] = p >= 0 ? [46, 204, 113] : [255, 69, 58]; // POS / NEG as rgb
  return `rgba(${r},${g},${b},${alpha.toFixed(3)})`;
}

function ago(unixSec: number | null | undefined): string {
  if (!unixSec) return "";
  const s = Math.max(0, Date.now() / 1000 - unixSec);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

export default function HeatmapTab() {
  const board = useConnection((s) => s.moversBoard);
  const refresh = useConnection((s) => s.refreshMovers);
  const setSymbol = useTerminal((s) => s.setSymbol);
  const setTab = useTerminal((s) => s.setTab);

  // Ask the server to (re)build the board on open, then keep it live on a timer —
  // the board is a polled snapshot, not a push stream.
  useEffect(() => {
    refresh();
    const id = window.setInterval(refresh, REFRESH_MS);
    return () => window.clearInterval(id);
  }, [refresh]);

  const focus = (sym: string) => {
    setSymbol(sym);
    setTab("equity");
  };

  const rows = board?.rows ?? [];

  return (
    <div className="flex h-full flex-col gap-2 p-2">
      {/* Toolbar: count, freshness, legend, manual refresh */}
      <div className="flex items-center justify-between border border-term-border bg-term-panel px-3 py-1.5 text-[9px] uppercase tracking-[2px] text-term-text-dim">
        <span>
          <span className="font-bold text-term-amber">Trending</span> · {rows.length} movers
          {board?.as_of ? ` · ${board.as_of.replace(/^Data as of /, "")}` : board ? ` · ${ago(board.generated_at)}` : ""}
        </span>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1">
            <i className="inline-block h-2 w-2" style={{ background: NEG }} /> down
            <i className="ml-2 inline-block h-2 w-2" style={{ background: POS }} /> up
          </span>
          <button
            type="button"
            onClick={refresh}
            className="text-term-text-dim hover:text-term-amber"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Tile grid */}
      <div className="min-h-0 flex-1 overflow-auto">
        {rows.length === 0 ? (
          <Empty text={board?.error ? `Movers feed error: ${board.error}` : "Loading market movers…"} />
        ) : (
          <div className="grid grid-cols-[repeat(auto-fill,minmax(130px,1fr))] gap-1.5">
            {rows.map((r) => (
              <Tile key={r.symbol} row={r} onClick={() => focus(r.symbol)} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Tile({ row, onClick }: { row: MoversRow; onClick: () => void }) {
  const up = row.change_pct >= 0;
  return (
    <button
      type="button"
      onClick={onClick}
      title={`${row.symbol}${row.name ? ` — ${row.name}` : ""} · open in Equity`}
      className="group relative flex aspect-[5/3] flex-col justify-between overflow-hidden border border-term-border/60 px-2.5 py-2 text-left transition-colors hover:border-term-amber"
      style={{ background: tileColor(row.change_pct) }}
    >
      <div className="flex items-start justify-between gap-1">
        <span className="text-[14px] font-bold leading-none text-term-text">{row.symbol}</span>
        <span className="rounded-sm bg-term-bg/40 px-1 text-[8px] font-bold uppercase tracking-wide text-term-amber">
          {row.category}
        </span>
      </div>
      <div>
        <div className="text-[15px] font-bold leading-none" style={{ color: up ? POS : NEG }}>
          {chg(row.change_pct)}
        </div>
        <div className="mt-0.5 truncate text-[9px] text-term-text-dim">{money(row.price, 2)}</div>
      </div>
    </button>
  );
}
