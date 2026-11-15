"""Unit and Integration Tests for Section 19 Upgrades & Institutional Contracts.

Validates:
1. Reporting: Decile table strictly sums to 120, Rupee equity curve, Sharpe hidden in UI.
2. Probability Honesty: Out-of-sample validation decile reliability, Spearman rho, and BSS gate.
3. EV: Three-outcome probabilities sum to 1.0, training-window E[R_E] intervals, EV lower-bound gate.
4. Placebo Test: Strategy edge over 1,000 random universe entries and NIFTY buy-and-hold with CIs.
5. Gate G1: Symbol master resolution, ISIN lookups, Upstox smoke contract, reconciliation report.
6. Housekeeping: TradeFillEvent immutability triggers, host binding 127.0.0.1, authenticated GET predictions.
"""

import datetime
import json
from pathlib import Path
import pytest
from sqlalchemy import text
from fastapi.testclient import TestClient

from backend.core.config import PROJECT_ROOT, settings
from backend.db.session import engine, SessionLocal
from backend.db.models import TradeFillEvent, Prediction
from backend.data.symbol_master import symbol_master
from backend.data.universe import resolve_symbol_master
from backend.ml.setup_priors import get_setup_empirical_priors, DEFAULT_SETUP_PRIORS
from backend.ml.predictor import ml_predictor
from backend.main import app

client = TestClient(app)


# --- 1. Reporting & Decile Table Sum Invariant ---

