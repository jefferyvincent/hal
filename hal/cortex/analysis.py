"""Options-chain screening and volatility-context helpers for HAL.

These wrap Massive's REST snapshot + aggregates endpoints with the
shaping HAL actually needs to make a recommendation: flat candidate
rows from the chain (delta/IV/spread filtered) and a realized-vs-
implied vol summary so HAL can judge whether premiums are rich or
cheap before picking a side.

The chain snapshot endpoint returns nested JSON with greeks/quote/trade
sub-objects per contract. Reading that inline forces HAL to navigate
nesting in tokens, which it does poorly. screen_options flattens to
one row per candidate and returns only what's actionable.
"""
from __future__ import annotations

import asyncio
import math
from datetime import date
from typing import Any, Optional

import httpx


BASE_URL: str = ""
API_KEY: str = ""


def configure(base_url: str, api_key: str) -> None:
    global BASE_URL, API_KEY
    BASE_URL = base_url
    API_KEY = api_key


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {API_KEY}"}


def _dte(expiration: str) -> Optional[int]:
    try:
        y, m, d = expiration.split("-")
        exp = date(int(y), int(m), int(d))
    except Exception:
        return None
    return (exp - date.today()).days


def _flatten_chain_row(row: dict) -> Optional[dict]:
    details = row.get("details") or {}
    greeks = row.get("greeks") or {}
    quote = row.get("last_quote") or {}
    day = row.get("day") or {}
    underlying = row.get("underlying_asset") or {}
    expiration = details.get("expiration_date") or ""
    bid = quote.get("bid")
    ask = quote.get("ask")
    mid = None
    spread_pct = None
    if bid is not None and ask is not None:
        mid = (bid + ask) / 2.0
        if mid > 0:
            spread_pct = (ask - bid) / mid * 100.0
    return {
        "ticker": details.get("ticker"),
        "type": details.get("contract_type"),
        "strike": details.get("strike_price"),
        "expiration": expiration,
        "dte": _dte(expiration),
        "bid": bid,
        "ask": ask,
        "mid": round(mid, 4) if mid is not None else None,
        "spread_pct": round(spread_pct, 2) if spread_pct is not None else None,
        "iv": row.get("implied_volatility"),
        "delta": greeks.get("delta"),
        "gamma": greeks.get("gamma"),
        "theta": greeks.get("theta"),
        "vega": greeks.get("vega"),
        "oi": row.get("open_interest"),
        "day_volume": day.get("volume"),
        "underlying_price": underlying.get("price"),
        "underlying_ticker": underlying.get("ticker"),
    }


async def _get(client: httpx.AsyncClient, path: str, params: dict) -> dict:
    url = BASE_URL + path
    r = await client.get(url, headers=_headers(), params=params, timeout=30)
    r.raise_for_status()
    return r.json()


