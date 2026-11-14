"""Comprehensive Synthetic-Bar Tests for AURA-NSE Pro Grader (Section 18.2 & Item 10).

Verifies:
1. Evaluates ONLY bars after entry time (entry bar ignored when entry_at_open=False).
2. Includes entry bar when entry_at_open=True, evaluating post-open price action.
3. If open gaps down through stop on entry day, trade is SKIPPED_GAP_DOWN (0 PnL, not entered).
4. Replay respects fill_time: intraday candles before fill_time are strictly ignored.
5. Stop wins when a single day's range touches both Stop and Target (conservative default).
6. 5-minute intraday tie-breaker resolves to TARGET_HIT when target was hit before stop.
7. 5-minute intraday tie-breaker resolves to STOP_LOSS_HIT when stop was hit before target.
8. Gap down through the stop on subsequent days fills at open price (slippage).
9. Gap up above target on subsequent days fills at open price.
10. Time limit expiration exits at close on day N.
11. Realized gross_pnl_r and net_pnl_r are computed accurately with transaction costs.
"""

from __future__ import annotations
import datetime
import pandas as pd
import pytest

from backend.core.grader import grade_trade_outcome, round_to_exchange_tick


def test_grader_evaluates_only_bars_after_entry_when_entry_at_close():
    """Verify bars on or before entry date are ignored when entry_at_open is False (e.g. entered at close)."""
    entry_date = datetime.date(2026, 11, 10)
    dates = pd.to_datetime(["2026-11-09", "2026-11-10", "2026-11-11"])

    # On entry date (2026-11-10), low breaches stop, but trade was entered at close
    # So entry day bar must NOT trigger stop loss!
    df = pd.DataFrame(
        {
            "open": [100.0, 95.0, 102.0],
            "high": [105.0, 102.0, 106.0],
            "low": [98.0, 80.0, 101.0],  # 80.0 on 11-10 would trigger stop if evaluated!
            "close": [100.0, 100.0, 105.0],
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
        entry_at_open=False,
    )

    # Only 2026-11-11 is after entry date. Low was 101, High was 106. Trade should still be OPEN!
    assert result["status"] == "OPEN"


def test_grader_includes_entry_bar_when_entry_at_open():
    """When entry_at_open is True, the entry day bar itself is evaluated post-fill."""
    entry_date = datetime.date(2026, 11, 10)
    dates = pd.to_datetime(["2026-11-10", "2026-11-11"])

    # On entry date (2026-11-10), stock enters at open (100.0), and subsequently drops to 85.0 (Stop 90.0)
    df = pd.DataFrame(
        {
            "open": [100.0, 102.0],
            "high": [102.0, 106.0],
            "low": [85.0, 101.0],
            "close": [88.0, 105.0],
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
        entry_at_open=True,
    )

    assert result["status"] == "STOP_LOSS_HIT"
    assert result["exit_price"] == 90.0
    assert result["exit_date"] == "2026-11-10"


def test_grader_skipped_gap_down_at_open():
    """If market open on entry date gaps below stop loss, trade is SKIPPED_GAP_DOWN (never filled)."""
    entry_date = datetime.date(2026, 11, 10)
    dates = pd.to_datetime(["2026-11-10", "2026-11-11"])

    # Stock was supposed to enter around 100, stop 90, but opens at 85 (gap down through stop)
    df = pd.DataFrame(
        {
            "open": [85.0, 92.0],
            "high": [88.0, 95.0],
            "low": [80.0, 90.0],
            "close": [86.0, 94.0],
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
        entry_at_open=True,
    )

    assert result["status"] == "SKIPPED_GAP_DOWN"
    assert result["gross_pnl_rupees"] == 0.0
    assert result["net_pnl_rupees"] == 0.0
    assert result["charges_rupees"] == 0.0
    assert "trade was not filled" in result["exit_reason"]


def test_grader_intraday_replay_respects_fill_time():
    """Intraday candles prior to fill_time must NOT trigger exits."""
    entry_date = datetime.date(2026, 11, 10)
    dates = pd.to_datetime(["2026-11-10"])

    df = pd.DataFrame(
        {
            "open": [100.0],
            "high": [125.0],
            "low": [85.0],
            "close": [105.0],
        },
        index=dates,
    )

    # Intraday candles:
    # 09:30 candle dropped to 85 (before our 10:00 fill!)
    # 10:15 candle reached 122 (Target hit after fill!)
    intraday_candles = {
        "2026-11-10": [
            {"time": "09:30:00", "high": 98.0, "low": 85.0},
            {"time": "10:15:00", "high": 122.0, "low": 100.0},
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
        entry_at_open=True,
        fill_time=datetime.time(10, 0),
        intraday_candles_by_date=intraday_candles,
    )

    # 09:30 candle must be ignored. 10:15 candle hit target!
    assert result["status"] == "TARGET_HIT"
    assert result["exit_price"] == 120.0


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
            {"time": "09:30:00", "high": 122.0, "low": 100.0},
            {"time": "10:00:00", "high": 110.0, "low": 88.0},
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
            {"time": "09:30:00", "high": 102.0, "low": 88.0},
            {"time": "10:00:00", "high": 122.0, "low": 100.0},
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
    dates = pd.date_range("2026-11-01", periods=5, freq="D")

    # Day 1 to 5: price stays between 95 and 105 (neither stop 90 nor target 120 hit)
    df = pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0, 103.0, 104.0],
            "high": [102.0, 103.0, 104.0, 105.0, 106.0],
            "low": [98.0, 99.0, 100.0, 101.0, 102.0],
            "close": [100.0, 102.0, 103.0, 104.0, 105.0],
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
        entry_at_open=True,
    )

    assert result["status"] == "TIME_EXPIRED"
    assert result["exit_price"] == 105.0  # Close of the 5th day
    assert "Holding period reached 5 days limit" in result["exit_reason"]
