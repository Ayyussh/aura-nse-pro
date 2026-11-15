"""Unit and Invariant Tests for Mutation Guards (Section 19.2 / Housekeeping).

Validates the three critical behavioral invariants:
1. Grader Entry-Bar Filtering Invariant: Prior bars before entry date MUST NOT trigger exits.
2. Charges GST Scope Invariant: GST (18%) MUST apply strictly to Brokerage, Exchange Txn Charges,
   and SEBI Turnover Fee. GST must NEVER apply to STT or Stamp Duty.
3. Three-Outcome EV Invariant: EV_R must incorporate time-expired expected return E[R_E].
   Omitting p_E reduces EV and mismodels portfolio return.
"""

import datetime
import pytest
import pandas as pd
import numpy as np

from backend.core.grader import grade_trade_outcome
from backend.costs.charges import charges_engine
from backend.ml.predictor import ml_predictor


def test_grader_entry_bar_filtering_invariant():
    """Verify that price action prior to the trade entry date has zero effect on grading."""
    entry_date = datetime.date(2026, 8, 10)
    stop_loss = 490.0
    target_price = 530.0
    entry_price = 500.0

    # Synthetic bars where pre-entry day (2026-08-07) had severe dip below stop (475.0)
    # But from entry date (2026-08-10) onward, price opens at 500.0 and climbs cleanly to target (535.0)
    dates = pd.date_range("2026-08-07", periods=5, freq="B")
    data = {
        "open": [495.0, 500.0, 510.0, 520.0, 532.0],
        "high": [500.0, 510.0, 522.0, 532.0, 540.0],
        "low": [475.0, 498.0, 505.0, 515.0, 528.0],  # 2026-08-07 hit 475.0 (below stop, pre-entry)
        "close": [480.0, 508.0, 518.0, 528.0, 535.0],
        "volume": [10000] * 5,
    }
    history_df = pd.DataFrame(data, index=dates)

    res = grade_trade_outcome(
        symbol="TEST.NS",
        entry_date=entry_date,
        entry_price=entry_price,
        stop_loss=stop_loss,
        target_price=target_price,
        quantity=10,
        time_limit_days=10,
        history_df=history_df,
        entry_at_open=True,
    )

    # Must be TARGET_HIT because the 475.0 low occurred BEFORE entry_date!
    assert res["status"] == "TARGET_HIT", f"Expected TARGET_HIT, got {res['status']}"
    assert res["exit_price"] == 530.0


def test_charges_gst_scope_strictly_excludes_stt_and_stamp():
    """Verify that GST is strictly 18% of (brokerage + exchange_txn + sebi_fee)."""
    buy_price = 1000.0
    sell_price = 1100.0
    quantity = 100
    res = charges_engine.calculate_delivery_charges(buy_price, sell_price, quantity)

    expected_gst_base = res.brokerage + res.exchange_txn_charge + res.sebi_fee
    expected_gst = round(expected_gst_base * 0.18, 2)

    assert abs(res.gst - expected_gst) <= 0.02, f"GST ₹{res.gst} does not match expected ₹{expected_gst}"

    # Verify STT and Stamp Duty are NOT in GST base
    total_turnover = (buy_price * quantity) + (sell_price * quantity)
    illegal_gst_on_turnover = round(total_turnover * 0.18, 2)
    assert res.gst < (illegal_gst_on_turnover * 0.05), "GST appears to be incorrectly computed on turnover!"


def test_three_outcome_ev_incorporates_time_expiry():
    """Verify that EV calculation accounts for Day 10 time-expired exits with E[R_E]."""
    features = {
        "rsi_14": 58.0,
        "adx_14": 25.0,
        "dist_ema20_pct": 1.5,
        "dist_ema50_pct": 3.0,
        "dist_sma200_pct": 8.0,
        "dist_52w_high_pct": 4.0,
        "rs_vs_nifty_20d": 3.5,
        "vol_ratio_20d": 1.4,
    }

    # Evaluate three-outcome model
    pred = ml_predictor.predict_probability(
        features=features,
        target_r=2.0,
        stop_r=1.0,
        expected_r_expired=0.37,
        cost_r=0.062,
    )

    assert pred["three_outcome_model"] is True
    assert abs(pred["probabilities_sum"] - 1.0) < 0.001
    assert "p_target" in pred
    assert "p_stop" in pred
    assert "p_expired" in pred

    # Mathematical identity check:
    # EV_R = (p_target * target_r) - (p_stop * stop_r) + (p_expired * expected_r_expired) - cost_r
    manual_ev = (pred["p_target"] * 2.0) - (pred["p_stop"] * 1.0) + (pred["p_expired"] * 0.37) - 0.062
    assert abs(pred["ev_r"] - round(manual_ev, 3)) <= 0.01
