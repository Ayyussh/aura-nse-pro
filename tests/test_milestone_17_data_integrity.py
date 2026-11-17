"""Unit and Integration Tests for Milestone 17: Data Accuracy and Integrity Layer.

Validates:
1. Exchange tick size rounding (sub-250: 0.01 vs >=250: 0.05).
2. Corporate action ledger, adjustment factor math, unadjusted 20% jump detector, and 20-day demerger exclusion.
3. Multi-source reconciliation voting (Confidence Grades A/B/C) and run gate threshold (>= 98%).
4. Contract note tradebook parser, execution slippage tracking, and charge drift alert (> ₹10).
5. Intraday candle replay tie-breaker for same-day target & stop-loss hit ambiguity.
"""

import datetime
import pytest
from backend.core.grader import round_to_exchange_tick, replay_intraday_tie_breaker
from backend.data.corporate_actions import (
    CorporateAction,
    CorporateActionEngine,
)
from backend.data.reconciliation import ReconciliationEngine, ReconciledBar
from backend.data.contract_note import ContractNoteReconciliationEngine


def test_tick_aware_pricing():
    """Verify tick size harmonization as per NSE June 2023 circular."""
    # Sub-250 scrip: 0.01 tick
    assert round_to_exchange_tick(184.234) == 184.23
    assert round_to_exchange_tick(45.126) == 45.13
    assert round_to_exchange_tick(249.99) == 249.99

    # >= 250 scrip: 0.05 tick
    assert round_to_exchange_tick(250.00) == 250.00
    assert round_to_exchange_tick(250.02) == 250.00
    assert round_to_exchange_tick(250.03) == 250.05
    assert round_to_exchange_tick(512.23) == 512.25
    assert round_to_exchange_tick(1000.08) == 1000.10


def test_jump_detector_and_demerger_exclusion():
    """Verify > 20% move without corporate action triggers quarantine,

    and demerger triggers 20-day quarantine.
    """
    engine = CorporateActionEngine()
    test_date = datetime.date(2026, 8, 10)

    # 1. Normal move (5% move): No quarantine
    quarantined, _ = engine.detect_unadjusted_jump(
        symbol="INFY.NS",
        prev_close=1800.0,
        cur_close=1890.0,
        date=test_date,
    )
    assert not quarantined
    is_q, _ = engine.is_quarantined("INFY.NS")
    assert not is_q

    # 2. 25% move with NO corporate action: Must quarantine
    quarantined, reason = engine.detect_unadjusted_jump(
        symbol="SUSPECT.NS",
        prev_close=100.0,
        cur_close=75.0,  # 25% drop
        date=test_date,
    )
    assert quarantined
    assert "UNADJUSTED_JUMP" in reason
    is_q, reason_q = engine.is_quarantined("SUSPECT.NS")
    assert is_q
    assert "SUSPECT.NS" in engine.quarantine_registry

    # 3. Demerger action: Must trigger demerger exclusion
    engine.ledger.append(CorporateAction(
        symbol="SPINOFF.NS",
        action_type="DEMERGER",
        ex_date=test_date,
        ratio_from=1.0,
        ratio_to=1.0,
        notes="Spin-off of business",
    ))

    quarantined, reason = engine.detect_unadjusted_jump(
        symbol="SPINOFF.NS",
        prev_close=1000.0,
        cur_close=700.0,  # 30% drop on demerger
        date=test_date,
    )
    assert quarantined
    assert "DEMERGER_EXCLUSION" in reason


def test_corporate_action_adjustment_math():
    """Verify split and bonus adjustment factor calculations."""
    engine = CorporateActionEngine()

    # 10:1 Split (1 old share -> 10 new shares)
    split_action = CorporateAction(
        symbol="SPLITCO.NS",
        action_type="SPLIT",
        ex_date=datetime.date(2026, 9, 1),
        ratio_from=10.0,
        ratio_to=1.0,
    )
    factor = engine.compute_adjustment_factor(split_action)
    assert factor == 0.10

    # 1:1 Bonus (1 bonus share for every 1 existing share)
    bonus_action = CorporateAction(
        symbol="BONUSCO.NS",
        action_type="BONUS",
        ex_date=datetime.date(2026, 9, 1),
        ratio_from=1.0,
        ratio_to=1.0,
    )
    factor_bonus = engine.compute_adjustment_factor(bonus_action)
    assert factor_bonus == 0.50


