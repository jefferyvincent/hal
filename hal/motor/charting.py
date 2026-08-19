"""Candlestick chart payloads for HAL's in-app chart view.

Fetches OHLC bars from Alpaca or Yahoo and shapes them into a
JSON-serializable payload the HAL frontend renders with TradingView's
lightweight-charts library: candles, a volume histogram, a SuperTrend
overlay (split into up/down line segments for colouring), and Buy/Sell
flip markers. All times are unix SECONDS (lightweight-charts wants
seconds; both fetchers below emit milliseconds and build_chart converts).

The server pushes the returned payload to the client over the WebSocket
as {"action": "open_view", "kind": "chart", "chart": <payload>}; the
client stores it and renders it as a new immersive source.
"""
from __future__ import annotations

import asyncio
import time
from datetime import date, timedelta
from typing import Any, Optional

import httpx

from hal.sensory import alpaca_data


SOURCE: str = "yahoo"  # "alpaca" | "yahoo"


def configure(source: str = "yahoo") -> None:
    global SOURCE
    SOURCE = source if source in ("alpaca", "yahoo") else "yahoo"


# --- timeframe parsing -----------------------------------------------------

# label -> (multiplier, timespan, lookback_days). Lookback is chosen to give
# a few hundred bars — enough context without an unbounded payload.
_TIMEFRAMES: dict[str, tuple[int, str, int]] = {
    "1m": (1, "minute", 2),
    "2m": (2, "minute", 4),
    "5m": (5, "minute", 7),
    "15m": (15, "minute", 21),
    "30m": (30, "minute", 45),
    "1h": (1, "hour", 90),
    "4h": (4, "hour", 240),
    "1d": (1, "day", 400),
    "1w": (1, "week", 1825),
}


def _resolve_timeframe(tf: str) -> tuple[tuple[int, str, int], str]:
    key = (tf or "").lower().strip().replace(" ", "")
    aliases = {
        "1min": "1m", "5min": "5m", "15min": "15m", "30min": "30m",
        "60m": "1h", "60min": "1h", "hourly": "1h",
        "daily": "1d", "d": "1d", "day": "1d",
        "weekly": "1w", "w": "1w", "week": "1w",
    }
    key = aliases.get(key, key)
    return _TIMEFRAMES.get(key, _TIMEFRAMES["5m"]), (key if key in _TIMEFRAMES else "5m")


# --- indicators ------------------------------------------------------------

def _supertrend(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int = 10,
    multiplier: float = 3.0,
) -> tuple[list[Optional[float]], list[int]]:
    """Canonical SuperTrend. Returns (line, direction) per bar.

    line[i] is the trailing stop level (None until the ATR warms up).
    direction[i] is +1 for uptrend (line below price, green) or -1 for
    downtrend (line above price, red).
    """
    n = len(closes)
    if n == 0:
        return [], []

    # True range, then Wilder-smoothed ATR.
    tr = [0.0] * n
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )

    atr: list[Optional[float]] = [None] * n
    if n >= period:
        seed = sum(tr[1 : period + 1]) / period if n > period else sum(tr[:period]) / period
        atr[period - 1] = seed
        for i in range(period, n):
            atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period  # type: ignore[operator]

    line: list[Optional[float]] = [None] * n
    direction = [1] * n
    final_upper = [0.0] * n
    final_lower = [0.0] * n

    for i in range(n):
        a = atr[i]
        if a is None:
            continue
        hl2 = (highs[i] + lows[i]) / 2.0
        basic_upper = hl2 + multiplier * a
        basic_lower = hl2 - multiplier * a

        if i == 0 or atr[i - 1] is None:
            final_upper[i] = basic_upper
            final_lower[i] = basic_lower
            direction[i] = 1 if closes[i] >= hl2 else -1
            line[i] = final_lower[i] if direction[i] == 1 else final_upper[i]
            continue

        final_upper[i] = (
            basic_upper
            if (basic_upper < final_upper[i - 1] or closes[i - 1] > final_upper[i - 1])
            else final_upper[i - 1]
        )
        final_lower[i] = (
            basic_lower
            if (basic_lower > final_lower[i - 1] or closes[i - 1] < final_lower[i - 1])
            else final_lower[i - 1]
        )

        prev_dir = direction[i - 1]
        if prev_dir == 1:
            direction[i] = -1 if closes[i] < final_lower[i] else 1
        else:
            direction[i] = 1 if closes[i] > final_upper[i] else -1

        line[i] = final_lower[i] if direction[i] == 1 else final_upper[i]

    return line, direction


