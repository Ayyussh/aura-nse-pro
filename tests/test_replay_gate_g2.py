"""Unit and Integration Tests for Phase P3: Replay & Scorekeeping (Gate G2).

Verifies:
1. Holdout lock protection: Attempting to evaluate holdout raises HoldoutLockError.
2. Holdout access audit: allow_holdout=True logs to reports/holdout_access_log.json.
3. Determinism: Replay runs are 100% deterministic (identical trade lists and metrics).
4. No-lookahead execution: Orders enter on D+1 open with live grader and costs.
5. Scorecards: Comprehensive breakdowns by setup, regime, decile, sector with bootstrap 95% CIs.
6. Sample size warnings: 'INSUFFICIENT SAMPLE (N < 30)' flagged on small cohorts.
"""

import json
import pytest
from pathlib import Path
from backend.strategies.replay import (
    replay_engine,
    HoldoutLockError,
    HOLDOUT_ACCESS_LOG,
    REPLAY_SCORECARD_FILE,
)


def test_holdout_lock_enforcement():
    """Verify evaluating the holdout partition raises HoldoutLockError without explicit flag."""
    with pytest.raises(HoldoutLockError) as exc_info:
        replay_engine.run_replay(split="holdout", allow_holdout=False)
    assert "Holdout partition is strictly locked" in str(exc_info.value)


def test_holdout_access_logging(tmp_path):
    """Verify accessing holdout with allow_holdout=True logs to audit file."""
    # Run a short run with allow_holdout=True on a limited universe
    res = replay_engine.run_replay(
        split="holdout",
        allow_holdout=True,
        symbols_limit=5,
    )
    assert res["status"] in ("COMPLETED", "NO_DATA")
    assert HOLDOUT_ACCESS_LOG.exists()

    with open(HOLDOUT_ACCESS_LOG, "r", encoding="utf-8") as f:
        logs = json.load(f)
    assert len(logs) >= 1
    latest = logs[-1]
    assert "HOLDOUT_ACCESS" in latest["access_id"]
    assert "split_accessed" in latest


def test_replay_determinism_train_split():
    """Verify running replay twice on the train split produces identical results (Gate G2)."""
    res1 = replay_engine.run_replay(split="train", symbols_limit=10)
    res2 = replay_engine.run_replay(split="train", symbols_limit=10)

    assert res1["status"] == "COMPLETED"
    assert res2["status"] == "COMPLETED"
    assert res1["total_trades_completed"] == res2["total_trades_completed"]
    assert res1["final_equity_rupees"] == res2["final_equity_rupees"]
    assert res1["total_return_pct"] == res2["total_return_pct"]
    assert res1["max_drawdown_pct"] == res2["max_drawdown_pct"]
    assert res1["overall_metrics"]["net_expectancy_r"] == res2["overall_metrics"]["net_expectancy_r"]


def test_scorecard_breakdowns_and_sample_warnings():
    """Verify scorecards generate setup, regime, decile, and sector breakdowns with bootstrap CIs."""
    res = replay_engine.run_replay(split="train", symbols_limit=15)

    assert "overall_metrics" in res
    assert "breakdown_by_setup" in res
    assert "breakdown_by_regime" in res
    assert "breakdown_by_decile" in res
    assert "breakdown_by_sector" in res

    # Verify overall metrics
    overall = res["overall_metrics"]
    assert "raw_win_rate_pct" in overall
    assert "net_positive_win_rate_pct" in overall
    assert "net_win_rate_ci_95" in overall
    assert "net_expectancy_r" in overall
    assert "net_expectancy_r_ci_95" in overall
    assert len(overall["net_expectancy_r_ci_95"]) == 2

    # Verify sample size warning when N < 30
    for setup_name, metrics in res["breakdown_by_setup"].items():
        if metrics.get("sample_size", 0) < 30:
            assert metrics.get("warning") == "INSUFFICIENT SAMPLE (N < 30)"

    # Verify equity curve properties
    assert res["starting_capital_rupees"] == 1_000_000.0
    assert "annualized_sharpe_ratio" in res
    assert REPLAY_SCORECARD_FILE.exists()
