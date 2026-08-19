"""SQLite persistence: conversation store + voiceprint/alert schema.

Importing this module initializes the database and runs the one-time legacy
history migration (both idempotent).
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid

from hal.brainstem.config import CONVERSATIONS_DIR, DB_PATH, HISTORY_FILE, MAX_TITLE_CHARS


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _init_db() -> None:
    with _db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id          TEXT PRIMARY KEY,
                title       TEXT NOT NULL,
                created_at  REAL NOT NULL,
                updated_at  REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                position        INTEGER NOT NULL,
                role            TEXT NOT NULL,
                content         TEXT NOT NULL,
                created_at      REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_messages_conv
                ON messages(conversation_id, position);
            CREATE INDEX IF NOT EXISTS idx_conv_updated
                ON conversations(updated_at DESC);

            CREATE TABLE IF NOT EXISTS voiceprints (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                embedding     BLOB NOT NULL,
                sample_count  INTEGER NOT NULL DEFAULT 1,
                created_at    INTEGER NOT NULL,
                last_seen     INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_voiceprints_name
                ON voiceprints(name);

            CREATE TABLE IF NOT EXISTS ws_subscriptions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                channel     TEXT NOT NULL,
                symbol      TEXT NOT NULL,
                note        TEXT,
                created_at  REAL NOT NULL,
                active      INTEGER NOT NULL DEFAULT 1,
                UNIQUE(channel, symbol)
            );
            CREATE TABLE IF NOT EXISTS alert_rules (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                subscription_id   INTEGER NOT NULL REFERENCES ws_subscriptions(id) ON DELETE CASCADE,
                rule_type         TEXT NOT NULL,
                config            TEXT NOT NULL,
                note              TEXT,
                active            INTEGER NOT NULL DEFAULT 1,
                triggered_count   INTEGER NOT NULL DEFAULT 0,
                last_triggered_at REAL,
                cooldown_seconds  REAL NOT NULL DEFAULT 60,
                created_at        REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS alert_events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id     INTEGER NOT NULL REFERENCES alert_rules(id) ON DELETE CASCADE,
                fired_at    REAL NOT NULL,
                payload     TEXT NOT NULL,
                message     TEXT NOT NULL,
                spoken      INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_alert_rules_sub
                ON alert_rules(subscription_id);
            CREATE INDEX IF NOT EXISTS idx_alert_events_fired
                ON alert_events(fired_at DESC);

            CREATE TABLE IF NOT EXISTS news_watches (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol      TEXT NOT NULL,
                keywords    TEXT,
                note        TEXT,
                created_at  REAL NOT NULL,
                active      INTEGER NOT NULL DEFAULT 1,
                last_polled_at REAL,
                UNIQUE(symbol)
            );
            CREATE TABLE IF NOT EXISTS news_articles (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                watch_id     INTEGER NOT NULL REFERENCES news_watches(id) ON DELETE CASCADE,
                symbol       TEXT NOT NULL,
                title        TEXT NOT NULL,
                url          TEXT NOT NULL,
                source       TEXT,
                published_at REAL,
                summary      TEXT,
                seen_at      REAL NOT NULL,
                spoken       INTEGER NOT NULL DEFAULT 0,
                UNIQUE(watch_id, url)
            );
            CREATE INDEX IF NOT EXISTS idx_news_articles_watch
                ON news_articles(watch_id, seen_at DESC);

            CREATE TABLE IF NOT EXISTS earnings_iv_alerts (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol        TEXT NOT NULL,
                earnings_date TEXT NOT NULL,
                earnings_when TEXT,
                atm_iv        REAL,
                hv30          REAL,
                iv_over_hv30  REAL,
                verdict       TEXT,
                message       TEXT NOT NULL,
                fired_at      REAL NOT NULL,
                spoken        INTEGER NOT NULL DEFAULT 0,
                UNIQUE(symbol, earnings_date)
            );
            CREATE INDEX IF NOT EXISTS idx_earnings_iv_alerts_fired
                ON earnings_iv_alerts(fired_at DESC);

            CREATE TABLE IF NOT EXISTS mcp_servers (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                slug        TEXT NOT NULL UNIQUE,
                transport   TEXT NOT NULL,
                command     TEXT,
                args        TEXT,
                url         TEXT,
                env         TEXT,
                headers     TEXT,
                enabled     INTEGER NOT NULL DEFAULT 1,
                created_at  REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS mcp_oauth (
                server_id   INTEGER PRIMARY KEY REFERENCES mcp_servers(id) ON DELETE CASCADE,
                client_info TEXT,
                tokens      TEXT,
                updated_at  REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS broker_orders (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                client_order_id TEXT,
                broker_order_id TEXT,
                symbol          TEXT NOT NULL,
                asset_class     TEXT NOT NULL,
                side            TEXT NOT NULL,
                qty             TEXT,
                order_type      TEXT,
                limit_price     REAL,
                status          TEXT,
                mode            TEXT,
                paper           INTEGER NOT NULL DEFAULT 1,
                submitted_at    REAL NOT NULL,
                detail          TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_broker_orders_submitted
                ON broker_orders(submitted_at DESC);
            -- Every gate decision on the order path, ALLOWED or BLOCKED.
            -- broker_orders records what was submitted; this records what was
            -- considered — the rejections that leave no other trace. Without it
            -- "why didn't HAL take that trade?" is unanswerable after the fact.
            CREATE TABLE IF NOT EXISTS decisions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                decided_at REAL NOT NULL,
                stage      TEXT NOT NULL,   -- 'rules_gate' | 'risk_gate' | 'committee'
                symbol     TEXT,
                allowed    INTEGER NOT NULL,
                reason     TEXT,            -- human-readable; '' when allowed
                detail     TEXT             -- JSON context
            );
            CREATE INDEX IF NOT EXISTS idx_decisions_at
                ON decisions(decided_at DESC);
            CREATE INDEX IF NOT EXISTS idx_decisions_symbol
                ON decisions(symbol, decided_at DESC);
            CREATE TABLE IF NOT EXISTS managed_exits (
                symbol      TEXT PRIMARY KEY,
                underlying  TEXT,
                qty         TEXT,
                stop_price  REAL,
                tp_price    REAL,
                created_at  REAL NOT NULL
            );
            """
        )


