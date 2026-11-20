"""Tests for Strategy-Level Benchmark Comparison, Point-in-Time Data, and Invalidation Triggers."""

import pytest
from backend.analytics.benchmark_comparison import benchmark_engine, AlphaComparisonResult
from backend.fundamental.compounder_scorecard import compounder_engine
from backend.fundamental.screener_client import screener_client


def test_benchmark_alpha_comparison():
    res = benchmark_engine.evaluate_alpha()
    assert isinstance(res, AlphaComparisonResult)
    assert res.as_of_date is not None
    assert res.swing_strategy.strategy_name == "AURA Institutional Swing Alpha"
    assert res.swing_strategy.net_return_pct > 0.0
    assert res.swing_strategy.max_drawdown_pct < res.benchmark.max_drawdown_pct
    assert res.drawdown_reduction_pct > 0.0
    assert res.calmar_outperformance_ratio > 1.0
    assert res.beating_benchmark_after_costs is True
    assert "point_in_time_guarantee" in res.data_quality_summary


def test_compounder_structured_invalidation_triggers():
    mock_screener = {
        "company_name": "Test Compounder Ltd",
        "top_ratios": {"roce_pct": 26.0, "roe_pct": 22.0, "current_price": 1200.0, "pe_ratio": 24.0},
        "ranges": {"current_price": 1200.0, "intrinsic_value": 1500.0},
        "cash_flow": {"cfo_latest": 600.0, "pat_latest": 500.0},
        "profit_loss": {"latest_sales_cr": 3000.0, "sales_growth_3yr": 16.0, "profit_growth_3yr": 19.0, "latest_opm_pct": 20.0},
        "balance_sheet": {"debt_to_equity": 0.10, "reserves_cr": 2000.0},
        "shareholding": {"promoter_pct": 68.0, "pledged_pct": 0.0, "fii_pct": 15.0, "dii_pct": 10.0},
        "analysis": {"pros": ["Company has good return on equity"], "cons": []},
    }

    eval_res = compounder_engine.evaluate_equity("COMPOUNDER", mock_screener)
    assert eval_res.invalidation_triggers is not None
    assert len(eval_res.invalidation_triggers) >= 4
    assert any("ROCE" in t for t in eval_res.invalidation_triggers)
    assert any("Promoter" in t for t in eval_res.invalidation_triggers)
    assert any("Operating Cash Flow" in t for t in eval_res.invalidation_triggers)


def test_screener_point_in_time_metadata():
    fallback = screener_client._build_offline_fallback("INFY")
    # Live or offline parsing structures point-in-time
    assert fallback["symbol"] == "INFY"
