"""Generic Model Context Protocol (MCP) client for HAL.

Connects to user-configured MCP servers (stdio for local commands, streamable
HTTP for hosted endpoints), discovers their tools, and calls them on behalf of
the LLM. Server config is persisted in the `mcp_servers` SQLite table (see
persistence.py); the user adds/removes servers from a form in the HAL UI.

Connection model: connect-per-call. Each tool discovery or call opens a fresh,
short-lived session and closes it. This avoids juggling long-lived async MCP
sessions across asyncio tasks (anyio cancel-scope affinity bugs), at the cost
of a small per-call connect overhead. Discovered tool schemas are cached so the
agent loop can advertise them every turn without reconnecting.

OAuth: HTTP servers that require login use the MCP SDK's OAuth provider with
DB-backed token storage (`mcp_oauth` table). The interactive flow opens the
user's browser; the server's GET /oauth/callback route feeds the authorization
code back via resolve_oauth(). Tokens are refreshed automatically on later
connects.

Tools are exposed to the Ollama model as `mcp__<server>__<tool>` so dispatch can
route them back to the right server (see server.execute_tool).
"""
from __future__ import annotations

import asyncio
import json
import re
import shlex
import subprocess
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from urllib.parse import parse_qs, urlparse

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.auth import OAuthClientProvider, OAuthFlowError, TokenStorage
from mcp.shared.auth import (
    OAuthClientInformationFull,
    OAuthClientMetadata,
    OAuthToken,
)

from hal.hippocampus import persistence

SEP = "__"
PREFIX = "mcp"
_LIST_TIMEOUT = 20.0
_CALL_TIMEOUT = 60.0
_HTTP_TRANSPORTS = ("http", "streamable_http", "sse")
# HAL's server serves this route; must match the server-side @app.get path.
OAUTH_REDIRECT_URI = "http://localhost:8000/oauth/callback"

# server_id -> {id, name, slug, transport, enabled, status, error, tools:[ollama dict]}
_cache: dict[int, dict] = {}

# Pending interactive authorizations, keyed by OAuth `state`. The /oauth/callback
# route resolves these once the user finishes login in the browser.
_pending: dict[str, asyncio.Future] = {}


# --- helpers ---------------------------------------------------------------

def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")
    return s or "server"


def unique_slug(name: str) -> str:
    base = slugify(name)
    slug = base
    n = 2
    while persistence.get_mcp_server_by_slug(slug) is not None:
        slug = f"{base}_{n}"
        n += 1
    return slug


def parse_args(raw: str | None) -> list[str]:
    """Accept a JSON array or a shell-style string for stdio args."""
    raw = (raw or "").strip()
    if not raw:
        return []
    if raw.startswith("["):
        try:
            val = json.loads(raw)
            if isinstance(val, list):
                return [str(x) for x in val]
        except json.JSONDecodeError:
            pass
    try:
        return shlex.split(raw)
    except ValueError:
        return raw.split()


def parse_kv(raw: str | None) -> dict[str, str]:
    """Parse KEY=VALUE lines (or a JSON object) into a dict for env/headers."""
    raw = (raw or "").strip()
    if not raw:
        return {}
    if raw.startswith("{"):
        try:
            val = json.loads(raw)
            if isinstance(val, dict):
                return {str(k): str(v) for k, v in val.items()}
        except json.JSONDecodeError:
            pass
    out: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _is_http(row: dict) -> bool:
    return (row.get("transport") or "").lower() in _HTTP_TRANSPORTS


def _has_static_auth(row: dict) -> bool:
    """True if the user supplied a static credential (API key / Authorization
    header). When set, we must NOT fall back to interactive OAuth — the user
    is authenticating with their own token, and an OAuth attempt against a
    token-only server just 404s on registration."""
    h = parse_kv(row.get("headers"))
    return any(k.lower() in ("authorization", "apikey", "x-api-key") for k in h)


def _fmt_exc(e: BaseException) -> str:
    """Flatten an exception into a readable, copy-pasteable string. anyio wraps
    failures in ExceptionGroup ("unhandled errors in TaskGroup (1 sub-exception)")
    which hides the real cause — recurse into .exceptions to surface it."""
    seen: list[str] = []

    def walk(ex: BaseException, depth: int = 0) -> None:
        subs = getattr(ex, "exceptions", None)  # ExceptionGroup / BaseExceptionGroup
        if subs:
            for sub in subs:
                walk(sub, depth + 1)
        else:
            label = f"{type(ex).__name__}: {ex}".strip()
            if label and label not in seen:
                seen.append(label)
    try:
        walk(e)
    except Exception:
        pass
    return " | ".join(seen) if seen else f"{type(e).__name__}: {e}"


