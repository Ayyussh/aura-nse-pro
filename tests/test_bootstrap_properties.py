"""Tests for Bootstrap Properties, Centrality, and Verdict Wording."""

import datetime
import numpy as np
import pandas as pd
import pytest

from backend.core.verdict_generator import generate_verdict_wording


def compute_week_block_bootstrap_ci(
    trades: list[dict[str, float | str]],
    metric_key: str = "r",
    num_reps: int = 1000,
    seed: int = 42,
) -> tuple[float, float, float]:
    """Stationary week-block bootstrap confidence interval."""
    if not trades:
        return (0.0, 0.0, 0.0)

    trades_df = pd.DataFrame(trades)
    week_groups = {w: group[metric_key].values for w, group in trades_df.groupby("week")}
    mean_obs = float(trades_df[metric_key].mean())

    weeks = list(week_groups.keys())
    if len(weeks) < 2:
        return (round(mean_obs, 4), round(mean_obs, 4), round(mean_obs, 4))

    rng = np.random.RandomState(seed)
    n_weeks = len(weeks)
    boot_means = []

    for _ in range(num_reps):
        sampled_weeks = rng.choice(weeks, size=n_weeks, replace=True)
        sampled_vals = np.concatenate([week_groups[w] for w in sampled_weeks])
        if len(sampled_vals) > 0:
            boot_means.append(float(np.mean(sampled_vals)))

    lower = float(np.percentile(boot_means, 2.5))
    upper = float(np.percentile(boot_means, 97.5))
    return (round(mean_obs, 4), round(lower, 4), round(upper, 4))


def test_verdict_wording_rules():
    """Rule: 'edge' may appear ONLY when ci_lower > 0.0."""
    # Case 1: Confirmed edge (lower > 0)
    v1 = generate_verdict_wording(ci_lower=0.05, ci_upper=0.35, mean_r=0.20)
    assert "Statistically significant edge confirmed" in v1

    # Case 2: Positive mean, but spans zero (lower <= 0)
    v2 = generate_verdict_wording(ci_lower=-0.04, ci_upper=0.30, mean_r=0.13)
    assert "edge not statistically confirmed" in v2
    assert "Statistically significant edge confirmed" not in v2

    # Case 3: Exactly zero lower bound
    v3 = generate_verdict_wording(ci_lower=0.00, ci_upper=0.25, mean_r=0.12)
    assert "edge not statistically confirmed" in v3
    assert "Statistically significant edge confirmed" not in v3

    # Case 4: Negative mean
    v4 = generate_verdict_wording(ci_lower=-0.40, ci_upper=-0.05, mean_r=-0.22)
    assert "no statistical advantage" in v4
    assert "edge" not in v4.lower()


def test_bootstrap_estimate_inside_interval_and_central():
    """Audit: for multi-week samples, mean is strictly inside CI and roughly central."""
    rng = np.random.RandomState(42)
    # 150 calendar weeks
    weeks = [f"2023-W{i:02d}" for i in range(1, 53)] + [f"2024-W{i:02d}" for i in range(1, 53)] + [f"2025-W{i:02d}" for i in range(1, 40)]
    trades = []
    for w in weeks:
        n_trades = rng.poisson(lam=3)
        for _ in range(n_trades):
            trades.append({"week": w, "r": float(rng.normal(loc=0.18, scale=1.1))})

    mean_obs, ci_low, ci_high = compute_week_block_bootstrap_ci(trades, metric_key="r", num_reps=1000)

    # 1. Assert mean lies strictly inside interval
    assert ci_low < mean_obs < ci_high, f"Mean {mean_obs} must lie strictly inside [{ci_low}, {ci_high}]"

    # 2. Assert estimate is roughly central (asymmetry < 0.20)
    width = ci_high - ci_low
    assert width > 0
    left_dist = mean_obs - ci_low
    right_dist = ci_high - mean_obs
    asymmetry = abs(left_dist - right_dist) / width
    assert asymmetry < 0.20, f"Asymmetry {asymmetry:.4f} exceeds 0.20 threshold (not roughly central)"
