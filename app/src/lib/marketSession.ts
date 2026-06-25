// Is the US equity market in its regular session right now (Mon-Fri 9:30-16:00
// ET)? Mirrors the server's markettime.is_regular_hours: time-of-day + weekday
// only, so market holidays are NOT accounted for (same caveat noted where this
// is used in App.tsx). Eastern wall-clock comes from Intl — the browser ships a
// full tz database, so DST is handled for us without any offset math.

export function isMarketOpen(): boolean {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(new Date());

  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";

  const weekday = get("weekday");
  if (weekday === "Sat" || weekday === "Sun") return false;

  // hour12:false emits "24" at midnight in some engines; fold it back to 0.
  const hour = Number(get("hour")) % 24;
  const minutes = hour * 60 + Number(get("minute"));
  return minutes >= 9 * 60 + 30 && minutes < 16 * 60;
}