# --- bar sources -----------------------------------------------------------
# Both return raw bars as [{t: ms, o, h, l, c, v}] so build_chart's loop is
# source-agnostic.

_YAHOO_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
# (multiplier, timespan) -> Yahoo interval. Yahoo has no 4-hour bar, so it
# degrades to hourly.
_YAHOO_INTERVALS: dict[tuple[int, str], str] = {
    (1, "minute"): "1m", (2, "minute"): "2m", (5, "minute"): "5m",
    (15, "minute"): "15m", (30, "minute"): "30m",
    (1, "hour"): "60m", (4, "hour"): "60m",
    (1, "day"): "1d", (1, "week"): "1wk",
}

# (multiplier, timespan) -> Alpaca timeframe string. Alpaca has no 2-minute bar,
# so it degrades to 1-minute.
_ALPACA_TIMEFRAMES: dict[tuple[int, str], str] = {
    (1, "minute"): "1Min", (2, "minute"): "1Min", (5, "minute"): "5Min",
    (15, "minute"): "15Min", (30, "minute"): "30Min",
    (1, "hour"): "1Hour", (4, "hour"): "4Hour",
    (1, "day"): "1Day", (1, "week"): "1Week",
}


async def _fetch_bars_alpaca(sym, mult, timespan, from_d, to_d) -> list[dict]:
    """OHLC from Alpaca. Real-time bars are IEX on the free tier; anything older
    than ~15 minutes comes from the full SIP tape (alpaca_data picks the feed)."""
    if not alpaca_data.is_configured():
        raise RuntimeError("ALPACA_API_KEY / ALPACA_SECRET_KEY not configured")
    tf = _ALPACA_TIMEFRAMES.get((mult, timespan), "5Min")
    bars = await alpaca_data.stock_bars(sym, tf, start=from_d, end=to_d)
    # alpaca_data emits unix seconds; this module's fetchers contract on ms.
    return [{**b, "t": b["t"] * 1000} for b in bars]


async def _fetch_bars_yahoo(sym, mult, timespan, from_d, to_d) -> list[dict]:
    """Free, keyless OHLC from Yahoo Finance's chart API. Near-real-time for US
    equities during market hours. Nulls (gaps / a still-forming bar) are skipped."""
    interval = _YAHOO_INTERVALS.get((mult, timespan), "5m")
    period1 = int(time.mktime(from_d.timetuple()))
    period2 = int(time.mktime((to_d + timedelta(days=1)).timetuple()))
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
    params = {
        "interval": interval, "period1": period1, "period2": period2,
        "includePrePost": "false",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, params=params, headers={"User-Agent": _YAHOO_UA})
    if r.status_code != 200:
        raise RuntimeError(f"Yahoo HTTP {r.status_code}: {r.text[:200]}")
    chart = (r.json() or {}).get("chart") or {}
    if chart.get("error"):
        raise RuntimeError(f"Yahoo error: {chart['error']}")
    result = (chart.get("result") or [None])[0]
    if not result:
        return []
    ts = result.get("timestamp") or []
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    vols = quote.get("volume") or []
    bars: list[dict] = []
    for i, t in enumerate(ts):
        o = opens[i] if i < len(opens) else None
        h = highs[i] if i < len(highs) else None
        l = lows[i] if i < len(lows) else None
        c = closes[i] if i < len(closes) else None
        if o is None or h is None or l is None or c is None:
            continue
        v = vols[i] if i < len(vols) and vols[i] is not None else 0
        bars.append({"t": int(t) * 1000, "o": o, "h": h, "l": l, "c": c, "v": v})
    return bars


