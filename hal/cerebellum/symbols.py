"""Company-name -> ticker resolution.

Lets Jeffery speak a company name ("chart Apple", "backtest Tesla") and have it
resolve to a ticker (AAPL, TSLA). Used by the deterministic chart/backtest
routes and by render_chart so the model's show_chart calls accept names too.
"""
from __future__ import annotations

import re

import httpx


# Spoken company name -> ticker. Lets Jeffery say "chart Apple" / "backtest
# Tesla" and have it resolve to AAPL / TSLA, the same way the index aliases
# resolve "the Dow" -> DIA. Keys are lowercase, single-spaced; include the
# obvious spoken variants (with/without "inc", possessives, "coca cola" and
# "coca-cola"). Names that are also common English words (Target, Block,
# Square, Visa, Gap, Now) are deliberately omitted: this map is scanned inside
# a full sentence, so an ambiguous word would mis-fire (e.g. "set a price
# target"). The long tail is handled at runtime by _resolve_symbol_online.
_COMPANY_TICKERS: dict[str, str] = {
    "apple": "AAPL",
    "microsoft": "MSFT",
    "nvidia": "NVDA",
    "tesla": "TSLA",
    "amazon": "AMZN",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "meta": "META",
    "facebook": "META",
    "netflix": "NFLX",
    "amd": "AMD",
    "advanced micro devices": "AMD",
    "broadcom": "AVGO",
    "palantir": "PLTR",
    "intel": "INTC",
    "micron": "MU",
    "qualcomm": "QCOM",
    "coinbase": "COIN",
    "paypal": "PYPL",
    "disney": "DIS",
    "walmart": "WMT",
    "costco": "COST",
    "starbucks": "SBUX",
    "mcdonalds": "MCD",
    "mcdonald's": "MCD",
    "nike": "NKE",
    "boeing": "BA",
    "ford": "F",
    "general motors": "GM",
    "jpmorgan": "JPM",
    "jp morgan": "JPM",
    "goldman sachs": "GS",
    "bank of america": "BAC",
    "berkshire": "BRK.B",
    "berkshire hathaway": "BRK.B",
    "coca cola": "KO",
    "coca-cola": "KO",
    "pepsi": "PEP",
    "pepsico": "PEP",
    "exxon": "XOM",
    "exxonmobil": "XOM",
    "chevron": "CVX",
    "pfizer": "PFE",
    "moderna": "MRNA",
    "johnson and johnson": "JNJ",
    "johnson & johnson": "JNJ",
    "uber": "UBER",
    "airbnb": "ABNB",
    "shopify": "SHOP",
    "salesforce": "CRM",
    "oracle": "ORCL",
    "adobe": "ADBE",
    "spotify": "SPOT",
    "robinhood": "HOOD",
    "microstrategy": "MSTR",
    "supermicro": "SMCI",
    "super micro": "SMCI",
    "eli lilly": "LLY",
    "mastercard": "MA",
    "gamestop": "GME",
    "general electric": "GE",
}

# One alternation of all company names, longest-first so multi-word names win
# over a shorter name they contain ("berkshire hathaway" before "berkshire").
_COMPANY_NAME_RE = re.compile(
    r"\b(" + "|".join(
        re.escape(name)
        for name in sorted(_COMPANY_TICKERS, key=len, reverse=True)
    ) + r")\b",
    re.IGNORECASE,
)

# A clean ticker: 1-5 letters, optional .B / -A class suffix (BRK.B, RDS-A).
_TICKER_SHAPE = re.compile(r"[A-Z]{1,5}([.\-][A-Z]{1,2})?$")

# Cache name -> resolved ticker for the online fallback so we don't re-hit the
# search API for a name Jeffery repeats.
_NAME_SYMBOL_CACHE: dict[str, str] = {}


def _resolve_company_name(text: str) -> str | None:
    """Scan `text` for a known company name and return its ticker, else None.
    Offline and instant — used by the deterministic chart/backtest routes."""
    if not text:
        return None
    m = _COMPANY_NAME_RE.search(text)
    if not m:
        return None
    key = re.sub(r"\s+", " ", m.group(1).lower().strip())
    return _COMPANY_TICKERS.get(key)


async def _resolve_symbol_online(name: str) -> str | None:
    """Resolve a company name we don't have mapped (e.g. 'Datadog') to a ticker
    via Webull's public search API. Returns the best US-equity match, else
    None. Cached. Network failures degrade to None (caller keeps the raw text)."""
    kw = (name or "").strip()
    if not kw:
        return None
    cache_key = kw.lower()
    if cache_key in _NAME_SYMBOL_CACHE:
        return _NAME_SYMBOL_CACHE[cache_key]
    url = "https://quotes-gw.webullfintech.com/api/search/pc/tickers"
    params = {"keyword": kw, "pageIndex": 1, "pageSize": 5, "regionId": 6}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
    except Exception:
        return None
    for item in data.get("data") or []:
        sym = (item.get("symbol") or "").upper().strip()
        if sym and _TICKER_SHAPE.match(sym):
            _NAME_SYMBOL_CACHE[cache_key] = sym
            return sym
    return None


async def _resolve_symbol(raw: str) -> str | None:
    """Turn whatever names a symbol (a clean ticker OR a spoken company name)
    into a ticker. Order: known-name map -> already-a-ticker passthrough ->
    online name search. Used by render_chart so both the model's show_chart
    calls and the deterministic routes accept company names. Returns None only
    for empty input; otherwise always yields a best-effort symbol."""
    s = (raw or "").strip()
    if not s:
        return None
    hit = _resolve_company_name(s)
    if hit:
        return hit
    up = s.upper()
    if _TICKER_SHAPE.match(up):
        return up
    return (await _resolve_symbol_online(s)) or up
