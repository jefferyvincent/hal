// TradeScan-style watch-list board for the immersive "watchlist" source.
// Renders the payload watchlist.py pushes via open_view(kind="watchlist"):
// one row per watched symbol with last price, day % change, volume, and news.
// Polls the server every REFRESH_MS for fresh quotes while it's open.

import { useEffect } from "react";
import { useImmersive } from "@/stores/immersive";
import { useConnection } from "@/stores/connection";
import type { WatchlistRow } from "@/types";

const REFRESH_MS = 5_000;
const UP = "#26a69a";
const DOWN = "#ef5350";

function fmtPrice(v?: number | null): string {
  return typeof v === "number" ? v.toFixed(2) : "—";
}

function fmtPct(v?: number | null): string {
  if (typeof v !== "number") return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}

function fmtVol(v?: number | null): string {
  if (typeof v !== "number") return "—";
  if (v >= 1e9) return `${(v / 1e9).toFixed(2)}B`;
  if (v >= 1e6) return `${(v / 1e6).toFixed(2)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
  return String(v);
}

function fmtAgo(t?: number | null): string {
  if (!t) return "";
  const secs = Date.now() / 1000 - t;
  if (secs < 90) return "just now";
  if (secs < 3600) return `${Math.round(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.round(secs / 3600)}h ago`;
  return `${Math.round(secs / 86400)}d ago`;
}

export default function WatchlistStage() {
  const wl = useImmersive((s) => s.watchlist);
  const refresh = useConnection((s) => s.refreshWatchlist);

  // Poll for fresh quotes while the board is mounted.
  useEffect(() => {
    const id = setInterval(refresh, REFRESH_MS);
    return () => clearInterval(id);
  }, [refresh]);

  if (!wl) return null;
  const rows = wl.rows ?? [];

  return (
    <div className="absolute inset-0 flex flex-col bg-[#0c0e12] font-mono text-hal-text">
      <div className="flex items-center justify-between border-b border-hal-red/25 px-5 py-3">
        <span className="text-[13px] font-semibold uppercase tracking-[4px] text-hal-red">
          Watchlist · {rows.length}
        </span>
        <span className="text-[10px] uppercase tracking-[2px] text-hal-text-dim">
          live · refreshes {REFRESH_MS / 1000}s
        </span>
      </div>

      {rows.length === 0 ? (
        <div className="flex flex-1 items-center justify-center text-[13px] text-hal-text-dim">
          No symbols yet — say "watch the news for SPY" to add one.
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto [scrollbar-color:rgba(255,30,30,0.3)_transparent] [scrollbar-width:thin]">
          <table className="w-full border-collapse text-[13px]">
            <thead className="sticky top-0 bg-[#0c0e12]">
              <tr className="text-[9px] uppercase tracking-[2px] text-hal-text-dim">
                <th className="px-5 py-2 text-left font-normal">Symbol</th>
                <th className="px-3 py-2 text-right font-normal">Last</th>
                <th className="px-3 py-2 text-right font-normal">Chg%</th>
                <th className="px-3 py-2 text-right font-normal">Volume</th>
                <th className="px-5 py-2 text-left font-normal">News</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r: WatchlistRow) => {
                const chg = typeof r.change_pct === "number" ? r.change_pct : null;
                const color = chg == null ? undefined : chg >= 0 ? UP : DOWN;
                return (
                  <tr
                    key={r.symbol}
                    className="border-t border-white/5 hover:bg-hal-red/[0.05]"
                  >
                    <td className="px-5 py-2.5 text-[15px] font-semibold tracking-wide text-white">
                      {r.symbol}
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums">
                      {r.error ? (
                        <span className="text-[10px] text-hal-text-dim">{r.error}</span>
                      ) : (
                        fmtPrice(r.price)
                      )}
                    </td>
                    <td
                      className="px-3 py-2.5 text-right tabular-nums"
                      style={color ? { color } : undefined}
                    >
                      {fmtPct(chg)}
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-hal-text-dim">
                      {fmtVol(r.volume)}
                    </td>
                    <td className="px-5 py-2.5 text-left">
                      {r.news_count > 0 ? (
                        <div className="flex flex-col">
                          <span className="truncate text-[12px] text-hal-text" title={r.latest_headline ?? ""}>
                            {r.latest_headline ?? `${r.news_count} headline${r.news_count === 1 ? "" : "s"}`}
                          </span>
                          <span className="text-[9px] uppercase tracking-[1px] text-hal-amber">
                            {r.news_count} · {fmtAgo(r.latest_at)}
                          </span>
                        </div>
                      ) : (
                        <span className="text-[10px] text-hal-text-dim">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
