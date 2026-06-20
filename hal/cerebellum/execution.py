"""Shared execution contract for live and simulated order flow.

nautilus_trader's defining guarantee is that a strategy runs through the SAME
code path in backtest and live — a green backtest then actually validates what
you run. HAL isn't there wholesale, but this module pins the seam where it
matters most: both the live broker and the backtest accept the IDENTICAL order
spec (sensory.broker.prepare_order's output) and return a fill. An order built
for a backtest is constructed exactly as it would be for Alpaca.

  · Execution   — the protocol both sides satisfy: submit_order(spec) + positions().
  · SimBroker   — fills specs against supplied historical prices, tracking signed
                  positions, commissions, and realized P&L. The backtest's fill
                  engine.
  · LiveExecution — thin named adapter over sensory.broker, so the contract is
                  explicit (the broker already satisfies it structurally).

Live submits at market, so it takes no price; SimBroker is told the bar price via
set_price() before each submit, keeping submit_order(spec) call-compatible on
both sides.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Execution(Protocol):
    """The order-flow surface a strategy targets, live or simulated."""

    def submit_order(self, spec: dict) -> dict:
        """Send a prepared order spec; return a fill/order dict."""
        ...

    def positions(self) -> list[dict]:
        """Currently open positions."""
        ...


class LiveExecution:
    """Adapt sensory.broker to the Execution protocol (broker imported lazily so
    the simulation path never requires the Alpaca SDK)."""

    def submit_order(self, spec: dict) -> dict:
        from hal.sensory import broker
        return broker.submit_order(spec)

    def positions(self) -> list[dict]:
        from hal.sensory import broker
        return broker.list_positions()


class SimBroker:
    """In-memory fill engine. Accepts the same order specs as the live broker and
    fills them at the price last set for the symbol (the historical bar). Tracks a
    signed position per symbol with average entry, and accrues realized P&L net of
    commissions on every closing/reducing fill."""

    def __init__(self, multiplier: int = 100, commission_per_contract: float = 0.0) -> None:
        self.multiplier = multiplier
        self.commission = commission_per_contract
        self.fills: list[dict] = []
        self.realized_pnl: float = 0.0
        self._price: dict[str, float] = {}
        # symbol -> {"qty": signed float, "avg": avg entry price}
        self._pos: dict[str, dict[str, float]] = {}

    def set_price(self, symbol: str, price: float) -> None:
        """Set the fill price for `symbol` (the current bar's premium/close)."""
        self._price[symbol.upper()] = float(price)

    def submit_order(self, spec: dict) -> dict:
        sym = (spec["symbol"] or "").upper()
        px = self._price.get(sym)
        if px is None:
            raise ValueError(f"no sim price set for {sym}; call set_price first")
        qty = float(spec["qty"])
        signed = qty if spec["side"] == "buy" else -qty
        commission = self.commission * qty

        pos = self._pos.get(sym, {"qty": 0.0, "avg": 0.0})
        prev_qty, avg = pos["qty"], pos["avg"]

        gross = 0.0
        # If this fill reduces the existing position, realize P&L on the closed part.
        if prev_qty != 0 and (signed > 0) != (prev_qty > 0):
            closed = min(qty, abs(prev_qty))
            direction = 1.0 if prev_qty > 0 else -1.0
            gross = (px - avg) * direction * closed * self.multiplier
        self.realized_pnl += gross - commission

        new_qty = prev_qty + signed
        if prev_qty == 0 or (signed > 0) == (prev_qty > 0):
            # Opening or adding: blend the average entry.
            avg = (avg * abs(prev_qty) + px * qty) / (abs(prev_qty) + qty)
        if abs(new_qty) < 1e-9:
            self._pos.pop(sym, None)
        else:
            self._pos[sym] = {"qty": new_qty, "avg": avg}

        fill = {
            "symbol": sym,
            "side": spec["side"],
            "qty": qty,
            "price": round(px, 4),
            "commission": round(commission, 4),
            "realized_pnl": round(gross - commission, 2),
            "status": "filled",
        }
        self.fills.append(fill)
        return fill

    def positions(self) -> list[dict]:
        out = []
        for sym, p in self._pos.items():
            qty = p["qty"]
            mark = self._price.get(sym, p["avg"])
            out.append({
                "symbol": sym,
                "qty": str(qty),
                "side": "long" if qty > 0 else "short",
                "avg_entry_price": round(p["avg"], 4),
                "current_price": round(mark, 4),
                "market_value": round(abs(qty) * mark * self.multiplier, 2),
            })
        return out