async def screen_options(
    underlying: str,
    side: str = "call",
    dte_min: int = 0,
    dte_max: int = 60,
    delta_min: Optional[float] = None,
    delta_max: Optional[float] = None,
    min_oi: int = 0,
    max_spread_pct: Optional[float] = None,
    strike_min: Optional[float] = None,
    strike_max: Optional[float] = None,
    top_n: int = 15,
    sort_by: str = "abs_delta",
) -> dict:
    """Fetch and filter the options chain for an underlying.

    Returns up to top_n candidate rows already filtered server-side
    where possible (contract_type, strike range) and locally for fields
    the API doesn't filter on (delta, OI, spread%, DTE bounds).

    sort_by: 'abs_delta' | 'mid' | 'oi' | 'theta' | 'iv'
    """
    underlying = underlying.upper().strip()
    side = side.lower().strip()
    if side not in ("call", "put"):
        return {"error": f"side must be 'call' or 'put', got {side!r}"}
    if not API_KEY:
        return {"error": "MASSIVE_API_KEY not configured"}

    params: dict[str, Any] = {
        "contract_type": side,
        "limit": 250,
        "order": "asc",
        "sort": "strike_price",
    }
    if strike_min is not None:
        params["strike_price.gte"] = strike_min
    if strike_max is not None:
        params["strike_price.lte"] = strike_max
    # DTE bounds map cleanly to expiration_date filters
    today = date.today()
    if dte_min is not None:
        params["expiration_date.gte"] = (
            today.replace().fromordinal(today.toordinal() + dte_min).isoformat()
        )
    if dte_max is not None:
        params["expiration_date.lte"] = (
            today.replace().fromordinal(today.toordinal() + dte_max).isoformat()
        )

    path = f"/v3/snapshot/options/{underlying}"
    async with httpx.AsyncClient() as client:
        try:
            body = await _get(client, path, params)
        except httpx.HTTPStatusError as e:
            return {
                "error": f"HTTP {e.response.status_code}: {e.response.text[:300]}"
            }
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    results = body.get("results") or []
    flat: list[dict] = []
    for raw in results:
        row = _flatten_chain_row(raw)
        if row is None:
            continue
        if row["dte"] is None:
            continue
        d = row["delta"]
        if delta_min is not None and (d is None or d < delta_min):
            continue
        if delta_max is not None and (d is None or d > delta_max):
            continue
        if min_oi and (row["oi"] or 0) < min_oi:
            continue
        if max_spread_pct is not None:
            sp = row["spread_pct"]
            if sp is None or sp > max_spread_pct:
                continue
        flat.append(row)

    def _sort_key(r: dict) -> float:
        if sort_by == "abs_delta":
            d = r.get("delta")
            return abs(d) if d is not None else math.inf
        if sort_by == "mid":
            v = r.get("mid")
            return -(v or 0.0)
        if sort_by == "oi":
            return -(r.get("oi") or 0)
        if sort_by == "theta":
            return r.get("theta") or 0.0
        if sort_by == "iv":
            return -(r.get("iv") or 0.0)
        return 0.0

    flat.sort(key=_sort_key)
    flat = flat[:top_n]

    return {
        "underlying": underlying,
        "side": side,
        "filters": {
            "dte_min": dte_min,
            "dte_max": dte_max,
            "delta_min": delta_min,
            "delta_max": delta_max,
            "min_oi": min_oi,
            "max_spread_pct": max_spread_pct,
        },
        "count": len(flat),
        "candidates": flat,
    }


