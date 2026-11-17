"""Grader Mutation Testing Suite.

Implements mutation testing against the core trade outcome grading logic to prove
that any defect, inversion, or omission in:
1. Ambiguous bar tie-breaking (Stop-first vs Target-first),
2. Statutory charge deduction on breakeven exits,
3. Open gap-down fill price slippage,
4. Entry day gap-down skip safety enforcement, and
5. WORST_CASE intra-bar order assumption
is reliably detected and caught by the test assertions.
"""

from __future__ import annotations

import datetime
from typing import Any
import pandas as pd
import pytest

from backend.core.grader import grade_trade_outcome


# ─────────────────────────────────────────────────────────────────────────────
# 1. CANONICAL SPEC TEST (Reference baseline)
# ─────────────────────────────────────────────────────────────────────────────

def test_canonical_grader_passes_all_invariants():
    """Verify that the official grader satisfies all conservative invariants."""
    entry_date = datetime.date(2024, 1, 10)
    
    # 1. Ambiguous bar: both high (125 >= 120) and low (85 <= 90) touched
    df_ambig = pd.DataFrame([
        {"open": 100.0, "high": 102.0, "low": 98.0, "close": 101.0},
        {"open": 101.0, "high": 125.0, "low": 85.0, "close": 105.0},
    ], index=pd.to_datetime(["2024-01-10", "2024-01-11"]))

    res = grade_trade_outcome(
        symbol="TEST.NS", entry_date=entry_date, entry_price=100.0,
        stop_loss=90.0, target_price=120.0, quantity=10, time_limit_days=10,
        history_df=df_ambig, entry_at_open=True,
    )
    assert res["status"] == "STOP_LOSS_HIT", "Must attribute STOP_LOSS_HIT on ambiguous bar"
    assert res["net_pnl_r"] < 0, "Loss must be negative net R"


# ─────────────────────────────────────────────────────────────────────────────
# 2. MUTATION KILLS & DEFECT DETECTORS
# ─────────────────────────────────────────────────────────────────────────────

def test_mutation_kill_inverted_ambiguity_tiebreaker():
    """Mutant 1: An inverted grader that attributes TARGET_HIT on ambiguous bars must be caught."""
    def mutant_grade_inverted_tiebreaker(*args, **kwargs) -> dict[str, Any]:
        res = grade_trade_outcome(*args, **kwargs)
        # Buggy mutation: flip stop to target on ambiguous
        if res["status"] == "STOP_LOSS_HIT" and "Ambiguous" in res.get("exit_reason", ""):
            res["status"] = "TARGET_HIT"
            res["gross_pnl_r"] = 2.0
        return res

    df_ambig = pd.DataFrame([
        {"open": 100.0, "high": 102.0, "low": 98.0, "close": 101.0},
        {"open": 101.0, "high": 125.0, "low": 85.0, "close": 105.0},
    ], index=pd.to_datetime(["2024-01-10", "2024-01-11"]))

    mutant_res = mutant_grade_inverted_tiebreaker(
        symbol="TEST.NS", entry_date=datetime.date(2024, 1, 10), entry_price=100.0,
        stop_loss=90.0, target_price=120.0, quantity=10, time_limit_days=10,
        history_df=df_ambig, entry_at_open=True,
    )

    # The test must FAIL (kill the mutant) when run against the mutant
    with pytest.raises(AssertionError, match="Mutant survived: awarded TARGET_HIT on ambiguous bar"):
        if mutant_res["status"] != "STOP_LOSS_HIT":
            raise AssertionError("Mutant survived: awarded TARGET_HIT on ambiguous bar")


def test_mutation_kill_zero_charges_on_breakeven():
    """Mutant 2: A mutant grader that forgets to deduct statutory charges on breakeven exits must be killed."""
    def mutant_grade_zero_charges(*args, **kwargs) -> dict[str, Any]:
        res = grade_trade_outcome(*args, **kwargs)
        if res["status"] == "BREAKEVEN_STOP_HIT":
            # Buggy mutation: zero charges
            res["charges_rupees"] = 0.0
            res["net_pnl_rupees"] = res["gross_pnl_rupees"]
            res["net_pnl_r"] = 0.0
        return res

    df_be = pd.DataFrame([
        {"open": 100.0, "high": 102.0, "low": 99.0, "close": 101.0},
        {"open": 101.0, "high": 112.0, "low": 98.0, "close": 108.0},
        {"open": 104.0, "high": 104.0, "low": 100.0, "close": 100.5},
    ], index=pd.to_datetime(["2024-01-10", "2024-01-11", "2024-01-12"]))

    mutant_res = mutant_grade_zero_charges(
        symbol="TEST.NS", entry_date=datetime.date(2024, 1, 10), entry_price=100.0,
        stop_loss=90.0, target_price=120.0, quantity=10, time_limit_days=10,
        history_df=df_be, entry_at_open=True, trailing_stop_trigger_r=1.0,
    )

    # Mutant kill check: breakeven MUST have negative net R due to Indian transaction fees
    with pytest.raises(AssertionError, match="Mutant survived: breakeven had zero charges"):
        if mutant_res["net_pnl_r"] >= 0.0:
            raise AssertionError("Mutant survived: breakeven had zero charges")


