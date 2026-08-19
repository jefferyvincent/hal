"""Alpaca market data for HAL — the single source of bars, chains and clock.

Replaces Massive/Polygon, whose options entitlement lapsed (the chain and
reference endpoints 403 "not entitled"). Everything here runs on the SAME
ALPACA_API_KEY/ALPACA_SECRET_KEY pair that already places orders in
sensory.broker, so there is no second subscription to keep alive.

What the free tier actually gives us (probed, not assumed):
- Stock bars, any timeframe, full history on the consolidated SIP tape —
  except the most recent ~15 minutes, which 403s ("subscription does not
  permit querying recent SIP data"). _sip_end() clamps every bar request to
  that boundary; live prices come from the snapshot helpers instead.
- Option chain snapshots WITH greeks and impliedVolatility on the free
  "indicative" feed. Real-time OPRA is a PAID upgrade (Algo Trader Plus);
  on the Basic plan feed=opra 403s "OPRA agreement is not signed" — that is a
  subscription gate, not a form. Set ALPACA_OPTION_FEED=opra only after
  upgrading.
- Historical option bars back to roughly Jan 2024, and expired-contract
  discovery via status=inactive. That bounds backtests to ~2.5 years.

Two Alpaca quirks this module hides from callers:
- Open interest is NOT on the chain snapshot; it lives on the contracts
  endpoint. option_chain() joins the two on the OCC symbol.
- Alpaca uses bare OCC symbols (SPY260918C00770000); Polygon/Massive used an
  "O:" prefix. _occ() strips it so old callers and stored tickers still work.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

import httpx


DATA_URL = "https://data.alpaca.markets"

API_KEY: str = ""
SECRET_KEY: str = ""
TRADING_URL: str = "https://paper-api.alpaca.markets"
# Options feed: "indicative" (free, carries greeks + IV) or "opra" (real-time
# NBBO, requires the paid Algo Trader Plus plan). Overridable via config.
OPTION_FEED: str = "indicative"

# SIP is denied for the most recent 15 minutes on the free tier; bar requests
# are clamped to this far back so they stay entitled (see _sip_end).
_SIP_DELAY = timedelta(minutes=16)

_TIMEOUT = 30.0
_MAX_PAGES = 20  # backstop against an unbounded next_page_token loop

# Alpaca's OPRA history begins here — verified by probing several 2024 contracts,
# every one of which starts on this exact date. Backtests are clamped to it, so
# any requested window earlier than this silently returns nothing otherwise.
OPTION_HISTORY_START = date(2024, 1, 18)


def configure(
    api_key: str, secret_key: str, paper: bool = True, option_feed: str = "indicative"
) -> None:
    global API_KEY, SECRET_KEY, TRADING_URL, OPTION_FEED
    API_KEY = api_key
    SECRET_KEY = secret_key
    TRADING_URL = (
        "https://paper-api.alpaca.markets" if paper else "https://api.alpaca.markets"
    )
    OPTION_FEED = option_feed if option_feed in ("indicative", "opra") else "indicative"


def is_configured() -> bool:
    return bool(API_KEY and SECRET_KEY)


def _headers() -> dict[str, str]:
    return {"APCA-API-KEY-ID": API_KEY, "APCA-API-SECRET-KEY": SECRET_KEY}


# --- symbol + time helpers --------------------------------------------------

def _occ(symbol: str) -> str:
    """Bare OCC symbol. Tolerates the legacy Polygon/Massive 'O:' prefix that
    may still be stored in ws_subscriptions rows or cached backtest results."""
    s = (symbol or "").strip().upper()
    return s[2:] if s.startswith("O:") else s


def _unix(ts: str) -> int:
    """RFC3339 ('2026-07-01T04:00:00Z') -> unix SECONDS."""
    return int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp())


def _iso(d: Any) -> str:
    """date | datetime | str -> the date/RFC3339 string Alpaca accepts."""
    if isinstance(d, datetime):
        return d.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(d, date):
        return d.isoformat()
    return str(d)


def _sip_end(end: Any) -> str:
    """The `end` to send so a SIP request stays inside the free tier.

    Alpaca serves the full consolidated tape for anything older than ~15
    minutes and 403s ("subscription does not permit querying recent SIP data")
    the moment a window reaches into that recent slice — and a date-only end
    like '2026-08-19' means END of that day, so "today" counts as reaching in.

    Clamping the window to now-16m keeps every request on SIP rather than
    downgrading the whole range to IEX, which carries only a few percent of
    volume and would quietly distort bars used for HV, regime and backtests.
    Callers that genuinely need the last few minutes use the snapshot helpers
    (latest_prices / daily_stats), which run on the real-time IEX feed.
    """
    cutoff = datetime.now(timezone.utc) - _SIP_DELAY
    if end is None:
        return _iso(cutoff)
    parsed: Any = end
    if isinstance(parsed, str):
        try:
            parsed = (date.fromisoformat(parsed) if len(parsed.strip()) == 10
                      else datetime.fromisoformat(parsed.replace("Z", "+00:00")))
        except ValueError:
            return _iso(cutoff)
    # datetime is a subclass of date, so it must be tested first.
    if isinstance(parsed, datetime):
        aware = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        return _iso(min(aware, cutoff))
    if isinstance(parsed, date):
        # A date-only end covers that whole day; only clamp if it reaches today.
        return _iso(cutoff) if parsed >= cutoff.date() else _iso(parsed)
    return _iso(cutoff)


def _shape_bars(raw: list[dict]) -> list[dict]:
    """Alpaca bar rows -> HAL's {t: unix SECONDS, o, h, l, c, v}."""
    out: list[dict] = []
    for b in raw:
        try:
            out.append({
                "t": _unix(b["t"]),
                "o": b["o"], "h": b["h"], "l": b["l"], "c": b["c"],
                "v": b.get("v", 0),
            })
        except (KeyError, ValueError, TypeError):
            continue
    return out


