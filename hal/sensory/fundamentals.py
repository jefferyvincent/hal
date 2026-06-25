"""Company fundamentals + statement history for HAL's terminal Equity tab.

A companion to earnings.py and news.py: where those poll Nasdaq's keyless
endpoints for calendars and headlines, this pulls the per-company quote summary
and the annual financial statements that feed the terminal's Equity Research /
DCF panel. Same no-API-key spirit and the same browser-ish headers Nasdaq
requires.

Five endpoints are fetched concurrently and normalised into one payload:
  - /api/quote/{sym}/info     → company name, live price, intraday change, volume
  - /api/quote/{sym}/summary  → market cap, avg volume, 52w range, day range,
                                previous close, 1y target, yield, sector/industry
  - /api/company/{sym}/financials?frequency=1 → annual income / balance / cash flow
  - /api/company/{sym}/company-profile → sector, industry, region, description
  - /api/analyst/{sym}/ratings → mean rating, analyst count, covering broker firms

Nasdaq reports statement line items in THOUSANDS and as display strings
("$391,035,000", "-$12,715,000", "--", ""); market cap comes through in whole
dollars. We convert everything to base dollars so the client can do arithmetic
directly. Shares outstanding, EPS and P/E aren't in these feeds, so we derive
them (shares = market cap / price; EPS = net income / shares; P/E = price / EPS).

Any single field may come back None — partial data is fine; the terminal's DCF
guards on what it needs. A hard failure (network / non-200) returns a payload
with `error` set and whatever was parsed.
"""
from __future__ import annotations

import asyncio
import re
import time
from typing import Any, Optional

import httpx

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
# Nasdaq only returns JSON with browser-ish headers + a trusted Origin/Referer
# (same trick earnings.py uses for the calendar endpoint).
_HEADERS = {
    "User-Agent": _UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.nasdaq.com",
    "Referer": "https://www.nasdaq.com/",
}
_BASE = "https://api.nasdaq.com/api"
_TIMEOUT = 15.0
_THOUSAND = 1000.0  # statement line items are reported in thousands


# --- string → number parsing ----------------------------------------------

def _money(s: Any) -> Optional[float]:
    """Parse a Nasdaq money string ("$391,035,000", "-$12,715,000", "($5)") to a
    float. "--", "", None and other non-numeric placeholders yield None."""
    if s is None:
        return None
    t = str(s).strip()
    if not t or t in ("--", "N/A", "NA"):
        return None
    neg = t.startswith("-") or (t.startswith("(") and t.endswith(")"))
    t = re.sub(r"[^0-9.]", "", t)
    if not t or t == ".":
        return None
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


def _pct(s: Any) -> Optional[float]:
    """"0.37%" -> 0.0037."""
    v = _money(s)
    return None if v is None else v / 100.0


def _statement(s: Any) -> Optional[float]:
    """Statement line item (thousands) -> base dollars."""
    v = _money(s)
    return None if v is None else v * _THOUSAND


# --- statement table helpers ------------------------------------------------

def _year_columns(table: dict) -> list[tuple[str, str]]:
    """Return [(col_key, year_label)] for a statement table, newest first.

    Headers look like {"value1": "Period Ending:", "value2": "9/27/2025", ...};
    we keep value2.. and pull the 4-digit year out of each date."""
    headers = table.get("headers") or {}
    cols: list[tuple[str, str]] = []
    for key in sorted(
        (k for k in headers if k != "value1"),
        key=lambda k: int(re.sub(r"\D", "", k) or 0),
    ):
        label = str(headers[key] or "")
        m = re.search(r"(\d{4})", label)
        cols.append((key, m.group(1) if m else label))
    return cols


def _row(table: dict, *labels: str) -> Optional[dict]:
    """First row whose value1 matches any of `labels` (case-insensitive exact)."""
    wanted = {l.lower() for l in labels}
    for row in table.get("rows") or []:
        if str(row.get("value1", "")).strip().lower() in wanted:
            return row
    return None


# --- public API -------------------------------------------------------------

