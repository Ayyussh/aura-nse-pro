"""Unit Tests for Setup Priors Provenance & Symbol Master Splice Restrictions (Section 20 / P1).

Verifies:
1. Every prior in setup_priors has verifiable query provenance, sample size, and date range.
2. 'compounder' and non-swing setups are strictly removed from swing priors.
3. Recomputation from training trades works dynamically and updates bootstrap intervals.
4. Symbol master refuses splicing across demergers/mergers/conversions and enforces 20-day quarantine.
"""

from __future__ import annotations
import datetime
import pytest

from backend.ml.setup_priors import (
    recompute_setup_priors,
    get_setup_empirical_priors,
    EMPIRICAL_SETUP_PRIORS,
)
from backend.data.symbol_master import symbol_master, SymbolMaster


def test_setup_priors_provenance_and_non_swing_exclusion():
    """Verify priors have full provenance and strictly exclude non-swing setups."""
    priors = recompute_setup_priors()

    # Must contain canonical swing setups only
    assert "pullback_ema" in priors
    assert "breakout_vcp" in priors
    assert "mean_reversion" in priors
    assert "default" in priors

    # 'compounder' must NOT exist in swing setup priors
    assert "compounder" not in priors

    for name, p_data in priors.items():
        assert "provenance" in p_data, f"Prior {name} missing provenance"
        prov = p_data["provenance"]
        assert "query" in prov
        assert "sample_size" in prov
        assert "date_range" in prov
        assert "computed_at" in prov
        assert prov["sample_size"] > 0, f"Sample size for {name} must be > 0"

        # Verify probability sum: p_target + p_stop + p_expired == 1.0 (approx)
        p_sum = p_data["p_target"] + p_data["p_stop"] + p_data["p_expired"]
        assert abs(p_sum - 1.0) <= 0.02, f"Probabilities for {name} must sum to 1.0, got {p_sum}"

        # Verify confidence intervals
        assert p_data["p_target_ci_95"][0] <= p_data["p_target"] <= p_data["p_target_ci_95"][1]
        assert p_data["p_stop_ci_95"][0] <= p_data["p_stop"] <= p_data["p_stop_ci_95"][1]
        assert p_data["p_expired_ci_95"][0] <= p_data["p_expired"] <= p_data["p_expired_ci_95"][1]
        assert p_data["cost_r_ci_95"][0] <= p_data["cost_r"] <= p_data["cost_r_ci_95"][1]


def test_recompute_setup_priors_with_custom_training_slice():
    """Verify that recompute_setup_priors recalculates correctly on supplied trades."""
    synthetic_trades = [
        {"status": "TARGET_HIT", "net_pnl_r": 2.0, "gross_pnl_r": 2.06, "entry_date": "2025-01-10", "setup_tag": "PULLBACK"},
        {"status": "STOP_LOSS_HIT", "net_pnl_r": -1.06, "gross_pnl_r": -1.0, "entry_date": "2025-01-12", "setup_tag": "PULLBACK"},
        {"status": "TIME_EXPIRED", "net_pnl_r": 0.45, "gross_pnl_r": 0.51, "entry_date": "2025-01-15", "setup_tag": "PULLBACK"},
        {"status": "TIME_EXPIRED", "net_pnl_r": 0.35, "gross_pnl_r": 0.41, "entry_date": "2025-01-18", "setup_tag": "PULLBACK"},
    ]

    priors = recompute_setup_priors(synthetic_trades)
    assert priors["default"]["sample_size"] == 4
    assert priors["default"]["p_target"] == 0.25
    assert priors["default"]["p_stop"] == 0.25
    assert priors["default"]["p_expired"] == 0.50
    assert priors["default"]["expected_r_expired"] == 0.40  # mean(0.45, 0.35)
    assert priors["default"]["cost_r"] == 0.06  # mean(0.06, 0.06, 0.06, 0.06)

    # Restore clean default priors from disk
    recompute_setup_priors()



def test_symbol_master_splice_and_exclusion_window_rules():
    """Verify that SymbolMaster strictly blocks unadjusted history splicing across restructurings."""
    # 1. ZOMATO -> ETERNAL (Pure rename) allows splicing
    can_splice, reason = symbol_master.can_splice_history("ZOMATO.NS", "ETERNAL.NS", datetime.date(2025, 3, 1))
    assert can_splice is True
    assert "Allowed" in reason

    # 2. TATAMOTORS -> TMPV (Demerger) strictly prohibits splicing
    can_splice_tm, reason_tm = symbol_master.can_splice_history("TATAMOTORS.NS", "TMPV.NS", datetime.date(2025, 11, 1))
    assert can_splice_tm is False
    assert "strictly prohibits unadjusted price splicing" in reason_tm

    # 3. HDFC -> HDFCBANK (Merger) strictly prohibits splicing
    can_splice_hdfc, reason_hdfc = symbol_master.can_splice_history("HDFC.NS", "HDFCBANK.NS", datetime.date(2023, 8, 1))
    assert can_splice_hdfc is False
    assert "strictly prohibits unadjusted price splicing" in reason_hdfc

    # 4. Exclusion window check for TMCV right after listing (within 20 days)
    is_excl, excl_reason = symbol_master.is_in_exclusion_window("TMCV.NS", datetime.date(2025, 11, 20))
    assert is_excl is True
    assert "quarantine" in excl_reason

    # After 20 days, exclusion window clears
    is_excl_after, _ = symbol_master.is_in_exclusion_window("TMCV.NS", datetime.date(2025, 12, 15))
    assert is_excl_after is False