async def iv_context(underlying: str, atm_window: int = 3) -> dict:
    """Compare current ATM implied vol against realized vol over 10/30/60/90
    trading days. Returns a richness verdict (RICH / FAIR / CHEAP) based on
    IV / HV30. Useful before deciding to sell vs. buy premium.

    Note: this is NOT IV rank in the traditional sense (which requires
    52-week historical IV). It is an implied-vs-realized comparison that
    serves the same decision: are options pricing more vol than the
    underlying has recently delivered?
    """
    underlying = underlying.upper().strip()

    today = date.today()
    start = today.fromordinal(today.toordinal() - 365)
    aggs_path = (
        f"/v2/aggs/ticker/{underlying}/range/1/day/"
        f"{start.isoformat()}/{today.isoformat()}"
    )
    snap_path = f"/v3/snapshot/options/{underlying}"

    closes: list[float] = []
    snap: dict = {}
    async with httpx.AsyncClient() as client:
        # Primary realized-vol source: Massive daily aggregates. Often 403s on
        # underlying value data (not in our plan), so failures are non-fatal —
        # we fall back to Alpaca below.
        if API_KEY:
            try:
                aggs = await _get(
                    client, aggs_path,
                    {"adjusted": "true", "sort": "asc", "limit": 50000},
                )
                results = aggs.get("results") or []
                closes = [r["c"] for r in results if r.get("c") is not None]
            except Exception as e:
                print(f"[iv_context] Massive aggregates unavailable for {underlying}: {e}")

        # HV fallback: Alpaca daily bars (entitled with our trading keys). This is
        # what fixes "insufficient historical volatility data" when Massive is thin.
        if len(closes) < 20:
            from hal.sensory import broker
            alpaca_closes = await asyncio.to_thread(broker.daily_closes, underlying, 260)
            if len(alpaca_closes) >= 20:
                closes = alpaca_closes
        if len(closes) < 20:
            return {
                "error": f"insufficient daily bars for {underlying} "
                f"({len(closes)} found; need 20+) — Massive and Alpaca both thin/unavailable"
            }

        # ATM implied vol still comes from the Massive options snapshot; a failure
        # here is non-fatal (we return realized-vol context with verdict UNKNOWN).
        underlying_price = closes[-1]
        if API_KEY:
            atm_lo = underlying_price * 0.95
            atm_hi = underlying_price * 1.05
            try:
                snap = await _get(
                    client, snap_path,
                    {"strike_price.gte": atm_lo, "strike_price.lte": atm_hi, "limit": 250},
                )
            except Exception as e:
                print(f"[iv_context] Massive options snapshot unavailable for {underlying}: {e}")

    # Realized vol from log returns
    log_returns: list[float] = []
    for prev, curr in zip(closes[:-1], closes[1:]):
        if prev and curr and prev > 0 and curr > 0:
            log_returns.append(math.log(curr / prev))

    def _hv(window: int) -> Optional[float]:
        if len(log_returns) < window:
            return None
        sample = log_returns[-window:]
        mean = sum(sample) / len(sample)
        var = sum((x - mean) ** 2 for x in sample) / max(len(sample) - 1, 1)
        return math.sqrt(var) * math.sqrt(252)

    hv10, hv30, hv60, hv90 = _hv(10), _hv(30), _hv(60), _hv(90)

    # Normalize ATM IV contracts to {strike, iv, expiration} from whichever source
    # is available: the Massive snapshot first, else Alpaca's option chain (IV
    # fallback). The selection below then runs identically on either source.
    iv_rows: list[dict] = []
    for r in (snap.get("results") or []):
        details = r.get("details") or {}
        strike = details.get("strike_price")
        iv = r.get("implied_volatility")
        if strike is not None and iv and iv > 0:
            iv_rows.append({"strike": strike, "iv": iv,
                            "expiration": details.get("expiration_date") or ""})
    if not iv_rows:
        from hal.sensory import broker
        iv_rows = await asyncio.to_thread(
            broker.option_iv_chain, underlying,
            underlying_price * 0.95, underlying_price * 1.05)

    # Pick the N closest-to-ATM contracts with valid IV (5–60 DTE); average their IV.
    near_atm: list[tuple[float, float]] = []
    for row in iv_rows:
        dte = _dte(row.get("expiration") or "")
        if dte is None or dte < 5 or dte > 60:
            continue
        near_atm.append((abs(row["strike"] - underlying_price), row["iv"]))
    near_atm.sort(key=lambda x: x[0])
    atm_ivs = [iv for _, iv in near_atm[: max(atm_window * 2, 4)]]
    atm_iv = sum(atm_ivs) / len(atm_ivs) if atm_ivs else None

    verdict = "UNKNOWN"
    iv_over_hv30 = None
    if atm_iv is not None and hv30:
        iv_over_hv30 = atm_iv / hv30
        if iv_over_hv30 >= 1.30:
            verdict = "RICH"
        elif iv_over_hv30 >= 0.90:
            verdict = "FAIR"
        else:
            verdict = "CHEAP"

    return {
        "underlying": underlying,
        "underlying_price": underlying_price,
        "atm_iv": round(atm_iv, 4) if atm_iv is not None else None,
        "atm_iv_sample_size": len(atm_ivs),
        "hv10": round(hv10, 4) if hv10 else None,
        "hv30": round(hv30, 4) if hv30 else None,
        "hv60": round(hv60, 4) if hv60 else None,
        "hv90": round(hv90, 4) if hv90 else None,
        "iv_over_hv30": round(iv_over_hv30, 3) if iv_over_hv30 else None,
        "verdict": verdict,
        "interpretation": {
            "RICH": "implied vol > 1.3x realized; premium selling has edge",
            "FAIR": "implied roughly matches realized; no clear edge from vol alone",
            "CHEAP": "implied vol < 0.9x realized; premium buying has edge",
            "UNKNOWN": "insufficient data to judge",
        }[verdict],
    }


