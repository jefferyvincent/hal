"""HAL-Vault read/write surface.

Single module for all vault I/O. The vault is ~/HAL-Vault/ by default
(override via HAL_VAULT_DIR). Notes are plain markdown with YAML frontmatter.

Public API
----------
write_note(rel_path, frontmatter, body)   -- atomic create/overwrite
update_frontmatter(rel_path, updates)     -- field-level frontmatter edit
read_note(rel_path)                       -- -> {path, frontmatter, body}
list_notes(folder, **filters)             -- -> list[dict] filtered by fm fields
validate_note(rel_path)                   -- -> list[str] of warnings
"""
from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Any

import yaml  # PyYAML — already in the env (used by TTS / other deps)

from hal.brainstem.config import VAULT_DIR


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _note_path(rel_path: str) -> Path:
    """Resolve a vault-relative path to an absolute Path, creating parents."""
    p = VAULT_DIR / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _parse(text: str) -> tuple[dict, str]:
    """Split markdown text into (frontmatter_dict, body_text)."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm_raw = text[3:end].strip()
    body = text[end + 4:].lstrip("\n")
    try:
        fm = yaml.safe_load(fm_raw) or {}
    except yaml.YAMLError:
        fm = {}
    return fm, body


def _render(frontmatter: dict, body: str) -> str:
    """Render frontmatter dict + body back to a markdown string."""
    fm_text = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True,
                        sort_keys=False).rstrip()
    return f"---\n{fm_text}\n---\n\n{body}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def write_note(rel_path: str, frontmatter: dict, body: str = "") -> Path:
    """Write a note atomically (temp-file rename). Returns the absolute path."""
    p = _note_path(rel_path)
    content = _render(frontmatter, body)
    # Atomic write: write to a sibling temp file then rename.
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=".hal_tmp_", suffix=".md")
    try:
        os.write(fd, content.encode("utf-8"))
        os.close(fd)
        os.replace(tmp, p)
    except Exception:
        os.close(fd)
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return p


def update_frontmatter(rel_path: str, updates: dict) -> Path:
    """Merge `updates` into the note's existing frontmatter. Body is untouched."""
    p = _note_path(rel_path)
    text = p.read_text(encoding="utf-8") if p.exists() else ""
    fm, body = _parse(text)
    fm.update(updates)
    return write_note(rel_path, fm, body)


def read_note(rel_path: str) -> dict[str, Any] | None:
    """Return {path, frontmatter, body} or None if the file doesn't exist."""
    p = VAULT_DIR / rel_path
    if not p.exists():
        return None
    text = p.read_text(encoding="utf-8")
    fm, body = _parse(text)
    return {"path": p, "rel_path": rel_path, "frontmatter": fm, "body": body}


def list_notes(folder: str, **filters) -> list[dict[str, Any]]:
    """Return all notes under `folder` whose frontmatter matches all `filters`.

    Filter values are compared with ==; pass None to skip a field.
    Example: list_notes("Journal", type="trade", status="open")
    """
    base = VAULT_DIR / folder
    if not base.exists():
        return []
    results = []
    for p in sorted(base.rglob("*.md")):
        text = p.read_text(encoding="utf-8")
        fm, body = _parse(text)
        rel = str(p.relative_to(VAULT_DIR)).replace("\\", "/")
        if all(fm.get(k) == v for k, v in filters.items() if v is not None):
            results.append({"path": p, "rel_path": rel, "frontmatter": fm, "body": body})
    return results


def validate_note(rel_path: str) -> list[str]:
    """Return a list of warning strings for frontmatter issues. Empty = OK."""
    note = read_note(rel_path)
    if note is None:
        return [f"File not found: {rel_path}"]
    fm = note["frontmatter"]
    warnings = []
    if not fm:
        warnings.append("frontmatter is missing or empty")
        return warnings
    if "type" not in fm:
        warnings.append("missing required field: type")
    note_type = fm.get("type")
    required_by_type = {
        "trade": ["symbol", "status", "side", "strategy", "opened"],
        "thesis": ["symbol", "conviction"],
        "watch": ["symbol", "trigger", "status"],
        "analysis": ["symbol", "bias"],
        "rule": [],
    }
    for field in required_by_type.get(note_type, []):
        if field not in fm or fm[field] is None or fm[field] == "":
            warnings.append(f"missing or blank: {field}")
    return warnings


# ---------------------------------------------------------------------------
# Vault-level helpers used by rag.py and server.py
# ---------------------------------------------------------------------------

def all_notes() -> list[dict[str, Any]]:
    """Yield every .md note in the vault (skips _attachments, Dashboards, Templates)."""
    skip = {"_attachments", "Dashboards", "Templates"}
    results = []
    for p in sorted(VAULT_DIR.rglob("*.md")):
        parts = p.relative_to(VAULT_DIR).parts
        if parts[0] in skip:
            continue
        text = p.read_text(encoding="utf-8")
        fm, body = _parse(text)
        rel = str(p.relative_to(VAULT_DIR)).replace("\\", "/")
        results.append({"path": p, "rel_path": rel, "frontmatter": fm, "body": body})
    return results
