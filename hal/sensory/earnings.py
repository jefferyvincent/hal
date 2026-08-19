"""Pre-earnings IV-crush screener for HAL.

A companion to news.py. Where news.py polls per-symbol headlines, this module
scans the watchlist (the news_watches table) for names that report earnings
soon AND whose options are overpriced — i.e. implied vol sits well above the
stock's recent realized vol. Those are exactly the setups the "skip earnings"
rule exists for: rich premium that the post-report IV crush will deflate. The
flag lets the user avoid or fade them deliberately instead of stumbling in.

It deliberately reuses the same plumbing as news.py:
  - market.clients.broadcast for spoken delivery + recording (one path)
  - the watchlist already in news_watches (no second list to maintain)
  - analysis.iv_context for the RICH/FAIR/CHEAP verdict (no second vol model)

Earnings dates come from Nasdaq's keyless calendar endpoint, matching the
no-API-key spirit of the news RSS feeds. Each report is a per-date query; we
fetch the next EARNINGS_LOOKAHEAD_DAYS days once per scan and intersect with
the watchlist.

Only RICH names (IV >= 1.3x HV30, per analysis.iv_context) are flagged, and
each earnings event is announced once — earnings_iv_alerts dedupes on
(symbol, earnings_date) and doubles as alert history + missed-while-away replay.
"""
from __future__ import annotations

import asyncio
import sqlite3
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import httpx

from hal.sensory import market  # reuse market.clients for spoken delivery + recording
from hal.sensory import news    # the watchlist lives in news_watches
from hal.cortex import analysis  # iv_context: RICH/FAIR/CHEAP verdict


# Filled by server via configure() at boot; avoids a circular import.
DB_PATH: Optional[Path] = None
POLL_SECONDS: float = 3600.0
LOOKAHEAD_DAYS: int = 3

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
_NASDAQ_URL = "https://api.nasdaq.com/api/calendar/earnings"
# Nasdaq sends JSON only with browser-ish headers + an Origin/Referer it trusts.
_NASDAQ_HEADERS = {
    "User-Agent": _UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.nasdaq.com",
    "Referer": "https://www.nasdaq.com/",
}


def configure(db_path: Path, poll_seconds: float = 3600.0, lookahead_days: int = 3) -> None:
    global DB_PATH, POLL_SECONDS, LOOKAHEAD_DAYS
    DB_PATH = db_path
    POLL_SECONDS = float(poll_seconds)
    LOOKAHEAD_DAYS = max(0, int(lookahead_days))


# --- DB helpers ------------------------------------------------------------

def _db() -> sqlite3.Connection:
    if DB_PATH is None:
        raise RuntimeError("earnings.configure() not called")
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def alert_exists(symbol: str, earnings_date: str) -> bool:
    """True if this earnings event was already flagged (dedupe before the
    expensive IV pull)."""
    with _db() as conn:
        row = conn.execute(
            "SELECT 1 FROM earnings_iv_alerts WHERE symbol=? AND earnings_date=?",
            (symbol, earnings_date),
        ).fetchone()
        return row is not None


def insert_alert(symbol: str, earnings_date: str, earnings_when: str,
                 ctx: dict, message: str, spoken: int = 0) -> Optional[int]:
    """Record a fired IV-crush alert. Returns the new row id, or None if this
    (symbol, earnings_date) was already recorded (UNIQUE conflict) — the dedupe."""
    with _db() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO earnings_iv_alerts"
            "(symbol, earnings_date, earnings_when, atm_iv, hv30, iv_over_hv30, "
            " verdict, message, fired_at, spoken) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                symbol, earnings_date, earnings_when,
                ctx.get("atm_iv"), ctx.get("hv30"), ctx.get("iv_over_hv30"),
                ctx.get("verdict"), message, time.time(), spoken,
            ),
        )
        return cur.lastrowid if cur.rowcount else None


def mark_alert_spoken(alert_id: int) -> None:
    with _db() as conn:
        conn.execute("UPDATE earnings_iv_alerts SET spoken=1 WHERE id=?", (alert_id,))


