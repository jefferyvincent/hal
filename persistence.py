"""SQLite persistence: conversation store + voiceprint/alert schema.

Importing this module initializes the database and runs the one-time legacy
history migration (both idempotent).
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid

from config import CONVERSATIONS_DIR, DB_PATH, HISTORY_FILE, MAX_TITLE_CHARS


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
            """
        )


_init_db()
print(f"[boot] DB: {DB_PATH}")


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
