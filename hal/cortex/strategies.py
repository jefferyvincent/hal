"""Named strategy playbooks from the vault's Strategy/ folder.

The vault's Rules/trading-rules.md is HAL's GLOBAL gate. This module adds
per-setup PLAYBOOKS: each Strategy/*.md file carries a fenced ```yaml block with
an `applies_to` condition set plus any parameter overrides (stop_loss_pct,
take_profit_pct, max_risk_per_trade_pct, …). When a proposed trade's context
matches a playbook, its parameters override the global rules — and because the
whole trade path (cortex.rules, cerebellum.strategy.exit_levels, sizing) consumes
a single rules-shaped dict, the override needs no execution-chain changes.

Selection is AUTO-MATCH by condition (deterministic, hands-off): the most
specific matching playbook wins; ties and no-match fall back to the global rules.
Only the NUMBERS are parsed here — the prose in each file is for you and for
HAL's reasoning, never the source of a stop level.

Example Strategy/momentum-calls.md:

    ```yaml
    name: momentum-calls
    applies_to:
      symbols: [NVDA, AAPL, MSFT]   # any of these tickers
      bias: [bullish]               # and a bullish setup
      iv_regime: [low, mid]         # and non-rich IV
    stop_loss_pct: 30
    take_profit_pct: 60
    max_risk_per_trade_pct: 1.0
    ```

A condition key is satisfied when the trade context's value is in the file's
allowed list; a playbook matches only if EVERY listed condition holds. An empty
`applies_to` never auto-selects (use the global rules as the deliberate default).
"""
from __future__ import annotations

import re
from typing import Any, Optional

import yaml

from hal.brainstem.config import VAULT_DIR

_STRATEGY_DIR = VAULT_DIR / "Strategy"
_FENCE_RE = re.compile(r"```ya?ml\s*\n(.*?)```", re.DOTALL)

# applies_to key -> the trade-context key it is matched against.
_CONDITION_KEYS = {"symbols": "symbol", "bias": "bias", "iv_regime": "iv_regime"}


def load_strategies() -> list[dict[str, Any]]:
    """Parse every Strategy/*.md playbook (the yaml block in each). Files without
    a yaml block or with invalid yaml are skipped, never fatal. `name` defaults
    to the filename stem."""
    if not _STRATEGY_DIR.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(_STRATEGY_DIR.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        m = _FENCE_RE.search(text)
        if not m:
            continue
        try:
            data = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            continue
        if not isinstance(data, dict):
            continue
        data.setdefault("name", path.stem)
        out.append(data)
    return out


def _match_score(applies_to: dict, context: dict) -> Optional[int]:
    """Number of conditions satisfied, or None if any listed condition fails.
    A playbook with no conditions returns None (never auto-selected)."""
    if not applies_to:
        return None
    score = 0
    for key, allowed in applies_to.items():
        ctx_key = _CONDITION_KEYS.get(key)
        if ctx_key is None:
            continue  # unknown condition key — ignore, don't fail on it
        allowed_list = [str(a).lower() for a in
                        (allowed if isinstance(allowed, list) else [allowed])]
        val = str(context.get(ctx_key, "")).lower()
        if not val or val not in allowed_list:
            return None
        score += 1
    return score or None


def select_strategy(context: dict,
                    strategies: Optional[list[dict]] = None) -> Optional[dict]:
    """Return the most-specific playbook whose conditions all match `context`
    (keys: symbol, bias, iv_regime), or None to fall back to the global rules.
    Most conditions satisfied wins; on a tie the first by filename order wins."""
    strategies = strategies if strategies is not None else load_strategies()
    best: Optional[dict] = None
    best_score = 0
    for s in strategies:
        score = _match_score(s.get("applies_to") or {}, context)
        if score is not None and score > best_score:
            best, best_score = s, score
    return best
