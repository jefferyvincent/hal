"""Market-movers board for the terminal's Heatmap tab.

A fixed, market-wide view of "what's trending" — top gainers, top losers and the
most-active names — rather than the user's personal watch list. Source is
Nasdaq's keyless /api/marketmovers endpoint, hit with the same browser-ish
headers fundamentals.py/earnings.py use (no API key, no Polygon entitlement —
our Polygon plan is Options-only and 403s the stock snapshot endpoints).

One request returns several categories; we merge gainers + losers + most-active
(by dollar volume) + Nasdaq-100 movers into a single deduped board and sort by
biggest absolute % move first, so the heatmap leads with the day's real action.
"""
from __future__ import annotations

import time
from typing import Optional

import httpx

# Browser-ish headers + trusted Origin/Referer — Nasdaq's keyless API only
# returns JSON for these (same trick fundamentals.py and earnings.py use).
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
_HEADERS = {
    "User-Agent": _UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.nasdaq.com",
    "Referer": "https://www.nasdaq.com/",
}
_URL = "https://api.nasdaq.com/api/marketmovers"
_TIMEOUT = 15.0

# Raw gainers/losers are dominated by sub-dollar penny stocks, warrants and units
# that aren't useful "what's trending" signal on a trading desk. Keep the board to
# liquid, recognizable names: a price floor, alpha-only tickers, and no warrant /
# unit / right symbols (5+ chars ending W/U/R).
_MIN_PRICE = 5.0


def _is_tradeable(symbol: str, price: Optional[float]) -> bool:
    if price is None or price < _MIN_PRICE:
        return False
    if not symbol.isalpha():
        return False
    if len(symbol) >= 5 and symbol[-1] in "WUR":
        return False
    return True

# Categories whose `change` field is a percent (skip MostActiveByShareVolume,
# whose `change` is raw share volume and which is dominated by sub-dollar junk).
# Listed in dedup priority order: a symbol keeps the first category it appears in.
_CATEGORIES: list[tuple[str, str]] = [
    ("MostAdvanced", "Gainer"),
    ("MostDeclined", "Loser"),
    ("MostActiveByDollarVolume", "Active"),
    ("Nasdaq100Movers", "NDX"),
]


def _num(s: Optional[str]) -> Optional[float]:
    """Parse Nasdaq's display strings ('$21.45', '202.7300', '+4.82%', '-87.71%',
    '1,204.5') into a float. Returns None for blanks/'N/A'/unparseable."""
    if not s:
        return None
    cleaned = s.strip().lstrip("+").replace("$", "").replace("%", "").replace(",", "")
    if not cleaned or cleaned.upper() in {"N/A", "NA", "--", "UNCH"}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


async def build_payload() -> dict:
    """Merged, deduped, biggest-mover-first board of US-stock market movers.

    Each row: {symbol, name, price, change_pct (percent units), category, error}.
    Swallows fetch errors into an empty board so the tab shows a placeholder
    rather than a stuck spinner."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
            r = await client.get(_URL)
            r.raise_for_status()
            stocks = (r.json().get("data") or {}).get("STOCKS") or {}
    except Exception as e:
        return {"rows": [], "generated_at": time.time(), "error": f"{e}"}

    rows: list[dict] = []
    seen: set[str] = set()
    as_of: Optional[str] = None
    for key, label in _CATEGORIES:
        block = stocks.get(key) or {}
        as_of = as_of or block.get("dataAsOf")
        for row in (block.get("table") or {}).get("rows") or []:
            sym = str(row.get("symbol") or "").upper().strip()
            if not sym or sym in seen:
                continue
            change_pct = _num(row.get("change"))
            if change_pct is None:
                continue  # no usable % move — nothing to colour the tile with
            price = _num(row.get("lastSalePrice"))
            if not _is_tradeable(sym, price):
                continue
            seen.add(sym)
            rows.append({
                "symbol": sym,
                "name": row.get("name"),
                "price": price,
                "change_pct": change_pct,
                "category": label,
                "error": None,
            })

    rows.sort(key=lambda r: abs(r["change_pct"]), reverse=True)
    return {"rows": rows, "generated_at": time.time(), "as_of": as_of}
