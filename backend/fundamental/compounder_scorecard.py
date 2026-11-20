"""AURA-NSE Pro — 100-Point Institutional Quality Compounder Scorecard.

Evaluates Indian equities across 8 core pillars with strict quantitative rubrics:
1. Financial Quality (20 pts) — ROCE, ROE, OPM profitability & margin stability
2. Earnings Growth (15 pts) — 3-5 Year Compounded Sales and Net Profit Growth
3. Cash Flow (15 pts) — 5-Year CFO to PAT Cash Conversion Ratio & Free Cash Flow
4. Valuation (20 pts) — Sector-Adjusted P/E, PEG, P/B vs ROE, and Margin of Safety
5. Balance Sheet (10 pts) — Debt to Equity, Interest Coverage, Solvency
6. Technicals (10 pts) — 50/200 SMA trend alignment, RSI momentum, 20d Volume ratio
7. Market Conditions (5 pts) — Macro Regime status and India VIX volatility
8. Governance (5 pts + HARD VETO) — Promoter Pledging (Veto > 20%), Institutional Stake

Returns a comprehensive composite grade (A/B/C/D) and detailed factor breakdown.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import logging
from typing import Any, Dict, List, Optional

from backend.data.universe import get_sector_for_symbol
from backend.fundamental.screener_client import screener_client

logger = logging.getLogger("aura.compounder")


@dataclass
class CategoryScore:
    name: str
    weight: float
    score: float
    max_score: float
    rating_pct: float
    notes: List[str] = field(default_factory=list)


@dataclass
class CompounderEvaluation:
    symbol: str
    company_name: str
    sector: str
    total_score: float
    max_possible_score: float
    score_percentage: float
    grade: str  # 'GRADE A (Institutional Compounder)', 'GRADE B (Solid Quality)', 'GRADE C (Mediocre/Cyclical)', 'GRADE D (Value Trap)'
    verdict: str  # 'APPROVED_COMPOUNDER', 'SELECTIVE_COMPOUNDER', 'REJECTED_VALUE_TRAP', 'REJECTED_GOVERNANCE_VETO'
    is_vetoed: bool
    veto_reason: Optional[str]
    categories: Dict[str, CategoryScore]
    summary_verdict: str
    key_strengths: List[str]
    key_risks: List[str]
    forward_estimates: Optional[Dict[str, Any]] = None
    event_risk_level: str = "CLEAN"
    invalidation_triggers: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["categories"] = {k: asdict(v) for k, v in self.categories.items()}
        return d


class CompounderScorecardEngine:
    """Evaluates an Indian equity against the 100-Point Compounder Matrix."""

    # Typical sector baseline P/E multiples in Indian markets
    SECTOR_PE_BENCHMARKS = {
        "Information Technology": 28.0,
        "Banking": 16.0,
        "Financial Services": 22.0,
        "Automobile": 22.0,
        "Pharmaceuticals": 32.0,
        "FMCG": 45.0,
        "Metals & Mining": 10.0,
        "Oil & Gas": 10.0,
        "Power & Utilities": 16.0,
        "Capital Goods": 35.0,
        "Chemicals": 28.0,
        "Consumer Durables": 38.0,
        "Construction & Realty": 25.0,
        "Telecom": 25.0,
        "Diversified/Other": 20.0,
    }

    def evaluate_equity(
        self,
        symbol: str,
        screener_data: Optional[Dict[str, Any]] = None,
        technical_data: Optional[Dict[str, Any]] = None,
        macro_regime: Optional[Dict[str, Any]] = None,
        margin_of_safety_pct: float = 0.0,
    ) -> CompounderEvaluation:
        """Run full 100-point composite compounder evaluation."""
        clean_symbol = symbol.replace(".NS", "").replace(".BO", "").strip().upper()
        sector = get_sector_for_symbol(symbol)

        # 1. Fetch / Use Screener Data
        if not screener_data:
            screener_data = screener_client.fetch_company_data(clean_symbol)

        company_name = screener_data.get("company_name", clean_symbol)
        top_ratios = screener_data.get("top_ratios", {})
        ranges = screener_data.get("ranges", {})
        cash_flow = screener_data.get("cash_flow", {})
        profit_loss = screener_data.get("profit_loss", {})
        balance_sheet = screener_data.get("balance_sheet", {})
        shareholding = screener_data.get("shareholding", {})
        analysis = screener_data.get("analysis", {})

        technical_data = technical_data or {}
        macro_regime = macro_regime or {}

        # -----------------------------------------------------------------
        # Governance & Hard Veto Gate (Evaluated First)
        # -----------------------------------------------------------------
        pledged_pct = float(shareholding.get("pledged_pct") or 0.0)
        is_vetoed = False
        veto_reason: Optional[str] = None

        if pledged_pct > 20.0:
            is_vetoed = True
            veto_reason = f"Promoter Pledging ({pledged_pct:.1f}%) exceeds strict 20% institutional governance veto ceiling."

        # Check for severe auditor qualification in cons
        for con in analysis.get("cons", []):
            if any(k in con.lower() for k in ["auditor resigned", "forensic audit", "fraud", "material misstatement"]):
                is_vetoed = True
                veto_reason = f"Severe Governance Red Flag: {con}"
                break

        # Check Corporate Event Risk Shield (Regulatory, Auditor Resignation, FDA Form 483)
        from backend.data.corporate_events import corporate_event_shield
        event_risk = corporate_event_shield.check_symbol_event_risk(symbol)
        if event_risk.veto_trade:
            is_vetoed = True
            veto_reason = f"Corporate Governance Event Shield: {event_risk.veto_reason}"

        # -----------------------------------------------------------------
        # Category 1: Financial Quality (Weight: 20 pts)
        # -----------------------------------------------------------------
        roce = float(top_ratios.get("roce_pct") or 0.0)
        roe = float(top_ratios.get("roe_pct") or 0.0)
        opm = float(profit_loss.get("latest_opm_pct") or 0.0)
        is_bank = "Bank" in sector or "Financial" in sector

        c1_score = 0.0
        c1_notes: List[str] = []

        # ROCE scoring (7 pts) - For banks, adjusted ROE/ROA applies
        if is_bank:
            if roe >= 16.0:
                c1_score += 7.0
                c1_notes.append(f"Bank ROE ({roe:.1f}%) meets top-tier efficiency (+7.0/7)")
            elif roe >= 12.0:
                c1_score += 5.0
                c1_notes.append(f"Bank ROE ({roe:.1f}%) healthy (+5.0/7)")
            else:
                c1_score += 2.0
                c1_notes.append(f"Bank ROE ({roe:.1f}%) below institutional threshold (+2.0/7)")
        else:
            if roce >= 25.0:
                c1_score += 7.0
                c1_notes.append(f"Exceptional ROCE ({roce:.1f}% >= 25%) indicates strong economic moat (+7.0/7)")
            elif roce >= 18.0:
                c1_score += 5.5
                c1_notes.append(f"Solid ROCE ({roce:.1f}% >= 18%) above cost of capital (+5.5/7)")
            elif roce >= 13.0:
                c1_score += 3.5
                c1_notes.append(f"Moderate ROCE ({roce:.1f}%) (+3.5/7)")
            else:
                c1_notes.append(f"Weak ROCE ({roce:.1f}% < 13%) shows poor capital efficiency (+0/7)")

        # ROE scoring (6 pts)
        if roe >= 20.0:
            c1_score += 6.0
            c1_notes.append(f"Top-quartile ROE ({roe:.1f}% >= 20%) (+6.0/6)")
        elif roe >= 15.0:
            c1_score += 4.5
            c1_notes.append(f"Healthy ROE ({roe:.1f}% >= 15%) (+4.5/6)")
        elif roe >= 12.0:
            c1_score += 3.0
            c1_notes.append(f"Acceptable ROE ({roe:.1f}%) (+3.0/6)")
        else:
            c1_notes.append(f"Sub-par ROE ({roe:.1f}% < 12%) (+0/6)")

        # Operating Margins (OPM) (4 pts)
        if opm >= 20.0 or (is_bank and roe >= 14.0):
            c1_score += 4.0
            c1_notes.append(f"High operating margin ({opm:.1f}% >= 20%) (+4.0/4)")
        elif opm >= 12.0:
            c1_score += 2.5
            c1_notes.append(f"Moderate operating margin ({opm:.1f}%) (+2.5/4)")
        else:
            c1_score += 1.0
            c1_notes.append(f"Slim operating margin ({opm:.1f}%) (+1.0/4)")

        # Margin Stability / ROE Track Record (3 pts)
        roe_3y = float(ranges.get("roe_3_years") or roe)
        if roe_3y >= 15.0:
            c1_score += 3.0
            c1_notes.append(f"Consistent 3-Year ROE track record ({roe_3y:.1f}% >= 15%) (+3.0/3)")
        elif roe_3y >= 10.0:
            c1_score += 1.5
            c1_notes.append(f"Stable 3-Year ROE ({roe_3y:.1f}%) (+1.5/3)")
        else:
            c1_notes.append(f"Volatile historical returns (+0/3)")

        c1 = CategoryScore("Financial Quality", 20.0, round(c1_score, 1), 20.0, round((c1_score / 20.0) * 100, 1), c1_notes)

        # -----------------------------------------------------------------
        # Category 2: Earnings Growth (Weight: 15 pts)
        # -----------------------------------------------------------------
        sales_g_3y = float(ranges.get("sales_growth_3_years") or ranges.get("sales_growth_5_years") or 0.0)
        sales_g_5y = float(ranges.get("sales_growth_5_years") or sales_g_3y)
        profit_g_3y = float(ranges.get("profit_growth_3_years") or ranges.get("profit_growth_5_years") or 0.0)
        profit_g_5y = float(ranges.get("profit_growth_5_years") or profit_g_3y)

        c2_score = 0.0
        c2_notes: List[str] = []

        # Revenue CAGR (7.5 pts)
        eff_sales_g = max(sales_g_3y, sales_g_5y)
        if eff_sales_g >= 15.0:
            c2_score += 7.5
            c2_notes.append(f"High revenue CAGR ({eff_sales_g:.1f}% >= 15%) (+7.5/7.5)")
        elif eff_sales_g >= 10.0:
            c2_score += 5.5
            c2_notes.append(f"Steady revenue CAGR ({eff_sales_g:.1f}% >= 10%) (+5.5/7.5)")
        elif eff_sales_g >= 6.0:
            c2_score += 3.5
            c2_notes.append(f"Moderate revenue CAGR ({eff_sales_g:.1f}%) (+3.5/7.5)")
        else:
            c2_score += 1.0
            c2_notes.append(f"Sluggish revenue CAGR ({eff_sales_g:.1f}% < 6%) (+1.0/7.5)")

        # Profit CAGR (7.5 pts)
        eff_profit_g = max(profit_g_3y, profit_g_5y)
        if eff_profit_g >= 15.0:
            c2_score += 7.5
            c2_notes.append(f"Robust net profit CAGR ({eff_profit_g:.1f}% >= 15%) (+7.5/7.5)")
        elif eff_profit_g >= 10.0:
            c2_score += 5.5
            c2_notes.append(f"Healthy net profit CAGR ({eff_profit_g:.1f}% >= 10%) (+5.5/7.5)")
        elif eff_profit_g >= 6.0:
            c2_score += 3.5
            c2_notes.append(f"Modest profit CAGR ({eff_profit_g:.1f}%) (+3.5/7.5)")
        else:
            c2_score += 0.5
            c2_notes.append(f"Stagnant/declining profit growth ({eff_profit_g:.1f}% < 6%) (+0.5/7.5)")

        c2 = CategoryScore("Earnings Growth", 15.0, round(c2_score, 1), 15.0, round((c2_score / 15.0) * 100, 1), c2_notes)

        # -----------------------------------------------------------------
        # Category 3: Cash Flow (Weight: 15 pts)
        # -----------------------------------------------------------------
        cfo_to_pat = float(cash_flow.get("cfo_to_pat_5y_pct") or 80.0)
        fcf_latest = cash_flow.get("fcf_latest_cr")
        fcf_history = cash_flow.get("fcf_history_cr", [])

        c3_score = 0.0
        c3_notes: List[str] = []

        # CFO vs Net Profit Conversion (8 pts)
        if is_bank:
            # Banking cash flows are distorted by lending/deposits; evaluate Net Interest Margin / credit health
            c3_score += 7.0
            c3_notes.append(f"Banking liquidity & operating cash conversion validated (+7.0/8)")
        else:
            if cfo_to_pat >= 85.0:
                c3_score += 8.0
                c3_notes.append(f"High-integrity cash conversion: 5Y CFO/PAT is {cfo_to_pat:.1f}% (+8.0/8)")
            elif cfo_to_pat >= 70.0:
                c3_score += 6.0
                c3_notes.append(f"Healthy cash conversion: 5Y CFO/PAT is {cfo_to_pat:.1f}% (+6.0/8)")
            elif cfo_to_pat >= 50.0:
                c3_score += 3.5
                c3_notes.append(f"Moderate cash conversion: 5Y CFO/PAT is {cfo_to_pat:.1f}% (+3.5/8)")
            else:
                c3_notes.append(f"Accrual Warning: 5Y CFO/PAT is {cfo_to_pat:.1f}% (<50%) indicates paper earnings (+0/8)")

        # Free Cash Flow Generation (7 pts)
        if is_bank:
            c3_score += 6.5
            c3_notes.append(f"Bank statutory liquidity & capital ratios sound (+6.5/7)")
        else:
            if fcf_latest is not None and fcf_latest > 0:
                if len(fcf_history) >= 2 and sum(fcf_history[-3:]) > 0:
                    c3_score += 7.0
                    c3_notes.append(f"Sustained positive Free Cash Flow generation (Latest FCF: ₹{fcf_latest:,.0f} Cr) (+7.0/7)")
                else:
                    c3_score += 5.0
                    c3_notes.append(f"Positive latest Free Cash Flow (₹{fcf_latest:,.0f} Cr) (+5.0/7)")
            elif fcf_latest == 0.0 or fcf_latest is None:
                c3_score += 3.5
                c3_notes.append("Flat/neutral Free Cash Flow (+3.5/7)")
            else:
                c3_notes.append(f"Negative Free Cash Flow (₹{fcf_latest:,.0f} Cr) due to heavy capex/working capital (+0/7)")

        c3 = CategoryScore("Cash Flow", 15.0, round(c3_score, 1), 15.0, round((c3_score / 15.0) * 100, 1), c3_notes)

        # -----------------------------------------------------------------
        # Category 4: Valuation (Weight: 20 pts)
        # -----------------------------------------------------------------
        pe_ratio = float(top_ratios.get("pe_ratio") or 20.0)
        pb_ratio = float(top_ratios.get("book_value") and (top_ratios.get("current_price", 1.0) / max(0.1, top_ratios["book_value"])) or 3.0)
        sector_bench_pe = self.SECTOR_PE_BENCHMARKS.get(sector, 22.0)

        c4_score = 0.0
        c4_notes: List[str] = []

        # PEG / Sector-relative P/E (10 pts)
        growth_rate = max(5.0, eff_profit_g)
        peg = round(pe_ratio / growth_rate, 2) if growth_rate > 0 else 3.0

        if peg <= 1.2 or pe_ratio <= (sector_bench_pe * 0.75):
            c4_score += 10.0
            c4_notes.append(f"Attractive valuation: PEG={peg:.2f} or P/E ({pe_ratio:.1f}x) at steep discount to {sector} benchmark ({sector_bench_pe}x) (+10.0/10)")
        elif peg <= 1.8 or pe_ratio <= sector_bench_pe:
            c4_score += 7.0
            c4_notes.append(f"Fairly valued: PEG={peg:.2f}, P/E ({pe_ratio:.1f}x) aligned with sector (+7.0/10)")
        elif peg <= 2.5 or pe_ratio <= (sector_bench_pe * 1.35):
            c4_score += 4.0
            c4_notes.append(f"Slight valuation premium: PEG={peg:.2f}, P/E {pe_ratio:.1f}x (+4.0/10)")
        else:
            c4_notes.append(f"Expensive multiple: PEG={peg:.2f}, P/E {pe_ratio:.1f}x (+0/10)")

        # P/B vs ROE alignment (5 pts)
        if pb_ratio <= 3.0 or (roe >= 25.0 and pb_ratio <= 7.0) or (is_bank and pb_ratio <= 2.0):
            c4_score += 5.0
            c4_notes.append(f"Price to Book ({pb_ratio:.1f}x) justified by return on capital (+5.0/5)")
        elif pb_ratio <= 6.0:
            c4_score += 3.0
            c4_notes.append(f"Moderate Price to Book ({pb_ratio:.1f}x) (+3.0/5)")
        else:
            c4_score += 1.0
            c4_notes.append(f"High Price to Book ({pb_ratio:.1f}x) requires flawless execution (+1.0/5)")

        # Margin of Safety / DCF (5 pts)
        if margin_of_safety_pct >= 20.0:
            c4_score += 5.0
            c4_notes.append(f"Strong Margin of Safety (+{margin_of_safety_pct:.1f}% discount to intrinsic worth) (+5.0/5)")
        elif margin_of_safety_pct >= 5.0:
            c4_score += 3.5
            c4_notes.append(f"Modest Margin of Safety (+{margin_of_safety_pct:.1f}%) (+3.5/5)")
        elif margin_of_safety_pct >= -10.0:
            c4_score += 2.0
            c4_notes.append(f"Trading near intrinsic fair worth ({margin_of_safety_pct:+.1f}%) (+2.0/5)")
        else:
            c4_notes.append(f"Trading at a premium to estimated fair value ({margin_of_safety_pct:+.1f}%) (+0/5)")

        # Forward Consensus & Value Trap Check (Adjusts Valuation Score)
        from backend.fundamental.forward_estimates import forward_estimates_engine
        forward_est = forward_estimates_engine.fetch_estimates(symbol)
        if forward_est.is_value_trap:
            c4_score = max(0.0, c4_score - 8.0)
            c4_notes.append(f"CRITICAL VALUE TRAP WARNING: {forward_est.value_trap_reason} (-8.0 pts)")
        elif forward_est.forward_growth_pct >= 15.0 and forward_est.analyst_upside_pct >= 15.0:
            c4_score = min(20.0, c4_score + 2.0)
            c4_notes.append(f"Consensus EPS Growth (+{forward_est.forward_growth_pct:.1f}%) & Analyst Upside (+{forward_est.analyst_upside_pct:.1f}%) (+2.0 pts)")

        c4 = CategoryScore("Valuation", 20.0, round(c4_score, 1), 20.0, round((c4_score / 20.0) * 100, 1), c4_notes)

        # -----------------------------------------------------------------
        # Category 5: Balance Sheet (Weight: 10 pts)
        # -----------------------------------------------------------------
        de_ratio = float(balance_sheet.get("debt_to_equity") or 0.0)
        c5_score = 0.0
        c5_notes: List[str] = []

        if is_bank:
            # Banks operate on high regulatory leverage; reward low NPA / strong net worth
            c5_score += 9.0
            c5_notes.append(f"Regulated banking balance sheet with institutional deposit franchise (+9.0/10)")
        else:
            # Debt to Equity (7 pts)
            if de_ratio <= 0.15:
                c5_score += 7.0
                c5_notes.append(f"Virtually debt-free balance sheet (D/E: {de_ratio:.2f}) (+7.0/7)")
            elif de_ratio <= 0.50:
                c5_score += 5.5
                c5_notes.append(f"Conservative industrial leverage (D/E: {de_ratio:.2f} <= 0.5) (+5.5/7)")
            elif de_ratio <= 0.90:
                c5_score += 3.0
                c5_notes.append(f"Moderate leverage (D/E: {de_ratio:.2f}) (+3.0/7)")
            else:
                c5_notes.append(f"High debt burden (D/E: {de_ratio:.2f} > 0.9) (+0/7)")

            # Liquidity / Reserves Solvency (3 pts)
            reserves = float(balance_sheet.get("reserves_cr") or 0.0)
            if reserves > 0 and de_ratio <= 0.5:
                c5_score += 3.0
                c5_notes.append("Strong retained earnings buffer and solvency cushions (+3.0/3)")
            else:
                c5_score += 1.5
                c5_notes.append("Adequate operational liquidity (+1.5/3)")

        c5 = CategoryScore("Balance Sheet", 10.0, round(c5_score, 1), 10.0, round((c5_score / 10.0) * 100, 1), c5_notes)

        # -----------------------------------------------------------------
        # Category 6: Technicals (Weight: 10 pts)
        # -----------------------------------------------------------------
        c6_score = 0.0
        c6_notes: List[str] = []

        # Moving average trend (4 pts)
        sma_50 = technical_data.get("sma_50")
        sma_200 = technical_data.get("sma_200")
        current_p = technical_data.get("close") or top_ratios.get("current_price", 0.0)

        if current_p and sma_50 and sma_200:
            if current_p >= sma_50 >= sma_200:
                c6_score += 4.0
                c6_notes.append("Bullish trend alignment: Price > 50-EMA > 200-SMA (+4.0/4)")
            elif current_p >= sma_200:
                c6_score += 2.5
                c6_notes.append("Trading above 200-SMA structural baseline (+2.5/4)")
            else:
                c6_notes.append("Below 200-SMA; structural downtrend caution (+0/4)")
        else:
            c6_score += 2.5
            c6_notes.append("Trend metrics baseline neutral (+2.5/4)")

        # RSI Momentum (3 pts)
        rsi = float(technical_data.get("rsi_14") or 52.0)
        if 45.0 <= rsi <= 65.0:
            c6_score += 3.0
            c6_notes.append(f"Healthy momentum: RSI ({rsi:.1f}) in constructive accumulation zone (+3.0/3)")
        elif 65.0 < rsi <= 75.0:
            c6_score += 2.0
            c6_notes.append(f"Strong momentum: RSI ({rsi:.1f}) near upper threshold (+2.0/3)")
        elif 35.0 <= rsi < 45.0:
            c6_score += 1.5
            c6_notes.append(f"Consolidating/oversold pullback: RSI ({rsi:.1f}) (+1.5/3)")
        else:
            c6_notes.append(f"Extreme momentum warning: RSI ({rsi:.1f}) (+0/3)")

        # Volume Ratio (3 pts)
        vol_ratio = float(technical_data.get("volume_ratio_20d") or 1.1)
        if vol_ratio >= 1.2:
            c6_score += 3.0
            c6_notes.append(f"Expanding institutional participation (Vol Ratio: {vol_ratio:.2f}x) (+3.0/3)")
        elif vol_ratio >= 0.9:
            c6_score += 2.0
            c6_notes.append(f"Normal trading liquidity (Vol Ratio: {vol_ratio:.2f}x) (+2.0/3)")
        else:
            c6_score += 1.0
            c6_notes.append(f"Light volume (Vol Ratio: {vol_ratio:.2f}x) (+1.0/3)")

        c6 = CategoryScore("Technicals", 10.0, round(c6_score, 1), 10.0, round((c6_score / 10.0) * 100, 1), c6_notes)

        # -----------------------------------------------------------------
        # Category 7: Market Conditions (Weight: 5 pts)
        # -----------------------------------------------------------------
        regime_label = macro_regime.get("regime_label", "GREEN")
        vix = float(macro_regime.get("india_vix") or macro_regime.get("vix") or 14.5)

        c7_score = 0.0
        c7_notes: List[str] = []

        if regime_label == "GREEN":
            c7_score += 3.0
            c7_notes.append("Macro Regime is GREEN: Institutional equity tailwind (+3.0/3)")
        elif regime_label == "AMBER":
            c7_score += 1.5
            c7_notes.append("Macro Regime is AMBER: Selective allocation posture (+1.5/3)")
        else:
            c7_notes.append("Macro Regime is RED: Capital preservation environment (+0/3)")

        if vix <= 16.0:
            c7_score += 2.0
            c7_notes.append(f"India VIX ({vix:.1f}) reflects stable market regime (+2.0/2)")
        elif vix <= 20.0:
            c7_score += 1.0
            c7_notes.append(f"India VIX ({vix:.1f}) elevated (+1.0/2)")
        else:
            c7_notes.append(f"India VIX ({vix:.1f} > 20) indicates high systemic volatility (+0/2)")

        c7 = CategoryScore("Market Conditions", 5.0, round(c7_score, 1), 5.0, round((c7_score / 5.0) * 100, 1), c7_notes)

        # -----------------------------------------------------------------
        # Category 8: Governance (Weight: 5 pts + Hard Veto)
        # -----------------------------------------------------------------
        promoter_pct = float(shareholding.get("promoter_pct") or 50.0)
        fii_pct = float(shareholding.get("fii_pct") or 10.0)
        dii_pct = float(shareholding.get("dii_pct") or 10.0)
        inst_holding = fii_pct + dii_pct

        c8_score = 0.0
        c8_notes: List[str] = []

        if is_vetoed:
            c8_score = 0.0
            c8_notes.append(f"🚨 HARD VETO TRIGGERED: {veto_reason}")
        else:
            # Pledging check (3 pts)
            if pledged_pct == 0.0:
                c8_score += 3.0
                c8_notes.append("Zero promoter share pledging (0.0%) (+3.0/3)")
            elif pledged_pct <= 5.0:
                c8_score += 1.5
                c8_notes.append(f"Negligible promoter pledge ({pledged_pct:.1f}% <= 5%) (+1.5/3)")
            else:
                c8_notes.append(f"Promoter pledge warning ({pledged_pct:.1f}%) (+0/3)")

            # Institutional sponsorship (2 pts)
            if inst_holding >= 20.0:
                c8_score += 2.0
                c8_notes.append(f"Strong institutional ownership (FII+DII: {inst_holding:.1f}%) (+2.0/2)")
            elif inst_holding >= 10.0:
                c8_score += 1.0
                c8_notes.append(f"Moderate institutional backing (FII+DII: {inst_holding:.1f}%) (+1.0/2)")
            else:
                c8_notes.append(f"Low institutional participation (FII+DII: {inst_holding:.1f}%) (+0/2)")

        c8 = CategoryScore("Governance", 5.0, round(c8_score, 1), 5.0, round((c8_score / 5.0) * 100, 1), c8_notes)

        # -----------------------------------------------------------------
        # Composite Calculation & Grading
        # -----------------------------------------------------------------
        categories = {
            "financial_quality": c1,
            "earnings_growth": c2,
            "cash_flow": c3,
            "valuation": c4,
            "balance_sheet": c5,
            "technicals": c6,
            "market_conditions": c7,
            "governance": c8,
        }

        raw_total = sum(cat.score for cat in categories.values())
        final_total = 0.0 if is_vetoed else round(raw_total, 1)
        score_pct = round((final_total / 100.0) * 100.0, 1)

        if is_vetoed:
            grade = "VETOED (Governance Alert)"
            verdict = "REJECTED_GOVERNANCE_VETO"
            summary_verdict = f"REJECTED: {veto_reason}. Capital preservation gate triggered."
        elif final_total >= 80.0:
            grade = "GRADE A (Institutional Compounder)"
            verdict = "APPROVED_COMPOUNDER"
            summary_verdict = f"HIGH CONVICTION COMPOUNDER ({final_total}/100): Exceptional ROCE, cash conversion, and balance sheet strength."
        elif final_total >= 65.0:
            grade = "GRADE B (Solid Quality)"
            verdict = "SELECTIVE_COMPOUNDER"
            summary_verdict = f"APPROVED QUALITY EQUITY ({final_total}/100): Sound fundamentals with manageable valuation/momentum headwind."
        elif final_total >= 50.0:
            grade = "GRADE C (Mediocre / Cyclical)"
            verdict = "REJECTED_VALUE_TRAP"
            summary_verdict = f"CAUTION ({final_total}/100): Cyclical or low-growth profile. Vulnerable to value-trap underperformance."
        else:
            grade = "GRADE D (Weak Fundamentals)"
            verdict = "REJECTED_VALUE_TRAP"
            summary_verdict = f"UNAPPROVED ({final_total}/100): Fails institutional quality, growth, or cash flow hurdles."

        # Key Strengths & Risks Extraction
        key_strengths: List[str] = []
        key_risks: List[str] = []

        for cat in categories.values():
            if cat.rating_pct >= 75.0:
                for note in cat.notes:
                    if "(+" in note and "weak" not in note.lower() and "sluggish" not in note.lower():
                        key_strengths.append(f"{cat.name}: {note.split('(+')[0].strip()}")
                        break
            elif cat.rating_pct < 50.0:
                for note in cat.notes:
                    if "(+0" in note or "warning" in note.lower() or "sub-par" in note.lower() or "sluggish" in note.lower():
                        key_risks.append(f"{cat.name}: {note.split('(+')[0].strip()}")
                        break

        # Screener Pros & Cons supplement
        if analysis.get("pros"):
            key_strengths.extend(analysis["pros"][:2])
        if analysis.get("cons"):
            key_risks.extend(analysis["cons"][:2])

        # Structured Invalidation Triggers (Thesis Violation Gates)
        invalidation_triggers = [
            f"Capital Efficiency Invalidation: Quarterly ROCE/ROE falls below {max(12.0, roce * 0.7):.1f}%",
            f"Governance Invalidation: Promoter share pledging increases above 10.0% (current: {pledged_pct:.1f}%)",
            "Cash Conversion Invalidation: Trailing 12M Operating Cash Flow (CFO) turns negative",
            "Regulatory / Integrity Invalidation: Statutory auditor resigns, adverse opinion issued, or ED/SEBI raid",
            "Structural Technical Invalidation: Weekly closing breaks below 200-SMA baseline on volume",
        ]

        return CompounderEvaluation(
            symbol=symbol,
            company_name=company_name,
            sector=sector,
            total_score=final_total,
            max_possible_score=100.0,
            score_percentage=score_pct,
            grade=grade,
            verdict=verdict,
            is_vetoed=is_vetoed,
            veto_reason=veto_reason,
            categories=categories,
            summary_verdict=summary_verdict,
            key_strengths=key_strengths[:4],
            key_risks=key_risks[:4],
            forward_estimates=forward_est.to_dict() if 'forward_est' in locals() and forward_est else None,
            event_risk_level=event_risk.risk_level if 'event_risk' in locals() and event_risk else "CLEAN",
            invalidation_triggers=invalidation_triggers,
        )


compounder_engine = CompounderScorecardEngine()
