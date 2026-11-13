"""Indian Capital Gains Tax Engine (FY 2026-27 / AY 2027-28).

Implements FIFO lot matching, STCG (20.8%), LTCG (13.0% over ₹1.25L),
loss set-off rules, tax harvesting signals, and pre/post-tax P&L attribution.
"""

from __future__ import annotations
import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

from backend.core.config import get_tax_config


@dataclass
class EquityLot:
    symbol: str
    quantity: int
    buy_price: float
    buy_date: datetime.date
    buy_charges: float = 0.0


@dataclass
class RealizedTaxLot:
    symbol: str
    quantity: int
    buy_price: float
    buy_date: datetime.date
    sell_price: float
    sell_date: datetime.date
    holding_days: int
    is_long_term: bool
    gross_gain: float
    realized_charges: float
    net_gain: float
    estimated_tax: float


class IndianTaxEngine:
    """Computes Indian Capital Gains with strict FIFO and statutory set-offs."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.cfg = config or get_tax_config()
        cg_cfg = self.cfg.get("capital_gains", {})
        self.stcg_rate = cg_cfg.get("stcg", {}).get("effective_rate_standard", 0.208)
        self.ltcg_rate = cg_cfg.get("ltcg", {}).get("effective_rate_standard", 0.130)
        self.ltcg_exemption = cg_cfg.get("ltcg", {}).get("exemption_limit_rupees", 125000.0)

    def is_long_term(self, buy_date: datetime.date, sell_date: datetime.date) -> bool:
        """Check if holding period exceeds 365 calendar days for listed equities."""
        delta = (sell_date - buy_date).days
        return delta > 365

    def match_fifo_sale(
        self,
        symbol: str,
        open_lots: List[EquityLot],
        sell_qty: int,
        sell_price: float,
        sell_date: datetime.date,
        sell_charges: float = 0.0,
    ) -> Tuple[List[RealizedTaxLot], List[EquityLot]]:
        """Perform strict First-In First-Out (FIFO) lot depletion for a sale."""
        remaining_to_sell = sell_qty
        realized: List[RealizedTaxLot] = []
        updated_open_lots: List[EquityLot] = []

        # Sort lots by buy date ascending (FIFO)
        sorted_lots = sorted(open_lots, key=lambda l: l.buy_date)

        for lot in sorted_lots:
            if remaining_to_sell <= 0:
                updated_open_lots.append(lot)
                continue

            matched_qty = min(lot.quantity, remaining_to_sell)
            holding_days = (sell_date - lot.buy_date).days
            long_term = self.is_long_term(lot.buy_date, sell_date)

            # Prorate buy charges
            prorated_buy_charges = (matched_qty / lot.quantity) * lot.buy_charges if lot.quantity > 0 else 0.0
            prorated_sell_charges = (matched_qty / sell_qty) * sell_charges if sell_qty > 0 else 0.0
            total_lot_charges = round(prorated_buy_charges + prorated_sell_charges, 2)

            gross_gain = round((sell_price - lot.buy_price) * matched_qty, 2)
            net_gain = round(gross_gain - total_lot_charges, 2)

            # Estimate tax on single lot (standalone)
            if net_gain <= 0:
                est_tax = 0.0
            elif long_term:
                est_tax = round(net_gain * self.ltcg_rate, 2)
            else:
                est_tax = round(net_gain * self.stcg_rate, 2)

            realized.append(RealizedTaxLot(
                symbol=symbol,
                quantity=matched_qty,
                buy_price=lot.buy_price,
                buy_date=lot.buy_date,
                sell_price=sell_price,
                sell_date=sell_date,
                holding_days=holding_days,
                is_long_term=long_term,
                gross_gain=gross_gain,
                realized_charges=total_lot_charges,
                net_gain=net_gain,
                estimated_tax=est_tax,
            ))

            remaining_to_sell -= matched_qty
            if lot.quantity > matched_qty:
                updated_open_lots.append(EquityLot(
                    symbol=lot.symbol,
                    quantity=lot.quantity - matched_qty,
                    buy_price=lot.buy_price,
                    buy_date=lot.buy_date,
                    buy_charges=lot.buy_charges - prorated_buy_charges,
                ))

        return realized, updated_open_lots

    def compute_portfolio_tax_summary(self, realized_lots: List[RealizedTaxLot]) -> Dict[str, Any]:
        """Aggregate realized trades across FY with statutory loss set-offs:

        Set-off Hierarchy:
        1. Short-Term Capital Losses (STCL) offset STCG first, then LTCG.
        2. Long-Term Capital Losses (LTCL) can ONLY offset LTCG.
        3. LTCG qualifies for ₹1.25 Lakh exemption threshold.
        """
        stcg_pos = 0.0
        stcl_neg = 0.0
        ltcg_pos = 0.0
        ltcl_neg = 0.0
        total_charges = 0.0

        for lot in realized_lots:
            total_charges += lot.realized_charges
            if lot.is_long_term:
                if lot.net_gain >= 0:
                    ltcg_pos += lot.net_gain
                else:
                    ltcl_neg += abs(lot.net_gain)
            else:
                if lot.net_gain >= 0:
                    stcg_pos += lot.net_gain
                else:
                    stcl_neg += abs(lot.net_gain)

        # 1. Offset LTCL against LTCG
        net_ltcg = max(0.0, ltcg_pos - ltcl_neg)
        unabsorbed_ltcl = max(0.0, ltcl_neg - ltcg_pos)

        # 2. Offset STCL against STCG
        net_stcg = max(0.0, stcg_pos - stcl_neg)
        unabsorbed_stcl = max(0.0, stcl_neg - stcg_pos)

        # 3. Offset unabsorbed STCL against remaining net LTCG
        if unabsorbed_stcl > 0 and net_ltcg > 0:
            offset_against_ltcg = min(unabsorbed_stcl, net_ltcg)
            net_ltcg -= offset_against_ltcg
            unabsorbed_stcl -= offset_against_ltcg

        # 4. Apply ₹1.25 Lakh LTCG exemption
        taxable_ltcg = max(0.0, net_ltcg - self.ltcg_exemption)
        exempt_ltcg_used = min(net_ltcg, self.ltcg_exemption)

        # 5. Calculate Final Taxes
        tax_stcg = round(net_stcg * self.stcg_rate, 2)
        tax_ltcg = round(taxable_ltcg * self.ltcg_rate, 2)
        total_tax = round(tax_stcg + tax_ltcg, 2)

        total_gross_pnl = sum(l.gross_gain for l in realized_lots)
        total_net_pnl_pre_tax = sum(l.net_gain for l in realized_lots)
        net_pnl_post_tax = round(total_net_pnl_pre_tax - total_tax, 2)

        return {
            "gross_realized_pnl": round(total_gross_pnl, 2),
            "total_trading_charges": round(total_charges, 2),
            "net_pnl_pre_tax": round(total_net_pnl_pre_tax, 2),
            "stcg_gross": round(stcg_pos, 2),
            "stcl_gross": round(stcl_neg, 2),
            "net_stcg_taxable": round(net_stcg, 2),
            "stcg_tax_payable": tax_stcg,
            "ltcg_gross": round(ltcg_pos, 2),
            "ltcl_gross": round(ltcl_neg, 2),
            "ltcg_exemption_utilized": round(exempt_ltcg_used, 2),
            "net_ltcg_taxable": round(taxable_ltcg, 2),
            "ltcg_tax_payable": tax_ltcg,
            "total_tax_payable": total_tax,
            "net_pnl_post_tax": net_pnl_post_tax,
            "unabsorbed_stcl_carry_forward": round(unabsorbed_stcl, 2),
            "unabsorbed_ltcl_carry_forward": round(unabsorbed_ltcl, 2),
        }

    def check_tax_harvesting_opportunities(
        self,
        holdings: List[Dict[str, Any]],
        today: datetime.date,
    ) -> List[Dict[str, Any]]:
        """Identify holdings approaching 12 months or loss-harvesting candidates."""
        suggestions = []
        for h in holdings:
            buy_dt = h.get("buy_date")
            if isinstance(buy_dt, str):
                buy_dt = datetime.date.fromisoformat(buy_dt)

            days_held = (today - buy_dt).days
            unrealized = h.get("unrealized_pnl", 0.0)

            # Approaching 12 months (day 330 to 365) with unrealized gain: suggest deferring sale
            if 330 <= days_held <= 365 and unrealized > 0:
                days_left = 366 - days_held
                suggestions.append({
                    "symbol": h["symbol"],
                    "type": "DEFER_SALE_LTCG",
                    "reason": f"Holding for {days_left} more days converts gain from 20.8% STCG to 13.0% LTCG.",
                    "potential_tax_saving": round(unrealized * (self.stcg_rate - self.ltcg_rate), 2),
                })

            # March tax loss harvesting: sell to offset realized gains
            if today.month == 3 and unrealized < -5000:
                suggestions.append({
                    "symbol": h["symbol"],
                    "type": "TAX_LOSS_HARVEST",
                    "reason": f"Harvesting ₹{abs(unrealized):,.0f} loss before March 31 can offset realized capital gains.",
                    "potential_tax_saving": round(abs(unrealized) * self.stcg_rate, 2),
                })

        return suggestions


tax_engine = IndianTaxEngine()
