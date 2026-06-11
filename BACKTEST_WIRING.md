# Backtester wiring guide

`backtest.py` is complete and tested. It is **not yet wired** into `server.py` or the
frontend, because the editing tools couldn't safely verify in-place edits to those
existing files during the session that created it. Apply the small changes below by
hand. Each is a paste-in; nothing else in those files changes.

After editing, verify: `python -m py_compile server.py` and (in `app/`) `npm run build`.

---

## 1. server.py — import (top, near `import charting`, ~line 42)

```python
import backtest
```

## 2. server.py — configure in `_lifespan` (next to the other `.configure` calls, ~line 1018)

```python
    backtest.configure(MASSIVE_BASE_URL, MASSIVE_API_KEY)
```

## 3. server.py — intent matcher (near `_match_chart_intent`, ~line 1604)

Mirrors the chart route because Qwen3 blanks on new tools with think:False, so a
deterministic route is more reliable than a tool call.

```python
_BACKTEST_INTENT = re.compile(r"\b(back\s?test|backtesting)\b", re.IGNORECASE)
_TICKER_RE = re.compile(r"\b([A-Z]{1,5})\b")

def _match_backtest_intent(text: str) -> str | None:
    """Return the underlying ticker if this is a backtest request, else None.
    Defaults to SPY when no ticker is named."""
    if not text or not _BACKTEST_INTENT.search(text):
        return None
    # Prefer an explicit known ticker; fall back to SPY.
    for m in _TICKER_RE.findall(text.upper()):
        if m not in {"A", "I", "BACK", "TEST", "THE", "ON", "OF", "MY"}:
            return m
    return "SPY"
```

## 4. server.py — route inside `process_turn` (right after the chart route, ~line 2307)

Place this immediately AFTER the `chart_req = _match_chart_intent(...)` block so a
"backtest" request is handled before the generic agent loop.

```python
        bt_symbol = _match_backtest_intent(user_text)
        if bt_symbol:
            await websocket.send_json({"state": "processing",
                                       "text": f"Backtesting {bt_symbol}..."})
            try:
                result = await backtest.run_backtest(bt_symbol, months=24)
                spoken = backtest.speak_summary(result)
                # Push the equity curve to the UI (frontend step 5 renders it).
                await websocket.send_json({"action": "open_view", "kind": "backtest",
                                           "backtest": backtest.equity_payload(result)})
            except Exception as e:
                spoken = f"I could not complete that backtest, Jeffery. {e}"
            await stream_sentence(spoken)
            new_history = history + [
                {"role": "user", "content": user_text},
                {"role": "assistant", "content": spoken},
            ]
            if on_reply:
                try:
                    await on_reply(new_history)
                except Exception as e:
                    print(f"[turn] on_reply failed: {e}")
            await _emit_telemetry(websocket, "backtest", bt_symbol, spoken, status="ok")
            await websocket.send_json({"state": "done"})
            if len(new_history) > MAX_HISTORY_MESSAGES:
                new_history = new_history[-MAX_HISTORY_MESSAGES:]
            return new_history
```

> Note: `run_backtest` over 24 months makes one API call per signal (contract lookup
> + bars). Expect a handful of seconds. If it feels slow, lower `months` or cache.

---

## 5. Frontend — render the equity curve

The server emits `{action:"open_view", kind:"backtest", backtest:{...}}`. Two small
additions mirror how `chart` is handled.

### `app/src/types.ts`
Add to the `ServerEnvelope` interface and a payload type:

```ts
  /** Backtest equity-curve payload (action="open_view", kind="backtest"). */
  backtest?: BacktestPayload;
```
```ts
export interface BacktestPayload {
  kind: "backtest";
  underlying: string;
  strategy: string;
  equity: { t: number; value: number }[];
  metrics: Record<string, number | null>;
  by_regime: Record<string, { trades: number; win_rate: number; avg_pnl: number }>;
}
```
Add `"backtest"` to the `ImmersiveSource` union.

### `app/src/stores/immersive.ts`
- Add `backtest: BacktestPayload | null` to state (init `null`).
- In `setSource`, add a branch like the `chart` one that stores the payload and sets
  `source: "backtest"`.

### `app/src/stores/connection.ts` (`onJson`, in the `open_view` handler)
```ts
          if (kind === "backtest") {
            await immersive.setSource("backtest", { backtest: msg.backtest });
            if (!immersive.active) await immersive.enter();
            return;
          }
```
(extend `setSource`'s payload arg type with `backtest?: BacktestPayload`.)

### `app/src/components/immersive/BacktestStage.tsx` (new file)
A line series of `equity` using lightweight-charts (copy ChartStage's setup; use
`addLineSeries` instead of candles), plus a small stats overlay reading `metrics`
(win_rate, total_pnl, profit_factor, max_drawdown) and the `by_regime` split. Render
it from `ImmersiveStage` when `source === "backtest"`, exactly like `ChartStage`.

---

## Strategy recap (what backtest.py implements)

- Long single call/put on SPY, trailing 24 months, 1 contract/trade.
- Signal = pivot S/R break + RSI (>50 call / <50 put). Direction filter only.
- Contract = ATM, nearest weekly (~7 DTE). P&L from the contract's own historical
  bars (real theta/IV). Each trade tagged with entry vol-regime.
- Exit = +50% / -50% / expiry. Metrics: win rate, profit factor, max drawdown,
  avg P&L, by-regime split.
- Assumptions stated in output: close-to-close fills (no historical bid/ask),
  $0.65/contract/side commission, no slippage. Historical, not a paper-forward test.