async def current_prices(symbols: list[str]) -> dict[str, float]:
    """Latest price per symbol from Yahoo Finance (meta.regularMarketPrice).
    Always Yahoo (keyless, near-real-time for US equities), independent of the
    chart SOURCE setting — used by the price-alert poller and direction
    inference. Symbols that fail to fetch are simply omitted from the result."""
    out: dict[str, float] = {}
    syms = [s for s in dict.fromkeys(symbols) if s]  # dedupe, preserve order
    if not syms:
        return out

    async def _one(client: httpx.AsyncClient, sym: str) -> None:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
        params = {"interval": "1m", "range": "1d"}
        try:
            r = await client.get(url, params=params, headers={"User-Agent": _YAHOO_UA})
            if r.status_code != 200:
                return
            result = (((r.json() or {}).get("chart") or {}).get("result") or [None])[0]
            price = ((result or {}).get("meta") or {}).get("regularMarketPrice")
            if price is not None:
                out[sym] = float(price)
        except Exception:
            return

    async with httpx.AsyncClient(timeout=15) as client:
        await asyncio.gather(*[_one(client, s) for s in syms])
    return out


async def _fetch_bars(sym, mult, timespan, from_d, to_d) -> list[dict]:
    if SOURCE == "alpaca":
        return await _fetch_bars_alpaca(sym, mult, timespan, from_d, to_d)
    return await _fetch_bars_yahoo(sym, mult, timespan, from_d, to_d)


async def build_chart(
    symbol: str,
    timeframe: str = "5m",
    st_period: int = 10,
    st_multiplier: float = 3.0,
) -> dict[str, Any]:
    """Fetch bars for `symbol` and return a chart payload (see module docs).

    Raises RuntimeError on configuration/API problems so the caller can
    surface a spoken error.
    """
    sym = symbol.upper().strip()
    (mult, timespan, lookback), tf_label = _resolve_timeframe(timeframe)

    to_d = date.today()
    from_d = to_d - timedelta(days=lookback)

    results = await _fetch_bars(sym, mult, timespan, from_d, to_d)
    if not results:
        raise RuntimeError(f"no bars returned for {sym} ({tf_label})")

    candles: list[dict] = []
    volume: list[dict] = []
    highs: list[float] = []
    lows: list[float] = []
    closes: list[float] = []
    times: list[int] = []
    for bar in results:
        t = int(bar["t"]) // 1000  # ms -> s
        o, h, l, c = bar["o"], bar["h"], bar["l"], bar["c"]
        v = bar.get("v", 0)
        times.append(t)
        highs.append(h)
        lows.append(l)
        closes.append(c)
        candles.append({"time": t, "open": o, "high": h, "low": l, "close": c})
        volume.append({"time": t, "value": v, "up": c >= o})

    line, direction = _supertrend(highs, lows, closes, st_period, st_multiplier)

    # Split the SuperTrend line into up/down series (gaps where the other
    # direction is active) so the client can colour them green/red, and emit
    # a Buy/Sell marker at each direction flip.
    st_up: list[dict] = []
    st_down: list[dict] = []
    markers: list[dict] = []
    for i, val in enumerate(line):
        if val is None:
            continue
        if direction[i] == 1:
            st_up.append({"time": times[i], "value": round(val, 4)})
        else:
            st_down.append({"time": times[i], "value": round(val, 4)})
        if i > 0 and direction[i] != direction[i - 1] and line[i - 1] is not None:
            markers.append(
                {"time": times[i], "side": "buy" if direction[i] == 1 else "sell"}
            )

    return {
        "symbol": sym,
        "timeframe": tf_label,
        "candles": candles,
        "volume": volume,
        "supertrend_up": st_up,
        "supertrend_down": st_down,
        "markers": markers,
        "bar_count": len(candles),
    }


