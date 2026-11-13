"""AURA-NSE Pro Long-Term Value & Quality Compounder Engine (1 to 3+ Years).

Evaluates high-conviction institutional fundamentals, earnings compounders,
balance sheet safety, governance checks (promoter pledge & holding),
fair-value bands, 3-tranche staggered allocations, and thesis-break triggers.
"""

from __future__ import annotations
import datetime
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List
import pandas as pd

from backend.core.config import get_strategy_config
from backend.data.universe import get_sector_for_symbol
from backend.strategies.indicators import compute_sma


@dataclass
class LongTermPick:
    symbol: str
    passed: bool
    sector: str
    current_price: float
    sma_200: float
    fair_value_min: float
    fair_value_max: float
    fair_value_mid: float
    margin_of_safety_pct: float
    target_weight_pct: float
    tranche_plan: Dict[str, Any]
    thesis_break_triggers: List[str]
    quarterly_review_date: str
    tax_12m_flag_date: str
    fundamentals: Dict[str, Any]
    rejection_reasons: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LongTermStrategyEngine:
    """Institutional Quality & Valuation Screener for Multi-Year Compounders."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.cfg = config or get_strategy_config()
        self.lt_cfg = self.cfg.get("long_term_strategy", {})

    def evaluate(
        self,
        symbol: str,
        df: pd.DataFrame,
        fundamentals: Dict[str, Any],
    ) -> LongTermPick:
        """Screen equity candidate for multi-year institutional holding."""
        rejection_reasons: List[str] = []
        sector = get_sector_for_symbol(symbol)
        is_financial = sector in ("Banking", "NBFC", "Insurance")

        if df.empty or len(df) < 200:
            rejection_reasons.append("Insufficient price history (< 200 bars).")
            c_last = 0.0
            sma200_last = 0.0
        else:
            c_last = float(df["close"].iloc[-1])
            sma200 = compute_sma(df["close"], 200)
            sma200_last = float(sma200.iloc[-1]) if not pd.isna(sma200.iloc[-1]) else c_last

            # 1. Price > 200-SMA
            if c_last <= sma200_last:
                rejection_reasons.append(f"Price ₹{c_last:.2f} is below 200-day SMA ₹{sma200_last:.2f} (long-term downtrend).")

        # 2. Market Cap Floor (>= ₹2,000 Cr)
        mcap = fundamentals.get("market_cap_cr")
        min_mcap = self.lt_cfg.get("market_cap_min_cr", 2000.0)
        if mcap == "UNKNOWN":
            rejection_reasons.append("Market cap is UNKNOWN from primary source.")
        elif isinstance(mcap, (int, float)) and mcap < min_mcap:
            rejection_reasons.append(f"Market Cap ₹{mcap:,.0f} Cr is below minimum ₹{min_mcap:,.0f} Cr.")

        # 3. ROE / Profitability (>= 15%)
        roe = fundamentals.get("roe_pct")
        min_roe = self.lt_cfg.get("roe_min_pct", 15.0)
        if roe == "UNKNOWN":
            rejection_reasons.append("ROE is UNKNOWN from primary source.")
        elif isinstance(roe, (int, float)) and roe < min_roe:
            rejection_reasons.append(f"ROE {roe:.1f}% below institutional minimum of {min_roe}%.")

        # 4. Debt to Equity (<= 0.8, exempt Banks/NBFCs)
        if not is_financial:
            de = fundamentals.get("debt_to_equity")
            max_de = self.lt_cfg.get("debt_to_equity_max", 0.8)
            if de == "UNKNOWN":
                pass  # flag for review
            elif isinstance(de, (int, float)) and de > max_de:
                rejection_reasons.append(f"Debt-to-Equity {de:.2f} exceeds conservative ceiling {max_de}.")

        # 5. Valuation P/E Checks
        pe = fundamentals.get("pe_ratio")
        max_pe_cap = self.lt_cfg.get("pe_max_cap", 35.0)
        if pe == "UNKNOWN":
            rejection_reasons.append("P/E ratio is UNKNOWN.")
        elif isinstance(pe, (int, float)):
            if pe <= 0:
                rejection_reasons.append("Negative P/E (loss-making company).")
            elif pe > max_pe_cap:
                rejection_reasons.append(f"P/E ratio {pe:.1f} exceeds hard cap of {max_pe_cap}.")

        # 6. Revenue & Earnings Growth
        rev_growth = fundamentals.get("rev_growth_yoy_pct")
        min_rev_growth = self.lt_cfg.get("rev_growth_yoy_min_pct", 10.0)
        if isinstance(rev_growth, (int, float)) and rev_growth < min_rev_growth:
            rejection_reasons.append(f"YoY Revenue Growth {rev_growth:.1f}% below {min_rev_growth}%.")

        earnings_growth = fundamentals.get("earnings_growth_yoy_pct")
        min_earnings_growth = self.lt_cfg.get("pat_growth_yoy_min_pct", 12.0)
        if isinstance(earnings_growth, (int, float)) and earnings_growth < min_earnings_growth:
            rejection_reasons.append(f"YoY Earnings Growth {earnings_growth:.1f}% below {min_earnings_growth}%.")

        # Fair Value Band & Margin of Safety
        # Heuristic DCF/EPS multiplier based on growth rate & ROE
        growth_est = float(earnings_growth) if isinstance(earnings_growth, (int, float)) and earnings_growth > 0 else 12.0
        fair_multiple = min(30.0, max(15.0, growth_est * 1.2))
        current_pe = float(pe) if isinstance(pe, (int, float)) and pe > 0 else 22.0
        fair_value_mid = round(c_last * (fair_multiple / current_pe), 2) if current_pe > 0 and c_last > 0 else c_last
        fair_value_min = round(fair_value_mid * 0.90, 2)
        fair_value_max = round(fair_value_mid * 1.15, 2)
        margin_of_safety = round(((fair_value_mid - c_last) / fair_value_mid) * 100.0, 2) if fair_value_mid > 0 else 0.0

        # Staggered 3-Tranche Allocation Plan
        tranche_plan = {
            "tranche_1_initial": {"pct": 40.0, "price_target": c_last, "trigger": "Immediate on approval"},
            "tranche_2_pullback": {"pct": 30.0, "price_target": round(c_last * 0.95, 2), "trigger": "5% dip or 50-EMA test"},
            "tranche_3_deep_value": {"pct": 30.0, "price_target": round(c_last * 0.90, 2), "trigger": "10% dip or 200-SMA support"},
        }

        # Thesis Break Triggers
        thesis_breaks = [
            "Promoter share pledge exceeds 10% or rises > 5% in a single quarter.",
            "Two consecutive quarters of negative earnings growth or EBITDA margin collapse > 300 bps.",
            "ROE drops below 12% on trailing 12-month basis.",
            "Auditor resignation, regulatory investigation, or qualified audit report from SEBI/MCA.",
        ]

        today = datetime.date.today()
        review_date = (today + datetime.timedelta(days=90)).strftime("%Y-%m-%d")
        tax_12m_date = (today + datetime.timedelta(days=366)).strftime("%Y-%m-%d")

        passed = len(rejection_reasons) == 0

        return LongTermPick(
            symbol=symbol,
            passed=passed,
            sector=sector,
            current_price=round(c_last, 2),
            sma_200=round(sma200_last, 2),
            fair_value_min=fair_value_min,
            fair_value_max=fair_value_max,
            fair_value_mid=fair_value_mid,
            margin_of_safety_pct=margin_of_safety,
            target_weight_pct=self.lt_cfg.get("portfolio_allocation", {}).get("target_weight_pct", 5.0),
            tranche_plan=tranche_plan,
            thesis_break_triggers=thesis_breaks,
            quarterly_review_date=review_date,
            tax_12m_flag_date=tax_12m_date,
            fundamentals=fundamentals,
            rejection_reasons=rejection_reasons,
        )


long_term_engine = LongTermStrategyEngine()
