"""Real-time market data subscriptions and alert delivery for HAL.

Owns outbound WebSocket connections to Alpaca's streams. Reads
ws_subscriptions and alert_rules from the same SQLite DB the conversation
history lives in (see server._init_db), evaluates rules in-process as ticks
arrive, and pushes fired alerts to active voice sessions via ClientRegistry.

Alpaca splits stocks and options across two sockets, so the manager runs one
_AlpacaStream per venue and routes each subscription by symbol shape (an OCC
symbol like SPY261219C00500000 is an option, anything else is a stock). That
is a real gain over the old options-only feed, which never ticked underlyings
at all — price rules on a plain ticker are now driven by live trades rather
than only by the Yahoo poller's 15-second snapshots.

Wire protocol (both venues):
  auth        {"action":"auth","key":...,"secret":...}
  subscribe   {"action":"subscribe","trades":[...],"quotes":[...],"bars":[...]}
  data        [{"T":"t","S":"SPY","p":...}, ...]   T=type, S=symbol
The two venues do NOT use the same encoding: the stock stream speaks JSON text
frames while the options stream speaks MessagePack binary frames (sending it
JSON returns {"T":"error","msg":"invalid syntax"}). Each connection detects the
codec from the server's greeting rather than assuming, so either venue can
switch without breaking the other.

Messages are normalized to the internal {"ev","sym",...} shape before dispatch
so evaluate_rule, the stored alert payloads and the UI stay unchanged.

Free-tier caveats: stock quotes/trades are the IEX tape (not full SIP), and
options run on the "indicative" feed; real-time OPRA is a paid upgrade.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

import msgpack
from websockets.asyncio.client import connect as ws_connect
from websockets.exceptions import ConnectionClosed


# Filled by server.configure_market() at boot; avoids a circular import.
DB_PATH: Optional[Path] = None
API_KEY: str = ""
SECRET_KEY: str = ""
STREAM_HOST = "stream.data.alpaca.markets"
# Stock feed: "iex" is the free real-time tape; "sip" needs a paid plan.
STOCK_PATH = "v2/iex"
# Option feed: "indicative" is free; "opra" needs the paid Algo Trader Plus plan.
OPTION_PATH = "v1beta1/indicative"


def configure(
    db_path: Path,
    api_key: str,
    secret_key: str,
    stock_feed: str = "iex",
    option_feed: str = "indicative",
) -> None:
    global DB_PATH, API_KEY, SECRET_KEY, STOCK_PATH, OPTION_PATH
    DB_PATH = db_path
    API_KEY = api_key
    SECRET_KEY = secret_key
    STOCK_PATH = f"v2/{stock_feed if stock_feed in ('iex', 'sip') else 'iex'}"
    OPTION_PATH = (
        f"v1beta1/{option_feed if option_feed in ('indicative', 'opra') else 'indicative'}"
    )


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

# Channels HAL will accept for a NEW subscription. Alpaca streams trades,
# quotes and minute bars; it has no per-second aggregate or fair-market-value
# channel, so the old "A" and "FMV" are no longer offered. Rows already in the
# DB using them still work — _STREAM_KEYS maps them onto minute bars rather
# than letting them go silently dead.
VALID_CHANNELS = {"T", "Q", "AM"}
VALID_RULE_TYPES = {"pct_move", "price_cross", "volume"}

# Internal channel -> Alpaca subscribe key.
_STREAM_KEYS = {"T": "trades", "Q": "quotes", "AM": "bars", "A": "bars", "FMV": "bars"}

# Alpaca message type -> internal channel. 'b' is a minute bar, which is what
# both AM and the legacy A/FMV rows resolve to.
_MSG_CHANNELS = {"t": "T", "q": "Q", "b": "AM"}


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
    """Local matching for a stored subscription pattern: '*' = all, 'SPY*' =
    every symbol with that root, or an exact match. Patterns are normalized on
    both sides so a legacy 'O:SPY*' row still matches Alpaca's bare symbols."""
    pattern, symbol = _bare(pattern), _bare(symbol)
    if pattern == "*" or pattern == symbol:
        return True
    if pattern.endswith("*"):
        return symbol.startswith(pattern[:-1])
    return False


