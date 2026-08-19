"""Multi-agent trade committee — a right-sized adaptation of the TradingAgents
pattern (TauricResearch) for HAL's options-first, local-inference setup.

The shape mirrors a trading desk, but re-specialized for what HAL actually has
an edge in (vol regime, the chain, the user's own journal) rather than
fundamentals/social:

    1. Analysts (parallel, FAST model) — narrow reads, each grounded in a
       real tool:
         · Vol analyst     → analysis.iv_context        (rich/cheap premium)
         · Setup analyst   → analysis.screen_options     (structure/liquidity)
         · Catalyst analyst→ rag.journal_search          (prior theses / context)
         · Analysis analyst→ vault Analysis/ notes        (the desk's own written
           trade ideas for this name) — only added when a note exists, so an
           empty folder leaves the desk's scoring untouched.
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
    read, never an exception, so a missing Alpaca key or un-ingested vault can't
    block the committee.

This module is intentionally NOT wired into tools/UI yet — it exposes one
entrypoint, run_committee(), so the orchestration can be reviewed and backtested
against build_trade_reco before it's trusted with a trigger.
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

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
from hal.hippocampus.vault import list_notes

# Optional progress callback: (step, summary, detail) -> awaitable. Lets a caller
# (the server) surface each committee step as its own telemetry / cognition event
# as it happens. None = silent — e.g. the backtest harness, which wants only the
# final verdict.
Emit = Optional[Callable[[str, str, str], Awaitable[None]]]


async def _emit(emit: Emit, step: str, summary: str, detail: str) -> None:
    """Fire a progress event, swallowing any callback error (never block the
    committee on a UI hiccup)."""
    if not emit:
        return
    try:
        await emit(step, summary, detail)
    except Exception as e:
        print(f"[committee] emit failed ({step}): {e}")


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


def _brace_spans(text: str) -> list[str]:
    """Every balanced top-level {...} substring, in order. A naive
    first-brace-to-last-brace grab breaks when the model emits a stray brace in
    prose ('the {call} spread') before the real object — the span then covers
    both and fails to parse. Scanning for balanced spans isolates the real JSON."""
    spans, depth, start = [], 0, -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start >= 0:
                spans.append(text[start:i + 1])
    return spans


def _parse_json(text: str) -> dict:
    """Pull a JSON object out of a model reply, tolerantly. Local models wrap the
    object in prose, stray braces, markdown fences, or trailing commas — any of
    which broke the old naive grab and silently defaulted the judge to PASS. Try
    each balanced {...} candidate newest-first (the real answer follows any
    reasoning), with a trailing-comma repair. Returns {} when nothing parses."""
    if not text:
        return {}
    for span in reversed(_brace_spans(text)):
        for attempt in (span, re.sub(r",(\s*[}\]])", r"\1", span)):
            try:
                obj = json.loads(attempt)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                return obj
    return {}


def _lean(d: dict) -> str:
    v = str(d.get("lean", "neutral")).lower()
    return v if v in ("bullish", "bearish", "neutral") else "neutral"


# --- Injected soft context (sentiment / alerts / HAL's seeded idea) ----------
# News and Reddit sentiment are classified upstream by the server (it owns the
# feeds + creds), so the committee takes them as pre-scored evidence — same
# dependency-injection shape as `open_positions` and `emit` — and converts them
# to analyst votes here with NO extra model call. Social is capped below news,
# and both cap well under the hard vol/chain/regime reads, so chatter informs
# the vote without ever dominating it.
_SENTIMENT_SPEC = (("news", "news", 0.55), ("reddit", "social", 0.45))


def _sentiment_reads(sentiment: Optional[dict]) -> list[dict]:
    """Turn injected {news,reddit} sentiment into analyst reads. A source with
    zero items is skipped (like the analysis analyst) so a quiet name doesn't
    dilute consensus with neutral filler."""
    reads = []
    for key, role, cap in _SENTIMENT_SPEC:
        src = (sentiment or {}).get(key) or {}
        count = int(src.get("count") or 0)
        if count <= 0:
            continue
        lean = str(src.get("label", "neutral")).lower()
        lean = lean if lean in ("bullish", "bearish", "neutral") else "neutral"
        # More items → a touch more confidence, capped; a neutral read stays low
        # so it barely moves the score either way.
        conf = 0.2 if lean == "neutral" else min(cap, 0.25 + 0.04 * count)
        note = (src.get("thesis") or "").strip() or f"{count} {role} item(s), {lean}"
        reads.append({
            "role": role,
            "lean": lean,
            "confidence": round(conf, 2),
            "note": note,
            "evidence": f"{count} {role} item(s) classified {lean}",
        })
    return reads


def _format_alerts(alerts: Optional[list[dict]]) -> str:
    """Compact view of recent fired alerts on the name. A burst of these is
    usually noise, so the desk sees them as context to weigh, not a vote."""
    lines = []
    for a in (alerts or [])[:8]:
        msg = " ".join(str(a.get("message") or "").split())[:120]
        lines.append(f"[{a.get('fired_at', '?')}] {a.get('symbol', '')}: {msg}".strip())
    return "\n".join(lines)


def _format_proposed(idea: Optional[dict]) -> str:
    """One-line rendering of the idea HAL is pleading to the desk."""
    if not idea:
        return ""
    parts = [str(idea.get("side") or "").strip(), str(idea.get("structure") or "").strip()]
    head = " ".join(p for p in parts if p) or "an idea"
    thesis = str(idea.get("thesis") or "").strip()
    return head + (f" — {thesis}" if thesis else "")


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
_ANALYSIS_SYS = (
    "You are a research analyst. You are given the desk's OWN written analysis "
    "notes on this symbol — actionable trade ideas the trader has documented "
    "(direction, setup, catalyst, structure). Summarize the standing trade idea "
    "and its direction, and weight your confidence by how specific and current "
    "the analysis is. If the analysis is thin or stale, lean neutral. Reply ONLY "
    'as JSON: {"lean":"bullish|bearish|neutral","confidence":0.0-1.0,"note":"..."}.'
)


def _summarize_vol(iv: dict) -> str:
    if not iv or iv.get("error"):
        return f"No vol data available ({(iv or {}).get('error', 'none')})."
    # Include the realized-vol (HV) ladder so the analyst can read the regime even
    # when ATM implied vol is unavailable (e.g. options snapshot down).
    hv = (f"hv10={iv.get('hv10')} hv30={iv.get('hv30')} "
          f"hv60={iv.get('hv60')} hv90={iv.get('hv90')}")
    return (
        f"underlying={iv.get('underlying')} price={iv.get('underlying_price')} "
        f"atm_iv={iv.get('atm_iv')} iv/hv30={iv.get('iv_over_hv30')} "
        f"verdict={iv.get('verdict')} ({iv.get('interpretation')}); realized: {hv}"
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


def _analysis_notes(symbol: str) -> str:
    """Read the desk's written Analysis/ notes for `symbol` → compact text.
    '' when the folder has nothing (active) on this name. Archived notes are
    skipped so a retired idea stops swaying the committee."""
    try:
        notes = list_notes("Analysis", type="analysis", symbol=symbol.upper())
    except Exception as e:
        print(f"[committee] analysis notes unavailable: {e}")
        return ""
    blocks = []
    for n in notes:
        fm = n["frontmatter"]
        if str(fm.get("status", "active")).lower() == "archived":
            continue
        body = " ".join(n["body"].split())[:600]
        blocks.append(
            f"[{fm.get('bias', '?')} / {fm.get('conviction', '?')} conviction] "
            f"{Path(n['rel_path']).stem}: {body}"
        )
    return "\n\n".join(blocks)


async def _gather_analysts(symbol: str, horizon: str) -> list[dict]:
    """Collect evidence (tool calls) then the analyst reads, concurrently. The
    analysis analyst is only included when the vault has a written idea for this
    name, so an empty Analysis/ folder leaves consensus and scoring untouched."""
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

    async def research() -> dict | None:
        evidence = await asyncio.to_thread(_analysis_notes, symbol)
        if not evidence:
            return None
        return await _analyst(_ANALYSIS_SYS, evidence, "analysis")

    async def regime() -> dict | None:
        """Deterministic price-regime read (no LLM): trending up/down vs chop.
        Gives the desk a directional-tape vote the vol/structure/journal analysts
        don't carry. Skipped (None) when bars are unavailable, so a data gap
        leaves the existing consensus untouched."""
        try:
            reg = await analysis.price_regime(symbol)
        except Exception as e:
            print(f"[committee] regime unavailable: {e}")
            return None
        if not reg or reg.get("error"):
            return None
        return {
            "role": "regime",
            "lean": reg["lean"],
            "confidence": float(reg.get("confidence", 0.3) or 0.3),
            "note": reg["note"],
            "evidence": reg.get("evidence", reg["note"]),
        }

    reads = await asyncio.gather(vol(), setup(), catalyst(), research(), regime())
    return [r for r in reads if r is not None]


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
    "Make ONE decision, and be willing to act: when the evidence points to a "
    "clear direction, express it — bullish → a defined-risk CALL structure, "
    "bearish → a defined-risk PUT structure. Defined-risk only; never naked "
    "short options. A bear case ALWAYS exists (a researcher is paid to write "
    "one), so its mere presence is NOT a reason to PASS — weigh whether the "
    "evidence, not the debate, supports a side. PASS only when the analyst reads "
    "genuinely conflict, the direction is unclear/neutral, or the structure and "
    "liquidity are poor — not by default. If HAL's proposed idea is included, it "
    "is the hypothesis on trial: endorse it, refine its structure/side, or reject "
    "it — say which, and don't ignore it. News and social reads are among the "
    "analysts; a cluster of recent alerts is often just noise — weigh whether it's "
    "signal before letting it move you. If an existing position in the name is "
    "shown, factor it in — decide whether to add, hold, trim, or stand aside, "
    "and don't over-concentrate. Reply ONLY as JSON: "
    '{"decision":"TRADE|PASS","side":"call|put|neutral","structure":"<label '
    'from the provided list>","conviction":"high|medium|low","thesis":"one '
    'sentence","invalidation":"one sentence","max_loss_note":"one sentence"}.'
)


async def _judge(brief: str) -> dict:
    raw = await _llm(brief, system=_JUDGE_SYS, model=OLLAMA_MODEL,
                     temperature=0.35, num_ctx=6144)
    out = _parse_json(raw)
    # A judge reply that doesn't parse silently becomes PASS below — log it so an
    # "always do-not-trade" run can be told apart from a real, reasoned pass.
    if not out:
        print(f"[committee] judge JSON unparseable → defaulting PASS; raw={raw[:200]!r}")
    # Diagnostic: the object parsed but has no `decision`/`side` key means the
    # model answered in a different schema (e.g. "recommendation":"BUY") and we're
    # silently defaulting to PASS/neutral. Log the raw so we can see the real shape.
    elif "decision" not in out or "side" not in out:
        print(f"[committee] judge object missing decision/side keys "
              f"(keys={list(out)}) → raw={raw[:300]!r}")
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


# Conviction → weight for the 0-100 committee score.
_CONV_W = {"high": 1.0, "medium": 0.6, "low": 0.3}


def _committee_score(*, decision: str, conviction: str, bias: str,
                     analysts: list[dict], rules_passed: bool) -> int:
    """A single 0-100 conviction-to-trade score. Blends the judge's conviction
    with how strongly the analysts agree on the consensus side, then hard-caps it
    when the desk passed or the rules gate blocked it — so a high number always
    means 'green light to trade', never just 'the model sounded confident'."""
    conv = _CONV_W.get(conviction, 0.3)
    if bias in ("bullish", "bearish") and analysts:
        agree = sum(a["confidence"] for a in analysts if a["lean"] == bias) / len(analysts)
    else:
        agree = 0.0
    score = round((0.55 * conv + 0.45 * min(1.0, agree)) * 100)
    if decision != "TRADE":
        score = min(score, 40)   # a PASS must never read as a green light
    if not rules_passed:
        score = min(score, 20)   # a rules-blocked trade is a hard no
    return max(0, min(100, score))


def _score_band(score: int) -> str:
    return ("strong" if score >= 70 else "moderate" if score >= 50
            else "weak" if score >= 30 else "avoid")


def _format_positions(positions: list[dict]) -> str:
    """Compact one-line-per-leg view of existing holdings in the name."""
    lines = []
    for p in positions or []:
        qty = p.get("qty")
        pl = p.get("unrealized_pl")
        plpc = p.get("unrealized_plpc")
        pl_s = (f"{'+' if (pl or 0) >= 0 else ''}{pl:.0f}" if isinstance(pl, (int, float)) else "?")
        pct_s = (f"{plpc * 100:+.1f}%" if isinstance(plpc, (int, float)) else "")
        lines.append(
            f"{p.get('symbol')} {qty} @ {p.get('avg_entry_price')} → "
            f"{p.get('current_price')} (P&L ${pl_s} {pct_s})".strip())
    return "\n".join(lines)


async def run_committee(
    symbol: str,
    *,
    horizon: str = "swing",
    account_size: float = 0.0,
    emit: Emit = None,
    open_positions: Optional[list[dict]] = None,
    sentiment: Optional[dict] = None,
    alerts: Optional[list[dict]] = None,
    proposed_idea: Optional[dict] = None,
) -> dict:
    """Run the full committee on `symbol` and return a structured verdict.

    Pure analysis — places no orders, pushes nothing to the UI. Safe to call
    repeatedly (e.g. from a backtest harness comparing it to build_trade_reco).
    Pass `emit` to stream each step (analysts → consensus → debate → judge →
    rules gate) as its own progress event. `sentiment` ({news,reddit} reads),
    `alerts` (recent fires on the name), and `proposed_idea` (the idea HAL is
    pleading — {side,structure,thesis}) are injected by the caller; the committee
    weighs them but never fetches them itself (no server import).
    """
    symbol = symbol.upper().strip()

    # 1. Analysts (evidence + reads), concurrently. Injected news/Reddit reads
    #    join the vote so consensus and score reflect the tape's chatter too.
    analysts = await _gather_analysts(symbol, horizon)
    analysts += _sentiment_reads(sentiment)
    bias = _consensus_bias(analysts)
    for a in analysts:
        await _emit(emit, f"analyst.{a['role']}",
                    f"{a['role']}: {a['lean']} ({a['confidence']:.0%})", a["note"])
    await _emit(emit, "consensus", f"consensus bias: {bias}",
                f"Weighted analyst leans → {bias}.")

    # 2. Candidate structures for that bias × vol regime (deterministic).
    vol_read = next((a for a in analysts if a["role"] == "vol"), {})
    iv_level = {"RICH": "high", "CHEAP": "low", "FAIR": "medium"}.get(
        _verdict_from(vol_read), "unknown")
    structures = candidate_structures(symbol, bias, iv_level)

    # 3. Reflection: realized outcomes from past closed trades like this.
    reflection = await _journal(
        symbol, query=f"{symbol} {bias} {' '.join(structures[:2])}", status="closed", k=4)
    if reflection:
        await _emit(emit, "reflection", "past closed trades", reflection)

    if open_positions:
        await _emit(emit, "position", f"holds {len(open_positions)} leg(s) in {symbol}",
                    _format_positions(open_positions))

    # 4-5. Debate → judge → deterministic rules gate.
    return await decide_from_evidence(
        symbol, analysts=analysts, structures=structures, iv_level=iv_level,
        bias=bias, reflection=reflection, account_size=account_size,
        horizon=horizon, emit=emit, open_positions=open_positions,
        alerts=alerts, proposed_idea=proposed_idea)


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
    emit: Emit = None,
    open_positions: Optional[list[dict]] = None,
    alerts: Optional[list[dict]] = None,
    proposed_idea: Optional[dict] = None,
) -> dict:
    """The reasoning core: bull/bear debate → judge → deterministic rules gate →
    verdict. Deliberately separated from evidence-gathering so the backtest can
    drive it with point-in-time RECONSTRUCTED evidence instead of live tool
    calls — same reasoning, swappable inputs. `emit` streams each step;
    `open_positions` (already filtered to this name) lets the desk see what's
    already on and decide to add / hold / trim / stand aside. `alerts` (recent
    fires on the name) and `proposed_idea` (HAL's seeded idea) become context the
    debate + judge weigh — the idea is the hypothesis on trial."""
    proposed_block = _format_proposed(proposed_idea)
    # HAL's own structure joins the shortlist so the judge can endorse it verbatim
    # rather than being forced onto a bias-derived label.
    if proposed_idea and (ps := str(proposed_idea.get("structure") or "").strip()) \
            and ps not in structures:
        structures = [ps, *structures]
    analyst_block = "\n".join(f"- {a['role']}: lean={a['lean']} conf={a['confidence']:.2f} :: {a['note']}"
                              for a in analysts)
    position_block = _format_positions(open_positions)
    alerts_block = _format_alerts(alerts)
    brief = (
        (f"HAL'S PROPOSED IDEA — the hypothesis on trial; endorse, refine, or "
         f"reject it and say which:\n{proposed_block}\n\n" if proposed_block else "")
        + f"Symbol: {symbol}  | horizon: {horizon}  | consensus bias: {bias}  | vol: {iv_level}\n"
        f"Analyst reads:\n{analyst_block}\n"
        f"Available structures: {', '.join(structures) or 'none'}\n"
        f"Past trade lessons:\n{reflection or '(none on record)'}"
        + (f"\nALREADY HELD in {symbol} (decide add/hold/trim/stand-aside, don't "
           f"over-concentrate):\n{position_block}" if position_block else "")
        + (f"\nRecent alerts on {symbol} (often just noise — weigh whether it's "
           f"signal):\n{alerts_block}" if alerts_block else "")
    )
    debate = await _debate(brief)
    await _emit(emit, "debate.bull", "bull case", debate["bull"])
    await _emit(emit, "debate.bear", "bear case", debate["bear"])
    judge = await _judge(
        brief + f"\n\nBULL:\n{debate['bull']}\n\nBEAR:\n{debate['bear']}"
        + (f"\n\nUser's standing rules:\n{TRADING_RULES[:1200]}" if TRADING_RULES.strip() else "")
    )
    await _emit(emit, "judge",
                f"judge: {judge['decision']} {judge['side']} {judge['structure']}".strip(),
                judge["thesis"] or judge["raw"])

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
    await _emit(emit, "rules_gate",
                f"rules gate {'passed' if gate['passed'] else 'failed'} → {decision}",
                "passed" if gate["passed"] else "FAILED: " + "; ".join(gate["failures"]))

    score = _committee_score(decision=decision, conviction=judge["conviction"],
                             bias=bias, analysts=analysts, rules_passed=gate["passed"])
    band = _score_band(score)
    await _emit(emit, "score", f"{decision} · {score}/100 ({band})",
                f"Committee conviction score: {score}/100 — {band}.")
    # One-line decision log — scores/bias are otherwise invisible, so a quiet
    # "everything PASSed" session can't be diagnosed. Covers every caller
    # (scalper, news, review, place-it gate) since they all reach this core.
    print(f"[committee] {symbol}: {decision} score={score} band={band} bias={bias} "
          f"judge_side={judge['side']} conv={judge['conviction']} "
          f"rules={'ok' if gate['passed'] else 'FAIL:' + ';'.join(gate['failures'])}")

    verdict = {
        "symbol": symbol,
        "horizon": horizon,
        "decision": decision,
        "score": score,
        "score_band": band,
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
        "open_positions": open_positions or [],
        "proposed_idea": proposed_idea or {},
        "alerts": alerts or [],
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
    light = "🟢" if v["decision"] == "TRADE" else "🔴"
    score = v.get("score")
    band = v.get("score_band", "")
    head = (f"### {light} {v['decision']} — {v['symbol']}"
            + (f"  ·  score {score}/100 ({band})" if score is not None else ""))
    lines = [
        head,
        "",
        f"- **Recommendation: {'PUT ON THE TRADE' if v['decision'] == 'TRADE' else 'DO NOT TRADE'}**"
        + (f" — {v['conviction']} conviction" if v["decision"] == "TRADE" else ""),
        f"- Bias: {v['bias']} · Vol: {v['iv_level']} · Side: {v['side']}"
        + (f" · Structure: {v['structure']}" if v["structure"] else ""),
    ]
    if v.get("proposed_idea"):
        lines.append(f"- 🗣 HAL pled: {_format_proposed(v['proposed_idea'])}")
    if v.get("open_positions"):
        lines.append(f"- 📌 Already open in {v['symbol']}:")
        for ln in _format_positions(v["open_positions"]).split("\n"):
            lines.append(f"    - {ln}")
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
    if v.get("alerts"):
        lines += ["", f"**Recent alerts (weighed as noise):** {len(v['alerts'])} on record"]
    lines.append("</details>")
    return "\n".join(lines)
