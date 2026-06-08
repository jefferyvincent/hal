"""Per-symbol news monitoring and alert delivery for HAL.

A lightweight companion to market.py. Where market.py owns a live options
WebSocket, this module polls per-symbol news RSS feeds on an interval and
speaks any *new* headline involving a watched symbol. It deliberately reuses
market.clients (the ClientRegistry) so news alerts are spoken and recorded the
exact same way price alerts are — no second delivery path.

Watch list lives in the news_watches table; news_articles is both the dedupe
cache and the alert history (and the source for missed-while-away replay).

Feeds (no API key required):
  - Yahoo Finance per-symbol RSS: feeds.finance.yahoo.com/rss/2.0/headline?s=SYM
  - Google News RSS (fallback):   news.google.com/rss/search?q=SYM+stock

The first poll of a brand-new watch seeds whatever headlines already exist as
"seen" silently, so Jeffery only ever hears genuinely new news, never a backlog
dump.
"""
from __future__ import annotations

import asyncio
import re
import sqlite3
import time
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote_plus, urlsplit
from xml.etree import ElementTree as ET

import httpx

from hal.sensory import market  # reuse market.clients for spoken delivery + recording


# Filled by server via configure() at boot; avoids a circular import.
DB_PATH: Optional[Path] = None
POLL_SECONDS: float = 300.0
PRIMARY_FEED: str = "yahoo"  # "yahoo" | "google"

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
_SYMBOL_RE = re.compile(r"^[A-Z0-9.\-]{1,12}$")
_TAG_RE = re.compile(r"<[^>]+>")


def configure(db_path: Path, poll_seconds: float = 300.0, primary_feed: str = "yahoo") -> None:
    global DB_PATH, POLL_SECONDS, PRIMARY_FEED
    DB_PATH = db_path
    POLL_SECONDS = float(poll_seconds)
    PRIMARY_FEED = primary_feed if primary_feed in ("yahoo", "google") else "yahoo"


# --- DB helpers ------------------------------------------------------------

def _db() -> sqlite3.Connection:
    if DB_PATH is None:
        raise RuntimeError("news.configure() not called")
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def list_watches_db(active_only: bool = True) -> list[dict]:
    with _db() as conn:
        q = (
            "SELECT w.id, w.symbol, w.keywords, w.note, w.created_at, w.active, "
            "       w.last_polled_at, "
            "       (SELECT COUNT(*) FROM news_articles a WHERE a.watch_id = w.id) "
            "         AS article_count "
            "FROM news_watches w"
        )
        if active_only:
            q += " WHERE w.active = 1"
        q += " ORDER BY w.created_at DESC"
        return [dict(r) for r in conn.execute(q).fetchall()]


def insert_watch(symbol: str, keywords: str = "", note: str = "") -> int:
    now = time.time()
    with _db() as conn:
        cur = conn.execute(
            "INSERT INTO news_watches(symbol, keywords, note, created_at, active) "
            "VALUES (?,?,?,?,1) "
            "ON CONFLICT(symbol) DO UPDATE SET active=1, "
            "  keywords=excluded.keywords, note=excluded.note "
            "RETURNING id",
            (symbol, keywords, note, now),
        )
        return cur.fetchone()[0]


def deactivate_watch(watch_id: int) -> bool:
    with _db() as conn:
        cur = conn.execute("UPDATE news_watches SET active=0 WHERE id=?", (watch_id,))
        return cur.rowcount > 0


def deactivate_watch_by_symbol(symbol: str) -> bool:
    with _db() as conn:
        cur = conn.execute(
            "UPDATE news_watches SET active=0 WHERE symbol=? AND active=1",
            (symbol,),
        )
        return cur.rowcount > 0


def mark_polled(watch_id: int) -> None:
    with _db() as conn:
        conn.execute(
            "UPDATE news_watches SET last_polled_at=? WHERE id=?",
            (time.time(), watch_id),
        )