async def fetch(symbol: str) -> dict:
    """Build the EquityFundamentals payload (see app/src/types.ts) for `symbol`."""
    sym = (symbol or "").upper().strip()
    payload: dict = {
        "symbol": sym,
        "name": None,
        "as_of": int(time.time()),
        "price": None,
        "currency": "USD",
        "market_cap": None,
        "shares_outstanding": None,
        "sector": None,
        "industry": None,
        "region": None,
        "description": None,
        "target_price": None,
        "analyst": None,
        "summary": {
            "pe": None, "eps": None, "dividend_yield": None, "beta": None,
            "week52_high": None, "week52_low": None, "volume": None, "avg_volume": None,
            "change": None, "change_pct": None,
            "day_high": None, "day_low": None, "prev_close": None,
        },
        "annual": [],
        "error": None,
    }
    if not sym:
        payload["error"] = "no symbol"
        return payload

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
            info_r, summary_r, fin_r, profile_r, analyst_r = await asyncio.gather(
                client.get(f"{_BASE}/quote/{sym}/info", params={"assetclass": "stocks"}),
                client.get(f"{_BASE}/quote/{sym}/summary", params={"assetclass": "stocks"}),
                client.get(f"{_BASE}/company/{sym}/financials", params={"frequency": "1"}),
                client.get(f"{_BASE}/company/{sym}/company-profile"),
                client.get(f"{_BASE}/analyst/{sym}/ratings"),
                return_exceptions=True,
            )
            info = _data(info_r)
            summary = (_data(summary_r) or {}).get("summaryData") or {}
            # Nasdaq's quote endpoints 400 on the wrong asset class. ETFs (the
            # default SPY, sector funds, etc.) have no "stocks" quote, so retry
            # the quote pair as etf. The statement / profile / analyst feeds have
            # no fund equivalent and just stay empty — correct for a fund.
            if not info:
                info_r, summary_r = await asyncio.gather(
                    client.get(f"{_BASE}/quote/{sym}/info", params={"assetclass": "etf"}),
                    client.get(f"{_BASE}/quote/{sym}/summary", params={"assetclass": "etf"}),
                    return_exceptions=True,
                )
                info = _data(info_r)
                summary = (_data(summary_r) or {}).get("summaryData") or {}
    except Exception as exc:  # noqa: BLE001 — surface any transport error to the UI
        payload["error"] = f"fetch failed: {exc}"
        return payload

    fin = _data(fin_r) or {}
    profile = _data(profile_r) or {}
    analyst = _data(analyst_r) or {}

    # --- quote / company ----------------------------------------------------
    if info:
        payload["name"] = info.get("companyName") or None
        prim = info.get("primaryData") or {}
        payload["price"] = _money(prim.get("lastSalePrice"))
        payload["currency"] = prim.get("currency") or "USD"
        payload["summary"]["volume"] = _money(prim.get("volume"))
        payload["summary"]["change"] = _money(prim.get("netChange"))
        payload["summary"]["change_pct"] = _pct(prim.get("percentageChange"))

    if summary:
        payload["market_cap"] = _money(_val(summary.get("MarketCap")))
        # ETF summaries key average volume differently and carry a Beta.
        payload["summary"]["avg_volume"] = _money(
            _val(summary.get("AverageVolume"))
            or _val(summary.get("AvgDailyVol65Days"))
            or _val(summary.get("FiftyDayAvgDailyVol"))
        )
        payload["summary"]["beta"] = _money(_val(summary.get("Beta")))
        payload["summary"]["dividend_yield"] = _pct(_val(summary.get("Yield")))
        payload["summary"]["prev_close"] = _money(_val(summary.get("PreviousClose")))
        payload["target_price"] = _money(_val(summary.get("OneYrTarget")))
        payload["sector"] = _val(summary.get("Sector")) or None
        payload["industry"] = _val(summary.get("Industry")) or None
        hi, lo = _split_range(_val(summary.get("FiftTwoWeekHighLow")))
        payload["summary"]["week52_high"] = hi
        payload["summary"]["week52_low"] = lo
        # TodayHighLow is "$high/$low".
        d_hi, d_lo = _split_range(_val(summary.get("TodayHighLow")))
        payload["summary"]["day_high"] = d_hi
        payload["summary"]["day_low"] = d_lo
        if payload["summary"]["volume"] is None:
            payload["summary"]["volume"] = _money(_val(summary.get("ShareVolume")))

    # --- company profile (description / classification) ---------------------
    if profile:
        payload["description"] = _pval(profile, "CompanyDescription")
        payload["region"] = _pval(profile, "Region")
        # Prefer the profile's sector/industry when present; summary is the fallback.
        payload["sector"] = _pval(profile, "Sector") or payload["sector"]
        payload["industry"] = _pval(profile, "Industry") or payload["industry"]

    # --- analyst coverage ---------------------------------------------------
    if analyst:
        brokers = [str(b) for b in (analyst.get("brokerNames") or []) if b]
        payload["analyst"] = {
            "rating": analyst.get("meanRatingType") or None,
            "count": _analyst_count(analyst.get("ratingsSummary")),
            "brokers": brokers,
        }

    # --- annual statements --------------------------------------------------
    income = fin.get("incomeStatementTable") or {}
    cash = fin.get("cashFlowTable") or {}
    balance = fin.get("balanceSheetTable") or {}
    cols = _year_columns(income) or _year_columns(cash)

    rev_row = _row(income, "Total Revenue")
    gp_row = _row(income, "Gross Profit")
    oi_row = _row(income, "Operating Income")
    ni_row = _row(income, "Net Income") or _row(cash, "Net Income")
    ocf_row = _row(cash, "Net Cash Flow-Operating")
    capex_row = _row(cash, "Capital Expenditures")
    cash_row = _row(balance, "Cash and Cash Equivalents")
    ltd_row = _row(balance, "Long-Term Debt")
    std_row = _row(balance, "Short-Term Debt / Current Portion of Long-Term Debt")

    annual: list[dict] = []
    for col, year in cols:
        ocf = _statement(_get(ocf_row, col))
        capex_signed = _statement(_get(capex_row, col))
        capex = abs(capex_signed) if capex_signed is not None else None
        fcf = ocf - capex if (ocf is not None and capex is not None) else None
        total_debt = _sum(_statement(_get(ltd_row, col)), _statement(_get(std_row, col)))
        annual.append({
            "year": year,
            "revenue": _statement(_get(rev_row, col)),
            "gross_profit": _statement(_get(gp_row, col)),
            "operating_income": _statement(_get(oi_row, col)),
            "net_income": _statement(_get(ni_row, col)),
            "operating_cash_flow": ocf,
            "capex": capex,
            "free_cash_flow": fcf,
            "total_debt": total_debt,
            "cash": _statement(_get(cash_row, col)),
        })
    payload["annual"] = annual

    # --- derived: shares, EPS, P/E -----------------------------------------
    price = payload["price"]
    mcap = payload["market_cap"]
    if price and mcap and price > 0:
        shares = mcap / price
        payload["shares_outstanding"] = shares
        latest_ni = annual[0]["net_income"] if annual else None
        if latest_ni is not None and shares > 0:
            eps = latest_ni / shares
            payload["summary"]["eps"] = eps
            if eps > 0:
                payload["summary"]["pe"] = price / eps

    if not info and not summary and not fin and not profile and not analyst:
        payload["error"] = "no data returned"
    return payload