_init_db()
print(f"[boot] DB: {DB_PATH}")


def arm_managed_exit(symbol: str, underlying: str, qty, stop_price: float,
                     tp_price: float) -> None:
    """Register/replace a HAL-managed exit for an option position. `symbol` is
    the OCC option symbol Alpaca reports in positions."""
    with _db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO managed_exits "
            "(symbol, underlying, qty, stop_price, tp_price, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (symbol.upper(), (underlying or "").upper(), str(qty),
             float(stop_price or 0), float(tp_price or 0), time.time()),
        )


def disarm_managed_exit(key: str) -> None:
    """Remove a managed exit by OCC symbol or underlying (so a panel close on
    the underlying clears its option exit too)."""
    k = (key or "").upper()
    with _db() as conn:
        conn.execute(
            "DELETE FROM managed_exits WHERE symbol=? OR underlying=?", (k, k))


def list_managed_exits() -> list[dict]:
    with _db() as conn:
        rows = conn.execute(
            "SELECT symbol, underlying, qty, stop_price, tp_price, created_at "
            "FROM managed_exits"
        ).fetchall()
    return [dict(r) for r in rows]


def log_broker_order(spec: dict, result: dict, mode: str, paper: bool) -> None:
    """Record a submitted Alpaca order. `spec` is the prepared order, `result`
    is the broker's response (see broker._order_to_dict)."""
    with _db() as conn:
        conn.execute(
            """
            INSERT INTO broker_orders
                (client_order_id, broker_order_id, symbol, asset_class, side, qty,
                 order_type, limit_price, status, mode, paper, submitted_at, detail)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                result.get("client_order_id"),
                result.get("id"),
                spec.get("symbol"),
                spec.get("asset_class"),
                spec.get("side"),
                str(spec.get("qty")),
                spec.get("type"),
                spec.get("limit_price"),
                result.get("status"),
                mode,
                1 if paper else 0,
                time.time(),
                json.dumps(result, default=str),
            ),
        )


def log_decision(stage: str, symbol: str | None, allowed: bool,
                 reason: str = "", detail: dict | None = None) -> None:
    """Record a gate decision. Never raises: an audit write must not be able to
    break the order path it is auditing."""
    try:
        with _db() as conn:
            conn.execute(
                "INSERT INTO decisions (decided_at, stage, symbol, allowed, reason, detail) "
                "VALUES (?,?,?,?,?,?)",
                (time.time(), stage, (symbol or "").upper() or None,
                 1 if allowed else 0, reason,
                 json.dumps(detail, default=str) if detail else None),
            )
    except Exception as e:  # pragma: no cover
        print(f"[decisions] log failed ({stage}/{symbol}): {type(e).__name__}: {e}")


def list_decisions(limit: int = 50, symbol: str | None = None,
                   blocked_only: bool = False) -> list[dict]:
    """Recent gate decisions, newest first — the 'why didn't HAL trade?' trail."""
    q = "SELECT * FROM decisions"
    where, args = [], []
    if symbol:
        where.append("symbol = ?")
        args.append(symbol.upper())
    if blocked_only:
        where.append("allowed = 0")
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY decided_at DESC LIMIT ?"
    args.append(limit)
    with _db() as conn:
        return [dict(r) for r in conn.execute(q, args).fetchall()]


def _new_conversation_obj(title: str = "New conversation") -> dict:
    now = time.time()
    return {
        "id": f"c_{int(now)}_{uuid.uuid4().hex[:6]}",
        "title": title,
        "created_at": now,
        "updated_at": now,
        "messages": [],
    }


def list_conversations() -> list[dict]:
    with _db() as conn:
        rows = conn.execute(
            """
            SELECT c.id, c.title, c.created_at, c.updated_at,
                   (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS message_count
            FROM conversations c
            ORDER BY c.updated_at DESC
            """
        ).fetchall()
    return [dict(r) for r in rows]


def load_conversation(cid: str) -> dict | None:
    with _db() as conn:
        row = conn.execute(
            "SELECT id, title, created_at, updated_at FROM conversations WHERE id = ?",
            (cid,),
        ).fetchone()
        if not row:
            return None
        msg_rows = conn.execute(
            "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY position",
            (cid,),
        ).fetchall()
    return {
        "id": row["id"],
        "title": row["title"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "messages": [{"role": m["role"], "content": m["content"]} for m in msg_rows],
    }


def save_conversation(conv: dict) -> None:
    """Upsert conversation + replace its messages atomically."""
    conv["updated_at"] = time.time()
    # Auto-title from first user message if still default.
    if conv.get("title") in (None, "", "New conversation"):
        for m in conv.get("messages", []):
            if m.get("role") == "user" and m.get("content"):
                first_line = str(m["content"]).strip().split("\n", 1)[0]
                conv["title"] = first_line[:MAX_TITLE_CHARS] or "Untitled"
                break
    with _db() as conn:
        conn.execute(
            """
            INSERT INTO conversations (id, title, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                updated_at = excluded.updated_at
            """,
            (conv["id"], conv.get("title", "Untitled"), conv["created_at"], conv["updated_at"]),
        )
        # Replace messages by deleting and re-inserting. Fine for our scale
        # (≤ MAX_HISTORY_MESSAGES per conversation).
        conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conv["id"],))
        now = time.time()
        rows = [
            (conv["id"], i, m.get("role", "user"), str(m.get("content", "")), now)
            for i, m in enumerate(conv.get("messages", []))
        ]
        if rows:
            conn.executemany(
                "INSERT INTO messages (conversation_id, position, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
                rows,
            )


