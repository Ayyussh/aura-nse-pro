"""Interactive Stock Research & AURA Chat Console.

Enables function-calling queries over the application database and live data layer:
- Inquire about stock fundamentals, technicals, and why a symbol was approved/rejected
- Inspect live market regime, portfolio holdings, and stress test performance
- Upholds educational decision support boundaries (no guaranteed returns, no order execution).
"""

from __future__ import annotations
import datetime
import json
from typing import Dict, Any, List

from backend.data.provider import data_provider
from backend.data.universe import get_sector_for_symbol
from backend.db.session import SessionLocal
from backend.db.models import Prediction, PortfolioHolding
from backend.strategies.regime import evaluate_market_regime


def query_stock_technical_summary(symbol: str) -> Dict[str, Any]:
    """Fetch live technical indicators and quality check for a given symbol."""
    sym = symbol.upper()
    if not (sym.endswith(".NS") or sym.endswith(".BO")):
        sym = f"{sym}.NS"

    df = data_provider.fetch_history(sym, period="1y", interval="1d")
    if df.empty:
        return {"error": f"No data found for symbol {sym}"}

    from backend.strategies.swing import swing_engine
    nifty_df = data_provider.fetch_history("^NSEI", period="1y", interval="1d")
    candidate = swing_engine.evaluate(sym, df, nifty_df)

    return {
        "symbol": sym,
        "sector": get_sector_for_symbol(sym),
        "latest_close": candidate.entry_price,
        "swing_screening_passed": candidate.passed,
        "setup_tag": candidate.setup_tag,
        "stop_loss": candidate.stop_loss,
        "target_price": candidate.target_price,
        "atr_14": candidate.atr_14,
        "indicators": candidate.indicators,
        "rejection_reasons": candidate.rejection_reasons,
        "source": "yfinance_ohlcv",
        "as_of": datetime.datetime.utcnow().isoformat(),
    }


def query_stock_fundamentals(symbol: str) -> Dict[str, Any]:
    """Fetch live fundamentals (ROE, PE, Debt, Market Cap) for an Indian equity."""
    sym = symbol.upper()
    if not (sym.endswith(".NS") or sym.endswith(".BO")):
        sym = f"{sym}.NS"
    return data_provider.fetch_fundamentals(sym)


def query_todays_recommendations() -> List[Dict[str, Any]]:
    """Retrieve today's active 9:00 AM predictions from the database."""
    db = SessionLocal()
    try:
        preds = db.query(Prediction).order_by(Prediction.created_at.desc()).limit(10).all()
        return [
            {
                "symbol": p.symbol,
                "horizon": p.horizon,
                "status": p.status,
                "entry_price": p.entry_price,
                "stop_loss": p.stop_loss,
                "target_price": p.target_price,
                "quantity": p.quantity,
                "win_probability": p.win_probability,
                "ev_r": p.ev_r,
                "verdict": p.llm_verdict,
                "created_at": p.created_at.isoformat(),
            }
            for p in preds
        ]
    finally:
        db.close()


def query_active_portfolio() -> List[Dict[str, Any]]:
    """Retrieve current holdings in paper or real portfolio."""
    db = SessionLocal()
    try:
        holdings = db.query(PortfolioHolding).all()
        return [
            {
                "symbol": h.symbol,
                "sector": h.sector,
                "quantity": h.quantity,
                "avg_price": h.average_buy_price,
                "current_price": h.current_price,
                "unrealized_pnl": h.unrealized_pnl,
                "is_paper": h.is_paper,
            }
            for h in holdings
        ]
    finally:
        db.close()