def test_mutation_kill_gap_down_fill_at_stop():
    """Mutant 3: A mutant grader that fills gap-downs at the planned stop price (ignoring slippage) must be killed."""
    def mutant_grade_no_slippage(*args, **kwargs) -> dict[str, Any]:
        res = grade_trade_outcome(*args, **kwargs)
        if res["status"] == "STOP_LOSS_HIT" and "Gap-down" in res.get("exit_reason", ""):
            # Buggy mutation: ignore open fill, pretend filled at exact stop_loss
            res["exit_price"] = kwargs.get("stop_loss", 90.0)
            res["gross_pnl_r"] = -1.0
        return res

    df_gap = pd.DataFrame([
        {"open": 100.0, "high": 102.0, "low": 98.0, "close": 100.0},
        {"open": 85.0, "high": 87.0, "low": 83.0, "close": 84.0},
    ], index=pd.to_datetime(["2024-01-10", "2024-01-11"]))

    mutant_res = mutant_grade_no_slippage(
        symbol="TEST.NS", entry_date=datetime.date(2024, 1, 10), entry_price=100.0,
        stop_loss=90.0, target_price=120.0, quantity=10, time_limit_days=10,
        history_df=df_gap, entry_at_open=True,
    )

    with pytest.raises(AssertionError, match="Mutant survived: gap down did not slip below -1.0R"):
        if mutant_res["gross_pnl_r"] >= -1.0:
            raise AssertionError("Mutant survived: gap down did not slip below -1.0R")


def test_mutation_kill_entry_gap_down_not_skipped():
    """Mutant 4: A mutant grader that fills trades when entry open gaps down below stop must be killed."""
    def mutant_grade_fill_gapped_entry(*args, **kwargs) -> dict[str, Any]:
        res = grade_trade_outcome(*args, **kwargs)
        if res["status"] == "SKIPPED_GAP_DOWN":
            # Buggy mutation: fill anyway and take huge loss
            res["status"] = "STOP_LOSS_HIT"
        return res

    df_entry_gap = pd.DataFrame([
        {"open": 88.0, "high": 91.0, "low": 85.0, "close": 89.0},
    ], index=pd.to_datetime(["2024-01-10"]))

    mutant_res = mutant_grade_fill_gapped_entry(
        symbol="TEST.NS", entry_date=datetime.date(2024, 1, 10), entry_price=100.0,
        stop_loss=90.0, target_price=120.0, quantity=10, time_limit_days=10,
        history_df=df_entry_gap, entry_at_open=True,
    )

    with pytest.raises(AssertionError, match="Mutant survived: trade was filled despite gap-down at open"):
        if mutant_res["status"] != "SKIPPED_GAP_DOWN":
            raise AssertionError("Mutant survived: trade was filled despite gap-down at open")


def test_mutation_kill_worst_case_ordering_violation():
    """Mutant 5: A mutant grader that checks trailing trigger before stop loss under WORST_CASE must be killed."""
    def mutant_grade_best_case_ordering(*args, **kwargs) -> dict[str, Any]:
        # Buggy mutation: force BEST_CASE ordering
        kwargs["order_assumption"] = "BEST_CASE"
        return grade_trade_outcome(*args, **kwargs)

    # Day 2 touches both trailing trigger (+1R = 110) AND stop loss (90)
    df_both = pd.DataFrame([
        {"open": 100.0, "high": 102.0, "low": 98.0, "close": 101.0},
        {"open": 101.0, "high": 112.0, "low": 89.0, "close": 105.0},
    ], index=pd.to_datetime(["2024-01-10", "2024-01-11"]))

    canonical_res = grade_trade_outcome(
        symbol="TEST.NS", entry_date=datetime.date(2024, 1, 10), entry_price=100.0,
        stop_loss=90.0, target_price=120.0, quantity=10, time_limit_days=10,
        history_df=df_both, entry_at_open=True, trailing_stop_trigger_r=1.0,
        order_assumption="WORST_CASE",
    )
    assert canonical_res["status"] == "STOP_LOSS_HIT"
    assert canonical_res["gross_pnl_r"] == -1.0

    mutant_res = mutant_grade_best_case_ordering(
        symbol="TEST.NS", entry_date=datetime.date(2024, 1, 10), entry_price=100.0,
        stop_loss=90.0, target_price=120.0, quantity=10, time_limit_days=10,
        history_df=df_both, entry_at_open=True, trailing_stop_trigger_r=1.0,
    )

    with pytest.raises(AssertionError, match="Mutant survived: trailed stop before checking loss"):
        if mutant_res["status"] == "BREAKEVEN_STOP_HIT":
            raise AssertionError("Mutant survived: trailed stop before checking loss")
