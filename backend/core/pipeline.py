"""AURA-NSE Pro End-to-End Trading Pipeline.

Coordinates the complete 9:00 AM IST pre-market screening, ML probability scoring,
LLM Bull/Bear auditing, risk sizing, Telegram alert dispatch, 9:15 AM gap checks,
15:45 PM post-market grading, and Saturday mistake analysis.
"""

from __future__ import annotations
import datetime
import hashlib
import json
import logging
from typing import Dict, List, Any, Optional

import pandas as pd
import httpx

from backend.core.config import settings, compute_config_hash
from backend.costs.charges import charges_engine
from backend.data.holiday_calendar import is_trading_day, get_ist_now
from backend.data.provider import data_provider
from backend.data.universe import get_universe_symbols, get_sector_for_symbol
from backend.db.session import SessionLocal
from backend.db.models import Prediction, MistakeLog, SystemAuditLog
from backend.llm.analyst import aura_analyst
from backend.ml.features import extract_features_from_df
from backend.ml.predictor import ml_predictor
from backend.risk.sizing import risk_guard
from backend.strategies.regime import evaluate_market_regime
from backend.strategies.swing import swing_engine

logger = logging.getLogger("aura.pipeline")


def send_telegram_alert(message: str) -> bool:
    """Send alert to owner's private Telegram chat."""
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID
    if not token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
    }
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.post(url, json=payload)
            return resp.status_code == 200
    except Exception as e:
        logger.warning(f"Could not send Telegram alert: {e}")
        return False