def _find_pivots(values, kind, k):
    """Fractal pivots: index i is a pivot when values[i] is the extreme of the
    window [i-k, i+k]. Larger k -> fewer, more prominent swings."""
    piv = []
    n = len(values)
    for i in range(k, n - k):
        win = values[i - k : i + k + 1]
        if kind == "high" and values[i] == max(win):
            piv.append((i, values[i]))
        elif kind == "low" and values[i] == min(win):
            piv.append((i, values[i]))
    return piv


def _structure(p_high, p_low, trend):
    hs = [v for _, v in p_high[-3:]]
    ls = [v for _, v in p_low[-3:]]
    if len(hs) >= 2 and len(ls) >= 2:
        if hs[-1] > hs[0] and ls[-1] > ls[0]:
            return "higher highs and higher lows"
        if hs[-1] < hs[0] and ls[-1] < ls[0]:
            return "lower highs and lower lows"
        return "mixed swings"
    if trend == "in an uptrend":
        return "trending up with shallow pullbacks"
    if trend == "in a downtrend":
        return "trending down with shallow bounces"
    return "ranging with few defined swings"


_EQ = 0.008   # how "equal" two swings must be to count as a pair
_SEP = 0.015  # minimum intervening move for a valid reversal
_FLAT = 0.01  # how flat a triangle's support/resistance line must be
_SHO = 0.03   # shoulder symmetry tolerance for head-and-shoulders


def _head_and_shoulders(p_high, p_low, last, top):
    """Confirmed H&S top (bearish) or inverse H&S (bullish). Needs 3 swings
    with a higher/lower head, ~symmetric shoulders, and a neckline break."""
    pk, tr = (p_high, p_low) if top else (p_low, p_high)
    if len(pk) < 3:
        return None
    (iL, L), (iH, H), (iR, R) = pk[-3:]
    head_ok = (H > L and H > R) if top else (H < L and H < R)
    if not head_ok or max(L, R) <= 0 or abs(L - R) / max(L, R) > _SHO:
        return None
    necks = [v for idx, v in tr if iL < idx < iR]
    if not necks:
        return None
    neck = sum(necks) / len(necks)
    if top and last < neck:
        return f"head & shoulders top, confirmed below {neck:.2f}"
    if not top and last > neck:
        return f"inverse head & shoulders, confirmed above {neck:.2f}"
    return None


def _triangle(p_high, p_low, last, descending):
    """Descending triangle (bearish: flat lows + lower highs, breaks down) or
    ascending triangle (bullish: flat highs + higher lows, breaks up)."""
    highs = [v for _, v in p_high[-3:]]
    lows = [v for _, v in p_low[-3:]]
    if len(highs) < 2 or len(lows) < 2:
        return None
    if descending:
        support = sum(lows) / len(lows)
        flat = support > 0 and (max(lows) - min(lows)) <= _FLAT * support
        if flat and highs[-1] < highs[0] and last < min(lows):
            return f"descending triangle, broke support {support:.2f}"
    else:
        res = sum(highs) / len(highs)
        flat = res > 0 and (max(highs) - min(highs)) <= _FLAT * res
        if flat and lows[-1] > lows[0] and last > max(highs):
            return f"ascending triangle, broke resistance {res:.2f}"
    return None


def _three_peaks(p_high, p_low, down):
    if down:
        hs = [v for _, v in p_high[-3:]]
        if len(hs) == 3 and hs[0] > hs[1] > hs[2]:
            return "three descending peaks (lower highs)"
    else:
        ls = [v for _, v in p_low[-3:]]
        if len(ls) == 3 and ls[0] < ls[1] < ls[2]:
            return "three rising valleys (higher lows)"
    return None