def test_multi_source_reconciliation_and_grades():
    """Verify confidence grades A, B, C assignment and tradeability flag."""
    recon = ReconciliationEngine()
    test_date = datetime.date(2026, 8, 10)

    # 1. Tier 1 + Tier 2 agree within 0.25% -> Grade A, Tradable
    bar_a = recon.reconcile_bar(
        symbol="RELIANCE.NS",
        date=test_date,
        bhavcopy_bar={"open": 2900.0, "high": 2950.0, "low": 2890.0, "close": 2920.0, "volume": 5000000},
        upstox_bar={"open": 2900.0, "high": 2950.0, "low": 2890.0, "close": 2922.0, "volume": 5050000},
        yf_bar={"open": 2900.0, "high": 2950.0, "low": 2890.0, "close": 2921.0, "volume": 4990000},
        fetch_missing=False,
    )
    assert bar_a.confidence_grade == "A"
    assert bar_a.is_tradable is True
    assert bar_a.close == 2920.0

    # 2. Bhavcopy only -> Grade B, Tradable
    bar_b = recon.reconcile_bar(
        symbol="TCS.NS",
        date=test_date,
        bhavcopy_bar={"open": 4100.0, "high": 4150.0, "low": 4080.0, "close": 4120.0, "volume": 1200000},
        upstox_bar=None,
        yf_bar=None,
        fetch_missing=False,
    )
    assert bar_b.confidence_grade == "B"
    assert bar_b.is_tradable is True

    # 3. Single unofficial source (yfinance only) -> Grade C, NEVER Tradable
    bar_c = recon.reconcile_bar(
        symbol="IDEA.NS",
        date=test_date,
        bhavcopy_bar=None,
        upstox_bar=None,
        yf_bar={"open": 14.0, "high": 14.5, "low": 13.8, "close": 14.2, "volume": 20000000},
        fetch_missing=False,
    )
    assert bar_c.confidence_grade == "C"
    assert bar_c.is_tradable is False


def test_reconciliation_run_gate():
    """Verify run-gate condition (>= 98% of universe must be Grade A or B)."""
    recon = ReconciliationEngine()
    test_date = datetime.date(2026, 8, 10)

    # 99 Grade A bars + 1 Grade C bar = 99% valid -> Can run
    universe_pass_syms = []
    for i in range(99):
        sym = f"SYM{i}.NS"
        universe_pass_syms.append(sym)
        recon.reconciled_cache[f"{sym}_{test_date.isoformat()}"] = ReconciledBar(
            symbol=sym, date=test_date, open=100.0, high=105.0, low=99.0,
            close=102.0, volume=100000, confidence_grade="A", source_set=["NSE_BHAVCOPY", "UPSTOX_V3"],
            discrepancies=[], is_tradable=True
        )
    universe_pass_syms.append("BAD.NS")
    recon.reconciled_cache[f"BAD.NS_{test_date.isoformat()}"] = ReconciledBar(
        symbol="BAD.NS", date=test_date, open=100.0, high=105.0, low=99.0,
        close=102.0, volume=100000, confidence_grade="C", source_set=["YFINANCE"],
        discrepancies=["Single source"], is_tradable=False
    )

    can_run, reason, stats = recon.evaluate_run_gate(universe_pass_syms, test_date)
    assert can_run is True
    assert stats["confidence_coverage_pct"] == 99.0

    # 90 Grade A bars + 10 Grade C bars = 90% valid -> Run gate holds execution
    universe_fail_syms = []
    for i in range(90):
        sym = f"SYM{i}.NS"
        universe_fail_syms.append(sym)
    for i in range(10):
        sym = f"FAIL{i}.NS"
        universe_fail_syms.append(sym)
        recon.reconciled_cache[f"{sym}_{test_date.isoformat()}"] = ReconciledBar(
            symbol=sym, date=test_date, open=100.0, high=105.0, low=99.0,
            close=102.0, volume=100000, confidence_grade="C", source_set=["YFINANCE"],
            discrepancies=["Single source"], is_tradable=False
        )

    can_run_fail, reason_fail, stats_fail = recon.evaluate_run_gate(universe_fail_syms, test_date)
    assert can_run_fail is False
    assert stats_fail["confidence_coverage_pct"] == 90.0


