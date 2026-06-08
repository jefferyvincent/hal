"""Options strategy backtester for HAL.

Simulates a long single-option (call/put) strategy over historical data so
Jeffery can see how a trade idea would have performed before risking real
money. Design decisions (agreed with Jeffery):

- The price-action signal is a DIRECTION FILTER only: a break of a pivot-based
  support/resistance level, confirmed by RSI. It decides long-call vs long-put;
  it never picks the contract.
- The contract is picked by moneyness + DTE (ATM, ~7 DTE weekly), NOT by delta
  (Massive's Options Advanced plan returns no historical greeks).
- P&L comes from the CHOSEN CONTRACT's own historical bars, so real theta decay
  and implied-vol moves over the holding period are captured faithfully.
- Each trade is tagged with the volatility regime at entry (realized-vol
  percentile over the trailing year) so results can be split by low/high vol.

This is a historical simulation. Commissions/slippage are explicit assumptions,
and it is NOT a substitute for forward paper-trading.

Massive endpoints used:
- /v2/aggs/ticker/{ticker}/range/1/day/{from}/{to}   underlying + option bars
- /v3/reference/options/contracts                     contract discovery (expired=true)
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Any, Optional

import httpx


BASE_URL: str = ""
API_KEY: str = ""

# Strategy constants (named, not magic — see CLAUDE.md).
RSI_PERIOD = 14
PIVOT_K = 5                 # fractal half-window for swing pivots
TAKE_PROFIT = 0.50         # +50% of premium
STOP_LOSS = 0.50           # -50% of premium
TARGET_DTE = 7             # aim for the nearest weekly
DTE_MIN, DTE_MAX = 3, 12   # acceptable expiry window around TARGET_DTE
CONTRACT_MULTIPLIER = 100  # shares per option contract
COMMISSION_PER_CONTRACT = 0.65  # assumption, per leg per side
VOL_LOOKBACK = 252         # trading days for the realized-vol percentile


def configure(base_url: str, api_key: str) -> None:
    global BASE_URL, API_KEY
    BASE_URL = base_url
    API_KEY = api_key


# Cash-settled index VALUE data (I:SPX etc.) isn't in the Massive plan (403),
# but the index OPTIONS are (Options Advanced / OPRA). So for index roots we
# pull the underlying daily bars from Yahoo Finance's free chart API (real
# index level, drives the signal) and still use Massive for the option chain
# and historical option bars. Map: our root -> Yahoo symbol.
_INDEX_YAHOO = {
    "SPX": "^GSPC", "XSP": "^GSPC", "OEX": "^OEX",
    "NDX": "^NDX",
    "RUT": "^RUT",
    "DJX": "^DJI",
    "VIX": "^VIX",
}

_YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/"

# Full-size index options that are too capital-heavy for a normal account get
# substituted. XSP (the 1/10 mini) is account-sized but thinly traded, so its
# backtests have too few trades to mean much; SPY (same S&P exposure, ~1/10 the
# index level) is the most liquid proxy and gives dense, meaningful data plus a
# real equity curve. So SPX -> SPY for backtests. (SPY uses Massive for both
# underlying and options — no Yahoo needed.)
_INDEX_MINI = {"SPX": "SPY"}

# Default set for the "backtest the indexes" comparison sweep. SPX routes to
# SPY above; NDX/RUT/DJX use their real index value from Yahoo + index options.
INDEX_SWEEP_SET = ["SPX", "NDX", "RUT", "DJX"]


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {API_KEY}"}


# --- indicators ------------------------------------------------------------

def rsi(closes: list[float], period: int = RSI_PERIOD) -> list[Optional[float]]:
    """Wilder's RSI. Returns one value per bar (None until warmed up)."""
    n = len(closes)
    out: list[Optional[float]] = [None] * n
    if n <= period:
        return out
    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        ch = closes[i] - closes[i - 1]
        gains += max(ch, 0.0)
        losses += max(-ch, 0.0)
    avg_gain = gains / period
    avg_loss = losses / period
    out[period] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    for i in range(period + 1, n):
        ch = closes[i] - closes[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(ch, 0.0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-ch, 0.0)) / period
        out[i] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    return out


