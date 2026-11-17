"""Section 21.1 Item 2 Test: Candidate Ranking Anti-Lookahead Invariant.

Verifies that:
1. Permuting, perturbing, or corrupting market data on or after Day D+1 leaves the candidate ranking on Day D strictly unchanged.
2. The candidate rank order depends exclusively on point-in-time Day D indicators.
"""

import datetime
import numpy as np
import pandas as pd
import pytest

from scripts.generate_candidate_level_report import rank_candidates


def test_permuting_future_data_leaves_ranking_unchanged():
    """Verify ranking on Day D is completely invariant to future bar permutations."""
    # Synthetic candidate batch on Day D
    candidates = [
        {"symbol": "RELIANCE.NS", "ev_r": 0.45, "win_probability": 0.52, "mansfield_rs": 4.5, "future_bars": [100, 102, 105]},
        {"symbol": "TCS.NS", "ev_r": 0.38, "win_probability": 0.48, "mansfield_rs": 2.1, "future_bars": [200, 198, 195]},
        {"symbol": "INFY.NS", "ev_r": 0.55, "win_probability": 0.54, "mansfield_rs": 6.2, "future_bars": [300, 310, 320]},
        {"symbol": "HDFCBANK.NS", "ev_r": 0.38, "win_probability": 0.48, "mansfield_rs": 3.8, "future_bars": [400, 405, 410]},
    ]

    # Baseline ranking on Day D
    ranked_orig = rank_candidates(candidates)
    orig_symbols = [c["symbol"] for c in ranked_orig]

    # Expected order: INFY (0.55), RELIANCE (0.45), HDFCBANK (0.38, RS 3.8), TCS (0.38, RS 2.1)
    assert orig_symbols == ["INFY.NS", "RELIANCE.NS", "HDFCBANK.NS", "TCS.NS"]

    # Perturb and permute future data (simulating future market fluctuations / lookahead corruption)
    rng = np.random.RandomState(42)
    corrupted_candidates = []
    for c in candidates:
        corrupted = dict(c)
        # Corrupt future bars completely
        corrupted["future_bars"] = list(rng.permutation([9999, -500, 12345]))
        corrupted["future_outcome_hypothetical"] = float(rng.uniform(-10, 10))
        corrupted_candidates.append(corrupted)

    # Re-rank candidates on Day D
    ranked_after_corrupt = rank_candidates(corrupted_candidates)
    corrupted_symbols = [c["symbol"] for c in ranked_after_corrupt]

    # Invariant: Ranking must be 100% IDENTICAL
    assert corrupted_symbols == orig_symbols, (
        f"Lookahead leak detected! Corrupting future data altered Day D ranking: {corrupted_symbols} != {orig_symbols}"
    )
