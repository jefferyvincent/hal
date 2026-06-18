"""Multi-agent trade committee — a right-sized adaptation of the TradingAgents
pattern (TauricResearch) for HAL's options-first, local-inference setup.

The shape mirrors a trading desk, but re-specialized for what HAL actually has
an edge in (vol regime, the chain, the user's own journal) rather than
fundamentals/social:

    1. Analysts (parallel, FAST model) — three narrow reads, each grounded in a
       real tool:
         · Vol analyst     → analysis.iv_context        (rich/cheap premium)
         · Setup analyst   → analysis.screen_options     (structure/liquidity)
         · Catalyst analyst→ rag.journal_search          (prior theses / context)
    2. Researchers (parallel, SMART model) — a bull and a bear argue the tape
       from the same evidence. One round. This is the cheapest, highest-value
       guard against the model talking itself into a position.
    3. Reflection — past CLOSED trades on this symbol/structure are retrieved and
       fed to the judge, so realized outcomes shape the next decision.
    4. Judge (SMART model) — synthesizes a single decision: TRADE or PASS, with
       structure, side, thesis, invalidation, conviction.
    5. Rules gate (deterministic, rules.check_trade) — the final word, exactly
       like TradingAgents' portfolio manager, except it can't be sweet-talked.
       A failed gate forces PASS regardless of how good the thesis sounded.

Design constraints this respects:
  · LOCAL inference — analysts run on the fast model, only debate+judge pay for
    the 27B; independent steps run concurrently. Built to be invoked as an async
    "deep dive", never on the live one-sentence voice turn.
  · No server import (avoids the cortex<-server cycle); this module only reaches
    "down" into analysis / cerebellum / rules / rag.
  · Degrades gracefully — any analyst or the journal failing yields a neutral
    read, never an exception, so a missing Massive key or un-ingested vault can't
    block the committee.

This module is intentionally NOT wired into tools/UI yet — it exposes one
entrypoint, run_committee(), so the orchestration can be reviewed and backtested
against build_trade_reco before it's trusted with a trigger.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Optional

import httpx

from hal.brainstem.config import (
    OLLAMA_URL,
    OLLAMA_MODEL,
    OLLAMA_FAST_MODEL,
    TRADING_RULES,
)
from hal.cortex import analysis
from hal.cerebellum import option_strategy
from hal.cortex.rules import check_trade

# Horizon → days-to-expiration window for the chain screen. Keeps the setup
# analyst looking at contracts that match the intended holding period.
_HORIZON_DTE: dict[str, tuple[int, int]] = {
    "day": (0, 7),
    "swing": (5, 45),
    "position": (30, 120),
    "leap": (180, 400),
}


# --- LLM plumbing -----------------------------------------------------------
def _strip_thinking(text: str) -> str:
    """qwen3.6 emits <think>...</think>; drop it (mirror of server._strip_thinking)."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


