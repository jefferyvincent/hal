"""Probe how Massive serves cash-settled INDEX data (SPX), so we wire the
backtester to the right ticker format.

Run from hal-voice:  C:\\Python312\\python.exe probe_index.py
Reads MASSIVE_API_KEY from .env. Prints which formats return data.
"""
import datetime
import os
import httpx

BASE = "https://api.massive.com"


def key() -> str:
    k = os.environ.get("MASSIVE_API_KEY", "")
    if not k and os.path.exists(".env"):
        for line in open(".env"):
            if line.startswith("MASSIVE_API_KEY"):
                k = line.split("=", 1)[1].strip()
                break
    return k


def main() -> None:
    k = key()
    if not k:
        print("FAIL: no MASSIVE_API_KEY")
        return
    h = {"Authorization": f"Bearer {k}"}
    today = datetime.date.today()
    frm = (today - datetime.timedelta(days=20)).isoformat()
    to = today.isoformat()

    with httpx.Client(timeout=30, headers=h) as c:
        # 1) Daily aggregates for the index underlying — try bare vs I: prefix.
        print("=== underlying daily bars ===")
        for tk in ("SPX", "I:SPX"):
            try:
                r = c.get(f"{BASE}/v2/aggs/ticker/{tk}/range/1/day/{frm}/{to}",
                          params={"adjusted": "true", "sort": "asc", "limit": 50})
                n = len((r.json() or {}).get("results") or [])
                print(f"  {tk:8} HTTP {r.status_code}  bars={n}")
            except Exception as e:
                print(f"  {tk:8} error {e}")

        # 2) Options contracts lookup — try underlying_ticker bare vs I: and
        #    both common index roots (SPX, SPXW).
        print("=== expired option contracts (underlying_ticker variants) ===")
        past = (today - datetime.timedelta(days=40)).isoformat()
        for ut in ("SPX", "I:SPX", "SPXW"):
            try:
                r = c.get(f"{BASE}/v3/reference/options/contracts", params={
                    "underlying_ticker": ut, "contract_type": "call",
                    "expiration_date.gte": past, "expiration_date.lte": to,
                    "expired": "true", "limit": 3,
                })
                rows = (r.json() or {}).get("results") or []
                print(f"  underlying_ticker={ut:6} HTTP {r.status_code}  contracts={len(rows)}")
                for row in rows[:2]:
                    print(f"      -> {row.get('ticker')}  exp {row.get('expiration_date')}  K {row.get('strike_price')}")
            except Exception as e:
                print(f"  underlying_ticker={ut:6} error {e}")

        # 3) If we found an option ticker, confirm it returns historical bars.
        print("=== option contract daily bars ===")
        found = None
        for ut in ("SPX", "I:SPX", "SPXW"):
            try:
                r = c.get(f"{BASE}/v3/reference/options/contracts", params={
                    "underlying_ticker": ut, "contract_type": "call",
                    "expiration_date.gte": past, "expiration_date.lte": to,
                    "expired": "true", "limit": 1,
                })
                rows = (r.json() or {}).get("results") or []
                if rows:
                    found = (ut, rows[0])
                    break
            except Exception:
                pass
        if found:
            ut, row = found
            tk = row["ticker"]
            exp = row["expiration_date"]
            f2 = (datetime.date.fromisoformat(exp) - datetime.timedelta(days=20)).isoformat()
            r = c.get(f"{BASE}/v2/aggs/ticker/{tk}/range/1/day/{f2}/{exp}",
                      params={"adjusted": "true", "sort": "asc", "limit": 50})
            n = len((r.json() or {}).get("results") or [])
            print(f"  {tk}  HTTP {r.status_code}  bars={n}  (via underlying_ticker={ut})")
        else:
            print("  no option contracts found in any format")

    print("\nReport the lines above — they tell us the exact index format to wire.")


if __name__ == "__main__":
    main()