# --- price/trend regime -----------------------------------------------------
# A deterministic market-structure read (borrowed in spirit from QuantDinger's
# regime_detect). The committee already judges the VOLATILITY regime (rich/cheap
# premium); this judges the PRICE regime (trending up, trending down, or chopping
# sideways) so the desk has an actual directional-tape input, not just a vol read.
# Trend strength uses Kaufman's Efficiency Ratio — net move / total path over the
# window — which cleanly separates a clean trend (ER→1) from chop (ER→0).

_ER_WINDOW = 20            # bars for the efficiency-ratio path measurement
_SMA_FAST, _SMA_SLOW = 20, 50
_TREND_ER = 0.30           # ER at/above this is a real trend, below it is chop


def detect_regime(closes: list[float]) -> dict:
    """Classify the price regime from daily closes. Pure function (no I/O).

    Returns {label, direction, lean, confidence, note, evidence, stats} where
    `lean` is bullish/bearish/neutral so a committee analyst can consume it
    directly. A choppy tape always leans neutral regardless of slope — trading a
    direction in chop is how breakout signals bleed to theta. Returns {error:...}
    when there isn't enough history.
    """
    if len(closes) < _SMA_SLOW + 1:
        return {"error": f"insufficient bars ({len(closes)}; need {_SMA_SLOW + 1}+)"}
    price = closes[-1]
    sma_fast = sum(closes[-_SMA_FAST:]) / _SMA_FAST
    sma_slow = sum(closes[-_SMA_SLOW:]) / _SMA_SLOW

    window = closes[-(_ER_WINDOW + 1):]
    net = abs(window[-1] - window[0])
    path = sum(abs(window[i] - window[i - 1]) for i in range(1, len(window)))
    er = net / path if path > 0 else 0.0

    trending = er >= _TREND_ER
    up = price > sma_slow and sma_fast >= sma_slow
    down = price < sma_slow and sma_fast <= sma_slow
    if trending and up:
        label, direction, lean = "uptrend", "up", "bullish"
    elif trending and down:
        label, direction, lean = "downtrend", "down", "bearish"
    elif trending:
        label, direction, lean = "transition", "mixed", "neutral"
    else:
        label, direction, lean = "range", "sideways", "neutral"

    # Trending: confidence scales with how clean the trend is. Neutral: a modest,
    # capped confidence in the "stand aside" call (stronger the choppier it is).
    if lean != "neutral":
        confidence = round(min(0.9, max(0.4, er)), 2)
    else:
        confidence = round(min(0.5, max(0.2, 1.0 - er)), 2)

    note = (
        f"{label}: price {price:.2f} {'>' if price > sma_slow else '<'} 50-day "
        f"{sma_slow:.2f}, 20-day {sma_fast:.2f}; efficiency ratio {er:.2f} "
        f"({'trending' if trending else 'choppy'})."
    )
    return {
        "label": label,
        "direction": direction,
        "lean": lean,
        "confidence": confidence,
        "note": note,
        "evidence": note,
        "stats": {
            "price": round(price, 2),
            "sma_fast": round(sma_fast, 2),
            "sma_slow": round(sma_slow, 2),
            "efficiency_ratio": round(er, 3),
        },
    }


async def price_regime(underlying: str, lookback: int = 120) -> dict:
    """Fetch daily closes and classify the price regime. Uses Alpaca daily bars
    (entitled with HAL's trading keys, unlike Massive underlying-value data which
    403s). Tolerant: returns {error:...} instead of raising so the committee can
    treat a missing read as 'no regime input' rather than failing."""
    underlying = underlying.upper().strip()
    from hal.sensory import broker
    try:
        closes = await asyncio.to_thread(broker.daily_closes, underlying, lookback)
    except Exception as e:
        return {"error": f"daily bars unavailable: {e}"}
    reg = detect_regime(closes or [])
    reg["underlying"] = underlying
    return reg
