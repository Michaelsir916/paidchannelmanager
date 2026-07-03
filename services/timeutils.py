from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30), name="IST")


def now_utc_iso():
    """Raw UTC timestamp for storage (always store in this format)."""
    return datetime.now(timezone.utc).isoformat()


def to_ist_dual(value):
    """
    Converts a stored UTC ISO string (or datetime) into a display string
    showing BOTH 24-hour and 12-hour time, in IST.
    Example: "02-07-2026 21:15:03 (24h) / 02-07-2026 09:15:03 PM (12h) IST"
    """
    if not value:
        return "Unknown"

    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            return value  # not a parseable timestamp, show as-is
    else:
        dt = value

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    ist_dt = dt.astimezone(IST)
    fmt_24h = ist_dt.strftime("%d-%m-%Y %H:%M:%S")
    fmt_12h = ist_dt.strftime("%d-%m-%Y %I:%M:%S %p")
    return f"{fmt_24h} (24h) / {fmt_12h} (12h) IST"
