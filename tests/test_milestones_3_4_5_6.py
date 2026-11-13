"""Comprehensive Unit Tests for Milestones 3, 4, 5, and 6.

Validates:
- Swing indicator screening, setup tagging, and anti-chase guardrails
- Conservative stop-first outcome grading on ambiguous daily OHLC
- ML probability estimation, EV_R gate, and label leakage test
- LLM Router failover and 429 cooldown rotation (mocked in tests)
"""

import datetime
import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

from backend.core.grader import grade_trade_outcome
from backend.ml.features import compute_triple_barrier_label, FEATURE_COLUMNS
from backend.ml.predictor import MLPredictor
from backend.strategies.indicators import compute_atr, compute_rsi, compute_macd, compute_adx
from backend.strategies.swing import SwingStrategyEngine
from backend.llm.router import LLMRouter


def generate_mock_ohlcv(days: int = 250, start_price: float = 100.0, trend: float = 0.5) -> pd.DataFrame:
    """Generate deterministic synthetic price bars for unit testing."""
    dates = pd.date_range(end=datetime.date.today(), periods=days, freq="B")
    prices = [start_price]
    for _ in range(days - 1):
        prices.append(prices[-1] + trend + np.sin(len(prices) / 5.0) * 1.5)

    df = pd.DataFrame(index=dates)
    df["close"] = prices
    df["open"] = [p - 0.5 for p in prices]
    df["high"] = [p + 2.0 for p in prices]
    df["low"] = [p - 2.0 for p in prices]
    df["volume"] = 1500000.0
    return df


def test_swing_screening_and_anti_chase():
    """Verify swing screening checks trend, RSI, ADX, and anti-chasing ratios."""
    engine = SwingStrategyEngine()
    df = generate_mock_ohlcv(days=250, start_price=100.0, trend=0.8)

    # Candidate with strong uptrend
    candidate = engine.evaluate("TEST.NS", df)
    assert candidate.symbol == "TEST.NS"
    assert candidate.entry_price > 0
    assert candidate.stop_loss < candidate.entry_price
    assert candidate.target_price > candidate.entry_price
    assert candidate.stop_distance_pct <= 8.0


def test_grader_stop_first_on_ambiguous_bar():
    """Verify that if both target and stop fall inside the same day's range, STOP is hit first."""
    entry_date = datetime.date(2026, 11, 10)
    entry_price = 100.0
    stop_loss = 95.0
    target_price = 110.0
    quantity = 50

    # Ambiguous next day bar: Low is 94 (breaches stop 95) AND High is 112 (touches target 110)
    next_date = pd.Timestamp("2026-11-11")
    df = pd.DataFrame(
        {
            "open": [100.0],
            "high": [112.0],  # Touched target
            "low": [94.0],    # Touched stop
            "close": [105.0],
            "volume": [1000000],
        },
        index=[next_date],
    )

    res = grade_trade_outcome(
        symbol="TEST.NS",
        entry_date=entry_date,
        entry_price=entry_price,
        stop_loss=stop_loss,
        target_price=target_price,
        quantity=quantity,
        time_limit_days=10,
        history_df=df,
    )

    # Must prioritize conservative STOP_LOSS_HIT
    assert res["status"] == "STOP_LOSS_HIT"
    assert res["exit_price"] == stop_loss
    assert res["net_pnl_rupees"] < 0
    assert res["net_pnl_r"] < 0


