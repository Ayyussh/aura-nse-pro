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
    result = engine.retrain_and_evaluate_candidate()

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
