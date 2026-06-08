"""Cache-Augmented Generation (CAG) context for HAL.

Loads "always-relevant" vault content — rules, open trades, watchlist,
theses — into a compact, stable text block that gets injected into the
system prompt prefix each turn.

Because Ollama caches the KV of any unchanged prompt prefix, a stable
block here means the model doesn't re-process this content on every turn;
it reuses the cached KV state. That is the CAG pattern.

The block is rebuilt only when vault files actually change (checked via
mtime fingerprint). In practice it stays stable for most turns, so cache
hits are the norm.

Public API
----------
get_context() -> str   -- returns the formatted context block (cached)
invalidate()           -- force a rebuild on next get_context() call
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from hal.brainstem.config import VAULT_DIR
from hal.hippocampus.vault import list_notes, read_note

# ---------------------------------------------------------------------------
# Fingerprint — rebuild only when vault files change
# ---------------------------------------------------------------------------

_WATCH_FOLDERS = ["Rules", "Watchlist", "Theses", "Journal"]
_cached_block: str = ""
_cached_fingerprint: str = ""


def _fingerprint() -> str:
    """Hash the mtimes of all relevant vault files. Changes → cache miss."""
    parts = []
    for folder in _WATCH_FOLDERS:
        base = VAULT_DIR / folder
        if not base.exists():
            continue
        for p in sorted(base.rglob("*.md")):
            parts.append(f"{p}:{p.stat().st_mtime}")
    return hashlib.md5("|".join(parts).encode()).hexdigest()


def invalidate() -> None:
    global _cached_fingerprint
    _cached_fingerprint = ""


# ---------------------------------------------------------------------------
# Formatters — each returns a compact markdown section
# ---------------------------------------------------------------------------

def _fmt_rules() -> str:
    note = read_note("Rules/trading-rules.md")
    if not note:
        return ""
    # Extract just the yaml block — that's the gate HAL needs
    import re
    m = re.search(r"```ya?ml\s*\n(.*?)```", note["body"], re.DOTALL)
    if not m:
        return ""
    lines = ["## Trading Rules (gate)"]
    lines.append("```yaml")
    lines.append(m.group(1).strip())
    lines.append("```")
    return "\n".join(lines)


def _fmt_open_trades() -> str:
    # Check both Journal and Trade-Ideas for open trades
    notes = list_notes("Journal", type="trade", status="open")
    notes += list_notes("Trade-Ideas", type="trade", status="open")
    if not notes:
        return "## Open Trades\n_None._"
    lines = ["## Open Trades"]
    for n in sorted(notes, key=lambda x: x["frontmatter"].get("opened", ""), reverse=True):
        fm = n["frontmatter"]
        sym = fm.get("symbol", "?")
        strat = fm.get("strategy", "?")
        opened = fm.get("opened", "?")
        entry = fm.get("entry")
        entry_str = f" @ ${entry}" if entry else ""
        lines.append(f"- **{sym}** {strat}{entry_str} (opened {opened})")
    return "\n".join(lines)


def _fmt_watchlist() -> str:
    notes = list_notes("Watchlist", type="watch", status="watching")
    if not notes:
        return "## Watchlist\n_Empty._"
    lines = ["## Watchlist"]
    for n in notes:
        fm = n["frontmatter"]
        sym = fm.get("symbol", "?")
        trigger = fm.get("trigger", "?")
        lines.append(f"- **{sym}**: {trigger}")
    return "\n".join(lines)


def _fmt_theses() -> str:
    notes = list_notes("Theses")
    if not notes:
        return ""
    lines = ["## Active Theses"]
    for n in sorted(notes, key=lambda x: x["frontmatter"].get("conviction", ""), reverse=True):
        fm = n["frontmatter"]
        sym = fm.get("symbol", "?")
        conviction = fm.get("conviction", "?")
        # First sentence of body as the one-liner
        body = n["body"].strip()
        # Skip header lines to find the first real sentence
        first = ""
        for line in body.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("##"):
                first = line[:120]
                break
        lines.append(f"- **{sym}** ({conviction} conviction): {first}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_context() -> str:
    """Return the CAG context block, rebuilt only when vault files change."""
    global _cached_block, _cached_fingerprint

    fp = _fingerprint()
    if fp == _cached_fingerprint and _cached_block:
        return _cached_block

    sections = []
    rules = _fmt_rules()
    if rules:
        sections.append(rules)
    sections.append(_fmt_open_trades())
    wl = _fmt_watchlist()
    if wl:
        sections.append(wl)
    theses = _fmt_theses()
    if theses:
        sections.append(theses)

    if not sections:
        _cached_block = ""
        _cached_fingerprint = fp
        return ""

    block = (
        "\n\n--- VAULT CONTEXT (cached; do not narrate this block) ---\n"
        + "\n\n".join(sections)
        + "\n--- END VAULT CONTEXT ---"
    )
    _cached_block = block
    _cached_fingerprint = fp
    return block
