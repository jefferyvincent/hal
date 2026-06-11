"""Journal RAG layer for HAL-Vault.

Embeds vault notes via nomic-embed-text (Ollama) and stores them in LanceDB.
Provides journal_search() for semantic search with frontmatter filters.

LanceDB and watchdog are optional dependencies — if they're not installed,
this module degrades gracefully: ingest() is a no-op and search() returns [].

Install:
    pip install lancedb watchdog
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import threading
from pathlib import Path
from typing import Any

import httpx

from hal.brainstem.config import VAULT_DIR, RAG_DB_DIR, OLLAMA_URL
from hal.hippocampus.vault import all_notes

log = logging.getLogger("hal.rag")

_EMBED_MODEL = "nomic-embed-text"
_EMBED_URL = OLLAMA_URL.replace("/api/chat", "/api/embeddings")
_TABLE_NAME = "vault_notes"

# ---------------------------------------------------------------------------
# LanceDB — imported lazily so missing dep doesn't crash the server
# ---------------------------------------------------------------------------

try:
    import lancedb  # type: ignore
    import pyarrow as pa  # type: ignore

    _LANCE_OK = True
except ImportError:
    lancedb = None  # type: ignore
    pa = None  # type: ignore
    _LANCE_OK = False


def _get_table():
    """Open (or create) the LanceDB table. Returns None if lancedb unavailable."""
    if not _LANCE_OK:
        return None
    db = lancedb.connect(str(RAG_DB_DIR / "vault.lance"))
    schema = pa.schema([
        pa.field("id", pa.string()),
        pa.field("rel_path", pa.string()),
        pa.field("type", pa.string()),
        pa.field("symbol", pa.string()),
        pa.field("status", pa.string()),
        pa.field("side", pa.string()),
        pa.field("strategy", pa.string()),
        pa.field("opened", pa.string()),
        pa.field("closed", pa.string()),
        pa.field("rules_passed", pa.string()),
        pa.field("body_hash", pa.string()),
        pa.field("text", pa.string()),
        pa.field("vector", pa.list_(pa.float32(), 768)),
    ])
    if _TABLE_NAME not in db.table_names():
        return db.create_table(_TABLE_NAME, schema=schema)
    return db.open_table(_TABLE_NAME)


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

def _embed_sync(text: str) -> list[float] | None:
    """Call Ollama embeddings endpoint synchronously. Returns None on failure."""
    try:
        r = httpx.post(
            _EMBED_URL,
            json={"model": _EMBED_MODEL, "prompt": text},
            timeout=30,
        )
        r.raise_for_status()
        return r.json().get("embedding")
    except Exception as e:
        log.warning("embed failed: %s", e)
        return None


async def _embed(text: str) -> list[float] | None:
    """Async wrapper around the embedding call (runs in a thread)."""
    return await asyncio.get_event_loop().run_in_executor(None, _embed_sync, text)


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------

def _note_id(rel_path: str) -> str:
    return hashlib.sha1(rel_path.encode()).hexdigest()[:16]


def _fm_str(fm: dict, key: str) -> str:
    v = fm.get(key)
    return "" if v is None else str(v)


def ingest_note_sync(note: dict) -> bool:
    """Embed one note and upsert into LanceDB. Returns True if upserted."""
    table = _get_table()
    if table is None:
        return False

    fm = note["frontmatter"]
    body = note["body"].strip()
    rel_path = note["rel_path"]
    body_hash = hashlib.sha1(body.encode()).hexdigest()[:16]

    # Skip re-embedding if body hasn't changed
    try:
        existing = table.search().where(
            f"id = '{_note_id(rel_path)}'"
        ).to_list()
        if existing and existing[0].get("body_hash") == body_hash:
            return False
    except Exception:
        pass

    # Embed title + body for richer retrieval
    title = Path(rel_path).stem
    embed_text = f"{title}\n\n{body}" if body else title
    vec = _embed_sync(embed_text)
    if vec is None:
        return False

    row = {
        "id": _note_id(rel_path),
        "rel_path": rel_path,
        "type": _fm_str(fm, "type"),
        "symbol": _fm_str(fm, "symbol"),
        "status": _fm_str(fm, "status"),
        "side": _fm_str(fm, "side"),
        "strategy": _fm_str(fm, "strategy"),
        "opened": _fm_str(fm, "opened"),
        "closed": _fm_str(fm, "closed"),
        "rules_passed": _fm_str(fm, "rules_passed"),
        "body_hash": body_hash,
        "text": embed_text[:2000],
        "vector": vec,
    }
    try:
        table.delete(f"id = '{row['id']}'")
        table.add([row])
        return True
    except Exception as e:
        log.warning("lancedb upsert failed: %s", e)
        return False


def ingest_vault() -> int:
    """Embed all vault notes. Returns count of upserted notes."""
    notes = all_notes()
    count = 0
    for note in notes:
        if ingest_note_sync(note):
            count += 1
    log.info("vault ingest: %d/%d notes updated", count, len(notes))
    return count


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

async def journal_search(
    query: str,
    symbol: str | None = None,
    type: str | None = None,
    status: str | None = None,
    k: int = 5,
) -> list[dict[str, Any]]:
    """Semantic search over vault notes with optional frontmatter filters.

    Returns up to `k` results as dicts with keys:
      rel_path, type, symbol, status, strategy, opened, text, score
    """
    table = _get_table()
    if table is None:
        log.debug("journal_search: lancedb unavailable")
        return []

    vec = await _embed(query)
    if vec is None:
        return []

    # Build a where clause for metadata filters
    clauses = []
    if symbol:
        clauses.append(f"symbol = '{symbol.upper()}'")
    if type:
        clauses.append(f"type = '{type}'")
    if status:
        clauses.append(f"status = '{status}'")
    where = " AND ".join(clauses) if clauses else None

    try:
        q = table.search(vec).limit(k)
        if where:
            q = q.where(where)
        rows = q.to_list()
    except Exception as e:
        log.warning("journal_search query failed: %s", e)
        return []

    results = []
    for row in rows:
        results.append({
            "rel_path": row.get("rel_path", ""),
            "type": row.get("type", ""),
            "symbol": row.get("symbol", ""),
            "status": row.get("status", ""),
            "strategy": row.get("strategy", ""),
            "opened": row.get("opened", ""),
            "text": row.get("text", "")[:500],
            "score": float(row.get("_distance", 0)),
        })
    return results


# ---------------------------------------------------------------------------
# File watcher (background thread) — incremental ingest on vault changes
# ---------------------------------------------------------------------------

try:
    from watchdog.observers import Observer  # type: ignore
    from watchdog.events import FileSystemEventHandler  # type: ignore

    _WATCHDOG_OK = True
except ImportError:
    Observer = None  # type: ignore
    FileSystemEventHandler = object  # type: ignore
    _WATCHDOG_OK = False


class _VaultHandler(FileSystemEventHandler):  # type: ignore
    def on_modified(self, event):
        self._handle(event.src_path)

    def on_created(self, event):
        self._handle(event.src_path)

    def _handle(self, src_path: str):
        p = Path(src_path)
        if p.suffix != ".md":
            return
        # Skip Obsidian temp files
        if p.name.startswith("."):
            return
        try:
            rel = str(p.relative_to(VAULT_DIR)).replace("\\", "/")
        except ValueError:
            return
        skip = ("_attachments/", "Dashboards/", "Templates/")
        if any(rel.startswith(s) for s in skip):
            return
        from hal.hippocampus.vault import read_note
        note = read_note(rel)
        if note:
            ingest_note_sync(note)
            log.debug("rag: re-indexed %s", rel)


_observer: Any = None


def start_watcher():
    """Start the background file-watcher. Call once at server startup."""
    global _observer
    if not _WATCHDOG_OK or not _LANCE_OK:
        log.info("rag watcher not started (missing watchdog or lancedb)")
        return
    if _observer is not None:
        return
    handler = _VaultHandler()
    _observer = Observer()
    _observer.schedule(handler, str(VAULT_DIR), recursive=True)
    t = threading.Thread(target=_observer.start, daemon=True)
    t.start()
    log.info("rag vault watcher started on %s", VAULT_DIR)


def stop_watcher():
    global _observer
    if _observer is not None:
        _observer.stop()
        _observer = None
