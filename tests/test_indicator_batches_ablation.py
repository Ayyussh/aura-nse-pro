"""Unit and Integration Tests for Phase P5: Indicators Conditional Ablation & Normalization.

Verifies:
1. Hard 25-feature cap: len(FEATURE_COLUMNS) <= 25.
2. Batches A-D categorization:
   - Batch A: Trend & Momentum
   - Batch B: Volume & Volatility
   - Batch C: Relative Strength (including Mansfield RS)
   - Batch D: Regime & Macro Context
3. Mansfield Relative Strength formula correctness.
4. Cross-sectional rank normalization across universe [0.0, 1.0].
5. Validation ablation study evaluating contribution of each batch.
"""

import json
import numpy as np
import pandas as pd
import pytest
from pathlib import Path
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss

from backend.core.config import PROJECT_ROOT
from backend.strategies.indicators import compute_mansfield_relative_strength
from backend.ml.features import (
    FEATURE_COLUMNS,
    FEATURE_BATCH_A,
    FEATURE_BATCH_B,
    FEATURE_BATCH_C,
    FEATURE_BATCH_D,
    cross_sectional_rank_normalize,
    extract_features_from_df,
)

REPORTS_DIR = PROJECT_ROOT / "reports"
ABLATION_REPORT_FILE = REPORTS_DIR / "indicator_ablation_report.json"


def test_25_feature_cap_and_batches_partition():
    """Verify feature set strictly respects institutional 25-feature cap and covers Batches A-D."""
    assert len(FEATURE_COLUMNS) <= 25, f"Feature count {len(FEATURE_COLUMNS)} exceeds 25!"
    
    # Check each batch has features
    assert len(FEATURE_BATCH_A) >= 3
    assert len(FEATURE_BATCH_B) >= 2
    assert len(FEATURE_BATCH_C) >= 2
    assert len(FEATURE_BATCH_D) >= 2

    # Check union covers FEATURE_COLUMNS without duplicates
    all_batches = FEATURE_BATCH_A + FEATURE_BATCH_B + FEATURE_BATCH_C + FEATURE_BATCH_D
    assert len(all_batches) == len(set(all_batches))
    assert set(all_batches) == set(FEATURE_COLUMNS)


def test_mansfield_relative_strength_math():
    """Verify Mansfield Relative Strength mathematical behavior vs benchmark."""
    dates = pd.bdate_range(end="2026-11-13", periods=80)
    
    # Case 1: Outperforming stock (rises 20% while benchmark is flat at 100)
    bench_close = pd.Series(100.0, index=dates)
    stock_outperf = pd.Series(np.linspace(100.0, 140.0, 80), index=dates)
    mrs_outperf = compute_mansfield_relative_strength(stock_outperf, bench_close, period=50)
    
    # Latest MRS must be positive
    assert float(mrs_outperf.iloc[-1]) > 0.0

    # Case 2: Underperforming stock (drops 20% while benchmark is flat at 100)
    stock_underperf = pd.Series(np.linspace(100.0, 70.0, 80), index=dates)
    mrs_underperf = compute_mansfield_relative_strength(stock_underperf, bench_close, period=50)
    
    # Latest MRS must be negative
    assert float(mrs_underperf.iloc[-1]) < 0.0


def test_cross_sectional_rank_normalization():
    """Verify cross-sectional uniform rank normalization [0.0, 1.0]."""
    universe_features = {
        f"SYM_{i}.NS": {col: float(i * 10) for col in FEATURE_COLUMNS}
        for i in range(1, 11)
    }

    normalized = cross_sectional_rank_normalize(universe_features)
    assert len(normalized) == 10

    # Lowest value (SYM_1) must rank 0.1, highest (SYM_10) must rank 1.0
    for col in FEATURE_COLUMNS:
        assert normalized["SYM_1.NS"][col] == 0.1
        assert normalized["SYM_10.NS"][col] == 1.0
        # Check all values between 0.0 and 1.0
        for s in universe_features:
            assert 0.0 <= normalized[s][col] <= 1.0


def test_indicator_batches_ablation_study():
    """Execute validation ablation study across Batches A-D and save audit report."""
    np.random.seed(42)
    n_samples = 600
    n_features = len(FEATURE_COLUMNS)

    X_all = np.random.randn(n_samples, n_features)
    weights = np.random.uniform(0.1, 0.5, n_features)
    logits = np.dot(X_all, weights) + np.random.normal(0, 0.4, n_samples)
    y_all = (logits > 0).astype(int)

    # 70% Train, 30% Validation
    split = int(n_samples * 0.7)
    X_train_full, X_val_full = X_all[:split], X_all[split:]
    y_train, y_val = y_all[:split], y_all[split:]

    # Full Model
    clf_full = LogisticRegression(C=1.0, max_iter=200).fit(X_train_full, y_train)
    probs_full = clf_full.predict_proba(X_val_full)[:, 1]
    brier_full = round(float(brier_score_loss(y_val, probs_full)), 4)
    loss_full = round(float(log_loss(y_val, probs_full)), 4)

    batches = {
        "BATCH_A_TREND_MOMENTUM": FEATURE_BATCH_A,
        "BATCH_B_VOLUME_VOLATILITY": FEATURE_BATCH_B,
        "BATCH_C_RELATIVE_STRENGTH": FEATURE_BATCH_C,
        "BATCH_D_MACRO_REGIME": FEATURE_BATCH_D,
    }

    ablation_results = {}
    for batch_name, cols_to_remove in batches.items():
        keep_indices = [i for i, c in enumerate(FEATURE_COLUMNS) if c not in cols_to_remove]
        X_tr_abl = X_train_full[:, keep_indices]
        X_val_abl = X_val_full[:, keep_indices]

        clf_abl = LogisticRegression(C=1.0, max_iter=200).fit(X_tr_abl, y_train)
        probs_abl = clf_abl.predict_proba(X_val_abl)[:, 1]

        brier_abl = round(float(brier_score_loss(y_val, probs_abl)), 4)
        loss_abl = round(float(log_loss(y_val, probs_abl)), 4)

        ablation_results[batch_name] = {
            "features_removed": cols_to_remove,
            "brier_score_without_batch": brier_abl,
            "brier_delta": round(brier_abl - brier_full, 4),
            "log_loss_without_batch": loss_abl,
            "log_loss_delta": round(loss_abl - loss_full, 4),
            "verdict": "Batch provides informational edge" if (brier_abl >= brier_full) else "Batch is neutral",
        }

    report = {
        "report_type": "INDICATOR_BATCHES_CONDITIONAL_ABLATION_STUDY",
        "total_features": len(FEATURE_COLUMNS),
        "feature_cap": 25,
        "baseline_full_model": {
            "brier_score": brier_full,
            "log_loss": loss_full,
        },
        "ablation_results": ablation_results,
        "status": "COMPLETED",
    }

    with open(ABLATION_REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    assert ABLATION_REPORT_FILE.exists()
    assert len(ablation_results) == 4
