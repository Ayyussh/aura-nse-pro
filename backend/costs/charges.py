"""Indian Brokerage and Statutory Charges Calculator.

Accurately implements statutory taxation and transaction fees for Indian equities:
- STT (Securities Transaction Tax): 0.1% Buy, 0.1% Sell for Delivery
- Stamp Duty: 0.015% on Buy Turnover only
- NSE/BSE Transaction Charges: ~0.00345% of total turnover
- SEBI Turnover Fee: ₹10 per Crore (0.0001%)
- GST: 18% on (Brokerage + Exchange Txn Charges + SEBI Fee)
- DP Charges: Flat ₹13.50 + 18% GST (₹15.93) per scrip on sell day
- Slippage model by market cap tier (5, 10, 20 bps)
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

from backend.core.config import get_charges_config


@dataclass
class TradeCharges:
    buy_turnover: float
    sell_turnover: float
    total_turnover: float
    stt: float
    stamp_duty: float
    exchange_txn_charge: float
    sebi_fee: float
    brokerage: float
    gst: float
    dp_charge: float
    total_statutory_charges: float
    total_charges_and_brokerage: float
    slippage_cost: float
    total_costs: float
    breakeven_sell_price: float
    charges_in_rupees: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class IndianChargesEngine:
    """Calculates granular Indian equity trading costs."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.cfg = config or get_charges_config()
        self.effective_date = self.cfg.get("effective_date", "2026-11-13")
        self.rates = self.cfg.get("rates", {})
        self.broker_profiles = self.cfg.get("broker_profiles", {})
        self.default_profile = self.cfg.get("default_broker_profile", "zero_brokerage_delivery")
        self.slippage_cfg = self.cfg.get("slippage_model", {})

    def calculate_delivery_charges(
        self,
        buy_price: float,
        sell_price: float,
        quantity: int,
        broker_profile_name: Optional[str] = None,
        market_cap_tier: str = "large_cap", # large_cap, mid_cap, small_cap
        include_slippage: bool = False,
    ) -> TradeCharges:
        """Calculate complete statutory & transaction charges for a delivery/swing trade."""
        if quantity <= 0 or buy_price <= 0 or sell_price <= 0:
            raise ValueError("Price and quantity must be positive numbers.")

        buy_turnover = round(buy_price * quantity, 2)
        sell_turnover = round(sell_price * quantity, 2)
        total_turnover = round(buy_turnover + sell_turnover, 2)

        stt_rates = self.rates.get("stt", {})
        stt_buy = round(buy_turnover * stt_rates.get("delivery_buy_rate", 0.001), 2)
        stt_sell = round(sell_turnover * stt_rates.get("delivery_sell_rate", 0.001), 2)
        total_stt = round(stt_buy + stt_sell, 2)

        stamp_rate = self.rates.get("stamp_duty", {}).get("buy_rate", 0.00015)
        stamp_duty = round(buy_turnover * stamp_rate, 2)

        txn_rate = self.rates.get("exchange_txn_charge", {}).get("nse_rate", 0.0000345)
        exchange_txn_charge = round(total_turnover * txn_rate, 2)

        sebi_rate_per_cr = self.rates.get("sebi_turnover_fee", {}).get("rate_per_crore", 10.0)
        sebi_fee = round((total_turnover / 10000000.0) * sebi_rate_per_cr, 2)

        # Brokerage calculation
        profile_key = broker_profile_name or self.default_profile
        profile = self.broker_profiles.get(profile_key, {})
        buy_brokerage = float(profile.get("delivery_brokerage_buy", 0.0))
        sell_brokerage = float(profile.get("delivery_brokerage_sell", 0.0))
        if "percentage_rate" in profile:
            pct = profile["percentage_rate"]
            min_b = profile.get("min_brokerage", 0.0)
            buy_brokerage = max(round(buy_turnover * pct, 2), min_b)
            sell_brokerage = max(round(sell_turnover * pct, 2), min_b)
        total_brokerage = round(buy_brokerage + sell_brokerage, 2)

        # GST: 18% on (Brokerage + Exchange Txn Charges + SEBI Fee)
        gst_base = total_brokerage + exchange_txn_charge + sebi_fee
        gst_rate = self.rates.get("gst", {}).get("rate", 0.18)
        gst = round(gst_base * gst_rate, 2)

        # DP Charge on Sell Day: Base ₹13.50 + 18% GST = ₹15.93
        dp_cfg = self.rates.get("dp_charges", {})
        base_dp = dp_cfg.get("flat_per_sell_scrip", 13.50)
        dp_gst = round(base_dp * dp_cfg.get("gst_rate", 0.18), 2)
        total_dp = round(base_dp + dp_gst, 2)

        # Slippage estimation
        slippage_cost = 0.0
        if include_slippage:
            bps_key = f"{market_cap_tier}_bps"
            bps = self.slippage_cfg.get(bps_key, 10.0)
            slippage_rate = bps / 10000.0
            slippage_cost = round(total_turnover * slippage_rate, 2)

        statutory_only = round(total_stt + stamp_duty + exchange_txn_charge + sebi_fee + gst + total_dp, 2)
        total_all = round(statutory_only + total_brokerage, 2)
        total_with_slippage = round(total_all + slippage_cost, 2)

        # Breakeven calculation: sell price required to make net profit >= 0
        # Sell turnover must cover buy_turnover + all buy/sell charges + DP
        breakeven_sell_price = round((buy_turnover + total_all) / quantity, 2)

        return TradeCharges(
            buy_turnover=buy_turnover,
            sell_turnover=sell_turnover,
            total_turnover=total_turnover,
            stt=total_stt,
            stamp_duty=stamp_duty,
            exchange_txn_charge=exchange_txn_charge,
            sebi_fee=sebi_fee,
            brokerage=total_brokerage,
            gst=gst,
            dp_charge=total_dp,
            total_statutory_charges=statutory_only,
            total_charges_and_brokerage=total_all,
            slippage_cost=slippage_cost,
            total_costs=total_with_slippage,
            breakeven_sell_price=breakeven_sell_price,
            charges_in_rupees=total_all,
        )


charges_engine = IndianChargesEngine()
