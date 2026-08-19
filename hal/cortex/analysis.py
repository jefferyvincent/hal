"""Options-chain screening and volatility-context helpers for HAL.

These wrap Alpaca's chain snapshot + daily bars (via sensory.alpaca_data)
with the shaping HAL actually needs to make a recommendation: flat
candidate rows from the chain (delta/IV/spread filtered) and a realized-
vs-implied vol summary so HAL can judge whether premiums are rich or
cheap before picking a side.

The chain snapshot endpoint returns nested JSON with greeks/quote/trade
sub-objects per contract. Reading that inline forces HAL to navigate
nesting in tokens, which it does poorly. alpaca_data.option_chain
flattens to one row per candidate; screen_options filters and ranks.
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Optional

from hal.sensory import alpaca_data


def _dte(expiration: str) -> Optional[int]:
    try:
        y, m, d = expiration.split("-")
        exp = date(int(y), int(m), int(d))
    except Exception:
        return None
    return (exp - date.today()).days


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
    if not alpaca_data.is_configured():
        return {"error": "ALPACA_API_KEY / ALPACA_SECRET_KEY not configured"}

    # DTE bounds map cleanly to expiration_date filters, so the chain is
    # narrowed server-side; delta / OI / spread% are filtered locally below.
    today = date.today()
    try:
        results = await alpaca_data.option_chain(
            underlying,
            side=side,
            expiration_gte=(today + timedelta(days=dte_min)).isoformat()
            if dte_min is not None else None,
            expiration_lte=(today + timedelta(days=dte_max)).isoformat()
            if dte_max is not None else None,
            strike_gte=strike_min,
            strike_lte=strike_max,
        )
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}

    flat: list[dict] = []
    for row in results:
        row["dte"] = _dte(row.get("expiration") or "")
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

    closes = await alpaca_data.daily_closes(underlying, 400)
    if len(closes) < 20:
        return {
            "error": f"insufficient daily bars for {underlying} "
            f"({len(closes)} found; need 20+)"
        }

    # ATM band is set from the last daily close; a failure fetching the chain is
    # non-fatal (we return realized-vol context with verdict UNKNOWN).
    underlying_price = closes[-1]
    today = date.today()
    chain: list[dict] = []
    try:
        chain = await alpaca_data.option_chain(
            underlying,
            expiration_gte=(today + timedelta(days=5)).isoformat(),
            expiration_lte=(today + timedelta(days=60)).isoformat(),
            strike_gte=underlying_price * 0.95,
            strike_lte=underlying_price * 1.05,
            with_oi=False,  # IV selection doesn't use OI; skip the second call
        )
    except Exception as e:
        print(f"[iv_context] Alpaca option chain unavailable for {underlying}: {e}")
    # The chain carries a live underlying price; prefer it over yesterday's close
    # so ATM distance is measured against where the stock actually is.
    for row in chain:
        if row.get("underlying_price"):
            underlying_price = row["underlying_price"]
            break

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

    iv_rows = [
        {"strike": r["strike"], "iv": r["iv"], "expiration": r.get("expiration") or ""}
        for r in chain
        if r.get("strike") is not None and r.get("iv") and r["iv"] > 0
    ]

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
    """Fetch daily closes and classify the price regime. Tolerant: returns
    {error:...} instead of raising so the committee can treat a missing read as
    'no regime input' rather than failing."""
    underlying = underlying.upper().strip()
    try:
        closes = await alpaca_data.daily_closes(underlying, lookback)
    except Exception as e:
        return {"error": f"daily bars unavailable: {e}"}
    reg = detect_regime(closes or [])
    reg["underlying"] = underlying
    return reg
