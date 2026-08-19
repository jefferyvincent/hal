"""Probe which Alpaca market-data endpoints HAL's keys are entitled to.

Run from the repo root:  python hal/cerebellum/probe.py

Prints PASS/FAIL per endpoint with a short sample. Useful after changing
plans — it answers "what can HAL actually see right now" without starting
the server.
"""
import asyncio
import os
import sys
from datetime import date, timedelta

import httpx

BASE_DATA = "https://data.alpaca.markets"
BASE_TRADE = "https://paper-api.alpaca.markets"


def env(name: str) -> str:
    v = os.environ.get(name, "")
    if v:
        return v
    try:
        for line in open(".env"):
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return ""


async def probe(client: httpx.AsyncClient, label: str, url: str, params: dict) -> None:
    try:
        r = await client.get(url, params=params)
    except Exception as e:
        print(f"FAIL {label}: {type(e).__name__}: {e}")
        return
    status = "PASS" if r.status_code == 200 else "FAIL"
    print(f"{status} {label}  [{r.status_code}]  {r.text[:160]}")


async def main() -> None:
    key, secret = env("ALPACA_API_KEY"), env("ALPACA_SECRET_KEY")
    if not (key and secret):
        print("FAIL: no ALPACA_API_KEY / ALPACA_SECRET_KEY (env or .env)")
        sys.exit(1)
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    sym = sys.argv[1].upper() if len(sys.argv) > 1 else "SPY"
    today = date.today()
    week_ago = (today - timedelta(days=7)).isoformat()

    async with httpx.AsyncClient(headers=headers, timeout=30) as c:
        await probe(c, "clock", f"{BASE_TRADE}/v2/clock", {})
        await probe(c, f"stock daily bars {sym}", f"{BASE_DATA}/v2/stocks/bars",
                    {"symbols": sym, "timeframe": "1Day", "start": week_ago, "limit": 2})
        await probe(c, f"stock snapshot {sym}", f"{BASE_DATA}/v2/stocks/snapshots",
                    {"symbols": sym})
        await probe(c, f"option chain {sym} (indicative)",
                    f"{BASE_DATA}/v1beta1/options/snapshots/{sym}",
                    {"feed": "indicative", "limit": 1})
        # Real-time OPRA: 403 "OPRA agreement is not signed" on the free Basic
        # plan. That wording suggests a form, but it is a SUBSCRIPTION gate —
        # it needs Algo Trader Plus. Expected to fail on a free account.
        await probe(c, f"option chain {sym} (opra)",
                    f"{BASE_DATA}/v1beta1/options/snapshots/{sym}",
                    {"feed": "opra", "limit": 1})
        await probe(c, f"option contracts {sym} (active)",
                    f"{BASE_TRADE}/v2/options/contracts",
                    {"underlying_symbols": sym, "limit": 1})
        await probe(c, f"option contracts {sym} (expired)",
                    f"{BASE_TRADE}/v2/options/contracts",
                    {"underlying_symbols": sym, "status": "inactive",
                     "expiration_date_lte": "2025-01-31", "limit": 1})
        # SIP inside the last 15 minutes is the paid tier; IEX is the free feed.
        await probe(c, "recent SIP quote (paid tier check)",
                    f"{BASE_DATA}/v2/stocks/quotes/latest", {"symbols": sym, "feed": "sip"})
        await probe(c, "screener movers", f"{BASE_DATA}/v1beta1/screener/stocks/movers",
                    {"top": 2})
        await probe(c, "news", f"{BASE_DATA}/v1beta1/news", {"symbols": sym, "limit": 1})


if __name__ == "__main__":
    asyncio.run(main())