def delete_conversation(cid: str) -> bool:
    with _db() as conn:
        cur = conn.execute("DELETE FROM conversations WHERE id = ?", (cid,))
        return cur.rowcount > 0


def rename_conversation(cid: str, new_title: str) -> bool:
    title = (new_title or "Untitled")[:MAX_TITLE_CHARS]
    with _db() as conn:
        cur = conn.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
            (title, time.time(), cid),
        )
        return cur.rowcount > 0


# --- MCP servers -----------------------------------------------------------
# Persisted config for user-added Model Context Protocol servers. args/env/
# headers are stored as JSON strings; mcp_client.py parses them.

_MCP_COLS = (
    "id, name, slug, transport, command, args, url, env, headers, "
    "enabled, created_at"
)


def list_mcp_servers(enabled_only: bool = False) -> list[dict]:
    with _db() as conn:
        q = f"SELECT {_MCP_COLS} FROM mcp_servers"
        if enabled_only:
            q += " WHERE enabled = 1"
        q += " ORDER BY created_at ASC"
        return [dict(r) for r in conn.execute(q).fetchall()]


def get_mcp_server(server_id: int) -> dict | None:
    with _db() as conn:
        row = conn.execute(
            f"SELECT {_MCP_COLS} FROM mcp_servers WHERE id = ?", (server_id,)
        ).fetchone()
        return dict(row) if row else None