async def _llm(
    prompt: str,
    *,
    system: str,
    model: str,
    temperature: float = 0.4,
    num_ctx: int = 4096,
    timeout: float = 120.0,
) -> str:
    """One-shot, non-streaming completion. Returns '' on any failure so every
    agent can degrade to a neutral read instead of crashing the committee."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "think": False,
        "options": {"temperature": temperature, "num_ctx": num_ctx},
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(OLLAMA_URL, json=payload)
            r.raise_for_status()
            return _strip_thinking(r.json().get("message", {}).get("content", ""))
    except Exception as e:
        print(f"[committee] llm failed ({model}): {e}")
        return ""


def _parse_json(text: str) -> dict:
    """Pull the first {...} object out of a model reply, tolerantly. Returns {}
    when nothing parses so callers apply their own defaults."""
    if not text:
        return {}
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


def _lean(d: dict) -> str:
    v = str(d.get("lean", "neutral")).lower()
    return v if v in ("bullish", "bearish", "neutral") else "neutral"


# --- Analyst roles (fast model, one tool each) ------------------------------
_VOL_SYS = (
    "You are a volatility analyst on an options desk. Given an implied-vs-"
    "realized vol read, state in 2 sentences whether premium is rich (favor "
    "selling), cheap (favor buying), or fair. Reply ONLY as JSON: "
    '{"lean":"bullish|bearish|neutral","confidence":0.0-1.0,"note":"..."} '
    "where lean reflects premium-buying(bullish on vol)/selling(bearish on vol) "
    "edge, not price direction."
)
_SETUP_SYS = (
    "You are a setup/structure analyst on an options desk. Given screened chain "
    "candidates (delta/IV/OI/spread), judge whether there is a clean, liquid "
    "structure to express a directional or neutral view. Reply ONLY as JSON: "
    '{"lean":"bullish|bearish|neutral","confidence":0.0-1.0,"note":"..."}.'
)
_CATALYST_SYS = (
    "You are a catalyst analyst. Given prior journal notes on this symbol, "
    "summarize the standing thesis and any known catalyst or risk. If there is "
    "no prior context, say so and lean neutral. Reply ONLY as JSON: "
    '{"lean":"bullish|bearish|neutral","confidence":0.0-1.0,"note":"..."}.'
)


def _summarize_vol(iv: dict) -> str:
    if not iv or iv.get("error"):
        return "No vol data available."
    return (
        f"underlying={iv.get('underlying')} price={iv.get('underlying_price')} "
        f"atm_iv={iv.get('atm_iv')} iv/hv30={iv.get('iv_over_hv30')} "
        f"verdict={iv.get('verdict')} ({iv.get('interpretation')})"
    )


def _summarize_chain(side: str, screen: dict) -> str:
    if not screen or screen.get("error"):
        return f"{side}: no candidates ({(screen or {}).get('error', 'none')})."
    rows = screen.get("candidates", [])[:4]
    if not rows:
        return f"{side}: no candidates passed filters."
    parts = [
        f"K{r.get('strike')} dte{r.get('dte')} delta{r.get('delta')} "
        f"iv{r.get('iv')} oi{r.get('oi')} spr{r.get('spread_pct')}%"
        for r in rows
    ]
    return f"{side} candidates: " + " | ".join(parts)


async def _analyst(system: str, evidence: str, label: str) -> dict:
    """Run one analyst read on the fast model; never raises."""
    raw = await _llm(
        f"Evidence:\n{evidence}\n\nGive your read.",
        system=system,
        model=OLLAMA_FAST_MODEL,
        temperature=0.3,
        num_ctx=2048,
    )
    out = _parse_json(raw)
    return {
        "role": label,
        "lean": _lean(out),
        "confidence": float(out.get("confidence", 0.4) or 0.4),
        "note": str(out.get("note") or raw[:300] or "no read"),
        "evidence": evidence,
    }


async def _gather_analysts(symbol: str, horizon: str) -> list[dict]:
    """Collect evidence (tool calls) then the three analyst reads, concurrently."""
    dte_min, dte_max = _HORIZON_DTE.get(horizon, _HORIZON_DTE["swing"])

    async def vol() -> dict:
        try:
            iv = await analysis.iv_context(symbol)
        except Exception as e:
            iv = {"error": str(e)}
        return await _analyst(_VOL_SYS, _summarize_vol(iv), "vol")

    async def setup() -> dict:
        try:
            calls = await analysis.screen_options(
                underlying=symbol, side="call", dte_min=dte_min, dte_max=dte_max, top_n=6)
            puts = await analysis.screen_options(
                underlying=symbol, side="put", dte_min=dte_min, dte_max=dte_max, top_n=6)
        except Exception as e:
            calls = puts = {"error": str(e)}
        evidence = _summarize_chain("CALL", calls) + "\n" + _summarize_chain("PUT", puts)
        return await _analyst(_SETUP_SYS, evidence, "setup")

    async def catalyst() -> dict:
        notes = await _journal(symbol, query=f"{symbol} thesis catalyst", status=None, k=4)
        evidence = notes or "No prior journal notes for this symbol."
        return await _analyst(_CATALYST_SYS, evidence, "catalyst")

    return list(await asyncio.gather(vol(), setup(), catalyst()))


# --- Reflection memory (journal RAG) ----------------------------------------
async def _journal(symbol: str, *, query: str, status: Optional[str], k: int) -> str:
    """Tolerant journal_search wrapper → compact text. '' if RAG unavailable."""
    try:
        from hal.cortex import rag  # lazy: avoids loading LanceDB unless used
        results = await rag.journal_search(query=query, symbol=symbol, status=status, k=k)
    except Exception as e:
        print(f"[committee] journal_search unavailable: {e}")
        return ""
    lines = []
    for r in results or []:
        head = (r.get("text") or "").strip().split("\n", 1)[0][:160]
        lines.append(
            f"[{r.get('status')}] {r.get('strategy')} {r.get('symbol')} "
            f"(opened {r.get('opened')}): {head}"
        )
    return "\n".join(lines)


# --- Researcher debate (smart model, bull vs bear) --------------------------
_BULL_SYS = (
    "You are the BULL researcher. Argue the strongest case to put on a bullish "
    "or premium-buying trade in this name, in 3-4 sentences. Engage the actual "
    "evidence; do not hedge into neutrality. End with the single best structure."
)
_BEAR_SYS = (
    "You are the BEAR researcher. Argue the strongest case AGAINST the trade — "
    "the bearish read, the vol/liquidity traps, what kills it — in 3-4 "
    "sentences. Your job is to find the reason to pass. Be specific."
)


async def _debate(brief: str) -> dict:
    bull, bear = await asyncio.gather(
        _llm(brief, system=_BULL_SYS, model=OLLAMA_MODEL, temperature=0.6, num_ctx=4096),
        _llm(brief, system=_BEAR_SYS, model=OLLAMA_MODEL, temperature=0.6, num_ctx=4096),
    )
    return {"bull": bull.strip() or "(no bull case)", "bear": bear.strip() or "(no bear case)"}


# --- Judge (smart model) ----------------------------------------------------
_JUDGE_SYS = (
    "You are the head trader. You receive three analyst reads, a bull case, a "
    "bear case, lessons from past trades, and the available option structures. "
    "Make ONE decision. Defined-risk only — never naked short options. If the "
    "bear case is not clearly beaten, PASS; passing is a valid, common answer. "
    "Reply ONLY as JSON: "
    '{"decision":"TRADE|PASS","side":"call|put|neutral","structure":"<label '
    'from the provided list>","conviction":"high|medium|low","thesis":"one '
    'sentence","invalidation":"one sentence","max_loss_note":"one sentence"}.'
)


async def _judge(brief: str) -> dict:
    raw = await _llm(brief, system=_JUDGE_SYS, model=OLLAMA_MODEL,
                     temperature=0.35, num_ctx=6144)
    out = _parse_json(raw)
    decision = str(out.get("decision", "PASS")).upper()
    return {
        "decision": "TRADE" if decision == "TRADE" else "PASS",
        "side": str(out.get("side", "neutral")).lower(),
        "structure": str(out.get("structure") or "").strip(),
        "conviction": str(out.get("conviction", "low")).lower(),
        "thesis": str(out.get("thesis") or "").strip(),
        "invalidation": str(out.get("invalidation") or "").strip(),
        "max_loss_note": str(out.get("max_loss_note") or "").strip(),
        "raw": raw[:600],
    }


# --- Orchestration ----------------------------------------------------------
def _consensus_bias(analysts: list[dict]) -> str:
    score = sum(
        a["confidence"] * (1 if a["lean"] == "bullish" else -1 if a["lean"] == "bearish" else 0)
        for a in analysts
    )
    return "bullish" if score > 0.3 else "bearish" if score < -0.3 else "neutral"


async def run_committee(
    symbol: str,
    *,
    horizon: str = "swing",
    account_size: float = 0.0,
) -> dict:
    """Run the full committee on `symbol` and return a structured verdict.

    Pure analysis — places no orders, pushes nothing to the UI. Safe to call
    repeatedly (e.g. from a backtest harness comparing it to build_trade_reco).
    """
    symbol = symbol.upper().strip()

    # 1. Analysts (evidence + reads), concurrently.
    analysts = await _gather_analysts(symbol, horizon)
    bias = _consensus_bias(analysts)

    # 2. Candidate structures for that bias × vol regime (deterministic).
    vol_read = next((a for a in analysts if a["role"] == "vol"), {})
    iv_level = {"RICH": "high", "CHEAP": "low", "FAIR": "medium"}.get(
        _verdict_from(vol_read), "unknown")
    structures = candidate_structures(symbol, bias, iv_level)

    # 3. Reflection: realized outcomes from past closed trades like this.
    reflection = await _journal(
        symbol, query=f"{symbol} {bias} {' '.join(structures[:2])}", status="closed", k=4)

    # 4-5. Debate → judge → deterministic rules gate.
    return await decide_from_evidence(
        symbol, analysts=analysts, structures=structures, iv_level=iv_level,
        bias=bias, reflection=reflection, account_size=account_size, horizon=horizon)


def candidate_structures(symbol: str, bias: str, iv_level: str) -> list[str]:
    """Deterministic structure shortlist for a bias × vol regime (no I/O, no LLM).
    Reused by the backtest so its structure list matches the live committee."""
    strat = option_strategy.recommend_strategy(
        underlying=symbol, bias=bias, iv_level=iv_level)
    return [r.get("label", r.get("spread_type", "")) for r in strat.get("recommendations", [])]


async def decide_from_evidence(
    symbol: str,
    *,
    analysts: list[dict],
    structures: list[str],
    iv_level: str,
    bias: str,
    reflection: str = "",
    account_size: float = 0.0,
    horizon: str = "swing",
) -> dict:
    """The reasoning core: bull/bear debate → judge → deterministic rules gate →
    verdict. Deliberately separated from evidence-gathering so the backtest can
    drive it with point-in-time RECONSTRUCTED evidence instead of live tool
    calls — same reasoning, swappable inputs."""
    analyst_block = "\n".join(f"- {a['role']}: lean={a['lean']} conf={a['confidence']:.2f} :: {a['note']}"
                              for a in analysts)
    brief = (
        f"Symbol: {symbol}  | horizon: {horizon}  | consensus bias: {bias}  | vol: {iv_level}\n"
        f"Analyst reads:\n{analyst_block}\n"
        f"Available structures: {', '.join(structures) or 'none'}\n"
        f"Past trade lessons:\n{reflection or '(none on record)'}"
    )
    debate = await _debate(brief)
    judge = await _judge(
        brief + f"\n\nBULL:\n{debate['bull']}\n\nBEAR:\n{debate['bear']}"
        + (f"\n\nUser's standing rules:\n{TRADING_RULES[:1200]}" if TRADING_RULES.strip() else "")
    )

    # Deterministic rules gate has the final word (cannot be talked out of a
    # PASS). Backstop only — account caps skip without a dollar risk estimate.
    gate = check_trade(
        symbol=symbol,
        strategy=judge["structure"] or " ".join(structures[:1]),
        side="buy" if judge["side"] in ("call", "neutral") else "sell",
        reward_risk=None,
        account_size=account_size,
    )
    decision = judge["decision"]
    if decision == "TRADE" and not gate["passed"]:
        decision = "PASS"

    verdict = {
        "symbol": symbol,
        "horizon": horizon,
        "decision": decision,
        "conviction": judge["conviction"],
        "bias": bias,
        "iv_level": iv_level,
        "side": judge["side"],
        "structure": judge["structure"],
        "thesis": judge["thesis"],
        "invalidation": judge["invalidation"],
        "max_loss_note": judge["max_loss_note"],
        "rules_passed": gate["passed"],
        "rules_failures": gate["failures"],
        "analysts": analysts,
        "debate": debate,
        "reflection": reflection,
        "candidate_structures": structures,
    }
    verdict["markdown"] = _render_markdown(verdict)
    return verdict


def _verdict_from(vol_read: dict) -> str:
    """Recover the RICH/FAIR/CHEAP verdict from the vol analyst's evidence."""
    ev = vol_read.get("evidence", "") if vol_read else ""
    m = re.search(r"verdict=(RICH|FAIR|CHEAP|UNKNOWN)", ev)
    return m.group(1) if m else "UNKNOWN"


