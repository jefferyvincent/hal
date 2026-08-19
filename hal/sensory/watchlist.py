"""Live quote snapshot for the watch-list immersive board.

Price, prior close and day volume all come from ONE Alpaca stock snapshot per
symbol (sensory.alpaca_data.daily_stats): latestTrade for the live price,
prevDailyBar for the true prior session close that drives % change, dailyBar
for volume. News count + latest headline are joined from news.py.

The free tier's real-time stock quotes are IEX-only, so the price is live but
reflects IEX prints rather than the full SIP tape. WatchlistStage polls
build_payload() on an interval.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

import httpx

from hal.sensory import alpaca_data, news


async def _fetch_quote(client: httpx.AsyncClient, symbol: str) -> dict:
    """Live price + prior close & day volume → last price, day % change, volume."""
    stats = await alpaca_data.daily_stats(symbol, client=client)
    price, prev_close = stats["price"], stats["prev_close"]
    if price is None and prev_close is None:
        return {"error": "no data"}
    change_pct: Optional[float] = None
    if price is not None and prev_close:
        change_pct = (price - prev_close) / prev_close * 100.0
    return {"price": price, "change_pct": change_pct, "volume": stats["volume"]}


async def build_payload() -> dict:
    """One row per watched symbol: quote + news count + latest headline.
    Sorted by biggest absolute % move first (errors/unknowns last)."""
    watches = await asyncio.to_thread(news.list_watches_db, True)
    quotes: list[Any]
    if alpaca_data.is_configured() and watches:
        async with httpx.AsyncClient(timeout=15.0, headers={"User-Agent": "HAL"}) as client:
            quotes = await asyncio.gather(
                *[_fetch_quote(client, w["symbol"]) for w in watches],
                return_exceptions=True,
            )
    else:
        quotes = [{} for _ in watches]

    rows: list[dict] = []
    for w, q in zip(watches, quotes):
        if isinstance(q, Exception) or not isinstance(q, dict):
            q = {"error": "fetch failed"}
        latest = await asyncio.to_thread(news.latest_article_for_symbol, w["symbol"])
        rows.append({
            "symbol": w["symbol"],
            "price": q.get("price"),
            "change_pct": q.get("change_pct"),
            "volume": q.get("volume"),
            "news_count": w.get("article_count", 0),
            "latest_headline": latest.get("title") if latest else None,
            "latest_at": latest.get("seen_at") if latest else None,
            "error": q.get("error"),
        })

    rows.sort(
        key=lambda r: abs(r["change_pct"]) if r["change_pct"] is not None else -1.0,
        reverse=True,
    )
    return {"rows": rows, "generated_at": time.time()}
