# Standalone OAuth-discovery probe for an MCP HTTP endpoint.
# Run on the HAL host (has network):
#     & '.\.venv\Scripts\python.exe' probe_mcp_oauth.py https://YOUR/mcp/url
# Prints the FULL authorization-server metadata and tests dynamic client
# registration so we can see exactly why DCR 404s.
import sys
import json
import httpx
from urllib.parse import urlsplit, urlunsplit


def origin_of(u):
    p = urlsplit(u)
    return urlunsplit((p.scheme, p.netloc, "", "", ""))


def jget(client, url):
    try:
        r = client.get(url, headers={"Accept": "application/json"})
        return r.status_code, r.text
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def main():
    if len(sys.argv) < 2:
        print("usage: python probe_mcp_oauth.py <mcp-url>")
        return
    url = sys.argv[1]
    origin = origin_of(url)

    with httpx.Client(timeout=20, follow_redirects=True) as c:
        # 1) Protected-resource metadata (path-based, per the WWW-Authenticate hint).
        pr_url = f"{url}/.well-known/oauth-protected-resource"
        sc, body = jget(c, pr_url)
        print(f"=== protected-resource [{sc}] {pr_url} ===")
        auth_servers = []
        try:
            pr = json.loads(body)
            print(json.dumps(pr, indent=2))
            auth_servers = pr.get("authorization_servers", [])
        except Exception:
            print(body[:400])

        if not auth_servers:
            print("\nNo authorization_servers found; stopping.")
            return
        asrv = auth_servers[0].rstrip("/")

        # 2) FULL authorization-server metadata (try both well-known shapes).
        as_meta = None
        for u in (
            f"{asrv}/.well-known/openid-configuration",
            f"{asrv}/.well-known/oauth-authorization-server",
            f"{origin}/.well-known/oauth-authorization-server{urlsplit(asrv).path}",
        ):
            sc, body = jget(c, u)
            print(f"\n=== AS metadata [{sc}] {u} ===")
            if sc == 200:
                try:
                    as_meta = json.loads(body)
                    print(json.dumps(as_meta, indent=2))
                    break
                except Exception:
                    print(body[:800])
            else:
                print(body[:200])

        if not as_meta:
            print("\nNo AS metadata parsed; stopping.")
            return

        print("\n=== KEY FIELDS ===")
        for k in ("registration_endpoint", "authorization_endpoint",
                  "token_endpoint", "code_challenge_methods_supported",
                  "grant_types_supported", "response_types_supported",
                  "client_id_metadata_document_supported",
                  "token_endpoint_auth_methods_supported"):
            print(f"  {k}: {as_meta.get(k)}")

        # 3) Try dynamic client registration (RFC 7591) at candidate endpoints.
        reg_body = {
            "client_name": "HAL",
            "redirect_uris": ["http://localhost:8000/oauth/callback"],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        }
        candidates = []
        if as_meta.get("registration_endpoint"):
            candidates.append(as_meta["registration_endpoint"])
        candidates += [
            f"{asrv}/oauth/clients/register",
            f"{asrv}/oauth/register",
            f"{asrv}/oauth/clients",
            f"{asrv}/register",
        ]
        seen = set()
        print("\n=== DCR registration attempts (POST) ===")
        for u in candidates:
            if u in seen:
                continue
            seen.add(u)
            try:
                r = c.post(u, json=reg_body, headers={"Content-Type": "application/json"})
                print(f"  [{r.status_code}] POST {u}")
                print(f"        {r.text[:300]}")
            except Exception as e:
                print(f"  [EXC] POST {u} -> {type(e).__name__}: {e}")

    print("\nDONE. Paste this whole output back.")


if __name__ == "__main__":
    main()