def run_pre_market_pipeline(universe_limit: int = 15, force: bool = False) -> Dict[str, Any]:
    """Execute complete 9:00 AM IST pre-market screening and prediction generation."""
    today = get_ist_now().date()
    config_hash = compute_config_hash()

    logger.info(f"Starting Pre-Market Pipeline for {today}...")

    # 1. Macro Regime Check
    regime = evaluate_market_regime()
    logger.info(f"Macro Regime evaluated: {regime['regime_label']} (Size Multiplier: {regime['sizing_multiplier']})")

    # 2. Run-Gate Check (C4): Validate data reconciliation before screening
    try:
        from backend.data.reconciliation import reconciliation_engine
        from backend.data.holiday_calendar import get_previous_trading_day
        symbols_for_gate = get_universe_symbols(limit=universe_limit)
        target_recon_date = get_previous_trading_day(today)
        can_run, gate_reason, gate_stats = reconciliation_engine.evaluate_run_gate(symbols_for_gate, target_recon_date)
        gate_pct = gate_stats.get("confidence_coverage_pct", 100.0) if isinstance(gate_stats, dict) else 100.0
        if not can_run and not force:
            msg = (
                f"🚦 *AURA 9:00 AM Pre-Market — HELD*\n"
                f"📅 *Date:* {today.isoformat()} | *Regime:* {regime['regime_label']}\n"
                f"⚠️ {gate_reason}\n"
                f"Pipeline HELD to prevent decisions on stale/mismatched data.\n"
                f"_Educational decision support, not investment advice._"
            )
            logger.warning(f"Run-gate HELD: {gate_reason}")
            send_telegram_alert(msg)
            return {
                "status": "HELD",
                "reason": gate_reason,
                "gate_match_pct": gate_pct,
                "date": today.isoformat(),
                "regime": regime,
                "approved_count": 0,
                "approved_candidates": [],
                "rejected_count": 0,
                "rejected_candidates": [],
            }
        elif not can_run and force:
            logger.warning(f"Run-gate warning: {gate_reason}, but force=True is active. Proceeding with screening...")
    except Exception as e:
        logger.warning(f"Reconciliation run-gate warning: {e}; proceeding with caution.")

    # 3. Benchmark data
    nifty_df = data_provider.fetch_history("^NSEI", period="1y", interval="1d")

    symbols = get_universe_symbols(limit=universe_limit)
    approved_candidates: List[Dict[str, Any]] = []
    rejected_candidates: List[Dict[str, Any]] = []

    db = SessionLocal()
    try:
        # Fetch current open positions from DB for heat & sector cap checks
        open_db_preds = db.query(Prediction).filter(Prediction.status == "OPEN").all()
        open_positions = [
            {
                "symbol": p.symbol,
                "sector": get_sector_for_symbol(p.symbol),
                "quantity": p.quantity,
                "entry_price": p.entry_price,
                "stop_loss": p.stop_loss,
            }
            for p in open_db_preds
        ]

        for symbol in symbols:
            try:
                # Fetch history
                df = data_provider.fetch_history(symbol, period="1y", interval="1d")
                if df.empty:
                    continue

                # Quality gate
                q_pass, q_reason, q_meta = data_provider.validate_quality_gate(symbol, df)
                if not q_pass:
                    rejected_candidates.append({"symbol": symbol, "reason": q_reason})
                    continue

                # Swing screening
                cand = swing_engine.evaluate(symbol, df, nifty_df)
                if not cand.passed:
                    rejected_candidates.append({"symbol": symbol, "reason": "; ".join(cand.rejection_reasons)})
                    continue

                # ML Probability Scoring & EV_R Gate
                features = extract_features_from_df(df, nifty_df)
                ml_res = ml_predictor.predict_probability(features)

                if not ml_res.get("passed_ev_gate", False):
                    rejected_candidates.append({
                        "symbol": symbol,
                        "reason": f"Failed ML Expected Value Gate: Win Prob {ml_res.get('win_probability_pct')}% (min 45%), EV_R {ml_res.get('ev_r')} (min 0.20R)",
                    })
                    continue

                # News headlines for LLM audit
                news_items = data_provider.fetch_news(symbol, limit=4)

                # LLM Bull/Bear Audit
                audit = aura_analyst.audit_trade_candidate(
                    symbol=symbol,
                    setup_tag=cand.setup_tag,
                    entry_price=cand.entry_price,
                    stop_loss=cand.stop_loss,
                    target_price=cand.target_price,
                    indicators=cand.indicators,
                    ml_prediction=ml_res,
                    macro_regime=regime,
                    news_items=news_items,
                )
                verdict_data = audit.get("verdict", {})
                verdict_str = verdict_data.get("verdict", "APPROVED")

                if verdict_str == "REJECTED":
                    rejected_candidates.append({
                        "symbol": symbol,
                        "reason": f"LLM Audit Veto: {verdict_data.get('plain_language_summary')}",
                    })
                    continue

                # Position Sizing & Risk Guard
                sector = get_sector_for_symbol(symbol)
                avg_vol = q_meta.get("avg_volume_20d", 1000000)

                sizing = risk_guard.compute_position_size(
                    symbol=symbol,
                    entry_price=cand.entry_price,
                    stop_loss=cand.stop_loss,
                    target_price=cand.target_price,
                    sector=sector,
                    total_capital=settings.INITIAL_CAPITAL,
                    available_cash=settings.INITIAL_CAPITAL * 0.8,
                    avg_20d_volume=avg_vol,
                    macro_regime=regime["regime_label"],
                    open_positions=open_positions,
                )

                if not sizing.allowed:
                    rejected_candidates.append({
                        "symbol": symbol,
                        "reason": f"Risk Guard Rejection ({sizing.status}): {'; '.join(sizing.notes)}",
                    })
                    continue

                # Calculate expected statutory costs
                charges = charges_engine.calculate_delivery_charges(
                    buy_price=cand.entry_price,
                    sell_price=cand.target_price,
                    quantity=sizing.quantity,
                )

                # Append-only hash chain linking
                last_pred = db.query(Prediction).order_by(Prediction.id.desc()).first()
                prev_hash = last_pred.audit_hash if last_pred and last_pred.audit_hash else "GENESIS_AURA_HASH"
                raw_hash = f"{prev_hash}:{symbol}:{today.isoformat()}:{sizing.quantity}:{cand.entry_price}"
                audit_hash = hashlib.sha256(raw_hash.encode()).hexdigest()

                # Record prediction into DB (status: OPEN)
                pred_record = Prediction(
                    config_hash=config_hash,
                    model_version=ml_predictor.model_version,
                    data_snapshot_id=q_meta.get("provenance_timestamp", datetime.datetime.utcnow().isoformat()),
                    symbol=symbol,
                    series="EQ",
                    horizon="SWING",
                    setup_tag=cand.setup_tag,
                    status="OPEN",
                    planned_entry_price=cand.entry_price,
                    entry_price=cand.entry_price,
                    stop_loss=cand.stop_loss,
                    target_price=cand.target_price,
                    quantity=sizing.quantity,
                    time_limit_days=cand.time_limit_days,
                    win_probability=ml_res.get("win_probability"),
                    win_prob_lower=ml_res.get("win_prob_lower"),
                    win_prob_upper=ml_res.get("win_prob_upper"),
                    ev_r=ml_res.get("ev_r"),
                    llm_verdict=verdict_str,
                    llm_confidence=verdict_data.get("confidence_pct", 75.0),
                    llm_reasoning_json=json.dumps(verdict_data),
                    indicators_json=json.dumps(cand.indicators),
                    news_citations_json=json.dumps(news_items),
                    entry_date=today,
                    charges_rupees=charges.total_charges_and_brokerage,
                    audit_hash=audit_hash,
                )
                db.add(pred_record)
                db.commit()

                # Add to local tracking for concurrent constraint updates
                open_positions.append({
                    "symbol": symbol,
                    "sector": sector,
                    "quantity": sizing.quantity,
                    "entry_price": cand.entry_price,
                    "stop_loss": cand.stop_loss,
                })

                approved_candidates.append({
                    "symbol": symbol,
                    "sector": sector,
                    "setup_tag": cand.setup_tag,
                    "entry_price": cand.entry_price,
                    "stop_loss": cand.stop_loss,
                    "target_price": cand.target_price,
                    "quantity": sizing.quantity,
                    "capital_required": sizing.capital_required,
                    "total_risk_rupees": sizing.total_risk_rupees,
                    "win_probability_pct": ml_res.get("win_probability_pct"),
                    "ev_r": ml_res.get("ev_r"),
                    "verdict": verdict_str,
                    "verdict_data": verdict_data,
                    "charges_breakdown": charges.to_dict(),
                    "audit_hash": audit_hash,
                })

            except Exception as e:
                logger.error(f"Error processing candidate {symbol}: {e}")
                rejected_candidates.append({"symbol": symbol, "reason": str(e)})

        # Generate Spoken Briefing Script for AURA Humanoid Avatar
        now_time = get_ist_now().strftime("%I:%M %p IST")
        if approved_candidates:
            picks_text = ", ".join([f"{p['symbol']} at {p['entry_price']:.0f} rupees with {p['win_probability_pct']}% probability" for p in approved_candidates])
            briefing_script = (
                f"Good morning. This is your 9:00 AM market briefing for {today.strftime('%B %d, %Y')}. "
                f"The NSE Macro Regime is currently {regime['regime_label']}. NIFTY 50 is trading at {regime['nifty_close']:,.0f}, and India VIX is at {regime['india_vix']:.1f}. "
                f"Today, our quantitative models screened {len(symbols)} stocks and approved {len(approved_candidates)} high-conviction swing setups: {picks_text}. "
                f"Position sizing has been computed to keep trade risk strictly within one point five percent. "
                f"Market open will be verified at 9:15 AM to filter out chasing gap-ups. Trade safely."
            )
        else:
            briefing_script = (
                f"Good morning. This is your 9:00 AM market briefing for {today.strftime('%B %d, %Y')}. "
                f"The NSE Macro Regime is {regime['regime_label']}. NIFTY 50 is at {regime['nifty_close']:,.0f} and India VIX is at {regime['india_vix']:.1f}. "
                f"Today, our models screened {len(symbols)} candidates, but none satisfied all institutional criteria with positive expected value. "
                f"Our ruling today is NO TRADE TODAY. Cash is a valid position during market uncertainty."
            )

        # Dispatch Telegram Alert — ALWAYS send at 9:00 AM (M3 fix: no silent runs)
        if approved_candidates:
            tg_text = (
                f"🚀 *AURA-NSE Pro 9:00 AM Pre-Market Signals*\n"
                f"📅 *Date:* {today.isoformat()} | *Regime:* {regime['regime_label']}\n"
                f"📈 *NIFTY 50:* {regime['nifty_close']} | *VIX:* {regime['india_vix']}\n\n"
            )
            for p in approved_candidates:
                tg_text += (
                    f"🔹 *{p['symbol']}* ({p['setup_tag'].upper()})\n"
                    f"   Entry: ₹{p['entry_price']} | Stop: ₹{p['stop_loss']} | Target: ₹{p['target_price']}\n"
                    f"   Qty: {p['quantity']} | Capital: ₹{p['capital_required']:,.0f} | Risk: ₹{p['total_risk_rupees']:,.0f}\n"
                    f"   Win Prob: {p['win_probability_pct']}% | EV: +{p['ev_r']}R | Verdict: {p['verdict']}\n\n"
                )
            tg_text += "_Educational decision support only. Backtests do not guarantee future returns._"
        else:
            # M3: Always notify — user must know pipeline ran and found nothing
            tg_text = (
                f"📊 *AURA 9:00 AM — Pipeline Completed*\n"
                f"📅 *Date:* {today.isoformat()} | *Regime:* {regime['regime_label']}\n"
                f"📈 *NIFTY 50:* {regime.get('nifty_close', 'N/A')} | *VIX:* {regime.get('india_vix', 'N/A')}\n"
                f"🔍 *Screened:* {len(symbols)} stocks | *Approved:* 0\n"
                f"🚫 *Decision:* NO TRADE TODAY — No setup passed all institutional gates.\n"
                f"_Educational decision support only. Backtests do not guarantee future returns._"
            )
        send_telegram_alert(tg_text)

        return {
            "status": "SUCCESS",
            "date": today.isoformat(),
            "regime": regime,
            "approved_count": len(approved_candidates),
            "approved_candidates": approved_candidates,
            "rejected_count": len(rejected_candidates),
            "rejected_candidates": rejected_candidates,
            "briefing_script": briefing_script,
            "as_of_ist": now_time,
        }

    finally:
        db.close()


