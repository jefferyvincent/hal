# Test an API key against an MCP HTTP endpoint in several header forms.
# Run on the HAL host:
#   & '.\.venv\Scripts\python.exe' probe_mcp_key.py <mcp-url> <your-key>
# Prints which header form (if any) the server accepts. Paste output back.
import sys
import json
import httpx

INIT = {
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {"protocolVersion": "2025-06-18", "capabilities": {},
               "clientInfo": {"name": "probe", "version": "0"}},
}
BASE = {"Accept": "application/json, text/event-stream",
        "Content-Type": "application/json"}


def attempt(client, url, label, extra):
    h = dict(BASE)
    h.update(extra)
    try:
        r = client.post(url, json=INIT, headers=h, timeout=20)
        ok = r.status_code < 400
        mark = "OK  " if ok else "FAIL"
        print(f"  [{mark} {r.status_code}] {label}")
        if not ok:
            print(f"          {r.text[:180].replace(chr(10),' ')}")
        else:
            print(f"          {r.text[:180].replace(chr(10),' ')}")
        return ok
    except Exception as e:
        print(f"  [EXC ] {label} -> {type(e).__name__}: {e}")
        return False


def main():
    if len(sys.argv) < 3:
        print("usage: python probe_mcp_key.py <mcp-url> <api-key>")
        return
    url, key = sys.argv[1], sys.argv[2]
    print(f"URL: {url}")
    print(f"key: {key[:6]}...{key[-4:]} (len {len(key)})\n")
    bearer = key if key.lower().startswith("bearer ") else f"Bearer {key}"
    forms = [
        ("Authorization: Bearer <key>", {"Authorization": bearer}),
        ("apikey: <key>", {"apikey": key}),
        ("x-api-key: <key>", {"x-api-key": key}),
        ("Authorization: Bearer + apikey (Supabase dual)",
         {"Authorization": bearer, "apikey": key}),
        ("Authorization: <key> (no Bearer)", {"Authorization": key}),
    ]
    any_ok = False
    with httpx.Client(follow_redirects=True) as c:
        print("=== attempts ===")
        for label, extra in forms:
            if attempt(c, url, label, extra):
                any_ok = True
    print()
    if any_ok:
        print(">>> Use the header form marked OK. If it's 'apikey' or 'x-api-key',")
        print(">>> put it in HAL's 'Extra headers' box as e.g.  apikey=<key>")
        print(">>> (and leave the API Key field empty).")
    else:
        print(">>> No header form worked. This key is likely the wrong kind for")
        print(">>> this server (e.g. a Supabase anon key, not a TradeScans token),")
        print(">>> OR the server only accepts an OAuth-issued token. Ask TradeScans")
        print(">>> for the exact header + key to use for programmatic/API access.")
    print("\nDONE. Paste this whole output back (the key is masked above; the")
    print("attempt bodies may echo error text but not your key).")


if __name__ == "__main__":
    main()