def insert_article(watch_id: int, symbol: str, item: dict, spoken: int = 0) -> Optional[int]:
    """Insert a headline. Returns the new row id, or None if this (watch, url)
    was already seen (UNIQUE conflict) — that's the dedupe."""
    with _db() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO news_articles"
            "(watch_id, symbol, title, url, source, published_at, summary, seen_at, spoken) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                watch_id, symbol, item["title"], item["url"], item.get("source"),
                item.get("published_at"), item.get("summary"), time.time(), spoken,
            ),
        )
        return cur.lastrowid if cur.rowcount else None


def mark_article_spoken(article_id: int) -> None:
    with _db() as conn:
        conn.execute("UPDATE news_articles SET spoken=1 WHERE id=?", (article_id,))


def latest_article_for_symbol(symbol: str) -> Optional[dict]:
    with _db() as conn:
        row = conn.execute(
            "SELECT title, url, seen_at FROM news_articles WHERE symbol = ? "
            "ORDER BY seen_at DESC LIMIT 1",
            (symbol,),
        ).fetchone()
        return dict(row) if row else None


def list_recent_articles(limit: int = 20) -> list[dict]:
    with _db() as conn:
        rows = conn.execute(
            "SELECT id, watch_id, symbol, title, url, source, published_at, "
            "       summary, seen_at, spoken "
            "FROM news_articles ORDER BY seen_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def list_unspoken_articles(limit: int = 20) -> list[dict]:
    """Headlines that were recorded but never announced (no app session was
    connected when they fired). Oldest first for chronological replay."""
    with _db() as conn:
        rows = conn.execute(
            "SELECT id, symbol, title, url, source, seen_at "
            "FROM news_articles WHERE spoken = 0 "
            "ORDER BY seen_at ASC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


# --- Feed fetch + parse ----------------------------------------------------

def _yahoo_url(symbol: str) -> str:
    return (
        f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={quote_plus(symbol)}"
        f"&region=US&lang=en-US"
    )


def _google_url(symbol: str) -> str:
    q = quote_plus(f"{symbol} stock")
    return f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"


def _host(url: str) -> str:
    try:
        return urlsplit(url).netloc or ""
    except Exception:
        return ""


def _parse_date(raw: Optional[str]) -> Optional[float]:
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw).timestamp()
    except Exception:
        return None


def _clean(text: str, limit: int = 280) -> str:
    text = _TAG_RE.sub("", text or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text[:limit]


def _parse_rss(content: bytes) -> list[dict]:
    """Parse RSS 2.0 bytes into a list of headline dicts. Pass bytes (not str)
    so ElementTree honours the document's own encoding declaration."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []
    channel = root.find("channel")
    nodes = channel.findall("item") if channel is not None else root.findall(".//item")
    out: list[dict] = []
    for it in nodes:
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        if not title or not link:
            continue
        src_node = it.find("source")
        source = (
            src_node.text.strip()
            if src_node is not None and src_node.text
            else _host(link)
        )
        out.append({
            "title": title,
            "url": link,
            "source": source,
            "published_at": _parse_date(it.findtext("pubDate")),
            "summary": _clean(it.findtext("description") or ""),
        })
    return out


async def _fetch_rss(client: httpx.AsyncClient, url: str) -> list[dict]:
    try:
        r = await client.get(url)
        r.raise_for_status()
        return _parse_rss(r.content)
    except Exception as e:
        print(f"[news] fetch failed {url}: {e}")
        return []


async def fetch_symbol_news(client: httpx.AsyncClient, symbol: str) -> list[dict]:
    """Primary feed, falling back to the other source if it yields nothing."""
    first, second = (
        (_yahoo_url, _google_url) if PRIMARY_FEED == "yahoo"
        else (_google_url, _yahoo_url)
    )
    items = await _fetch_rss(client, first(symbol))
    if not items:
        items = await _fetch_rss(client, second(symbol))
    return items


def _parse_keywords(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    return [k.strip().lower() for k in raw.split(",") if k.strip()]


def _matches_keywords(item: dict, keywords: list[str]) -> bool:
    hay = f"{item.get('title', '')} {item.get('summary', '')}".lower()
    return any(k in hay for k in keywords)


# --- Monitor ---------------------------------------------------------------

class NewsMonitor:
    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()
        self._wake = asyncio.Event()

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="news-monitor")

    async def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=3)
            except (asyncio.TimeoutError, Exception):
                pass

    def request_resync(self) -> None:
        """Wake the loop so a newly added watch gets seeded promptly."""
        self._wake.set()

    async def _run(self) -> None:
        print(f"[news] monitor started (poll {POLL_SECONDS:.0f}s, feed {PRIMARY_FEED})")
        while not self._stop.is_set():
            try:
                await self._poll_all()
            except Exception as e:
                print(f"[news] poll error: {e}")
            if self._stop.is_set():
                break
            self._wake.clear()
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=POLL_SECONDS)
            except asyncio.TimeoutError:
                pass
        print("[news] monitor stopped")

    async def _poll_all(self) -> None:
        watches = list_watches_db(active_only=True)
        if not watches:
            return
        async with httpx.AsyncClient(
            timeout=15.0, follow_redirects=True, headers={"User-Agent": _UA}
        ) as client:
            for w in watches:
                if self._stop.is_set():
                    return
                try:
                    await self._poll_watch(client, w)
                except Exception as e:
                    print(f"[news] watch {w.get('symbol')} error: {e}")

    async def _poll_watch(self, client: httpx.AsyncClient, w: dict) -> None:
        symbol = w["symbol"]
        first_poll = w.get("last_polled_at") is None
        items = await fetch_symbol_news(client, symbol)

        if first_poll:
            # Seed everything currently in the feed as already-seen, silently.
            for it in items:
                insert_article(w["id"], symbol, it, spoken=1)
            mark_polled(w["id"])
            print(f"[news] seeded {len(items)} headline(s) for {symbol}")
            return

        keywords = _parse_keywords(w.get("keywords"))
        for it in items:
            if keywords and not _matches_keywords(it, keywords):
                continue
            art_id = insert_article(w["id"], symbol, it, spoken=0)
            if art_id is None:
                continue  # already seen
            message = f"News on {symbol}: {it['title']}"
            payload = {
                "kind": "news",
                "symbol": symbol,
                "title": it["title"],
                "url": it["url"],
                "source": it.get("source"),
                "article_id": art_id,
            }
            delivered = await market.clients.broadcast(message, payload)
            if delivered > 0:
                mark_article_spoken(art_id)
            print(f"[news] {symbol} alert (delivered={delivered}): {it['title']}")
        mark_polled(w["id"])


monitor = NewsMonitor()


# --- HAL-facing tool entry points -----------------------------------------

def tool_add_news_watch(symbol: str, keywords: str = "", note: str = "") -> dict:
    symbol = (symbol or "").upper().strip()
    if not symbol:
        return {"error": "symbol is required"}
    if not _SYMBOL_RE.match(symbol):
        return {"error": f"invalid symbol {symbol!r} (letters/digits/.- only)"}
    watch_id = insert_watch(symbol, (keywords or "").strip(), (note or "").strip())
    monitor.request_resync()
    return {"watch_id": watch_id, "symbol": symbol, "keywords": keywords}


def tool_list_news_watches() -> dict:
    return {"watches": list_watches_db(active_only=True)}


def tool_remove_news_watch(watch_id: int = 0, symbol: str = "") -> dict:
    """Stop watching news. Accepts either a watch_id or a ticker symbol."""
    symbol = (symbol or "").upper().strip()
    if symbol:
        if deactivate_watch_by_symbol(symbol):
            return {"deactivated": symbol}
        return {"error": f"no active news watch for {symbol}"}
    if watch_id:
        if deactivate_watch(watch_id):
            return {"deactivated": watch_id}
        return {"error": f"no news watch with id {watch_id}"}
    return {"error": "provide a symbol or watch_id to remove"}


def tool_list_news_history(limit: int = 20) -> dict:
    return {"articles": list_recent_articles(limit)}