# --- small extractors -------------------------------------------------------

def _data(resp: Any) -> Optional[dict]:
    """Pull the `data` object from a Nasdaq response, tolerating exceptions and
    non-200s returned by asyncio.gather(return_exceptions=True)."""
    if isinstance(resp, Exception) or resp is None:
        return None
    try:
        if resp.status_code != 200:
            return None
        return (resp.json() or {}).get("data")
    except Exception:  # noqa: BLE001
        return None


def _val(cell: Any) -> Any:
    """Nasdaq summary cells are {"label": ..., "value": ...}."""
    return cell.get("value") if isinstance(cell, dict) else cell


def _pval(profile: dict, key: str) -> Optional[str]:
    """Pull a company-profile field's value (cells are {"label":, "value":})."""
    v = _val(profile.get(key))
    s = str(v).strip() if v is not None else ""
    return s or None


def _analyst_count(summary: Any) -> Optional[int]:
    """"Based on 29 analysts offering recommendations for 'AAPL'." -> 29."""
    if not summary:
        return None
    m = re.search(r"(\d+)\s+analyst", str(summary))
    return int(m.group(1)) if m else None


def _get(row: Optional[dict], col: str) -> Any:
    return row.get(col) if isinstance(row, dict) else None


def _sum(*vals: Optional[float]) -> Optional[float]:
    present = [v for v in vals if v is not None]
    return sum(present) if present else None


def _split_range(s: Any) -> tuple[Optional[float], Optional[float]]:
    """"$317.4/$199.2607" -> (317.4, 199.2607)."""
    if not s or "/" not in str(s):
        return None, None
    hi, lo = str(s).split("/", 1)
    return _money(hi), _money(lo)
