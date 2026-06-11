"""Live quote snapshot for the watch-list immersive board.

Live underlying price comes from the OPTIONS snapshot (/v3/snapshot/options/{sym}),
whose contract rows each carry underlying_asset.price — a real-time stock price
that's part of the Options plan. Prior close and day volume come from daily
aggregates (prior close is historical, so it's reliable even if stock REST lags).
News count + latest headline are joined from news.py.

There is no underlying stock websocket on the Options plan (the live WS feeds are
options contracts only), so WatchlistStage polls build_payload() on an interval —
but the price it reads is real-time, so the board still feels live.
"""
from __future__ import annotations

import asyncio
import time
from datetime import date, timedelta
from typing import Any, Optional

import httpx

from hal.sensory import news


BASE_URL: str = ""
API_KEY: str = ""


def configure(base_url: str, api_key: str) -> None:
    global BASE_URL, API_KEY
    BASE_URL = base_url
    API_KEY = api_key


def _headers() -> dict:
    return {"Authorization": f"Bearer {API_KEY}"}


async def _underlying_price(client: httpx.AsyncClient, symbol: str) -> Optional[float]:
    """Real-time underlying price from the options snapshot (Options plan): each
    contract row carries underlying_asset.price. limit=1 keeps the payload tiny —
    we only want the underlying, not the whole chain."""
    path = f"/v3/snapshot/options/{symbol}"
    try:
        r = await client.get(BASE_URL + path, headers=_headers(), params={"limit": 1})
        r.raise_for_status()
        results = r.json().get("results") or []
    except Exception:
        return None
    for row in results:
        price = (row.get("underlying_asset") or {}).get("price")
        if price is not None:
            return price
    return None


async def _daily_stats(
    client: httpx.AsyncClient, symbol: str
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """(prior_close, day_volume, last_daily_close) from daily aggregates. Prior
    close drives % change; it's historical so it's reliable even if stock REST
    lags. last_daily_close is a fallback price if the snapshot has none."""
    today = date.today()
    frm = (today - timedelta(days=7)).isoformat()  # span weekends/holidays
    path = f"/v2/aggs/ticker/{symbol}/range/1/day/{frm}/{today.isoformat()}"
    params = {"adjusted": "true", "sort": "desc", "limit": 2}
    try:
        r = await client.get(BASE_URL + path, headers=_headers(), params=params)
        r.raise_for_status()
        results = r.json().get("results") or []
    except Exception:
        return None, None, None
    if not results:
        return None, None, None
    cur = results[0]
    prev_close = results[1].get("c") if len(results) > 1 else cur.get("o")
    return prev_close, cur.get("v"), cur.get("c")


async def _fetch_quote(client: httpx.AsyncClient, symbol: str) -> dict:
    """Real-time underlying price (options snapshot) + prior close & day volume
    (daily aggregates) → last price, day % change, volume."""
    price = await _underlying_price(client, symbol)
    prev_close, volume, last_close = await _daily_stats(client, symbol)
    if price is None:
        price = last_close  # fall back to the most recent daily close
    if price is None and prev_close is None:
        return {"error": "no data"}
    change_pct: Optional[float] = None
    if price is not None and prev_close:
        change_pct = (price - prev_close) / prev_close * 100.0
    return {"price": price, "change_pct": change_pct, "volume": volume}


async def build_payload() -> dict:
    """One row per watched symbol: quote + news count + latest headline.
    Sorted by biggest absolute % move first (errors/unknowns last)."""
    watches = await asyncio.to_thread(news.list_watches_db, True)
    quotes: list[Any]
    if API_KEY and watches:
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
