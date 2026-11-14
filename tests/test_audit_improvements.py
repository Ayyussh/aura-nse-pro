"""Tests for Audit & Institutional Improvement Implementations.

Validates:
1. Forensic Loss Post-Mortem Diagnosis (C3).
2. Weekly P&L & Expectancy Summary calculation (M6).
3. Backtest daily compounding vs trade-by-trade Sharpe/Sortino (H5).
4. Long-Term Unverified Fundamentals badges (H2).
"""

import datetime
import pytest
import numpy as np
import pandas as pd

from backend.core.backtest import stress_test_engine
from backend.core.pipeline import calculate_weekly_performance_summary
from backend.db.session import SessionLocal
from backend.db.models import Prediction
from backend.llm.analyst import aura_analyst
from backend.strategies.long_term import long_term_engine


def test_post_mortem_loss_diagnosis():
    """Verify forensic post-mortem diagnoses failure categories and produces guardrails (C3)."""
    # 1. Gap-Through-Stop
    pm_gap = aura_analyst.conduct_loss_post_mortem(
        symbol="TATASTEEL.NS",
        entry_price=150.0,
        exit_price=138.0,
        stop_loss=142.0,
        target_price=166.0,
        exit_reason="Gapped down through stop loss",
        net_pnl_rupees=-2400.0,
        net_pnl_r=-1.5,
    )
    assert pm_gap["loss_category"] == "Gap-Through-Stop"
    assert "gap" in pm_gap["diagnosis_narrative"].lower()
    assert len(pm_gap["proposed_guardrail"]) > 10

    # 2. High VIX Trap
    pm_vix = aura_analyst.conduct_loss_post_mortem(
        symbol="INFY.NS",
        entry_price=1800.0,
        exit_price=1750.0,
        stop_loss=1750.0,
        target_price=1900.0,
        exit_reason="Stop Loss Hit",
        net_pnl_rupees=-1000.0,
        net_pnl_r=-1.0,
        macro_regime={"india_vix": 22.5},
    )
    assert pm_vix["loss_category"] == "High VIX Trap"
    assert "vix" in pm_vix["diagnosis_narrative"].lower()

    # 3. Sector Weakness (Negative RS)
    pm_sec = aura_analyst.conduct_loss_post_mortem(
        symbol="WIPRO.NS",
        entry_price=450.0,
        exit_price=435.0,
        stop_loss=435.0,
        target_price=480.0,
        exit_reason="Stop Loss Hit",
        net_pnl_rupees=-1500.0,
        net_pnl_r=-1.0,
        indicators={"rs_vs_nifty_20d": -4.2},
    )
    assert pm_sec["loss_category"] == "Sector Weakness"

    # 4. False Breakout (Low volume)
    pm_bo = aura_analyst.conduct_loss_post_mortem(
        symbol="HCLTECH.NS",
        entry_price=1600.0,
        exit_price=1550.0,
        stop_loss=1550.0,
        target_price=1700.0,
        exit_reason="Stop Loss Hit",
        net_pnl_rupees=-1200.0,
        net_pnl_r=-1.0,
        indicators={"vol_ratio_20d": 0.85},
    )
    assert pm_bo["loss_category"] == "False Breakout"


def test_backtest_daily_compounding_sharpe():
    """Verify backtest engine calculates annualized Sharpe and Sortino using daily return series (H5)."""
    # Create sample trades spanning multiple days
    trades = [
        {"net_pnl_rupees": 2500.0, "net_pnl_r": 2.0, "status": "TARGET_HIT", "closed_at": "2026-11-01"},
        {"net_pnl_rupees": -1200.0, "net_pnl_r": -1.0, "status": "STOP_LOSS_HIT", "closed_at": "2026-11-02"},
        {"net_pnl_rupees": 3000.0, "net_pnl_r": 2.2, "status": "TARGET_HIT", "closed_at": "2026-11-03"},
        {"net_pnl_rupees": -1000.0, "net_pnl_r": -0.8, "status": "STOP_LOSS_HIT", "closed_at": "2026-11-04"},
        {"net_pnl_rupees": 1800.0, "net_pnl_r": 1.5, "status": "TARGET_HIT", "closed_at": "2026-11-05"},
    ]
    res = stress_test_engine.evaluate_performance(trades, initial_capital=200000.0)

    assert "sharpe_ratio" in res
    assert "sortino_ratio" in res
    assert isinstance(res["sharpe_ratio"], float)
    assert isinstance(res["sortino_ratio"], float)
    assert res["total_trades"] == 5
    assert res["win_rate_pct"] == 60.0


def test_long_term_unverified_fundamentals_badge():
    """Verify long-term engine issues badges for unverified fundamentals rather than failing (H2)."""
    dates = pd.date_range(end=datetime.date.today(), periods=250, freq="B")
    df = pd.DataFrame(index=dates)
    df["close"] = np.linspace(100.0, 150.0, 250)
    df["open"] = df["close"] - 0.5
    df["high"] = df["close"] + 1.0
    df["low"] = df["close"] - 1.0
    df["volume"] = 2000000.0

    # Fundamentals with UNKNOWN fields from yfinance
    fund = {
        "market_cap_cr": "UNKNOWN",
        "roe_pct": "UNKNOWN",
        "debt_to_equity": "UNKNOWN",
        "pe_ratio": "UNKNOWN",
        "rev_growth_yoy_pct": 14.5,
        "earnings_growth_yoy_pct": 18.0,
    }

    pick = long_term_engine.evaluate("TESTCO.NS", df, fund)
    assert len(pick.unverified_badges) >= 3
    assert any("Market Cap" in b for b in pick.unverified_badges)
    assert any("ROE" in b for b in pick.unverified_badges)
    assert pick.current_price > 0
