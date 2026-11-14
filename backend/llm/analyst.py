"""AURA Institutional Humanoid AI Analyst (Bull, Bear & Judge Stages).

Performs qualitative auditing of quantitative candidates:
- Evaluates live news headlines and corporate filings
- Scans governance red flags (promoter pledge, auditor resignation, litigations)
- Conducts Bull vs Bear thesis debate
- Can VETO (REJECT) or REDUCE SIZE, but cannot modify mathematical entry/stop/target.
"""

from __future__ import annotations
import json
from typing import Dict, List, Any, Optional

from backend.core.config import PROJECT_ROOT
from backend.llm.router import llm_router

MISTAKE_RULES_FILE = PROJECT_ROOT / "data" / "mistake_rules.json"


AURA_SYSTEM_PROMPT = """You are AURA, an institutional Chief Investment Officer and quantitative audit judge for Indian equities (NSE/BSE).
Your task is to conduct a rigorous Bull vs. Bear debate on a screened stock setup and deliver a definitive verdict:
- APPROVED: Robust technical setup, clean governance, catalyst alignment.
- APPROVED_REDUCED_SIZE: Valid setup with identifiable headwind (e.g. macro volatility, near-term event risk).
- REJECTED: Red flags detected (governance issues, promoter selling, litigation, auditor resignation, earnings gap risk).
- NOT_AUDITED: Inconclusive qualitative data.

RULES:
1. Base your arguments ONLY on the provided indicators, market regime, corporate actions, and cited news items.
2. DO NOT hallucinate numbers, prices, or past performance.
3. Every news reference must cite the provided News ID.
4. Output MUST be valid JSON matching the exact schema requested.
"""


