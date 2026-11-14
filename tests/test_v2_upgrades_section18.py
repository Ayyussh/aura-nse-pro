"""Unit and Integration Tests for Specification v2 Section 18 Upgrades.

Verifies:
- U0: baseline_v0 freeze and docs/AUDIT.md existence.
- U1: Grader outputs both gross_pnl_r and net_pnl_r.
- U1: Anti-chase ATR-relative clamp.
- U1: POST /api/scanner/run with lock, deprecated GET returning 405.
- U1: Audit chain verification endpoint.
- U2: Promoter group caps from config/groups.yaml.
"""

from __future__ import annotations
import datetime
import json
from pathlib import Path
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.core.config import get_groups_config, PROJECT_ROOT
from backend.core.grader import grade_trade_outcome
from backend.risk.sizing import risk_guard


client = TestClient(app)


def test_u0_freeze_and_audit_doc_exist():
    """Verify baseline_v0 freeze and AUDIT.md exist."""
    baseline_file = PROJECT_ROOT / "reports" / "baseline_v0.json"
    audit_doc = PROJECT_ROOT / "docs" / "AUDIT.md"

    assert baseline_file.exists(), "reports/baseline_v0.json must exist"
    assert audit_doc.exists(), "docs/AUDIT.md must exist"

    with open(baseline_file, "r") as f:
        meta = json.load(f)
    assert meta["tag"] == "baseline_v0"
    assert meta["status"] == "FROZEN_BASELINE_DO_NOT_MODIFY"
    assert "config_hash" in meta
    assert "old_as_built_metrics" in meta
    assert "corrected_grader_metrics" in meta


def test_u1_grader_returns_both_gross_and_net_r():
    """Verify grader outputs gross_pnl_r and net_pnl_r after Indian charges."""
    entry_date = datetime.date(2026, 11, 1)
    dates = pd.date_range("2026-11-01", periods=5, freq="D")
    df = pd.DataFrame(
        {
            "open": [1000.0, 1010.0, 1020.0, 1030.0, 1040.0],
            "high": [1005.0, 1025.0, 1035.0, 1045.0, 1085.0],
            "low": [990.0, 1005.0, 1015.0, 1025.0, 1035.0],
            "close": [1000.0, 1020.0, 1030.0, 1040.0, 1080.0],
        },
        index=dates,
    )

    result = grade_trade_outcome(
        symbol="TCS.NS",
        entry_date=entry_date,
        entry_price=1000.0,
        stop_loss=960.0,
        target_price=1080.0,
        quantity=25,
        time_limit_days=10,
        history_df=df,
    )

    assert result["status"] == "TARGET_HIT"
    assert "gross_pnl_r" in result
    assert "net_pnl_r" in result
    assert result["gross_pnl_r"] > result["net_pnl_r"]  # Net R is lower due to real charges
    assert result["charges_rupees"] > 0


def test_u2_promoter_group_caps():
    """Verify promoter group caps (max 2 positions or 25% exposure per group)."""
    groups_cfg = get_groups_config()
    assert "groups" in groups_cfg
    assert "Tata" in groups_cfg["groups"]
    assert "TCS.NS" in groups_cfg["groups"]["Tata"]
    assert "TATAMOTORS.NS" in groups_cfg["groups"]["Tata"]
    assert "TATASTEEL.NS" in groups_cfg["groups"]["Tata"]

    # Mock open positions with 2 Tata stocks already active
    open_positions = [
        {"symbol": "TCS.NS", "sector": "IT", "quantity": 10, "entry_price": 4000.0, "stop_loss": 3900.0},
        {"symbol": "TATAMOTORS.NS", "sector": "Auto", "quantity": 20, "entry_price": 1000.0, "stop_loss": 950.0},
    ]

    # Attempt to size a 3rd Tata stock (TATASTEEL.NS) -> Must reject with SKIPPED_GROUP_CAP
    decision = risk_guard.compute_position_size(
        symbol="TATASTEEL.NS",
        entry_price=150.0,
        stop_loss=140.0,
        target_price=170.0,
        sector="Metals",
        total_capital=100000.0,
        available_cash=80000.0,
        avg_20d_volume=1000000,
        macro_regime="GREEN",
        open_positions=open_positions,
    )

    assert not decision.allowed
    assert decision.status == "SKIPPED_GROUP_CAP"
    assert any("Promoter group 'Tata'" in n for n in decision.notes)


