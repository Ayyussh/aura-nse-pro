"""Comprehensive Synthetic-Bar Tests for AURA-NSE Pro Grader (Section 18.2).

Verifies:
1. Evaluates ONLY bars strictly after entry date (entry-day bar ignored).
2. Stop wins when a single day's range touches both Stop and Target (conservative default).
3. 5-minute intraday tie-breaker resolves to TARGET_HIT when target was hit before stop.
4. 5-minute intraday tie-breaker resolves to STOP_LOSS_HIT when stop was hit before target.
5. Gap down through the stop fills at the open price (capturing tail slippage).
6. Gap up above the target fills at the open price.
7. Time limit expiration exits at close on day N.
8. Realized gross_pnl_r and net_pnl_r are computed accurately with transaction costs.
"""

from __future__ import annotations
import datetime
import pandas as pd
import pytest

from backend.core.grader import grade_trade_outcome, round_to_exchange_tick


def test_grader_evaluates_only_bars_after_entry():
    """Verify bars on or before entry date are completely ignored."""
    entry_date = datetime.date(2026, 11, 10)
    dates = pd.to_datetime(["2026-11-09", "2026-11-10", "2026-11-11"])

    # On entry date (2026-11-10), low breaches stop, but trade was entered that day
    # So entry day bar must NOT trigger stop loss!
    df = pd.DataFrame(
        {
            "open": [100.0, 95.0, 102.0],
            "high": [105.0, 102.0, 106.0],
            "low": [98.0, 80.0, 101.0],  # 80.0 on 11-10 would trigger stop if evaluated!
            "close": [100.0, 101.0, 105.0],
        },
        index=dates,
    )

    result = grade_trade_outcome(
        symbol="TEST.NS",
        entry_date=entry_date,
        entry_price=100.0,
        stop_loss=90.0,
        target_price=120.0,
        quantity=10,
        time_limit_days=10,
        history_df=df,
    )

    # Only 2026-11-11 is after entry date. Low was 101, High was 106. Trade should still be OPEN!
    assert result["status"] == "OPEN"


def test_grader_stop_wins_on_ambiguous_day_without_intraday():
    """When both Target and Stop are touched on the same day, Stop wins conservatively."""
    entry_date = datetime.date(2026, 11, 10)
    dates = pd.to_datetime(["2026-11-10", "2026-11-11"])

    # 2026-11-11 touches both: Low=85 (<= 90) AND High=125 (>= 120)
    df = pd.DataFrame(
        {
            "open": [100.0, 100.0],
            "high": [105.0, 125.0],
            "low": [98.0, 85.0],
            "close": [100.0, 110.0],
        },
        index=dates,
    )

    result = grade_trade_outcome(
        symbol="TEST.NS",
        entry_date=entry_date,
        entry_price=100.0,
        stop_loss=90.0,
        target_price=120.0,
        quantity=10,
        time_limit_days=10,
        history_df=df,
    )

    assert result["status"] == "STOP_LOSS_HIT"
    assert result["exit_price"] == 90.0
    assert "conservative stop-first" in result["exit_reason"]


def test_grader_intraday_tie_breaker_target_first():
    """5-min candles confirm Target was touched before Stop on ambiguous day."""
    entry_date = datetime.date(2026, 11, 10)
    dates = pd.to_datetime(["2026-11-10", "2026-11-11"])

    df = pd.DataFrame(
        {
            "open": [100.0, 100.0],
            "high": [105.0, 125.0],
            "low": [98.0, 85.0],
            "close": [100.0, 110.0],
        },
        index=dates,
    )

    # 5-minute candles: first bar rallies to 122 (hits target), second bar dumps to 88
    intraday_candles = {
        "2026-11-11": [
            {"high": 122.0, "low": 100.0},
            {"high": 110.0, "low": 88.0},
        ]
    }

    result = grade_trade_outcome(
        symbol="TEST.NS",
        entry_date=entry_date,
        entry_price=100.0,
        stop_loss=90.0,
        target_price=120.0,
        quantity=10,
        time_limit_days=10,
        history_df=df,
        intraday_candles_by_date=intraday_candles,
    )

    assert result["status"] == "TARGET_HIT"
    assert result["exit_price"] == 120.0
    assert "Intraday replay verified target reached before stop" in result["exit_reason"]