class HumanoidAnalyst:
    """AURA Institutional Analyst & Decision Auditor."""

    def audit_trade_candidate(
        self,
        symbol: str,
        setup_tag: str,
        entry_price: float,
        stop_loss: float,
        target_price: float,
        indicators: Dict[str, Any],
        ml_prediction: Dict[str, Any],
        macro_regime: Dict[str, Any],
        news_items: List[Dict[str, Any]],
        corporate_actions: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Audit trade setup through Bull, Bear, and Judge deliberation."""
        # Read dynamically learned failure archetypes from Mistake Lab
        failure_rules = []
        if MISTAKE_RULES_FILE.exists():
            try:
                with open(MISTAKE_RULES_FILE, "r") as f:
                    failure_rules = json.load(f).get("rules", [])
            except Exception:
                pass

        # Structure facts cleanly
        prompt_data = {
            "symbol": symbol,
            "setup_type": setup_tag,
            "entry_price_inr": entry_price,
            "stop_loss_inr": stop_loss,
            "target_price_inr": target_price,
            "risk_reward_ratio": "1:2 (ATR-based)",
            "ml_probability_target_hit": ml_prediction.get("win_probability_pct"),
            "expected_value_r": ml_prediction.get("ev_r"),
            "macro_regime": macro_regime.get("regime_label"),
            "india_vix": macro_regime.get("india_vix"),
            "technical_indicators": indicators,
            "corporate_actions_and_earnings": corporate_actions or {"status": "NO_EARNINGS_WITHIN_5_DAYS"},
            "live_news_disclosures": news_items,
            "systemic_mistake_rules_to_avoid": failure_rules[:3],
        }

        user_prompt = f"""Evaluate this NSE trade candidate and provide your Bull, Bear, and Judge ruling in strict JSON:

{json.dumps(prompt_data, indent=2)}

Required JSON Schema:
{{
  "verdict": "APPROVED" | "APPROVED_REDUCED_SIZE" | "REJECTED",
  "confidence_pct": float (0-100),
  "bull_arguments": [3 specific points],
  "bear_arguments": [3 specific points],
  "red_flags": [list of any red flags detected or empty list],
  "invalidation_criteria": "string",
  "plain_language_summary": "string"
}}
"""
        audit_res = llm_router.complete_audit(user_prompt, AURA_SYSTEM_PROMPT)
        return audit_res

    def conduct_loss_post_mortem(
        self,
        symbol: str,
        entry_price: float,
        exit_price: float,
        stop_loss: float,
        target_price: float,
        exit_reason: str,
        net_pnl_rupees: float,
        net_pnl_r: float,
        indicators: Optional[Dict[str, Any]] = None,
        macro_regime: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """Conduct an LLM-driven forensic post-mortem on a closed losing trade.

        Identifies the failure mode (e.g., False Breakout, Gap-Through-Stop, High VIX Trap,
        Sector Weakness, Stop Too Tight) and synthesizes a concrete guardrail for Mistake Lab.
        """
        system_prompt = (
            "You are AURA Chief Risk Auditor. Analyze this failed Indian equity trade and diagnose "
            "the precise structural flaw that caused the loss. Respond strictly in valid JSON with keys: "
            "'loss_category' (one of 'False Breakout', 'High VIX Trap', 'Sector Weakness', 'Gap-Through-Stop', 'Stop Too Tight'), "
            "'diagnosis_narrative' (2-3 sentences on failure mechanics), "
            "'proposed_guardrail' (1 concrete, quantitative rule to filter similar setups in future)."
        )

        facts = {
            "symbol": symbol,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "stop_loss": stop_loss,
            "target_price": target_price,
            "exit_reason": exit_reason,
            "loss_rupees": abs(net_pnl_rupees),
            "loss_r": abs(net_pnl_r),
            "indicators": indicators or {},
            "macro_regime": macro_regime or {},
        }

        user_prompt = f"Failed Trade Facts:\n{json.dumps(facts, indent=2)}"

        res = llm_router.complete_json_prompt(user_prompt, system_prompt)
        if (
            res
            and "loss_category" in res
            and "diagnosis_narrative" in res
            and "proposed_guardrail" in res
        ):
            return {
                "loss_category": str(res["loss_category"]),
                "diagnosis_narrative": str(res["diagnosis_narrative"]),
                "proposed_guardrail": str(res["proposed_guardrail"]),
            }

        # Deterministic fallback when LLM is unavailable
        inds = indicators or {}
        reg = macro_regime or {}
        vix = float(reg.get("india_vix", 14.0)) if isinstance(reg, dict) else 14.0
        rs = float(inds.get("rs_vs_nifty_20d", 0.0))
        vol_ratio = float(inds.get("vol_ratio_20d", 1.0))

        if exit_price < stop_loss or "gap" in exit_reason.lower():
            cat = "Gap-Through-Stop"
            diag = (
                f"{symbol} suffered an overnight adverse gap, opening below stop loss at ₹{exit_price:.2f} "
                f"(stop was ₹{stop_loss:.2f})."
            )
            guard = "Enforce max overnight gap threshold (2.5%) and avoid holding into earnings/major events."
        elif vix > 18.0:
            cat = "High VIX Trap"
            diag = (
                f"Trade entered during elevated macro volatility (India VIX {vix:.1f}). "
                f"Broader market chop triggered the stop loss prematurely."
            )
            guard = "Halve position size or raise minimum setup threshold when India VIX is above 18."
        elif rs < 0:
            cat = "Sector Weakness"
            diag = (
                f"{symbol} exhibited negative relative strength vs NIFTY 50 (RS: {rs:.2f}%), "
                f"causing it to underperform its sector peers and hit stop."
            )
            guard = "Require positive 20-day Relative Strength vs NIFTY before entering long swing setups."
        elif vol_ratio < 1.2:
            cat = "False Breakout"
            diag = (
                f"Breakout lacked institutional volume participation (volume ratio was only {vol_ratio:.2f}x). "
                f"Momentum quickly faded into a bull trap."
            )
            guard = "Require minimum 1.2x 20-day average volume confirmation on breakout entry."
        else:
            cat = "Stop Too Tight"
            diag = (
                f"{symbol} was stopped out at ₹{exit_price:.2f} due to normal intraday noise before trend continuation."
            )
            guard = "Maintain minimum stop distance of 1.5 * ATR(14) below recent swing swing low."

        return {
            "loss_category": cat,
            "diagnosis_narrative": diag,
            "proposed_guardrail": guard,
        }


aura_analyst = HumanoidAnalyst()