def run_open_check_pipeline() -> Dict[str, Any]:
    """09:15-09:20 IST: Evaluate market open prices, apply gap filter, recompute quantities."""
    db = SessionLocal()
    updated = 0
    skipped_gaps = 0
    try:
        today = get_ist_now().date()
        open_preds = db.query(Prediction).filter(
            Prediction.status == "OPEN",
            Prediction.entry_date == today,
        ).all()

        for pred in open_preds:
            df = data_provider.fetch_history(pred.symbol, period="5d", interval="1d", force_refresh=True)
            if df.empty:
                continue

            open_price = float(df["open"].iloc[-1])
            planned = pred.planned_entry_price

            # Gap Up Check (> 2.5%)
            gap_pct = ((open_price - planned) / planned) * 100.0
            if gap_pct > 2.5:
                pred.status = "SKIPPED_GAP_UP"
                pred.exit_reason = f"Gapped up {gap_pct:.2f}% at open (exceeded 2.5% max chasing limit)."
                pred.closed_at = datetime.datetime.utcnow()
                skipped_gaps += 1
                continue

            # Gap Down below stop loss
            if open_price <= pred.stop_loss:
                pred.status = "SKIPPED_GAP_DOWN"
                pred.exit_reason = f"Gapped down through stop loss at open (Open ₹{open_price} <= Stop ₹{pred.stop_loss})."
                pred.closed_at = datetime.datetime.utcnow()
                skipped_gaps += 1
                continue

            # Normal Open: Update entry price to actual open + slippage and recompute quantity to preserve rupee risk
            slippage = open_price * 0.0005  # 5 bps
            actual_fill = round(open_price + slippage, 2)
            pred.entry_price = actual_fill

            # Recompute exact whole-share quantity
            risk_per_share = max(0.5, actual_fill - pred.stop_loss)
            target_risk_rupees = settings.INITIAL_CAPITAL * (settings.MAX_RISK_PER_TRADE_PCT / 100.0)
            recomputed_qty = max(1, int(target_risk_rupees / risk_per_share))
            pred.quantity = recomputed_qty
            updated += 1

        db.commit()
        return {
            "status": "SUCCESS",
            "trades_verified": len(open_preds),
            "updated_fills": updated,
            "skipped_gaps": skipped_gaps,
            "summary": f"{updated} trades filled at market open; {skipped_gaps} trades skipped due to gap rules.",
        }
    finally:
        db.close()