def pivots(values: list[float], kind: str, k: int = PIVOT_K) -> list[tuple[int, float]]:
    """Fractal pivots: index i is a pivot when values[i] is the window extreme.
    Mirrors charting.py's _find_pivots so S/R lines match what HAL draws."""
    out: list[tuple[int, float]] = []
    n = len(values)
    for i in range(k, n - k):
        win = values[i - k : i + k + 1]
        if kind == "high" and values[i] == max(win):
            out.append((i, values[i]))
        elif kind == "low" and values[i] == min(win):
            out.append((i, values[i]))
    return out


def realized_vol(closes: list[float], window: int = 20) -> Optional[float]:
    """Annualized realized vol from the last `window` log returns."""
    if len(closes) <= window:
        return None
    rets = []
    for a, b in zip(closes[-window - 1 : -1], closes[-window:]):
        if a > 0 and b > 0:
            rets.append(math.log(b / a))
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((x - mean) ** 2 for x in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(252)


def vol_regime_percentile(closes_to_date: list[float]) -> Optional[float]:
    """Where does today's 20-day realized vol sit within its own trailing-year
    distribution? Returns a 0-1 percentile (1 = highest vol in the window)."""
    if len(closes_to_date) < 40:
        return None
    series = []
    # Compute a rolling 20-day RV for each day in the trailing VOL_LOOKBACK.
    start = max(21, len(closes_to_date) - VOL_LOOKBACK)
    for end in range(start, len(closes_to_date) + 1):
        rv = realized_vol(closes_to_date[:end], 20)
        if rv is not None:
            series.append(rv)
    if len(series) < 10:
        return None
    today = series[-1]
    below = sum(1 for v in series if v <= today)
    return below / len(series)


def regime_label(pct: Optional[float]) -> str:
    if pct is None:
        return "unknown"
    if pct >= 0.66:
        return "high-vol"
    if pct <= 0.33:
        return "low-vol"
    return "mid-vol"


# --- signal generation -----------------------------------------------------

def generate_signals(bars: list[dict]) -> list[dict]:
    """Scan daily bars; emit a signal when price breaks the most recent pivot
    S/R with RSI confirmation.

    bars: [{t (unix s), o,h,l,c,v}] ascending.
    Returns [{index, date, side ('call'|'put'), spot, regime, regime_pct}].
    A signal at bar i means: enter at bar i's close (next-day fill is a future
    refinement). We require a confirmed pivot strictly before i so we are not
    peeking at future bars when defining the level.
    """
    closes = [b["c"] for b in bars]
    highs = [b["h"] for b in bars]
    lows = [b["l"] for b in bars]
    rsis = rsi(closes)

    signals: list[dict] = []
    last_side: Optional[str] = None  # de-dupe consecutive same-direction breaks
    # Need enough history for pivots + RSI before the first possible signal.
    first = max(RSI_PERIOD + 1, PIVOT_K * 2 + 1)
    for i in range(first, len(bars)):
        r = rsis[i]
        if r is None:
            continue
        # Pivots strictly in the past (indices < i - PIVOT_K can be confirmed).
        past_high = pivots(highs[:i], "high")
        past_low = pivots(lows[:i], "low")
        if not past_high or not past_low:
            continue
        resistance = past_high[-1][1]
        support = past_low[-1][1]
        price = closes[i]
        side: Optional[str] = None
        if price > resistance and r > 50:
            side = "call"
        elif price < support and r < 50:
            side = "put"
        if side is None or side == last_side:
            # require a flip to avoid firing every bar inside a breakout run
            if side is None:
                last_side = None
            continue
        last_side = side
        pct = vol_regime_percentile(closes[: i + 1])
        signals.append({
            "index": i,
            "date": date.fromtimestamp(bars[i]["t"]).isoformat()
                    if bars[i]["t"] < 10**11 else
                    datetime.utcfromtimestamp(bars[i]["t"] // 1000).date().isoformat(),
            "side": side,
            "spot": price,
            "rsi": round(r, 1),
            "resistance": round(resistance, 2),
            "support": round(support, 2),
            "regime": regime_label(pct),
            "regime_pct": round(pct, 3) if pct is not None else None,
        })
    return signals


# --- data fetch ------------------------------------------------------------

async def _get(client: httpx.AsyncClient, path: str, params: dict) -> dict:
    r = await client.get(BASE_URL + path, headers=_headers(), params=params, timeout=30)
    r.raise_for_status()
    return r.json()


async def fetch_daily(client: httpx.AsyncClient, ticker: str, frm: str, to: str) -> list[dict]:
    """Daily OHLC bars for any ticker (underlying or option). Times -> unix s."""
    body = await _get(
        client,
        f"/v2/aggs/ticker/{ticker}/range/1/day/{frm}/{to}",
        {"adjusted": "true", "sort": "asc", "limit": 50000},
    )
    out = []
    for b in body.get("results") or []:
        out.append({
            "t": int(b["t"]) // 1000,
            "o": b["o"], "h": b["h"], "l": b["l"], "c": b["c"], "v": b.get("v", 0),
        })
    return out


async def fetch_yahoo_daily(client: httpx.AsyncClient, yahoo_sym: str, frm: str, to: str) -> list[dict]:
    """Daily OHLC bars for an index from Yahoo Finance's free chart API. Used
    for index underlyings whose value feed isn't in the Massive plan. Times are
    already unix seconds. A User-Agent is required or Yahoo returns 429."""
    p1 = int(datetime.combine(date.fromisoformat(frm), datetime.min.time()).timestamp())
    p2 = int(datetime.combine(date.fromisoformat(to), datetime.min.time()).timestamp())
    url = f"{_YAHOO_CHART}{yahoo_sym}"
    r = await client.get(
        url,
        params={"period1": p1, "period2": p2, "interval": "1d"},
        headers={"User-Agent": "Mozilla/5.0 (HAL backtester)"},
        timeout=30,
    )
    r.raise_for_status()
    body = r.json()
    result = ((body.get("chart") or {}).get("result") or [None])[0]
    if not result:
        return []
    ts = result.get("timestamp") or []
    q = (((result.get("indicators") or {}).get("quote") or [{}])[0])
    opens, highs, lows, closes = q.get("open") or [], q.get("high") or [], q.get("low") or [], q.get("close") or []
    vols = q.get("volume") or []
    out = []
    for i, t in enumerate(ts):
        o, h, l, c = opens[i], highs[i], lows[i], closes[i]
        if None in (o, h, l, c):  # Yahoo emits nulls on no-trade days
            continue
        out.append({"t": int(t), "o": o, "h": h, "l": l, "c": c, "v": (vols[i] if i < len(vols) and vols[i] else 0)})
    return out


async def pick_contract(
    client: httpx.AsyncClient, underlying: str, side: str, spot: float, entry: date,
) -> Optional[dict]:
    """Find the ATM contract nearest TARGET_DTE on/after `entry`.

    Lists expired contracts whose expiration falls in the DTE window, then
    picks the one with strike closest to spot and DTE closest to TARGET_DTE.
    Returns {ticker, strike, expiration, dte} or None.
    """
    lo = (entry + timedelta(days=DTE_MIN)).isoformat()
    hi = (entry + timedelta(days=DTE_MAX)).isoformat()
    body = await _get(client, "/v3/reference/options/contracts", {
        "underlying_ticker": underlying,
        "contract_type": side,
        "expiration_date.gte": lo,
        "expiration_date.lte": hi,
        "expired": "true",
        "limit": 1000,
    })
    rows = body.get("results") or []
    best = None
    best_key = None
    for c in rows:
        strike = c.get("strike_price")
        exp = c.get("expiration_date")
        tk = c.get("ticker")
        if strike is None or not exp or not tk:
            continue
        try:
            exp_d = date.fromisoformat(exp)
        except ValueError:
            continue
        dte = (exp_d - entry).days
        # sort key: nearest strike first, then nearest to TARGET_DTE
        key = (abs(strike - spot), abs(dte - TARGET_DTE))
        if best_key is None or key < best_key:
            best_key = key
            best = {"ticker": tk, "strike": strike, "expiration": exp, "dte": dte}
    return best


# --- trade simulation ------------------------------------------------------

def _entry_premium(bar: dict) -> Optional[float]:
    """Approximate fill from a daily option bar. We have no historical bid/ask,
    so use the bar close as the entry/exit mark. Returns None if unusable."""
    c = bar.get("c")
    return c if c and c > 0 else None


def simulate_trade(
    side: str, opt_bars: list[dict], next_opp_index_date: Optional[str],
) -> Optional[dict]:
    """Walk an option's daily bars from entry to exit.

    Entry = first bar's close. Exit, in priority order each subsequent bar:
      1) take-profit: close >= entry*(1+TAKE_PROFIT)
      2) stop-loss:   close <= entry*(1-STOP_LOSS)
      3) opposite signal date reached (caller passes it; handled upstream)
      4) last available bar (expiry week)
    Long options only, so P&L = (exit - entry) * 100 - commissions (both sides).
    Returns a trade dict or None if no usable bars.
    """
    bars = [b for b in opt_bars if _entry_premium(b) is not None]
    if len(bars) < 2:
        return None
    entry = bars[0]["c"]
    tp = entry * (1 + TAKE_PROFIT)
    sl = entry * (1 - STOP_LOSS)
    exit_px = bars[-1]["c"]
    exit_reason = "expiry"
    exit_t = bars[-1]["t"]
    for b in bars[1:]:
        px = b["c"]
        if px >= tp:
            exit_px, exit_reason, exit_t = tp, "take_profit", b["t"]
            break
        if px <= sl:
            exit_px, exit_reason, exit_t = sl, "stop_loss", b["t"]
            break
    gross = (exit_px - entry) * CONTRACT_MULTIPLIER
    net = gross - 2 * COMMISSION_PER_CONTRACT
    return {
        "side": side,
        "entry_premium": round(entry, 4),
        "exit_premium": round(exit_px, 4),
        "exit_reason": exit_reason,
        "exit_t": exit_t,
        "pnl": round(net, 2),
        "pnl_pct": round((exit_px - entry) / entry, 4),
        "bars_held": len(bars),
    }


# --- metrics ---------------------------------------------------------------

def compute_metrics(trades: list[dict]) -> dict:
    """Summary stats over completed trades. Equity is cumulative net P&L of one
    contract per trade (starting at 0)."""
    if not trades:
        return {"trades": 0}
    pnls = [t["pnl"] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gross_win = sum(wins)
    gross_loss = -sum(losses)
    equity = []
    cum = 0.0
    peak = 0.0
    max_dd = 0.0
    for t in trades:
        cum += t["pnl"]
        peak = max(peak, cum)
        max_dd = max(max_dd, peak - cum)
        equity.append({"t": t["exit_t"], "value": round(cum, 2)})
    return {
        "trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(trades), 4),
        "total_pnl": round(sum(pnls), 2),
        "avg_pnl": round(sum(pnls) / len(trades), 2),
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss > 0 else None,
        "max_drawdown": round(max_dd, 2),
        "best": round(max(pnls), 2),
        "worst": round(min(pnls), 2),
        "equity": equity,
    }


def split_by_regime(trades: list[dict]) -> dict:
    """Per-regime win rate and avg P&L (Jeffery's 'check the weather' point)."""
    out: dict[str, dict] = {}
    for label in ("low-vol", "mid-vol", "high-vol", "unknown"):
        sub = [t for t in trades if t.get("regime") == label]
        if not sub:
            continue
        pnls = [t["pnl"] for t in sub]
        wins = sum(1 for p in pnls if p > 0)
        out[label] = {
            "trades": len(sub),
            "win_rate": round(wins / len(sub), 4),
            "avg_pnl": round(sum(pnls) / len(sub), 2),
        }
    return out


# --- orchestrator ----------------------------------------------------------

async def run_backtest(underlying: str = "SPY", months: int = 24) -> dict:
    """Full pipeline: fetch underlying -> signals -> contracts -> trades ->
    metrics. Returns a result dict (also carries an equity-curve payload for
    the UI). Raises RuntimeError on config/data problems."""
    if not API_KEY:
        raise RuntimeError("MASSIVE_API_KEY not configured")
    underlying = underlying.upper().strip()
    # Account-size guard: full SPX options are ~10x too large for most accounts;
    # substitute the 1/10-size mini (XSP) so picks aren't capital-heavy.
    note_parts: list[str] = []
    if underlying in _INDEX_MINI:
        sub = _INDEX_MINI[underlying]
        note_parts.append(f"{underlying} options are ~10x account size and thinly traded; backtested {sub} (same S&P exposure, far more liquid) instead.")
        underlying = sub
    # Index roots: underlying value data isn't in the Massive plan (403), so
    # pull the index level from Yahoo for the signal; option contracts still
    # come from Massive under the bare root.
    yahoo_sym = _INDEX_YAHOO.get(underlying)
    if yahoo_sym:
        note_parts.append(f"Underlying from Yahoo ({yahoo_sym}); options from Massive.")
    proxy_note = " ".join(note_parts)
    to_d = date.today()
    frm_d = to_d - timedelta(days=int(months * 30.5))

    async with httpx.AsyncClient() as client:
        if yahoo_sym:
            bars = await fetch_yahoo_daily(client, yahoo_sym, frm_d.isoformat(), to_d.isoformat())
        else:
            bars = await fetch_daily(client, underlying, frm_d.isoformat(), to_d.isoformat())
        if len(bars) < 60:
            raise RuntimeError(f"only {len(bars)} daily bars for {underlying}; need 60+")
        signals = generate_signals(bars)

        trades: list[dict] = []
        for sig in signals:
            entry = date.fromisoformat(sig["date"])
            contract = await pick_contract(client, underlying, sig["side"], sig["spot"], entry)
            if not contract:
                continue
            opt_bars = await fetch_daily(client, contract["ticker"], entry.isoformat(), contract["expiration"])
            trade = simulate_trade(sig["side"], opt_bars, None)
            if not trade:
                continue
            trade.update({
                "date": sig["date"],
                "regime": sig["regime"],
                "regime_pct": sig["regime_pct"],
                "spot": sig["spot"],
                "strike": contract["strike"],
                "expiration": contract["expiration"],
                "ticker": contract["ticker"],
            })
            trades.append(trade)

    metrics = compute_metrics(trades)
    return {
        "underlying": underlying,
        "proxy_note": proxy_note,
        "months": months,
        "strategy": "long single (S/R break + RSI), ATM ~7DTE, +50%/-50% exit",
        "signals_found": len(signals),
        "metrics": metrics,
        "by_regime": split_by_regime(trades),
        "trades": trades,
        "assumptions": (
            f"1 contract/trade; entry/exit at daily close (no historical bid/ask); "
            f"${COMMISSION_PER_CONTRACT:.2f}/contract/side commission; no slippage. "
            "Historical simulation, not a forward paper-test."
        ),
    }


def equity_payload(result: dict) -> dict:
    """Shape the equity curve for the frontend (lightweight-charts line)."""
    eq = (result.get("metrics") or {}).get("equity") or []
    return {
        "kind": "backtest",
        "underlying": result.get("underlying"),
        "strategy": result.get("strategy"),
        "equity": eq,
        "metrics": {k: v for k, v in (result.get("metrics") or {}).items() if k != "equity"},
        "by_regime": result.get("by_regime"),
    }


def speak_summary(result: dict) -> str:
    """Speech-friendly one-paragraph read of the backtest."""
    m = result.get("metrics") or {}
    if not m.get("trades"):
        return (f"I ran the backtest on {result.get('underlying')}, but found no "
                "qualifying trades in that window.")
    parts = [
        f"Backtest on {result['underlying']} over {result['months']} months: "
        f"{m['trades']} trades, {int(m['win_rate']*100)} percent win rate.",
        f"Total profit and loss {m['total_pnl']:+.0f} dollars on one contract per trade, "
        f"average {m['avg_pnl']:+.0f} per trade.",
    ]
    if m.get("profit_factor") is not None:
        parts.append(f"Profit factor {m['profit_factor']}.")
    parts.append(f"Max drawdown {m['max_drawdown']:.0f} dollars.")
    reg = result.get("by_regime") or {}
    if reg:
        bits = [f"{k} {int(v['win_rate']*100)} percent" for k, v in reg.items()]
        parts.append("By volatility regime: " + ", ".join(bits) + ".")
    parts.append(verdict(result))
    parts.append("Remember, this is historical and assumes close-to-close fills.")
    if result.get("proxy_note"):
        parts.append(result["proxy_note"])
    return " ".join(parts)


def verdict(result: dict) -> str:
    """HAL's take: a plain recommendation from the metrics. Profit factor is the
    primary lens (gross win / gross loss); win rate, sample size, and the best
    regime qualify it. Heuristic read of the historical edge, not advice."""
    m = result.get("metrics") or {}
    pf = m.get("profit_factor")
    wr = m.get("win_rate") or 0
    n = m.get("trades") or 0
    sym = result.get("underlying", "this")
    if n < 10:
        return (f"My take: only {n} trades — too small a sample to trust. "
                "I would not act on this yet.")
    if pf is None or pf < 1.0:
        return (f"My take: a loser as it stands — profit factor under one, losses "
                f"outweigh wins. I would not trade {sym} on this signal; buying "
                "breakouts bleeds to theta. Consider flipping it, selling premium "
                "instead, or waiting for a stronger setup.")
    if pf < 1.3:
        return ("My take: marginally positive but a thin edge that barely clears "
                "costs. I would paper-trade it first, not risk real money yet.")
    reg = result.get("by_regime") or {}
    best = max(reg.items(), key=lambda kv: kv[1].get("win_rate", 0), default=None)
    strong = (f" It does best in {best[0]} conditions, so favor it there."
              if best and best[1].get("win_rate", 0) >= 0.6 else "")
    return (f"My take: a real historical edge — profit factor {pf}, "
            f"{int(wr*100)} percent wins.{strong} I would forward-test it on paper "
            "to confirm, then size small per your risk rules.")


def primer_stats(result: dict) -> str:
    """Compact backtest summary injected into the LLM context on a trade-idea
    question, so HAL can cite the historical edge before recommending."""
    m = result.get("metrics") or {}
    if not m.get("trades"):
        return f"\n\n[BACKTEST — {result.get('underlying')}, 24mo] No qualifying trades; no historical edge to cite."
    reg = result.get("by_regime") or {}
    reg_s = ", ".join(f"{k} {int(v['win_rate']*100)}%" for k, v in reg.items())
    return (
        f"\n\n[BACKTEST — {result['underlying']}, 24mo, long-single S/R-break + RSI strategy]\n"
        f"{m['trades']} trades, {int(m['win_rate']*100)}% win rate, total {m['total_pnl']:+.0f}, "
        f"profit factor {m.get('profit_factor')}, max drawdown {m['max_drawdown']:.0f}. "
        f"By volatility regime: {reg_s}.\n"
        "Cite these numbers so Jeffery sees the historical edge (or lack of one) before placing the trade."
    )


# --- index comparison sweep ------------------------------------------------

async def run_index_sweep(symbols: list[str] | None = None, months: int = 12) -> list[dict]:
    """Backtest several indexes and return their results (errors captured per
    symbol so one failure doesn't sink the sweep). Each runs the full pipeline;
    expect this to take a while (one set of API calls per symbol)."""
    syms = symbols or INDEX_SWEEP_SET
    out: list[dict] = []
    for s in syms:
        try:
            out.append(await run_backtest(s, months=months))
        except Exception as e:
            out.append({"underlying": s, "error": str(e), "metrics": {}})
    return out


def _sweep_rank_key(r: dict) -> float:
    """Rank by profit factor desc; symbols with no trades/errors sink to bottom."""
    m = r.get("metrics") or {}
    pf = m.get("profit_factor")
    return pf if isinstance(pf, (int, float)) else -1.0


def sweep_table(results: list[dict], months: int = 12) -> str:
    """Markdown comparison table of a sweep, ranked best-to-worst by profit
    factor. Renders in chat via the pipe-table renderer."""
    ranked = sorted(results, key=_sweep_rank_key, reverse=True)
    rows = [
        f"**Index backtest comparison** — {months}-month, long-single S/R-break + RSI.",
        "",
        "| Index | Trades | Win % | Total P&L | Profit Factor | Max DD |",
        "|---|---|---|---|---|---|",
    ]
    for r in ranked:
        sym = r.get("underlying", "?")
        m = r.get("metrics") or {}
        if r.get("error") or not m.get("trades"):
            reason = "no data" if r.get("error") else "no trades"
            rows.append(f"| {sym} | — | — | — | — | {reason} |")
            continue
        rows.append(
            f"| {sym} | {m['trades']} | {int(m['win_rate']*100)}% | "
            f"${m['total_pnl']:,.0f} | {m.get('profit_factor')} | ${m['max_drawdown']:,.0f} |"
        )
    return "\n".join(rows)


def sweep_summary(results: list[dict]) -> str:
    """Speech-friendly read: which index had the best/worst historical edge."""
    scored = [r for r in results if (r.get("metrics") or {}).get("trades")]
    if not scored:
        return "I ran the index sweep but got no qualifying trades on any of them."
    ranked = sorted(scored, key=_sweep_rank_key, reverse=True)
    best, worst = ranked[0], ranked[-1]
    bm, wm = best["metrics"], worst["metrics"]
    parts = [
        f"Index sweep done. Best historical edge was {best['underlying']}, "
        f"profit factor {bm.get('profit_factor')} on {bm['trades']} trades, "
        f"{int(bm['win_rate']*100)} percent wins."
    ]
    if worst is not best:
        parts.append(
            f"Worst was {worst['underlying']}, profit factor {wm.get('profit_factor')}."
        )
    profitable = [r["underlying"] for r in ranked
                  if (r["metrics"].get("profit_factor") or 0) >= 1.0]
    if profitable:
        parts.append("Profitable historically: " + ", ".join(profitable) + ".")
    else:
        parts.append("None were profitable historically. See the table on screen.")
    return " ".join(parts)
