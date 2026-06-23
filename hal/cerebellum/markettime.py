"""US Eastern clock + market-session helpers.

Computes Eastern wall-clock time without a tz database (tzdata isn't installed
in the pinned torch env) and the live market-session context string that gets
injected into the system prompt each turn.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from hal.brainstem.config import USER_NAME


def _eastern_now() -> tuple[datetime, str]:
    """Current US Eastern wall-clock time, computed from UTC without relying on
    a tz database (tzdata isn't installed and the torch env is pinned). DST runs
    from the 2nd Sunday of March (02:00 EST = 07:00 UTC) to the 1st Sunday of
    November (02:00 EDT = 06:00 UTC). Returns (naive ET datetime, 'EST'|'EDT')."""
    utc = datetime.now(timezone.utc)
    year = utc.year
    mar1 = datetime(year, 3, 1, tzinfo=timezone.utc)
    dst_start = mar1 + timedelta(days=(6 - mar1.weekday()) % 7 + 7, hours=7)
    nov1 = datetime(year, 11, 1, tzinfo=timezone.utc)
    dst_end = nov1 + timedelta(days=(6 - nov1.weekday()) % 7, hours=6)
    is_dst = dst_start <= utc < dst_end
    offset = -4 if is_dst else -5
    et = (utc + timedelta(hours=offset)).replace(tzinfo=None)
    return et, ("EDT" if is_dst else "EST")


def is_regular_hours() -> bool:
    """True during the US regular equity session (Mon-Fri 9:30-16:00 ET).
    Used to gate the price-alert poller. Holidays are not accounted for."""
    et, _ = _eastern_now()
    return _market_session(et) == "OPEN (regular hours)"


def _market_session(et: datetime) -> str:
    """US equity/options session label for a given Eastern time. Time-of-day +
    weekday only; market holidays are not accounted for."""
    if et.weekday() >= 5:
        return "CLOSED (weekend)"
    minutes = et.hour * 60 + et.minute
    if minutes < 4 * 60:
        return "CLOSED (overnight)"
    if minutes < 9 * 60 + 30:
        return "pre-market (not yet open)"
    if minutes < 16 * 60:
        return "OPEN (regular hours)"
    if minutes < 20 * 60:
        return "after-hours (regular session closed)"
    return "CLOSED (overnight)"


def market_status_line() -> str:
    """A terse, authoritative market-session reminder meant to sit at the END of
    the message list (highest recency), right before generation. The full clock
    block lives in the system prefix, but when history is saturated with a stale
    framing (e.g. every prior turn copied '(after-hours) ... wait for Monday'),
    a buried system line loses to recency — this line wins it back and explicitly
    voids the stale wording so the model stops parroting it."""
    et, abbr = _eastern_now()
    session = _market_session(et)
    return (
        "=== LIVE CLOCK — AUTHORITATIVE, overrides anything earlier in this "
        f"conversation. It is {et:%A, %B %d, %Y %I:%M %p} {abbr}. US equity & "
        f"options market RIGHT NOW: {session}. If earlier messages call it "
        "'after-hours', 'closed', or say to 'wait for Monday', that wording is "
        "STALE — do NOT repeat it; state the real session above."
    )


def _options_date_context() -> str:
    """Pre-computed date/time + market-session context the LLM would otherwise
    have to derive itself. /no_think mode skips reasoning, so we hand it the
    current Eastern time, whether the US market is open, ISO + YYMMDD (option-
    ticker) date formats, and the next 4 weekly Friday expirations — keeping it
    from inventing wrong dates or guessing whether the market is live."""
    et, abbr = _eastern_now()
    today = et.date()
    session = _market_session(et)
    # Days until next Friday (Mon=0..Sun=6, Fri=4). Today counts if it IS Friday.
    days_until_fri = (4 - today.weekday()) % 7
    fridays = [today + timedelta(days=days_until_fri + 7 * i) for i in range(4)]
    lines = [
        "=== LIVE CLOCK — AUTHORITATIVE. This is the real current time. Trust it "
        "over ANY time, date, or 'this morning/afternoon' wording earlier in the "
        "conversation; that history is stale. ===",
        f"Current time: {et:%A, %B %d, %Y  %I:%M %p} {abbr} (US Eastern — this IS market time)",
        f"US equity & options market right now: {session}. "
        "Regular hours are 9:30 AM-4:00 PM ET, Mon-Fri. Market holidays are not "
        "reflected here; if it might be a holiday, confirm with query_massive "
        "/v1/marketstatus/now before claiming the market is open.",
        f"When {USER_NAME} asks the time or whether the market is open, answer directly "
        "from the two lines above — do NOT infer it from earlier messages or do "
        "your own clock math.",
        f"Today's date: {today:%A, %B %d, %Y}  (ISO {today:%Y-%m-%d}, option-ticker YYMMDD {today:%y%m%d})",
        "Upcoming Friday option expirations:",
    ]
    for f in fridays:
        delta = (f - today).days
        rel = "today" if delta == 0 else f"+{delta}d"
        lines.append(f"  {f:%a} {f:%Y-%m-%d}  (YYMMDD {f:%y%m%d})  [{rel}]")
    return "\n".join(lines)
