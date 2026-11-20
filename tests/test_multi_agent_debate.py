"""Unit tests for Multi-Agent Dialectical Debate Engine, Tiered Model Routing, and Dossier Generator."""

from __future__ import annotations
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from backend.core.config import settings
from backend.llm.debate import MultiAgentDebateEngine, debate_engine
from backend.llm.router import call_tiered_model, llm_router
from scripts.analyze_ticker import generate_html_dossier


@pytest.fixture
def sample_setup_data():
    return {
        "symbol": "INFY.NS",
        "sector": "Information Technology",
        "current_price": 1850.0,
        "entry_price": 1850.0,
        "target_price": 2035.0,
        "stop_loss": 1757.5,
        "win_probability_pct": 68.5,
        "ev_r": 0.55,
        "macro_regime": "GREEN",
        "pe_ratio": 24.5,
        "roe_pct": 31.2,
        "debt_to_equity": 0.08,
        "fair_value_mid": 2150.0,
        "margin_of_safety_pct": 16.2,
        "swing_setup_passed": True,
        "indicators": {
            "rsi_14": 56.4,
            "adx_14": 26.8,
            "sma_50": 1810.0,
            "sma_200": 1680.0,
            "volume_ratio_20d": 1.45,
        },
    }


def test_tiered_model_selection():
    """Verify call_tiered_model selects correct models according to tier."""
    with patch.object(llm_router, "get_active_vault_entries", return_value=[
        MagicMock(id=1, provider="gemini", model_name="gemini-2.5-flash", api_key="dummy", is_active=True, rpm_limit=60)
    ]):
        with patch.object(llm_router, "complete_json_prompt", return_value={"test": "ok"}) as mock_complete:
            res = call_tiered_model("Test prompt", tier="quick")
            assert res.get("status") in ["SUCCESS", "FALLBACK"]


def test_debate_engine_offline_fallback(sample_setup_data):
    """Verify debate engine produces valid deterministic fallback when LLM is offline."""
    with patch.object(llm_router, "call_tiered_model", return_value={"status": "FALLBACK", "data": None}):
        engine = MultiAgentDebateEngine()
        result = engine.run_debate("INFY.NS", sample_setup_data, rounds=2)

        assert result["symbol"] == "INFY.NS"
        assert result["rounds_conducted"] == 2
        # Round 1: Bull & Bear (2 entries); Round 2: Bull & Bear (2 entries) -> 4 total transcript items
        assert len(result["transcript"]) == 4

        # Verify Round 1 items
        bull_entry = result["transcript"][0]
        assert bull_entry["speaker"] == "Agent Bull"
        assert "core_thesis" in bull_entry["data"]
        assert len(bull_entry["data"]["primary_catalysts"]) > 0

        bear_entry = result["transcript"][1]
        assert bear_entry["speaker"] == "Agent Bear"
        assert "counter_thesis" in bear_entry["data"]
        assert len(bear_entry["data"]["structural_hazards"]) > 0

        # Verify Adjudication
        adj = result["adjudication"]
        assert adj["verdict"] in ["APPROVED", "APPROVED_REDUCED_SIZE", "REJECTED"]
        assert "winner" in adj
        assert "confidence_pct" in adj
        assert "arbitrator_rationale" in adj