def _looks_auth_error(msg: str) -> bool:
    m = msg.lower()
    return any(t in m for t in ("401", "403", "unauthor", "oauth", "forbidden",
                                "authorization required", "invalid_token"))


def _ollama_tool(slug: str, tool: Any) -> dict:
    schema = getattr(tool, "inputSchema", None) or {"type": "object", "properties": {}}
    return {
        "type": "function",
        "function": {
            "name": f"{PREFIX}{SEP}{slug}{SEP}{tool.name}",
            "description": (getattr(tool, "description", "") or "")[:1024],
            "parameters": schema,
        },
    }


# --- OAuth -----------------------------------------------------------------

class DbTokenStorage(TokenStorage):
    """Persists OAuth client registration + tokens in the mcp_oauth table."""

    def __init__(self, server_id: int) -> None:
        self.sid = server_id

    async def get_tokens(self) -> OAuthToken | None:
        row = await asyncio.to_thread(persistence.get_mcp_oauth, self.sid)
        if not row or not row.get("tokens"):
            return None
        try:
            return OAuthToken.model_validate_json(row["tokens"])
        except Exception:
            return None

    async def set_tokens(self, tokens: OAuthToken) -> None:
        await asyncio.to_thread(
            persistence.set_mcp_oauth_tokens, self.sid, tokens.model_dump_json()
        )

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        row = await asyncio.to_thread(persistence.get_mcp_oauth, self.sid)
        if not row or not row.get("client_info"):
            return None
        try:
            return OAuthClientInformationFull.model_validate_json(row["client_info"])
        except Exception:
            return None

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        await asyncio.to_thread(
            persistence.set_mcp_oauth_client, self.sid, client_info.model_dump_json()
        )


def resolve_oauth(state: str, code: str | None) -> bool:
    """Called by the /oauth/callback route with the returned code + state."""
    fut = _pending.get(state or "")
    if fut and not fut.done():
        fut.set_result(code)
        return True
    return False


def _open_browser(url: str) -> None:
    try:
        subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-Command", f"Start-Process '{url}'"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        print(f"[mcp] could not open browser: {e}; URL: {url}")


def _client_metadata() -> OAuthClientMetadata:
    return OAuthClientMetadata(
        client_name="HAL",
        redirect_uris=[OAUTH_REDIRECT_URI],
        grant_types=["authorization_code", "refresh_token"],
        response_types=["code"],
        token_endpoint_auth_method="client_secret_post",
    )


def _interactive_handlers():
    """Build (redirect_handler, callback_handler) that open the browser and wait
    for the /oauth/callback route to deliver the authorization code."""
    loop = asyncio.get_event_loop()
    holder: dict[str, Any] = {"state": None, "fut": None}

    async def redirect_handler(url: str) -> None:
        st = parse_qs(urlparse(url).query).get("state", [None])[0] or ""
        fut: asyncio.Future = loop.create_future()
        holder["state"] = st
        holder["fut"] = fut
        _pending[st] = fut
        print(f"[mcp] opening browser for OAuth (state={st[:8]}...)")
        _open_browser(url)

    async def callback_handler() -> tuple[str, str | None]:
        fut = holder["fut"]
        try:
            code = await asyncio.wait_for(fut, timeout=300)
        finally:
            _pending.pop(holder["state"] or "", None)
        if not code:
            raise OAuthFlowError("no authorization code returned")
        return code, holder["state"]

    return redirect_handler, callback_handler


def _provider(row: dict, *, interactive: bool) -> OAuthClientProvider:
    if interactive:
        redirect_handler, callback_handler = _interactive_handlers()
    else:
        async def redirect_handler(url: str) -> None:
            raise OAuthFlowError("authorization required")

        async def callback_handler() -> tuple[str, str | None]:
            raise OAuthFlowError("authorization required")

    return OAuthClientProvider(
        server_url=row["url"],
        client_metadata=_client_metadata(),
        storage=DbTokenStorage(row["id"]),
        redirect_handler=redirect_handler,
        callback_handler=callback_handler,
    )


