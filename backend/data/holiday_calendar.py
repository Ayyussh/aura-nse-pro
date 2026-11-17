"""Official NSE Trading Holiday Calendar & Market Schedule.

Validates Indian equity market holidays, trading sessions, weekend rules,
and special trading windows (e.g., Muhurat Trading).
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, Set
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

# Official NSE Equity Market Holidays for 2026 & 2025
NSE_HOLIDAYS_2026: Set[str] = {
    "2026-01-26",  # Republic Day
    "2026-02-17",  # Mahashivratri
    "2026-03-04",  # Holi
    "2026-03-20",  # Id-Ul-Fitr (Ramzan Id)
    "2026-03-27",  # Shri Ram Navami
    "2026-04-03",  # Good Friday
    "2026-04-14",  # Dr. Baba Saheb Ambedkar Jayanti
    "2026-05-01",  # Maharashtra Day
    "2026-05-27",  # Bakri Id / Eid ul-Adha
    "2026-06-26",  # Muharram
    "2026-08-15",  # Independence Day (Saturday)
    "2026-10-02",  # Mahatma Gandhi Jayanti
    "2026-10-20",  # Dussehra
    "2026-11-08",  # Diwali Balipratipada
    "2026-11-24",  # Gurunanak Jayanti
    "2026-12-25",  # Christmas
}

# Special sessions (e.g. Muhurat Trading on Diwali evening)
NSE_SPECIAL_SESSIONS_2026: Dict[str, str] = {
    "2026-11-08": "Diwali Laxmi Pujan (Muhurat Trading: 18:15 to 19:15 IST)"
}


def get_ist_now() -> datetime.datetime:
    """Return current timestamp in Asia/Kolkata timezone."""
    return datetime.datetime.now(IST)


def is_weekend(d: datetime.date) -> bool:
    """Return True if Saturday (5) or Sunday (6)."""
    return d.weekday() in (5, 6)


def is_trading_holiday(d: datetime.date) -> bool:
    """Return True if date is an official NSE holiday."""
    return d.isoformat() in NSE_HOLIDAYS_2026


def is_special_session(d: datetime.date) -> bool:
    """Return True if date is a special weekend session."""
    return d.isoformat() in NSE_SPECIAL_SESSIONS_2026


def is_trading_day(d: datetime.date) -> bool:
    """Determine whether the specified date is an active NSE trading day."""
    if is_special_session(d):
        return True
    if is_weekend(d):
        return False
    if is_trading_holiday(d):
        return False
    return True


def get_previous_trading_day(d: datetime.date) -> datetime.date:
    """Find the most recent past trading day."""
    curr = d - datetime.timedelta(days=1)
    while not is_trading_day(curr):
        curr -= datetime.timedelta(days=1)
    return curr


def get_next_trading_day(d: datetime.date) -> datetime.date:
    """Find the next upcoming trading day."""
    curr = d + datetime.timedelta(days=1)
    while not is_trading_day(curr):
        curr += datetime.timedelta(days=1)
    return curr


def get_market_status(now: datetime.datetime | None = None) -> Dict[str, Any]:
    """Get real-time market operational status in IST."""
    if now is None:
        now = get_ist_now()
    elif now.tzinfo is None:
        now = now.replace(tzinfo=IST)
    else:
        now = now.astimezone(IST)

    today = now.date()
    today_is_trading = is_trading_day(today)

    time_str = now.strftime("%H:%M:%S")
    t = now.time()

    pre_open_start = datetime.time(9, 0, 0)
    pre_open_end = datetime.time(9, 15, 0)
    market_open = datetime.time(9, 15, 0)
    market_close = datetime.time(15, 30, 0)
    post_close = datetime.time(16, 0, 0)

    if not today_is_trading:
        reason = "Weekend" if is_weekend(today) else "NSE Public Holiday"
        return {
            "status": "CLOSED",
            "reason": reason,
            "is_trading_day": False,
            "current_time_ist": time_str,
            "next_trading_day": get_next_trading_day(today).isoformat(),
        }

    if t < pre_open_start:
        status = "PRE_MARKET_AWAITING"
    elif pre_open_start <= t < pre_open_end:
        status = "PRE_OPEN_AUCTION"
    elif market_open <= t <= market_close:
        status = "MARKET_OPEN"
    elif market_close < t <= post_close:
        status = "POST_MARKET_CLOSING"
    else:
        status = "MARKET_CLOSED"

    return {
        "status": status,
        "is_trading_day": True,
        "current_time_ist": time_str,
        "next_trading_day": get_next_trading_day(today).isoformat() if status == "MARKET_CLOSED" else today.isoformat(),
    }
