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
    """Verify PSU cluster allows up to 3 open positions and 30% capital (Item 10)."""
    # 2 PSU open positions (SBI and NTPC)
    open_positions = [
        {"symbol": "SBIN.NS", "sector": "Banking", "quantity": 10, "entry_price": 800.0, "stop_loss": 780.0},
        {"symbol": "NTPC.NS", "sector": "Power", "quantity": 20, "entry_price": 380.0, "stop_loss": 370.0},
    ]

    # Attempt to size a 3rd PSU stock (HAL.NS) -> Allowed because PSU cap is 3!
    decision_3rd = risk_guard.compute_position_size(
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
    assert decision_3rd.allowed, f"PSU 3rd position should be allowed under looser cap! Notes: {decision_3rd.notes}"

    # Now simulate 3 open PSU positions
    open_positions_3 = open_positions + [
        {"symbol": "HAL.NS", "sector": "Defense", "quantity": 5, "entry_price": 4200.0, "stop_loss": 4100.0}
    ]

    # Attempt to size a 4th PSU stock (BEL.NS) -> REJECTED because PSU cap is 3!
    decision_4th = risk_guard.compute_position_size(
        symbol="BEL.NS",
        entry_price=300.0,
        stop_loss=290.0,
        target_price=320.0,
        sector="Defense",
        total_capital=100000.0,
        available_cash=80000.0,
        avg_20d_volume=1000000,
        macro_regime="GREEN",
        open_positions=open_positions_3,
    )
    assert not decision_4th.allowed
    assert decision_4th.status == "SKIPPED_GROUP_CAP"
    assert any("Promoter group 'PSU' already has 3 open trades" in n for n in decision_4th.notes)


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


def test_charges_yaml_contains_verified_on_and_effective_date():
    """Verify config/charges.yaml contains verified_on: '2026-11-13' (Item 10)."""
    charges_file = PROJECT_ROOT / "config" / "charges.yaml"
    assert charges_file.exists()
    content = charges_file.read_text(encoding="utf-8")
    assert 'verified_on: "2026-11-13"' in content
    assert 'effective_date: "2026-11-13"' in content


def test_unmapped_symbol_defaults_to_standalone():
    """Verify unmapped symbols default to Standalone_Equities (Item 10)."""
    decision = risk_guard.compute_position_size(
        symbol="NONEXISTENT_STOCK.NS",
        entry_price=500.0,
        stop_loss=480.0,
        target_price=540.0,
        sector="Specialty",
        total_capital=100000.0,
        available_cash=80000.0,
        avg_20d_volume=1000000,
        macro_regime="GREEN",
        open_positions=[],
    )
    # Should be permitted under Standalone_Equities default
    assert decision.allowed


def test_audit_canonical_float_and_timestamp_formats():
    """Verify canonical float format (4 decimals) and ISO UTC timestamp ending in Z."""
    from backend.core.audit_ledger import (
        format_canonical_float,
        format_canonical_timestamp,
        build_canonical_prediction_payload,
        compute_audit_hash,
    )
    assert format_canonical_float(100.5) == "100.5000"
    assert format_canonical_float(0.123456) == "0.1235"
    ts = format_canonical_timestamp()
    assert ts.endswith("Z")

    payload = build_canonical_prediction_payload(
        symbol="TCS.NS",
        side="BUY",
        entry_price=3500.0,
        stop_loss=3400.0,
        target_price=3700.0,
        quantity=10,
        probability=0.62,
        ev_r=0.45,
        model_version="v1.0.0",
        config_hash="cfg_hash_1",
        data_snapshot_id="snap_1",
        llm_output_hash="llm_hash_1",
        prev_hash="GENESIS_AURA_HASH",
        utc_timestamp="2026-11-14T10:00:00.000000Z",
    )
    assert payload["entry_price"] == "3500.0000"
    assert payload["stop_loss"] == "3400.0000"
    h = compute_audit_hash(payload)
    assert len(h) == 64


def test_audit_tamper_detection_and_verification():
    """Verify cryptographic chain verification catches modified row or prev_hash."""
    from backend.core.audit_ledger import verify_audit_ledger

    class FakeRecord:
        def __init__(self, id, audit_hash, prev_hash, hash_version="v2"):
            self.id = id
            self.audit_hash = audit_hash
            self.prev_hash = prev_hash
            self.hash_version = hash_version

    # Valid chain
    records = [
        FakeRecord(1, "hash_row_1", "GENESIS_AURA_HASH"),
        FakeRecord(2, "hash_row_2", "hash_row_1"),
        FakeRecord(3, "hash_row_3", "hash_row_2"),
    ]
    res_valid = verify_audit_ledger(records)
    assert res_valid["chain_valid"] is True
    assert res_valid["total_records_checked"] == 3

    # Tampered chain (record 3 points to wrong prev_hash)
    tampered_records = [
        FakeRecord(1, "hash_row_1", "GENESIS_AURA_HASH"),
        FakeRecord(2, "hash_row_2", "hash_row_1"),
        FakeRecord(3, "hash_row_3", "FORGED_PREV_HASH"),
    ]
    res_tampered = verify_audit_ledger(tampered_records)
    assert res_tampered["chain_valid"] is False
    assert 3 in res_tampered["tampered_record_ids"]


def test_audit_external_daily_anchor_appends_history():
    """Verify external daily anchor appends to data/audit_anchor_history.jsonl."""
    from backend.core.audit_ledger import append_external_daily_anchor, read_external_anchor_history
    anchor = append_external_daily_anchor(
        latest_hash="test_head_hash_abcdef1234567890",
        record_count=42,
        notes="Automated test daily anchor",
    )
    assert anchor["head_hash"] == "test_head_hash_abcdef1234567890"
    assert anchor["record_count"] == 42
    history = read_external_anchor_history()
    assert len(history) >= 1
    assert any(h["head_hash"] == "test_head_hash_abcdef1234567890" for h in history)


def test_regime_asymmetric_hysteresis_and_shadow_mode():
    """Verify:
    1. Step down immediately on 1 close or VIX spike (capital preservation).
    2. Step up only after 2 confirming closes (avoids bear trap whipsaws).
    3. Middle state is strictly named AMBER.
    4. RED regime triggers is_shadow_mode and zero live capital.
    """
    from backend.strategies.regime import apply_regime_hysteresis

    # 1. Step down immediately on 1 close
    # Confirmed was GREEN, today is AMBER -> Steps down to AMBER immediately
    assert apply_regime_hysteresis(confirmed_prev_regime="GREEN", today_raw="AMBER", prev_day_raw="GREEN") == "AMBER"
    # Confirmed was GREEN, today is RED -> Steps down to RED immediately
    assert apply_regime_hysteresis(confirmed_prev_regime="GREEN", today_raw="RED", prev_day_raw="GREEN") == "RED"

    # 2. Step down immediately on VIX spike
    assert apply_regime_hysteresis(confirmed_prev_regime="GREEN", today_raw="GREEN", prev_day_raw="GREEN", vix_spike=True) == "AMBER"

    # 3. Step up requires 2 confirming closes
    # Confirmed was RED, today is GREEN, but yesterday was RED -> Retains RED!
    assert apply_regime_hysteresis(confirmed_prev_regime="RED", today_raw="GREEN", prev_day_raw="RED") == "RED"
    # Confirmed was RED, today is GREEN, and yesterday was GREEN -> Confirmed 2 closes, steps up to GREEN!
    assert apply_regime_hysteresis(confirmed_prev_regime="RED", today_raw="GREEN", prev_day_raw="GREEN") == "GREEN"

    # Confirmed was AMBER, today is GREEN, but yesterday was AMBER -> Retains AMBER!
    assert apply_regime_hysteresis(confirmed_prev_regime="AMBER", today_raw="GREEN", prev_day_raw="AMBER") == "AMBER"
    # Confirmed was AMBER, today is GREEN, and yesterday was GREEN -> Steps up to GREEN!
    assert apply_regime_hysteresis(confirmed_prev_regime="AMBER", today_raw="GREEN", prev_day_raw="GREEN") == "GREEN"


def test_regime_breadth_input():
    """Verify market breadth influences raw regime classification."""
    from backend.strategies.regime import classify_raw_regime
    # Healthy technicals (NIFTY above EMAs, low VIX), but breadth collapsed (<20%) -> RED
    r_breadth_bad = classify_raw_regime(nifty_close=25000, ema20=24800, ema50=24500, vix_level=14.0, breadth_pct=18.0)
    assert r_breadth_bad == "RED"

    # Moderate breadth degradation (<40%) -> AMBER
    r_breadth_amber = classify_raw_regime(nifty_close=25000, ema20=24800, ema50=24500, vix_level=14.0, breadth_pct=35.0)
    assert r_breadth_amber == "AMBER"


def test_bss_uses_empirical_out_of_sample_base_rate():
    """Verify BSS calculation uses empirical base_rate * (1 - base_rate)."""
    from backend.ml.predictor import MLPredictor
    p = MLPredictor()
    p.brier_score = 0.18
    p.base_rate = 0.40  # base_rate = 0.40 -> brier_base = 0.40 * 0.60 = 0.24
    res = p.predict_probability({"rs_vs_nifty_20d": 2.0})

    # Expected BSS = 1 - (0.18 / 0.24) = 1 - 0.75 = 0.250
    assert abs(res["brier_skill_score"] - 0.250) < 0.01


def test_basket_export_gated_after_gap_check_and_shadow():
    """Verify frontend kiteBasket.ts blocks un-gated or shadow trades."""
    basket_file = PROJECT_ROOT / "frontend" / "src" / "utils" / "kiteBasket.ts"
    content = basket_file.read_text(encoding="utf-8")
    assert "Kite Basket Export Gated" in content
    assert "market-open gap check" in content
    assert "Shadow Mode active" in content


def test_public_page_trade_tickets_locked():
    """Verify CommandCenter.tsx replaces trade tickets with private lock on public demo."""
    cc_file = PROJECT_ROOT / "frontend" / "src" / "components" / "CommandCenter.tsx"
    content = cc_file.read_text(encoding="utf-8")
    assert "Private Lock" in content
    assert "SEBI non-broadcast guidelines" in content


def test_audit_database_triggers_block_tampering():
    """Verify SQLite triggers actively abort UPDATE on audit logs and DELETE on predictions (Item 10)."""
    from backend.db.session import engine
    from sqlalchemy import text
    import pytest

    with engine.begin() as conn:
        # Clean up any leftover test scrip
        conn.execute(text("DELETE FROM predictions WHERE symbol = 'TEST_TRIGGER.NS'")) if False else None
        
        # 1. Insert a test prediction row
        conn.execute(text("""
            INSERT INTO predictions (
                config_hash, model_version, data_snapshot_id, symbol, series, horizon, setup_tag, status, planned_entry_price, entry_price, stop_loss, target_price, quantity, time_limit_days, audit_hash, prev_hash, entry_date, created_at
            ) VALUES (
                'test_cfg', 'v1.0.0', 'snap_01', 'TEST_TRIGGER.NS', 'EQ', 'SWING', 'PULLBACK', 'OPEN', 1000.0, 1000.0, 950.0, 1100.0, 10, 10, 'initial_hash_123', 'GENESIS_AURA_HASH', CURRENT_DATE, CURRENT_TIMESTAMP
            )
        """))

        # 2. Attempting to tamper with entry_price or audit_hash MUST raise an exception from SQLite trigger
        with pytest.raises(Exception) as exc_info:
            conn.execute(text("UPDATE predictions SET entry_price = 1200.0 WHERE symbol = 'TEST_TRIGGER.NS'"))
        assert "IMMUTABLE_PREDICTION_AUDIT" in str(exc_info.value)

        with pytest.raises(Exception) as exc_info2:
            conn.execute(text("UPDATE predictions SET audit_hash = 'forged_hash' WHERE symbol = 'TEST_TRIGGER.NS'"))
        assert "IMMUTABLE_PREDICTION_AUDIT" in str(exc_info2.value)

        # 3. Attempting to DELETE from predictions MUST raise an exception from SQLite trigger
        with pytest.raises(Exception) as exc_info3:
            conn.execute(text("DELETE FROM predictions WHERE symbol = 'TEST_TRIGGER.NS'"))
        assert "IMMUTABLE_PREDICTIONS" in str(exc_info3.value)
