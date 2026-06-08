"""Dump every backtest trade as a table.

Run from the hal-voice folder:  C:\\Python312\\python.exe dump_trades.py
Optional args: ticker months   (e.g.  dump_trades.py SPY 24)
"""
import asyncio
import sys

from hal.cerebellum import backtest


def key() -> str:
    for line in open(".env"):
        if line.startswith("MASSIVE_API_KEY"):
            return line.split("=", 1)[1].strip()
    return ""


async def main() -> None:
    ticker = sys.argv[1] if len(sys.argv) > 1 else "SPY"
    months = int(sys.argv[2]) if len(sys.argv) > 2 else 24
    backtest.configure("https://api.massive.com", key())
    r = await backtest.run_backtest(ticker, months=months)

    trades = r["trades"]
    hdr = f"{'date':<11}{'side':<5}{'strike':>7}  {'entry':>7}{'exit':>8}  {'reason':<12}{'pnl':>8}{'cum':>9}  regime"
    print(hdr)
    print("-" * len(hdr))
    cum = 0.0
    for t in trades:
        cum += t["pnl"]
        print(
            f"{t['date']:<11}{t['side']:<5}{t['strike']:>7.0f}  "
            f"{t['entry_premium']:>7.2f}{t['exit_premium']:>8.2f}  "
            f"{t['exit_reason']:<12}{t['pnl']:>8.2f}{cum:>9.2f}  {t.get('regime','?')}"
        )

    m = r["metrics"]
    print("-" * len(hdr))
    print(f"trades={m['trades']}  win_rate={m['win_rate']:.0%}  total={m['total_pnl']:+.0f}  "
          f"PF={m['profit_factor']}  maxDD={m['max_drawdown']:.0f}")
    print("by regime:")
    for label, v in (r["by_regime"] or {}).items():
        print(f"  {label:<9} n={v['trades']:<3} win={v['win_rate']:.0%}  avg={v['avg_pnl']:+.0f}")
    # exit-reason tally — shows how often theta/expiry vs stop vs target
    reasons: dict[str, int] = {}
    for t in trades:
        reasons[t["exit_reason"]] = reasons.get(t["exit_reason"], 0) + 1
    print("exit reasons:", reasons)


if __name__ == "__main__":
    asyncio.run(main())