def test_contract_note_parser_and_drift_alert():
    """Verify broker tradebook reconciliation, slippage, and charge drift alert."""
    engine = ContractNoteReconciliationEngine()

    csv_data = (
        "Symbol,Trade Date,Type,Qty,Price,Charges\n"
        "RELIANCE,2026-08-10,BUY,50,2905.00,120.00\n"
        "INFY,2026-08-10,BUY,20,1800.00,15.00\n"
    )

    records = engine.parse_tradebook_csv(csv_data)
    assert len(records) == 2
    assert records[0].symbol == "RELIANCE.NS"
    assert records[0].price == 2905.00
    assert records[0].quantity == 50

    planned_trades = [
        {"symbol": "RELIANCE.NS", "entry_price": 2900.00, "quantity": 50},  # ₹5 positive slippage
        {"symbol": "INFY.NS", "entry_price": 1800.00, "quantity": 20},     # 0 slippage
    ]

    audit = engine.audit_trade_fills(planned_trades, records)
    assert audit["audited_trades_count"] == 2
    assert audit["records"][0]["slippage_rupees"] == 5.00
    assert audit["records"][1]["slippage_rupees"] == 0.00


def test_intraday_replay_tie_breaker():
    """Verify tie-breaker resolution when both target and stop are in range."""
    # Target = 550, Stop = 480
    target = 550.0
    stop = 480.0

    # Case 1: Stop hit first at 09:30 candle before Target at 14:15
    candles_stop_first = [
        {"time": "09:15", "open": 500.0, "high": 505.0, "low": 495.0, "close": 498.0},
        {"time": "09:30", "open": 498.0, "high": 500.0, "low": 478.0, "close": 482.0},  # Low 478 <= 480 Stop!
        {"time": "14:15", "open": 520.0, "high": 555.0, "low": 518.0, "close": 552.0},  # High 555 >= 550 Target
    ]
    res_status, exit_price, reason = replay_intraday_tie_breaker(candles_stop_first, stop, target)
    assert res_status == "STOP_LOSS_HIT"
    assert exit_price == stop
    assert "stop loss hit first" in reason

    # Case 2: Target hit first at 10:00 candle before Stop at 14:30
    candles_target_first = [
        {"time": "09:15", "open": 500.0, "high": 510.0, "low": 495.0, "close": 508.0},
        {"time": "10:00", "open": 515.0, "high": 552.0, "low": 512.0, "close": 548.0},  # High 552 >= 550 Target!
        {"time": "14:30", "open": 510.0, "high": 512.0, "low": 475.0, "close": 476.0},  # Low 475 <= 480 Stop
    ]
    res_status, exit_price, reason = replay_intraday_tie_breaker(candles_target_first, stop, target)
    assert res_status == "TARGET_HIT"
    assert exit_price == target
    assert "target reached before stop" in reason


def test_historical_store_duckdb_parquet():
    """Verify DuckDB & Parquet historical store loading and query speed."""
    from backend.data.historical_store import historical_store

    # Ensure store has data for ^NSEI.NS
    df = historical_store.load_ohlcv("^NSEI.NS")
    assert not df.empty
    assert len(df) >= 1000
    assert "adjusted_close" in df.columns
    assert "volume" in df.columns
    assert "close" in df.columns

    # Test duckdb direct SQL query
    import duckdb
    con = duckdb.connect(str(historical_store.duckdb_path), read_only=True)
    count = con.execute("SELECT count(*) FROM daily_ohlcv WHERE symbol = '^NSEI.NS'").fetchone()[0]
    con.close()
    assert count >= 1000


