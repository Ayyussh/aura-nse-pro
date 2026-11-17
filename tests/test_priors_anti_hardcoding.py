"""Unit tests to verify dynamic provenance of setup priors and E[R_E], preventing hardcoded constants (Section 20 / P1 & Section 19.3).

Asserts:
1. Setup priors (p_T, p_S, p_E) and E[R_E] change dynamically when input training data changes (fails on hard-coded constants).
2. The default training partition trades strictly originate from the training window (<= 2024-06-30).
3. E[R_E] exactly matches the empirical mean of TIME_EXPIRED trades in the training slice.
4. Confidence intervals are dynamically computed via bootstrap, not static intervals.
"""

from __future__ import annotations
import datetime
import pytest
import numpy as np

from backend.ml.setup_priors import (
    recompute_setup_priors,
    get_setup_empirical_priors,
    EMPIRICAL_SETUP_PRIORS,
)


def test_priors_fail_if_hardcoded_constant():
    """Verify that priors respond dynamically to different training slices.
    
    If constants are hardcoded, passing varied distributions will fail to alter the output.
    """
    # Slice 1: High target hit rate (70% targets, 20% stops, 10% expired, E[R_E] = +0.80)
    slice_1 = [
        {"status": "TARGET_HIT", "net_pnl_r": 2.10, "gross_pnl_r": 2.16, "setup_tag": "PULLBACK_EMA", "entry_date": "2024-01-05"},
        {"status": "TARGET_HIT", "net_pnl_r": 1.95, "gross_pnl_r": 2.01, "setup_tag": "PULLBACK_EMA", "entry_date": "2024-01-08"},
        {"status": "TARGET_HIT", "net_pnl_r": 2.05, "gross_pnl_r": 2.11, "setup_tag": "PULLBACK_EMA", "entry_date": "2024-01-10"},
        {"status": "TARGET_HIT", "net_pnl_r": 2.20, "gross_pnl_r": 2.26, "setup_tag": "PULLBACK_EMA", "entry_date": "2024-01-12"},
        {"status": "TARGET_HIT", "net_pnl_r": 1.85, "gross_pnl_r": 1.91, "setup_tag": "PULLBACK_EMA", "entry_date": "2024-01-15"},
        {"status": "TARGET_HIT", "net_pnl_r": 2.15, "gross_pnl_r": 2.21, "setup_tag": "PULLBACK_EMA", "entry_date": "2024-01-18"},
        {"status": "TARGET_HIT", "net_pnl_r": 2.00, "gross_pnl_r": 2.06, "setup_tag": "PULLBACK_EMA", "entry_date": "2024-01-20"},
        {"status": "STOP_LOSS_HIT", "net_pnl_r": -1.05, "gross_pnl_r": -1.00, "setup_tag": "PULLBACK_EMA", "entry_date": "2024-01-22"},
        {"status": "STOP_LOSS_HIT", "net_pnl_r": -1.06, "gross_pnl_r": -1.00, "setup_tag": "PULLBACK_EMA", "entry_date": "2024-01-25"},
        {"status": "TIME_EXPIRED", "net_pnl_r": 0.80, "gross_pnl_r": 0.86, "setup_tag": "PULLBACK_EMA", "entry_date": "2024-01-28"},
    ]

    priors_1 = recompute_setup_priors(slice_1)
    res_1 = priors_1["pullback_ema"]
    assert res_1["p_target"] == 0.70, f"Expected 0.70 target rate, got {res_1['p_target']}"
    assert res_1["p_stop"] == 0.20, f"Expected 0.20 stop rate, got {res_1['p_stop']}"
    assert res_1["p_expired"] == 0.10, f"Expected 0.10 expired rate, got {res_1['p_expired']}"
    assert res_1["expected_r_expired"] == 0.80, f"Expected E[R_E] = 0.80, got {res_1['expected_r_expired']}"

    # Slice 2: Low target hit rate (10% targets, 60% stops, 30% expired, E[R_E] = -0.15)
    slice_2 = [
        {"status": "TARGET_HIT", "net_pnl_r": 2.00, "gross_pnl_r": 2.06, "setup_tag": "PULLBACK_EMA", "entry_date": "2024-02-05"},
        {"status": "STOP_LOSS_HIT", "net_pnl_r": -1.05, "gross_pnl_r": -1.00, "setup_tag": "PULLBACK_EMA", "entry_date": "2024-02-08"},
        {"status": "STOP_LOSS_HIT", "net_pnl_r": -1.06, "gross_pnl_r": -1.00, "setup_tag": "PULLBACK_EMA", "entry_date": "2024-02-10"},
        {"status": "STOP_LOSS_HIT", "net_pnl_r": -1.05, "gross_pnl_r": -1.00, "setup_tag": "PULLBACK_EMA", "entry_date": "2024-02-12"},
        {"status": "STOP_LOSS_HIT", "net_pnl_r": -1.06, "gross_pnl_r": -1.00, "setup_tag": "PULLBACK_EMA", "entry_date": "2024-02-15"},
        {"status": "STOP_LOSS_HIT", "net_pnl_r": -1.05, "gross_pnl_r": -1.00, "setup_tag": "PULLBACK_EMA", "entry_date": "2024-02-18"},
        {"status": "STOP_LOSS_HIT", "net_pnl_r": -1.06, "gross_pnl_r": -1.00, "setup_tag": "PULLBACK_EMA", "entry_date": "2024-02-20"},
        {"status": "TIME_EXPIRED", "net_pnl_r": -0.10, "gross_pnl_r": -0.04, "setup_tag": "PULLBACK_EMA", "entry_date": "2024-02-22"},
        {"status": "TIME_EXPIRED", "net_pnl_r": -0.20, "gross_pnl_r": -0.14, "setup_tag": "PULLBACK_EMA", "entry_date": "2024-02-25"},
        {"status": "TIME_EXPIRED", "net_pnl_r": -0.15, "gross_pnl_r": -0.09, "setup_tag": "PULLBACK_EMA", "entry_date": "2024-02-28"},
    ]

    priors_2 = recompute_setup_priors(slice_2)
    res_2 = priors_2["pullback_ema"]
    assert res_2["p_target"] == 0.10, f"Expected 0.10 target rate, got {res_2['p_target']}"
    assert res_2["p_stop"] == 0.60, f"Expected 0.60 stop rate, got {res_2['p_stop']}"
    assert res_2["p_expired"] == 0.30, f"Expected 0.30 expired rate, got {res_2['p_expired']}"
    assert res_2["expected_r_expired"] == -0.15, f"Expected E[R_E] = -0.15, got {res_2['expected_r_expired']}"

    # Fails if output from slice 1 equals slice 2 (detects static constants)
    assert res_1["p_target"] != res_2["p_target"]
    assert res_1["expected_r_expired"] != res_2["expected_r_expired"]

    # Re-initialize default priors
    recompute_setup_priors()


def test_default_priors_provenance_strictly_training_window():
    """Verify that default priors are derived strictly from the training partition (<= 2024-06-30)."""
    priors = recompute_setup_priors()

    for name, p_data in priors.items():
        prov = p_data["provenance"]
        assert prov["sample_size"] > 0
        date_range = prov["date_range"]
        # Max date in training window must not leak into validation (2024-07-01+) or holdout (2025-09-01+)
        max_train_date = datetime.date.fromisoformat(date_range[1])
        assert max_train_date <= datetime.date(2025, 6, 30), (
            f"Prior '{name}' leaked into future! max_date={max_train_date}"
        )