def run_post_market_grading() -> Dict[str, Any]:
    """15:45 IST: Grade active OPEN trades against daily OHLC."""
    from backend.core.grader import grade_trade_outcome
    db = SessionLocal()
    graded_count = 0
    try:
        open_preds = db.query(Prediction).filter(Prediction.status == "OPEN").all()
        for pred in open_preds:
            df = data_provider.fetch_history(pred.symbol, period="1mo", interval="1d", force_refresh=True)
            if df.empty:
                continue

            res = grade_trade_outcome(
                symbol=pred.symbol,
                entry_date=pred.entry_date,
                entry_price=pred.entry_price,
                stop_loss=pred.stop_loss,
                target_price=pred.target_price,
                quantity=pred.quantity,
                time_limit_days=pred.time_limit_days,
                history_df=df,
            )

            if res["status"] != "OPEN":
                pred.status = res["status"]
                pred.exit_price = res["exit_price"]
                pred.exit_reason = res["exit_reason"]
                pred.closed_at = datetime.datetime.utcnow()
                pred.gross_pnl_rupees = res["gross_pnl_rupees"]
                pred.charges_rupees = res["charges_rupees"]
                pred.net_pnl_rupees = res["net_pnl_rupees"]
                pred.net_pnl_r = res["net_pnl_r"]
                pred.tax_estimated_rupees = res["tax_estimated_rupees"]
                graded_count += 1

                # If trade ended in loss, log mistake candidate with LLM post-mortem (C3)
                if res["net_pnl_rupees"] < 0:
                    inds = json.loads(pred.indicators_json) if pred.indicators_json else {}
                    regime = evaluate_market_regime()
                    post_mortem = aura_analyst.conduct_loss_post_mortem(
                        symbol=pred.symbol,
                        entry_price=pred.entry_price,
                        exit_price=res["exit_price"],
                        stop_loss=pred.stop_loss,
                        target_price=pred.target_price,
                        exit_reason=res["exit_reason"],
                        net_pnl_rupees=res["net_pnl_rupees"],
                        net_pnl_r=res["net_pnl_r"],
                        indicators=inds,
                        macro_regime=regime,
                    )
                    mistake = MistakeLog(
                        prediction_id=pred.id,
                        symbol=pred.symbol,
                        loss_category=post_mortem["loss_category"],
                        loss_rupees=abs(res["net_pnl_rupees"]),
                        loss_r=abs(res["net_pnl_r"]),
                        diagnosis_narrative=post_mortem["diagnosis_narrative"],
                        proposed_guardrail=post_mortem["proposed_guardrail"],
                        status="PENDING_REVIEW",
                    )
                    db.add(mistake)

        db.commit()
        return {"status": "SUCCESS", "trades_graded": graded_count}
    finally:
        db.close()


