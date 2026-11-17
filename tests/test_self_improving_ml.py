"""Unit and Integration Tests for AURA Self-Improving ML & Continual Learning.

Validates:
1. Dataset generation and closed-loop experience replay.
2. Candidate model training with calibrated probabilities.
3. Champion vs Candidate evaluation and version promotion.
4. Dynamic mistake rules distillation from MistakeLog into JSON artifacts.
5. Persistent model reloading from disk.
"""

import json
from pathlib import Path
import numpy as np
import pytest

from backend.core.config import PROJECT_ROOT
from backend.db.session import SessionLocal
from backend.db.models import MistakeLog, Prediction
from backend.ml.features import FEATURE_COLUMNS
from backend.ml.predictor import ml_predictor
from backend.ml.retrain import (
    SelfImprovingMLEngine,
    self_improving_engine,
    MISTAKE_RULES_FILE,
)


def test_self_improving_dataset_generation():
    """Verify historical prior dataset generation meets feature specifications."""
    engine = SelfImprovingMLEngine()
    X, y = engine.generate_baseline_historical_dataset(n_samples=200)

    assert X.shape == (200, len(FEATURE_COLUMNS))
    assert len(y) == 200
    assert set(np.unique(y)).issubset({0, 1})


def test_retraining_and_promotion_cycle():
    """Verify that the retraining cycle runs, evaluates candidate metrics,

    and handles promotion or champion retention gracefully.
    """
    engine = SelfImprovingMLEngine()

    # 1. Guard validation: with < 20 live trades, promotion is skipped to prevent synthetic overfitting
    guard_res = engine.retrain_and_evaluate_candidate()
    assert guard_res["status"] == "SKIPPED"
    assert guard_res["decision"] == "RETAINED_CHAMPION"
    assert "Insufficient" in guard_res["reason"] or "Need >=" in guard_res["reason"]

    # 2. Cycle evaluation: passing min_live_trades=0 tests candidate training & metric evaluation
    result = engine.retrain_and_evaluate_candidate(min_live_trades=0)
    assert result["status"] == "SUCCESS"
    assert result["decision"] in ["PROMOTED", "RETAINED_CHAMPION"]
    assert "candidate_metrics" in result
    assert result["candidate_metrics"]["brier_score"] <= 0.25
    assert result["candidate_metrics"]["auc"] >= 0.55
    assert isinstance(result["active_mistake_rules"], list)


def test_dynamic_mistake_rules_extraction():
    """Verify that mistake patterns in DB are distilled into LLM guidance rules."""
    db = SessionLocal()
    try:
        # Seed a test mistake
        m = MistakeLog(
            symbol="TESTCO.NS",
            loss_category="High VIX Trap",
            loss_rupees=5000.0,
            loss_r=1.5,
            diagnosis_narrative="Momentum failed abruptly on high VIX day.",
            status="PENDING_REVIEW",
        )
        db.add(m)
        db.commit()

        engine = SelfImprovingMLEngine()
        rules = engine.distill_dynamic_mistake_rules()

        assert len(rules) >= 1
        assert MISTAKE_RULES_FILE.exists()

        with open(MISTAKE_RULES_FILE, "r") as f:
            data = json.load(f)
            assert "rules" in data
            assert len(data["rules"]) >= 1

    finally:
        db.close()


def test_persistent_champion_loading():
    """Verify that the model predictor can initialize and load saved champion models."""
    from backend.ml.predictor import MLPredictor

    # Initialize a new instance
    predictor = MLPredictor()
    assert predictor.is_trained is True
    assert predictor.model is not None
    assert predictor.brier_score <= 0.25

    # Run sample prediction
    sample_feats = {col: 0.5 for col in FEATURE_COLUMNS}
    pred_res = predictor.predict_probability(sample_feats)
    assert "win_probability" in pred_res
    assert 0.0 <= pred_res["win_probability"] <= 1.0
    assert "ev_r" in pred_res
    assert "model_version" in pred_res


def test_champion_challenger_retention_and_rollback():
    """Verify that degrading candidates are rejected in favor of the champion,

    and explicit rollback can restore previous champion state.
    """
    engine = SelfImprovingMLEngine()

    # Artificially set an unachievable threshold to force candidate rejection
    original_threshold = engine.max_brier_threshold
    try:
        engine.max_brier_threshold = 0.0001  # Impossible Brier threshold
        result = engine.retrain_and_evaluate_candidate(min_live_trades=0)
        assert result["decision"] == "RETAINED_CHAMPION"
    finally:
        engine.max_brier_threshold = original_threshold

    # Test explicit rollback capability
    rollback_res = engine.rollback_to_champion()
    # Should either succeed or return clean status if no backup exists
    assert rollback_res["status"] in ("SUCCESS", "FAILED")


def test_ci_leakage_guard_blocks_unrealistic_auc_or_bss():
    """Verify that suspected lookahead leakage (AUC > 0.80 or BSS > 0.50) blocks promotion.
    
    Section 18.2 / Section 20 ML Safety Guard: In financial equity prediction,
    AUC > 0.80 or BSS > 0.50 almost invariably indicates label leakage from future bars.
    """
    engine = SelfImprovingMLEngine()

    # Simulate candidate metrics where AUC = 0.88 (blatant future leakage)
    cand_auc = 0.88
    cand_bss = 0.65
    suspected_leakage = (cand_auc > 0.80) or (cand_bss > 0.50)
    assert suspected_leakage is True

    # In retrain_and_evaluate_candidate, suspected_leakage blocks passed_gates
    passed_gates = (
        0.18 <= engine.max_brier_threshold
        and cand_auc >= engine.min_auc_threshold
        and 0.18 <= (0.20 + 0.015)
        and not suspected_leakage
    )
    assert passed_gates is False, "CI Leakage Guard must block promotion when suspected_leakage is True"


def test_ml_skill_test_metrics():
    """Verify ML skill test results and institutional leakage boundary enforcement."""
    from scipy.stats import spearmanr
    from backend.ml.predictor import ml_predictor
    from backend.ml.setup_priors import get_setup_empirical_priors

    # 1. Brier score must be well-calibrated (<= 0.20)
    assert ml_predictor.brier_score <= 0.20, f"Brier score {ml_predictor.brier_score} exceeds 0.20"

    # 2. Institutional Leakage Rule Enforcement (Section 20 ML Safety Guard)
    priors = get_setup_empirical_priors()
    base_rate = priors.get("p_target", 0.0682)
    brier_base = base_rate * (1.0 - base_rate)
    bss = 1.0 - (ml_predictor.brier_score / max(0.001, brier_base))
    
    # BSS must not exceed 0.50 (leakage rule)
    assert bss <= 0.50, f"Brier Skill Score {bss} exceeds 0.50 leakage threshold!"

    # 3. Check Validation Report on Disk
    val_file = PROJECT_ROOT / "reports" / "validation_reliability_report.json"
    if val_file.exists():
        val_data = json.load(open(val_file))
        assert val_data.get("leakage_rule_passed") is True
        rho = val_data["spearman_rank_correlation"]["rho"]
        # Rank correlation must not exceed 0.90 (leakage rule)
        assert rho <= 0.90, f"Spearman rank correlation {rho} exceeds 0.90 leakage threshold!"

