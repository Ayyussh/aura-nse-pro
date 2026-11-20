"""Unit test for Tier-2 Momentum Watchlist Screening and Static Export."""

import pytest
import pandas as pd
import numpy as np
from backend.strategies.swing import swing_engine, SwingCandidate
from backend.data.static_exporter import export_all_static_snapshots


def test_tier_2_candidate_detection():
    """Verify that an uptrending stock with positive RS but consolidating with sub-threshold breakout volume is classified as Tier-2."""
    dates = pd.date_range("2025-01-01", periods=250, freq="B")
    
    # Construct an uptrending price series (Close > EMA50 > SMA200)
    # Price rises smoothly from 100 to 190 over 235 bars, then consolidates near 190 for last 15 bars
    trend_part = np.linspace(100, 190, 235)
    consol_part = np.linspace(189, 191, 15)
    base_price = np.concatenate([trend_part, consol_part])
    
    # Add minor noise
    np.random.seed(42)
    close = base_price + np.random.normal(0, 0.3, 250)
    high = close + 1.2
    low = close - 1.2
    open_p = close - 0.1
    # Volume is low (e.g. 0.8x of average, so it fails Tier-1 volume > 1.2x SMA20)
    volume = np.full(250, 100000.0)
    volume[-1] = 80000.0  # volume ratio ~ 0.8x

    df = pd.DataFrame(
        {"open": open_p, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )

    # Benchmark NIFTY series (slower rise from 100 to 120, so stock has strong RS)
    nifty_close = np.linspace(100, 120, 250)
    nifty_df = pd.DataFrame(
        {"open": nifty_close, "high": nifty_close + 1, "low": nifty_close - 1, "close": nifty_close, "volume": volume},
        index=dates,
    )

    cand = swing_engine.evaluate("TEST_TIER2.NS", df, nifty_df)

    # It should NOT pass Tier-1 because volume ratio is 0.8x (requires > 1.2x)
    assert not cand.passed
    assert any("Volume ratio" in r for r in cand.rejection_reasons)

    # BUT it SHOULD qualify as Tier-2 Watchlist
    assert cand.is_tier_2 is True
    assert cand.tier_2_score > 0.0
    assert len(cand.tier_2_reason) > 0


def test_static_exporter_exports_tier_2_and_swing_watchlist():
    """Verify that static_exporter exports both today_predictions with tier_2 and swing_watchlist.json."""
    counts = export_all_static_snapshots()
    assert "today_predictions" in counts
    assert "swing_watchlist" in counts