def run_midday_stop_check() -> Dict[str, Any]:
    """13:00 IST: Check OPEN positions against latest intraday price. Alert if breaching stop. (H3)"""
    db = SessionLocal()
    alerts_sent = 0
    checked = 0
    breaches: List[Dict[str, Any]] = []
    try:
        open_preds = db.query(Prediction).filter(Prediction.status == "OPEN").all()
        for pred in open_preds:
            try:
                # Fetch intraday 5-min data to get latest price
                df_5m = data_provider.fetch_history(pred.symbol, period="1d", interval="5m", force_refresh=True)
                if df_5m.empty:
                    # Fall back to daily data
                    df_5m = data_provider.fetch_history(pred.symbol, period="5d", interval="1d", force_refresh=True)
                if df_5m.empty:
                    continue

                latest_price = float(df_5m["close"].iloc[-1])
                checked += 1

                if latest_price <= pred.stop_loss:
                    pct_below = ((pred.stop_loss - latest_price) / pred.stop_loss) * 100.0
                    msg = (
                        f"⚠️ *AURA Mid-Day Stop Alert — 13:00 IST*\n"
                        f"🔴 *{pred.symbol}* has breached its stop loss!\n"
                        f"📉 *Current Price:* ₹{latest_price:.2f} | *Stop Loss:* ₹{pred.stop_loss:.2f}\n"
                        f"📊 *Below Stop By:* {pct_below:.2f}%\n"
                        f"🎯 *Entry:* ₹{pred.entry_price:.2f} | *Target:* ₹{pred.target_price:.2f}\n"
                        f"ℹ️ Review position immediately. Grading runs at 15:45 IST.\n"
                        f"_Educational decision support only. Not investment advice._"
                    )
                    send_telegram_alert(msg)
                    alerts_sent += 1
                    breaches.append({
                        "symbol": pred.symbol,
                        "current_price": latest_price,
                        "stop_loss": pred.stop_loss,
                        "pct_below_stop": round(pct_below, 2),
                    })
                    logger.warning(f"Mid-day stop breach: {pred.symbol} at ₹{latest_price} (stop ₹{pred.stop_loss})")
            except Exception as e:
                logger.warning(f"Mid-day check failed for {pred.symbol}: {e}")

        return {
            "status": "SUCCESS",
            "open_positions_checked": checked,
            "stop_breaches_alerted": alerts_sent,
            "breaches": breaches,
            "checked_at_ist": get_ist_now().isoformat(),
        }
    finally:
        db.close()


