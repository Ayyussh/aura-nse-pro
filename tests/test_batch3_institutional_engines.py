"""Tests for Institutional Batch 3 Engines:
1. Automated Broker OMS / EMS API (Upstox GTT OCO Orders)
2. Hierarchical Risk Parity (HRP) Portfolio Optimizer
3. Market-Neutral & Tail-Risk Put Hedging Engine
"""

import pytest
import pandas as pd
import numpy as np

from backend.execution.oms import UpstoxOrderManager, OrderResult
from backend.risk.portfolio_optimizer import HierarchicalRiskParityOptimizer, HRPOptimizationResult
from backend.strategies.hedging import HedgingEngine, PutHedgeRecommendation, ShortCandidate


def test_oms_gtt_oco_paper_execution():
    oms = UpstoxOrderManager(mode="PAPER")

    # Valid GTT OCO Order
    res = oms.place_gtt_oco_order(
        symbol="RELIANCE.NS",
        quantity=50,
        entry_price=1280.0,
        target_price=1380.0,
        stop_loss_price=1230.0,
    )
    assert res.status == "PAPER_FILLED"
    assert res.is_paper is True
    assert res.symbol == "RELIANCE"
    assert res.quantity == 50
    assert res.price == 1280.0
    assert res.target_price == 1380.0
    assert res.stop_loss_price == 1230.0


def test_oms_gtt_oco_validation_rejections():
    oms = UpstoxOrderManager(mode="PAPER")

    # 1. Invalid price structure (Stop loss above entry)
    r1 = oms.place_gtt_oco_order(
        symbol="TCS",
        quantity=25,
        entry_price=3500.0,
        target_price=3800.0,
        stop_loss_price=3600.0,  # Invalid: stop > entry
    )
    assert r1.status == "REJECTED"
    assert "Invalid GTT OCO price structure" in r1.message

    # 2. Invalid quantity
    r2 = oms.place_gtt_oco_order(
        symbol="INFY",
        quantity=0,
        entry_price=1800.0,
        target_price=1950.0,
        stop_loss_price=1750.0,
    )
    assert r2.status == "REJECTED"
    assert "Quantity must be greater than 0" in r2.message


def test_hrp_portfolio_optimizer():
    optimizer = HierarchicalRiskParityOptimizer(max_weight=0.35, min_weight=0.05)

    # Generate synthetic 1-year returns for 4 correlated assets
    np.random.seed(42)
    n_days = 252
    dates = pd.date_range("2025-01-01", periods=n_days, freq="B")

    # Common market factor + idiosyncratic returns
    market = np.random.normal(0.0005, 0.01, n_days)
    r_hcl = market * 0.8 + np.random.normal(0, 0.015, n_days)
    r_tcs = market * 0.9 + np.random.normal(0, 0.012, n_days)
    r_itc = market * 0.3 + np.random.normal(0, 0.010, n_days)
    r_lt = market * 1.2 + np.random.normal(0, 0.020, n_days)

    returns_df = pd.DataFrame({
        "HCLTECH": r_hcl,
        "TCS": r_tcs,
        "ITC": r_itc,
        "LT": r_lt,
    }, index=dates)

    res = optimizer.optimize(returns_df, total_capital=1_000_000.0)

    assert isinstance(res, HRPOptimizationResult)
    assert res.status in ("OPTIMAL", "FALLBACK_INVERSE_VOL")
    assert res.num_assets == 4
    assert len(res.allocations) == 4

    # Weights must sum to approximately 1.0 (100%)
    total_weight = sum(res.weights.values())
    assert pytest.approx(total_weight, abs=0.01) == 1.0

    # Low vol asset (ITC) should generally get higher or equal allocation compared to high vol (LT)
    assert res.weights["ITC"] >= res.weights["LT"]
    assert res.diversification_ratio >= 1.0


def test_hrp_single_asset():
    optimizer = HierarchicalRiskParityOptimizer()
    dates = pd.date_range("2025-01-01", periods=50, freq="B")
    returns_df = pd.DataFrame({"TITAN": np.random.normal(0.001, 0.015, 50)}, index=dates)

    res = optimizer.optimize(returns_df, total_capital=500_000.0)
    assert res.status == "SINGLE_ASSET"
    assert res.weights["TITAN"] == 1.0
    assert res.allocations[0].rupee_allocation == 500_000.0


def test_put_hedge_recommendation():
    engine = HedgingEngine()

    # 1. GREEN Regime -> No hedge required
    rec_green = engine.calculate_nifty_put_hedge(
        portfolio_value=1_000_000.0,
        portfolio_beta=1.1,
        nifty_ltp=25_000.0,
        macro_regime="GREEN"
    )
    assert rec_green.hedge_required is False
    assert rec_green.contract_count == 0

    # 2. RED Regime -> Full 100% hedge required
    rec_red = engine.calculate_nifty_put_hedge(
        portfolio_value=1_000_000.0,
        portfolio_beta=1.0,
        nifty_ltp=25_000.0,
        macro_regime="RED"
    )
    assert rec_red.hedge_required is True
    # 1,000,000 / (25,000 * 25) = 1,000,000 / 625,000 = ~1.6 -> 2 contracts
    assert rec_red.contract_count >= 1
    assert rec_red.recommended_strike == 24400.0 or rec_red.recommended_strike == 24350.0
    assert rec_red.estimated_cost_rupees > 0


def test_bearish_short_screener():
    engine = HedgingEngine()

    # Generate synthetic breakdown series (Close < EMA50 < SMA200 with RSI in 30-45)
    n = 220
    dates = pd.date_range("2026-01-01", periods=n, freq="B")
    close = np.linspace(200, 100, n)  # Downtrend
    df = pd.DataFrame({
        "open": close * 1.01,
        "high": close * 1.02,
        "low": close * 0.98,
        "close": close,
        "volume": [1_000_000] * n,
    }, index=dates)

    # NIFTY flat to positive so stock has negative RS
    nifty_df = pd.DataFrame({
        "close": [25000.0] * n,
    }, index=dates)

    short_cand = engine.evaluate_short_setup("BEARSTOCK", df, nifty_df)
    assert isinstance(short_cand, ShortCandidate)
    # The downward slope puts RSI into 30-48 range
    assert short_cand.entry_price == 100.0
    assert short_cand.stop_loss > short_cand.entry_price
    assert short_cand.target_price < short_cand.entry_price
