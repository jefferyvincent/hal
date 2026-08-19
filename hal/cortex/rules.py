"""Parse HAL trading rules from Rules/trading-rules.md in the vault.

The file contains a fenced ```yaml block that is the in-memory gate.
HAL re-reads on demand (no caching — file is tiny, reads are fast).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from hal.brainstem.config import VAULT_DIR

_RULES_PATH = VAULT_DIR / "Rules" / "trading-rules.md"
_FENCE_RE = re.compile(r"```ya?ml\s*\n(.*?)```", re.DOTALL)

_DEFAULT_RULES: dict[str, Any] = {
    "max_risk_per_trade_pct": 1.5,
    "max_concurrent_risk_pct": 6,
    "instruments": ["options-large-cap", "index-etf"],
    "wont_trade": ["earnings-week", "price-under-5"],
    "min_conviction": "confirmed",
    "min_reward_risk": 1.5,
    "stop": "pct-of-premium",
    "stop_loss_pct": 20,
    "take_profit_pct": 20,
    "limit_buffer_pct": 2,
    "sizing": "fixed-fractional",
}


def load_rules() -> dict[str, Any]:
    """Read the yaml gate block from trading-rules.md. Falls back to defaults."""
    if not _RULES_PATH.exists():
        return dict(_DEFAULT_RULES)
    text = _RULES_PATH.read_text(encoding="utf-8")
    m = _FENCE_RE.search(text)
    if not m:
        return dict(_DEFAULT_RULES)
    try:
        parsed = yaml.safe_load(m.group(1)) or {}
        return {**_DEFAULT_RULES, **parsed}
    except yaml.YAMLError:
        return dict(_DEFAULT_RULES)


# How far ahead "earnings-week" reaches. A won't-trade rule should err toward
# blocking, so this is a full calendar week rather than the 3-day window the
# IV-crush *screener* uses (that one only needs to flag a setup, not veto one).
_EARNINGS_BLOCK_DAYS = 7

_PRICE_UNDER_RE = re.compile(r"price[\s_-]*(?:under|below)[\s_-]*(\d+(?:\.\d+)?)")
_DEFAULT_PRICE_FLOOR = 5.0

# Sides that OPEN exposure. Semantic blockers apply only to these: a rule saying
# "don't trade earnings week" must never stop you closing a position during one.
_OPENING_SIDES = {"buy", "long"}


def _wont_trade_failures(wont: list[str], symbol: str, strategy: str, side: str,
                         underlying_price: float | None,
                         days_to_earnings: int | None) -> list[str]:
    """Evaluate the vault's `wont_trade` list.

    Two entries name conditions about the WORLD rather than words in a strategy
    label — 'earnings-week' and 'price-under-N'. Those are checked against facts
    the caller supplies. A fact left None means "couldn't verify", and the
    blocker is SKIPPED: the calendar and quote feeds are keyless and do go down,
    and halting all trading on a fetch hiccup is the worse failure. This matches
    how the account-size caps already skip when no risk estimate is given.

    Anything else in the list falls through to keyword matching, which now tests
    both the hyphenated and spaced forms — previously only the spaced form was
    compared, so a 'no-chase' style entry could never match its own spelling.
    """
    failures: list[str] = []
    opening = side.lower().strip() in _OPENING_SIDES
    haystack = f"{strategy} {symbol}".lower()

    for blocker in wont:
        raw = str(blocker).strip().lower()
        if not raw:
            continue
        spaced = raw.replace("-", " ").replace("_", " ")

        if spaced.startswith("earnings"):
            if opening and days_to_earnings is not None \
                    and 0 <= days_to_earnings <= _EARNINGS_BLOCK_DAYS:
                failures.append(
                    f"blocked: {raw} — reports in {days_to_earnings}d "
                    f"(within {_EARNINGS_BLOCK_DAYS}d)")
            continue

        price_match = _PRICE_UNDER_RE.search(spaced)
        if price_match:
            floor = float(price_match.group(1) or _DEFAULT_PRICE_FLOOR)
            if opening and underlying_price is not None and underlying_price < floor:
                failures.append(
                    f"blocked: {raw} — underlying at ${underlying_price:.2f}")
            continue

        # Plain keyword blocker: match either spelling against strategy/symbol.
        if raw in haystack or spaced in haystack:
            failures.append(f"blocked: {raw}")

    return failures


def check_trade(symbol: str, strategy: str, side: str, reward_risk: float | None,
                account_size: float = 0, trade_risk_dollars: float = 0,
                concurrent_risk_dollars: float = 0,
                underlying_price: float | None = None,
                days_to_earnings: int | None = None) -> dict[str, Any]:
    """Run the loaded rules gate against a proposed trade.

    Pure and synchronous by design — the caller fetches any facts. `underlying_
    price` and `days_to_earnings` let the `wont_trade` conditions be judged on
    reality instead of on the strategy's name; omit them and those blockers are
    skipped rather than fired.

    Returns {passed: bool, failures: list[str], rules: dict}.
    """
    rules = load_rules()
    failures = []

    # Instrument filter
    allowed = rules.get("instruments", [])
    if allowed and strategy:
        strat_lower = strategy.lower()
        # Accept if any allowed instrument keyword appears in the strategy name
        if not any(inst.replace("-", " ") in strat_lower or inst in strat_lower
                   for inst in allowed):
            # Allow if we simply don't know — don't block on ambiguity
            pass

    failures.extend(_wont_trade_failures(
        rules.get("wont_trade", []) or [], symbol, strategy, side,
        underlying_price, days_to_earnings))

    # Reward/risk gate
    min_rr = float(rules.get("min_reward_risk", 1.5))
    if reward_risk is not None and reward_risk < min_rr:
        failures.append(f"reward/risk {reward_risk:.1f} < minimum {min_rr:.1f}")

    # Per-trade risk cap
    if account_size > 0 and trade_risk_dollars > 0:
        max_pct = float(rules.get("max_risk_per_trade_pct", 1.5))
        actual_pct = trade_risk_dollars / account_size * 100
        if actual_pct > max_pct:
            failures.append(
                f"trade risk {actual_pct:.1f}% > max {max_pct:.1f}% of account"
            )

    # Concurrent risk cap
    if account_size > 0 and concurrent_risk_dollars > 0:
        max_pct = float(rules.get("max_concurrent_risk_pct", 6))
        actual_pct = concurrent_risk_dollars / account_size * 100
        if actual_pct > max_pct:
            failures.append(
                f"concurrent risk {actual_pct:.1f}% > max {max_pct:.1f}% of account"
            )

    result = {"passed": len(failures) == 0, "failures": failures, "rules": rules}
    # Audit every verdict here rather than at the three call sites, so a refusal
    # is recorded no matter who asked (order path, committee, or vault write).
    from hal.hippocampus import persistence
    persistence.log_decision(
        "rules_gate", symbol, result["passed"], "; ".join(failures),
        {"strategy": strategy, "side": side, "reward_risk": reward_risk,
         "account_size": account_size, "trade_risk_dollars": trade_risk_dollars,
         "concurrent_risk_dollars": concurrent_risk_dollars,
         "underlying_price": underlying_price,
         "days_to_earnings": days_to_earnings},
    )
    return result
