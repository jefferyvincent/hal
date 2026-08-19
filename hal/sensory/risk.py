"""Pre-trade risk engine — portfolio- and rate-level circuit breakers.

This is the layer the per-trade rules gate (cortex.rules.check_trade) doesn't
cover. That gate judges a single trade on its own merits (reward/risk, sizing,
won't-trade list); this one enforces ceilings across the whole account and over
time, independent of any trade's quality. It exists because an LLM can drive
orders in autopilot, and the failure mode to guard against isn't a bad trade —
it's a runaway: a loop that machine-guns the broker, or a string of losers that
should have halted trading hours ago.

Borrowed in spirit from nautilus_trader's RiskEngine. Six checks, all
computable from an account snapshot + open positions (no extra quotes):

  1. Order-rate throttle   — at most N entries per rolling minute.
  2. Max open positions    — hard cap on concurrent holdings.
  3. Max gross exposure    — sum |market_value| as a multiple of equity.
  4. Daily-loss kill switch — once equity drops past the day's floor, LATCH
                              and block all new entries until manually reset.
  5. Per-underlying cap    — exposure to any ONE underlying, so five strikes on
                             the same name can't quietly become the whole book.
  6. Correlated-group cap  — exposure across a basket that moves together.
                             SPY + QQQ + IWM is one bet wearing three tickers;
                             checks 2 and 3 count it as three and wave it
                             through. Groups are a static map (_CORRELATED_
                             GROUPS) rather than a live correlation matrix,
                             which would need return history for every holding.

Exposure ceilings (3, 5, 6) additionally scale DOWN with the volatility regime
when the caller supplies a percentile: the same dollar exposure is a bigger bet
when the tape is wild, so the ceiling contracts as realized vol climbs through
its own trailing-year distribution.

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
_max_symbol_exposure_pct: float = 60.0   # ceiling per underlying; 0 disables
_max_group_exposure_pct: float = 100.0   # ceiling per correlated group; 0 disables

_THROTTLE_WINDOW_S = 60.0

# Names that move together closely enough that holding several is one position,
# not a diversified book. Deliberately small and legible — a static map beats a
# live correlation matrix here because it needs no data, never goes stale mid
# session, and is auditable by eye. A symbol may appear in more than one group;
# every group it belongs to is checked.
_CORRELATED_GROUPS: dict[str, set[str]] = {
    "us-broad-market": {"SPY", "VOO", "IVV", "QQQ", "QQQM", "IWM", "DIA", "VTI",
                        "MDY", "RSP", "SPXL", "TQQQ", "QLD", "SSO", "UPRO"},
    "semiconductors": {"NVDA", "AMD", "AVGO", "SMH", "SOXX", "SOXL", "INTC",
                       "MU", "TSM", "ARM", "QCOM", "TXN", "LRCX", "AMAT"},
    "megacap-tech": {"AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "NFLX",
                     "TSLA", "XLK", "VGT"},
}

# Volatility-regime scaling of the exposure ceilings. Keyed on where today's
# realized vol sits inside its own trailing-year distribution (0..1) — the same
# percentile cerebellum.backtest.vol_regime_percentile computes and tags trades
# with. Highest matching threshold wins.
_VOL_EXPOSURE_SCALE: tuple[tuple[float, float], ...] = (
    (0.80, 0.50),   # top-quintile vol: halve the ceilings
    (0.60, 0.75),
)

# --- Runtime state -----------------------------------------------------------
_entry_times: deque[float] = deque()      # timestamps of submitted entries
_baseline_equity: Optional[float] = None  # start-of-day equity
_baseline_day: Optional[str] = None       # local date the baseline belongs to
_killed: bool = False
_kill_reason: str = ""


def configure(max_orders_per_min: int, max_open_positions: int,
              max_gross_exposure_pct: float, daily_loss_limit_pct: float,
              max_symbol_exposure_pct: float = 60.0,
              max_group_exposure_pct: float = 100.0) -> None:
    global _max_orders_per_min, _max_open_positions
    global _max_gross_exposure_pct, _daily_loss_limit_pct
    global _max_symbol_exposure_pct, _max_group_exposure_pct
    _max_orders_per_min = max_orders_per_min
    _max_open_positions = max_open_positions
    _max_gross_exposure_pct = max_gross_exposure_pct
    _daily_loss_limit_pct = daily_loss_limit_pct
    _max_symbol_exposure_pct = max_symbol_exposure_pct
    _max_group_exposure_pct = max_group_exposure_pct


def _underlying(symbol: str) -> str:
    """Underlying root for a holding — option positions are OCC symbols, equity
    positions are already the ticker."""
    from hal.sensory.alpaca_data import occ_root
    return occ_root(symbol or "")


def _groups_for(root: str) -> list[str]:
    return [name for name, members in _CORRELATED_GROUPS.items() if root in members]


def vol_scale(vol_percentile: Optional[float]) -> float:
    """Multiplier applied to the exposure ceilings for the current vol regime.
    1.0 when no percentile is supplied, so the caller failing to read vol can
    never tighten or loosen risk silently — it just leaves the base limits."""
    if vol_percentile is None:
        return 1.0
    for threshold, scale in _VOL_EXPOSURE_SCALE:
        if vol_percentile >= threshold:
            return scale
    return 1.0


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


def check_entry(spec: dict, account: dict, positions: list[dict],
                vol_percentile: Optional[float] = None) -> dict[str, Any]:
    """Gate an OPENING order. Returns {passed, failures, tripped_now, vol_scale}.

    `tripped_now` is True only on the call that first latches the kill switch, so
    the caller can react once (e.g. drop autopilot back to confirm).

    `vol_percentile` (0..1) is where the underlying's realized vol sits in its
    trailing-year range; supplying it scales the exposure ceilings down in a
    high-vol tape. Omit it and the base limits apply unchanged.
    """
    was_killed = _killed
    _update_daily_loss(account)
    failures: list[str] = []
    now = time.time()
    _prune(now)
    scale = vol_scale(vol_percentile)

    if _killed:
        failures.append(f"kill switch active — {_kill_reason}")
        # Latched: skip the other checks, the answer is no regardless.
        return {"passed": False, "failures": failures, "vol_scale": scale,
                "tripped_now": _killed and not was_killed}

    if _max_orders_per_min > 0 and len(_entry_times) >= _max_orders_per_min:
        failures.append(
            f"order-rate throttle: {len(_entry_times)} entries in the last minute "
            f"(max {_max_orders_per_min})")

    if _max_open_positions > 0 and len(positions) >= _max_open_positions:
        failures.append(
            f"max open positions reached ({len(positions)}/{_max_open_positions})")

    equity = float(account.get("equity") or 0)
    if equity > 0:
        vol_note = "" if scale == 1.0 else f" (vol-scaled x{scale:g})"

        if _max_gross_exposure_pct > 0:
            gross = sum(abs(float(p.get("market_value") or 0)) for p in positions)
            gross_pct = gross / equity * 100.0
            limit = _max_gross_exposure_pct * scale
            if gross_pct >= limit:
                failures.append(
                    f"gross exposure {gross_pct:.0f}% of equity ≥ max "
                    f"{limit:.0f}%{vol_note}")

        # Concentration: bucket existing exposure by underlying, then by the
        # correlated groups each underlying belongs to. The order being gated is
        # counted too, via the underlying it would add to.
        by_root: dict[str, float] = {}
        for p in positions:
            root = _underlying(p.get("symbol") or "")
            if root:
                by_root[root] = by_root.get(root, 0.0) + abs(
                    float(p.get("market_value") or 0))

        new_root = _underlying(spec.get("symbol") or "")
        if _max_symbol_exposure_pct > 0 and new_root:
            limit = _max_symbol_exposure_pct * scale
            root_pct = by_root.get(new_root, 0.0) / equity * 100.0
            if root_pct >= limit:
                failures.append(
                    f"{new_root} exposure {root_pct:.0f}% of equity ≥ max "
                    f"{limit:.0f}%{vol_note}")

        if _max_group_exposure_pct > 0 and new_root:
            limit = _max_group_exposure_pct * scale
            for group in _groups_for(new_root):
                members = _CORRELATED_GROUPS[group]
                held = sum(v for r, v in by_root.items() if r in members)
                group_pct = held / equity * 100.0
                if group_pct >= limit:
                    held_names = sorted(r for r in by_root if r in members)
                    # Only call it out as a basket when it actually is one.
                    note = (f" — {', '.join(held_names)} move together"
                            if len(held_names) > 1 else "")
                    failures.append(
                        f"correlated '{group}' exposure {group_pct:.0f}% of equity "
                        f"≥ max {limit:.0f}%{vol_note}{note}")

    return {"passed": not failures, "failures": failures,
            "tripped_now": False, "vol_scale": scale}


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
            "max_symbol_exposure_pct": _max_symbol_exposure_pct,
            "max_group_exposure_pct": _max_group_exposure_pct,
        },
    }