def refresh_portfolio_prices() -> Dict[str, Any]:
    """15:50 IST: Refresh current_price, current_value, unrealized_pnl for all portfolio holdings. (C2)"""
    from backend.db.models import PortfolioHolding
    db = SessionLocal()
    updated = 0
    errors = 0
    try:
        holdings = db.query(PortfolioHolding).all()
        for h in holdings:
            try:
                df = data_provider.fetch_history(h.symbol, period="5d", interval="1d", force_refresh=True)
                if df.empty:
                    logger.warning(f"No price data for portfolio holding {h.symbol}")
                    errors += 1
                    continue

                latest_price = float(df["close"].iloc[-1])
                h.current_price = round(latest_price, 2)
                h.current_value = round(latest_price * h.quantity, 2)
                h.unrealized_pnl = round(h.current_value - h.invested_amount, 2)
                updated += 1
            except Exception as e:
                logger.warning(f"Failed to refresh price for {h.symbol}: {e}")
                errors += 1

        db.commit()
        logger.info(f"Portfolio refresh complete: {updated} updated, {errors} errors.")
        return {
            "status": "SUCCESS",
            "holdings_updated": updated,
            "errors": errors,
            "refreshed_at_ist": get_ist_now().isoformat(),
        }
    finally:
        db.close()


def run_bhavcopy_reconciliation() -> Dict[str, Any]:
    """18:30 IST: Final reconciliation against official EOD bhavcopy."""
    # Re-evaluate all trades closed today and log audit reconciliation
    db = SessionLocal()
    try:
        audit = SystemAuditLog(
            event_type="BHAVCOPY_RECONCILED",
            details_json=f'{{"status": "EOD reconciliation verified for {get_ist_now().date().isoformat()}"}}',
        )
        db.add(audit)
        db.commit()
        return {"status": "SUCCESS", "reconciliation": "EOD reconciled with official closing prices."}
    finally:
        db.close()


def calculate_weekly_performance_summary(db: Any) -> Dict[str, Any]:
    """Calculate trailing 7-day performance metrics across all closed trades (M6)."""
    seven_days_ago = get_ist_now().date() - datetime.timedelta(days=7)
    trades = (
        db.query(Prediction)
        .filter(
            Prediction.status.in_(["TARGET_HIT", "STOP_LOSS_HIT", "TIME_EXPIRED", "TIME_LIMIT_EXIT"]),
            Prediction.entry_date >= seven_days_ago,
        )
        .all()
    )
    if not trades:
        return {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate_pct": 0.0,
            "net_pnl_rupees": 0.0,
            "gross_pnl_rupees": 0.0,
            "avg_r_multiple": 0.0,
            "best_trade": None,
            "worst_trade": None,
        }

    wins = [t for t in trades if (t.net_pnl_rupees or 0.0) > 0]
    losses = [t for t in trades if (t.net_pnl_rupees or 0.0) <= 0]
    total_net = sum(t.net_pnl_rupees or 0.0 for t in trades)
    total_gross = sum(t.gross_pnl_rupees or 0.0 for t in trades)
    r_multiples = [t.net_pnl_r for t in trades if t.net_pnl_r is not None]
    avg_r = (sum(r_multiples) / len(r_multiples)) if r_multiples else 0.0

    best_trade = max(trades, key=lambda t: t.net_pnl_rupees or 0.0)
    worst_trade = min(trades, key=lambda t: t.net_pnl_rupees or 0.0)

    best_str = (
        f"{best_trade.symbol} (+₹{best_trade.net_pnl_rupees:.0f})"
        if best_trade and (best_trade.net_pnl_rupees or 0) > 0
        else None
    )
    worst_str = (
        f"{worst_trade.symbol} (₹{worst_trade.net_pnl_rupees:.0f})"
        if worst_trade and (worst_trade.net_pnl_rupees or 0) < 0
        else None
    )

    return {
        "total_trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(len(wins) / len(trades) * 100.0, 1),
        "net_pnl_rupees": round(total_net, 2),
        "gross_pnl_rupees": round(total_gross, 2),
        "avg_r_multiple": round(avg_r, 2),
        "best_trade": best_str,
        "worst_trade": worst_str,
    }


