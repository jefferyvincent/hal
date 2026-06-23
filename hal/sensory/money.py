"""Fixed-precision money/price/qty helpers.

Borrowed in spirit from nautilus_trader's value types: prices and money are never
carried as raw floats through arithmetic, because float drift silently corrupts
P&L comparisons and — more concretely here — makes Alpaca reject an order with a
sub-penny or off-tick limit price (HTTP 422). We don't need nautilus's
integer-backed types; standardizing on Decimal at the order-construction and
exit-math boundary removes the same bug class with a fraction of the surface.

Tick rules match the venues HAL trades:
  · equities      — $0.01 (penny) above $1.00.
  · options       — $0.01 below $3.00, $0.05 at/above $3.00 (standard increments).
Both round HALF_UP so a computed limit never lands a fraction of a cent off and
bounces.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

_CENT = Decimal("0.01")
_NICKEL = Decimal("0.05")


def D(value: Any) -> Decimal:
    """Coerce to Decimal via str() so we never inherit binary-float noise
    (Decimal(0.1) != Decimal('0.1')). None/'' raise — callers gate those."""
    return Decimal(str(value))


def _quantize(value: Decimal, tick: Decimal) -> Decimal:
    return (value / tick).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * tick


def round_price(value: Any, asset_class: str = "equity") -> Decimal:
    """Round a price to the venue's tick for `asset_class` ('equity'|'option')."""
    px = D(value)
    if asset_class == "option":
        tick = _CENT if px < Decimal("3") else _NICKEL
    else:
        tick = _CENT
    return _quantize(px, tick)


def round_qty(value: Any) -> Decimal:
    """Quantize an order quantity. HAL trades whole shares/contracts, so this
    truncates to an integer-valued Decimal (fractional shares aren't used)."""
    return D(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def as_float(value: Decimal) -> float:
    """Cross back to float only at the wire/JSON boundary, where precision no
    longer matters and the SDK/serializer wants a primitive."""
    return float(value)
