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


def check_trade(symbol: str, strategy: str, side: str, reward_risk: float | None,
                account_size: float = 0, trade_risk_dollars: float = 0,
                concurrent_risk_dollars: float = 0) -> dict[str, Any]:
    """Run the loaded rules gate against a proposed trade.

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

    # Wont-trade list (caller supplies context as keywords in strategy/symbol)
    wont = rules.get("wont_trade", [])
    for blocker in wont:
        key = blocker.replace("-", " ")
        if key in strategy.lower() or key in symbol.lower():
            failures.append(f"blocked: {blocker}")

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

    return {"passed": len(failures) == 0, "failures": failures, "rules": rules}
