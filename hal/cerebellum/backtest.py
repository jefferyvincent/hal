"""Options strategy backtester for HAL.

Simulates a long single-option (call/put) strategy over historical data so
the user can see how a trade idea would have performed before risking real
money. Design decisions (agreed with the user):

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
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Optional

import httpx

from hal.brainstem.config import USER_NAME
from hal.cerebellum import strategy
from hal.cerebellum.execution import SimBroker


BASE_URL: str = ""
API_KEY: str = ""

# Strategy constants (named, not magic — see CLAUDE.md).
RSI_PERIOD = 14
PIVOT_K = 5                 # fractal half-window for swing pivots
# Exit policy (stop / take-profit %) now comes from the vault trading-rules via
# strategy.exit_levels(), so the backtest validates the SAME exit the live trader
# runs. strategy._FALLBACK_*_PCT supplies the historical ±50% only if the vault
# defines none.
TARGET_DTE = 7             # aim for the nearest weekly
DTE_MIN, DTE_MAX = 3, 12   # acceptable expiry window around TARGET_DTE
CONTRACT_MULTIPLIER = 100  # shares per option contract
COMMISSION_PER_CONTRACT = 0.65  # assumption, per leg per side
VOL_LOOKBACK = 252         # trading days for the realized-vol percentile


@dataclass(frozen=True)
class StrategyParams:
    """Tunable knobs for the S/R-break + RSI signal and the contract pick.

    Defaults reproduce the original hardcoded behavior, so generate_signals(bars)
    and run_backtest(...) are byte-for-byte unchanged unless a caller passes
    overrides. The optimizer (cerebellum.optimize) sweeps these to find a robust
    configuration; stop_pct/tp_pct of None means "use the vault trading-rules
    exit" (the live policy), so the default backtest still validates the same
    exit the live trader runs.
    """
    rsi_period: int = RSI_PERIOD
    pivot_k: int = PIVOT_K
    rsi_long: float = 50.0     # RSI must EXCEED this to confirm a call (break up)
    rsi_short: float = 50.0    # RSI must be BELOW this to confirm a put (break down)
    target_dte: int = TARGET_DTE
    dte_min: int = DTE_MIN
    dte_max: int = DTE_MAX
    stop_pct: Optional[float] = None   # None → vault rules
    tp_pct: Optional[float] = None      # None → vault rules


DEFAULT_PARAMS = StrategyParams()


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

def generate_signals(bars: list[dict], params: StrategyParams = DEFAULT_PARAMS) -> list[dict]:
    """Scan daily bars; emit a signal when price breaks the most recent pivot
    S/R with RSI confirmation.

    bars: [{t (unix s), o,h,l,c,v}] ascending.
    params: signal tuning (RSI period, pivot half-window, RSI thresholds); the
    defaults reproduce the original fixed strategy.
    Returns [{index, date, side ('call'|'put'), spot, regime, regime_pct}].
    A signal at bar i means: enter at bar i's close (next-day fill is a future
    refinement). We require a confirmed pivot strictly before i so we are not
    peeking at future bars when defining the level.
    """
    closes = [b["c"] for b in bars]
    highs = [b["h"] for b in bars]
    lows = [b["l"] for b in bars]
    rsis = rsi(closes, params.rsi_period)

    signals: list[dict] = []
    last_side: Optional[str] = None  # de-dupe consecutive same-direction breaks
    # Need enough history for pivots + RSI before the first possible signal.
    first = max(params.rsi_period + 1, params.pivot_k * 2 + 1)
    for i in range(first, len(bars)):
        r = rsis[i]
        if r is None:
            continue
        # Pivots strictly in the past (indices < i - pivot_k can be confirmed).
        past_high = pivots(highs[:i], "high", params.pivot_k)
        past_low = pivots(lows[:i], "low", params.pivot_k)
        if not past_high or not past_low:
            continue
        resistance = past_high[-1][1]
        support = past_low[-1][1]
        price = closes[i]
        side: Optional[str] = None
        if price > resistance and r > params.rsi_long:
            side = "call"
        elif price < support and r < params.rsi_short:
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
    params: StrategyParams = DEFAULT_PARAMS,
) -> Optional[dict]:
    """Find the ATM contract nearest params.target_dte on/after `entry`.

    Lists expired contracts whose expiration falls in the DTE window, then
    picks the one with strike closest to spot and DTE closest to target_dte.
    Returns {ticker, strike, expiration, dte} or None.
    """
    lo = (entry + timedelta(days=params.dte_min)).isoformat()
    hi = (entry + timedelta(days=params.dte_max)).isoformat()
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
        # sort key: nearest strike first, then nearest to target_dte
        key = (abs(strike - spot), abs(dte - params.target_dte))
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
    symbol: str = "OPT", sim: Optional[SimBroker] = None,
    rules: Optional[dict] = None,
) -> Optional[dict]:
    """Walk an option's daily bars from entry to exit.

    Entry = first bar's close. Exit, in priority order each subsequent bar:
      1) take-profit / 2) stop-loss at the vault-configured premium levels
         (strategy.exit_levels — same policy the live trader runs; pass a loaded
         `rules` dict to avoid re-reading the vault per trade)
      3) opposite signal date reached (caller passes it; handled upstream)
      4) last available bar (expiry week)

    The entry and exit are constructed via the SAME broker.prepare_order used for
    live Alpaca orders and filled through the shared SimBroker (execution.py), so
    P&L (= (exit - entry) * 100 - commissions both sides) comes from the same
    order/fill path the live trader runs. Long options only. Pass a shared `sim`
    to accumulate fills across trades; the default fresh sim scores one round
    trip. Returns a trade dict or None if no usable bars.
    """
    bars = [b for b in opt_bars if _entry_premium(b) is not None]
    if len(bars) < 2:
        return None
    entry = bars[0]["c"]
    sl, tp = strategy.exit_levels(entry, rules)
    exit_px = bars[-1]["c"]
    exit_reason = "expiry"
    exit_t = bars[-1]["t"]
    for b in bars[1:]:
        # Same exit rule the live bracket monitor runs (strategy.exit_signal).
        kind = strategy.exit_signal(b["c"], sl, tp)
        if kind == "take_profit":
            exit_px, exit_reason, exit_t = tp, "take_profit", b["t"]
            break
        if kind == "stop":
            exit_px, exit_reason, exit_t = sl, "stop_loss", b["t"]
            break

    sim = sim or SimBroker(CONTRACT_MULTIPLIER, COMMISSION_PER_CONTRACT)
    realized_before = sim.realized_pnl
    # Build entry/exit via the shared OrderIntent → broker.prepare_order path,
    # then fill through SimBroker — the same construction the live trader uses.
    sim.set_price(symbol, entry)
    sim.submit_order(strategy.OrderIntent(side="buy", qty=1, symbol=symbol).to_spec())
    sim.set_price(symbol, exit_px)
    sim.submit_order(strategy.OrderIntent(side="sell", qty=1, symbol=symbol).to_spec())
    net = round(sim.realized_pnl - realized_before, 2)
    return {
        "side": side,
        "entry_premium": round(entry, 4),
        "exit_premium": round(exit_px, 4),
        "exit_reason": exit_reason,
        "exit_t": exit_t,
        "pnl": net,
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

    # --- Tearsheet stats (nautilus PortfolioAnalyzer spirit) ----------------
    # Per-trade, NOT annualized: trades aren't time-uniform, so annualizing a
    # per-trade Sharpe would invent a cadence the data doesn't have. Read these
    # as the distribution shape of one-contract trade P&L.
    n = len(trades)
    mean = sum(pnls) / n
    std = math.sqrt(sum((p - mean) ** 2 for p in pnls) / n)
    downside = math.sqrt(sum(min(p, 0.0) ** 2 for p in pnls) / n)
    avg_win = round(gross_win / len(wins), 2) if wins else 0.0
    avg_loss = round(sum(losses) / len(losses), 2) if losses else 0.0  # negative
    return {
        "trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(trades), 4),
        "total_pnl": round(sum(pnls), 2),
        "avg_pnl": round(mean, 2),
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss > 0 else None,
        "max_drawdown": round(max_dd, 2),
        "max_drawdown_pct": round(max_dd / peak, 4) if peak > 0 else None,  # give-back of peak cumulative P&L
        "expectancy": round(mean, 2),  # avg $ per trade
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "payoff_ratio": round(avg_win / abs(avg_loss), 2) if avg_loss < 0 else None,
        "sharpe_per_trade": round(mean / std, 3) if std > 0 else None,
        "sortino_per_trade": round(mean / downside, 3) if downside > 0 else None,
        # t-stat of mean trade P&L vs zero (= sharpe_per_trade · √n). This is the
        # significance test profit factor and win-rate hide: a PF of 1.6 on 6
        # noisy trades and one on 60 steady trades read the same on PF but not
        # here. qlib scores signals by IC-IR (mean/std of the edge) for exactly
        # this reason; this is that idea applied to realized trade returns.
        # |t| ≳ 2 ⇒ the edge is unlikely to be a fluke of the sample.
        "t_stat": round(mean / (std / math.sqrt(n)), 2) if std > 0 else None,
        "best": round(max(pnls), 2),
        "worst": round(min(pnls), 2),
        "equity": equity,
    }


def split_by_regime(trades: list[dict]) -> dict:
    """Per-regime win rate and avg P&L (the user's 'check the weather' point)."""
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

def _resolve_underlying(underlying: str) -> tuple[str, Optional[str], str]:
    """Map a requested root to the symbol actually traded, the Yahoo symbol for
    its underlying value (None if Massive serves it), and a human-facing note
    explaining any substitution. Pulled out of run_backtest so the optimizer
    resolves the symbol the same way."""
    underlying = underlying.upper().strip()
    note_parts: list[str] = []
    # Account-size guard: full SPX options are ~10x too large for most accounts;
    # substitute the 1/10-size mini (XSP) so picks aren't capital-heavy.
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
    return underlying, yahoo_sym, " ".join(note_parts)


async def _fetch_underlying_bars(
    client: httpx.AsyncClient, underlying: str, yahoo_sym: Optional[str], months: int,
) -> list[dict]:
    """Daily underlying bars for the signal — Yahoo for index values, else Massive.
    Depends only on (symbol, months), so the optimizer fetches it ONCE and reuses
    it across every parameter combo."""
    to_d = date.today()
    frm_d = to_d - timedelta(days=int(months * 30.5))
    if yahoo_sym:
        return await fetch_yahoo_daily(client, yahoo_sym, frm_d.isoformat(), to_d.isoformat())
    return await fetch_daily(client, underlying, frm_d.isoformat(), to_d.isoformat())


def exit_rules_for(params: StrategyParams, vault_rules: dict) -> dict:
    """Resolve the exit policy a backtest run should use: the vault trading-rules,
    overridden by any explicit stop_pct/tp_pct on `params`. Default params leave
    the vault policy untouched, so the live exit is what gets validated."""
    rules = dict(vault_rules)
    if params.stop_pct is not None:
        rules["stop_loss_pct"] = params.stop_pct
    if params.tp_pct is not None:
        rules["take_profit_pct"] = params.tp_pct
    return rules


async def simulate_signals(
    client: httpx.AsyncClient,
    underlying: str,
    signals: list[dict],
    exit_rules: dict,
    params: StrategyParams = DEFAULT_PARAMS,
    *,
    contract_cache: Optional[dict] = None,
    optbar_cache: Optional[dict] = None,
) -> list[dict]:
    """Turn signals into completed trades: pick each contract, fetch its bars,
    simulate the exit. Optional caches let a sweep reuse contract discovery and
    option-bar fetches across parameter combos (the expensive API calls), so an
    optimizer pays for each unique contract once, not once per combo."""
    trades: list[dict] = []
    for sig in signals:
        entry = date.fromisoformat(sig["date"])
        ckey = (underlying, sig["side"], sig["date"], round(sig["spot"], 2),
                params.dte_min, params.dte_max, params.target_dte)
        if contract_cache is not None and ckey in contract_cache:
            contract = contract_cache[ckey]
        else:
            contract = await pick_contract(client, underlying, sig["side"], sig["spot"], entry, params)
            if contract_cache is not None:
                contract_cache[ckey] = contract
        if not contract:
            continue
        okey = contract["ticker"]
        if optbar_cache is not None and okey in optbar_cache:
            opt_bars = optbar_cache[okey]
        else:
            opt_bars = await fetch_daily(client, contract["ticker"], entry.isoformat(), contract["expiration"])
            if optbar_cache is not None:
                optbar_cache[okey] = opt_bars
        trade = simulate_trade(sig["side"], opt_bars, None,
                               symbol=contract["ticker"], rules=exit_rules)
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
    return trades


async def run_backtest(
    underlying: str = "SPY", months: int = 24, params: StrategyParams = DEFAULT_PARAMS,
) -> dict:
    """Full pipeline: fetch underlying -> signals -> contracts -> trades ->
    metrics. Returns a result dict (also carries an equity-curve payload for
    the UI). Raises RuntimeError on config/data problems. `params` defaults to
    the original fixed strategy; the optimizer passes swept variants."""
    if not API_KEY:
        raise RuntimeError("MASSIVE_API_KEY not configured")
    underlying, yahoo_sym, proxy_note = _resolve_underlying(underlying)

    async with httpx.AsyncClient() as client:
        bars = await _fetch_underlying_bars(client, underlying, yahoo_sym, months)
        if len(bars) < 60:
            raise RuntimeError(f"only {len(bars)} daily bars for {underlying}; need 60+")
        signals = generate_signals(bars, params)

        # Load the vault exit policy ONCE and reuse it for every trade so the
        # backtest exits exactly where the live trader would (same stop/TP %),
        # unless params explicitly override the levels (optimizer sweep).
        from hal.cortex import rules as _rules
        exit_rules = exit_rules_for(params, _rules.load_rules())
        stop_pct = exit_rules.get("stop_loss_pct", 50)
        tp_pct = exit_rules.get("take_profit_pct", 50)

        trades = await simulate_signals(client, underlying, signals, exit_rules, params)

    metrics = compute_metrics(trades)
    return {
        "underlying": underlying,
        "proxy_note": proxy_note,
        "months": months,
        "strategy": (f"long single (S/R break + RSI), ATM ~7DTE, "
                     f"+{tp_pct:g}%/-{stop_pct:g}% exit (vault rules)"),
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
    if m.get("payoff_ratio") is not None:
        parts.append(f"Payoff ratio {m['payoff_ratio']} to one.")
    if m.get("sharpe_per_trade") is not None:
        parts.append(f"Per-trade Sharpe {m['sharpe_per_trade']}.")
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
        f"Cite these numbers so {USER_NAME} sees the historical edge (or lack of one) before placing the trade."
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
