"""Milestone 2 Unit Tests: Indian Charges, Capital Gains Tax, and Position Sizing."""

import datetime
import pytest

from backend.costs.charges import IndianChargesEngine
from backend.tax.capital_gains import IndianTaxEngine, EquityLot
from backend.risk.sizing import RiskGuardEngine


def test_charges_worked_example():
    """Verify exact worked example:

    Buying 100 shares at ₹1,00,000 and selling at ₹1,05,000 gives roughly ₹240-245 in total charges.
    """
    engine = IndianChargesEngine()
    result = engine.calculate_delivery_charges(
        buy_price=1000.0,
        sell_price=1050.0,
        quantity=100,
        broker_profile_name="zero_brokerage_delivery",
    )

    # Validate breakdowns
    assert result.buy_turnover == 100000.0
    assert result.sell_turnover == 105000.0
    assert result.total_turnover == 205000.0
    assert result.stt == 205.0  # 0.1% on buy (100) + 0.1% on sell (105)
    assert result.stamp_duty == 15.0  # 0.015% on buy
    assert result.dp_charge == 15.93  # ₹13.50 + 18% GST

    # Total statutory and brokerage charges must fall between ₹240 and ₹245
    assert 240.0 <= result.total_charges_and_brokerage <= 245.0
    assert result.total_charges_and_brokerage == 244.52
    assert result.breakeven_sell_price == 1002.45


def test_tax_engine_fifo_and_setoff():
    """Verify FIFO matching and statutory capital gains set-off."""
    tax = IndianTaxEngine()

    open_lots = [
        EquityLot(symbol="TCS.NS", quantity=50, buy_price=3000.0, buy_date=datetime.date(2025, 1, 10)),
        EquityLot(symbol="TCS.NS", quantity=50, buy_price=3200.0, buy_date=datetime.date(2025, 8, 15)),
    ]

    # Sell 60 shares on 2026-03-01:
    # First lot (50 shares): Held > 365 days -> LTCG: (3500 - 3000)*50 = 25,000
    # Second lot (10 shares): Held < 365 days -> STCG: (3500 - 3200)*10 = 3,000
    sell_date = datetime.date(2026, 3, 1)
    realized, remaining_lots = tax.match_fifo_sale(
        symbol="TCS.NS",
        open_lots=open_lots,
        sell_qty=60,
        sell_price=3500.0,
        sell_date=sell_date,
        sell_charges=120.0,
    )

    assert len(realized) == 2
    assert realized[0].quantity == 50
    assert realized[0].is_long_term is True
    assert realized[1].quantity == 10
    assert realized[1].is_long_term is False

    assert len(remaining_lots) == 1
    assert remaining_lots[0].quantity == 40
    assert remaining_lots[0].buy_price == 3200.0

    # Summary set-off check:
    summary = tax.compute_portfolio_tax_summary(realized)
    assert summary["stcg_gross"] > 0
    # LTCG < ₹1.25 Lakh exemption threshold -> 0 tax on LTCG
    assert summary["ltcg_tax_payable"] == 0.0
    assert summary["stcg_tax_payable"] > 0.0


def test_position_sizing_and_regime():
    """Verify position sizing under capital, risk, stop distance, and regime rules."""
    risk = RiskGuardEngine()

    # Total capital ₹3,00,000, 1.5% risk = ₹4,500.
    # Entry: ₹500, Stop: ₹470 (risk ₹30, distance 6% <= 8%).
    # Base Qty = floor(4500 / 30) = 150 shares.
    # Capital required: 150 * 500 = ₹75,000 (well within 20% of ₹3,00,000 = ₹60,000? Wait, 20% of 3L is 60k, so 120 shares).
    # If Entry: ₹200, Stop: ₹190 (risk ₹10, distance 5% <= 8%).
    # Total capital ₹1,00,000, 1.5% risk = ₹1,500.
    # Base Qty = floor(1500 / 10) = 150 shares.
    # Capital required = 150 * 200 = 30,000 > 20% (20,000). Max by 20% cap = 100 shares.
    decision = risk.compute_position_size(
        symbol="INFY.NS",
        entry_price=200.0,
        stop_loss=190.0,
        target_price=220.0,
        sector="IT",
        total_capital=100000.0,
        available_cash=100000.0,
        avg_20d_volume=1000000,
        macro_regime="GREEN",
    )
    assert decision.allowed is True
    # Clamped to 20% capital cap: ₹20,000 / ₹200 = 100 shares
    assert decision.quantity == 100
    assert decision.capital_required == 20000.0

    # Under AMBER regime, risk is halved (₹750 / ₹10 = 75 shares)
    amber_decision = risk.compute_position_size(
        symbol="INFY.NS",
        entry_price=200.0,
        stop_loss=190.0,
        target_price=220.0,
        sector="IT",
        total_capital=100000.0,
        available_cash=100000.0,
        avg_20d_volume=1000000,
        macro_regime="AMBER",
    )
    assert amber_decision.allowed is True
    assert amber_decision.quantity == 75

    # Under RED regime, no new entries allowed
    red_decision = risk.compute_position_size(
        symbol="INFY.NS",
        entry_price=200.0,
        stop_loss=190.0,
        target_price=220.0,
        sector="IT",
        total_capital=100000.0,
        available_cash=100000.0,
        avg_20d_volume=1000000,
        macro_regime="RED",
    )
    assert red_decision.allowed is False
    assert red_decision.status == "SKIPPED_REGIME_RED"

    # Stop too wide rejection (> 8%)
    wide_stop_decision = risk.compute_position_size(
        symbol="INFY.NS",
        entry_price=100.0,
        stop_loss=90.0,  # 10% distance > 8%
        target_price=120.0,
        sector="IT",
        total_capital=100000.0,
        available_cash=100000.0,
        avg_20d_volume=1000000,
        macro_regime="GREEN",
    )
    assert wide_stop_decision.allowed is False
    assert wide_stop_decision.status == "REJECTED_STOP_TOO_WIDE"
