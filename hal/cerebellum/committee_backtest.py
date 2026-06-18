"""Backtest referee for the trade committee (hal.cortex.committee).

The point of this file is to answer ONE question before a trigger is ever wired:
does the multi-agent debate add directional edge over its own deterministic
inputs, or just latency? It does that by replaying point-in-time evidence and
scoring two arms on the same dates:

  · baseline  (run_llm=False) — decision = the deterministic consensus bias.
                Needs no Ollama. Run this FIRST: if the raw signals don't predict
                direction, no amount of LLM debate will rescue them.
  · committee (run_llm=True)  — the full bull/bear debate + judge on the SAME
                reconstructed evidence. If it doesn't beat baseline on hit-rate,
                forward-return, or selectivity, the 27B layer isn't earning its
                cost.

HONEST LIMITATIONS — read before trusting any number this prints:
  · DIRECTIONAL PROXY, not options P&L. We score whether the committee's side
    (call/put) matched the underlying's realized move over the next
    `horizon_days`. Real spread P&L depends on strike, IV path and theta we
    can't reconstruct from free daily bars.
  · VOL IS A REGIME PROXY. Per-day historical ATM IV isn't in the free data
    path, so the vol read here is REALIZED-vol percentile (HV), not the live
    committee's IV/HV richness. Same axis, different signal — don't equate them.
  · NO PRICE LEAKAGE, BUT MODEL-KNOWLEDGE LEAKAGE IS POSSIBLE. Evidence is
    rebuilt from bars UP TO the as-of date only (reusing backtest.py's
    no-lookahead RSI/HV), so prices don't leak. But an LLM judging "AAPL in
    2023" already knows how that quarter resolved — treat in-sample dates on
    famous moves with suspicion; prefer recent, boring windows.

Because the committee arm makes ~3 smart-model calls per date, mind the call
budget: `points × 3`. Use `step_days` and `limit` to keep it sane.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

import httpx

from hal.cerebellum import backtest as bt
from hal.cortex import committee

# Trading days of history to pull before the first as-of date so HV percentile
# and RSI have a full warm-up (vol_regime_percentile wants a trailing year).
_WARMUP_CALENDAR_DAYS = 420
_SMA_WINDOW = 20
_RSI_PERIOD = 14


# --- Point-in-time evidence reconstruction ----------------------------------
def reconstruct_evidence(closes_to_date: list[float]) -> tuple[list[dict], str, str]:
    """Rebuild the committee's analyst evidence from daily closes up to (and
    including) the as-of date. Returns (analysts, iv_level, bias).

    Mirrors the live analysts' SHAPE so committee.decide_from_evidence accepts
    it unchanged — but every value comes from bars, not live tool calls."""
    iv_level = {"high-vol": "high", "low-vol": "low", "mid-vol": "medium"}.get(
        bt.regime_label(bt.vol_regime_percentile(closes_to_date)), "unknown")

    # Setup/momentum: last close vs SMA20, confirmed by RSI side of 50.
    last = closes_to_date[-1]
    sma = (sum(closes_to_date[-_SMA_WINDOW:]) / _SMA_WINDOW
           if len(closes_to_date) >= _SMA_WINDOW else last)
    rsi_series = bt.rsi(closes_to_date, _RSI_PERIOD)
    rsi_now = next((v for v in reversed(rsi_series) if v is not None), 50.0)
    if last > sma and rsi_now >= 50:
        setup_lean, setup_note = "bullish", f"above SMA20, RSI {rsi_now:.0f}"
    elif last < sma and rsi_now <= 50:
        setup_lean, setup_note = "bearish", f"below SMA20, RSI {rsi_now:.0f}"
    else:
        setup_lean, setup_note = "neutral", f"mixed: px vs SMA20 / RSI {rsi_now:.0f}"
    setup_conf = min(0.8, 0.4 + abs(rsi_now - 50) / 50)

    analysts = [
        # Vol is about premium, not direction → neutral lean, but it sets iv_level.
        {"role": "vol", "lean": "neutral", "confidence": 0.4,
         "note": f"realized-vol regime: {iv_level}", "evidence": f"hv_regime={iv_level}"},
        {"role": "setup", "lean": setup_lean, "confidence": round(setup_conf, 2),
         "note": setup_note, "evidence": f"last={last:.2f} sma20={sma:.2f}"},
        {"role": "catalyst", "lean": "neutral", "confidence": 0.3,
         "note": "no point-in-time catalyst reconstruction", "evidence": ""},
    ]
    return analysts, iv_level, committee._consensus_bias(analysts)


def _bias_to_side(bias: str) -> str:
    return {"bullish": "call", "bearish": "put"}.get(bias, "neutral")


# --- Data --------------------------------------------------------------------
async def _load_closes(symbol: str, start: str, end: str) -> list[dict]:
    """Daily bars [{t,o,h,l,c,v}] from Yahoo (keyless) covering warm-up → end+buffer."""
    frm = (datetime.strptime(start, "%Y-%m-%d").date()
           - timedelta(days=_WARMUP_CALENDAR_DAYS)).isoformat()
    to = (datetime.strptime(end, "%Y-%m-%d").date() + timedelta(days=45)).isoformat()
    yahoo_sym = bt._INDEX_YAHOO.get(symbol.upper(), symbol.upper())
    async with httpx.AsyncClient(timeout=30) as client:
        return await bt.fetch_yahoo_daily(client, yahoo_sym, frm, to)


def _bar_date(bar: dict) -> date:
    t = bar["t"]
    return (date.fromtimestamp(t) if t < 10**11
            else datetime.utcfromtimestamp(t // 1000).date())


# --- Backtest ----------------------------------------------------------------
async def backtest(
    symbol: str,
    start: str,
    end: str,
    *,
    horizon_days: int = 10,
    step_days: int = 5,
    run_llm: bool = False,
    account_size: float = 0.0,
    limit: Optional[int] = None,
) -> dict:
    """Replay `symbol` from `start` to `end` (YYYY-MM-DD), one as-of point every
    `step_days` trading days, scoring direction `horizon_days` forward.

    horizon_days / step_days are counted in TRADING days (bar offsets), so
    weekends/holidays never skew the forward window.
    """
    symbol = symbol.upper().strip()
    bars = await _load_closes(symbol, start, end)
    if len(bars) < 60:
        return {"error": f"not enough history for {symbol} ({len(bars)} bars)"}
    closes = [b["c"] for b in bars]
    dates = [_bar_date(b) for b in bars]
    start_d = datetime.strptime(start, "%Y-%m-%d").date()
    end_d = datetime.strptime(end, "%Y-%m-%d").date()

    # As-of indices: inside [start,end] and with a full forward window available.
    idxs = [i for i in range(len(bars))
            if start_d <= dates[i] <= end_d and i + horizon_days < len(bars)]
    idxs = idxs[::step_days]
    if limit:
        idxs = idxs[:limit]

    points: list[dict] = []
    for i in idxs:
        analysts, iv_level, bias = reconstruct_evidence(closes[: i + 1])
        fwd = (closes[i + horizon_days] - closes[i]) / closes[i]
        point = {
            "date": dates[i].isoformat(),
            "bias": bias,
            "iv_level": iv_level,
            "fwd_return": round(fwd, 4),
            "baseline_side": _bias_to_side(bias),
            "committee_side": None,
            "committee_decision": None,
        }
        if run_llm:
            structures = committee.candidate_structures(symbol, bias, iv_level)
            v = await committee.decide_from_evidence(
                symbol, analysts=analysts, structures=structures, iv_level=iv_level,
                bias=bias, reflection="", account_size=account_size)
            point["committee_decision"] = v["decision"]
            point["committee_side"] = v["side"] if v["decision"] == "TRADE" else "neutral"
        points.append(point)

    result = {
        "symbol": symbol,
        "window": f"{start} → {end}",
        "horizon_days": horizon_days,
        "step_days": step_days,
        "n_points": len(points),
        "baseline": _score(points, "baseline_side"),
        "committee": _score(points, "committee_side") if run_llm else None,
        "points": points,
    }
    result["report"] = _render_report(result)
    return result


def _score(points: list[dict], side_key: str) -> dict:
    """Directional hit-rate + forward-return for one arm. Neutral/None sides are
    excluded from hit-rate (counted as a PASS instead)."""
    directional = [p for p in points if p.get(side_key) in ("call", "put")]
    hits = sum(1 for p in directional
               if (p[side_key] == "call") == (p["fwd_return"] > 0))
    aligned = [p["fwd_return"] if p[side_key] == "call" else -p["fwd_return"]
               for p in directional]
    n = len(points)
    return {
        "n": n,
        "trades": len(directional),
        "pass_rate": round(1 - len(directional) / n, 3) if n else None,
        "hit_rate": round(hits / len(directional), 3) if directional else None,
        "avg_aligned_return": round(sum(aligned) / len(aligned), 4) if aligned else None,
    }


def _render_report(r: dict) -> str:
    def arm(name: str, s: Optional[dict]) -> str:
        if not s:
            return f"- {name}: (not run)"
        hr = f"{s['hit_rate']:.0%}" if s["hit_rate"] is not None else "—"
        ar = f"{s['avg_aligned_return']:+.2%}" if s["avg_aligned_return"] is not None else "—"
        return (f"- {name}: {s['trades']}/{s['n']} trades · hit-rate {hr} · "
                f"avg aligned move {ar} · pass-rate {s['pass_rate']:.0%}")

    lines = [
        f"**Committee backtest — {r['symbol']}  {r['window']}**",
        f"_{r['n_points']} as-of points · {r['horizon_days']}d forward · "
        f"step {r['step_days']}d · DIRECTIONAL PROXY (not P&L)_",
        "",
        arm("Baseline (bias)", r["baseline"]),
        arm("Committee (LLM)", r["committee"]),
    ]
    if r["committee"] and r["baseline"]["hit_rate"] is not None \
            and r["committee"]["hit_rate"] is not None:
        delta = r["committee"]["hit_rate"] - r["baseline"]["hit_rate"]
        verdict = ("committee adds directional edge" if delta > 0.02
                   else "committee no better than its inputs — not worth the latency"
                   if delta < -0.02 else "committee ≈ baseline (it mostly filters, not redirects)")
        lines += ["", f"**Read:** {verdict} (Δhit-rate {delta:+.0%})."]
    return "\n".join(lines)
