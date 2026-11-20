"""AURA-NSE Pro — Interactive Single-Ticker Research & Multi-Agent Debate CLI.

Generates an exhaustive institutional research dossier for any NSE equity:
1. Live pricing, technical indicators, and liquidity gating
2. Calibrated ML probability & friction-adjusted Expected Value (EV_R)
3. Intrinsic Worth, Margin of Safety, and 3-tranche allocation plan
4. Multi-Agent Dialectical Debate (Agent Bull vs Agent Bear vs Chief Arbitrator)
5. Paisa-accurate Indian statutory cost breakdown (STT, GST, Stamp Duty, DP charges)
6. Exports a complete, self-contained standalone HTML report dossier for browser viewing.

Usage:
  python scripts/analyze_ticker.py --ticker TATAMOTORS.NS
  python scripts/analyze_ticker.py --ticker RELIANCE.NS --rounds 2 --open
"""

from __future__ import annotations
import argparse
import datetime
import json
import logging
import os
from pathlib import Path
import sys
import webbrowser

# Ensure project root is in sys.path
_current_file = Path(__file__).resolve()
_project_root = _current_file.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from backend.core.config import PROJECT_ROOT, settings
from backend.costs.charges import charges_engine
from backend.data.holiday_calendar import get_ist_now
from backend.data.provider import data_provider
from backend.data.universe import get_sector_for_symbol
from backend.fundamental.compounder_scorecard import compounder_engine
from backend.llm.debate import debate_engine
from backend.ml.features import extract_features_from_df
from backend.ml.predictor import ml_predictor
from backend.risk.sizing import risk_guard
from backend.strategies.long_term import long_term_engine
from backend.strategies.regime import evaluate_market_regime
from backend.strategies.swing import swing_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("aura.dossier")


