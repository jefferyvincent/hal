"""Option strategy knowledge for HAL.

Ported from TradeScan (D:\\repos\\tradescans):
  - src/constants/options.ts        SPREAD_TYPE_DESCRIPTIONS, labels
  - src/utils/strategy-screener.ts  bias x IV -> ranked spreads, leg specs
  - src/types/strategy-screener.ts  shapes

Given a directional bias and an implied-vol regime, recommend ranked option
strategies with plain-English rationale and risk level, and (when a price is
supplied) the concrete legs to structure each one. Purely algorithmic — no
network calls — so it is fast and deterministic for voice turns.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

# ─── Plain-English strategy knowledge (SPREAD_TYPE_DESCRIPTIONS) ──────────────

SPREAD_TYPE_DESCRIPTIONS: dict[str, str] = {
    "long_call": "Bullish strategy. Buy a call option to profit from upward price movement with limited downside risk.",
    "long_put": "Bearish strategy. Buy a put option to profit from downward price movement with limited downside risk.",
    "vertical_call": "Moderately bullish. Buy a lower strike call and sell a higher strike call to reduce cost while capping profit potential.",
    "vertical_put": "Moderately bearish. Buy a higher strike put and sell a lower strike put to reduce cost while capping profit potential.",
    "iron_condor": "Neutral strategy. Profit from low volatility by selling both a call spread and put spread. Max profit when price stays between short strikes.",
    "iron_butterfly": "Neutral strategy. Similar to iron condor but with short strikes at the same price. Higher potential profit but narrower profit zone.",
    "butterfly_call": "Neutral to slightly bullish. Profit if price stays near the middle strike at expiration. Limited risk and reward.",
    "butterfly_put": "Neutral to slightly bearish. Profit if price stays near the middle strike at expiration. Limited risk and reward.",
    "calendar_call": "Neutral to bullish. Sell a near-term call and buy a longer-term call at the same strike. Profit from time decay.",
    "calendar_put": "Neutral to bearish. Sell a near-term put and buy a longer-term put at the same strike. Profit from time decay.",
    "diagonal_call": "Bullish. Similar to calendar but with different strikes. Combines directional bias with time decay.",
    "diagonal_put": "Bearish. Similar to calendar but with different strikes. Combines directional bias with time decay.",
    "straddle": "Volatility play. Buy both a call and put at the same strike. Profit from large price moves in either direction.",
    "strangle": "Volatility play. Buy a call and put at different strikes. Cheaper than straddle but needs larger price move to profit.",
    "covered_call": "Income strategy. Own stock and sell calls against it. Generate income while holding shares with capped upside.",
    "protective_put": "Hedging strategy. Own stock and buy puts for downside protection. Like insurance for your shares.",
    "collar": "Hedging strategy. Own stock, buy a put for protection, and sell a call to offset the put cost. Limited risk and reward.",
    "custom": "Custom strategy with user-defined legs.",
    "stock_long": "Buy shares of stock. Profit from price appreciation with unlimited upside potential.",
    "stock_short": "Sell borrowed shares. Profit from price decline with unlimited risk if price rises.",
}

# Human-readable labels (from SPREAD_TYPE_OPTIONS).
LABELS: dict[str, str] = {
    "stock_long": "Long Stock",
    "stock_short": "Short Stock",
    "long_call": "Long Call",
    "long_put": "Long Put",
    "vertical_call": "Vertical Call Spread",
    "vertical_put": "Vertical Put Spread",
    "iron_condor": "Iron Condor",
    "iron_butterfly": "Iron Butterfly",
    "butterfly_call": "Call Butterfly",
    "butterfly_put": "Put Butterfly",
    "calendar_call": "Call Calendar",
    "calendar_put": "Put Calendar",
    "diagonal_call": "Call Diagonal",
    "diagonal_put": "Put Diagonal",
    "straddle": "Straddle",
    "strangle": "Strangle",
    "covered_call": "Covered Call",
    "protective_put": "Protective Put",
    "collar": "Collar",
    "custom": "Custom",
}

# ─── Recommendation map: bias x IV regime -> ranked spread types ──────────────

RECOMMENDATIONS: dict[str, dict[str, list[str]]] = {
    "bullish": {
        "high": ["covered_call", "vertical_call", "collar"],
        "medium": ["long_call", "stock_long", "vertical_call"],
        "low": ["long_call", "stock_long", "vertical_call"],
        "unknown": ["long_call", "vertical_call", "stock_long"],
    },
    "bearish": {
        "high": ["vertical_put", "protective_put", "collar"],
        "medium": ["long_put", "stock_short", "vertical_put"],
        "low": ["long_put", "stock_short", "vertical_put"],
        "unknown": ["long_put", "vertical_put", "stock_short"],
    },
    "neutral": {
        "high": ["iron_condor", "iron_butterfly", "strangle"],
        "medium": ["iron_condor", "calendar_call", "calendar_put"],
        "low": ["calendar_call", "calendar_put", "diagonal_call"],
        "unknown": ["iron_condor", "calendar_call", "strangle"],
    },
}

RISK_LEVELS: dict[str, str] = {
    "stock_long": "high",
    "stock_short": "high",
    "long_call": "medium",
    "long_put": "medium",
    "vertical_call": "low",
    "vertical_put": "low",
    "iron_condor": "low",
    "iron_butterfly": "low",
    "butterfly_call": "low",
    "butterfly_put": "low",
    "calendar_call": "low",
    "calendar_put": "low",
    "diagonal_call": "low",
    "diagonal_put": "low",
    "straddle": "medium",
    "strangle": "medium",
    "covered_call": "low",
    "protective_put": "low",
    "collar": "low",
    "custom": "high",
}

# ─── Classification helpers ───────────────────────────────────────────────────


def classify_iv(iv: float) -> str:
    """Implied vol (decimal, e.g. 0.25) -> 'low' | 'medium' | 'high'."""
    if iv < 0.2:
        return "low"
    if iv <= 0.4:
        return "medium"
    return "high"


def derive_bias(change_percent: float) -> str:
    """Daily % change -> directional bias. >1% bullish, <-1% bearish, else neutral."""
    if change_percent > 1:
        return "bullish"
    if change_percent < -1:
        return "bearish"
    return "neutral"


# ─── Strike / expiration math ─────────────────────────────────────────────────


def _js_weekday(d: date) -> int:
    """JS Date.getDay(): Sunday=0 .. Saturday=6 (Python weekday is Monday=0)."""
    return (d.weekday() + 1) % 7


def nth_friday_from_now(n: int, frm: Optional[date] = None) -> str:
    """ISO date of the Nth Friday from `frm`. n=4 ~ 28 DTE, n=8 ~ 56 DTE.
    Mirrors TradeScan nthFridayFromNow exactly (first Friday may be today)."""
    d = frm or date.today()
    day = _js_weekday(d)
    days_until_friday = 5 - day if day <= 5 else 6
    d = d + timedelta(days=days_until_friday + (n - 1) * 7)
    return d.isoformat()


def nearest_five_strike(price: float) -> int:
    """Round a price to the nearest $5 increment (half-up, like JS Math.round)."""
    import math

    return int(math.floor(price / 5 + 0.5) * 5)


def build_leg_specs(spread_type: str, current_price: float) -> list[dict]:
    """Optimal legs (strike, expiry, option type, position type) for a spread at
    a given price. Strikes target ATM +/-5/10% rounded to $5; expiries ~30/60 DTE.
    Ported from TradeScan buildStrategyLegSpecs."""
    atm = nearest_five_strike(current_price)
    otm_call = nearest_five_strike(current_price * 1.05)
    otm_call2 = nearest_five_strike(current_price * 1.10)
    otm_put = nearest_five_strike(current_price * 0.95)
    otm_put2 = nearest_five_strike(current_price * 0.90)
    exp30 = nth_friday_from_now(4)
    exp60 = nth_friday_from_now(8)

    def leg(opt: str, pos: str, strike: float, exp: str) -> dict:
        return {
            "optionType": opt,
            "positionType": pos,
            "strikePrice": strike,
            "expirationDate": exp,
        }

    table: dict[str, list[dict]] = {
        "long_call": [leg("call", "long", atm, exp30)],
        "long_put": [leg("put", "long", atm, exp30)],
        "vertical_call": [
            leg("call", "long", atm, exp30),
            leg("call", "short", otm_call, exp30),
        ],
        "vertical_put": [
            leg("put", "long", atm, exp30),
            leg("put", "short", otm_put, exp30),
        ],
        "iron_condor": [
            leg("put", "short", otm_put, exp30),
            leg("put", "long", otm_put2, exp30),
            leg("call", "short", otm_call, exp30),
            leg("call", "long", otm_call2, exp30),
        ],
        "iron_butterfly": [
            leg("put", "long", otm_put, exp30),
            leg("put", "short", atm, exp30),
            leg("call", "short", atm, exp30),
            leg("call", "long", otm_call, exp30),
        ],
        "butterfly_call": [
            leg("call", "long", otm_put, exp30),
            leg("call", "short", atm, exp30),
            leg("call", "long", otm_call, exp30),
        ],
        "butterfly_put": [
            leg("put", "long", otm_put, exp30),
            leg("put", "short", atm, exp30),
            leg("put", "long", otm_call, exp30),
        ],
        "straddle": [
            leg("call", "long", atm, exp30),
            leg("put", "long", atm, exp30),
        ],
        "strangle": [
            leg("call", "long", otm_call, exp30),
            leg("put", "long", otm_put, exp30),
        ],
        "covered_call": [
            leg("stock", "long", current_price, exp30),
            leg("call", "short", otm_call, exp30),
        ],
        "protective_put": [
            leg("stock", "long", current_price, exp30),
            leg("put", "long", otm_put, exp30),
        ],
        "collar": [
            leg("stock", "long", current_price, exp30),
            leg("call", "short", otm_call, exp30),
            leg("put", "long", otm_put, exp30),
        ],
        "calendar_call": [
            leg("call", "short", atm, exp30),
            leg("call", "long", atm, exp60),
        ],
        "calendar_put": [
            leg("put", "short", atm, exp30),
            leg("put", "long", atm, exp60),
        ],
        "diagonal_call": [
            leg("call", "long", atm, exp60),
            leg("call", "short", otm_call, exp30),
        ],
        "diagonal_put": [
            leg("put", "long", atm, exp60),
            leg("put", "short", otm_put, exp30),
        ],
        "stock_long": [leg("stock", "long", current_price, exp30)],
        "stock_short": [leg("stock", "short", current_price, exp30)],
    }
    return table.get(spread_type, [])


# ─── Top-level entry point ────────────────────────────────────────────────────


def recommend_strategy(
    underlying: str = "",
    bias: str = "auto",
    change_percent: Optional[float] = None,
    iv: Optional[float] = None,
    iv_level: Optional[str] = None,
    current_price: Optional[float] = None,
) -> dict:
    """Recommend ranked option strategies for a bias x IV regime.

    bias: 'auto' | 'bullish' | 'bearish' | 'neutral'. When 'auto', derived from
          change_percent (defaults to neutral if that is also absent).
    iv:   implied vol as a decimal (0.25 = 25%). Classified into low/medium/high.
    iv_level: pass directly to skip classification; overrides `iv`.
    current_price: when given, each recommendation includes concrete legs.
    """
    if bias == "auto":
        resolved_bias = derive_bias(change_percent) if change_percent is not None else "neutral"
    else:
        resolved_bias = bias
    if resolved_bias not in RECOMMENDATIONS:
        return {"error": f"invalid bias {bias!r}; use auto/bullish/bearish/neutral"}

    if iv_level is None:
        resolved_iv_level = classify_iv(iv) if iv is not None else "unknown"
    else:
        resolved_iv_level = iv_level
    if resolved_iv_level not in RECOMMENDATIONS[resolved_bias]:
        return {"error": f"invalid iv_level {iv_level!r}; use low/medium/high/unknown"}

    recs = []
    for st in RECOMMENDATIONS[resolved_bias][resolved_iv_level]:
        rec = {
            "spread_type": st,
            "label": LABELS.get(st, st),
            "rationale": SPREAD_TYPE_DESCRIPTIONS.get(st, ""),
            "risk_level": RISK_LEVELS.get(st, "unknown"),
        }
        if current_price is not None:
            rec["legs"] = build_leg_specs(st, current_price)
        recs.append(rec)

    return {
        "underlying": underlying or None,
        "bias": resolved_bias,
        "iv": iv,
        "iv_level": resolved_iv_level,
        "current_price": current_price,
        "recommendations": recs,
        "note": (
            "Strikes target ATM +/-5/10% rounded to $5; expiries ~30/60 DTE. "
            "Educational structure only — confirm live strikes/premium in the chain."
        ),
    }


# ─── Self-test (fidelity vs TradeScan source) ─────────────────────────────────

if __name__ == "__main__":
    # Bias x IV map fidelity.
    assert RECOMMENDATIONS["bullish"]["high"] == ["covered_call", "vertical_call", "collar"]
    assert RECOMMENDATIONS["neutral"]["low"] == ["calendar_call", "calendar_put", "diagonal_call"]
    assert RECOMMENDATIONS["bearish"]["unknown"] == ["long_put", "vertical_put", "stock_short"]

    # IV classification thresholds.
    assert classify_iv(0.19) == "low"
    assert classify_iv(0.2) == "medium"
    assert classify_iv(0.4) == "medium"
    assert classify_iv(0.41) == "high"

    # Bias derivation.
    assert derive_bias(1.5) == "bullish"
    assert derive_bias(-2) == "bearish"
    assert derive_bias(0.5) == "neutral"

    # Strike rounding.
    assert nearest_five_strike(502) == 500
    assert nearest_five_strike(503) == 505
    assert nearest_five_strike(100 * 1.05) == 105

    # Leg specs: vertical_call at $500 -> long ATM 500 / short OTM 525.
    legs = build_leg_specs("vertical_call", 500)
    assert legs[0]["strikePrice"] == 500 and legs[0]["positionType"] == "long"
    assert legs[1]["strikePrice"] == 525 and legs[1]["positionType"] == "short"
    assert legs[0]["optionType"] == "call"

    # Iron condor has 4 legs, two puts then two calls.
    ic = build_leg_specs("iron_condor", 500)
    assert len(ic) == 4
    assert [l["optionType"] for l in ic] == ["put", "put", "call", "call"]

    # Top-level shape.
    out = recommend_strategy(underlying="SPY", bias="auto", change_percent=2.0, iv=0.18, current_price=500)
    assert out["bias"] == "bullish" and out["iv_level"] == "low"
    assert out["recommendations"][0]["spread_type"] == "long_call"
    assert "legs" in out["recommendations"][0]

    # Auto bias with no signal -> neutral; unknown IV when no iv given.
    out2 = recommend_strategy()
    assert out2["bias"] == "neutral" and out2["iv_level"] == "unknown"

    print("option_strategy self-tests passed")