def _bare(symbol: str) -> str:
    """Strip the legacy Polygon/Massive 'O:' option prefix. Subscriptions
    created before the Alpaca migration still carry it."""
    s = (symbol or "").strip().upper()
    return s[2:] if s.startswith("O:") else s


def _is_option(symbol: str) -> bool:
    """True for an OCC contract symbol (root + YYMMDD + C/P + 8-digit strike).
    Decides which of the two Alpaca sockets a subscription belongs on."""
    s = _bare(symbol).rstrip("*")
    if len(s) < 16:
        return False
    tail = s[-15:]
    return tail[0:6].isdigit() and tail[6] in ("C", "P") and tail[7:15].isdigit()


def _normalize(msg: dict) -> Optional[dict]:
    """Alpaca stream message -> the internal {"ev","sym",...} shape the rule
    engine, stored payloads and UI already speak. None for non-data frames."""
    ev = _MSG_CHANNELS.get(msg.get("T", ""))
    if ev is None:
        return None
    out: dict[str, Any] = {"ev": ev, "sym": msg.get("S", "")}
    if ev == "T":
        out["p"], out["s"] = msg.get("p"), msg.get("s")
    elif ev == "Q":
        out["bp"], out["ap"] = msg.get("bp"), msg.get("ap")
        out["bs"], out["as"] = msg.get("bs"), msg.get("as")
    else:  # minute bar
        out["o"], out["h"] = msg.get("o"), msg.get("h")
        out["l"], out["c"] = msg.get("l"), msg.get("c")
        out["v"] = msg.get("v")
    return out


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
        # Quiet mode (do-not-disturb): drop every proactive spoken alert at this
        # one chokepoint. News, earnings, price, and managed-exit announcements
        # all funnel through here, so the single guard silences them all. Returns
        # 0 = "not delivered", so callers leave items unspoken (they replay later
        # once quiet is lifted) rather than marking them announced.
        if _quiet:
            return 0
        # Single-user app: deliver ONLY to the most recently registered client
        # (the live UI). Stale registrations linger briefly across reconnects,
        # and delivering to all of them makes HAL speak the alert more than once.
        async with self._lock:
            target = self._delivers[-1] if self._delivers else None
        if target is None:
            return 0
        try:
            await target(message, payload)
            return 1
        except Exception as e:
            print(f"[market] alert delivery failed: {e}")
            return 0


clients = ClientRegistry()


# Quiet mode (do-not-disturb) flag. Runtime-only and latches until lifted — a
# server restart clears it. Read by ClientRegistry.broadcast (suppresses spoken
# alerts) and by the turn loop (suppresses HAL's proactive trade-pitching).
_quiet = False


def set_quiet(on: bool) -> None:
    global _quiet
    _quiet = bool(on)


def is_quiet() -> bool:
    return _quiet


# Futures mode. Runtime-only, latches until lifted (a restart clears it). When
# OFF (the default), HAL stops volunteering trade ideas once the equity session
# has closed for the day (see the turn loop + AFTER_HOURS_DIRECTIVE). ON lets him
# pitch around the clock — for when the user is trading overnight futures.
_futures = False


def set_futures(on: bool) -> None:
    global _futures
    _futures = bool(on)


def is_futures() -> bool:
    return _futures


# --- Subscription manager --------------------------------------------------

