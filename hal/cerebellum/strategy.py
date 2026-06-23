"""Strategy primitives shared verbatim by backtest and live trading.

This is the "single code path" nautilus_trader is built around: the rule that
decides when to exit a position, and the shape of the order that does it, are
defined ONCE here and run in both places —

  · backtest (cerebellum.backtest.simulate_trade) walks historical premium bars,
  · live (sensory.brackets) polls the position's Alpaca premium,

— and both call exit_signal() to make the decision and build an OrderIntent to
act on it. A backtest therefore exercises the exact exit logic the live trader
runs; if the rule changes, both move together.

Entries are deliberately NOT unified: live entries are LLM/committee-driven
(discretionary), while the backtest's entry is a mechanical S/R+RSI signal. Only
the management/execution half is a genuine single code path, so that's all this
module claims.

OrderIntent is venue-agnostic; to_spec() turns it into a concrete broker spec via
the same sensory.broker.prepare_order used live, so the order is constructed
identically on both sides. broker is imported lazily so the backtest/strategy
import graph never drags in the Alpaca SDK unless an intent is actually realized.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# Fallback exit policy used only if the vault rules define no stop/take-profit
# (historically the backtest's hardcoded ±50%). Normally the vault's
# stop_loss_pct / take_profit_pct supply these, so backtest and live match.
_FALLBACK_STOP_PCT = 50.0
_FALLBACK_TP_PCT = 50.0


def exit_levels(entry_premium: float, rules: Optional[dict] = None) -> tuple[float, float]:
    """Stop and take-profit PREMIUM levels for a long option, sourced from the
    vault trading-rules (stop_loss_pct / take_profit_pct). Returns (stop, tp);
    a 0 means that side is disabled. Pass a pre-loaded `rules` dict to avoid
    re-reading the vault in a loop. This is the single source of truth both the
    backtest and the live bracket-arming compute their levels from.
    """
    if rules is None:
        from hal.cortex import rules as rules_mod
        rules = rules_mod.load_rules()
    stop_pct = float(rules.get("stop_loss_pct", _FALLBACK_STOP_PCT))
    tp_pct = float(rules.get("take_profit_pct", _FALLBACK_TP_PCT))
    stop = entry_premium * (1 - stop_pct / 100.0) if stop_pct > 0 else 0.0
    tp = entry_premium * (1 + tp_pct / 100.0) if tp_pct > 0 else 0.0
    return stop, tp


def exit_signal(current: float, stop: float, tp: float) -> Optional[str]:
    """The stop / take-profit rule for a LONG option, judged on premium.

    Returns 'stop', 'take_profit', or None. A level of 0 disables that side.
    Stop is checked first so a gap that blows through both exits as a loss.
    """
    if stop > 0 and current <= stop:
        return "stop"
    if tp > 0 and current >= tp:
        return "take_profit"
    return None


@dataclass(frozen=True)
class OrderIntent:
    """A venue-agnostic order request. Realized into a broker spec (and thus an
    Alpaca order, or a SimBroker fill) via to_spec()."""
    side: str            # "buy" | "sell"
    qty: float
    symbol: str
    asset_class: str = "option"
    order_type: str = "market"
    limit_price: Optional[float] = None

    def to_spec(self) -> dict:
        from hal.sensory import broker
        return broker.prepare_order(
            asset_class=self.asset_class, side=self.side, qty=self.qty,
            order_type=self.order_type, limit_price=self.limit_price,
            symbol=self.symbol,
        )
