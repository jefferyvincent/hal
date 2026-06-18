"""Alpaca brokerage: account, positions, orders, and a confirm/autopilot gate.

HAL places orders directly through Alpaca (equities + single-leg options) using
the official alpaca-py SDK. Paper vs live is set by ALPACA_PAPER (paper by
default) — the SDK selects the API host from that flag, so nothing can touch
real money until it's deliberately set false.

Two safety layers sit in front of every order:
  1. The vault trading-rules gate (cortex.rules.check_trade), applied by the
     caller before an order is staged or submitted.
  2. A runtime mode: "confirm" (default) stages the order and waits for an
     explicit confirmation; "autopilot" submits immediately.

The SDK is synchronous; the async server calls these helpers via
asyncio.to_thread so the event loop never blocks on a broker round-trip.
"""
from __future__ import annotations

import time
import uuid
from typing import Any, Optional

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce
from alpaca.trading.requests import (
    GetOrdersRequest,
    LimitOrderRequest,
    MarketOrderRequest,
)

from hal.hippocampus import persistence

# --- Module state -----------------------------------------------------------
_client: Optional[TradingClient] = None
_paper: bool = True
_autopilot: bool = False

# Orders staged in confirm mode, keyed by an 8-char token. In-memory only — a
# pending (un-confirmed) order is intentionally NOT persisted across a restart.
_pending: dict[str, dict[str, Any]] = {}


def configure(api_key: str, secret_key: str, paper: bool, autopilot: bool) -> None:
    global _client, _paper, _autopilot
    _paper = paper
    _autopilot = autopilot
    _client = (
        TradingClient(api_key, secret_key, paper=paper)
        if api_key and secret_key
        else None
    )


def is_ready() -> bool:
    """True once credentials are configured and the client is live."""
    return _client is not None


def is_paper() -> bool:
    return _paper


# --- Runtime mode (confirm / autopilot) -------------------------------------
def get_mode() -> str:
    return "autopilot" if _autopilot else "confirm"


def set_mode(mode: str) -> str:
    """Flip between 'confirm' (stage + wait) and 'autopilot' (submit now)."""
    global _autopilot
    _autopilot = mode.strip().lower() == "autopilot"
    return get_mode()


# --- Helpers ----------------------------------------------------------------
def _enum(v: Any) -> Any:
    """Unwrap an alpaca enum to its string value; pass scalars through."""
    return getattr(v, "value", v) if v is not None else None


def _f(v: Any) -> Optional[float]:
    return float(v) if v not in (None, "") else None


def build_option_symbol(underlying: str, expiration: str, opt_type: str, strike: float) -> str:
    """OCC-style option symbol Alpaca expects, e.g. AAPL241220C00150000.

    expiration is 'YYYY-MM-DD'; opt_type is 'call'/'put' (only the first letter
    matters); strike is in dollars and encoded as strike*1000 padded to 8 digits.
    """
    u = underlying.upper().strip()
    y, m, d = expiration.split("-")
    cp = "C" if opt_type.lower().startswith("c") else "P"
    strike_milli = int(round(float(strike) * 1000))
    return f"{u}{y[2:]}{m}{d}{cp}{strike_milli:08d}"


def _order_to_dict(o: Any) -> dict:
    return {
        "id": str(o.id),
        "client_order_id": o.client_order_id,
        "symbol": o.symbol,
        "asset_class": _enum(getattr(o, "asset_class", None)),
        "qty": str(o.qty) if o.qty is not None else None,
        "side": _enum(o.side),
        "type": _enum(getattr(o, "order_type", None) or getattr(o, "type", None)),
        "time_in_force": _enum(o.time_in_force),
        "status": _enum(o.status),
        "limit_price": _f(o.limit_price),
        "filled_qty": str(o.filled_qty) if o.filled_qty is not None else None,
        "filled_avg_price": _f(o.filled_avg_price),
        "submitted_at": str(o.submitted_at) if o.submitted_at else None,
    }


# --- Reads ------------------------------------------------------------------
def get_account() -> dict:
    a = _client.get_account()
    return {
        "account_number": a.account_number,
        "status": _enum(a.status),
        "currency": a.currency,
        "cash": _f(a.cash),
        "equity": _f(a.equity),
        "buying_power": _f(a.buying_power),
        "options_buying_power": _f(getattr(a, "options_buying_power", None)),
        "options_trading_level": getattr(a, "options_trading_level", None),
        "pattern_day_trader": a.pattern_day_trader,
        "paper": _paper,
    }


def list_positions() -> list[dict]:
    out = []
    for p in _client.get_all_positions():
        out.append({
            "symbol": p.symbol,
            "asset_class": _enum(p.asset_class),
            "qty": str(p.qty),
            "side": _enum(p.side),
            "avg_entry_price": _f(p.avg_entry_price),
            "current_price": _f(p.current_price),
            "market_value": _f(p.market_value),
            "unrealized_pl": _f(p.unrealized_pl),
            "unrealized_plpc": _f(p.unrealized_plpc),
        })
    return out


def list_orders(status: str = "open", limit: int = 20) -> list[dict]:
    try:
        qstatus = QueryOrderStatus(status.lower())
    except ValueError:
        qstatus = QueryOrderStatus.OPEN
    req = GetOrdersRequest(status=qstatus, limit=limit)
    return [_order_to_dict(o) for o in _client.get_orders(filter=req)]


def cancel_order(order_id: str) -> dict:
    _client.cancel_order_by_id(order_id)
    return {"canceled": order_id}


