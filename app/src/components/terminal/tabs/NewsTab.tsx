// F3 NEWS — the terminal's news desk. Reuses HAL's existing news plumbing: the
// per-symbol watch list (news_watches), the captured-headline feed, and the
// fired-alert log. Click a watch to filter the feed; everything streams in over
// the same WS the rest of the app uses.

import { useEffect, useState } from "react";
import { useConnection } from "@/stores/connection";
import { Panel, Empty } from "@/components/terminal/primitives";

function ago(unixSec: number | null | undefined): string {
  if (!unixSec) return "";
  const s = Math.max(0, Date.now() / 1000 - unixSec);
  if (s < 60) return `${Math.floor(s)}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return `${Math.floor(s / 86400)}d`;
}

export default function NewsTab() {
  const watches = useConnection((s) => s.newsWatches);
  const articles = useConnection((s) => s.newsArticles);
  const alerts = useConnection((s) => s.alertEvents);
  const list = useConnection((s) => s.listSubscriptions);
  const removeWatch = useConnection((s) => s.removeNewsWatch);
  const [filter, setFilter] = useState<string | null>(null);

  useEffect(() => {
    list();
  }, [list]);

  const feed = (filter ? articles.filter((a) => a.symbol === filter) : articles)
    .slice()
    .sort((a, b) => (b.published_at ?? b.seen_at) - (a.published_at ?? a.seen_at));

  return (
    <div className="grid h-full grid-cols-1 gap-2 p-2 lg:grid-cols-[260px_1fr_280px]">
      {/* Watch list */}
      <Panel
        title={`Watches · ${watches.length}`}
        right={
          <button
            type="button"
            onClick={list}
            className="text-[9px] uppercase tracking-[2px] text-term-text-dim hover:text-term-amber"
          >
            Refresh
          </button>
        }
      >
        {watches.length === 0 ? (
          <Empty text='No watches — ask HAL "watch news for NVDA"' />
        ) : (
          <ul className="divide-y divide-term-border/50">
            <li>
              <button
                type="button"
                onClick={() => setFilter(null)}
                className={`flex w-full items-center justify-between px-2.5 py-1.5 text-[11px] ${
                  filter === null ? "bg-term-panel-2 text-term-amber" : "text-term-text-dim hover:text-term-text"
                }`}
              >
                <span className="uppercase tracking-[2px]">All symbols</span>
                <span>{articles.length}</span>
              </button>
            </li>
            {watches.map((w) => (
              <li key={w.id} className="group flex items-center">
                <button
                  type="button"
                  onClick={() => setFilter(w.symbol)}
                  className={`flex flex-1 items-center justify-between px-2.5 py-1.5 text-[11px] ${
                    filter === w.symbol ? "bg-term-panel-2 text-term-amber" : "text-term-text hover:bg-term-panel-2/50"
                  }`}
                >
                  <span className="font-bold">{w.symbol}</span>
                  <span className="text-term-text-dim">
                    {w.article_count} · {ago(w.last_polled_at)}
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => removeWatch(w.id)}
                  title={`Stop watching ${w.symbol}`}
                  className="px-2 text-[11px] text-term-muted opacity-0 transition-opacity hover:text-term-red group-hover:opacity-100"
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      {/* Headline feed */}
      <Panel title={filter ? `Headlines · ${filter}` : "Headlines · All"}>
        {feed.length === 0 ? (
          <Empty text="(no headlines captured yet)" />
        ) : (
          <ul className="divide-y divide-term-border/50">
            {feed.map((a) => (
              <li key={a.id} className="px-3 py-2">
                <div className="flex items-baseline gap-2">
                  <span className="text-[10px] font-bold text-term-amber">{a.symbol}</span>
                  <span className="text-[9px] text-term-text-dim">
                    {a.source ?? "news"} · {ago(a.published_at ?? a.seen_at)} ago
                  </span>
                </div>
                <a
                  href={a.url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-0.5 block text-[12px] leading-snug text-term-text hover:text-term-amber-bright hover:underline"
                >
                  {a.title}
                </a>
                {a.summary ? (
                  <p className="mt-1 line-clamp-2 text-[10px] leading-snug text-term-text-dim">{a.summary}</p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </Panel>

      {/* Alert log */}
      <Panel title={`Alerts · ${alerts.length}`}>
        {alerts.length === 0 ? (
          <Empty text="(no alerts fired)" />
        ) : (
          <ul className="divide-y divide-term-border/50">
            {alerts
              .slice()
              .sort((a, b) => b.fired_at - a.fired_at)
              .map((e) => (
                <li key={e.id} className="px-2.5 py-1.5">
                  <div className="flex items-baseline justify-between">
                    <span className="text-[10px] font-bold text-term-cyan">{e.symbol}</span>
                    <span className="text-[9px] text-term-text-dim">{ago(e.fired_at)} ago</span>
                  </div>
                  <p className="mt-0.5 text-[10px] leading-snug text-term-text">{e.message}</p>
                </li>
              ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