def process_research_chat_query(user_message: str) -> Dict[str, Any]:
    """Answer conversational user queries with live tool execution."""
    msg_lower = user_message.lower()

    # Route based on query intent
    if "regime" in msg_lower or "market" in msg_lower or "nifty" in msg_lower or "vix" in msg_lower:
        regime = evaluate_market_regime()
        summary = (
            f"**NSE Macro Regime:** **{regime['regime_label']}** (Sizing multiplier: {regime['sizing_multiplier']*100:.0f}%)\n\n"
            f"- **NIFTY 50 Close:** ₹{regime['nifty_close']:,.2f} (20-EMA: ₹{regime['nifty_20_ema']:,.2f}, 50-EMA: ₹{regime['nifty_50_ema']:,.2f})\n"
            f"- **India VIX:** {regime['india_vix']} (5-Day change: {regime['vix_5d_change']:+.2f})\n"
            f"- **Leading Sectors:** {', '.join(regime['top_leading_sectors'])}\n\n"
            f"_{regime['description']}_"
        )
        return {
            "reply": summary,
            "tool_data": regime,
            "source": "live_nse_feed",
            "timestamp": datetime.datetime.utcnow().isoformat(),
        }

    if "today" in msg_lower or "recommend" in msg_lower or "pick" in msg_lower or "call" in msg_lower:
        recs = query_todays_recommendations()
        if not recs:
            return {
                "reply": "No trades currently logged for today. AURA runs the screening pipeline at 9:00 AM IST or you can click 'Run 9:00 AM Scan Now' in the Command Center.",
                "tool_data": [],
                "source": "predictions_db",
                "timestamp": datetime.datetime.utcnow().isoformat(),
            }
        cards = "\n".join([f"- **{r['symbol']}** ({r['horizon']}): Entry ₹{r['entry_price']}, Stop ₹{r['stop_loss']}, Target ₹{r['target_price']}, Qty {r['quantity']}, Win Prob {r.get('win_probability', 0)*100:.0f}%, Verdict: {r['verdict']}" for r in recs])
        return {
            "reply": f"**Latest Screened & Approved Signals:**\n\n{cards}",
            "tool_data": recs,
            "source": "predictions_db",
            "timestamp": datetime.datetime.utcnow().isoformat(),
        }

    if "portfolio" in msg_lower or "holding" in msg_lower:
        ports = query_active_portfolio()
        if not ports:
            return {
                "reply": "Your portfolio currently has no open positions recorded. You can add holdings manually or import a broker contract note in the Portfolio tab.",
                "tool_data": [],
                "source": "portfolio_db",
                "timestamp": datetime.datetime.utcnow().isoformat(),
            }
        port_lines = "\n".join([f"- **{h['symbol']}** ({h['sector']}): {h['quantity']} shares @ ₹{h['avg_price']}, Current: ₹{h['current_price']}, Unrealized P&L: ₹{h['unrealized_pnl']:+,.2f}" for h in ports])
        return {
            "reply": f"**Current Portfolio Holdings:**\n\n{port_lines}",
            "tool_data": ports,
            "source": "portfolio_db",
            "timestamp": datetime.datetime.utcnow().isoformat(),
        }

    # Extract ticker mentions (e.g. TCS, INFY, RELIANCE, HDFCBANK)
    for sym in ["TCS", "INFY", "RELIANCE", "HDFCBANK", "ICICIBANK", "SBIN", "TATAMOTORS", "ITC", "LT", "BHARTIARTL"]:
        if sym.lower() in msg_lower:
            tech = query_stock_technical_summary(sym)
            fund = query_stock_fundamentals(sym)
            passed_txt = "Passed All Quantitative Filters" if tech.get("swing_screening_passed") else "Failed Strategy Filters"
            reasons = "; ".join(tech.get("rejection_reasons", [])) or "None (Clean setup)"
            reply = (
                f"### Analysis for {tech['symbol']} ({tech['sector']})\n\n"
                f"- **Latest Close:** ₹{tech.get('latest_close', 0):,.2f}\n"
                f"- **Swing Screening Verdict:** **{passed_txt}** (Setup: `{tech.get('setup_tag')}`)\n"
                f"- **Stop Loss / Target (1:2 R:R):** Stop ₹{tech.get('stop_loss', 0):,.2f} | Target ₹{tech.get('target_price', 0):,.2f}\n"
                f"- **Indicators:** RSI: {tech['indicators'].get('rsi_14')}, ADX: {tech['indicators'].get('adx_14')}, 20d Rel. Strength: {tech['indicators'].get('relative_strength_nifty_20d')}%\n"
                f"- **Filter Notes:** {reasons}\n\n"
                f"**Fundamentals:**\n"
                f"- **P/E Ratio:** {fund.get('pe_ratio')} | **ROE:** {fund.get('roe_pct')}% | **Debt/Equity:** {fund.get('debt_to_equity')}\n"
                f"- **Market Cap:** ₹{fund.get('market_cap_cr')} Cr\n\n"
                f"> **Compliance Note:** Educational decision support only; not financial advice."
            )
            return {
                "reply": reply,
                "tool_data": {"technicals": tech, "fundamentals": fund},
                "source": "live_nse_yfinance",
                "timestamp": datetime.datetime.utcnow().isoformat(),
            }

    # General AI assistant guidance
    return {
        "reply": (
            "I am **AURA**, your quantitative AI market analyst. I can answer questions about:\n\n"
            "1. **Macro Regime:** Ask *'What is the current market regime?'* or *'How is India VIX looking?'*\n"
            "2. **Specific Equities:** Ask *'Analyze TCS'*, *'Check INFY technicals'*, or *'Review Reliance fundamentals'*\n"
            "3. **Today's Signals:** Ask *'What are today's approved trades?'*\n"
            "4. **Portfolio & Risk:** Ask *'Show my active portfolio holdings'*\n\n"
            "What would you like me to inspect?"
        ),
        "tool_data": {},
        "source": "aura_knowledge_base",
        "timestamp": datetime.datetime.utcnow().isoformat(),
    }