async def _auth_for(row: dict):
    """Non-interactive auth for normal connects: a provider that uses stored
    tokens (and silently refreshes them) when the server has OAuth set up."""
    if not _is_http(row):
        return None
    # A user-supplied static credential takes precedence over OAuth — never
    # attach an OAuth provider when the request already carries an API key.
    if _has_static_auth(row):
        return None
    oauth = await asyncio.to_thread(persistence.get_mcp_oauth, row["id"])
    if oauth and (oauth.get("tokens") or oauth.get("client_info")):
        return _provider(row, interactive=False)
    return None


# --- session ---------------------------------------------------------------

@asynccontextmanager
async def _session(row: dict, auth=None) -> AsyncIterator[ClientSession]:
    transport = (row.get("transport") or "").lower()
    if transport == "stdio":
        if not row.get("command"):
            raise ValueError("stdio server needs a command")
        params = StdioServerParameters(
            command=row["command"],
            args=parse_args(row.get("args")),
            env=(parse_kv(row.get("env")) or None),
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session
    elif transport in _HTTP_TRANSPORTS:
        if not row.get("url"):
            raise ValueError("http server needs a url")
        headers = parse_kv(row.get("headers")) or None
        async with streamablehttp_client(row["url"], headers=headers, auth=auth) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session
    else:
        raise ValueError(f"unknown transport {transport!r}")


# --- discovery / cache -----------------------------------------------------

async def refresh(row: dict) -> dict:
    sid = row["id"]
    entry = {
        "id": sid,
        "name": row["name"],
        "slug": row["slug"],
        "transport": row["transport"],
        "enabled": bool(row["enabled"]),
        "status": "connecting",
        "error": None,
        "tools": [],
    }
    if not row["enabled"]:
        entry["status"] = "disabled"
        _cache[sid] = entry
        return entry
    try:
        auth = await _auth_for(row)
        async with _session(row, auth=auth) as session:
            resp = await asyncio.wait_for(session.list_tools(), timeout=_LIST_TIMEOUT)
        entry["tools"] = [_ollama_tool(row["slug"], t) for t in resp.tools]
        entry["status"] = "connected"
    except Exception as e:
        msg = _fmt_exc(e)
        entry["error"] = msg
        # HTTP servers that reject us for auth reasons can be fixed by the user
        # clicking Authorize, so surface that as a distinct, actionable state —
        # BUT only when the user has NOT supplied a static credential. If they
        # pasted an API key/Authorization header, a 401 means the key is wrong
        # or the wrong header name; do NOT drag them into the OAuth flow (which
        # 404s on token-only servers). Show the real error instead.
        if _is_http(row) and _looks_auth_error(msg) and not _has_static_auth(row):
            entry["status"] = "needs_auth"
        else:
            entry["status"] = "error"
    _cache[sid] = entry
    return entry


async def refresh_all() -> None:
    rows = await asyncio.to_thread(persistence.list_mcp_servers)
    live_ids = {r["id"] for r in rows}
    for dead in [k for k in _cache if k not in live_ids]:
        _cache.pop(dead, None)
    for row in rows:
        await refresh(row)


async def start() -> None:
    """Called from the FastAPI lifespan: discover all enabled servers' tools."""
    try:
        await refresh_all()
        connected = sum(1 for e in _cache.values() if e["status"] == "connected")
        print(f"[mcp] {connected}/{len(_cache)} server(s) connected")
    except Exception as e:
        print(f"[mcp] start failed: {e}")


# --- agent integration -----------------------------------------------------

def tools_for_agent() -> list[dict]:
    """Flatten cached tools across connected servers for the Ollama tools param."""
    out: list[dict] = []
    for entry in _cache.values():
        if entry.get("status") == "connected":
            out.extend(entry.get("tools", []))
    return out


async def call(full_name: str, args: dict | None) -> str:
    """Execute an `mcp__<slug>__<tool>` call. Returns text for the model."""
    try:
        _, slug, tool = full_name.split(SEP, 2)
    except ValueError:
        return f"Bad MCP tool name: {full_name!r}"
    row = await asyncio.to_thread(persistence.get_mcp_server_by_slug, slug)
    if not row:
        return f"No MCP server registered for {slug!r}."
    if not row["enabled"]:
        return f"MCP server {slug!r} is disabled."
    try:
        auth = await _auth_for(row)
        async with _session(row, auth=auth) as session:
            result = await asyncio.wait_for(
                session.call_tool(tool, args or {}), timeout=_CALL_TIMEOUT
            )
    except Exception as e:
        return f"MCP call failed ({slug}.{tool}): {_fmt_exc(e)}"
    return _format_result(result)


def _format_result(result: Any) -> str:
    parts: list[str] = []
    for c in getattr(result, "content", None) or []:
        text = getattr(c, "text", None)
        if text is not None:
            parts.append(text)
        else:
            parts.append(f"[{getattr(c, 'type', 'content')}]")
    body = "\n".join(parts).strip() or "(no content)"
    if getattr(result, "isError", False):
        return f"[tool error] {body}"
    return body


# --- management (called by WS commands) ------------------------------------

def _merge_api_key(headers: str, api_key: str) -> str:
    """Fold a raw API key into the headers dict as a Bearer Authorization
    header. Lets the user paste just the key instead of hand-formatting
    'Authorization=Bearer ...'. If they already typed an Authorization line,
    that wins and the api_key is ignored."""
    h = parse_kv(headers)
    api_key = (api_key or "").strip()
    if api_key and not any(k.lower() == "authorization" for k in h):
        # Accept either a bare token or one the user prefixed with 'Bearer '.
        h["Authorization"] = api_key if api_key.lower().startswith("bearer ") else f"Bearer {api_key}"
    return json.dumps(h)


async def add(
    name: str,
    transport: str,
    command: str = "",
    args: str = "",
    url: str = "",
    env: str = "",
    headers: str = "",
    api_key: str = "",
) -> dict:
    name = (name or "").strip() or "Unnamed"
    transport = (transport or "stdio").strip().lower()
    slug = await asyncio.to_thread(unique_slug, name)
    sid = await asyncio.to_thread(
        persistence.insert_mcp_server,
        name, slug, transport, command.strip(),
        json.dumps(parse_args(args)),
        url.strip(),
        json.dumps(parse_kv(env)),
        _merge_api_key(headers, api_key),
        True,
    )
    row = await asyncio.to_thread(persistence.get_mcp_server, sid)
    if row:
        await refresh(row)
    return {"id": sid, "slug": slug}


async def remove(server_id: int) -> bool:
    ok = await asyncio.to_thread(persistence.delete_mcp_server, server_id)
    _cache.pop(server_id, None)
    return ok


async def set_enabled(server_id: int, enabled: bool) -> bool:
    ok = await asyncio.to_thread(persistence.set_mcp_enabled, server_id, enabled)
    row = await asyncio.to_thread(persistence.get_mcp_server, server_id)
    if row:
        await refresh(row)
    return ok


async def authorize(server_id: int) -> dict:
    """Run the interactive OAuth flow for an HTTP server: opens the browser,
    waits for the /oauth/callback, exchanges + stores tokens, then reconnects."""
    row = await asyncio.to_thread(persistence.get_mcp_server, server_id)
    if not row:
        return {"error": "no such server"}
    if not _is_http(row):
        return {"error": "OAuth only applies to http servers"}
    if _has_static_auth(row):
        return {"error": "this server uses a static API key; OAuth does not apply"}
    provider = _provider(row, interactive=True)
    try:
        async with _session(row, auth=provider) as session:
            await asyncio.wait_for(session.list_tools(), timeout=_LIST_TIMEOUT)
    except Exception as e:
        msg = _fmt_exc(e)
        entry = _cache.get(server_id)
        if entry:
            entry["status"] = "error"
            entry["error"] = msg
        return {"error": msg}
    # Tokens are now stored; reconnect non-interactively to populate the cache.
    await refresh(row)
    return {"ok": True}


def status_snapshot() -> list[dict]:
    """UI-facing view: every configured server merged with its live status."""
    rows = persistence.list_mcp_servers()
    out: list[dict] = []
    for row in rows:
        c = _cache.get(row["id"], {})
        tools = [
            {
                "name": t["function"]["name"].split(SEP, 2)[-1],
                "description": t["function"]["description"],
            }
            for t in c.get("tools", [])
        ]
        out.append({
            "id": row["id"],
            "name": row["name"],
            "slug": row["slug"],
            "transport": row["transport"],
            "command": row["command"],
            "url": row["url"],
            "enabled": bool(row["enabled"]),
            "status": c.get("status", "disabled" if not row["enabled"] else "unknown"),
            "error": c.get("error"),
            "tools": tools,
            "tool_count": len(tools),
        })
    return out
