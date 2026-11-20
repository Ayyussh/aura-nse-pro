"""AURA-NSE Pro Multi-Agent Dialectical Debate Engine.

Implements multi-agent deliberation inspired by institutional trading desks:
- Bull Analyst Agent: Constructs upside momentum, growth, and catalyst theses.
- Bear Risk Agent: Attacks structural vulnerabilities, overhead supply, and governance hazards.
- Chief Arbitrator (CIO): Reviews multi-round debate arguments using Deep-Think cognitive models
  and issues binding verdict, confidence %, and thesis invalidation criteria.
"""

from __future__ import annotations
import json
import logging
from typing import Dict, List, Any, Optional

from backend.llm.router import llm_router

logger = logging.getLogger("aura.llm_debate")


BULL_AGENT_SYSTEM_PROMPT = """You are Agent Bull, an institutional Growth & Technical Momentum Analyst for Indian Equities (NSE/BSE).
Your mission is to formulate the strongest data-driven bull thesis for the given trade candidate.
Focus strictly on:
1. Technical trend alignment (20/50/200 MAs, ADX momentum, pullback support).
2. Volume absorption and relative strength (Mansfield RS vs NIFTY 50).
3. Positive corporate, sector, or earnings catalysts.
4. Favorable risk-to-reward geometry (minimum 2.5R target potential).

Output MUST be valid JSON with keys:
- "round_theme": "Bullish Opening Thesis" or "Rebuttal to Bear"
- "core_thesis": "string (2-3 sentences)",
- "primary_catalysts": ["catalyst 1", "catalyst 2", "catalyst 3"],
- "technical_edge": "string explaining why price is positioned for upside expansion",
- "target_defense": "string defending the mathematical target level"
"""

BEAR_AGENT_SYSTEM_PROMPT = """You are Agent Bear, an institutional Risk Officer and Short-Side Forensic Analyst for Indian Equities (NSE/BSE).
Your mission is to aggressively challenge and attempt to invalidate the trade setup.
Focus strictly on:
1. Overhead resistance, supply zones, or divergence (e.g. RSI bearish divergence).
2. Macro and sector drag (NIFTY resistance, high India VIX, sector underperformance).
3. Valuation stretch, governance alerts, promoter pledging, or upcoming event risks.
4. Stop-loss vulnerability (potential for stop-hunting or gap-down breach).

Output MUST be valid JSON with keys:
- "round_theme": "Bearish Opening Counter" or "Cross-Examination & Threat Matrix"
- "counter_thesis": "string (2-3 sentences)",
- "structural_hazards": ["hazard 1", "hazard 2", "hazard 3"],
- "technical_fragility": "string detailing resistance hurdles or lack of volume confirmation",
- "invalidation_condition": "string specifying exact price action that proves the setup failed"
"""

ARBITRATOR_SYSTEM_PROMPT = """You are the Chief Investment Officer (CIO) and Final Arbitrator for AURA-NSE Pro.
You moderate the multi-agent debate between Agent Bull and Agent Bear.
Your task is to weigh both arguments against verified market facts, risk budgets, and macro regimes,
and render an institutional ruling.

RULING TIERS:
- APPROVED: Bull thesis conclusively outperforms; risks are manageable with strict stop.
- APPROVED_REDUCED_SIZE: Valid setup with identifiable headwinds; allocate 50% capital.
- REJECTED: Bear exposed critical flaws, overhead supply, or unfavorable risk/reward.

Output MUST be strictly valid JSON matching this schema:
{
  "winner": "BULL" | "BEAR" | "SPLIT",
  "verdict": "APPROVED" | "APPROVED_REDUCED_SIZE" | "REJECTED",
  "confidence_pct": float (0-100),
  "consensus_thesis": "string (executive summary of the ruling)",
  "arbitrator_rationale": "detailed 2-3 sentence explanation of why the winning side prevailed",
  "key_catalysts": ["catalyst 1", "catalyst 2", "catalyst 3"],
  "critical_vulnerabilities": ["vulnerability 1", "vulnerability 2", "vulnerability 3"],
  "invalidation_criteria": "specific price or macro event that triggers immediate exit",
  "recommended_sizing_multiplier": float (0.0 to 1.0)
}
"""


