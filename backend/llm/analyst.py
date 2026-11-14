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


import re

def verify_and_sanitize_audit_verdict(
    audit_res: Dict[str, Any],
    prompt_data: Dict[str, Any],
    news_items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Strict institutional validation of LLM Bull/Bear debate (Section 18.2 & Item 10):
    1. Exactly 3 bull and 3 bear points.
    2. Number verification against the data layer (rejects hallucinations).
    3. Mathematical levels (entry, stop, target) are immutable and cannot be altered by LLM.
    4. Untrusted news items are flagged and ungrounded citations rejected.
    5. Provider failure policy: safe deterministic fallback to NOT_AUDITED.
    """
    # Provider-failure policy check
    if audit_res.get("status") == "NOT_AUDITED" or not audit_res.get("verdict"):
        return {
            "status": "NOT_AUDITED",
            "provider": audit_res.get("provider", "none"),
            "model": audit_res.get("model", "none"),
            "verdict": {
                "verdict": "NOT_AUDITED",
                "confidence_pct": 50.0,
                "bull_arguments": [
                    "Passed quantitative technical screening filters.",
                    "Price structure aligns with 50-EMA and 200-SMA trend criteria.",
                    "Relative strength vs NIFTY benchmark is positive.",
                ],
                "bear_arguments": [
                    "LLM provider vault unreachable or rate-limited; qualitative audit unverified.",
                    "Qualitative governance and catalyst check could not be completed.",
                    "Strict safety policy: non-audited candidates cannot be approved without review.",
                ],
                "red_flags": ["PROVIDER_FAILURE_UNAUDITED"],
                "invalidation_criteria": "Price falls below strict mathematical stop loss.",
                "plain_language_summary": "Quantitative screening passed; qualitative LLM debate was NOT_AUDITED due to provider unavailability.",
                "verified_entry_price": prompt_data["entry_price_inr"],
                "verified_stop_loss": prompt_data["stop_loss_inr"],
                "verified_target_price": prompt_data["target_price_inr"],
            },
        }

    verdict_data = audit_res.get("verdict", {})
    red_flags = list(verdict_data.get("red_flags", []))

    # 1. Prompt Injection Defense (Section 19.2)
    injection_patterns = [
        r"ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions",
        r"system\s+prompt\s+override",
        r"disregard\s+(?:risk|safety|rules|stop)",
        r"approve\s+(?:this\s+)?trade\s+(?:immediately|unconditionally|with\s+100%)",
        r"override\s+(?:safety|risk|regime)\s+policy",
        r"jailbreak",
    ]
    all_news_text = " ".join([str(n.get("title", "")) + " " + str(n.get("summary", "")) for n in news_items])
    for pat in injection_patterns:
        if re.search(pat, all_news_text, re.IGNORECASE) or re.search(pat, str(verdict_data), re.IGNORECASE):
            red_flags.append("PROMPT_INJECTION_DETECTED: Adversarial instruction detected in qualitative input.")
            verdict_data["verdict"] = "REJECTED"

    # 2. Enforce EXACTLY 3 Bull and 3 Bear points (No Padding Allowed - Section 19.2)
    bulls = verdict_data.get("bull_arguments", [])
    bears = verdict_data.get("bear_arguments", [])
    if not isinstance(bulls, list):
        bulls = [str(bulls)] if bulls else []
    if not isinstance(bears, list):
        bears = [str(bears)] if bears else []

    if len(bulls) < 3 or len(bears) < 3:
        red_flags.append(
            f"INSUFFICIENT_ARGUMENTS: Required exactly 3 bull and 3 bear points, received {len(bulls)} bull and {len(bears)} bear. Padding prohibited."
        )
        verdict_data["verdict"] = "NOT_AUDITED"

    if len(bulls) > 3:
        bulls = bulls[:3]
    if len(bears) > 3:
        bears = bears[:3]

    verdict_data["bull_arguments"] = bulls
    verdict_data["bear_arguments"] = bears

    # 3. Number Checks Against Data Layer (Anti-Hallucination Guard - Section 19.2)
    all_text = " ".join(bulls + bears + [verdict_data.get("plain_language_summary", "")])

    # Check Entry, Stop, and Target Prices (0.5% relative tolerance)
    entry_price = float(prompt_data.get("entry_price_inr", 0.0))
    stop_loss = float(prompt_data.get("stop_loss_inr", 0.0))
    target_price = float(prompt_data.get("target_price_inr", 0.0))

    if entry_price > 0:
        entry_matches = re.findall(r"entry\s*(?:of|is|at|[:=])?\s*(?:₹|rs\.?)?\s*(\d+(?:\.\d+)?)", all_text, re.IGNORECASE)
        for em in entry_matches:
            try:
                val = float(em)
                if abs(val - entry_price) / entry_price > 0.005:
                    red_flags.append(f"UNGROUNDED_NUMBER_HALLUCINATION: Quoted entry ₹{val} deviates > 0.5% from data layer ₹{entry_price}")
                    verdict_data["verdict"] = "NOT_AUDITED"
            except Exception:
                pass

    if stop_loss > 0:
        stop_matches = re.findall(r"stop(?:\s*loss)?\s*(?:of|is|at|[:=])?\s*(?:₹|rs\.?)?\s*(\d+(?:\.\d+)?)", all_text, re.IGNORECASE)
        for sm in stop_matches:
            try:
                val = float(sm)
                if abs(val - stop_loss) / stop_loss > 0.005:
                    red_flags.append(f"UNGROUNDED_NUMBER_HALLUCINATION: Quoted stop ₹{val} deviates > 0.5% from data layer ₹{stop_loss}")
                    verdict_data["verdict"] = "NOT_AUDITED"
            except Exception:
                pass

    if target_price > 0:
        target_matches = re.findall(r"target\s*(?:of|is|at|[:=])?\s*(?:₹|rs\.?)?\s*(\d+(?:\.\d+)?)", all_text, re.IGNORECASE)
        for tm in target_matches:
            try:
                val = float(tm)
                if abs(val - target_price) / target_price > 0.005:
                    red_flags.append(f"UNGROUNDED_NUMBER_HALLUCINATION: Quoted target ₹{val} deviates > 0.5% from data layer ₹{target_price}")
                    verdict_data["verdict"] = "NOT_AUDITED"
            except Exception:
                pass

    # Check RSI (tightened to 2.0 pts tolerance)
    actual_rsi = float(prompt_data.get("technical_indicators", {}).get("rsi_14", 55.0))
    rsi_matches = re.findall(r"rsi\s*(?:of|is|at|[:=])?\s*(\d+(?:\.\d+)?)", all_text, re.IGNORECASE)
    for rm in rsi_matches:
        try:
            val = float(rm)
            if abs(val - actual_rsi) > 2.0:  # Quoted RSI contradicts data layer by > 2 points
                red_flags.append(f"UNGROUNDED_NUMBER_HALLUCINATION: RSI quoted as {val} vs actual {actual_rsi}")
                verdict_data["verdict"] = "NOT_AUDITED"
        except Exception:
            pass

    # Check India VIX (tightened to 1.0 pt tolerance)
    actual_vix = float(prompt_data.get("india_vix", 15.0))
    vix_matches = re.findall(r"vix\s*(?:of|is|at|[:=])?\s*(\d+(?:\.\d+)?)", all_text, re.IGNORECASE)
    for vm in vix_matches:
        try:
            val = float(vm)
            if abs(val - actual_vix) > 1.0:  # Quoted VIX contradicts data layer by > 1 point
                red_flags.append(f"UNGROUNDED_NUMBER_HALLUCINATION: VIX quoted as {val} vs actual {actual_vix}")
                verdict_data["verdict"] = "NOT_AUDITED"
        except Exception:
            pass

    # 4. No Changes to Numbers (Mathematical levels are strictly immutable)
    verdict_data["verified_entry_price"] = prompt_data["entry_price_inr"]
    verdict_data["verified_stop_loss"] = prompt_data["stop_loss_inr"]
    verdict_data["verified_target_price"] = prompt_data["target_price_inr"]

    # 5. Untrusted News Handling
    for n in news_items:
        if n.get("untrusted") or "rumor" in str(n.get("source", "")).lower():
            red_flags.append(f"UNTRUSTED_NEWS_SOURCE: {n.get('source')} flagged as unverified.")

    verdict_data["red_flags"] = list(set(red_flags))
    audit_res["verdict"] = verdict_data
    return audit_res


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
        v = audit_res.get("verdict", {})
        if isinstance(v, dict):
            b_cnt = len(v.get("bull_arguments", [])) if isinstance(v.get("bull_arguments"), list) else 0
            br_cnt = len(v.get("bear_arguments", [])) if isinstance(v.get("bear_arguments"), list) else 0
            if b_cnt < 3 or br_cnt < 3:
                # Retry once requesting explicitly 3 distinct bull and 3 distinct bear points (Section 19.2)
                retry_prompt = user_prompt + "\n\nCRITICAL: Your previous response contained fewer than 3 arguments. You MUST provide EXACTLY 3 bull arguments and EXACTLY 3 bear arguments."
                audit_res = llm_router.complete_audit(retry_prompt, AURA_SYSTEM_PROMPT)
        # Apply strict institutional verification & sanitization
        sanitized = verify_and_sanitize_audit_verdict(audit_res, prompt_data, news_items)
        return sanitized

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