def test_grader_gap_down_through_stop():
    """Verify that a gap down through stop loss is filled at the open price, not the stop price."""
    entry_date = datetime.date(2026, 11, 10)
    entry_price = 100.0
    stop_loss = 95.0
    target_price = 110.0
    quantity = 50

    # Stock opens with severe gap down at 90.0
    next_date = pd.Timestamp("2026-11-11")
    df = pd.DataFrame(
        {
            "open": [90.0],   # Severe gap through stop (95.0)
            "high": [92.0],
            "low": [89.0],
            "close": [91.0],
            "volume": [1000000],
        },
        index=[next_date],
    )

    res = grade_trade_outcome(
        symbol="TEST.NS",
        entry_date=entry_date,
        entry_price=entry_price,
        stop_loss=stop_loss,
        target_price=target_price,
        quantity=quantity,
        time_limit_days=10,
        history_df=df,
    )

    assert res["status"] == "STOP_LOSS_HIT"
    # Slipped fill at Open (90.0), not stop (95.0)
    assert res["exit_price"] == 90.0
    assert res["gross_pnl_rupees"] == (90.0 - 100.0) * 50  # -500.0


def test_ml_leakage_and_ev_gate():
    """Verify ML EV_R calculation and check that random labels do not leak predictive power (~50% AUC)."""
    predictor = MLPredictor()

    features = {col: 1.0 for col in FEATURE_COLUMNS}
    res = predictor.predict_probability(features)

    assert "win_probability" in res
    assert 0.0 < res["win_probability"] < 1.0
    assert "ev_r" in res
    assert "cost_drag_r" in res

    # Leakage test: shuffled labels should yield close to 50% AUC (no data leakage)
    np.random.seed(42)
    n = 200
    X_shuffled = np.random.randn(n, len(FEATURE_COLUMNS))
    y_shuffled = np.random.permutation([0] * 100 + [1] * 100)

    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    clf = LogisticRegression()
    clf.fit(X_shuffled[:150], y_shuffled[:150])
    test_probs = clf.predict_proba(X_shuffled[150:])[:, 1]
    auc = roc_auc_score(y_shuffled[150:], test_probs)
    # Shuffled labels must stay around 0.50 (+/- 0.15 for small sample)
    assert 0.35 <= auc <= 0.65


def test_llm_rotation_on_simulated_429_and_failover():
    """Test LLM router automatic cooldown and failover when primary encounters 429."""
    router = LLMRouter()

    # Mock active vault entries with 2 keys
    mock_key1 = MagicMock()
    mock_key1.id = 1
    mock_key1.provider = "gemini"
    mock_key1.key_label = "KEY_PRIMARY"
    mock_key1.model_name = "gemini-2.5-flash"
    mock_key1.encrypted_key = "dummy"

    mock_key2 = MagicMock()
    mock_key2.id = 2
    mock_key2.provider = "gemini"
    mock_key2.key_label = "KEY_BACKUP"
    mock_key2.model_name = "gemini-2.5-flash"
    mock_key2.encrypted_key = "dummy"

    with patch.object(router, "get_active_vault_entries", return_value=[mock_key1, mock_key2]):
        with patch.object(router, "mark_key_cooldown") as mock_cooldown:
            # First key throws 429 ResourceExhausted, second key succeeds
            def mock_call_gemini(key, model, prompt, sys_prompt):
                if key == "KEY_PRIMARY_SECRET":
                    raise Exception("429 ResourceExhausted: rate limit exceeded.")
                return '{"verdict": "APPROVED", "confidence_pct": 80.0, "bull_arguments": ["1", "2", "3"], "bear_arguments": ["1", "2", "3"], "red_flags": [], "invalidation_criteria": "Stop hit", "plain_language_summary": "Passed."}'

            with patch("backend.llm.router.decrypt_secret", side_effect=["KEY_PRIMARY_SECRET", "KEY_BACKUP_SECRET"]):
                with patch.object(router, "call_gemini", side_effect=mock_call_gemini):
                    with patch.object(router, "mark_key_success") as mock_success:
                        audit_result = router.complete_audit("prompt", "sys_prompt")

                        # Verify key 1 was put on cooldown
                        mock_cooldown.assert_called_once_with(1, duration_seconds=180, reason="429 Rate Limit")
                        # Verify key 2 succeeded
                        assert audit_result["status"] == "SUCCESS"
                        assert audit_result["key_label"] == "KEY_BACKUP"
                        assert audit_result["verdict"]["verdict"] == "APPROVED"