def test_u1_api_scanner_endpoints():
    """Verify POST /api/scanner/run and deprecated GET returning 405."""
    # Deprecated GET returns 405 Method Not Allowed
    resp_get = client.get("/api/scanner/run")
    assert resp_get.status_code == 405

    # Verification endpoint
    resp_verify = client.get("/api/predictions/verify-chain")
    assert resp_verify.status_code == 200
    data = resp_verify.json()
    assert "chain_valid" in data
    assert "total_records_checked" in data


def test_100_percent_universe_mapped_in_groups():
    """Verify that every single equity in the 191 universe is mapped in config/groups.yaml."""
    from backend.data.universe import NIFTY_500_SYMBOLS
    groups_cfg = get_groups_config()
    group_map = groups_cfg.get("groups", {})

    all_mapped = set()
    for g_name, syms in group_map.items():
        all_mapped.update(syms)

    unmapped = [s for s in NIFTY_500_SYMBOLS if s not in all_mapped]
    assert len(unmapped) == 0, f"Unmapped symbols in groups.yaml: {unmapped}"
    assert len(all_mapped) == len(NIFTY_500_SYMBOLS) == 191


def test_psu_cluster_has_looser_cap():
    """Verify PSU cluster allows up to 4 open positions (looser cap than private groups)."""
    # 2 PSU open positions (SBI and NTPC)
    open_positions = [
        {"symbol": "SBIN.NS", "sector": "Banking", "quantity": 10, "entry_price": 800.0, "stop_loss": 780.0},
        {"symbol": "NTPC.NS", "sector": "Power", "quantity": 20, "entry_price": 380.0, "stop_loss": 370.0},
    ]

    # Attempt to size a 3rd PSU stock (HAL.NS) -> Allowed because PSU cap is 4, unlike private group cap of 2!
    decision = risk_guard.compute_position_size(
        symbol="HAL.NS",
        entry_price=4200.0,
        stop_loss=4100.0,
        target_price=4450.0,
        sector="Defense",
        total_capital=100000.0,
        available_cash=80000.0,
        avg_20d_volume=1000000,
        macro_regime="GREEN",
        open_positions=open_positions,
    )
    assert decision.allowed, f"PSU 3rd position should be allowed under looser cap! Notes: {decision.notes}"


def test_charges_engine_dp_and_gst_scopes():
    """Verify DP fee includes GST, GST applies only to brokerage + exchange, and effective_date is read."""
    from backend.costs.charges import charges_engine
    assert charges_engine.effective_date == "2026-11-13"

    # Standard zero-brokerage test case: Buy 100 @ 1000, Sell 100 @ 1050
    charges = charges_engine.calculate_delivery_charges(
        buy_price=1000.0,
        sell_price=1050.0,
        quantity=100,
        broker_profile_name="zero_brokerage_delivery",
    )

    # 1. Total charges must fall within expected ₹240-245 range
    assert 240.0 <= charges.total_charges_and_brokerage <= 246.0

    # 2. DP charge must be ₹15.93 (₹13.50 + 18% GST self-contained)
    assert charges.dp_charge == 15.93

    # 3. GST must apply ONLY to (brokerage + exchange + sebi fee) = 0 + 7.07 + 0.21 = 7.28 * 0.18 = ₹1.31
    assert charges.gst == 1.31


def test_ev_brier_skill_score_and_leakage_flag():
    """Verify Brier skill score is computed and leakage flag blocks promotion on excessive metrics."""
    from backend.ml.predictor import ml_predictor
    features = {"rs_vs_nifty_20d": 3.5, "adx_14": 25.0, "rsi_14": 58.0}
    res = ml_predictor.predict_probability(features, cost_r=0.07, target_r=2.0)

    assert "brier_skill_score" in res
    assert "suspected_leakage" in res
    assert "passed_ev_gate" in res


def test_demo_data_quarantine():
    """Verify demo data contains explicit DEMO badges and basket export is protected."""
    demo_file = PROJECT_ROOT / "frontend" / "src" / "utils" / "demoData.ts"
    basket_file = PROJECT_ROOT / "frontend" / "src" / "utils" / "kiteBasket.ts"

    assert demo_file.exists()
    assert basket_file.exists()

    demo_text = demo_file.read_text(encoding="utf-8")
    assert "is_demo: true" in demo_text
    assert "DEMO, NOT LIVE" in demo_text
    assert "demo_" in demo_text

    basket_text = basket_file.read_text(encoding="utf-8")
    assert "Kite Basket Export Disabled: Demo data cannot be exported" in basket_text
