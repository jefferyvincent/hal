"""Closed-loop research agent for HAL's options strategy — a right-sized
adaptation of qlib's RD-Agent (LLM-driven, evolving data-driven R&D).

RD-Agent runs Hypothesis -> Implement -> Validate -> Feedback in a loop, evolving
what it knows each cycle. This module runs that loop on top of HAL's existing
optimizer, with ONE deliberate departure that the whole design hinges on:

  · Hypothesis  — the smart model reads the running leaderboard + round history
                  and proposes the NEXT search grid plus a one-line thesis. This
                  is optimize.ai_optimize() evolved from a one-shot hint into the
                  loop's driver: the LLM now decides where to search, instead of
                  a human re-running the sweep.
  · Implement   — DETERMINISTIC, and NOT code generation. The proposal is a set
                  of PARAMETER values inside an audited allow-list (_GRID_BOUNDS);
                  it is instantiated through the same optimize._expand the manual
                  sweep uses. The LLM never authors signal/exit code — generate_
                  signals stays fixed — because HAL's output can reach a real
                  broker. This is the key safety line vs qlib's RD-Agent, which
                  evolves executable factor code.
  · Validate    — the existing optimize() is the REFEREE: walk-forward IS/OOS,
                  the significance-dampened objective, and the OOS robustness
                  gate. The LLM proposes experiments; it can never score itself.
  · Feedback    — the round is recorded, best-so-far updated by OUT-OF-SAMPLE
                  performance (not in-sample, so the loop can't win by curve-
                  fitting the tuning slice), and convergence checked.

THE LOCK-BOX (why this loop needs a third data slice):
  A one-shot ai_optimize() can safely show the model the OOS numbers. A LOOP
  cannot: if the LLM steers by OOS every round, OOS silently becomes in-sample
  and the overfit guard is gone. So a recent slice (`holdout_months`) is reserved
  before the loop starts (optimize(holdout_iso=...) drops those bars) and the
  single chosen config is scored on it EXACTLY ONCE at the end. That lock-box
  number — not the leaderboard — is the only go/no-go. If it disagrees with the
  in-loop OOS, the loop overfit the search itself and the verdict is "do not
  trade".

Scope guarantees (mirrors optimize.ai_optimize / committee ethos):
  · Gated behind confirm_llm_usage and bounded by max_rounds (cost = at most
    max_rounds smart-model calls; the Alpaca sweep cost is shared across rounds
    via persistent caches).
  · Produces a research artifact + ONE candidate flagged for paper-forward. It
    never wires a trigger and never places a trade.
  · Degrades gracefully: a malformed/invalid LLM proposal falls back to a
    deterministic perturbation of the current best, so a flaky model can't break
    the loop — it just makes that round dumber.

Library entrypoint only by design — research()/report() are meant to be called
and reviewed from a script before any route or trigger is built on top.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import httpx

from hal.cerebellum import backtest as bt
from hal.cerebellum import optimize as opt
from hal.sensory import alpaca_data

# --- Search-space allow-list -------------------------------------------------
# The ONLY knobs the agent may move, with hard bounds. Anything outside this is
# rejected (not clamped silently for keys; out-of-range values are dropped). This
# is the audited boundary that keeps an LLM proposal from steering the strategy
# somewhere unvalidated — it can only pick points inside HAL's known grid.
_GRID_BOUNDS: dict[str, tuple[float, float]] = {
    "rsi_period": (2, 50),
    "pivot_k": (2, 15),
    "rsi_long": (50, 80),     # rsi_short is mirrored by optimize._expand
    "stop_pct": (5, 90),
    "tp_pct": (10, 300),
}
_INT_KEYS = {"rsi_period", "pivot_k"}     # these must be whole numbers
_MAX_COMBOS = 48          # per-round cap so one grid can't explode the API budget
_HOLDOUT_MONTHS = 3       # recent slice reserved as the lock-box
_IMPROVE_EPS = 0.05       # min OOS-objective gain to count a round as progress


# --- Round scoring -----------------------------------------------------------
def _val_objective(row: Optional[dict]) -> float:
    """Rank a config by its OUT-OF-SAMPLE objective. The loop optimizes this, not
    the in-sample score optimize() sorts by, so progress means 'better on data the
    tuning never touched' rather than 'better fit'."""
    if not row:
        return -1.0
    return opt._objective(row.get("oos") or {})


def _round_best(result: dict) -> Optional[dict]:
    """Best ROBUST config of a round, ranked by out-of-sample objective. Returns
    None when no config in the round held up out-of-sample — a round that found
    nothing trustworthy contributes no candidate."""
    robust = [r for r in (result.get("top") or []) if r.get("robust")]
    if not robust:
        return None
    return max(robust, key=_val_objective)


