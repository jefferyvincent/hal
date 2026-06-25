"""Parameter optimization for HAL's options backtester.

Borrowed in spirit from QuantDinger's `submit_structured_tune` / `submit_ai_optimize`:
sweep the strategy's knobs, score each configuration, and surface the robust ones
— but built on HAL's existing single-code-path backtest so a tuned config exits
exactly where the live trader would.

Two guards against the classic optimizer failure (curve-fitting a number that
won't repeat):

  1. Walk-forward split — every configuration is scored on an IN-SAMPLE slice
     (the older ~70% of the window) and SEPARATELY measured on the OUT-OF-SAMPLE
     tail it never influenced. A config that only wins in-sample is overfit; the
     report flags whether the edge survived out-of-sample.
  2. Sample-size shrink — profit factor on 3 trades is noise. The objective
     shrinks configs with fewer than MIN_TRADES so a lucky handful can't top the
     board.
  3. Significance dampener — profit factor measures the SIZE of the edge, never
     whether it's distinguishable from zero. Borrowed from qlib's IC-IR lens
     (rank a signal by mean/std of its edge, not just its mean), the objective
     scales each config by the t-stat of its trade returns, so a high-PF config
     whose edge is statistical noise sinks beneath a steadier one. This matters
     most as a referee for any automated/LLM search on top of the sweep: the
     loop is only as trustworthy as the number it maximizes.

API efficiency: contract discovery and option-bar fetches (the expensive Massive
calls) are cached and shared across the whole sweep, so each unique contract is
fetched once regardless of how many parameter combos reference it. The underlying
bars are fetched once. A 100-combo sweep costs roughly the API of a single
backtest plus the distinct contracts the varied signals discover.

ai_optimize() is an OPTIONAL, explicitly-gated LLM step (mirrors QuantDinger's
confirm_llm_usage): it reads the tearsheet and proposes where to search next. It
never places a trade and never auto-reruns.
"""
from __future__ import annotations

import itertools
from dataclasses import replace
from datetime import date
from typing import Optional

import httpx

from hal.cerebellum import backtest as bt
from hal.cerebellum.backtest import StrategyParams

# Default search space. The signal dimensions (rsi_period × pivot_k × rsi_long)
# decide which contracts get fetched; the exit dimensions (stop_pct × tp_pct) are
# essentially free to vary because they re-score the SAME cached option bars.
DEFAULT_GRID: dict[str, list] = {
    "rsi_period": [9, 14, 21],
    "pivot_k": [3, 5],
    "rsi_long": [50, 55],          # rsi_short is mirrored to 100 - rsi_long
    "stop_pct": [40, 50, 60],
    "tp_pct": [50, 75, 100],
}

MIN_TRADES = 8          # below this a result is shrunk as statistically thin
IS_FRACTION = 0.70      # older share of the window used as in-sample
TOP_N = 8               # configs returned in the report
T_TARGET = 2.0          # |t-stat| treated as "significant"; below it the
                        # significance dampener fades a config's score toward 0


def _expand(grid: dict[str, list]) -> list[StrategyParams]:
    """Cartesian product of the grid → StrategyParams list. rsi_short mirrors
    rsi_long around 50 so the call/put thresholds stay symmetric."""
    keys = [k for k in ("rsi_period", "pivot_k", "rsi_long", "stop_pct", "tp_pct") if k in grid]
    combos: list[StrategyParams] = []
    for values in itertools.product(*(grid[k] for k in keys)):
        kw = dict(zip(keys, values))
        if "rsi_long" in kw:
            kw["rsi_short"] = 100.0 - float(kw["rsi_long"])
        combos.append(replace(bt.DEFAULT_PARAMS, **kw))
    return combos


def _objective(m: dict) -> float:
    """Rank score from a metrics dict. Profit factor is the lens, scaled by two
    dampeners that can only LOWER a score, never inflate it: a sample-size shrink
    (too few trades) and a significance factor (the edge's t-stat — see guard #3).
    Returns -1 for an empty/failed result so it sinks."""
    n = m.get("trades", 0)
    if not n:
        return -1.0
    pf = m.get("profit_factor")
    if pf is None:  # no losing trades — strong, but cap so it can't dominate on a fluke
        pf = 3.0 if (m.get("total_pnl", 0) or 0) > 0 else 0.0
    shrink = min(1.0, n / MIN_TRADES)
    # Significance: fade configs whose per-trade edge can't be told from zero.
    # t_stat is None when variance is zero (identical trades) — treat that as
    # already-significant (factor 1.0) rather than penalising it.
    t = m.get("t_stat")
    sig = 1.0 if t is None else min(1.0, abs(t) / T_TARGET)
    return pf * shrink * sig