def _rectangle(p_high, p_low, last):
    """Trading range (neutral): flat resistance AND flat support with price
    between them. The rails are iron-condor short-strike guides."""
    highs = [v for _, v in p_high[-3:]]
    lows = [v for _, v in p_low[-3:]]
    if len(highs) < 2 or len(lows) < 2:
        return None
    res = sum(highs) / len(highs)
    sup = sum(lows) / len(lows)
    flat_h = res > 0 and (max(highs) - min(highs)) <= 0.012 * res
    flat_l = sup > 0 and (max(lows) - min(lows)) <= 0.012 * sup
    if flat_h and flat_l and sup < last < res and (res - sup) / sup >= 0.01:
        return (f"trading range between {sup:.2f} and {res:.2f}", "neutral")
    return None


def _flag(closes):
    """Bull/bear flag (continuation): a strong impulse leg followed by a tight
    counter-trend consolidation. Conservative thresholds for scalp setups."""
    if len(closes) < 20:
        return None
    cons = closes[-6:]
    cmean = sum(cons) / len(cons)
    if not cmean or (max(cons) - min(cons)) / cmean > 0.012:
        return None  # consolidation not tight enough
    leg = closes[-18:-6]
    if len(leg) < 6 or not leg[0]:
        return None
    impulse = (leg[-1] - leg[0]) / leg[0]
    if impulse >= 0.03:
        return ("bull flag (impulse up, now consolidating)", "bullish")
    if impulse <= -0.03:
        return ("bear flag (impulse down, now consolidating)", "bearish")
    return None


def _detect_patterns(closes, p_high, p_low, pct):
    """Return confirmed patterns as (text, side) where side is bearish/bullish/
    neutral. Confirmation-gated so HAL doesn't flag setups that haven't triggered."""
    out: list[tuple[str, str]] = []
    last = closes[-1]

    # Double top (bearish) / double bottom (bullish), confirmed on neckline break.
    if len(p_high) >= 2 and len(p_low) >= 1:
        (i1, h1), (i2, h2) = p_high[-2], p_high[-1]
        peak = max(h1, h2)
        if peak and abs(h1 - h2) / peak <= _EQ:
            mids = [v for idx, v in p_low if i1 < idx < i2]
            if mids and (peak - min(mids)) / peak >= _SEP and last < min(mids):
                out.append((f"double top, confirmed below {min(mids):.2f}", "bearish"))
    if not out and len(p_low) >= 2 and len(p_high) >= 1:
        (i1, l1), (i2, l2) = p_low[-2], p_low[-1]
        trough = min(l1, l2)
        if trough and abs(l1 - l2) / max(l1, l2) <= _EQ:
            mids = [v for idx, v in p_high if i1 < idx < i2]
            if mids and (max(mids) - trough) / max(mids) >= _SEP and last > max(mids):
                out.append((f"double bottom, confirmed above {max(mids):.2f}", "bullish"))

    for fn, side in ((True, "bearish"), (False, "bullish")):
        hs = _head_and_shoulders(p_high, p_low, last, fn)
        if hs:
            out.append((hs, side))
    dt = _triangle(p_high, p_low, last, True)
    if dt:
        out.append((dt, "bearish"))
    at = _triangle(p_high, p_low, last, False)
    if at:
        out.append((at, "bullish"))
    tp = _three_peaks(p_high, p_low, True)
    if tp:
        out.append((tp, "bearish"))
    tv = _three_peaks(p_high, p_low, False)
    if tv:
        out.append((tv, "bullish"))
    rect = _rectangle(p_high, p_low, last)
    if rect:
        out.append(rect)
    flag = _flag(closes)
    if flag:
        out.append(flag)

    recent_h = [v for _, v in p_high[-4:]]
    recent_l = [v for _, v in p_low[-4:]]
    if recent_h and last > max(recent_h):
        out.append(("breaking out above recent swing highs", "bullish"))
    elif recent_l and last < min(recent_l):
        out.append(("breaking down below recent swing lows", "bearish"))

    if abs(pct) < 1.5:
        window = closes[-30:]
        if len(window) >= 15:
            mean = sum(window) / len(window)
            if mean and (max(window) - min(window)) / mean <= 0.015:
                out.append(("tight consolidation / coiling range", "neutral"))

    # De-dupe while preserving order.
    seen = set()
    deduped = []
    for text, side in out:
        if text not in seen:
            seen.add(text)
            deduped.append((text, side))
    return deduped


