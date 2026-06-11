"""One-shot probe: does Massive serve historical bars for EXPIRED options?

Run from the repo root:  python hal/cerebellum/probe.py
Reads MASSIVE_API_KEY from .env. Prints PASS/FAIL and a sample.
This is the make-or-break check for the singles backtester.
"""
import datetime
import os

import httpx


def load_key() -> str:
    # Prefer the environment; fall back to the .env file next to this script.
    key = os.environ.get("MASSIVE_API_KEY", "")
    if not key and os.path.exists(".env"):
        for line in open(".env"):
            if line.startswith("MASSIVE_API_KEY"):
                key = line.split("=", 1)[1].strip()
                break
    return key


BASE = "https://api.massive.com"


def main() -> None:
    key = load_key()
    if not key:
        print("FAIL: no MASSIVE_API_KEY found (env or .env)")
        return
    headers = {"Authorization": f"Bearer {key}"}
    today = datetime.date.today()
    past = today - datetime.timedelta(days=45)

    with httpx.Client(timeout=30, headers=headers) as c:
        # 1) list a few SPY calls that already expired in the last ~45 days
        r = c.get(f"{BASE}/v3/reference/options/contracts", params={
            "underlying_ticker": "SPY",
            "contract_type": "call",
            "expiration_date.gte": past.isoformat(),
            "expiration_date.lte": today.isoformat(),
            "expired": "true",
            "limit": 5,
        })
        print(f"[1] list expired contracts: HTTP {r.status_code}")
        if r.status_code != 200:
            print("FAIL:", r.text[:300])
            return
        rows = r.json().get("results") or []
        print(f"    found {len(rows)} expired contracts")
        if not rows:
            print("FAIL: no expired contracts returned — cannot backtest singles this way")
            return
        for row in rows:
            print("   ", row.get("ticker"), row.get("expiration_date"), "strike", row.get("strike_price"))

        # 2) pull daily bars for the first one across its final month
        tk = rows[0]["ticker"]
        exp = rows[0]["expiration_date"]
        frm = (datetime.date.fromisoformat(exp) - datetime.timedelta(days=30)).isoformat()
        r2 = c.get(f"{BASE}/v2/aggs/ticker/{tk}/range/1/day/{frm}/{exp}", params={
            "adjusted": "true", "sort": "asc", "limit": 50000,
        })
        print(f"[2] daily bars for {tk}: HTTP {r2.status_code}")
        bars = (r2.json() or {}).get("results") or []
        print(f"    {len(bars)} bars")
        if bars:
            f, l = bars[0], bars[-1]
            fd = datetime.datetime.utcfromtimestamp(f["t"] / 1000).date()
            ld = datetime.datetime.utcfromtimestamp(l["t"] / 1000).date()
            print(f"    first {fd}: close {f['c']}  vol {f.get('v')}")
            print(f"    last  {ld}: close {l['c']}  vol {l.get('v')}")

    if bars:
        print("\nPASS: expired-option history is available. The backtester can run.")
    else:
        print("\nFAIL: contract listed but no historical bars — singles backtest blocked.")


if __name__ == "__main__":
    main()