def _is_improvement(cand: Optional[dict], best: Optional[dict]) -> bool:
    if not cand:
        return False
    if not best:
        return True
    return _val_objective(cand) > _val_objective(best) + _IMPROVE_EPS


# --- Grid proposal (LLM) -----------------------------------------------------
_PROPOSE_SYS = (
    "You are a quant directing an options-strategy parameter search. Each round "
    "you see the leaderboard so far (configs with in-sample and out-of-sample "
    "profit factor, an in-sample t-stat where |t|<~2 means the edge is noise, and "
    "whether each held up out-of-sample). Propose the NEXT grid to test — move "
    "toward regions that held up OUT of sample, not just high in-sample numbers; "
    "widen where the surface looks flat, narrow where it looks peaked. Reply with "
    "ONLY a JSON object, no prose:\n"
    '{"hypothesis": "<one sentence>", "grid": {"rsi_period":[...], "pivot_k":[...], '
    '"rsi_long":[...], "stop_pct":[...], "tp_pct":[...]}, "stop": false}\n'
    "Include only the keys you want to change; omit a key to leave it at the "
    "current values. Keep each list short (<=4 values). Set \"stop\": true if the "
    "evidence says no real edge exists here and more searching is just curve-"
    "fitting — recommending a stop is a valid, useful answer."
)


def _validate_grid(raw: object) -> Optional[dict[str, list]]:
    """Coerce an LLM-proposed grid to a safe one: keep only allow-listed keys,
    drop out-of-range/non-numeric values, enforce ints where required, and cap the
    combinatorial size. Returns None if nothing usable survives, so the caller
    falls back to a deterministic perturbation."""
    if not isinstance(raw, dict):
        return None
    clean: dict[str, list] = {}
    for key, lo_hi in _GRID_BOUNDS.items():
        vals = raw.get(key)
        if not isinstance(vals, (list, tuple)):
            continue
        lo, hi = lo_hi
        kept = []
        for v in vals:
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                continue
            if not (lo <= v <= hi):
                continue
            kept.append(int(v) if key in _INT_KEYS else float(v))
        # de-dup, preserve order, cap per-axis
        seen, axis = set(), []
        for v in kept:
            if v not in seen:
                seen.add(v)
                axis.append(v)
        if axis:
            clean[key] = axis[:4]
    if not clean:
        return None
    # Cap total combinations so one proposal can't blow the API budget.
    size = 1
    for axis in clean.values():
        size *= len(axis)
    if size > _MAX_COMBOS:
        for key in clean:                      # trim widest axes first
            while size > _MAX_COMBOS and len(clean[key]) > 1:
                size //= len(clean[key])
                clean[key] = clean[key][:-1]
                size *= len(clean[key])
    return clean


def _perturb(row: Optional[dict]) -> dict[str, list]:
    """Deterministic fallback grid centred on the current best params, used when
    the LLM proposal is unusable. Each knob steps around its current value, clamped
    to the allow-list. With no best yet, just re-seed the default grid."""
    if not row:
        return dict(opt.DEFAULT_GRID)
    p = row["params"]
    cur = {"rsi_period": p.rsi_period, "pivot_k": p.pivot_k, "rsi_long": p.rsi_long,
           "stop_pct": p.stop_pct if p.stop_pct is not None else 50,
           "tp_pct": p.tp_pct if p.tp_pct is not None else 75}
    steps = {"rsi_period": 3, "pivot_k": 2, "rsi_long": 5, "stop_pct": 10, "tp_pct": 25}
    grid: dict[str, list] = {}
    for key, (lo, hi) in _GRID_BOUNDS.items():
        c, s = cur[key], steps[key]
        axis = sorted({max(lo, c - s), c, min(hi, c + s)})
        grid[key] = [int(v) if key in _INT_KEYS else float(v) for v in axis]
    return grid


def _board_for_prompt(result: dict) -> str:
    lines = []
    for r in (result.get("top") or [])[:6]:
        is_m, oos_m = r["is"], r["oos"]
        lines.append(
            f"- {r['label']}: IS pf={is_m.get('profit_factor')} "
            f"(n={is_m.get('trades', 0)}, t={is_m.get('t_stat')}), "
            f"OOS pf={oos_m.get('profit_factor')} (n={oos_m.get('trades', 0)}), "
            f"held_up={r['robust']}"
        )
    return "\n".join(lines) or "(no qualifying configs this round)"


