"""Unit tests for 100-Point Institutional Quality Compounder Matrix & Screener Client."""

from __future__ import annotations
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from backend.fundamental.compounder_scorecard import CompounderScorecardEngine, compounder_engine
from backend.fundamental.screener_client import ScreenerClient, _clean_number


def test_clean_number_parser():
    """Verify Indian numeric formatting parser."""
    assert _clean_number("₹ 8,59,296 Cr.") == 859296.0
    assert _clean_number("63.0 %") == 63.0
    assert _clean_number("-13%") == -13.0
    assert _clean_number("N/A") is None
    assert _clean_number("") is None


def test_compounder_scorecard_weights_sum_to_100():
    """Verify the 8 categories strictly sum to 100 points."""
    engine = CompounderScorecardEngine()
    ev = engine.evaluate_equity("INFY.NS")
    total_weight = sum(cat.weight for cat in ev.categories.values())
    assert total_weight == 100.0
    assert ev.max_possible_score == 100.0


def test_hard_veto_on_high_promoter_pledging():
    """Verify strict Hard Veto triggers when promoter pledge exceeds 20%."""
    engine = CompounderScorecardEngine()
    screener_mock = {
        "company_name": "Pledge Trap Ltd",
        "top_ratios": {"roce_pct": 35.0, "roe_pct": 30.0, "pe_ratio": 8.0},
        "ranges": {"sales_growth_3_years": 25.0, "profit_growth_3_years": 30.0},
        "cash_flow": {"cfo_to_pat_5y_pct": 95.0, "fcf_latest_cr": 200.0},
        "balance_sheet": {"debt_to_equity": 0.1},
        "shareholding": {"pledged_pct": 25.5, "promoter_pct": 50.0, "fii_pct": 10.0, "dii_pct": 10.0},
        "analysis": {"pros": ["Great profit growth"], "cons": []},
    }

    ev = engine.evaluate_equity("TRAP.NS", screener_data=screener_mock)
    assert ev.is_vetoed is True
    assert ev.total_score == 0.0
    assert "Governance" in ev.grade or "VETOED" in ev.grade
    assert ev.verdict == "REJECTED_GOVERNANCE_VETO"
    assert "20%" in (ev.veto_reason or "")


def test_high_conviction_compounder_grade_a():
    """Verify bluechip compounder with stellar ROCE, FCF, and zero debt achieves Grade A."""
    engine = CompounderScorecardEngine()
    tcs_mock = {
        "company_name": "Tata Consultancy Services Ltd",
        "top_ratios": {
            "market_cap_cr": 850000.0,
            "current_price": 2400.0,
            "pe_ratio": 16.0,
            "book_value": 330.0,
            "roce_pct": 60.0,
            "roe_pct": 50.0,
        },
        "ranges": {
            "sales_growth_3_years": 8.0,
            "sales_growth_5_years": 10.0,
            "profit_growth_3_years": 9.0,
            "profit_growth_5_years": 10.0,
            "roe_3_years": 50.0,
        },
        "cash_flow": {
            "cfo_to_pat_5y_pct": 95.0,
            "fcf_latest_cr": 45000.0,
            "fcf_history_cr": [35000.0, 40000.0, 45000.0],
        },
        "profit_loss": {
            "latest_opm_pct": 26.0,
        },
        "balance_sheet": {
            "debt_to_equity": 0.08,
            "reserves_cr": 100000.0,
        },
        "shareholding": {
            "promoter_pct": 71.8,
            "fii_pct": 10.0,
            "dii_pct": 13.0,
            "pledged_pct": 0.0,
        },
        "analysis": {"pros": ["High return on equity"], "cons": []},
    }

    tech_data = {
        "close": 2400.0,
        "sma_50": 2350.0,
        "sma_200": 2200.0,
        "rsi_14": 55.0,
        "volume_ratio_20d": 1.15,
    }
    macro_regime = {"regime_label": "GREEN", "india_vix": 14.5}

    ev = engine.evaluate_equity(
        "TCS.NS",
        screener_data=tcs_mock,
        technical_data=tech_data,
        macro_regime=macro_regime,
        margin_of_safety_pct=18.0,
    )

    assert ev.is_vetoed is False
    assert ev.total_score >= 80.0
    assert "GRADE A" in ev.grade
    assert ev.verdict == "APPROVED_COMPOUNDER"
    assert ev.categories["financial_quality"].score >= 18.0
    assert ev.categories["cash_flow"].score >= 13.0
    assert ev.categories["balance_sheet"].score >= 9.0


def test_screener_client_offline_fallback():
    """Verify ScreenerClient produces complete offline fallback if network fails."""
    with patch.object(ScreenerClient, "_fetch_html", return_value=(None, "")):
        client = ScreenerClient()
        data = client.fetch_company_data("OFFLINE_MOCK.NS", force_refresh=True)
        assert data["status"] == "FALLBACK"
        assert "top_ratios" in data
        assert "cash_flow" in data
        assert "shareholding" in data
