"""Normalize and format user-supplied attachments (text + images) for a turn."""
from __future__ import annotations

from config import MAX_ATTACHMENT_COUNT, MAX_ATTACHMENT_TEXT_CHARS


def _normalize_attachments(raw: list | None) -> list[dict]:
    if not raw:
        return []
    out = []
    for a in raw[:MAX_ATTACHMENT_COUNT]:
        if not isinstance(a, dict):
            continue
        kind = a.get("kind")
        if kind not in ("text", "image"):
            continue
        name = str(a.get("name") or "unnamed")
        content = a.get("content") or ""
        if not isinstance(content, str) or not content:
            continue
        if kind == "text":
            content = content[:MAX_ATTACHMENT_TEXT_CHARS]
        out.append({"name": name, "kind": kind, "content": content})
    return out


def _format_text_attachments(attachments: list[dict]) -> str:
    text_atts = [a for a in attachments if a["kind"] == "text"]
    if not text_atts:
        return ""
    parts = ["<attachments>"]
    for a in text_atts:
        parts.append(f'<file name="{a["name"]}">\n{a["content"]}\n</file>')
    parts.append("</attachments>")
    return "\n".join(parts)


def _attachment_summary(attachments: list[dict]) -> str:
    if not attachments:
        return ""
    names = [a["name"] for a in attachments]
    return f"[Attached: {', '.join(names)}]"