def _split(trades: list[dict], cutoff_iso: str) -> tuple[list[dict], list[dict]]:
    """Partition trades into (in-sample, out-of-sample) on entry date."""
    in_s = [t for t in trades if t.get("date", "") <= cutoff_iso]
    out_s = [t for t in trades if t.get("date", "") > cutoff_iso]
    return in_s, out_s


def _label(p: StrategyParams) -> str:
    stop = "vault" if p.stop_pct is None else f"-{p.stop_pct:g}%"
    tp = "vault" if p.tp_pct is None else f"+{p.tp_pct:g}%"
    return (f"RSI{p.rsi_period}({p.rsi_long:g}/{p.rsi_short:g}) "
            f"piv{p.pivot_k} exit {tp}/{stop}")


def _robust(is_m: dict, oos_m: dict) -> bool:
    """A config 'held up' if it was profitable in-sample AND the edge survived
    out-of-sample (both profit factors >= 1, with at least a couple OOS trades)."""
    is_pf = is_m.get("profit_factor")
    oos_pf = oos_m.get("profit_factor")
    return (bool(is_m.get("trades"))
            and (is_pf is None or is_pf >= 1.0)
            and oos_m.get("trades", 0) >= 2
            and (oos_pf is None or oos_pf >= 1.0))


async def optimize(
    underlying: str = "SPY",
    months: int = 24,
    grid: Optional[dict[str, list]] = None,
    is_fraction: float = IS_FRACTION,
    *,
    holdout_iso: Optional[str] = None,
    contract_cache: Optional[dict] = None,
    optbar_cache: Optional[dict] = None,
) -> dict:
    """Sweep `grid` over the backtester and rank configurations by in-sample
    objective, reporting out-of-sample performance for each so overfit configs
    are visible. Returns a structured result; raises RuntimeError on config/data
    problems (same as run_backtest).

    holdout_iso (YYYY-MM-DD) reserves a LOCK-BOX: bars on/after that date are
    dropped from the sweep entirely, so a caller running this in a loop (e.g.
    research_agent) can keep a recent slice the search never influenced and test
    the chosen config on it once. contract_cache/optbar_cache may be passed in to
    share the expensive Massive fetches across repeated calls (the same caches
    optimize uses internally for a single sweep)."""
    if not bt.API_KEY:
        raise RuntimeError("MASSIVE_API_KEY not configured")
    grid = grid or DEFAULT_GRID
    combos = _expand(grid)
    resolved, yahoo_sym, proxy_note = bt._resolve_underlying(underlying)

    from hal.cortex import rules as _rules
    vault_rules = _rules.load_rules()

    contract_cache = {} if contract_cache is None else contract_cache
    optbar_cache = {} if optbar_cache is None else optbar_cache

    async with httpx.AsyncClient() as client:
        bars = await bt._fetch_underlying_bars(client, resolved, yahoo_sym, months)
        # Lock-box: hold back recent bars so the search never sees them.
        if holdout_iso:
            bars = [b for b in bars
                    if date.fromtimestamp(b["t"]).isoformat() < holdout_iso]
        if len(bars) < 60:
            raise RuntimeError(f"only {len(bars)} daily bars for {resolved}; need 60+")
        cutoff_iso = date.fromtimestamp(bars[int(len(bars) * is_fraction)]["t"]).isoformat()

        rows: list[dict] = []
        for p in combos:
            signals = bt.generate_signals(bars, p)
            exit_rules = bt.exit_rules_for(p, vault_rules)
            trades = await bt.simulate_signals(
                client, resolved, signals, exit_rules, p,
                contract_cache=contract_cache, optbar_cache=optbar_cache)
            in_s, out_s = _split(trades, cutoff_iso)
            is_m = bt.compute_metrics(in_s)
            oos_m = bt.compute_metrics(out_s)
            rows.append({
                "params": p,
                "label": _label(p),
                "score": round(_objective(is_m), 3),
                "robust": _robust(is_m, oos_m),
                "all": bt.compute_metrics(trades),
                "is": is_m,
                "oos": oos_m,
            })

    rows.sort(key=lambda r: r["score"], reverse=True)
    top = rows[:TOP_N]
    robust = [r for r in rows if r["robust"]]
    best = robust[0] if robust else (top[0] if top else None)

    return {
        "underlying": resolved,
        "proxy_note": proxy_note,
        "months": months,
        "combos_tested": len(combos),
        "in_sample_through": cutoff_iso,
        "holdout_from": holdout_iso,
        "min_trades": MIN_TRADES,
        "best": best,
        "best_is_robust": bool(robust),
        "top": top,
        "robust_count": len(robust),
    }


# --- presentation -----------------------------------------------------------

