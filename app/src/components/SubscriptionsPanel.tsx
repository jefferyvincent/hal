import { useEffect } from "react";
import { useConnection } from "@/stores/connection";
import { useUi } from "@/stores/ui";
import { cn } from "@/lib/cn";
import type { AlertRule } from "@/types";

function ruleSummary(r: AlertRule): string {
  const cfg =
    typeof r.config === "string"
      ? safeParse(r.config)
      : (r.config as Record<string, unknown>);
  if (r.rule_type === "pct_move") return `±${cfg.threshold_pct ?? "?"}% move`;
  if (r.rule_type === "price_cross") return `crosses ${cfg.price ?? "?"}`;
  if (r.rule_type === "volume") return `size ≥ ${cfg.min_size ?? "?"}`;
  return r.rule_type;
}

function safeParse(s: string): Record<string, unknown> {
  try {
    return JSON.parse(s);
  } catch {
    return {};
  }
}

function fmtTime(t?: number | null): string {
  if (!t) return "";
  return new Date(t * 1000).toLocaleString();
}

// Read-only view of HAL's live market subscriptions, their alert rules, and
// recently fired alerts. The engine (market.py) is server-side; this only
// displays what's running. Alerts are delivered by HAL speaking them.
export default function SubscriptionsPanel() {
  const open = useUi((s) => s.subscriptionsOpen);
  const toggle = useUi((s) => s.toggleSubscriptions);
  const subs = useConnection((s) => s.subscriptions);
  const connected = useConnection((s) => s.subscriptionsConnected);
  const events = useConnection((s) => s.alertEvents);
  const newsWatches = useConnection((s) => s.newsWatches);
  const newsArticles = useConnection((s) => s.newsArticles);
  const removeNewsWatch = useConnection((s) => s.removeNewsWatch);
  const list = useConnection((s) => s.listSubscriptions);

  useEffect(() => {
    if (open) list();
  }, [open, list]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-40 flex items-start justify-center bg-black/60 backdrop-blur-sm"
      onClick={toggle}
    >
      <aside
        onClick={(e) => e.stopPropagation()}
        className={cn(
          "mt-[70px] flex max-h-[calc(100vh-140px)] w-[460px] flex-col font-mono",
          "border border-hal-red/25 bg-[rgba(8,8,11,0.96)] shadow-[0_0_40px_rgba(0,0,0,0.7)]",
        )}
      >
        <header className="flex items-center justify-between border-b border-hal-red/20 bg-hal-red/[0.04] px-3 py-2.5 text-[9px] uppercase tracking-[4px] text-hal-red">
          <span>Subscriptions · {subs.length}</span>
          <div className="flex items-center gap-3">
            <span
              className={cn(
                "text-[9px] uppercase tracking-[2px]",
                connected ? "text-emerald-400" : "text-hal-text-dim",
              )}
            >
              {connected ? "● feed live" : "○ feed offline"}
            </span>
            <button
              type="button"
              onClick={list}
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

        <div className="overflow-y-auto p-4 [scrollbar-color:rgba(255,30,30,0.3)_transparent] [scrollbar-width:thin]">
          {subs.length === 0 ? (
            <div className="text-center text-[11px] text-hal-text-dim">
              (no active subscriptions — ask HAL to watch a ticker)
            </div>
          ) : null}

          <div className="flex flex-col gap-3">
            {subs.map((s) => (
              <article key={s.id} className="border-l-2 border-l-hal-red/40 pl-2.5">
                <div className="flex items-center justify-between">
                  <div className="text-[12px] text-hal-text">
                    {s.channel}.{s.symbol}
                  </div>
                  <div className="text-[9px] uppercase tracking-[2px] text-hal-text-dim">
                    #{s.id}
                  </div>
                </div>
                {s.note ? (
                  <div className="text-[10px] text-hal-text-dim">{s.note}</div>
                ) : null}
                {s.rules.length === 0 ? (
                  <div className="mt-1 text-[10px] text-hal-text-dim">
                    (no alert rules)
                  </div>
                ) : (
                  <ul className="mt-1 flex flex-col gap-1 border-l border-hal-amber/30 pl-2">
                    {s.rules.map((r) => (
                      <li
                        key={r.id}
                        className="flex items-center justify-between text-[10.5px] text-hal-text-dim"
                      >
                        <span className="text-hal-text">{ruleSummary(r)}</span>
                        <span>
                          {r.triggered_count}× fired
                          {r.last_triggered_at
                            ? ` · ${fmtTime(r.last_triggered_at)}`
                            : ""}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </article>
            ))}
          </div>

          {events.length > 0 ? (
            <div className="mt-4">
              <div className="mb-1.5 text-[9px] uppercase tracking-[3px] text-hal-amber">
                Recent alerts
              </div>
              <ul className="flex flex-col gap-1.5">
                {events.map((e) => (
                  <li key={e.id} className="text-[10.5px] text-hal-text-dim">
                    <span className="text-hal-text">{e.message}</span>
                    <span className="block text-[9px] text-hal-text-dim/70">
                      {fmtTime(e.fired_at)}
                      {e.spoken ? "" : " · unannounced"}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <div className="mt-5 border-t border-hal-red/15 pt-3">
            <div className="mb-1.5 text-[9px] uppercase tracking-[3px] text-hal-red">
              News watches · {newsWatches.length}
            </div>
            {newsWatches.length === 0 ? (
              <div className="text-[10.5px] text-hal-text-dim">
                (no symbols watched — ask HAL to watch news for a ticker)
              </div>
            ) : (
              <ul className="flex flex-col gap-1.5">
                {newsWatches.map((w) => (
                  <li
                    key={w.id}
                    className="flex items-center justify-between gap-2 border-l-2 border-l-hal-red/40 pl-2.5 text-[11px]"
                  >
                    <span className="text-hal-text">
                      {w.symbol}
                      {w.keywords ? (
                        <span className="text-hal-text-dim"> · {w.keywords}</span>
                      ) : null}
                    </span>
                    <span className="flex items-center gap-2">
                      <span className="text-[9px] uppercase tracking-[2px] text-hal-text-dim">
                        {w.article_count} hit{w.article_count === 1 ? "" : "s"}
                        {w.last_polled_at ? "" : " · pending"}
                      </span>
                      <button
                        type="button"
                        onClick={() => removeNewsWatch(w.id)}
                        title={`Stop watching ${w.symbol}`}
                        aria-label={`Stop watching ${w.symbol}`}
                        className="px-1 text-[12px] leading-none text-hal-text-dim hover:text-hal-red"
                      >
                        ×
                      </button>
                    </span>
                  </li>
                ))}
              </ul>
            )}

            {newsArticles.length > 0 ? (
              <div className="mt-3">
                <div className="mb-1.5 text-[9px] uppercase tracking-[3px] text-hal-amber">
                  Recent headlines
                </div>
                <ul className="flex flex-col gap-1.5">
                  {newsArticles.map((a) => (
                    <li key={a.id} className="text-[10.5px] text-hal-text-dim">
                      <a
                        href={a.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-hal-text hover:text-hal-red-glow"
                      >
                        <span className="text-hal-amber">{a.symbol}</span> {a.title}
                      </a>
                      <span className="block text-[9px] text-hal-text-dim/70">
                        {a.source ? `${a.source} · ` : ""}
                        {fmtTime(a.seen_at)}
                        {a.spoken ? "" : " · unannounced"}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        </div>
      </aside>
    </div>
  );
}