def list_recent_alerts(limit: int = 20) -> list[dict]:
    with _db() as conn:
        rows = conn.execute(
            "SELECT id, symbol, earnings_date, earnings_when, atm_iv, hv30, "
            "       iv_over_hv30, verdict, message, fired_at, spoken "
            "FROM earnings_iv_alerts ORDER BY fired_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def list_unspoken_alerts(limit: int = 20) -> list[dict]:
    """Alerts recorded while no app session was connected — replayed on
    reconnect, oldest first."""
    with _db() as conn:
        rows = conn.execute(
            "SELECT id, symbol, earnings_date, message, fired_at "
            "FROM earnings_iv_alerts WHERE spoken = 0 "
            "ORDER BY fired_at ASC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


# --- Earnings calendar fetch (Nasdaq, keyless) -----------------------------

def _classify_when(raw: Optional[str]) -> str:
    """Map Nasdaq's report-time string to bmo / amc / unknown."""
    t = (raw or "").lower()
    if "pre-market" in t or "pre market" in t:
        return "bmo"
    if "after-hours" in t or "after hours" in t:
        return "amc"
    return "unknown"


async def _fetch_calendar_for_date(client: httpx.AsyncClient, day: date) -> dict[str, str]:
    """Symbols reporting on `day` -> report-time class. Empty on any failure
    (weekend/holiday/transient), so one bad date never sinks the scan."""
    try:
        r = await client.get(
            _NASDAQ_URL, params={"date": day.isoformat()}, headers=_NASDAQ_HEADERS,
        )
        r.raise_for_status()
        rows = ((r.json() or {}).get("data") or {}).get("rows") or []
    except Exception as e:
        print(f"[earnings] calendar fetch failed for {day.isoformat()}: {e}")
        return {}
    out: dict[str, str] = {}
    for row in rows:
        sym = (row.get("symbol") or "").upper().strip()
        if sym:
            out[sym] = _classify_when(row.get("time"))
    return out


async def fetch_upcoming(client: httpx.AsyncClient) -> dict[str, dict]:
    """Earnings within the lookahead window, keyed by symbol. Earliest report
    wins if a symbol somehow appears on multiple dates. Value:
    {"date": ISO str, "when": bmo|amc|unknown, "days_until": int}."""
    today = date.today()
    upcoming: dict[str, dict] = {}
    for offset in range(LOOKAHEAD_DAYS + 1):
        day = today + timedelta(days=offset)
        for sym, when in (await _fetch_calendar_for_date(client, day)).items():
            if sym not in upcoming:  # earliest date wins (offsets ascend)
                upcoming[sym] = {"date": day.isoformat(), "when": when,
                                 "days_until": offset}
    return upcoming


# --- Pre-trade lookup ------------------------------------------------------
# The screener above runs hourly over the watchlist; the rules gate needs a
# different shape — "is THIS symbol reporting soon?", answered on the order path
# where latency matters. One calendar day is fetched at a time, so a week costs
# 8 requests; cached per (day, depth) so the cost is paid once per session and
# the gate is free thereafter. Nasdaq is keyless and does go down: on failure
# this returns None ("unknown"), and the gate treats unknown as "don't block".

_calendar_cache: dict[int, tuple[str, dict[str, dict]]] = {}


async def upcoming_within(days: int) -> dict[str, dict]:
    """Earnings within `days` calendar days, keyed by symbol. Cached for the
    current date. Returns {} if the calendar can't be reached."""
    today = date.today().isoformat()
    hit = _calendar_cache.get(days)
    if hit and hit[0] == today:
        return hit[1]
    upcoming: dict[str, dict] = {}
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            for offset in range(max(0, days) + 1):
                day = date.today() + timedelta(days=offset)
                for sym, when in (await _fetch_calendar_for_date(client, day)).items():
                    if sym not in upcoming:  # earliest date wins (offsets ascend)
                        upcoming[sym] = {"date": day.isoformat(), "when": when,
                                         "days_until": offset}
    except Exception as e:
        print(f"[earnings] calendar unavailable: {type(e).__name__}: {e}")
        return {}
    _calendar_cache[days] = (today, upcoming)
    return upcoming


async def days_until_earnings(symbol: str, within_days: int = 7) -> Optional[int]:
    """Calendar days until `symbol` next reports, or None when it doesn't report
    inside the window OR the calendar is unreachable. The caller cannot tell
    those apart on purpose — both mean "no reason to block"."""
    sym = (symbol or "").strip().upper()
    if not sym:
        return None
    info = (await upcoming_within(within_days)).get(sym)
    return info["days_until"] if info else None


# --- Alert phrasing --------------------------------------------------------

def _timing_phrase(days_until: int, when: str) -> str:
    if days_until == 0:
        base = "today"
    elif days_until == 1:
        base = "tomorrow"
    else:
        base = f"in {days_until} days"
    suffix = {"bmo": " before the open", "amc": " after the close"}.get(when, "")
    return base + suffix


def _build_message(symbol: str, info: dict, ctx: dict) -> str:
    ratio = ctx.get("iv_over_hv30")
    ratio_txt = f"{ratio:.1f}x recent realized vol" if ratio else "well above recent realized vol"
    return (
        f"Earnings watch: {symbol} reports {_timing_phrase(info['days_until'], info['when'])} "
        f"and its options look overpriced — implied vol is {ratio_txt} (RICH). "
        f"Per your skip-earnings rule, avoid buying premium here or consider fading it; "
        f"expect an IV crush right after the report."
    )


# --- Monitor ---------------------------------------------------------------

class EarningsCrushMonitor:
    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()
        self._wake = asyncio.Event()

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="earnings-crush-monitor")

    async def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=3)
            except (asyncio.TimeoutError, Exception):
                pass

    def request_resync(self) -> None:
        """Wake the loop so a freshly added watchlist name is screened promptly."""
        self._wake.set()

    async def _run(self) -> None:
        print(f"[earnings] screener started (poll {POLL_SECONDS:.0f}s, "
              f"lookahead {LOOKAHEAD_DAYS}d)")
        while not self._stop.is_set():
            try:
                await self._scan()
            except Exception as e:
                print(f"[earnings] scan error: {e}")
            if self._stop.is_set():
                break
            self._wake.clear()
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=POLL_SECONDS)
            except asyncio.TimeoutError:
                pass
        print("[earnings] screener stopped")

    async def _scan(self) -> None:
        watches = news.list_watches_db(active_only=True)
        if not watches:
            return
        watch_syms = {(w["symbol"] or "").upper() for w in watches}

        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            upcoming = await fetch_upcoming(client)

        in_scope = {s: upcoming[s] for s in watch_syms if s in upcoming}
        if not in_scope:
            return

        for symbol, info in in_scope.items():
            if self._stop.is_set():
                return
            if alert_exists(symbol, info["date"]):
                continue  # already flagged this earnings event
            try:
                ctx = await analysis.iv_context(symbol)
            except Exception as e:
                print(f"[earnings] {symbol} iv_context error: {e}")
                continue
            # Only flag overpriced premium — that's the IV-crush setup. FAIR/CHEAP
            # names are re-checked next scan, since IV typically ramps into the report.
            if ctx.get("verdict") != "RICH":
                continue

            message = _build_message(symbol, info, ctx)
            alert_id = insert_alert(symbol, info["date"], info["when"], ctx, message, spoken=0)
            if alert_id is None:
                continue  # raced/duplicate
            payload = {
                "kind": "earnings_iv",
                "symbol": symbol,
                "earnings_date": info["date"],
                "earnings_when": info["when"],
                "days_until": info["days_until"],
                "atm_iv": ctx.get("atm_iv"),
                "hv30": ctx.get("hv30"),
                "iv_over_hv30": ctx.get("iv_over_hv30"),
                "verdict": ctx.get("verdict"),
                "alert_id": alert_id,
            }
            delivered = await market.clients.broadcast(message, payload)
            if delivered > 0:
                mark_alert_spoken(alert_id)
            print(f"[earnings] {symbol} flagged (delivered={delivered}): "
                  f"IV/HV30={ctx.get('iv_over_hv30')} report {info['date']}")


monitor = EarningsCrushMonitor()


# --- HAL-facing tool entry point ------------------------------------------

def tool_list_earnings_alerts(limit: int = 20) -> dict:
    """Recent pre-earnings IV-crush flags (history)."""
    return {"alerts": list_recent_alerts(limit)}