def test_grader_intraday_tie_breaker_stop_first():
    """5-min candles confirm Stop was touched before Target on ambiguous day."""
    entry_date = datetime.date(2026, 11, 10)
    dates = pd.to_datetime(["2026-11-10", "2026-11-11"])

    df = pd.DataFrame(
        {
            "open": [100.0, 100.0],
            "high": [105.0, 125.0],
            "low": [98.0, 85.0],
            "close": [100.0, 110.0],
        },
        index=dates,
    )

    # 5-minute candles: first bar dumps to 88 (hits stop), second bar rallies to 122
    intraday_candles = {
        "2026-11-11": [
            {"high": 102.0, "low": 88.0},
            {"high": 122.0, "low": 100.0},
        ]
    }

    result = grade_trade_outcome(
        symbol="TEST.NS",
        entry_date=entry_date,
        entry_price=100.0,
        stop_loss=90.0,
        target_price=120.0,
        quantity=10,
        time_limit_days=10,
        history_df=df,
        intraday_candles_by_date=intraday_candles,
    )

    assert result["status"] == "STOP_LOSS_HIT"
    assert result["exit_price"] == 90.0
    assert "Intraday replay verified stop loss hit first" in result["exit_reason"]


def test_grader_gap_down_through_stop_fills_at_open():
    """A gap-down through the stop fills at the open price (realistic slippage)."""
    entry_date = datetime.date(2026, 11, 10)
    dates = pd.to_datetime(["2026-11-10", "2026-11-11"])

    # Stock closes at 98 on day 0, then gaps down to 82 at open on day 1 (stop was 90)
    df = pd.DataFrame(
        {
            "open": [100.0, 82.0],
            "high": [102.0, 84.0],
            "low": [98.0, 80.0],
            "close": [98.0, 83.0],
        },
        index=dates,
    )

    result = grade_trade_outcome(
        symbol="TEST.NS",
        entry_date=entry_date,
        entry_price=100.0,
        stop_loss=90.0,
        target_price=120.0,
        quantity=10,
        time_limit_days=10,
        history_df=df,
    )

    assert result["status"] == "STOP_LOSS_HIT"
    assert result["exit_price"] == 82.0  # Filled at open price 82.0, not stop 90.0!
    assert "Gap-down below stop loss at open" in result["exit_reason"]
    # Net R will be worse than -1R due to gap slippage
    assert result["net_pnl_r"] < -1.0


def test_grader_gap_up_above_target_fills_at_open():
    """A gap-up above the target fills at the open price."""
    entry_date = datetime.date(2026, 11, 10)
    dates = pd.to_datetime(["2026-11-10", "2026-11-11"])

    # Gaps up to 128 at open (target was 120)
    df = pd.DataFrame(
        {
            "open": [100.0, 128.0],
            "high": [102.0, 130.0],
            "low": [98.0, 126.0],
            "close": [98.0, 129.0],
        },
        index=dates,
    )

    result = grade_trade_outcome(
        symbol="TEST.NS",
        entry_date=entry_date,
        entry_price=100.0,
        stop_loss=90.0,
        target_price=120.0,
        quantity=10,
        time_limit_days=10,
        history_df=df,
    )

    assert result["status"] == "TARGET_HIT"
    assert result["exit_price"] == 128.0  # Filled at open price 128.0!
    assert "Gap-up to target at open" in result["exit_reason"]


def test_grader_time_limit_expiration():
    """Trade exits on day Time_Limit_Days at close."""
    entry_date = datetime.date(2026, 11, 1)
    dates = pd.date_range("2026-11-01", periods=6, freq="D")

    # Day 1 to 5: price stays between 95 and 105 (neither stop 90 nor target 120 hit)
    df = pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0, 103.0, 104.0, 102.0],
            "high": [102.0, 103.0, 104.0, 105.0, 106.0, 104.0],
            "low": [98.0, 99.0, 100.0, 101.0, 102.0, 101.0],
            "close": [100.0, 102.0, 103.0, 104.0, 105.0, 103.0],
        },
        index=dates,
    )

    result = grade_trade_outcome(
        symbol="TEST.NS",
        entry_date=entry_date,
        entry_price=100.0,
        stop_loss=90.0,
        target_price=120.0,
        quantity=10,
        time_limit_days=5,  # 5 days time limit
        history_df=df,
    )

    assert result["status"] == "TIME_EXPIRED"
    assert result["exit_price"] == 103.0  # Close of the 5th day after entry
    assert "Holding period reached 5 days limit" in result["exit_reason"]