class _AlpacaStream:
    """One authenticated Alpaca WebSocket, reconnecting with backoff.

    Holds no rule state — it owns the socket and the set of live topics, and
    hands every normalized data message to the manager's dispatch callback.
    Two of these run at once (stocks and options) because Alpaca serves the
    two venues from separate endpoints.
    """

    def __init__(
        self,
        name: str,
        path: str,
        desired: Callable[[], dict[str, set[str]]],
        dispatch: Callable[[dict], Awaitable[None]],
        binary: bool = False,
    ) -> None:
        self._name = name
        self._path = path
        self._desired = desired
        self._dispatch = dispatch
        # Encoding this venue is expected to use; corrected from the greeting
        # frame on every connect, so a server-side change can't strand us.
        self._binary = binary
        self._ws: Any = None
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()
        self._dirty = asyncio.Event()
        self._live: dict[str, set[str]] = {}
        self.authed = False

    def _encode(self, obj: dict) -> Any:
        return msgpack.packb(obj) if self._binary else json.dumps(obj)

    def _decode(self, raw: Any) -> list[dict]:
        """Frame -> list of messages, whichever codec the peer is using."""
        try:
            msgs = msgpack.unpackb(raw, raw=False) if isinstance(raw, (bytes, bytearray)) \
                else json.loads(raw)
        except Exception:
            return []
        if isinstance(msgs, dict):
            return [msgs]
        return [m for m in msgs if isinstance(m, dict)] if isinstance(msgs, list) else []

    @property
    def url(self) -> str:
        return f"wss://{STREAM_HOST}/{self._path}"

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name=f"market-ws-{self._name}")

    async def stop(self) -> None:
        self._stop.set()
        self._dirty.set()
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

    def mark_dirty(self) -> None:
        self._dirty.set()

    async def _authenticate(self, ws: Any) -> bool:
        """Alpaca greets with [{"T":"success","msg":"connected"}], then expects
        an auth frame and answers [{"T":"success","msg":"authenticated"}].
        The greeting also reveals the codec: a binary frame means MessagePack,
        and replying in the wrong one earns 'invalid syntax'."""
        try:
            hello = await asyncio.wait_for(ws.recv(), timeout=10)
            self._binary = isinstance(hello, (bytes, bytearray))
            print(f"[market:{self._name}] hello ({'msgpack' if self._binary else 'json'}): "
                  f"{self._decode(hello)}")
        except asyncio.TimeoutError:
            print(f"[market:{self._name}] no hello; assuming "
                  f"{'msgpack' if self._binary else 'json'}")
        await ws.send(self._encode(
            {"action": "auth", "key": API_KEY, "secret": SECRET_KEY}))
        try:
            resp = await asyncio.wait_for(ws.recv(), timeout=10)
        except asyncio.TimeoutError:
            print(f"[market:{self._name}] auth timeout")
            return False
        msgs = self._decode(resp)
        print(f"[market:{self._name}] auth resp: {msgs}")
        for m in msgs:
            if m.get("T") == "error":
                # A bad key or an already-connected session is permanent —
                # reconnecting in a loop would just hammer Alpaca.
                print(f"[market:{self._name}] auth FAILED: {m.get('msg')}")
                self._stop.set()
                return False
            if m.get("T") == "success" and m.get("msg") == "authenticated":
                return True
        return False

    async def _run(self) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            try:
                async with ws_connect(self.url, max_size=8 * 1024 * 1024) as ws:
                    self._ws = ws
                    self.authed = False
                    backoff = 1.0
                    print(f"[market:{self._name}] connected {self.url}")
                    if not await self._authenticate(ws):
                        raise ConnectionClosed(None, None)
                    self.authed = True
                    self._live = {}
                    await self._sync()
                    while not self._stop.is_set():
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        except asyncio.TimeoutError:
                            if self._dirty.is_set():
                                self._dirty.clear()
                                await self._sync()
                            continue
                        for m in self._decode(raw):
                            kind = m.get("T")
                            if kind == "subscription":
                                self._apply_subscription(m)
                                continue
                            if kind == "success":
                                continue
                            if kind == "error":
                                print(f"[market:{self._name}] error: {m.get('msg')}")
                                continue
                            norm = _normalize(m)
                            if norm is not None:
                                await self._dispatch(norm)
                        if self._dirty.is_set():
                            self._dirty.clear()
                            await self._sync()
            except (ConnectionClosed, OSError) as e:
                print(f"[market:{self._name}] connection lost: {e}; "
                      f"reconnecting in {backoff:.1f}s")
            except Exception as e:
                print(f"[market:{self._name}] unexpected error: {e}; "
                      f"reconnecting in {backoff:.1f}s")
            finally:
                self._ws = None
                self.authed = False
                self._live = {}
            if self._stop.is_set():
                break
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=backoff)
            except asyncio.TimeoutError:
                pass
            backoff = min(backoff * 2, 30.0)
        print(f"[market:{self._name}] stopped")

    def _apply_subscription(self, msg: dict) -> None:
        """Record what Alpaca says is actually subscribed.

        The server answers every subscribe/unsubscribe with the full live set,
        which is the ONLY trustworthy source: a request can be partly or wholly
        rejected (the free plan caps concurrent symbols and replies "symbol
        limit exceeded"). Trusting our own request instead would mark a symbol
        as streaming when it isn't — and the Yahoo poller skips streaming
        symbols, so those alerts would go quietly dead.
        """
        live = {k: set(msg.get(k) or []) for k in _STREAM_KEYS.values() if msg.get(k)}
        if live != self._live:
            print(f"[market:{self._name}] live topics now: {live or '{}'}")
        self._live = live

    async def _sync(self) -> None:
        """Diff desired vs live topics and send one subscribe/unsubscribe frame.
        Alpaca groups symbols by channel, so each frame carries up to three
        lists rather than the old comma-joined 'channel.symbol' string.

        `_live` is deliberately NOT updated here — it's set from the server's
        subscription confirmation (see _apply_subscription). Re-sending an
        already-live subscribe before the confirmation lands is harmless.
        """
        if self._ws is None or not self.authed:
            return
        desired = self._desired()
        add = {k: sorted(v - self._live.get(k, set()))
               for k, v in desired.items()}
        add = {k: v for k, v in add.items() if v}
        drop = {k: sorted(v - desired.get(k, set()))
                for k, v in self._live.items()}
        drop = {k: v for k, v in drop.items() if v}
        if add:
            print(f"[market:{self._name}] subscribe: {add}")
            await self._ws.send(self._encode({"action": "subscribe", **add}))
        if drop:
            print(f"[market:{self._name}] unsubscribe: {drop}")
            await self._ws.send(self._encode({"action": "unsubscribe", **drop}))


