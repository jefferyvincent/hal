"""Scalper — an autonomous, committee-gated profit-target auto-trader.

Given a capital allotment and a dollar profit target for a period (a day or a
week), this engine scans a candidate universe, convenes HAL's trade committee on
each name, and — in autopilot ("robo trader") mode only — auto-submits equity
orders on strong verdicts (score >= threshold). It manages exits by re-running
the committee on the names it holds, and it HALTS the moment the target is
reached or the loss floor is breached.

It is deliberately NOT a tick scalper: the committee is a multi-LLM deep dive
(tens of seconds per decision), so the loop is paced by committee throughput —
a handful of high-conviction entries per session, not per second.

Design (mirrors the rest of the codebase):
  · Pure orchestration, side-effects INJECTED (like committee.decide_from_evidence
    and the execution.Execution protocol). The engine never imports `server`, so
    there is no cerebellum<-server cycle and it runs headless against SimBroker.
  · A cancellable asyncio background loop (like sensory.brackets.Monitor).
  · Every order still flows through the caller's gated place_order (rules gate →
    risk engine → confirm/autopilot submit). The scalper is a CALLER, never a
    bypass of those guards.

Three independent risk floors protect a session:
  1. `catastrophic_stop_pct` — a cheap, no-LLM per-position circuit breaker,
     checked every pass, so a single fast mover can't run while the committee is
     mid-deliberation.
  2. `loss_limit` — session-level dollar floor; breaching it flattens every
     position the session opened and halts.
  3. The caller's account-level daily-loss kill switch (sensory.risk) remains the
     outer backstop, independent of this engine.
"""
from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

# Progress callback: (step, summary, detail) -> awaitable. Mirrors committee.Emit
# so a caller (the server) can surface each pass as telemetry. None = silent.
Emit = Optional[Callable[[str, str, str], Awaitable[None]]]


@dataclass
class ScalperConfig:
    """One session's mandate. Dollar amounts are absolute (not percentages)."""
    capital: float                    # working capital the session may deploy
    profit_target: float              # $ gain that ENDS the session (stop-when-hit)
    loss_limit: float                 # $ loss that hard-halts + flattens (the floor)
    period: str = "day"               # "day" | "week" — the target window
    score_threshold: int = 70         # min committee score to auto-enter
    max_concurrent: int = 3           # positions open at once (also caps per-name size)
    poll_seconds: float = 60.0        # floor on the loop cadence (real pace = committee)
    allow_short: bool = True          # bearish bias -> sell-to-open
    catastrophic_stop_pct: float = 15.0   # per-position disaster brake (positive %)
    max_candidates_per_pass: int = 5  # cap committee runs on new names per pass
    multiplier: int = 1               # contract multiplier (1 for equities)

    def normalized(self) -> "ScalperConfig":
        self.period = (self.period or "day").strip().lower()
        if self.period not in ("day", "week"):
            self.period = "day"
        return self


# Terminal statuses (loop has stopped) vs transient ones (loop still alive).
_TERMINAL = {"target_hit", "floor_hit", "stopped", "error"}


@dataclass
class ScalperState:
    status: str = "idle"              # idle|running|market_closed|target_hit|floor_hit|stopped|error
    realized_pnl: float = 0.0         # banked P&L this period
    unrealized_pnl: float = 0.0       # open P&L on tagged positions (last pass)
    period_key: str = ""              # current period bucket (day/week key)
    passes: int = 0                   # loop iterations run
    tagged: dict[str, str] = field(default_factory=dict)  # symbol -> intended side
    last_note: str = ""               # last human-facing line, for the UI

    @property
    def total_pnl(self) -> float:
        return self.realized_pnl + self.unrealized_pnl


@dataclass
class ScalperDeps:
    """Everything the engine touches the outside world through. The server wires
    these to the real committee / gated broker; tests wire them to a SimBroker."""
    decide: Callable[[str, list[dict]], Awaitable[Optional[dict]]]
    place_order: Callable[[dict], Awaitable[dict]]
    flatten: Callable[[str], Awaitable[dict]]
    read_positions: Callable[[], Awaitable[list[dict]]]
    candidates: Callable[[], Awaitable[list[dict]]]      # [{symbol, price}]
    prepare_order: Callable[..., dict]
    market_open: Callable[[], bool]
    period_key: Callable[[], str]
    emit: Emit = None


def _bias_side(bias: str, allow_short: bool) -> Optional[str]:
    """Map a committee bias to an equity order side. Bearish shorts only when
    allowed; neutral never opens."""
    if bias == "bullish":
        return "buy"
    if bias == "bearish" and allow_short:
        return "sell"
    return None


def _opposes(side: str, bias: str) -> bool:
    """True when a fresh committee bias runs AGAINST an open position — the exit
    signal alongside an outright PASS."""
    return (side == "buy" and bias == "bearish") or (side == "sell" and bias == "bullish")