# --- HTTP -------------------------------------------------------------------

async def _get(client: httpx.AsyncClient, url: str, params: dict) -> dict:
    r = await client.get(url, headers=_headers(), params=params, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json() or {}


async def _paged(
    client: httpx.AsyncClient, url: str, params: dict, collect: str
) -> Any:
    """Follow next_page_token, merging the `collect` key across pages. That key
    is a dict for the multi-symbol bar/snapshot endpoints and a list for the
    contracts endpoint, so both shapes are handled."""
    merged: Any = None
    page = dict(params)
    for _ in range(_MAX_PAGES):
        body = await _get(client, url, page)
        chunk = body.get(collect)
        if isinstance(chunk, dict):
            if merged is None:
                merged = {}
            for k, v in chunk.items():
                merged.setdefault(k, []).extend(v if isinstance(v, list) else [v])
        elif isinstance(chunk, list):
            merged = (merged or []) + chunk
        token = body.get("next_page_token")
        if not token:
            break
        page["page_token"] = token
    return merged if merged is not None else ({} if collect != "option_contracts" else [])


# --- stock bars -------------------------------------------------------------

async def stock_bars(
    symbol: str,
    timeframe: str = "1Day",
    start: Any = None,
    end: Any = None,
    limit: int = 10000,
    client: Optional[httpx.AsyncClient] = None,
) -> list[dict]:
    """Daily/intraday OHLCV for one equity or ETF, oldest first.
    Returns [{t: unix seconds, o, h, l, c, v}]; [] when unconfigured."""
    if not is_configured():
        return []
    sym = (symbol or "").strip().upper()
    params: dict[str, Any] = {
        "symbols": sym, "timeframe": timeframe,
        "limit": limit, "adjustment": "all", "sort": "asc",
        "feed": "sip", "end": _sip_end(end),
    }
    if start is not None:
        params["start"] = _iso(start)

    async def _run(c: httpx.AsyncClient) -> list[dict]:
        bars = await _paged(c, f"{DATA_URL}/v2/stocks/bars", params, "bars")
        return _shape_bars((bars or {}).get(sym) or [])

    if client is not None:
        return await _run(client)
    async with httpx.AsyncClient() as c:
        return await _run(c)


async def daily_closes(symbol: str, lookback_days: int = 400) -> list[float]:
    """Adjusted daily closes, oldest->newest. The realized-vol / regime input."""
    start = datetime.now(timezone.utc).date() - timedelta(days=lookback_days)
    bars = await stock_bars(symbol, "1Day", start=start)
    return [b["c"] for b in bars if b.get("c") is not None]


async def latest_prices(
    symbols: list[str], client: Optional[httpx.AsyncClient] = None
) -> dict[str, float]:
    """Latest trade price per symbol from the stock snapshot. Symbols that
    fail are omitted, matching charting.current_prices' contract."""
    syms = [s for s in dict.fromkeys(s.strip().upper() for s in symbols) if s]
    if not syms or not is_configured():
        return {}

    async def _run(c: httpx.AsyncClient) -> dict[str, float]:
        body = await _get(c, f"{DATA_URL}/v2/stocks/snapshots",
                          {"symbols": ",".join(syms), "feed": "iex"})
        out: dict[str, float] = {}
        for sym, snap in (body or {}).items():
            px = ((snap or {}).get("latestTrade") or {}).get("p")
            if px is None:
                px = ((snap or {}).get("dailyBar") or {}).get("c")
            if px is not None:
                out[sym] = float(px)
        return out

    try:
        if client is not None:
            return await _run(client)
        async with httpx.AsyncClient() as c:
            return await _run(c)
    except Exception as e:
        print(f"[alpaca] latest_prices failed: {type(e).__name__}: {e}")
        return {}


async def daily_stats(
    symbol: str, client: Optional[httpx.AsyncClient] = None
) -> dict[str, Optional[float]]:
    """{price, prev_close, volume} from one stock snapshot — what the watchlist
    board needs per row. prevDailyBar is the true prior session close, so the
    day %-change stays correct pre-market when dailyBar hasn't formed yet."""
    if not is_configured():
        return {"price": None, "prev_close": None, "volume": None}
    sym = (symbol or "").strip().upper()

    async def _run(c: httpx.AsyncClient) -> dict[str, Optional[float]]:
        body = await _get(c, f"{DATA_URL}/v2/stocks/snapshots",
                          {"symbols": sym, "feed": "iex"})
        snap = (body or {}).get(sym) or {}
        daily = snap.get("dailyBar") or {}
        prev = snap.get("prevDailyBar") or {}
        price = (snap.get("latestTrade") or {}).get("p") or daily.get("c")
        return {
            "price": price,
            "prev_close": prev.get("c") or daily.get("o"),
            "volume": daily.get("v"),
        }

    try:
        if client is not None:
            return await _run(client)
        async with httpx.AsyncClient() as c:
            return await _run(c)
    except Exception:
        return {"price": None, "prev_close": None, "volume": None}


# --- options ----------------------------------------------------------------

async def option_bars(
    symbol: str,
    timeframe: str = "1Day",
    start: Any = None,
    end: Any = None,
    client: Optional[httpx.AsyncClient] = None,
) -> list[dict]:
    """Historical OHLCV for one option contract, oldest first. Alpaca's OPRA
    history begins around Jan 2024 — earlier windows come back empty."""
    if not is_configured():
        return []
    sym = _occ(symbol)
    params: dict[str, Any] = {"symbols": sym, "timeframe": timeframe,
                              "limit": 10000, "sort": "asc"}
    if start is not None:
        params["start"] = _iso(start)
    if end is not None:
        params["end"] = _iso(end)

    async def _run(c: httpx.AsyncClient) -> list[dict]:
        bars = await _paged(c, f"{DATA_URL}/v1beta1/options/bars", params, "bars")
        return _shape_bars((bars or {}).get(sym) or [])

    if client is not None:
        return await _run(client)
    async with httpx.AsyncClient() as c:
        return await _run(c)


async def option_contracts(
    underlying: str,
    side: Optional[str] = None,
    expiration_gte: Optional[str] = None,
    expiration_lte: Optional[str] = None,
    strike_gte: Optional[float] = None,
    strike_lte: Optional[float] = None,
    expired: bool = False,
    limit: int = 10000,
    client: Optional[httpx.AsyncClient] = None,
) -> list[dict]:
    """Contract reference data: strike, expiry, type, and open_interest.
    `expired=True` (status=inactive) is how the backtester discovers the
    contracts that existed on a past date."""
    if not is_configured():
        return []
    params: dict[str, Any] = {
        "underlying_symbols": (underlying or "").strip().upper(),
        "status": "inactive" if expired else "active",
        "limit": min(limit, 10000),
    }
    if side:
        params["type"] = side.lower()
    if expiration_gte:
        params["expiration_date_gte"] = expiration_gte
    if expiration_lte:
        params["expiration_date_lte"] = expiration_lte
    if strike_gte is not None:
        params["strike_price_gte"] = round(strike_gte, 2)
    if strike_lte is not None:
        params["strike_price_lte"] = round(strike_lte, 2)

    async def _run(c: httpx.AsyncClient) -> list[dict]:
        try:
            rows = await _paged(
                c, f"{TRADING_URL}/v2/options/contracts", params, "option_contracts")
        except httpx.HTTPStatusError as e:
            # Alpaca 422s on a root it doesn't carry (NDX and RUT, for two). A
            # caller sweeping several roots should get "no contracts" for those
            # rather than an exception that kills the whole sweep.
            if e.response.status_code == 422:
                print(f"[alpaca] no option contracts for {params['underlying_symbols']}: "
                      f"{e.response.text[:120]}")
                return []
            raise
        out: list[dict] = []
        for r in rows or []:
            try:
                out.append({
                    "ticker": r["symbol"],
                    "type": r.get("type"),
                    "strike": float(r["strike_price"]),
                    "expiration": r.get("expiration_date") or "",
                    "oi": int(r.get("open_interest") or 0),
                    "close_price": (
                        float(r["close_price"]) if r.get("close_price") else None
                    ),
                })
            except (KeyError, TypeError, ValueError):
                continue
        return out

    if client is not None:
        return await _run(client)
    async with httpx.AsyncClient() as c:
        return await _run(c)


def _flatten_snapshot(sym: str, snap: dict, underlying_price: Optional[float]) -> dict:
    """One Alpaca chain snapshot -> the flat row HAL's screener reasons over.
    Same keys the Massive flattener produced, so downstream code is unchanged."""
    greeks = snap.get("greeks") or {}
    quote = snap.get("latestQuote") or {}
    daily = snap.get("dailyBar") or {}
    bid, ask = quote.get("bp"), quote.get("ap")
    mid = spread_pct = None
    if bid is not None and ask is not None:
        mid = (bid + ask) / 2.0
        if mid > 0:
            spread_pct = (ask - bid) / mid * 100.0
    strike, expiration, kind = parse_occ(sym)
    return {
        "ticker": sym,
        "type": kind,
        "strike": strike,
        "expiration": expiration,
        "bid": bid,
        "ask": ask,
        "mid": round(mid, 4) if mid is not None else None,
        "spread_pct": round(spread_pct, 2) if spread_pct is not None else None,
        "iv": snap.get("impliedVolatility"),
        "delta": greeks.get("delta"),
        "gamma": greeks.get("gamma"),
        "theta": greeks.get("theta"),
        "vega": greeks.get("vega"),
        "oi": None,  # joined from option_contracts by the caller
        "day_volume": daily.get("v"),
        "underlying_price": underlying_price,
        "underlying_ticker": None,
    }


def occ_root(sym: str) -> str:
    """Underlying root from an OCC option symbol ('SPY260918C00770000' -> 'SPY').
    A plain ticker is returned unchanged, so callers can pass either."""
    s = _occ(sym)
    if len(s) < 16:
        return s
    tail = s[-15:]
    if tail[0:6].isdigit() and tail[6] in ("C", "P") and tail[7:15].isdigit():
        return s[:-15]
    return s


def parse_occ(sym: str) -> tuple[Optional[float], str, Optional[str]]:
    """(strike, 'YYYY-MM-DD', 'call'|'put') from an OCC symbol. The last 15
    chars are YYMMDD + C/P + strike*1000; the root is variable-length."""
    s = _occ(sym)
    if len(s) < 16:
        return None, "", None
    tail = s[-15:]
    yymmdd, cp, strike8 = tail[0:6], tail[6], tail[7:15]
    if not (yymmdd.isdigit() and strike8.isdigit() and cp in ("C", "P")):
        return None, "", None
    return (
        int(strike8) / 1000.0,
        f"20{yymmdd[0:2]}-{yymmdd[2:4]}-{yymmdd[4:6]}",
        "call" if cp == "C" else "put",
    )


async def option_chain(
    underlying: str,
    side: Optional[str] = None,
    expiration_gte: Optional[str] = None,
    expiration_lte: Optional[str] = None,
    strike_gte: Optional[float] = None,
    strike_lte: Optional[float] = None,
    limit: int = 1000,
    with_oi: bool = True,
) -> list[dict]:
    """Flat chain rows with greeks, IV, bid/ask and (optionally) open interest.

    Two upstream calls run concurrently: the snapshot endpoint for live
    quote/greeks/IV, and the contracts endpoint for open interest, which the
    snapshot omits. They're joined on the OCC symbol. Raises on HTTP failure so
    callers can surface the reason.
    """
    if not is_configured():
        return []
    sym = (underlying or "").strip().upper()
    params: dict[str, Any] = {"feed": OPTION_FEED, "limit": min(limit, 1000)}
    if side:
        params["type"] = side.lower()
    if expiration_gte:
        params["expiration_date_gte"] = expiration_gte
    if expiration_lte:
        params["expiration_date_lte"] = expiration_lte
    if strike_gte is not None:
        params["strike_price_gte"] = round(strike_gte, 2)
    if strike_lte is not None:
        params["strike_price_lte"] = round(strike_lte, 2)

    async with httpx.AsyncClient() as client:
        snaps_task = _paged(
            client, f"{DATA_URL}/v1beta1/options/snapshots/{sym}", params, "snapshots")
        oi_task = (
            option_contracts(
                sym, side=side, expiration_gte=expiration_gte,
                expiration_lte=expiration_lte, strike_gte=strike_gte,
                strike_lte=strike_lte, client=client)
            if with_oi else asyncio.sleep(0, result=[])
        )
        px_task = latest_prices([sym], client=client)
        snaps, contracts, prices = await asyncio.gather(
            snaps_task, oi_task, px_task, return_exceptions=False)

    underlying_price = (prices or {}).get(sym)
    oi_by_symbol = {c["ticker"]: c["oi"] for c in (contracts or [])}
    rows: list[dict] = []
    for occ_sym, snap in (snaps or {}).items():
        # _paged merges dict values into lists; a snapshot map yields one each.
        raw = snap[0] if isinstance(snap, list) else snap
        row = _flatten_snapshot(occ_sym, raw or {}, underlying_price)
        row["oi"] = oi_by_symbol.get(occ_sym)
        row["underlying_ticker"] = sym
        rows.append(row)
    return rows


# --- clock / calendar -------------------------------------------------------

async def clock() -> dict:
    """Authoritative market status — holidays included, unlike a weekday check.
    {} on failure so callers can fall back to their own clock math."""
    if not is_configured():
        return {}
    try:
        async with httpx.AsyncClient() as client:
            return await _get(client, f"{TRADING_URL}/v2/clock", {})
    except Exception as e:
        print(f"[alpaca] clock failed: {type(e).__name__}: {e}")
        return {}