def analyze(payload: dict) -> dict:
    """Structured technical analysis of a chart payload. Returns a dict the
    server stores per-session so HAL can answer questions about the chart
    deterministically, draw key levels, and speak a read."""
    candles = payload.get("candles") or []
    sym = payload.get("symbol", "?")
    tf = payload.get("timeframe", "")
    if not candles:
        return {"symbol": sym, "timeframe": tf, "empty": True, "levels": []}
    closes = [c["close"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    last, first = closes[-1], closes[0]
    hi, lo = max(highs), min(lows)
    pct = (last - first) / first * 100 if first else 0.0
    rng = hi - lo
    pos = (last - lo) / rng if rng else 0.5
    where = "near the highs" if pos >= 0.66 else "near the lows" if pos <= 0.34 else "mid-range"

    last_t = candles[-1]["time"]
    up = payload.get("supertrend_up") or []
    down = payload.get("supertrend_down") or []
    if up and up[-1]["time"] == last_t:
        trend = "in an uptrend"
    elif down and down[-1]["time"] == last_t:
        trend = "in a downtrend"
    else:
        trend = "range-bound"

    k = min(12, max(5, len(closes) // 40))
    p_high = _find_pivots(highs, "high", k)
    p_low = _find_pivots(lows, "low", k)
    structure = _structure(p_high, p_low, trend)
    tagged = _detect_patterns(closes, p_high, p_low, pct)
    patterns = [t for t, _ in tagged]
    bearish_setups = [t for t, side in tagged if side == "bearish"]
    bullish_setups = [t for t, side in tagged if side == "bullish"]
    if len(bearish_setups) > len(bullish_setups):
        bias = "bearish"
    elif len(bullish_setups) > len(bearish_setups):
        bias = "bullish"
    elif trend == "in a downtrend":
        bias = "bearish"
    elif trend == "in an uptrend":
        bias = "bullish"
    else:
        bias = "neutral"
    resistance = min((v for _, v in p_high if v > last), default=None)
    support = max((v for _, v in p_low if v < last), default=None)

    # Volatility regime (true range), used to map the chart to a strategy.
    trs = [max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
           for i in range(1, len(closes))]
    recent_atr = sum(trs[-14:]) / min(14, len(trs)) if trs else 0.0
    prior = trs[-60:-14] if len(trs) > 20 else (trs[:-14] if len(trs) > 14 else trs)
    prior_atr = (sum(prior) / len(prior)) if prior else recent_atr
    contracting = bool(prior_atr) and recent_atr < 0.80 * prior_atr
    expanding = bool(prior_atr) and recent_atr > 1.25 * prior_atr
    vol_regime = "contracting" if contracting else "expanding" if expanding else "steady"

    pat_text = " ".join(patterns).lower()
    rangebound = ("trading range" in pat_text or "consolidation" in pat_text or bias == "neutral")
    trending = bias in ("bearish", "bullish") and (
        "higher highs" in structure or "lower highs" in structure or abs(pct) >= 2
    )
    sup_s = f"{support:.2f}" if support is not None else f"{lo:.2f}"
    res_s = f"{resistance:.2f}" if resistance is not None else f"{hi:.2f}"
    if trending:
        direction = "puts or put spreads" if bias == "bearish" else "calls or call spreads"
        strategy = (f"trending {bias} - favors directional {direction}; scalp the continuation "
                    f"intraday, or LEAPS on the daily for the bigger trend.")
    elif rangebound:
        strategy = (f"range-bound{' and contracting' if contracting else ''} - favors a neutral, "
                    f"premium-selling structure like an iron condor with short strikes outside "
                    f"{sup_s} to {res_s}.")
    elif expanding:
        strategy = ("volatility is expanding with no clear direction - a long straddle or strangle "
                    "fits, or stand aside until it picks a side.")
    else:
        strategy = "no clean structure right now - better to wait for a setup."
    range_bounds = [support, resistance] if (support is not None and resistance is not None) else None

    signal = None
    markers = payload.get("markers") or []
    if markers:
        m = markers[-1]
        ago = sum(1 for c in candles if c["time"] > m["time"])
        signal = f"Last signal was a {m['side']} about {ago} bars ago."

    volume_note = None
    vols = [v["value"] for v in (payload.get("volume") or [])]
    if len(vols) >= 5:
        w = vols[-20:]
        avg = sum(w) / len(w) if w else 0
        if avg:
            x = vols[-1] / avg
            if x >= 1.5 or x <= 0.6:
                volume_note = f"Last-bar volume is about {x:.1f} times the recent average."

    times = [c["time"] for c in candles]
    t_first, t_last = times[0], times[-1]
    t_recent = times[max(0, len(times) - 40)]
    spike_time = None
    spike_mult = None
    if vols and len(vols) >= 10:
        avg_all = sum(vols) / len(vols)
        if avg_all:
            si = max(range(len(vols)), key=lambda i: vols[i])
            mult = vols[si] / avg_all
            if mult >= 2.0:
                spike_time = times[si]
                spike_mult = mult
                ago = len(times) - 1 - si
                volume_note = f"Biggest volume spike was {ago} bars ago, about {mult:.1f} times average."
    signal_time = markers[-1]["time"] if markers else None

    levels = []
    if resistance is not None:
        levels.append({"price": round(resistance, 2), "kind": "resistance", "label": f"R {resistance:.2f}"})
    if support is not None:
        levels.append({"price": round(support, 2), "kind": "support", "label": f"S {support:.2f}"})

    return {
        "symbol": sym, "timeframe": tf, "empty": False,
        "last": last, "pct": pct, "lo": lo, "hi": hi, "where": where,
        "trend": trend, "structure": structure,
        "support": support, "resistance": resistance,
        "patterns": patterns, "signal": signal, "volume_note": volume_note,
        "bearish_setups": bearish_setups, "bullish_setups": bullish_setups, "bias": bias,
        "vol_regime": vol_regime, "strategy": strategy, "range_bounds": range_bounds,
        "levels": levels,
        "times": times, "t_first": t_first, "t_last": t_last, "t_recent": t_recent,
        "spike_time": spike_time, "spike_mult": spike_mult, "signal_time": signal_time,
    }


def read(a: dict) -> str:
    """Speech-friendly read built from an analyze() dict."""
    if a.get("empty"):
        return f"Here is {a['symbol']} on the {a['timeframe']}, but I got no bars back."
    parts = [
        f"Here is {a['symbol']} on the {a['timeframe']} — {a['trend']}, last {a['last']:.2f}, "
        f"{a['pct']:+.1f} percent over the window, trading {a['where']} of the "
        f"{a['lo']:.2f} to {a['hi']:.2f} range."
    ]
    parts.append(f"Structure is {a['structure']}.")
    sr = []
    if a["resistance"] is not None:
        sr.append(f"resistance near {a['resistance']:.2f}")
    if a["support"] is not None:
        sr.append(f"support near {a['support']:.2f}")
    if sr:
        parts.append("Nearest " + " and ".join(sr) + ".")
    if a["patterns"]:
        parts.append("Pattern: " + "; ".join(a["patterns"]) + ".")
    if a["signal"]:
        parts.append(a["signal"])
    if a["volume_note"]:
        parts.append(a["volume_note"])
    return " ".join(parts)


def summarize_payload(payload: dict) -> str:
    return read(analyze(payload))
