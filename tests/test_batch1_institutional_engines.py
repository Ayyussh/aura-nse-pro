"""Comprehensive Unit Test Suite for Batch 1 Institutional Engines:
1. NSE Demat Delivery % Engine
2. F&O Derivatives Telemetry & Sentiment Engine
3. Global Macro Cross-Asset Factor Suite
"""

import pytest
from backend.data.delivery import delivery_engine, DeliveryMetrics
from backend.data.derivatives import derivatives_engine, IndexDerivativesSnapshot, EquityDerivativesSnapshot
from backend.data.macro_factors import macro_engine, MacroSnapshot
from backend.strategies.regime import evaluate_market_regime
from backend.data.static_exporter import export_all_static_snapshots


def test_delivery_engine_classification_and_metrics():
    """Verify Demat Delivery % calculation, accumulation vs churn tagging."""
    # Test high delivery (institutional accumulation)
    v1, is_acc1, is_churn1 = delivery_engine._classify_delivery(58.5)
    assert v1 == "INSTITUTIONAL_ACCUMULATION"
    assert is_acc1 is True
    assert is_churn1 is False

    # Test solid delivery
    v2, is_acc2, is_churn2 = delivery_engine._classify_delivery(44.0)
    assert v2 == "SOLID_DELIVERY"
    assert is_acc2 is True
    assert is_churn2 is False

    # Test speculative churn
    v3, is_acc3, is_churn3 = delivery_engine._classify_delivery(18.2)
    assert v3 == "SPECULATIVE_CHURN"
    assert is_acc3 is False
    assert is_churn3 is True

    # Test live or fallback fetch for RELIANCE
    metrics = delivery_engine.fetch_delivery_metrics("RELIANCE.NS")
    assert isinstance(metrics, DeliveryMetrics)
    assert metrics.delivery_pct > 0.0
    assert metrics.verdict in ("INSTITUTIONAL_ACCUMULATION", "SOLID_DELIVERY", "NORMAL", "SPECULATIVE_CHURN")


def test_derivatives_engine_pcr_max_pain_and_buildup():
    """Verify Put-Call Ratio (PCR), Max Pain, and Futures Open Interest buildup."""
    snap = derivatives_engine.fetch_index_derivatives("NIFTY")
    assert isinstance(snap, IndexDerivativesSnapshot)
    assert snap.underlying == "NIFTY"
    assert snap.pcr_oi > 0.0
    assert snap.max_pain_strike > 0.0
    assert snap.gamma_resistance_call_strike > 0.0
    assert snap.gamma_support_put_strike > 0.0
    assert snap.sentiment in ("BULLISH", "BEARISH", "NEUTRAL", "EXTREME_OVERSOLD", "EXTREME_OVERBOUGHT")

    # Test Single-stock Futures OI buildup classification
    # Price +1.5%, OI +5.0% -> Long Buildup
    b1 = derivatives_engine.classify_equity_buildup("TRENT.NS", 1.5, 5.0)
    assert b1.buildup_type == "LONG_BUILDUP"

    # Price -2.0%, OI +4.0% -> Short Buildup
    b2 = derivatives_engine.classify_equity_buildup("TRENT.NS", -2.0, 4.0)
    assert b2.buildup_type == "SHORT_BUILDUP"

    # Price +1.0%, OI -3.0% -> Short Covering
    b3 = derivatives_engine.classify_equity_buildup("TRENT.NS", 1.0, -3.0)
    assert b3.buildup_type == "SHORT_COVERING"

    # Price -1.0%, OI -4.0% -> Long Unwinding
    b4 = derivatives_engine.classify_equity_buildup("TRENT.NS", -1.0, -4.0)
    assert b4.buildup_type == "LONG_UNWINDING"


def test_global_macro_factor_engine_and_mpi():
    """Verify Global Macro Cross-Asset Factor suite and Macro Pressure Index (MPI)."""
    macro_snap = macro_engine.fetch_macro_snapshot()
    assert isinstance(macro_snap, MacroSnapshot)
    assert 0.0 <= macro_snap.macro_pressure_index <= 100.0
    assert macro_snap.regime_impact in ("GOLDILOCKS", "NEUTRAL", "HEADWIND", "CRITICAL_HEADWIND")
    assert macro_snap.brent_crude.current_value > 0.0
    assert macro_snap.us_10y_yield.current_value > 0.0
    assert macro_snap.usdinr.current_value > 0.0
    assert macro_snap.dxy.current_value > 0.0
    assert len(macro_snap.tailwinds) > 0 or len(macro_snap.headwinds) > 0


def test_regime_integration_with_macro_and_derivatives():
    """Verify that market regime evaluation cleanly incorporates macro and derivatives."""
    regime = evaluate_market_regime()
    assert "macro_pressure_index" in regime
    assert "macro_regime_impact" in regime
    assert "macro_factors" in regime
    assert "derivatives_telemetry" in regime
    assert 0.0 <= regime["macro_pressure_index"] <= 100.0


def test_static_exporter_exports_batch1_snapshots():
    """Verify that static_exporter generates macro_snapshot.json and derivatives_matrix.json."""
    counts = export_all_static_snapshots()
    assert counts.get("macro_snapshot", 0) == 1
    assert counts.get("derivatives_matrix", 0) == 1