def generate_html_dossier(
    symbol: str,
    company_name: str,
    sector: str,
    current_price: float,
    as_of_ist: str,
    regime: dict,
    indicators: dict,
    ml_res: dict,
    swing_cand: Any,
    value_pick: Any,
    debate_res: dict,
    charges: dict,
    compounder_eval: Any = None,
) -> str:
    """Generate self-contained, publication-grade HTML research dossier."""
    adj = debate_res.get("adjudication", {})
    verdict = adj.get("verdict", "APPROVED")
    winner = adj.get("winner", "BULL")
    confidence = float(adj.get("confidence_pct", 75.0) or 75.0)

    regime = regime or {}
    regime_label = regime.get("regime_label", "UNKNOWN")
    nifty_close = float(regime.get("nifty_close") or 0.0)
    vix_val = float(regime.get("india_vix") if regime.get("india_vix") is not None else (regime.get("vix") or 0.0))
    
    fv_mid = getattr(value_pick, "fair_value_mid", None)
    fv_mid = float(fv_mid) if fv_mid is not None else float(current_price)
    mos_pct = getattr(value_pick, "margin_of_safety_pct", None)
    mos_pct = float(mos_pct) if mos_pct is not None else 0.0

    verdict_badge_color = "#10B981" if verdict == "APPROVED" else ("#F59E0B" if verdict == "APPROVED_REDUCED_SIZE" else "#EF4444")
    winner_badge_color = "#3B82F6" if winner == "BULL" else ("#8B5CF6" if winner == "SPLIT" else "#DC2626")

    # Format transcript items
    transcript_html = ""
    for item in debate_res.get("transcript", []):
        speaker = item.get("speaker", "")
        data = item.get("data", {})
        is_bull = "Bull" in speaker
        card_border = "#10B981" if is_bull else "#EF4444"
        badge_bg = "rgba(16, 185, 129, 0.15)" if is_bull else "rgba(239, 68, 68, 0.15)"
        speaker_color = "#34D399" if is_bull else "#F87171"

        title = data.get("round_theme", speaker)
        core_msg = data.get("core_thesis") or data.get("counter_thesis", "")
        bullets = data.get("primary_catalysts") or data.get("structural_hazards", [])

        bullets_html = "".join([f"<li style='margin-bottom: 6px;'>{b}</li>" for b in bullets])
        sub_edge = data.get("technical_edge") or data.get("technical_fragility", "")
        sub_defense = data.get("target_defense") or data.get("invalidation_condition", "")

        transcript_html += f"""
        <div style="background: #181920; border: 1px solid {card_border}; border-radius: 8px; padding: 18px; margin-bottom: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <span style="font-weight: 700; font-size: 1.05rem; color: {speaker_color};">● {speaker}</span>
                <span style="font-size: 0.8rem; background: {badge_bg}; color: {speaker_color}; padding: 3px 8px; border-radius: 4px; border: 1px solid {card_border};">{title}</span>
            </div>
            <p style="font-size: 0.95rem; line-height: 1.5; color: #E2E8F0; margin-bottom: 12px;">{core_msg}</p>
            <ul style="font-size: 0.88rem; color: #94A3B8; padding-left: 20px; margin-bottom: 12px;">
                {bullets_html}
            </ul>
            <div style="border-top: 1px solid #2D3748; padding-top: 10px; font-size: 0.85rem; color: #CBD5E1;">
                <div><strong>Technical Focus:</strong> {sub_edge}</div>
                <div style="margin-top: 4px;"><strong>Target / Invalidation Defense:</strong> {sub_defense}</div>
            </div>
        </div>
        """

    # Tranche plan formatting
    tranche_html = ""
    if value_pick and getattr(value_pick, "tranche_plan", None):
        tp = value_pick.tranche_plan
        for k, v in tp.items():
            label = k.replace("_", " ").title()
            pct = v.get("pct", 0)
            pt = v.get("price_target", 0.0)
            trg = v.get("trigger", "")
            tranche_html += f"""
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #2D3748; font-weight: 600;">{label}</td>
                <td style="padding: 10px; border-bottom: 1px solid #2D3748; text-align: center; color: #38BDF8;">{pct:.0f}%</td>
                <td style="padding: 10px; border-bottom: 1px solid #2D3748; text-align: right; font-weight: 700;">₹{pt:,.2f}</td>
                <td style="padding: 10px; border-bottom: 1px solid #2D3748; color: #94A3B8;">{trg}</td>
            </tr>
            """

    # 100-Point Compounder Matrix HTML formatting
    compounder_card_html = ""
    if compounder_eval:
        comp_score = compounder_eval.total_score
        comp_badge_color = "#10B981" if comp_score >= 80 else ("#38BDF8" if comp_score >= 65 else ("#F59E0B" if comp_score >= 50 else "#EF4444"))
        if compounder_eval.is_vetoed:
            comp_badge_color = "#DC2626"

        cat_rows = []
        for cat_k, cat in compounder_eval.categories.items():
            bar_color = "#10B981" if cat.rating_pct >= 75 else ("#38BDF8" if cat.rating_pct >= 50 else "#EF4444")
            notes_str = "; ".join(cat.notes[:2])
            cat_rows.append(f"""
            <tr>
                <td style="font-weight: 600; padding: 10px; border-bottom: 1px solid #1E232F;">{cat.name}</td>
                <td style="text-align: center; color: #94A3B8; padding: 10px; border-bottom: 1px solid #1E232F;">{cat.weight:.0f} pts</td>
                <td style="text-align: right; font-weight: 700; color: {bar_color}; padding: 10px; border-bottom: 1px solid #1E232F;">{cat.score:.1f} / {cat.max_score:.1f}</td>
                <td style="font-size: 0.85rem; color: #CBD5E1; padding: 10px; border-bottom: 1px solid #1E232F;">{notes_str}</td>
            </tr>
            """)

        cat_tbody = "".join(cat_rows)
        compounder_card_html = f"""
        <!-- 100-POINT INSTITUTIONAL COMPOUNDER MATRIX -->
        <div class="card" style="border-top: 4px solid {comp_badge_color};">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; border-bottom: 1px solid #1E232F; padding-bottom: 12px;">
                <div>
                    <div style="font-size: 0.8rem; font-weight: 700; color: #38BDF8; letter-spacing: 0.5px;">INSTITUTIONAL QUALITY & MOAT SCORECARD (SCREENER.IN AUDITED)</div>
                    <h2 style="font-size: 1.35rem; font-weight: 700; color: #F8FAFC;">100-Point Compounder Matrix</h2>
                </div>
                <div style="text-align: right;">
                    <span class="badge" style="background: {comp_badge_color}; color: #000; font-size: 1.1rem; padding: 6px 14px;">{comp_score:.1f} / 100</span>
                    <div style="font-size: 0.8rem; color: #94A3B8; margin-top: 4px;">{compounder_eval.grade}</div>
                </div>
            </div>
            <p style="font-size: 0.95rem; color: #E2E8F0; margin-bottom: 16px; line-height: 1.5;"><strong>Verdict:</strong> {compounder_eval.summary_verdict}</p>
            <table>
                <thead>
                    <tr>
                        <th>Evaluation Pillar</th>
                        <th style="text-align: center;">Max Weight</th>
                        <th style="text-align: right;">Audited Score</th>
                        <th>Institutional Metrics & Evidence</th>
                    </tr>
                </thead>
                <tbody>
                    {cat_tbody}
                </tbody>
            </table>
        </div>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AURA Institutional Dossier — {symbol}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background: #0B0E14;
            color: #F8FAFC;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            padding: 32px 20px;
            line-height: 1.5;
        }}
        .container {{
            max-width: 1140px;
            margin: 0 auto;
        }}
        .card {{
            background: #111319;
            border: 1px solid #1E232F;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #1E232F;
            padding-bottom: 20px;
            margin-bottom: 24px;
        }}
        .badge {{
            display: inline-block;
            font-size: 0.8rem;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 6px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .grid-2 {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }}
        .grid-3 {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
        }}
        .metric-box {{
            background: #161A23;
            border: 1px solid #232936;
            border-radius: 8px;
            padding: 14px 16px;
        }}
        .metric-title {{
            font-size: 0.75rem;
            color: #94A3B8;
            text-transform: uppercase;
            margin-bottom: 6px;
            font-weight: 600;
        }}
        .metric-val {{
            font-size: 1.35rem;
            font-weight: 700;
            color: #FFFFFF;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
        }}
        th {{
            text-align: left;
            padding: 10px;
            background: #161A23;
            color: #94A3B8;
            border-bottom: 1px solid #2D3748;
            font-size: 0.8rem;
            text-transform: uppercase;
        }}
        td {{
            padding: 10px;
            border-bottom: 1px solid #1E232F;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- HEADER -->
        <div class="header">
            <div>
                <div style="font-size: 0.8rem; font-weight: 700; color: #38BDF8; letter-spacing: 1px; margin-bottom: 4px;">AURA-NSE PRO INSTITUTIONAL DOSSIER</div>
                <h1 style="font-size: 2.2rem; font-weight: 800; color: #FFFFFF;">{symbol} <span style="font-size: 1.1rem; color: #94A3B8; font-weight: 400;">({sector})</span></h1>
                <div style="font-size: 0.85rem; color: #64748B; margin-top: 4px;">As of {as_of_ist} | Macro Regime: <span style="color: #10B981; font-weight: 600;">{regime_label}</span> (NIFTY 50: {nifty_close:,.1f}, VIX: {vix_val:.1f})</div>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 0.8rem; color: #94A3B8; margin-bottom: 4px;">CURRENT MARKET PRICE</div>
                <div style="font-size: 2.2rem; font-weight: 800; color: #38BDF8;">₹{current_price:,.2f}</div>
                <div class="badge" style="background: rgba(56, 189, 248, 0.15); color: #38BDF8; border: 1px solid #0284C7; margin-top: 6px;">NSE_EQ LIVE TELEMETRY</div>
            </div>
        </div>

        <!-- EXECUTIVE VERDICT BANNER -->
        <div class="card" style="border-left: 6px solid {verdict_badge_color};">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                <div style="display: flex; align-items: center; gap: 12px;">
                    <span class="badge" style="background: {verdict_badge_color}; color: #000; font-size: 1rem; padding: 6px 14px;">{verdict}</span>
                    <span class="badge" style="background: rgba(255,255,255,0.08); color: #FFFFFF; border: 1px solid #334155;">DEBATE WINNER: <strong style="color: {winner_badge_color};">{winner}</strong></span>
                </div>
                <div style="font-size: 1.1rem; font-weight: 700; color: #E2E8F0;">
                    Adjudication Conviction: <span style="color: #38BDF8;">{confidence:.1f}%</span>
                </div>
            </div>
            <p style="font-size: 1.05rem; line-height: 1.6; color: #F1F5F9; margin-bottom: 16px;">{adj.get('consensus_thesis', 'Quantitative setup validated through dialectical review.')}</p>
            <div style="background: #161A23; border: 1px dashed #334155; border-radius: 8px; padding: 12px 16px; font-size: 0.9rem; color: #FCA5A5;">
                <strong>🚨 THESIS INVALIDATION TRIGGER:</strong> {adj.get('invalidation_criteria', 'Price break below key stop level.')}
            </div>
        </div>

        <!-- KEY METRICS GRID -->
        <div class="grid-3" style="margin-bottom: 24px;">
            <div class="metric-box">
                <div class="metric-title">ML Win Probability</div>
                <div class="metric-val" style="color: #34D399;">{ml_res.get('win_probability_pct', 50.0):.1f}%</div>
                <div style="font-size: 0.75rem; color: #64748B; margin-top: 4px;">Calibrated Walk-Forward Model</div>
            </div>
            <div class="metric-box">
                <div class="metric-title">Expected Value (EV_R)</div>
                <div class="metric-val" style="color: #38BDF8;">+{ml_res.get('ev_r', 0.0):.2f}R</div>
                <div style="font-size: 0.75rem; color: #64748B; margin-top: 4px;">Net of All Taxes & STT Fees</div>
            </div>
            <div class="metric-box">
                <div class="metric-title">Intrinsic Fair Worth</div>
                <div class="metric-val" style="color: #FCD34D;">₹{fv_mid:,.2f}</div>
                <div style="font-size: 0.75rem; color: #64748B; margin-top: 4px;">Margin of Safety: {mos_pct:+.1f}%</div>
            </div>
        </div>

        {compounder_card_html}

        <!-- MULTI-AGENT DIALECTICAL DEBATE SECTION -->
        <div class="card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; border-bottom: 1px solid #1E232F; padding-bottom: 12px;">
                <h2 style="font-size: 1.35rem; font-weight: 700; color: #F8FAFC;">Multi-Agent Dialectical Debate Transcript</h2>
                <span style="font-size: 0.8rem; color: #94A3B8;">{debate_res.get('rounds_conducted', 2)} Structured Rounds Refereed by CIO</span>
            </div>
            {transcript_html}
            
            <div style="background: #131722; border: 1px solid #3B82F6; border-radius: 8px; padding: 18px; margin-top: 20px;">
                <div style="font-weight: 700; font-size: 1rem; color: #60A5FA; margin-bottom: 6px;">Chief Arbitrator Summary Ruling:</div>
                <p style="font-size: 0.95rem; color: #E2E8F0; line-height: 1.5;">{adj.get('arbitrator_rationale', '')}</p>
            </div>
        </div>

        <!-- 3-TRANCHE EXECUTION PLAN -->
        <div class="grid-2">
            <div class="card">
                <h3 style="font-size: 1.15rem; font-weight: 700; color: #F8FAFC; margin-bottom: 14px;">Staggered 3-Tranche Execution Ladder</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Tranche</th>
                            <th style="text-align: center;">Allocation</th>
                            <th style="text-align: right;">Target Price</th>
                            <th>Trigger Rule</th>
                        </tr>
                    </thead>
                    <tbody>
                        {tranche_html if tranche_html else "<tr><td colspan='4' style='text-align:center; color:#64748B;'>Standard swing limit order at entry.</td></tr>"}
                    </tbody>
                </table>
            </div>

            <div class="card">
                <h3 style="font-size: 1.15rem; font-weight: 700; color: #F8FAFC; margin-bottom: 14px;">Indian Statutory Charges Breakdown (Paisa Accuracy)</h3>
                <table>
                    <tr><td>Gross Capital Outlay</td><td style="text-align:right; font-weight:700;">₹{charges.get('buy_turnover', 0.0):,.2f}</td></tr>
                    <tr><td>Securities Transaction Tax (STT)</td><td style="text-align:right; color:#F87171;">₹{charges.get('stt', 0.0):,.2f}</td></tr>
                    <tr><td>Exchange Turnover Charges</td><td style="text-align:right; color:#F87171;">₹{charges.get('exchange_txn_charge', 0.0):,.2f}</td></tr>
                    <tr><td>SEBI Regulatory Turnover Fee</td><td style="text-align:right; color:#F87171;">₹{charges.get('sebi_fee', 0.0):,.2f}</td></tr>
                    <tr><td>State Stamp Duty</td><td style="text-align:right; color:#F87171;">₹{charges.get('stamp_duty', 0.0):,.2f}</td></tr>
                    <tr><td>GST (@ 18% on fees & brokerage)</td><td style="text-align:right; color:#F87171;">₹{charges.get('gst', 0.0):,.2f}</td></tr>
                    <tr><td>Depository DP Charges (Delivery)</td><td style="text-align:right; color:#F87171;">₹{charges.get('dp_charge', 0.0):,.2f}</td></tr>
                    <tr style="border-top: 2px solid #334155; font-weight:700;"><td>Total Statutory Friction</td><td style="text-align:right; color:#38BDF8;">₹{charges.get('total_costs', charges.get('total_charges_and_brokerage', 0.0)):,.2f}</td></tr>
                </table>
            </div>
        </div>

        <!-- FOOTER -->
        <div style="text-align: center; color: #64748B; font-size: 0.8rem; margin-top: 32px; border-top: 1px solid #1E232F; padding-top: 20px;">
            AURA-NSE Pro Institutional Research Dossier • Generated automatically via Tiered Cognitive AI Engine • Single-User Educational Decision Support
        </div>
    </div>
</body>
</html>
"""
    return html_content