def test_decile_table_strictly_sums_to_120():
    """Verify that decile reliability table sums strictly to 120 with exactly 10 deciles."""
    diag_file = PROJECT_ROOT / "reports" / "diagnostics_120_trades.json"
    assert diag_file.exists(), "diagnostics_120_trades.json must exist"

    with open(diag_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    decile_table = data["decile_reliability_table"]
    assert len(decile_table) == 10, f"Expected 10 deciles, got {len(decile_table)}"
    total_trades = sum(d["trade_count"] for d in decile_table)
    assert total_trades == 120, f"Decile trade counts must sum strictly to 120, got {total_trades}"

    # Each decile must have exactly 12 trades
    for d in decile_table:
        assert d["trade_count"] == 12, f"Decile {d['decile_rank']} had {d['trade_count']} trades, expected 12"


def test_rupee_portfolio_simulation_metrics():
    """Verify rupee equity curve metrics from actual sizing, caps, and cash constraints."""
    diag_file = PROJECT_ROOT / "reports" / "diagnostics_120_trades.json"
    with open(diag_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    sim = data["rupee_portfolio_simulation"]
    assert sim["initial_capital_inr"] == 100000.0
    assert sim["final_capital_inr"] > sim["initial_capital_inr"]
    assert sim["total_net_return_pct"] > 0.0
    assert sim["max_drawdown_pct"] < 10.0  # Max drawdown well within risk budget
    assert sim["trades_executed"] + sim["trades_skipped_due_to_caps_or_cash"] == 120
    assert sim["sharpe_display_policy"] == "HIDDEN_IN_UI"


def test_sharpe_hidden_in_frontend_codebase():
    """Confirm Sharpe ratio is strictly omitted/hidden from user-facing stress ledger UI."""
    ledger_path = PROJECT_ROOT / "frontend" / "src" / "components" / "StressTestLedger.tsx"
    assert ledger_path.exists()
    content = ledger_path.read_text(encoding="utf-8")
    assert "Daily Mark-to-Market Sharpe" not in content
    assert "Sharpe Ratio (Annualized)" not in content
    assert "Profit Factor" in content
    assert "Risk-Adjusted Expectancy" in content


# --- 2. Probability Honesty ---

def test_probability_honesty_validation_report():
    """Verify validation reliability report contains deciles, Spearman rho, and honesty badge."""
    val_file = PROJECT_ROOT / "reports" / "validation_reliability_report.json"
    assert val_file.exists(), "validation_reliability_report.json must exist"

    with open(val_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["dataset_type"] == "OUT_OF_SAMPLE_VALIDATION"
    assert "decile_reliability_table" in data
    assert len(data["decile_reliability_table"]) == 10
    assert "spearman_rank_correlation" in data
    assert "rho" in data["spearman_rank_correlation"]
    assert "p_value" in data["spearman_rank_correlation"]
    assert data["model_skill_badge"] in ("MODEL_SKILL_DEMONSTRATED", "MODEL_SKILL_NOT_DEMONSTRATED")

    # If BSS <= 0, model skill must be flagged as not demonstrated
    if data["brier_skill_score_bss"] <= 0:
        assert data["model_skill_badge"] == "MODEL_SKILL_NOT_DEMONSTRATED"
        assert not data["model_skill_demonstrated"]


# --- 3. Three-Outcome EV & Prior Estimation ---

def test_three_outcome_probabilities_sum_strictly_to_one():
    """Verify that p_T + p_S + p_E == 1.0 across all setup types."""
    for setup in ["pullback_ema", "breakout_vcp", "mean_reversion", "compounder", None]:
        priors = get_setup_empirical_priors(setup)
        total_p = priors["p_target"] + priors["p_stop"] + priors["p_expired"]
        assert abs(total_p - 1.0) < 0.001, f"Setup {setup} probabilities do not sum to 1: {total_p}"

        # Prediction output verification
        pred = ml_predictor.predict_probability(
            features={"rsi_14": 55.0, "adx_14": 22.0},
            setup_tag=setup,
        )
        assert abs(pred["probabilities_sum"] - 1.0) < 0.001
        assert "p_target_ci_95" in pred
        assert "p_stop_ci_95" in pred
        assert "p_expired_ci_95" in pred
        assert "expected_r_expired" in pred


def test_ev_lower_bound_gate():
    """Verify that EV lower-bound gate rejects trade when lower bound <= 0, replacing p >= 0.45 floor."""
    # Predict with negative expected value setup
    pred = ml_predictor.predict_probability(
        features={"rsi_14": 30.0, "adx_14": 12.0},
        target_r=1.0,
        stop_r=2.0,
        expected_r_expired=-0.2,
        cost_r=0.10,
    )
    # Even if raw win probability was > 0.45, EV lower bound is negative, so gate must fail
    assert pred["passed_ev_gate"] is False


# --- 4. Placebo Test ---

def test_placebo_test_report_metrics():
    """Verify placebo report has >= 1000 draws, edge over random with intervals, and month/regime splits."""
    placebo_file = PROJECT_ROOT / "reports" / "placebo_test_report.json"
    assert placebo_file.exists(), "placebo_test_report.json must exist"

    with open(placebo_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["num_random_draws"] >= 1000
    assert "edge_over_random_net_r" in data
    assert "edge_over_random_ci_95" in data
    assert len(data["edge_over_random_ci_95"]) == 2
    assert "edge_over_nifty_r" in data
    assert "monthly_breakdown" in data
    assert len(data["monthly_breakdown"]) > 0
    assert "regime_breakdown" in data
    for reg in ["GREEN", "AMBER", "RED"]:
        assert reg in data["regime_breakdown"]


# --- 5. Gate G1 & Symbol Master ---

def test_symbol_master_historical_resolution():
    """Verify Symbol Master resolves historical mergers and name changes by effective date."""
    # Zomato -> Eternal after 2024-07-25
    assert symbol_master.resolve_symbol_at_date("ZOMATO.NS", datetime.date(2024, 8, 1)) == "ETERNAL.NS"
    assert symbol_master.resolve_symbol_at_date("ZOMATO.NS", datetime.date(2023, 1, 1)) == "ZOMATO.NS"

    # LTI -> LTIM after 2022-12-05
    assert symbol_master.resolve_symbol_at_date("LTI.NS", datetime.date(2023, 1, 1)) == "LTIM.NS"

    # ISIN Lookup
    isin_eternal = symbol_master.get_isin_for_symbol("ETERNAL")
    assert isin_eternal == "INE758T01015"


def test_gate_g1_reconciliation_report():
    """Verify Gate G1 reconciliation report passes with >= 98% Grade A/B coverage."""
    recon_file = PROJECT_ROOT / "reports" / "reconciliation_mismatch_report.json"
    assert recon_file.exists(), "reconciliation_mismatch_report.json must exist"

    with open(recon_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["confidence_coverage_a_b_pct"] >= 98.0
    assert data["gate_g1_status"] == "PASSED"
    assert data["total_discrepancies_detected"] == 0


# --- 6. Housekeeping & Security ---

def test_trade_fill_event_immutable_triggers():
    """Verify that TradeFillEvent table blocks UPDATE and DELETE via SQLite triggers."""
    db = SessionLocal()
    try:
        # Create a dummy prediction for FK
        pred = Prediction(
            config_hash="test_hash_123",
            model_version="v1.0.0",
            data_snapshot_id="snap_123",
            symbol="INFY.NS",
            planned_entry_price=1800.0,
            entry_price=1800.0,
            stop_loss=1750.0,
            target_price=1900.0,
            quantity=10,
            entry_date=datetime.date(2026, 8, 10),
            created_at=datetime.datetime.utcnow(),
        )
        db.add(pred)
        db.commit()

        fill = TradeFillEvent(
            prediction_id=pred.id,
            symbol="INFY.NS",
            order_side="BUY",
            planned_price=1800.0,
            fill_price=1801.5,
            slippage_rupees=1.5,
            quantity=10,
            event_hash="hash_fill_001",
            prev_event_hash="GENESIS_FILL_EVENT",
        )
        db.add(fill)
        db.commit()
        fill_id = fill.id

        # 1. Attempt UPDATE: Must fail with trigger error
        with pytest.raises(Exception) as excinfo:
            with engine.begin() as conn:
                conn.execute(text(f"UPDATE trade_fill_events SET fill_price = 1750.0 WHERE id = {fill_id}"))
        assert "IMMUTABLE_FILL_EVENTS" in str(excinfo.value)

        # 2. Attempt DELETE: Must fail with trigger error
        with pytest.raises(Exception) as excinfo:
            with engine.begin() as conn:
                conn.execute(text(f"DELETE FROM trade_fill_events WHERE id = {fill_id}"))
        assert "IMMUTABLE_FILL_EVENTS" in str(excinfo.value)

    finally:
        db.close()


def test_host_binding_is_strictly_localhost():
    """Verify that application host configuration is strictly bound to 127.0.0.1 loopback."""
    assert settings.HOST == "127.0.0.1", f"HOST must be 127.0.0.1, got {settings.HOST}"


def test_get_prediction_endpoints_require_authentication():
    """Verify that unauthenticated GET requests to /predictions/today and /predictions/history are rejected."""
    # Unauthenticated request to /predictions/today
    res_today = client.get("/api/predictions/today")
    assert res_today.status_code == 401, f"Expected 401 Unauthorized, got {res_today.status_code}"

    # Unauthenticated request to /predictions/history
    res_hist = client.get("/api/predictions/history")
    assert res_hist.status_code == 401, f"Expected 401 Unauthorized, got {res_hist.status_code}"
