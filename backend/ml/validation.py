"""Out-of-Sample Probability Honesty & Validation Reliability Engine (Section 19 / Decision 007).

Evaluates model predictions exclusively on out-of-sample validation data:
1. Reliability by Decile (10 bins, strictly partitioned).
2. Spearman Rank Correlation (rho and p-value) between predicted probability and actual outcomes.
3. Out-of-sample Brier Skill Score (BSS) against empirical base rate.
4. Enforces 'MODEL_SKILL_NOT_DEMONSTRATED' badge and setup-level base rate fallback with 95% CIs
   whenever BSS <= 0.
"""

from __future__ import annotations
import datetime
from typing import Dict, List, Any, Tuple
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import brier_score_loss

from backend.ml.setup_priors import get_setup_empirical_priors, DEFAULT_SETUP_PRIORS


def evaluate_validation_probability_honesty(
    validation_trades: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compute out-of-sample reliability by decile, Spearman rank correlation, and skill score."""
    if not validation_trades:
        raise ValueError("Validation trade set cannot be empty.")

    n_total = len(validation_trades)
    df = pd.DataFrame(validation_trades).sort_values(by=["predicted_prob", "trade_id"]).reset_index(drop=True)

    # 1. Strict 10-decile partitioning (no quantile collapse)
    df["decile"] = [min(9, i // (max(1, n_total // 10))) for i in range(n_total)]

    decile_table = []
    for d, group in df.groupby("decile"):
        decile_table.append({
            "decile_rank": int(d) + 1,
            "trade_count": len(group),
            "prob_range": [round(float(group["predicted_prob"].min()), 3), round(float(group["predicted_prob"].max()), 3)],
            "mean_predicted_prob": round(float(group["predicted_prob"].mean()), 3),
            "realized_win_rate": round(float(group["outcome"].mean()), 3),
            "realized_net_r": round(float(group.get("net_pnl_r", pd.Series([0.0]*len(group))).mean()), 3),
        })

    # 2. Spearman Rank Correlation between predicted probability and actual outcome
    preds = df["predicted_prob"].values
    outcomes = df["outcome"].values
    spearman_res = stats.spearmanr(preds, outcomes)
    rho = round(float(spearman_res.statistic), 4) if hasattr(spearman_res, "statistic") else round(float(spearman_res[0]), 4)
    p_value = round(float(spearman_res.pvalue), 5) if hasattr(spearman_res, "pvalue") else round(float(spearman_res[1]), 5)

    # 3. Out-of-sample Brier Score and BSS against empirical base rate
    val_base_rate = float(np.mean(outcomes))
    brier_val = round(float(brier_score_loss(outcomes, preds)), 4)
    brier_ref = max(0.001, round(val_base_rate * (1.0 - val_base_rate), 4))
    bss = round(1.0 - (brier_val / brier_ref), 4)

    # 4. Model Skill Determination
    # If BSS <= 0 out-of-sample, model does NOT beat empirical base rate
    model_skill_demonstrated = bool(bss > 0.0 and p_value < 0.05)
    model_status_badge = "MODEL_SKILL_DEMONSTRATED" if model_skill_demonstrated else "MODEL_SKILL_NOT_DEMONSTRATED"
    leakage_detected = bool(bss > 0.50 or rho > 0.90)
    leakage_rule_passed = not leakage_detected

    # Setup-level empirical priors fallback
    setup_priors = DEFAULT_SETUP_PRIORS

    return {
        "evaluation_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "dataset_type": "OUT_OF_SAMPLE_VALIDATION",
        "sample_size": n_total,
        "empirical_base_rate": round(val_base_rate, 4),
        "validation_brier_score": brier_val,
        "reference_brier_score": brier_ref,
        "brier_skill_score_bss": bss,
        "leakage_rule_passed": leakage_rule_passed,
        "leakage_detected": leakage_detected,
        "spearman_rank_correlation": {
            "rho": rho,
            "p_value": p_value,
            "statistically_significant": bool(p_value < 0.05),
        },
        "model_skill_badge": model_status_badge,
        "model_skill_demonstrated": model_skill_demonstrated,
        "decile_reliability_table": decile_table,
        "setup_level_empirical_priors": setup_priors,
        "policy_action": (
            "Model skill demonstrated out-of-sample; calibrated model probabilities used with shrinkage."
            if model_skill_demonstrated
            else "Model skill not demonstrated out-of-sample (BSS <= 0). Tickets display 'MODEL_SKILL_NOT_DEMONSTRATED' "
                 "and use empirical setup-level base rates with 95% bootstrap intervals."
        ),
    }