def analyze_ticker(
    ticker: str,
    rounds: int = 2,
    output_html: Optional[str] = None,
    open_browser: bool = False,
) -> dict:
    """Run end-to-end multi-agent analysis on a single ticker."""
    symbol = ticker.strip().upper()
    if not symbol.endswith(".NS") and not symbol.endswith(".BO"):
        symbol = f"{symbol}.NS"

    logger.info(f"=== Starting AURA Deep Dive Analysis for {symbol} ===")

    # 1. Benchmark & Macro Regime
    now_ist = get_ist_now()
    regime = evaluate_market_regime()
    nifty_df = data_provider.fetch_history("^NSEI", period="1y", interval="1d")

    # 2. Fetch Historical Stock OHLCV
    df = data_provider.fetch_history(symbol, period="1y", interval="1d")
    if df.empty or len(df) < 50:
        logger.error(f"Insufficient history or data unavailable for {symbol}.")
        return {"status": "ERROR", "message": f"Could not fetch historical OHLCV for {symbol}"}

    current_price = float(df["close"].iloc[-1])
    sector = get_sector_for_symbol(symbol)

    # 3. Quality Gate
    q_pass, q_reason, q_meta = data_provider.validate_quality_gate(symbol, df)

    # 4. Swing Strategy Evaluation
    swing_cand = swing_engine.evaluate(symbol, df, nifty_df)

    # 5. Fundamentals & Intrinsic Valuation
    fundamentals = data_provider.fetch_fundamentals(symbol)
    value_pick = long_term_engine.evaluate(symbol, df, fundamentals)

    # 5b. 100-Point Institutional Compounder Scorecard (Screener.in Audited)
    tech_data = {
        "rsi_14": swing_cand.indicators.get("rsi_14") if hasattr(swing_cand, "indicators") and swing_cand.indicators else 52.0,
        "sma_50": swing_cand.indicators.get("sma_50") if hasattr(swing_cand, "indicators") and swing_cand.indicators else current_price,
        "sma_200": swing_cand.indicators.get("sma_200") if hasattr(swing_cand, "indicators") and swing_cand.indicators else current_price,
        "volume_ratio_20d": swing_cand.indicators.get("volume_ratio_20d") if hasattr(swing_cand, "indicators") and swing_cand.indicators else 1.0,
        "close": current_price,
    }
    compounder_eval = compounder_engine.evaluate_equity(
        symbol=symbol,
        technical_data=tech_data,
        macro_regime=regime,
        margin_of_safety_pct=getattr(value_pick, "margin_of_safety_pct", 0.0),
    )

    # 6. ML Probability & Expected Value (EV_R)
    features = extract_features_from_df(df, nifty_df)
    ml_res = ml_predictor.predict_probability(features)

    # 7. Statutory Indian Friction & Charges
    entry_p = current_price
    target_p = swing_cand.target_price if swing_cand.passed else round(current_price * 1.10, 2)
    stop_p = swing_cand.stop_loss if swing_cand.passed else round(current_price * 0.95, 2)

    avg_vol = q_meta.get("avg_volume_20d", 1000000.0) if q_meta else 1000000.0
    risk_result = risk_guard.compute_position_size(
        symbol=symbol,
        entry_price=entry_p,
        stop_loss=stop_p,
        target_price=target_p,
        sector=sector,
        total_capital=settings.INITIAL_CAPITAL,
        available_cash=settings.INITIAL_CAPITAL * 0.8,
        avg_20d_volume=avg_vol,
        macro_regime=regime.get("regime_label", "GREEN"),
    )
    default_qty = max(1, int((settings.INITIAL_CAPITAL * 0.05) // entry_p))
    qty = risk_result.quantity if (risk_result.allowed and risk_result.quantity > 0) else default_qty

    charges = charges_engine.calculate_delivery_charges(
        buy_price=entry_p,
        sell_price=target_p,
        quantity=qty,
        include_slippage=True,
    )

    # 8. Multi-Agent Dialectical Debate (Agent Bull vs Agent Bear vs CIO Arbitrator)
    setup_data = {
        "symbol": symbol,
        "sector": sector,
        "current_price": entry_p,
        "entry_price": entry_p,
        "target_price": target_p,
        "stop_loss": stop_p,
        "win_probability_pct": ml_res.get("win_probability_pct", 50.0),
        "ev_r": ml_res.get("ev_r", 0.0),
        "macro_regime": regime.get("regime_label"),
        "pe_ratio": fundamentals.get("pe_ratio"),
        "roe_pct": fundamentals.get("roe_pct"),
        "debt_to_equity": fundamentals.get("debt_to_equity"),
        "fair_value_mid": getattr(value_pick, "fair_value_mid", entry_p),
        "margin_of_safety_pct": getattr(value_pick, "margin_of_safety_pct", 0.0),
        "swing_setup_passed": swing_cand.passed,
        "indicators": swing_cand.indicators if hasattr(swing_cand, "indicators") else {},
    }

    debate_res = debate_engine.run_debate(symbol=symbol, setup_data=setup_data, rounds=rounds)

    # 9. HTML Dossier Generation
    clean_sym = symbol.replace(".NS", "").replace(".BO", "")
    target_html_path = Path(output_html) if output_html else (PROJECT_ROOT / "reports" / f"dossier_{clean_sym}.html")
    target_html_path.parent.mkdir(parents=True, exist_ok=True)

    html_content = generate_html_dossier(
        symbol=symbol,
        company_name=clean_sym,
        sector=sector,
        current_price=current_price,
        as_of_ist=now_ist.strftime("%d %b %Y, %I:%M %p IST"),
        regime=regime,
        indicators=setup_data["indicators"],
        ml_res=ml_res,
        swing_cand=swing_cand,
        value_pick=value_pick,
        debate_res=debate_res,
        charges=charges.to_dict(),
        compounder_eval=compounder_eval,
    )

    target_html_path.write_text(html_content, encoding="utf-8")
    logger.info(f"HTML Dossier successfully saved to: {target_html_path}")

    # 10. Terminal Summary Output
    adj = debate_res.get("adjudication", {})
    fv_mid_val = getattr(value_pick, 'fair_value_mid', current_price) if value_pick else current_price
    mos_pct_val = getattr(value_pick, 'margin_of_safety_pct', 0.0) if value_pick else 0.0
    print("\n" + "="*70)
    print(f"📊 AURA INSTITUTIONAL RESEARCH DOSSIER: {symbol} ({sector})")
    print("="*70)
    print(f"💵 Market Price:     ₹{current_price:,.2f}")
    print(f"🎯 Target Level:     ₹{target_p:,.2f} | Stop Loss: ₹{stop_p:,.2f}")
    print(f"🧠 Calibrated ML:    Win Prob: {ml_res.get('win_probability_pct', 50):.1f}% | EV_R: +{ml_res.get('ev_r', 0):.2f}R")
    print(f"💎 Fundamental Fair: ₹{fv_mid_val:,.2f} (Margin of Safety: {mos_pct_val:+.1f}%)")
    print(f"🏆 Compounder Score: {compounder_eval.total_score:.1f}/100 [{compounder_eval.grade}]")
    if compounder_eval.is_vetoed:
        print(f"🚨 Governance Veto:  {compounder_eval.veto_reason}")
    print(f"⚖️ Final Verdict:     {adj.get('verdict')} (Conviction: {adj.get('confidence_pct', 75):.1f}%)")
    print(f"🏆 Debate Winner:    {adj.get('winner')}")
    print(f"🚨 Invalidation:     {adj.get('invalidation_criteria')}")
    print(f"📄 Full HTML Report: {target_html_path.resolve()}")
    print("="*70 + "\n")

    if open_browser:
        webbrowser.open(str(target_html_path.resolve()))

    return {
        "status": "SUCCESS",
        "symbol": symbol,
        "verdict": adj.get("verdict"),
        "confidence_pct": adj.get("confidence_pct"),
        "html_report_path": str(target_html_path.resolve()),
        "debate_transcript": debate_res.get("transcript"),
    }


def main():
    parser = argparse.ArgumentParser(description="AURA-NSE Pro Single-Ticker Research & Debate CLI")
    parser.add_argument("--ticker", type=str, required=True, help="NSE/BSE Ticker symbol (e.g. TATAMOTORS.NS, RELIANCE)")
    parser.add_argument("--rounds", type=int, default=2, help="Number of multi-agent debate rounds (default: 2)")
    parser.add_argument("--output-html", type=str, default=None, help="Custom output path for the HTML dossier")
    parser.add_argument("--open", action="store_true", help="Automatically open generated HTML report in browser")
    args = parser.parse_args()

    analyze_ticker(
        ticker=args.ticker,
        rounds=args.rounds,
        output_html=args.output_html,
        open_browser=args.open,
    )


if __name__ == "__main__":
    main()