async def _propose_grid(underlying: str, history: list[dict]) -> dict:
    """Ask the smart model for the next grid + thesis. Returns
    {hypothesis, grid|None, stop}. Never raises — a failed/garbled call yields an
    empty proposal so the loop falls back to a perturbation."""
    from hal.cortex.committee import _llm, _parse_json
    from hal.brainstem.config import OLLAMA_MODEL

    last = history[-1]
    prior = "\n\n".join(
        f"Round {h['round']} — hypothesis: {h.get('hypothesis') or 'seed grid'}\n"
        f"{_board_for_prompt(h['result'])}"
        for h in history[-3:]
    )
    brief = (
        f"Underlying: {underlying}. Search so far (most recent last):\n{prior}\n\n"
        f"In-sample is through {last['result'].get('in_sample_through')}; a recent "
        f"slice is held back as an untouched lock-box. Propose the next grid."
    )
    out = await _llm(brief, system=_PROPOSE_SYS, model=OLLAMA_MODEL,
                     temperature=0.3, num_ctx=4096)
    parsed = _parse_json(out)
    return {
        "hypothesis": (parsed.get("hypothesis") or "").strip(),
        "grid": _validate_grid(parsed.get("grid")),
        "stop": bool(parsed.get("stop")),
    }


# --- Lock-box ----------------------------------------------------------------
async def _lockbox_eval(underlying: str, months: int, row: dict, holdout_iso: str) -> dict:
    """Score the chosen config ONCE on the reserved recent slice the search never
    saw. Runs the SAME signal/exit path as the loop (so it's a true out-of-sample
    read) but keeps only trades entered on/after holdout_iso."""
    p = row["params"]
    resolved, yahoo_sym, _ = bt._resolve_underlying(underlying)
    from hal.cortex import rules as _rules
    exit_rules = bt.exit_rules_for(p, _rules.load_rules())
    async with httpx.AsyncClient() as client:
        bars = await bt._fetch_underlying_bars(client, resolved, yahoo_sym, months)
        signals = [s for s in bt.generate_signals(bars, p) if s["date"] >= holdout_iso]
        trades = await bt.simulate_signals(client, resolved, signals, exit_rules, p)
    return bt.compute_metrics(trades)


def _lockbox_verdict(row: dict, lb: dict) -> str:
    """Compare in-loop OOS to the lock-box. Agreement => trustworthy enough to
    paper-forward; disagreement => the loop overfit the search."""
    if lb.get("trades", 0) < 3:
        return ("inconclusive — too few lock-box trades to judge; extend the window "
                "or holdout before trusting this")
    lb_pf = lb.get("profit_factor")
    oos_pf = (row.get("oos") or {}).get("profit_factor")
    survived = (lb_pf is None or lb_pf >= 1.0)
    if survived and (lb.get("t_stat") is None or abs(lb.get("t_stat") or 0) >= 1.5):
        return "held up on the untouched lock-box — reasonable to paper-forward (not to trade live yet)"
    if not survived:
        return ("FAILED the lock-box — profitable in-loop but not on untouched data; "
                "this is curve-fit to the search. Do not trade.")
    return ("marginal on the lock-box — edge present but weak/insignificant; "
            "paper-forward only with small size, expect it may not hold")


