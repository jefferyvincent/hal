"""HAL-managed exits ("synthetic brackets") for option positions.

Alpaca won't hold stop / take-profit orders on options, so HAL watches the
positions itself: a background loop polls each managed position's premium and,
when it hits the stop or take-profit level, submits a MARKET order to flatten
it. Active only while HAL is running — a catch-up pass on start closes anything
already past its level, and a position closed by any other means (the panel
Sell button, manual, expiry) is reconciled away on the next pass.

This is intentionally decoupled from the price-alert engine: the alerts give
the spoken heads-up in real time; this loop is the actuator, using Alpaca's own
position price as the source of truth so it can't fire on a stale tick.
"""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Optional

from hal.cerebellum import strategy
from hal.cerebellum.execution import LiveExecution
from hal.hippocampus import persistence
from hal.sensory import broker

# How often to re-check managed positions against their exit levels.
POLL_SECONDS = 30.0

# The live order surface (Execution protocol). Exits go through this so they
# share the exact submit path the backtest's SimBroker stands in for.
_live = LiveExecution()

# Announce callback: (message) -> awaitable. The server wires this to the alert
# delivery path so a fired exit is spoken. The market sell happens regardless.
Announce = Callable[[str], Awaitable[None]]


def arm(symbol: str, underlying: str, qty, stop_price: float, tp_price: float) -> None:
    """Register a managed exit for an option position HAL just opened."""
    persistence.arm_managed_exit(symbol, underlying, qty, stop_price, tp_price)
    print(f"[brackets] armed {symbol}: stop ${stop_price:.2f} / tp ${tp_price:.2f}")


def disarm(key: str) -> None:
    """Drop a managed exit by OCC symbol or underlying (e.g. on a panel close)."""
    persistence.disarm_managed_exit(key)


async def check_once(announce: Optional[Announce] = None) -> None:
    """One reconciliation pass: fire any managed exit that's hit its level, and
    drop exits whose position is gone. Safe to call repeatedly; never raises."""
    exits = persistence.list_managed_exits()
    if not exits or not broker.is_ready():
        return
    try:
        positions = await asyncio.to_thread(broker.list_positions)
    except Exception as e:
        print(f"[brackets] positions read failed: {e}")
        return
    by_symbol = {(p.get("symbol") or "").upper(): p for p in positions}
    for ex in exits:
        sym = (ex.get("symbol") or "").upper()
        pos = by_symbol.get(sym)
        if pos is None:
            # Closed elsewhere (panel Sell, manual, expiry) — stop managing it.
            persistence.disarm_managed_exit(sym)
            print(f"[brackets] {sym} position gone; disarmed")
            continue
        current = pos.get("current_price") or 0.0
        if current <= 0:
            # No usable quote this pass — never fire on a missing price.
            continue
        kind = strategy.exit_signal(current, ex.get("stop_price") or 0, ex.get("tp_price") or 0)
        if not kind:
            continue
        try:
            order = await asyncio.to_thread(
                lambda: _live.submit_order(broker.build_close_spec(sym)))
        except Exception as e:
            print(f"[brackets] {sym} auto-close failed: {e}")
            continue
        persistence.disarm_managed_exit(sym)
        label = ex.get("underlying") or sym
        level = ex["stop_price"] if kind == "stop" else ex["tp_price"]
        verb = "Stopped out of" if kind == "stop" else "Took profit on"
        msg = (f"{verb} {label} — premium hit ${current:.2f} "
               f"(${level:.2f} {kind.replace('_', ' ')}); sold at market.")
        oid = order.get("id") if isinstance(order, dict) else order
        print(f"[brackets] {msg} order={oid}")
        if announce:
            try:
                await announce(msg)
            except Exception as e:
                print(f"[brackets] announce failed: {e}")


class Monitor:
    """Background loop that runs check_once on an interval. The first pass on
    start is the catch-up (close anything already past its level)."""

    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._announce: Optional[Announce] = None

    def set_announce(self, fn: Announce) -> None:
        self._announce = fn

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if not self._task:
            return
        self._task.cancel()
        try:
            await self._task
        except (asyncio.CancelledError, Exception):
            pass
        self._task = None

    async def _loop(self) -> None:
        while True:
            try:
                await check_once(self._announce)
            except Exception as e:
                print(f"[brackets] check loop error: {e}")
            await asyncio.sleep(POLL_SECONDS)


monitor = Monitor()