class ScalperSession:
    """One running mandate. Owns only the positions IT opened (tracked in
    state.tagged), so target/floor are measured on session P&L, never the whole
    account."""

    def __init__(self, config: ScalperConfig, deps: ScalperDeps) -> None:
        self.config = config.normalized()
        self.deps = deps
        self.state = ScalperState()
        self._task: Optional[asyncio.Task] = None
        # Last observed open P&L per tagged symbol, so a position that vanishes
        # (closed by us, a bracket, or a manual sell) is realized on the next pass.
        self._last_unreal: dict[str, float] = {}
        # True once the session has seen the market open, so a DAY session can end
        # at the closing bell (rather than idle overnight) while still allowing a
        # pre-market arm to wait for the open instead of halting immediately.
        self._market_was_open: bool = False

    # --- lifecycle ----------------------------------------------------------
    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self.state.status = "running"
        self.state.period_key = self.deps.period_key()
        self._task = asyncio.create_task(self._run())

    async def stop(self, flatten: bool = False) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        if flatten:
            await self._flatten_all()
        if self.state.status not in _TERMINAL:
            self.state.status = "stopped"

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def status(self) -> dict[str, Any]:
        s, c = self.state, self.config
        return {
            "status": s.status,
            "realized_pnl": round(s.realized_pnl, 2),
            "unrealized_pnl": round(s.unrealized_pnl, 2),
            "total_pnl": round(s.total_pnl, 2),
            "profit_target": c.profit_target,
            "loss_limit": c.loss_limit,
            "period": c.period,
            "period_key": s.period_key,
            "open_positions": dict(s.tagged),
            "passes": s.passes,
            "note": s.last_note,
        }

    # --- loop ---------------------------------------------------------------
    async def _run(self) -> None:
        while True:
            try:
                keep = await self._pass()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                await self._emit("error", "pass failed", f"{type(e).__name__}: {e}")
                keep = True  # a transient error must not kill the session
            if not keep:
                break
            await asyncio.sleep(self.config.poll_seconds)

    async def _pass(self) -> bool:
        """One loop iteration. Returns False to stop the session (terminal)."""
        self.state.passes += 1
        self._maybe_roll_period()

        if not self.deps.market_open():
            # A DAY session is done at the closing bell: once it has traded a
            # session and the market closes, halt rather than spin overnight. A
            # WEEK session spans days, so it keeps waiting for the next open.
            if self.config.period == "day" and self._market_was_open:
                self.state.last_note = "Market closed — day session ended."
                await self._emit("stopped", self.state.last_note,
                                 "Halting for the day. Open positions are left as-is.")
                self.state.status = "stopped"
                return False
            self.state.status = "market_closed"
            await self._emit("wait", "market closed", "Waiting for regular hours.")
            return True

        self._market_was_open = True
        self.state.status = "running"
        positions = {p["symbol"].upper(): p for p in await self.deps.read_positions()}
        self._refresh_pnl(positions)
        pnl = self.state.total_pnl
        await self._emit("pnl", f"P&L ${pnl:+.0f} (target ${self.config.profit_target:.0f})",
                         f"realized ${self.state.realized_pnl:+.0f} + "
                         f"unrealized ${self.state.unrealized_pnl:+.0f}")

        # 1. Loss floor — flatten everything the session opened, then halt.
        if pnl <= -self.config.loss_limit:
            self.state.last_note = f"Loss floor hit at ${pnl:+.0f} — flattened and halted."
            await self._emit("floor_hit", self.state.last_note, "")
            await self._flatten_all()
            self.state.status = "floor_hit"
            return False

        # 2. Target — stop opening; leave winners riding under their exits.
        if pnl >= self.config.profit_target:
            self.state.last_note = f"Target reached at ${pnl:+.0f} — session banked."
            await self._emit("target_hit", self.state.last_note, "")
            self.state.status = "target_hit"
            return False

        # 3. Catastrophic per-position backstop (no LLM).
        await self._backstop(positions)

        # 4. Exits: re-run the committee on each held name.
        await self._manage_exits(positions)

        # 5. Entries: only if there's room and capital.
        await self._seek_entry(positions)
        return True

    # --- P&L accounting -----------------------------------------------------
    def _pos_pnl(self, side: str, pos: dict) -> float:
        """Unrealized $ on one tagged position, broker-agnostic: computed from the
        entry we recorded and the position's current price (SimBroker doesn't
        report unrealized_pl, the live broker does — we don't rely on it)."""
        entry = float(pos.get("avg_entry_price") or 0)
        current = float(pos.get("current_price") or 0)
        qty = abs(float(pos.get("qty") or 0))
        if entry <= 0 or current <= 0 or qty <= 0:
            return 0.0
        sign = 1.0 if side == "buy" else -1.0
        return (current - entry) * sign * qty * self.config.multiplier

    def _refresh_pnl(self, positions: dict[str, dict]) -> None:
        """Recompute unrealized on still-open tags; realize any tag that vanished
        (closed by us, a bracket, or manually) using its last-seen open P&L."""
        unreal = 0.0
        for sym in list(self.state.tagged):
            side = self.state.tagged[sym]
            pos = positions.get(sym)
            if pos is None:
                # Gone — bank the last open P&L we saw and drop the tag.
                self.state.realized_pnl += self._last_unreal.pop(sym, 0.0)
                del self.state.tagged[sym]
                continue
            pl = self._pos_pnl(side, pos)
            self._last_unreal[sym] = pl
            unreal += pl
        self.state.unrealized_pnl = unreal

    # --- exits --------------------------------------------------------------
    async def _backstop(self, positions: dict[str, dict]) -> None:
        limit = self.config.catastrophic_stop_pct
        if limit <= 0:
            return
        for sym in list(self.state.tagged):
            pos = positions.get(sym)
            if not pos:
                continue
            entry = float(pos.get("avg_entry_price") or 0)
            current = float(pos.get("current_price") or 0)
            if entry <= 0 or current <= 0:
                continue
            side = self.state.tagged[sym]
            move_pct = (current - entry) / entry * 100.0 * (1 if side == "buy" else -1)
            if move_pct <= -limit:
                await self._emit("backstop", f"{sym} {move_pct:.0f}% — catastrophic stop",
                                 f"flattening {sym} at market")
                await self._flatten(sym)

    async def _manage_exits(self, positions: dict[str, dict]) -> None:
        for sym in list(self.state.tagged):
            if sym not in positions:
                continue
            side = self.state.tagged[sym]
            verdict = await self.deps.decide(sym, [positions[sym]])
            if not verdict:
                continue
            decision = verdict.get("decision")
            bias = verdict.get("bias", "neutral")
            if decision == "PASS" or _opposes(side, bias):
                why = "committee passed" if decision == "PASS" else f"bias flipped {bias}"
                await self._emit("exit", f"{sym} exit — {why}", verdict.get("thesis", ""))
                await self._flatten(sym)

    # --- entries ------------------------------------------------------------
    def _size(self, price: float) -> int:
        """Whole shares for one slot: an equal slice of capital / price, floored
        so a slot never exceeds its budget."""
        if price <= 0 or self.config.max_concurrent <= 0:
            return 0
        slot = self.config.capital / self.config.max_concurrent
        return max(0, math.floor(slot / price))

    async def _seek_entry(self, positions: dict[str, dict]) -> None:
        if len(self.state.tagged) >= self.config.max_concurrent:
            return
        cands = await self.deps.candidates()
        scanned = 0
        for c in cands:
            if scanned >= self.config.max_candidates_per_pass:
                await self._emit("scan_cap",
                                 f"scanned {scanned} candidates (cap)",
                                 "more candidates left unscanned this pass")
                break
            sym = (c.get("symbol") or "").upper()
            price = float(c.get("price") or 0)
            if not sym or sym in self.state.tagged or sym in positions:
                continue
            scanned += 1
            verdict = await self.deps.decide(sym, [])
            if not verdict:
                continue
            score = int(verdict.get("score") or 0)
            if verdict.get("decision") != "TRADE" or score < self.config.score_threshold:
                continue
            side = _bias_side(verdict.get("bias", "neutral"), self.config.allow_short)
            if side is None:
                continue
            qty = self._size(price)
            if qty < 1:
                await self._emit("skip", f"{sym} size 0", f"price ${price} exceeds slot budget")
                continue
            spec = self.deps.prepare_order(
                asset_class="equity", side=side, qty=qty, order_type="market", symbol=sym)
            res = await self.deps.place_order(spec)
            if isinstance(res, dict) and res.get("blocked"):
                await self._emit("blocked", f"{sym} entry blocked",
                                 "; ".join(res.get("failures", [])))
                continue
            self.state.tagged[sym] = side
            self.state.last_note = f"Opened {side} {qty} {sym} (score {score})."
            await self._emit("entry", self.state.last_note, verdict.get("thesis", ""))
            return  # one entry per pass — respects the risk engine's rate throttle

    # --- helpers ------------------------------------------------------------
    async def _flatten(self, symbol: str) -> None:
        try:
            await self.deps.flatten(symbol)
        except Exception as e:
            await self._emit("error", f"{symbol} flatten failed", f"{type(e).__name__}: {e}")
            return
        # Bank whatever open P&L we last saw, drop the tag, and re-derive the
        # open total from what's left so realized/unrealized never double-count
        # (matters on a terminal flatten, where no later pass would correct it).
        self.state.realized_pnl += self._last_unreal.pop(symbol, 0.0)
        self.state.tagged.pop(symbol, None)
        self.state.unrealized_pnl = sum(self._last_unreal.values())

    async def _flatten_all(self) -> None:
        for sym in list(self.state.tagged):
            await self._flatten(sym)

    def _maybe_roll_period(self) -> None:
        """When the day/week bucket changes, re-baseline: banked and open P&L reset
        so the target/floor apply to the new window."""
        key = self.deps.period_key()
        if key != self.state.period_key:
            self.state.period_key = key
            self.state.realized_pnl = 0.0
            self.state.unrealized_pnl = 0.0
            self._last_unreal.clear()

    async def _emit(self, step: str, summary: str, detail: str) -> None:
        self.state.last_note = summary
        if not self.deps.emit:
            return
        try:
            await self.deps.emit(step, summary, detail)
        except Exception as e:
            print(f"[scalper] emit failed ({step}): {e}")
