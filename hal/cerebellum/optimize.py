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
    """Rank score from a metrics dict. Profit factor is the lens; configs with
    too few trades are shrunk toward zero so noise can't win. Returns -1 for an
    empty/failed result so it sinks."""
    n = m.get("trades", 0)
    if not n:
        return -1.0
    pf = m.get("profit_factor")
    if pf is None:  # no losing trades — strong, but cap so it can't dominate on a fluke
        pf = 3.0 if (m.get("total_pnl", 0) or 0) > 0 else 0.0
    return pf * min(1.0, n / MIN_TRADES)


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
) -> dict:
    """Sweep `grid` over the backtester and rank configurations by in-sample
    objective, reporting out-of-sample performance for each so overfit configs
    are visible. Returns a structured result; raises RuntimeError on config/data
    problems (same as run_backtest)."""
    if not bt.API_KEY:
        raise RuntimeError("MASSIVE_API_KEY not configured")
    grid = grid or DEFAULT_GRID
    combos = _expand(grid)
    resolved, yahoo_sym, proxy_note = bt._resolve_underlying(underlying)

    from hal.cortex import rules as _rules
    vault_rules = _rules.load_rules()

    contract_cache: dict = {}
    optbar_cache: dict = {}

    async with httpx.AsyncClient() as client:
        bars = await bt._fetch_underlying_bars(client, resolved, yahoo_sym, months)
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
        "| Config | IS trades | IS PF | OOS trades | OOS PF | Total P&L | Held up? |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in top:
        is_m, oos_m, all_m = r["is"], r["oos"], r["all"]
        rows.append(
            f"| {r['label']} | {is_m.get('trades', 0)} | {is_m.get('profit_factor')} | "
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
    "factors. In 4-6 sentences: judge whether any edge is real or just curve-fit "
    "(big in-sample vs out-of-sample gaps = overfit), say which direction to widen "
    "or narrow the search next, and name the single biggest risk in trusting these "
    "numbers. Be blunt; recommending 'do not trade this' is a valid answer."
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
        f"(n={r['is'].get('trades', 0)}), OOS pf={r['oos'].get('profit_factor')} "
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