def _render_markdown(v: dict) -> str:
    """Human-facing summary — the body of a Trade Idea (or a documented PASS)."""
    head = f"**Committee: {v['symbol']} — {v['decision']}**"
    if v["decision"] == "TRADE":
        head += f" ({v['conviction']} conviction)"
    lines = [
        head,
        "",
        f"- Bias: {v['bias']} · Vol: {v['iv_level']} · Side: {v['side']}"
        + (f" · Structure: {v['structure']}" if v["structure"] else ""),
    ]
    if v["thesis"]:
        lines.append(f"- Thesis: {v['thesis']}")
    if v["invalidation"]:
        lines.append(f"- Invalidation: {v['invalidation']}")
    if v["max_loss_note"]:
        lines.append(f"- Risk: {v['max_loss_note']}")
    if not v["rules_passed"]:
        lines.append(f"- ⚠ Rules gate: {'; '.join(v['rules_failures']) or 'failed'}")
    lines += [
        "",
        "<details><summary>Desk reasoning</summary>",
        "",
        *[f"- **{a['role']}** ({a['lean']}, {a['confidence']:.0%}): {a['note']}" for a in v["analysts"]],
        "",
        f"**Bull:** {v['debate']['bull']}",
        "",
        f"**Bear:** {v['debate']['bear']}",
    ]
    if v["reflection"]:
        lines += ["", f"**Past trades:** {v['reflection']}"]
    lines.append("</details>")
    return "\n".join(lines)