class MultiAgentDebateEngine:
    """Orchestrates structured multi-round Bull vs. Bear debate refereed by Chief Arbitrator."""

    def run_debate(
        self,
        symbol: str,
        setup_data: Dict[str, Any],
        rounds: int = 2,
    ) -> Dict[str, Any]:
        """Execute multi-round debate for a specific equity setup."""
        logger.info(f"Initiating Multi-Agent Debate for {symbol} ({rounds} rounds)...")

        transcript: List[Dict[str, Any]] = []

        # -------------------------------------------------------------
        # Round 1: Opening Arguments
        # -------------------------------------------------------------
        bull_r1 = self._run_bull_round(symbol, setup_data, round_num=1, prev_bear=None)
        transcript.append({"round": 1, "speaker": "Agent Bull", "data": bull_r1})

        bear_r1 = self._run_bear_round(symbol, setup_data, round_num=1, prev_bull=bull_r1)
        transcript.append({"round": 1, "speaker": "Agent Bear", "data": bear_r1})

        # -------------------------------------------------------------
        # Round 2: Cross-Examination (if requested)
        # -------------------------------------------------------------
        bull_r2 = None
        bear_r2 = None
        if rounds >= 2:
            bull_r2 = self._run_bull_round(symbol, setup_data, round_num=2, prev_bear=bear_r1)
            transcript.append({"round": 2, "speaker": "Agent Bull (Rebuttal)", "data": bull_r2})

            bear_r2 = self._run_bear_round(symbol, setup_data, round_num=2, prev_bull=bull_r2)
            transcript.append({"round": 2, "speaker": "Agent Bear (Counter)", "data": bear_r2})

        # -------------------------------------------------------------
        # Final Adjudication (Deep-Think Model Tier)
        # -------------------------------------------------------------
        adjudication = self._run_arbitrator(
            symbol=symbol,
            setup_data=setup_data,
            transcript=transcript,
        )

        return {
            "symbol": symbol,
            "rounds_conducted": rounds,
            "adjudication": adjudication,
            "transcript": transcript,
            "debate_summary": {
                "verdict": adjudication.get("verdict", "APPROVED"),
                "confidence_pct": adjudication.get("confidence_pct", 75.0),
                "winner": adjudication.get("winner", "BULL"),
                "consensus_thesis": adjudication.get("consensus_thesis", ""),
                "invalidation_criteria": adjudication.get("invalidation_criteria", ""),
            },
        }

    def _run_bull_round(
        self,
        symbol: str,
        setup_data: Dict[str, Any],
        round_num: int,
        prev_bear: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Invoke Bull Analyst agent using Quick-Think model tier."""
        prompt_content = {
            "symbol": symbol,
            "round": round_num,
            "market_setup": setup_data,
            "bear_arguments_to_rebut": prev_bear,
        }
        user_prompt = f"Candidate facts:\n{json.dumps(prompt_content, indent=2)}\n\nPresent your Bull arguments in JSON."
        resp = llm_router.call_tiered_model(
            prompt=user_prompt,
            system_prompt=BULL_AGENT_SYSTEM_PROMPT,
            tier="quick",
            response_json=True,
        )
        if resp.get("status") == "SUCCESS" and isinstance(resp.get("data"), dict):
            return resp["data"]

        # Algorithmic fallback
        return {
            "round_theme": f"Bullish Thesis (Round {round_num})",
            "core_thesis": f"{symbol} exhibits strong trend alignment with price trading above key structural moving averages and constructive volume expansion.",
            "primary_catalysts": [
                f"Breakout confirmation on 20-day moving average test",
                f"Mansfield Relative Strength vs NIFTY 50 remains positive",
                f"Clean risk-reward skew with stop placed beneath major support",
            ],
            "technical_edge": "High-liquidity setup displaying controlled pullback volatility and positive mathematical expectancy.",
            "target_defense": f"Target price ₹{setup_data.get('target_price', 0.0)} represents an unreached liquidity pool aligned with prior swing highs.",
        }

    def _run_bear_round(
        self,
        symbol: str,
        setup_data: Dict[str, Any],
        round_num: int,
        prev_bull: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Invoke Bear Risk agent using Quick-Think model tier."""
        prompt_content = {
            "symbol": symbol,
            "round": round_num,
            "market_setup": setup_data,
            "bull_claims_to_challenge": prev_bull,
        }
        user_prompt = f"Candidate facts:\n{json.dumps(prompt_content, indent=2)}\n\nChallenge the bull case in JSON."
        resp = llm_router.call_tiered_model(
            prompt=user_prompt,
            system_prompt=BEAR_AGENT_SYSTEM_PROMPT,
            tier="quick",
            response_json=True,
        )
        if resp.get("status") == "SUCCESS" and isinstance(resp.get("data"), dict):
            return resp["data"]

        # Algorithmic fallback
        return {
            "round_theme": f"Bearish Counter (Round {round_num})",
            "counter_thesis": f"{symbol} faces immediate overhead resistance and risk of false breakout if broader market breadth weakens.",
            "structural_hazards": [
                "Overhead supply zone near recent multi-week highs",
                "Potential momentum divergence on shorter intraday timeframes",
                "Broad market NIFTY volatility / sector consolidation risk",
            ],
            "technical_fragility": "Failure of buyers to sustain gap openings could trigger cascade stop-loss hits.",
            "invalidation_condition": f"Daily close below stop loss ₹{setup_data.get('stop_loss', 0.0)} completely invalidates the setup.",
        }

    def _run_arbitrator(
        self,
        symbol: str,
        setup_data: Dict[str, Any],
        transcript: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Invoke Chief Arbitrator using Deep-Think model tier."""
        dossier = {
            "symbol": symbol,
            "setup": setup_data,
            "debate_transcript": transcript,
        }
        user_prompt = f"Review the complete multi-round debate transcript and issue final binding adjudication in JSON:\n\n{json.dumps(dossier, indent=2)}"
        resp = llm_router.call_tiered_model(
            prompt=user_prompt,
            system_prompt=ARBITRATOR_SYSTEM_PROMPT,
            tier="deep",
            response_json=True,
        )
        if resp.get("status") == "SUCCESS" and isinstance(resp.get("data"), dict):
            adj = resp["data"]
            # Enforce validation
            if "verdict" in adj and "confidence_pct" in adj:
                return adj

        # Algorithmic fallback
        win_prob = setup_data.get("win_probability_pct", 55.0)
        ev_r = setup_data.get("ev_r", 0.35)
        verdict = "APPROVED" if (win_prob >= 50.0 and ev_r >= 0.20) else ("APPROVED_REDUCED_SIZE" if ev_r >= 0.10 else "REJECTED")

        return {
            "winner": "BULL" if verdict == "APPROVED" else ("SPLIT" if verdict == "APPROVED_REDUCED_SIZE" else "BEAR"),
            "verdict": verdict,
            "confidence_pct": float(win_prob),
            "consensus_thesis": f"{symbol} validated through dialectical review: Bull thesis exhibits superior risk-adjusted asymmetric payoff.",
            "arbitrator_rationale": "Quantitative momentum metrics and relative strength outweigh overhead supply concerns provided stop loss is strictly honored.",
            "key_catalysts": [
                "Technical pullback absorption at 20-EMA",
                "Positive Mansfield relative strength vs benchmark",
                "Mathematical EV exceeds institutional +0.20R friction hurdle",
            ],
            "critical_vulnerabilities": [
                "Resistance supply cluster near 52-week peak",
                "Macro volatility spikes during market open",
                "Sector-wide rotation pressure",
            ],
            "invalidation_criteria": f"Close below ₹{setup_data.get('stop_loss', 0.0)} or gap-down breach at market open.",
            "recommended_sizing_multiplier": 1.0 if verdict == "APPROVED" else 0.5,
        }


debate_engine = MultiAgentDebateEngine()
