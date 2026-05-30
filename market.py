"""Real-time market data subscriptions and alert delivery for HAL.

Owns a single outbound WebSocket connection to Massive's options
feed (wss://socket.massive.com/options). Reads ws_subscriptions and
alert_rules from the same SQLite DB the conversation history lives in
(see server._init_db), evaluates rules in-process as ticks arrive,
and pushes fired alerts to active voice sessions via ClientRegistry.

Connection model: Polygon-style — one socket, JSON action messages.
Auth: {"action":"auth","params":"<key>"}. Subscribe params are
comma-separated topics of form "<channel>.<symbol>" where channel is
T (trades), Q (quotes), A (per-second aggregates), AM (per-minute
aggregates), or FMV (fair market value), and symbol can be '*',
'O:UNDERLYING*', or a specific 'O:SPY261219C00500000'.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from websockets.asyncio.client import connect as ws_connect
from websockets.exceptions import ConnectionClosed


# Filled by server.configure_market() at boot; avoids a circular import.
DB_PATH: Optional[Path] = None
API_KEY: str = ""
FEED_HOST = "socket.massive.com"
MARKET_PATH = "options"


def configure(db_path: Path, api_key: str) -> None:
    global DB_PATH, API_KEY
    DB_PATH = db_path
    API_KEY = api_key


# --- DB helpers ------------------------------------------------------------

def _db() -> sqlite3.Connection:
    if DB_PATH is None:
        raise RuntimeError("market.configure() not called")
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def list_subscriptions_db(active_only: bool = True) -> list[dict]:
    with _db() as conn:
        q = "SELECT id, channel, symbol, note, created_at, active FROM ws_subscriptions"
        if active_only:
            q += " WHERE active = 1"
        q += " ORDER BY created_at DESC"
        return [dict(r) for r in conn.execute(q).fetchall()]


def insert_subscription(channel: str, symbol: str, note: str = "") -> int:
    now = time.time()
    with _db() as conn:
        cur = conn.execute(
            "INSERT INTO ws_subscriptions(channel, symbol, note, created_at, active) "
            "VALUES (?,?,?,?,1) "
            "ON CONFLICT(channel, symbol) DO UPDATE SET active=1, note=excluded.note "
            "RETURNING id",
            (channel, symbol, note, now),
        )
        return cur.fetchone()[0]


def deactivate_subscription(sub_id: int) -> bool:
    with _db() as conn:
        cur = conn.execute("UPDATE ws_subscriptions SET active=0 WHERE id=?", (sub_id,))
        return cur.rowcount > 0


def list_rules_with_subs(active_only: bool = True) -> list[dict]:
    with _db() as conn:
        q = (
            "SELECT r.id AS rule_id, r.subscription_id, r.rule_type, r.config, "
            "       r.note AS rule_note, r.active AS rule_active, "
            "       r.triggered_count, r.last_triggered_at, r.cooldown_seconds, "
            "       s.channel, s.symbol, s.active AS sub_active "
            "FROM alert_rules r "
            "JOIN ws_subscriptions s ON s.id = r.subscription_id"
        )
        if active_only:
            q += " WHERE r.active = 1 AND s.active = 1"
        return [dict(r) for r in conn.execute(q).fetchall()]


def list_rules_for_sub(sub_id: int) -> list[dict]:
    with _db() as conn:
        rows = conn.execute(
            "SELECT id, rule_type, config, note, active, triggered_count, "
            "       last_triggered_at, cooldown_seconds, created_at "
            "FROM alert_rules WHERE subscription_id = ? ORDER BY created_at DESC",
            (sub_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def insert_rule(
    sub_id: int,
    rule_type: str,
    config: dict,
    note: str = "",
    cooldown_seconds: float = 60.0,
) -> int:
    now = time.time()
    with _db() as conn:
        cur = conn.execute(
            "INSERT INTO alert_rules(subscription_id, rule_type, config, note, "
            "cooldown_seconds, created_at) VALUES (?,?,?,?,?,?) RETURNING id",
            (sub_id, rule_type, json.dumps(config), note, cooldown_seconds, now),
        )
        return cur.fetchone()[0]


def deactivate_rule(rule_id: int) -> bool:
    with _db() as conn:
        cur = conn.execute("UPDATE alert_rules SET active=0 WHERE id=?", (rule_id,))
        return cur.rowcount > 0


def record_alert(rule_id: int, payload: dict, message: str) -> int:
    now = time.time()
    with _db() as conn:
        cur = conn.execute(
            "INSERT INTO alert_events(rule_id, fired_at, payload, message) "
            "VALUES (?,?,?,?) RETURNING id",
            (rule_id, now, json.dumps(payload), message),
        )
        event_id = cur.fetchone()[0]
        conn.execute(
            "UPDATE alert_rules SET triggered_count = triggered_count + 1, "
            "last_triggered_at = ? WHERE id = ?",
            (now, rule_id),
        )
        return event_id


def mark_alert_spoken(event_id: int) -> None:
    with _db() as conn:
        conn.execute("UPDATE alert_events SET spoken=1 WHERE id=?", (event_id,))


def list_alert_events(limit: int = 20) -> list[dict]:
    with _db() as conn:
        rows = conn.execute(
            "SELECT e.id, e.rule_id, e.fired_at, e.message, e.spoken, "
            "       r.subscription_id, s.channel, s.symbol "
            "FROM alert_events e "
            "JOIN alert_rules r ON r.id = e.rule_id "
            "JOIN ws_subscriptions s ON s.id = r.subscription_id "
            "ORDER BY e.fired_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def list_unspoken_alerts(limit: int = 20) -> list[dict]:
    """Alerts that fired but were never announced (no app session was connected
    when they broadcast). Oldest first so a replay reads in chronological order."""
    with _db() as conn:
        rows = conn.execute(
            "SELECT e.id, e.rule_id, e.fired_at, e.message, s.channel, s.symbol "
            "FROM alert_events e "
            "JOIN alert_rules r ON r.id = e.rule_id "
            "JOIN ws_subscriptions s ON s.id = r.subscription_id "
            "WHERE e.spoken = 0 "
            "ORDER BY e.fired_at ASC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


# --- Rule evaluation -------------------------------------------------------

VALID_CHANNELS = {"T", "Q", "A", "AM", "FMV"}
VALID_RULE_TYPES = {"pct_move", "price_cross", "volume"}


@dataclass
class RuleState:
    rule_id: int
    sub_id: int
    channel: str
    symbol_pattern: str
    rule_type: str
    config: dict
    cooldown_seconds: float
    last_fired_at: float = 0.0
    baseline_price: Optional[float] = None
    last_price: Optional[float] = None


def _msg_price(msg: dict) -> Optional[float]:
    ev = msg.get("ev")
    if ev == "T":
        return msg.get("p")
    if ev == "Q":
        bp, ap = msg.get("bp"), msg.get("ap")
        if bp is None or ap is None:
            return None
        return (bp + ap) / 2.0
    if ev in ("A", "AM", "FMV"):
        return msg.get("c")
    return None


def _symbol_matches(pattern: str, symbol: str) -> bool:
    """Massive subscribe wildcards: '*' = all, 'O:SPY*' = all SPY options,
    or exact match."""
    if pattern == "*" or pattern == symbol:
        return True
    if pattern.endswith("*"):
        return symbol.startswith(pattern[:-1])
    return False


def evaluate_rule(state: RuleState, msg: dict) -> Optional[str]:
    """Returns a human-readable alert string if the rule fires, else None.
    Mutates state.last_fired_at and per-rule-type state on fire."""
    now = time.time()
    if now - state.last_fired_at < state.cooldown_seconds:
        return None

    cfg = state.config
    rt = state.rule_type
    sym = msg.get("sym", "?")

    if rt == "pct_move":
        price = _msg_price(msg)
        if price is None:
            return None
        if state.baseline_price is None:
            state.baseline_price = price
            return None
        threshold = float(cfg.get("threshold_pct", 1.0)) / 100.0
        direction = cfg.get("direction", "any")
        change = (price - state.baseline_price) / state.baseline_price
        if direction == "up" and change < threshold:
            return None
        if direction == "down" and change > -threshold:
            return None
        if direction == "any" and abs(change) < threshold:
            return None
        state.last_fired_at = now
        pct = change * 100.0
        sign = "up" if change > 0 else "down"
        return (
            f"{sym} {sign} {abs(pct):.2f}% to {price:.2f} "
            f"(baseline {state.baseline_price:.2f})"
        )

    if rt == "price_cross":
        price = _msg_price(msg)
        if price is None:
            return None
        target = float(cfg["price"])
        direction = cfg.get("direction", "any")
        if state.last_price is None:
            state.last_price = price
            return None
        prev = state.last_price
        state.last_price = price
        crossed_up = prev < target <= price
        crossed_down = prev > target >= price
        if direction == "above" and not crossed_up:
            return None
        if direction == "below" and not crossed_down:
            return None
        if direction == "any" and not (crossed_up or crossed_down):
            return None
        state.last_fired_at = now
        which = "above" if crossed_up else "below"
        return f"{sym} crossed {which} {target} (now {price:.2f})"

    if rt == "volume":
        if msg.get("ev") != "T":
            return None
        size = msg.get("s")
        if size is None:
            return None
        min_size = int(cfg.get("min_size", 1000))
        if size < min_size:
            return None
        state.last_fired_at = now
        price = msg.get("p", 0.0)
        return f"{sym} block trade: size {size} @ {price:.2f}"

    return None


# --- Client registry -------------------------------------------------------

AlertDeliver = Callable[[str, dict], Awaitable[None]]


class ClientRegistry:
    """Tracks active voice-session websocket connections so alerts can
    be pushed to whoever is currently listening."""

    def __init__(self) -> None:
        self._delivers: list[AlertDeliver] = []
        self._lock = asyncio.Lock()

    async def register(self, deliver: AlertDeliver) -> None:
        async with self._lock:
            self._delivers.append(deliver)

    async def unregister(self, deliver: AlertDeliver) -> None:
        async with self._lock:
            if deliver in self._delivers:
                self._delivers.remove(deliver)

    async def broadcast(self, message: str, payload: dict) -> int:
        async with self._lock:
            targets = list(self._delivers)
        delivered = 0
        for d in targets:
            try:
                await d(message, payload)
                delivered += 1
            except Exception as e:
                print(f"[market] alert delivery failed: {e}")
        return delivered


clients = ClientRegistry()


# --- Subscription manager --------------------------------------------------

class SubscriptionManager:
    def __init__(self) -> None:
        self._ws: Any = None
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()
        self._sub_dirty = asyncio.Event()
        self._live_topics: set[str] = set()
        self._rule_states: dict[int, RuleState] = {}
        self._authed = False

    @property
    def url(self) -> str:
        return f"wss://{FEED_HOST}/{MARKET_PATH}"

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        if not API_KEY:
            print("[market] no MASSIVE_API_KEY; SubscriptionManager disabled")
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="market-ws")

    async def stop(self) -> None:
        self._stop.set()
        self._sub_dirty.set()
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=3)
            except (asyncio.TimeoutError, Exception):
                pass

    def request_resync(self) -> None:
        """Called by HAL tools after DB mutation; triggers diff+update on
        the next loop iteration. Also reloads in-memory rule states."""
        self._reload_rule_states()
        self._sub_dirty.set()

    def _reload_rule_states(self) -> None:
        new_states: dict[int, RuleState] = {}
        for r in list_rules_with_subs():
            rid = r["rule_id"]
            prev = self._rule_states.get(rid)
            if prev:
                prev.config = json.loads(r["config"])
                prev.cooldown_seconds = r["cooldown_seconds"]
                prev.channel = r["channel"]
                prev.symbol_pattern = r["symbol"]
                new_states[rid] = prev
            else:
                new_states[rid] = RuleState(
                    rule_id=rid,
                    sub_id=r["subscription_id"],
                    channel=r["channel"],
                    symbol_pattern=r["symbol"],
                    rule_type=r["rule_type"],
                    config=json.loads(r["config"]),
                    cooldown_seconds=r["cooldown_seconds"],
                )
        self._rule_states = new_states

    def _desired_topics(self) -> set[str]:
        return {f"{s['channel']}.{s['symbol']}" for s in list_subscriptions_db()}

    async def _run(self) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            try:
                async with ws_connect(self.url, max_size=8 * 1024 * 1024) as ws:
                    self._ws = ws
                    self._authed = False
                    backoff = 1.0
                    print(f"[market] connected {self.url}")
                    try:
                        hello = await asyncio.wait_for(ws.recv(), timeout=10)
                        print(f"[market] hello: {hello!r}")
                    except asyncio.TimeoutError:
                        print("[market] no hello; continuing")
                    await ws.send(json.dumps({"action": "auth", "params": API_KEY}))
                    try:
                        auth_resp = await asyncio.wait_for(ws.recv(), timeout=10)
                    except asyncio.TimeoutError:
                        print("[market] auth timeout")
                        raise ConnectionClosed(None, None)
                    print(f"[market] auth resp: {auth_resp!r}")
                    try:
                        parsed = json.loads(auth_resp)
                        if isinstance(parsed, list) and parsed:
                            status = parsed[0].get("status")
                            if status == "auth_failed":
                                print(
                                    f"[market] auth FAILED: "
                                    f"{parsed[0].get('message')}"
                                )
                                self._stop.set()
                                break
                    except json.JSONDecodeError:
                        pass
                    self._authed = True
                    self._reload_rule_states()
                    self._live_topics = set()
                    await self._sync_subscriptions()
                    while not self._stop.is_set():
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        except asyncio.TimeoutError:
                            if self._sub_dirty.is_set():
                                self._sub_dirty.clear()
                                await self._sync_subscriptions()
                            continue
                        try:
                            msgs = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        if not isinstance(msgs, list):
                            continue
                        for m in msgs:
                            if m.get("ev") == "status":
                                print(f"[market] status: {m.get('message')}")
                                continue
                            await self._dispatch(m)
                        if self._sub_dirty.is_set():
                            self._sub_dirty.clear()
                            await self._sync_subscriptions()
            except (ConnectionClosed, OSError) as e:
                print(
                    f"[market] connection lost: {e}; reconnecting in {backoff:.1f}s"
                )
            except Exception as e:
                print(
                    f"[market] unexpected error: {e}; reconnecting in {backoff:.1f}s"
                )
            finally:
                self._ws = None
                self._authed = False
                self._live_topics = set()
            if self._stop.is_set():
                break
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=backoff)
            except asyncio.TimeoutError:
                pass
            backoff = min(backoff * 2, 30.0)
        print("[market] manager stopped")

    async def _sync_subscriptions(self) -> None:
        if self._ws is None or not self._authed:
            return
        desired = self._desired_topics()
        to_add = desired - self._live_topics
        to_remove = self._live_topics - desired
        if to_add:
            params = ",".join(sorted(to_add))
            print(f"[market] subscribe: {params}")
            await self._ws.send(
                json.dumps({"action": "subscribe", "params": params})
            )
        if to_remove:
            params = ",".join(sorted(to_remove))
            print(f"[market] unsubscribe: {params}")
            await self._ws.send(
                json.dumps({"action": "unsubscribe", "params": params})
            )
        self._live_topics = desired

    async def _dispatch(self, msg: dict) -> None:
        ev = msg.get("ev", "")
        sym = msg.get("sym", "")
        for state in list(self._rule_states.values()):
            if state.channel != ev:
                continue
            if not _symbol_matches(state.symbol_pattern, sym):
                continue
            try:
                fired = evaluate_rule(state, msg)
            except Exception as e:
                print(f"[market] rule {state.rule_id} eval error: {e}")
                continue
            if fired:
                event_id = record_alert(state.rule_id, msg, fired)
                delivered = await clients.broadcast(
                    fired, {"event_id": event_id, **msg}
                )
                if delivered > 0:
                    mark_alert_spoken(event_id)
                print(
                    f"[market] alert (rule {state.rule_id}, "
                    f"delivered={delivered}): {fired}"
                )


manager = SubscriptionManager()


# --- HAL-facing tool entry points -----------------------------------------

def tool_subscribe_market(channel: str, symbol: str, note: str = "") -> dict:
    channel = channel.upper().strip()
    symbol = symbol.strip()
    if channel not in VALID_CHANNELS:
        return {
            "error": f"channel must be one of {sorted(VALID_CHANNELS)}, got {channel!r}"
        }
    if not symbol:
        return {"error": "symbol is required"}
    sub_id = insert_subscription(channel, symbol, note)
    manager.request_resync()
    return {"subscription_id": sub_id, "channel": channel, "symbol": symbol}


def tool_add_alert_rule(
    subscription_id: int,
    rule_type: str,
    config: dict,
    note: str = "",
    cooldown_seconds: float = 60.0,
) -> dict:
    rule_type = rule_type.strip()
    if rule_type not in VALID_RULE_TYPES:
        return {
            "error": f"rule_type must be one of {sorted(VALID_RULE_TYPES)}, "
            f"got {rule_type!r}"
        }
    # Basic config validation per type
    if rule_type == "pct_move":
        if "threshold_pct" not in config:
            return {"error": "pct_move requires config.threshold_pct (number)"}
    elif rule_type == "price_cross":
        if "price" not in config:
            return {"error": "price_cross requires config.price (number)"}
    elif rule_type == "volume":
        if "min_size" not in config:
            return {"error": "volume requires config.min_size (integer)"}
    # Confirm the sub exists
    subs = list_subscriptions_db()
    if not any(s["id"] == subscription_id for s in subs):
        return {"error": f"no active subscription with id {subscription_id}"}
    rule_id = insert_rule(
        subscription_id, rule_type, config, note, cooldown_seconds
    )
    manager.request_resync()
    return {"rule_id": rule_id, "subscription_id": subscription_id}


def tool_list_subscriptions() -> dict:
    subs = list_subscriptions_db()
    for s in subs:
        s["rules"] = list_rules_for_sub(s["id"])
        for r in s["rules"]:
            try:
                r["config"] = json.loads(r["config"])
            except Exception:
                pass
    return {"subscriptions": subs, "connected": manager._authed, "url": manager.url}


def tool_unsubscribe(subscription_id: int) -> dict:
    ok = deactivate_subscription(subscription_id)
    if not ok:
        return {"error": f"no subscription with id {subscription_id}"}
    manager.request_resync()
    return {"deactivated": subscription_id}


def tool_remove_rule(rule_id: int) -> dict:
    ok = deactivate_rule(rule_id)
    if not ok:
        return {"error": f"no rule with id {rule_id}"}
    manager.request_resync()
    return {"deactivated_rule": rule_id}


def tool_list_alert_history(limit: int = 20) -> dict:
    return {"events": list_alert_events(limit)}
