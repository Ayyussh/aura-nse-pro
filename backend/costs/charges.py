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

from dataclasses import asdict, dataclass
from typing import Any

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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class IndianChargesEngine:
    """Calculates granular Indian equity trading costs."""

    def __init__(self, config: dict[str, Any] | None = None):
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
        broker_profile_name: str | None = None,
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

    def calculate_single_order_charges(
        self,
        price: float,
        quantity: int,
        side: str = "BUY",  # "BUY" or "SELL"
        broker_profile_name: str | None = None,
    ) -> dict[str, float]:
        """Calculate statutory and brokerage charges for a single order side."""
        if quantity <= 0 or price <= 0:
            raise ValueError("Price and quantity must be positive numbers.")

        turnover = round(price * quantity, 2)
        is_buy = (side.upper() == "BUY")

        # STT: 0.1% on delivery BUY or SELL
        stt_rate = self.rates.get("stt", {}).get("delivery_buy_rate" if is_buy else "delivery_sell_rate", 0.001)
        stt = round(turnover * stt_rate, 2)

        # Stamp duty: 0.015% on BUY only
        stamp_rate = self.rates.get("stamp_duty", {}).get("buy_rate", 0.00015) if is_buy else 0.0
        stamp_duty = round(turnover * stamp_rate, 2)

        # Exchange txn charge: ~0.00345% of turnover
        txn_rate = self.rates.get("exchange_txn_charge", {}).get("nse_rate", 0.0000345)
        exchange_txn = round(turnover * txn_rate, 2)

        # SEBI fee: ₹10 per crore (0.0001%)
        sebi_rate = self.rates.get("sebi_turnover_fee", {}).get("rate_per_crore", 10.0)
        sebi_fee = round((turnover / 10000000.0) * sebi_rate, 2)

        # Brokerage
        profile_key = broker_profile_name or self.default_profile
        profile = self.broker_profiles.get(profile_key, {})
        brokerage = float(profile.get("delivery_brokerage_buy" if is_buy else "delivery_brokerage_sell", 0.0))

        # GST: 18% on (Brokerage + Exchange Txn + SEBI)
        gst_base = brokerage + exchange_txn + sebi_fee
        gst = round(gst_base * self.rates.get("gst", {}).get("rate", 0.18), 2)

        # DP charge applies only on SELL side for delivery
        dp_charge = 0.0
        if not is_buy:
            dp_cfg = self.rates.get("dp_charges", {})
            base_dp = dp_cfg.get("flat_per_sell_scrip", 13.50)
            dp_gst = round(base_dp * dp_cfg.get("gst_rate", 0.18), 2)
            dp_charge = round(base_dp + dp_gst, 2)

        order_charges = round(stt + stamp_duty + exchange_txn + sebi_fee + brokerage + gst, 2)
        total_with_dp = round(order_charges + dp_charge, 2)

        return {
            "turnover": turnover,
            "stt": stt,
            "stamp_duty": stamp_duty,
            "exchange_txn_charge": exchange_txn,
            "sebi_fee": sebi_fee,
            "brokerage": brokerage,
            "gst": gst,
            "dp_charge": dp_charge,
            "order_charges": order_charges,
            "total_charges": order_charges,
            "total_charges_with_dp": total_with_dp,
        }

    def compare_with_upstox_order(
        self,
        symbol: str,
        price: float,
        quantity: int,
        upstox_charges: dict[str, Any],
        side: str = "BUY",
        broker_profile_name: str | None = None,
    ) -> dict[str, Any]:
        """Compare our engine's calculation against Upstox's Charges API and log differences."""
        our_calc = self.calculate_single_order_charges(price, quantity, side=side, broker_profile_name=broker_profile_name)

        differences = {}
        comparison_table = {}

        fields = ["turnover", "stt", "stamp_duty", "exchange_txn_charge", "sebi_fee", "brokerage", "gst", "total_charges"]
        for field in fields:
            our_val = our_calc.get(field, 0.0)
            upstox_val = float(upstox_charges.get(field, 0.0))
            diff = round(our_val - upstox_val, 2)
            pct_diff = round((diff / upstox_val * 100.0), 2) if upstox_val > 0 else 0.0

            comparison_table[field] = {
                "our_engine": our_val,
                "upstox_api": upstox_val,
                "diff_rupees": diff,
                "diff_pct": pct_diff,
            }
            if abs(diff) > 0.05:  # Tolerance for fractional paise rounding
                differences[field] = {
                    "our_engine": our_val,
                    "upstox_api": upstox_val,
                    "diff_rupees": diff,
                }

        is_consistent = len(differences) == 0
        dp_note = None
        if side.upper() == "SELL":
            dp_note = "Upstox /v2/charges/brokerage evaluates order-level charges and excludes DP charges. CDSL/NSDL charges ₹15.93 (₹13.50 + 18% GST) directly upon EOD demat debit."

        return {
            "symbol": symbol,
            "side": side.upper(),
            "price": price,
            "quantity": quantity,
            "turnover": our_calc["turnover"],
            "is_consistent": is_consistent,
            "comparison_table": comparison_table,
            "differences": differences,
            "dp_charge_demat_note": dp_note,
            "notes": (
                "Charges match Upstox within 5 paise precision."
                if is_consistent
                else f"Differences observed in: {list(differences.keys())}."
            ),
        }


charges_engine = IndianChargesEngine()