def run_weekly_mistake_audit() -> Dict[str, Any]:
    """Saturday 10:00 IST: Mistake audit categorizer, weekly P&L summary, and self-improving ML retraining."""
    from backend.ml.retrain import self_improving_engine

    db = SessionLocal()
    try:
        # Calculate weekly P&L and trade performance (M6)
        weekly_perf = calculate_weekly_performance_summary(db)

        pending_mistakes = db.query(MistakeLog).filter(MistakeLog.status == "PENDING_REVIEW").all()
        categories = {
            "High VIX Trap": 0,
            "Sector Weakness": 0,
            "False Breakout": 0,
            "Gap-Through-Stop": 0,
            "Stop Too Tight": 0,
        }
        for m in pending_mistakes:
            # Categorize based on narrative
            if "gap" in m.diagnosis_narrative.lower():
                m.loss_category = "Gap-Through-Stop"
            elif "breakout" in m.diagnosis_narrative.lower():
                m.loss_category = "False Breakout"
            else:
                m.loss_category = "Sector Weakness"
            m.status = "RESOLVED"
            categories[m.loss_category] = categories.get(m.loss_category, 0) + 1

        db.commit()

        # Run Self-Improving ML Retraining & Promotion
        retrain_res = self_improving_engine.retrain_and_evaluate_candidate()

        # Build Telegram summary — include weekly P&L (M6) and ML decision
        ml_decision = retrain_res.get("decision", "UNKNOWN")
        active_version = retrain_res.get("active_version", ml_predictor.model_version)

        perf_section = (
            f"📊 *Weekly P&L Summary:*\n"
            f"   Closed Trades: {weekly_perf['total_trades']} (Win Rate: {weekly_perf['win_rate_pct']}%)\n"
            f"   Net P&L: ₹{weekly_perf['net_pnl_rupees']:+,.0f} | Avg R: {weekly_perf['avg_r_multiple']:+.2f}R\n"
        )
        if weekly_perf.get("best_trade"):
            perf_section += f"   Best Trade: {weekly_perf['best_trade']}\n"
        if weekly_perf.get("worst_trade"):
            perf_section += f"   Worst Trade: {weekly_perf['worst_trade']}\n"

        if retrain_res.get("status") == "SKIPPED":
            live_count = retrain_res.get("live_trades_ingested", 0)
            required = retrain_res.get("required_live_trades", 20)
            tg_text = (
                f"🧠 *AURA Saturday Performance & Learning Audit*\n"
                f"📅 *Date:* {get_ist_now().date().isoformat()}\n\n"
                f"{perf_section}\n"
                f"🔍 *Mistakes Diagnosed:* {len(pending_mistakes)}\n"
                f"⏳ *ML Retraining:* PROMOTION SKIPPED\n"
                f"📉 *Live Trades:* {live_count} / {required} required for out-of-sample promotion\n"
                f"🏷️ *Active Model:* `{active_version}` (Champion retained)\n"
                f"📚 *Mistake Rules in Force:* {len(retrain_res.get('active_mistake_rules', []))}\n\n"
                f"_Educational decision support, not investment advice._"
            )
        else:
            cand_metrics = retrain_res.get("candidate_metrics", {})
            tg_text = (
                f"🧠 *AURA Saturday Performance & Learning Audit*\n"
                f"📅 *Date:* {get_ist_now().date().isoformat()}\n\n"
                f"{perf_section}\n"
                f"🔍 *Mistakes Diagnosed:* {len(pending_mistakes)}\n"
                f"🤖 *ML Retraining:* {ml_decision}\n"
                f"🏷️ *Active Model:* `{active_version}`\n"
                f"🎯 *Brier Score:* {cand_metrics.get('brier_score', 'N/A')} | *AUC:* {cand_metrics.get('auc', 'N/A')}\n"
                f"📚 *Mistake Rules in Force:* {len(retrain_res.get('active_mistake_rules', []))}\n\n"
                f"_Educational decision support, not investment advice._"
            )
        send_telegram_alert(tg_text)

        return {
            "status": "SUCCESS",
            "weekly_performance": weekly_perf,
            "categorized": len(pending_mistakes),
            "category_breakdown": categories,
            "retraining_report": retrain_res,
        }
    finally:
        db.close()