class SubscriptionManager:
    """Owns both venue streams plus the shared rule state, and evaluates every
    incoming tick against the rules whose channel and symbol pattern match."""

    def __init__(self) -> None:
        self._rule_states: dict[int, RuleState] = {}
        self._stocks = _AlpacaStream(
            "stocks", STOCK_PATH, lambda: self._topics(options=False), self._dispatch,
            binary=False)
        self._options = _AlpacaStream(
            "options", OPTION_PATH, lambda: self._topics(options=True), self._dispatch,
            binary=True)

    @property
    def url(self) -> str:
        return f"{self._stocks.url} + {self._options.url}"

    @property
    def _authed(self) -> bool:
        """True if either venue is live — tool_list_subscriptions reports it."""
        return self._stocks.authed or self._options.authed

    def live_symbols(self) -> set[str]:
        """Symbols currently streaming, so the Yahoo poller can skip them and
        avoid double-firing a rule that the WS already drives."""
        out: set[str] = set()
        for stream in (self._stocks, self._options):
            if stream.authed:
                for syms in stream._live.values():
                    out |= syms
        return out

    async def start(self) -> None:
        if not (API_KEY and SECRET_KEY):
            print("[market] no Alpaca keys; SubscriptionManager disabled")
            return
        # Paths are resolved at configure() time, after this object was built.
        self._stocks._path, self._options._path = STOCK_PATH, OPTION_PATH
        self._reload_rule_states()
        await self._stocks.start()
        await self._options.start()

    async def stop(self) -> None:
        await self._stocks.stop()
        await self._options.stop()

    def request_resync(self) -> None:
        """Called by HAL tools after DB mutation; triggers diff+update on
        the next loop iteration. Also reloads in-memory rule states."""
        self._reload_rule_states()
        self._stocks.mark_dirty()
        self._options.mark_dirty()

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

    def _topics(self, options: bool) -> dict[str, set[str]]:
        """Subscriptions for one venue, grouped by Alpaca channel key.

        Alpaca has no prefix wildcard, so a stored 'SPY*' pattern cannot be put
        on the wire. The bare '*' exists but the free plan rejects it with
        "symbol limit exceeded" (there is a cap on concurrent symbols), so it
        is dropped too. Both are skipped with a warning rather than silently
        failing — local matching in _symbol_matches still applies to whatever
        does arrive from the explicit subscriptions.
        """
        topics: dict[str, set[str]] = {}
        for sub in list_subscriptions_db():
            symbol = _bare(sub["symbol"])
            if _is_option(symbol) != options:
                continue
            key = _STREAM_KEYS.get(sub["channel"])
            if key is None:
                continue
            if symbol.endswith("*"):
                print(f"[market] '{sub['symbol']}' skipped: Alpaca has no prefix "
                      f"wildcard and rejects '*' on this plan — name symbols explicitly")
                continue
            topics.setdefault(key, set()).add(symbol)
        return topics

    async def _dispatch(self, msg: dict) -> None:
        ev = msg.get("ev", "")
        sym = msg.get("sym", "")
        for state in list(self._rule_states.values()):
            # Legacy A/FMV rows resolve to minute bars on the wire, so they
            # must match the AM messages those subscriptions now produce.
            if _STREAM_KEYS.get(state.channel) != _STREAM_KEYS.get(ev):
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