def get_mcp_server_by_slug(slug: str) -> dict | None:
    with _db() as conn:
        row = conn.execute(
            f"SELECT {_MCP_COLS} FROM mcp_servers WHERE slug = ?", (slug,)
        ).fetchone()
        return dict(row) if row else None


def insert_mcp_server(
    name: str,
    slug: str,
    transport: str,
    command: str = "",
    args: str = "[]",
    url: str = "",
    env: str = "{}",
    headers: str = "{}",
    enabled: bool = True,
) -> int:
    now = time.time()
    with _db() as conn:
        cur = conn.execute(
            "INSERT INTO mcp_servers(name, slug, transport, command, args, url, "
            "env, headers, enabled, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?) RETURNING id",
            (name, slug, transport, command, args, url, env, headers,
             1 if enabled else 0, now),
        )
        return cur.fetchone()[0]


def delete_mcp_server(server_id: int) -> bool:
    with _db() as conn:
        cur = conn.execute("DELETE FROM mcp_servers WHERE id = ?", (server_id,))
        return cur.rowcount > 0


def set_mcp_enabled(server_id: int, enabled: bool) -> bool:
    with _db() as conn:
        cur = conn.execute(
            "UPDATE mcp_servers SET enabled = ? WHERE id = ?",
            (1 if enabled else 0, server_id),
        )
        return cur.rowcount > 0


def get_mcp_oauth(server_id: int) -> dict | None:
    with _db() as conn:
        row = conn.execute(
            "SELECT server_id, client_info, tokens, updated_at "
            "FROM mcp_oauth WHERE server_id = ?",
            (server_id,),
        ).fetchone()
        return dict(row) if row else None


def _upsert_mcp_oauth(server_id: int, *, client_info: str | None = None,
                      tokens: str | None = None) -> None:
    """Upsert one column of the oauth row, leaving the other intact."""
    now = time.time()
    with _db() as conn:
        existing = conn.execute(
            "SELECT client_info, tokens FROM mcp_oauth WHERE server_id = ?",
            (server_id,),
        ).fetchone()
        if existing:
            ci = client_info if client_info is not None else existing["client_info"]
            tk = tokens if tokens is not None else existing["tokens"]
            conn.execute(
                "UPDATE mcp_oauth SET client_info = ?, tokens = ?, updated_at = ? "
                "WHERE server_id = ?",
                (ci, tk, now, server_id),
            )
        else:
            conn.execute(
                "INSERT INTO mcp_oauth(server_id, client_info, tokens, updated_at) "
                "VALUES (?,?,?,?)",
                (server_id, client_info, tokens, now),
            )


def set_mcp_oauth_client(server_id: int, client_info: str) -> None:
    _upsert_mcp_oauth(server_id, client_info=client_info)


def set_mcp_oauth_tokens(server_id: int, tokens: str) -> None:
    _upsert_mcp_oauth(server_id, tokens=tokens)


def _migrate_legacy_history() -> None:
    """Migrate pre-DB storage (single JSON file or per-conversation JSON files)
    into SQLite on first boot. Idempotent."""
    # Skip if DB already has conversations
    with _db() as conn:
        existing = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
    if existing > 0:
        return

    # 1) Per-conversation JSON files
    migrated = 0
    if CONVERSATIONS_DIR.exists():
        for path in CONVERSATIONS_DIR.glob("c_*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    continue
                save_conversation(
                    {
                        "id": data.get("id") or f"c_{int(time.time())}_{uuid.uuid4().hex[:6]}",
                        "title": data.get("title") or "Untitled",
                        "created_at": data.get("created_at", time.time()),
                        "updated_at": data.get("updated_at", time.time()),
                        "messages": data.get("messages", []),
                    }
                )
                path.rename(path.with_suffix(".json.migrated"))
                migrated += 1
            except (json.JSONDecodeError, OSError) as e:
                print(f"[conv] Migration failed for {path.name}: {e}")

    # 2) Original single hal_history.json (only if no per-conversation files migrated)
    if migrated == 0 and HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                messages = json.load(f)
            if isinstance(messages, list) and messages:
                conv = _new_conversation_obj("Legacy history")
                conv["messages"] = messages
                save_conversation(conv)
                HISTORY_FILE.rename(HISTORY_FILE.with_suffix(".json.migrated"))
                migrated += 1
        except (json.JSONDecodeError, OSError) as e:
            print(f"[conv] Legacy migration failed: {e}")

    if migrated:
        print(f"[conv] Migrated {migrated} conversation(s) into SQLite")


_migrate_legacy_history()