def test_debate_engine_with_mocked_llm(sample_setup_data):
    """Verify multi-round debate with realistic mocked LLM agent responses."""
    bull_mock = {
        "round_theme": "Bullish Thesis",
        "core_thesis": "Strong momentum consolidation breakout above 50-EMA with expanding volume.",
        "primary_catalysts": ["RSI at 56 indicates healthy room to run", "Institutional order flow support"],
        "technical_edge": "High-liquidity setup displaying positive mathematical expectancy.",
        "target_defense": "High conviction target at 2035.",
    }
    bear_mock = {
        "round_theme": "Bearish Counter",
        "counter_thesis": "Global tech spending slowdown poses guidance cut risk at upcoming earnings.",
        "structural_hazards": ["Rich PE of 24.5x relative to peers", "Macro US rate environment"],
        "technical_fragility": "Failure of buyers could trigger cascade stop hits.",
        "invalidation_condition": "Daily close below 1757.50 stop loss.",
    }
    arbitrator_mock = {
        "winner": "BULL",
        "verdict": "APPROVED",
        "confidence_pct": 78.0,
        "consensus_thesis": "Bull arguments supported by high volume and positive Expected Value.",
        "arbitrator_rationale": "Strong risk-reward setup outweighing overhead supply.",
        "key_catalysts": ["Breakout above 1860 with volume > 1.2x avg"],
        "critical_vulnerabilities": ["Short-term earnings volatility"],
        "invalidation_criteria": "Close below 1757.50",
        "recommended_sizing_multiplier": 1.0,
    }

    def mock_call(prompt, system_prompt="", tier="quick", response_json=True):
        if "Chief Investment Officer" in system_prompt or tier == "deep":
            return {"status": "SUCCESS", "data": arbitrator_mock}
        elif "Agent Bull" in system_prompt:
            return {"status": "SUCCESS", "data": bull_mock}
        elif "Agent Bear" in system_prompt:
            return {"status": "SUCCESS", "data": bear_mock}
        return {"status": "SUCCESS", "data": arbitrator_mock}

    with patch.object(llm_router, "call_tiered_model", side_effect=mock_call):
        engine = MultiAgentDebateEngine()
        result = engine.run_debate("INFY.NS", sample_setup_data, rounds=1)

        assert result["rounds_conducted"] == 1
        assert len(result["transcript"]) == 2
        assert result["transcript"][0]["data"]["core_thesis"] == bull_mock["core_thesis"]
        assert result["transcript"][1]["data"]["counter_thesis"] == bear_mock["counter_thesis"]
        assert result["adjudication"]["verdict"] == "APPROVED"
        assert result["adjudication"]["confidence_pct"] == 78.0


def test_generate_html_dossier():
    """Verify HTML research dossier generation renders all institutional sections."""
    mock_debate = {
        "symbol": "INFY.NS",
        "rounds_conducted": 1,
        "transcript": [
            {
                "round": 1,
                "speaker": "Agent Bull",
                "data": {
                    "round_theme": "Bullish Thesis (Round 1)",
                    "core_thesis": "Bullish expansion thesis",
                    "primary_catalysts": ["Advantage 1", "Advantage 2"],
                    "technical_edge": "Strong moving average support",
                    "target_defense": "2035 target supported by ATR",
                },
            },
            {
                "round": 1,
                "speaker": "Agent Bear",
                "data": {
                    "round_theme": "Bearish Counter (Round 1)",
                    "counter_thesis": "Bearish resistance thesis",
                    "structural_hazards": ["Concern 1", "Concern 2"],
                    "technical_fragility": "Overhead supply cluster",
                    "invalidation_condition": "Breach of stop loss 1757.50",
                },
            },
        ],
        "adjudication": {
            "verdict": "APPROVED",
            "winner": "BULL",
            "confidence_pct": 75.0,
            "consensus_thesis": "High conviction setup",
            "arbitrator_rationale": "Strong risk-reward setup",
            "invalidation_criteria": "Breach below 1757.50",
        },
    }

    mock_charges = {
        "buy_turnover": 18500.0,
        "stt": 37.0,
        "exchange_txn_charge": 1.28,
        "sebi_fee": 0.04,
        "stamp_duty": 2.78,
        "gst": 0.24,
        "dp_charge": 15.93,
        "total_charges_and_brokerage": 57.27,
        "total_costs": 75.77,
    }

    html = generate_html_dossier(
        symbol="INFY.NS",
        company_name="INFY",
        sector="Information Technology",
        current_price=1850.0,
        as_of_ist="20 Nov 2026, 03:30 PM IST",
        regime={"regime_label": "GREEN", "nifty_close": 25500.0, "vix": 14.5},
        indicators={"rsi_14": 58.0, "adx_14": 27.5, "sma_50": 1810.0, "sma_200": 1700.0},
        ml_res={"win_probability_pct": 68.0, "ev_r": 0.52, "model_version": "v2_calibrated"},
        swing_cand=None,
        value_pick=None,
        debate_res=mock_debate,
        charges=mock_charges,
    )

    assert "<title>AURA Institutional Dossier — INFY.NS</title>" in html
    assert "Multi-Agent Dialectical Debate Transcript" in html
    assert "Agent Bull" in html
    assert "Agent Bear" in html
    assert "Chief Arbitrator Summary Ruling" in html
    assert "Indian Statutory Charges Breakdown (Paisa Accuracy)" in html
    assert "₹18,500.00" in html
    assert "₹75.77" in html