# --- Yahoo price-alert poller ----------------------------------------------
# A safety net beneath the WS streams: every POLL_SECONDS during regular hours
# it pulls each rule's symbol price from Yahoo and runs the very same
# evaluate_rule + record_alert + clients.broadcast path the WS uses.
#
# Alpaca's stock stream now covers underlyings directly, so this only handles
# symbols the WS is NOT currently streaming — a symbol served by both would
# otherwise fire the same rule twice, from two different prices. It still
# earns its keep: it covers rules whose subscription is a wildcard pattern
# Alpaca can't express, and keeps alerts alive if a stream is down.

class YahooAlertPoller:
    def __init__(self, poll_seconds: float = 15.0) -> None:
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()
        self._poll_seconds = poll_seconds
        # Per-rule evaluation state (last_price / baseline / cooldown), kept
        # across polls so price_cross can detect an actual crossing.
        self._states: dict[int, RuleState] = {}

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="yahoo-alert-poller")

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=3)
            except (asyncio.TimeoutError, Exception):
                pass

    async def _run(self) -> None:
        from hal.cerebellum import markettime
        print(f"[alert-poll] started ({self._poll_seconds:.0f}s, regular hours)")
        while not self._stop.is_set():
            try:
                if markettime.is_regular_hours():
                    await self._poll_once()
            except Exception as e:
                print(f"[alert-poll] error: {e}")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._poll_seconds)
            except asyncio.TimeoutError:
                pass
        print("[alert-poll] stopped")

    async def _poll_once(self) -> None:
        from hal.motor import charting
        rules = list_rules_with_subs(active_only=True)
        # Only price rules can be evaluated from a snapshot price; volume rules
        # need per-trade size, which the poll can't provide.
        rules = [r for r in rules if r["rule_type"] in ("pct_move", "price_cross")]
        # Skip anything the WS is already ticking, or the rule fires twice.
        streaming = manager.live_symbols()
        rules = [r for r in rules if _bare(r["symbol"]) not in streaming]
        if not rules:
            self._states.clear()
            return
        live_ids = {r["rule_id"] for r in rules}
        self._states = {rid: s for rid, s in self._states.items() if rid in live_ids}

        prices = await charting.current_prices([r["symbol"] for r in rules])
        for r in rules:
            sym = r["symbol"]
            price = prices.get(sym)
            if price is None:
                continue
            st = self._states.get(r["rule_id"])
            if st is None:
                st = RuleState(
                    rule_id=r["rule_id"],
                    sub_id=r["subscription_id"],
                    channel=r["channel"],
                    symbol_pattern=sym,
                    rule_type=r["rule_type"],
                    config=json.loads(r["config"]),
                    cooldown_seconds=r["cooldown_seconds"],
                )
                self._states[r["rule_id"]] = st
            else:
                st.config = json.loads(r["config"])
                st.cooldown_seconds = r["cooldown_seconds"]
            # Synthetic trade message so _msg_price returns our polled price.
            msg = {"ev": st.channel, "sym": sym, "p": price, "c": price, "src": "yahoo"}
            try:
                fired = evaluate_rule(st, msg)
            except Exception as e:
                print(f"[alert-poll] rule {st.rule_id} eval error: {e}")
                continue
            if fired:
                event_id = record_alert(st.rule_id, msg, fired)
                delivered = await clients.broadcast(fired, {"event_id": event_id, **msg})
                if delivered > 0:
                    mark_alert_spoken(event_id)
                print(f"[alert-poll] fired (rule {st.rule_id}, delivered={delivered}): {fired}")


alert_poller = YahooAlertPoller()


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
