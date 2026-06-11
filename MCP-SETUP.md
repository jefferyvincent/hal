# MCP servers + Subscriptions panel — setup & how it works

## One-time install (required)
HAL's MCP client uses the official `mcp` Python SDK. Install it into HAL's venv:

```bash
# from the repo root:
.venv/bin/python -m pip install mcp
# Windows:  & '.\.venv\Scripts\python.exe' -m pip install mcp
```

## Apply the changes
1. Restart the server (creates the mcp_servers / mcp_oauth tables and loads the
   new MCP client + WS commands). Kill whatever holds port 8000, then relaunch
   server.py with the venv python (start-hal.ps1).
2. Rebuild the app (new panels + buttons): from app/, `npm run tauri:dev` or
   `npm run tauri:build`. Browser check: `npm run dev` -> http://localhost:1420.

If "nothing opens" when you add a server, you are almost certainly still on the
OLD build -- do BOTH steps above to get the OAuth sign-in flow.

## Using it
Top-right HUD now has WATCHES and MCP buttons next to CHATS.

- MCP panel: a form to add a server. Two transports:
  - stdio (local command): command `npx`, args `-y @some/mcp-server`, env as
    KEY=VALUE lines.
  - http (hosted): a URL, optional headers as KEY=VALUE lines.
  Servers persist in SQLite (mcp_servers), connect on save, tools are discovered
  and shown. Enable/disable/remove per server.
- Watches panel: read-only view of live market subscriptions, their alert rules,
  fire counts, and recent fired alerts.

## Servers that require login (OAuth)
Some MCP servers require an interactive account sign-in instead of a static
token (e.g. TradeScans: "sign in with your account when prompted").

1. Add the server as http with just its URL. Leave Headers EMPTY -- do NOT paste
   a bearer token. OAuth servers issue their own token after you sign in.
2. On add, if the server needs login HAL automatically opens your browser to the
   provider's sign-in page. If it doesn't open, the server shows status
   needs_auth with an Authorize button -- click it.
3. After you sign in, the browser lands on HAL's
   http://localhost:8000/oauth/callback ("HAL is authorized -- close this tab").
   HAL exchanges the code, stores tokens in SQLite (mcp_oauth), and reconnects.
4. Tokens refresh automatically on later connects; re-click Authorize only if it
   ever drops back to needs_auth/error.

OAuth uses dynamic client registration + PKCE via the MCP SDK; the redirect URI
is http://localhost:8000/oauth/callback. If a provider asks you to register a
redirect URI by hand, use exactly that.

### Bearer token vs OAuth -- which is which
- "Sign in with your account when prompted" -> OAuth. Leave Headers empty and let
  the browser flow run. (TradeScans is this.)
- Provider gives you a static token / API key -> paste it in Headers as
  `Authorization=Bearer <token>` and skip the sign-in flow.

## How HAL calls MCP tools
Tools are exposed to the model as mcp__<slug>__<tool> and dispatched to the right
server. Because Qwen3 ignores freshly-added tools when think:False, HAL flips
think:True for just the first (tool-selection) iteration of an MCP-eligible turn;
the spoken answer keeps think:False so latency only hits those turns. Thinking
output is held back from TTS.

## Notes
- Connect-per-call model (fresh short-lived MCP session per discovery/call) --
  simple and robust; can move to persistent sessions later if desired.
