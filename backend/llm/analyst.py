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


aura_analyst = HumanoidAnalyst()