# --- Order construction + submission ----------------------------------------
def prepare_order(
    asset_class: str = "equity",
    side: str = "",
    qty: float = 0,
    order_type: str = "market",
    limit_price: Optional[float] = None,
    time_in_force: Optional[str] = None,
    symbol: Optional[str] = None,
    underlying: Optional[str] = None,
    expiration: Optional[str] = None,
    option_type: Optional[str] = None,
    strike: Optional[float] = None,
) -> dict:
    """Validate inputs and return a normalized order spec (no I/O).

    For options, pass either an explicit OCC `symbol` or the
    underlying+expiration+option_type+strike to build one.
    """
    asset_class = (asset_class or "equity").lower()
    side = (side or "").lower()
    if side not in ("buy", "sell"):
        raise ValueError("side must be 'buy' or 'sell'")
    order_type = (order_type or "market").lower()
    if order_type not in ("market", "limit"):
        raise ValueError("order_type must be 'market' or 'limit'")
    if order_type == "limit" and limit_price is None:
        raise ValueError("limit_price is required for a limit order")
    qty = float(qty)
    if qty <= 0:
        raise ValueError("qty must be a positive number")

    if asset_class == "option":
        if not symbol:
            if not (underlying and expiration and option_type and strike is not None):
                raise ValueError(
                    "option order needs an OCC symbol, or "
                    "underlying + expiration + option_type + strike"
                )
            symbol = build_option_symbol(underlying, expiration, option_type, strike)
        # Alpaca only accepts day-length time-in-force for options.
        tif = (time_in_force or "day").lower()
    else:
        asset_class = "equity"
        if not symbol:
            raise ValueError("equity order requires a symbol")
        symbol = symbol.upper().strip()
        tif = (time_in_force or "day").lower()

    return {
        "asset_class": asset_class,
        "symbol": symbol,
        "side": side,
        "qty": qty,
        "type": order_type,
        "limit_price": float(limit_price) if limit_price is not None else None,
        "time_in_force": tif,
    }


def build_close_spec(symbol: str) -> dict:
    """Return an offsetting order spec that flattens the position in `symbol`.

    Raises ValueError if there's no open position. Shared by the gated close
    (HAL's close_position tool) and the immediate manual close below, so both
    produce identical orders.
    """
    symbol = symbol.upper().strip()
    pos = next((p for p in list_positions() if p["symbol"].upper() == symbol), None)
    if pos is None:
        raise ValueError(f"no open position in {symbol}")
    asset_class = "option" if "option" in (pos["asset_class"] or "") else "equity"
    return prepare_order(
        asset_class=asset_class,
        side="sell" if pos["side"] == "long" else "buy",
        qty=abs(float(pos["qty"])),
        order_type="market",
        symbol=symbol,
    )


def close_position_now(symbol: str) -> dict:
    """Immediately submit an offsetting market order to flatten `symbol`,
    bypassing the confirm/autopilot gate. This backs the manual UI override —
    the human clicking "close" IS the authorization, so there's nothing to stage.
    """
    return submit_order(build_close_spec(symbol))


def summarize_order(spec: dict) -> str:
    """One-line human-readable preview of a prepared order."""
    venue = "PAPER" if _paper else "LIVE"
    unit = "contract(s)" if spec["asset_class"] == "option" else "share(s)"
    q = spec["qty"]
    q_s = str(int(q)) if float(q).is_integer() else str(q)
    px = f"limit {spec['limit_price']:.2f}" if spec["type"] == "limit" else "market"
    return (
        f"[{venue}] {spec['side'].upper()} {q_s} {unit} of {spec['symbol']} "
        f"({px}, {spec['time_in_force']})"
    )


def _build_request(spec: dict):
    common = dict(
        symbol=spec["symbol"],
        qty=spec["qty"],
        side=OrderSide(spec["side"]),
        time_in_force=TimeInForce(spec["time_in_force"]),
    )
    if spec["type"] == "limit":
        return LimitOrderRequest(limit_price=spec["limit_price"], **common)
    return MarketOrderRequest(**common)


def submit_order(spec: dict) -> dict:
    """Send a prepared spec to Alpaca and log the result. Submits unconditionally
    — the confirm/autopilot decision is the caller's; this is the wire call."""
    if _client is None:
        raise RuntimeError(
            "Alpaca is not configured — set ALPACA_API_KEY / ALPACA_SECRET_KEY in .env"
        )
    order = _client.submit_order(order_data=_build_request(spec))
    result = _order_to_dict(order)
    persistence.log_broker_order(spec, result, mode=get_mode(), paper=_paper)
    return result


# --- Confirm-mode staging ---------------------------------------------------
def stage_order(spec: dict, summary: str) -> str:
    """Hold a prepared order pending an explicit confirm; return its token."""
    token = uuid.uuid4().hex[:8]
    _pending[token] = {"spec": spec, "summary": summary, "staged_at": time.time()}
    return token


def _resolve_token(token: Optional[str]) -> Optional[str]:
    """Map a token to a pending order; if omitted and exactly one is pending,
    use that one (the common 'confirm the order I just proposed' case)."""
    if token:
        return token if token in _pending else None
    return next(iter(_pending)) if len(_pending) == 1 else None


def list_pending() -> list[dict]:
    return [{"token": t, "summary": p["summary"]} for t, p in _pending.items()]


def get_pending(token: Optional[str] = None) -> Optional[dict]:
    t = _resolve_token(token)
    return _pending.get(t) if t else None


def discard_pending(token: Optional[str] = None) -> bool:
    t = _resolve_token(token)
    if t:
        _pending.pop(t, None)
        return True
    return False


def submit_pending(token: Optional[str] = None) -> dict:
    t = _resolve_token(token)
    if not t:
        raise ValueError(
            "no matching pending order to confirm"
            + (f" (token {token})" if token else "")
        )
    spec = _pending.pop(t)["spec"]
    return submit_order(spec)