# --- Loop --------------------------------------------------------------------
async def research(
    underlying: str = "SPY",
    months: int = 24,
    holdout_months: int = _HOLDOUT_MONTHS,
    max_rounds: int = 6,
    no_improve_stop: int = 2,
    confirm_llm_usage: bool = False,
) -> dict:
    """Run the closed research loop and return a structured result with a
    round-by-round history and the lock-box verdict. Gated behind
    confirm_llm_usage because each round spends the smart model; bounded by
    max_rounds and an early stop after `no_improve_stop` rounds with no
    out-of-sample improvement."""
    if not confirm_llm_usage:
        return {"gated": True, "report": (
            "The research agent runs the smart model once per round. Re-run with "
            "confirm_llm_usage=True to spend it on an autonomous parameter search.")}
    if not alpaca_data.is_configured():
        raise RuntimeError("ALPACA_API_KEY / ALPACA_SECRET_KEY not configured")

    holdout_iso = (date.today() - timedelta(days=int(holdout_months * 30.5))).isoformat()
    # Shared across rounds so each unique contract is fetched from Alpaca once for
    # the WHOLE search, not once per round (same efficiency optimize gives a sweep).
    contract_cache: dict = {}
    optbar_cache: dict = {}

    history: list[dict] = []
    best: Optional[dict] = None
    grid: dict[str, list] = dict(opt.DEFAULT_GRID)
    hypothesis = "seed grid"
    no_improve = 0
    stop_reason = "reached max rounds"

    for rnd in range(1, max_rounds + 1):
        result = await opt.optimize(
            underlying, months, grid=grid, holdout_iso=holdout_iso,
            contract_cache=contract_cache, optbar_cache=optbar_cache)
        cand = _round_best(result)
        if _is_improvement(cand, best):
            best, no_improve = cand, 0
        else:
            no_improve += 1
        history.append({
            "round": rnd,
            "hypothesis": hypothesis,
            "grid": grid,
            "result": result,
            "round_best": cand["label"] if cand else None,
            "round_best_oos_obj": round(_val_objective(cand), 3) if cand else None,
        })

        if no_improve >= no_improve_stop:
            stop_reason = f"converged ({no_improve} rounds with no out-of-sample gain)"
            break
        if rnd == max_rounds:
            break

        proposal = await _propose_grid(underlying, history)
        if proposal["stop"]:
            stop_reason = "agent judged there is no real edge here and stopped"
            break
        hypothesis = proposal["hypothesis"] or "perturb around current best"
        grid = proposal["grid"] or _perturb(best)

    lockbox = await _lockbox_eval(underlying, months, best, holdout_iso) if best else None
    verdict = _lockbox_verdict(best, lockbox) if (best and lockbox) else (
        "no configuration held up out-of-sample in any round — the signal needs "
        "rethinking, not more tuning")

    out = {
        "underlying": result.get("underlying", underlying.upper()),
        "proxy_note": result.get("proxy_note", ""),
        "months": months,
        "holdout_from": holdout_iso,
        "rounds_run": len(history),
        "stop_reason": stop_reason,
        "best": best,
        "lockbox": lockbox,
        "verdict": verdict,
        "history": history,
    }
    out["report"] = report(out)
    return out


# --- presentation ------------------------------------------------------------
def report(result: dict) -> str:
    """Markdown: the round-by-round search trail, the chosen config, and the
    lock-box verdict that's the only number worth acting on."""
    if result.get("gated"):
        return result["report"]
    lines = [
        f"**Research agent — {result['underlying']}**, {result['months']}-month window, "
        f"{result['rounds_run']} round(s). Lock-box reserved from {result['holdout_from']} "
        f"(never seen during the search).",
        f"_Stopped: {result['stop_reason']}._",
        "",
        "| Round | Hypothesis | Best config (this round) | OOS objective |",
        "|---|---|---|---|",
    ]
    for h in result["history"]:
        lines.append(
            f"| {h['round']} | {h['hypothesis']} | {h['round_best'] or '— none held up —'} | "
            f"{h['round_best_oos_obj'] if h['round_best_oos_obj'] is not None else '—'} |"
        )
    best = result.get("best")
    lb = result.get("lockbox")
    lines += ["", "**Chosen config & lock-box test**"]
    if best:
        is_m, oos_m = best["is"], best["oos"]
        lines.append(
            f"- {best['label']} — in-loop IS pf {is_m.get('profit_factor')} "
            f"(t {is_m.get('t_stat')}), OOS pf {oos_m.get('profit_factor')}"
        )
        if lb:
            lines.append(
                f"- Lock-box (untouched): {lb.get('trades', 0)} trades, pf "
                f"{lb.get('profit_factor')}, t {lb.get('t_stat')}, total "
                f"${lb.get('total_pnl', 0):,.0f}"
            )
    else:
        lines.append("- No config held up out-of-sample in any round.")
    lines += ["", f"**Verdict:** {result['verdict']}",
              "", "_Research artifact only — no trade was placed and no trigger was wired. "
              "Paper-forward any survivor before risking capital._"]
    if result.get("proxy_note"):
        lines += ["", f"_{result['proxy_note']}_"]
    return "\n".join(lines)


def speak_summary(result: dict) -> str:
    """Voice-friendly read of the research run."""
    if result.get("gated"):
        return ("The research agent needs explicit confirmation to spend the smart "
                "model. Re-run it with confirmation enabled.")
    best = result.get("best")
    if not best:
        return (f"I ran {result['rounds_run']} rounds on {result['underlying']} but "
                "nothing held up out of sample. The signal needs rethinking, not more "
                "tuning.")
    lb = result.get("lockbox") or {}
    return (
        f"On {result['underlying']} I searched {result['rounds_run']} rounds and "
        f"settled on {best['label']}. {result['stop_reason'].capitalize()}. "
        f"On the untouched lock-box it did {lb.get('trades', 0)} trades at profit "
        f"factor {lb.get('profit_factor')}. {result['verdict']}."
    )
