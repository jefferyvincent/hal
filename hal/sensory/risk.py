"""Pre-trade risk engine — portfolio- and rate-level circuit breakers.

This is the layer the per-trade rules gate (cortex.rules.check_trade) doesn't
cover. That gate judges a single trade on its own merits (reward/risk, sizing,
won't-trade list); this one enforces ceilings across the whole account and over
time, independent of any trade's quality. It exists because an LLM can drive
orders in autopilot, and the failure mode to guard against isn't a bad trade —
it's a runaway: a loop that machine-guns the broker, or a string of losers that
should have halted trading hours ago.

Borrowed in spirit from nautilus_trader's RiskEngine. Four checks, all
computable from an account snapshot + open positions (no extra quotes):

  1. Order-rate throttle   — at most N entries per rolling minute.
  2. Max open positions    — hard cap on concurrent holdings.
  3. Max gross exposure    — sum |market_value| as a multiple of equity.
  4. Daily-loss kill switch — once equity drops past the day's floor, LATCH
                              and block all new entries until manually reset.

Scope: ENTRIES only. Exits/closes (close_position, the synthetic-bracket
auto-close, the panel Sell) must never be blocked — when the kill switch is
tripped you still want to be able to de-risk. The caller applies this gate on
the opening path only.

Module-level state (counters, baseline, latch) is process-wide, matching how
the broker module holds its own runtime mode. No I/O here and no broker import:
the caller passes the account + positions it already fetched.
"""
from __future__ import annotations

import time
from collections import deque
from typing import Any, Optional

# --- Config (set from .env via configure(); see brainstem.config) ------------
_max_orders_per_min: int = 6        # 0 disables the throttle
_max_open_positions: int = 20       # 0 disables the count cap
_max_gross_exposure_pct: float = 200.0   # gross notional ceiling vs equity; 0 disables
_daily_loss_limit_pct: float = 10.0      # day's drawdown floor vs start equity; 0 disables

_THROTTLE_WINDOW_S = 60.0

# --- Runtime state -----------------------------------------------------------
_entry_times: deque[float] = deque()      # timestamps of submitted entries
_baseline_equity: Optional[float] = None  # start-of-day equity
_baseline_day: Optional[str] = None       # local date the baseline belongs to
_killed: bool = False
_kill_reason: str = ""


def configure(max_orders_per_min: int, max_open_positions: int,
              max_gross_exposure_pct: float, daily_loss_limit_pct: float) -> None:
    global _max_orders_per_min, _max_open_positions
    global _max_gross_exposure_pct, _daily_loss_limit_pct
    _max_orders_per_min = max_orders_per_min
    _max_open_positions = max_open_positions
    _max_gross_exposure_pct = max_gross_exposure_pct
    _daily_loss_limit_pct = daily_loss_limit_pct


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.localtime())


def _prune(now: float) -> None:
    cutoff = now - _THROTTLE_WINDOW_S
    while _entry_times and _entry_times[0] < cutoff:
        _entry_times.popleft()


def _update_daily_loss(account: dict) -> None:
    """Refresh the day's equity baseline and latch the kill switch if equity has
    fallen past the floor. Baseline resets at the first check of a new day."""
    global _baseline_equity, _baseline_day, _killed, _kill_reason
    equity = float(account.get("equity") or 0)
    if equity <= 0:
        return
    today = _today()
    if _baseline_day != today:
        # New trading day: re-baseline and clear a loss-triggered latch. (A latch
        # set by something other than daily loss would also clear here, which is
        # fine — a fresh day is a clean slate.)
        _baseline_day = today
        _baseline_equity = equity
        _killed = False
        _kill_reason = ""
        return
    if _daily_loss_limit_pct <= 0 or _baseline_equity is None:
        return
    floor = _baseline_equity * (1 - _daily_loss_limit_pct / 100.0)
    if equity <= floor and not _killed:
        loss_pct = (1 - equity / _baseline_equity) * 100.0
        _killed = True
        _kill_reason = (
            f"daily loss {loss_pct:.1f}% hit the {_daily_loss_limit_pct:g}% floor "
            f"(equity ${equity:,.0f} vs ${_baseline_equity:,.0f} at open)"
        )


def check_entry(spec: dict, account: dict, positions: list[dict]) -> dict[str, Any]:
    """Gate an OPENING order. Returns {passed, failures, tripped_now}.

    `tripped_now` is True only on the call that first latches the kill switch, so
    the caller can react once (e.g. drop autopilot back to confirm)."""
    was_killed = _killed
    _update_daily_loss(account)
    failures: list[str] = []
    now = time.time()
    _prune(now)

    if _killed:
        failures.append(f"kill switch active — {_kill_reason}")
        # Latched: skip the other checks, the answer is no regardless.
        return {"passed": False, "failures": failures,
                "tripped_now": _killed and not was_killed}

    if _max_orders_per_min > 0 and len(_entry_times) >= _max_orders_per_min:
        failures.append(
            f"order-rate throttle: {len(_entry_times)} entries in the last minute "
            f"(max {_max_orders_per_min})")

    if _max_open_positions > 0 and len(positions) >= _max_open_positions:
        failures.append(
            f"max open positions reached ({len(positions)}/{_max_open_positions})")

    equity = float(account.get("equity") or 0)
    if _max_gross_exposure_pct > 0 and equity > 0:
        gross = sum(abs(float(p.get("market_value") or 0)) for p in positions)
        gross_pct = gross / equity * 100.0
        if gross_pct >= _max_gross_exposure_pct:
            failures.append(
                f"gross exposure {gross_pct:.0f}% of equity ≥ max "
                f"{_max_gross_exposure_pct:g}%")

    return {"passed": not failures, "failures": failures, "tripped_now": False}


def record_entry() -> None:
    """Stamp a successfully submitted entry so the throttle can count it."""
    _entry_times.append(time.time())


def reset_kill_switch() -> None:
    """Manually clear the latched daily-loss halt (a human override)."""
    global _killed, _kill_reason
    _killed = False
    _kill_reason = ""


def status() -> dict[str, Any]:
    """Snapshot for the UI / telemetry."""
    _prune(time.time())
    return {
        "killed": _killed,
        "kill_reason": _kill_reason,
        "orders_last_min": len(_entry_times),
        "baseline_equity": _baseline_equity,
        "limits": {
            "max_orders_per_min": _max_orders_per_min,
            "max_open_positions": _max_open_positions,
            "max_gross_exposure_pct": _max_gross_exposure_pct,
            "daily_loss_limit_pct": _daily_loss_limit_pct,
        },
    }
