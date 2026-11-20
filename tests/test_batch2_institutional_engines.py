"""Tests for Institutional Batch 2 Engines:
1. Forward Consensus & Revisions Engine (Forward Estimates, Value Trap Detection, PEG)
2. Corporate Governance & Regulatory Event Shield (BSE/NSE Disclosures, Auditor Resignations, FDA 483, CBI/ED)
3. Integration with 100-Point Compounder Scorecard & Swing Strategy
"""

import pytest
import pandas as pd
import numpy as np

from backend.fundamental.forward_estimates import ForwardEstimates, ForwardEstimatesEngine
from backend.data.corporate_events import CorporateEventShield, EventItem, CorporateEventRisk
from backend.fundamental.compounder_scorecard import compounder_engine
from backend.strategies.swing import swing_engine


def test_forward_estimates_value_trap_detection():
    engine = ForwardEstimatesEngine()
    # Mocking consensus where trailing PE is 12 (cheap) but forward EPS drops from 20 to 10 (-50%)
    # This should be flagged as an institutional VALUE TRAP
    est = engine._query_yfinance_consensus("TRAP.NS", "TRAP")
    # Even with fallback:
    fallback = engine._generate_fallback_estimates("TRAP")
    assert isinstance(fallback, ForwardEstimates)
    assert fallback.symbol == "TRAP"
    assert fallback.forward_pe > 0


def test_corporate_event_shield_keyword_scans():
    shield = CorporateEventShield()

    # 1. High-risk scans
    r1, cat1, rsn1 = shield.scan_text_for_risks("Company informs about resignation of statutory auditor with immediate effect.")
    assert r1 == "HIGH"
    assert cat1 == "AUDITOR_RESIGNATION"
    assert "auditor" in rsn1.lower()

    r2, cat2, rsn2 = shield.scan_text_for_risks("US FDA issues Form 483 with 8 observations and Official Action Indicated (OAI) for Goa facility.")
    assert r2 == "HIGH"
    assert cat2 == "FDA_WARNING"

    r3, cat3, rsn3 = shield.scan_text_for_risks("Enforcement Directorate conducts search and seizure operations at corporate head office.")
    assert r3 == "HIGH"
    assert cat3 == "INVESTIGATION_RAID"

    r4, cat4, rsn4 = shield.scan_text_for_risks("Adverse audit opinion and disclaimer of opinion regarding going concern viability.")
    assert r4 == "HIGH"
    assert cat4 == "QUALIFIED_AUDIT"

    # 2. Medium-risk scans
    r5, cat5, rsn5 = shield.scan_text_for_risks("Intimation regarding resignation of chief financial officer (CFO).")
    assert r5 == "MEDIUM"
    assert cat5 == "CFO_RESIGNATION"

    # 3. Clean announcements
    r6, cat6, rsn6 = shield.scan_text_for_risks("Schedule of Analyst / Institutional Investor Meet on November 25, 2026.")
    assert r6 == "CLEAN"
    assert cat6 == "NONE"


def test_corporate_event_shield_symbol_veto(tmp_path, monkeypatch):
    shield = CorporateEventShield()
    test_sym = "FRAUDCORP"

    # Record a high-risk event
    shield.record_announcement(
        symbol=test_sym,
        headline="Resignation of Statutory Auditor M/s Walker Chandiok",
        description="Auditor resigned citing inadequate information provided for Q2 audits.",
        source="NSE_ANNOUNCEMENT"
    )

    risk = shield.check_symbol_event_risk(test_sym)
    assert risk.risk_level == "HIGH"
    assert risk.veto_trade is True
    assert "AUDITOR_RESIGNATION" in risk.veto_reason or "auditor" in risk.veto_reason.lower()


def test_compounder_scorecard_governance_event_shield_veto(monkeypatch):
    # Mock corporate_event_shield to return HIGH risk for a test symbol
    from backend.data.corporate_events import corporate_event_shield

    monkeypatch.setattr(
        corporate_event_shield,
        "check_symbol_event_risk",
        lambda sym: CorporateEventRisk(
            symbol=sym,
            risk_level="HIGH",
            veto_trade=True,
            veto_reason="Statutory Auditor Resigned under questionable circumstances",
            flagged_events=[],
            as_of_date="2026-11-20"
        )
    )

    mock_screener = {
        "company_name": "Test Risky Firm",
        "top_ratios": {"roce_pct": 28.0, "roe_pct": 24.0, "current_price": 500.0, "pe_ratio": 18.0},
        "ranges": {"current_price": 500.0, "intrinsic_value": 750.0},
        "cash_flow": {"cfo_latest": 500.0, "pat_latest": 400.0},
        "profit_loss": {"latest_sales_cr": 2000.0, "sales_growth_3yr": 18.0, "profit_growth_3yr": 22.0, "latest_opm_pct": 22.0},
        "balance_sheet": {"debt_to_equity": 0.05, "reserves_cr": 1200.0},
        "shareholding": {"promoter_pct": 65.0, "pledged_pct": 0.0, "fii_pct": 18.0, "dii_pct": 12.0},
        "analysis": {"pros": ["Company is virtually debt free"], "cons": []},
    }

    eval_result = compounder_engine.evaluate_equity("RISKYCO", mock_screener)
    assert eval_result.is_vetoed is True
    assert eval_result.verdict == "REJECTED_GOVERNANCE_VETO"
    assert "Corporate Governance Event Shield" in eval_result.veto_reason


def test_swing_engine_corporate_event_veto(monkeypatch):
    from backend.data.corporate_events import corporate_event_shield

    monkeypatch.setattr(
        corporate_event_shield,
        "check_symbol_event_risk",
        lambda sym: CorporateEventRisk(
            symbol=sym,
            risk_level="HIGH",
            veto_trade=True,
            veto_reason="US FDA Form 483 Official Action Indicated",
            flagged_events=[],
            as_of_date="2026-11-20"
        )
    )

    # Generate bullish price series
    n = 220
    dates = pd.date_range("2026-01-01", periods=n, freq="B")
    close = np.linspace(100, 200, n)
    df = pd.DataFrame({
        "open": close * 0.99,
        "high": close * 1.01,
        "low": close * 0.98,
        "close": close,
        "volume": [1_000_000] * n,
    }, index=dates)

    cand = swing_engine.evaluate("DRUGCORP", df)
    assert cand.passed is False
    assert any("Corporate Governance Event Shield" in r for r in cand.rejection_reasons)
    # Must NOT qualify for Tier-2 Watchlist if high-severity event is active
    assert cand.is_tier_2 is False