def table(result: dict) -> str:
    """Markdown leaderboard, ranked by in-sample objective, with the out-of-sample
    profit factor alongside so overfit configs are obvious at a glance."""
    top = result.get("top") or []
    rows = [
        f"**Backtest optimization — {result.get('underlying')}**, {result.get('months')}-month "
        f"window, {result.get('combos_tested')} configs. In-sample through "
        f"{result.get('in_sample_through')}; the rest is out-of-sample (OOS).",
        "",
        "| Config | IS trades | IS PF | IS t | OOS trades | OOS PF | Total P&L | Held up? |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in top:
        is_m, oos_m, all_m = r["is"], r["oos"], r["all"]
        is_t = is_m.get("t_stat")
        rows.append(
            f"| {r['label']} | {is_m.get('trades', 0)} | {is_m.get('profit_factor')} | "
            f"{is_t if is_t is not None else '—'} | "
            f"{oos_m.get('trades', 0)} | {oos_m.get('profit_factor')} | "
            f"${all_m.get('total_pnl', 0):,.0f} | {'✅' if r['robust'] else '—'} |"
        )
    if not result.get("best_is_robust"):
        rows += ["", "_No configuration held up out-of-sample — treat the top rows as "
                 "in-sample-only and do not trust them live._"]
    return "\n".join(rows)


def speak_summary(result: dict) -> str:
    """Speech-friendly read of the optimization."""
    best = result.get("best")
    if not best:
        return (f"I optimized {result.get('underlying')} but no configuration produced "
                "qualifying trades.")
    is_m, oos_m = best["is"], best["oos"]
    parts = [
        f"Optimization done on {result['underlying']}: I tested "
        f"{result['combos_tested']} configurations over {result['months']} months."
    ]
    if result.get("best_is_robust"):
        parts.append(
            f"The best one that also held up out of sample was {best['label']}, "
            f"in-sample profit factor {is_m.get('profit_factor')} on {is_m.get('trades')} trades, "
            f"and out of sample {oos_m.get('profit_factor')} on {oos_m.get('trades')}."
        )
        parts.append("I'd forward-test that on paper before trusting it.")
    else:
        parts.append(
            f"The top in-sample config was {best['label']}, profit factor "
            f"{is_m.get('profit_factor')}, but nothing held up out of sample, so I would "
            "not trade any of these — they look curve-fit. The signal needs rethinking, "
            "not just retuning."
        )
    if result.get("proxy_note"):
        parts.append(result["proxy_note"])
    return " ".join(parts)


# --- optional LLM hints (gated, mirrors QuantDinger submit_ai_optimize) ------

_AI_SYS = (
    "You are a quant reviewing an options-strategy parameter sweep. You are given "
    "a leaderboard of configurations with in-sample and out-of-sample profit "
    "factors and an in-sample t-stat (t = significance of the per-trade edge vs "
    "zero; |t| under ~2 means the edge is statistical noise no matter how high the "
    "profit factor looks). In 4-6 sentences: judge whether any edge is real or just "
    "curve-fit (big in-sample vs out-of-sample gaps = overfit; low t = noise), say "
    "which direction to widen or narrow the search next, and name the single biggest "
    "risk in trusting these numbers. Be blunt; recommending 'do not trade this' is a "
    "valid answer."
)


async def ai_optimize(result: dict, confirm_llm_usage: bool = False) -> str:
    """LLM read of the optimization tearsheet — where to search next and whether
    the edge is trustworthy. Gated behind `confirm_llm_usage` (the call burns the
    smart model) exactly like QuantDinger's submit_ai_optimize, and like it this
    only produces hints — it never reruns or trades."""
    if not confirm_llm_usage:
        return ("AI optimization hints are gated to avoid surprise model usage. "
                "Re-run with confirm_llm_usage=True to spend the smart model on a "
                "review of these results.")
    top = result.get("top") or []
    if not top:
        return "No configurations to review."
    board = "\n".join(
        f"- {r['label']}: IS pf={r['is'].get('profit_factor')} "
        f"(n={r['is'].get('trades', 0)}, t={r['is'].get('t_stat')}), "
        f"OOS pf={r['oos'].get('profit_factor')} "
        f"(n={r['oos'].get('trades', 0)}), robust={r['robust']}"
        for r in top
    )
    brief = (
        f"Underlying: {result.get('underlying')}, {result.get('months')}-month window, "
        f"{result.get('combos_tested')} configs, in-sample through "
        f"{result.get('in_sample_through')}.\nLeaderboard (ranked by in-sample score):\n{board}"
    )
    # Lazy import: reuse the committee's tolerant one-shot LLM client. Keeps the
    # cerebellum→cortex dependency lazy and out of the import graph by default.
    from hal.cortex.committee import _llm
    from hal.brainstem.config import OLLAMA_MODEL
    out = await _llm(brief, system=_AI_SYS, model=OLLAMA_MODEL, temperature=0.3, num_ctx=4096)
    return out.strip() or "The model returned no review."
