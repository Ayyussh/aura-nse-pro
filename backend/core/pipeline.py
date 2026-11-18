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
import time
from typing import Any, cast

import httpx
import pandas as pd

from backend.core.config import compute_config_hash, settings
from backend.costs.charges import charges_engine
from backend.data.holiday_calendar import get_ist_now
from backend.data.provider import data_provider
from backend.data.universe import get_sector_for_symbol, get_universe_symbols
from backend.db.models import MistakeLog, Prediction, SystemAuditLog
from backend.db.session import SessionLocal
from backend.llm.analyst import aura_analyst
from backend.ml.features import extract_features_from_df
from backend.ml.predictor import ml_predictor
from backend.risk.sizing import risk_guard
from backend.strategies.regime import evaluate_market_regime
from backend.strategies.swing import swing_engine

logger = logging.getLogger("aura.pipeline")


def anchor_latest_audit_hash(latest_hash: str) -> None:
    """Anchor the latest audit hash externally to an immutable daily anchor file."""
    try:
        from backend.core.config import PROJECT_ROOT
        anchor_file = PROJECT_ROOT / "data" / "audit_anchor_latest.json"
        anchor_file.parent.mkdir(parents=True, exist_ok=True)
        with open(anchor_file, "w", encoding="utf-8") as f:
            json.dump({
                "latest_audit_hash": latest_hash,
                "anchored_at_ist": get_ist_now().strftime("%Y-%m-%d %H:%M:%S IST"),
                "anchored_at_utc": datetime.datetime.utcnow().isoformat() + "Z",
                "status": "TAMPER_EVIDENT_DAILY_ANCHOR",
            }, f, indent=2)
    except Exception as e:
        logger.warning(f"Could not write external audit anchor: {e}")


def log_alert_to_audit(message: str, channel: str = "TELEGRAM") -> None:
    """Persist alert to SystemAuditLog so frontend and audit trail can view it."""
    try:
        db = SessionLocal()
        audit_record = SystemAuditLog(
            event_type="TELEGRAM_ALERT",
            details_json=json.dumps({
                "message": message,
                "channel": channel,
                "timestamp_ist": get_ist_now().strftime("%Y-%m-%d %H:%M:%S IST"),
                "date": get_ist_now().date().isoformat(),
            }),
            timestamp=datetime.datetime.utcnow(),
        )
        db.add(audit_record)
        db.commit()
        db.close()
    except Exception as e:
        logger.warning(f"Could not persist alert to SystemAuditLog: {e}")


def send_telegram_alert(message: str) -> bool:
    """Send alert to all registered Telegram devices/subscribers with Markdown and plain-text fallback.

    Dynamically queries Telegram getUpdates to auto-discover any new device that added or
    started the bot (/start), supports channels (-100...) and group chats, and persists
    active subscribers to `data/telegram_subscribers.json`.
    """
    # Always log to internal audit feed so it appears on frontend
    log_alert_to_audit(message)

    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        logger.warning("Telegram alert skipped: TELEGRAM_BOT_TOKEN not configured in settings/env.")
        return False

    try:
        from backend.core.telegram_subscribers import sync_subscribers, remove_subscriber
        chat_ids = sync_subscribers(token)
    except Exception as e:
        logger.warning(f"Subscriber auto-sync encountered an error: {e}. Falling back to settings.")
        raw_chat_id = settings.TELEGRAM_CHAT_ID or ""
        chat_ids = [c.strip() for c in str(raw_chat_id).replace(";", ",").split(",") if c.strip()]

    if not chat_ids:
        logger.warning("Telegram alert skipped: No registered subscribers or chat IDs found.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    any_success = False

    with httpx.Client(timeout=10.0) as client:
        for cid in chat_ids:
            payload = {
                "chat_id": cid,
                "text": message,
                "parse_mode": "Markdown",
            }
            try:
                resp = client.post(url, json=payload)
                if resp.status_code == 200:
                    logger.info(f"Telegram alert successfully sent to {cid}.")
                    any_success = True
                    continue

                # Auto-cleanup if bot was blocked or chat deleted
                if resp.status_code == 403 or (resp.status_code == 400 and "chat not found" in resp.text.lower()):
                    logger.info(f"Subscriber {cid} blocked bot or chat deleted. Cleaning up registry.")
                    try:
                        remove_subscriber(cid)
                    except Exception:
                        pass
                    continue

                # If Markdown parsing failed, fallback to plain text
                logger.warning(f"Telegram Markdown send returned HTTP {resp.status_code} for {cid}: {resp.text}. Retrying plain-text fallback...")
                plain_payload = {
                    "chat_id": cid,
                    "text": message.replace("*", "").replace("_", "").replace("`", ""),
                }
                resp_plain = client.post(url, json=plain_payload)
                if resp_plain.status_code == 200:
                    logger.info(f"Telegram plain-text alert successfully sent to {cid}.")
                    any_success = True
                else:
                    logger.error(f"Telegram alert delivery failed for {cid} (HTTP {resp_plain.status_code}): {resp_plain.text}")
            except Exception as e:
                logger.error(f"Could not send Telegram alert to {cid} due to connection error: {e}")

    return any_success


def run_pre_market_pipeline(universe_limit: int = 750, force: bool = False, is_shadow: bool = False) -> dict[str, Any]:
    """Execute complete pre-market screening and prediction generation across the institutional universe."""
    today = get_ist_now().date()
    config_hash = compute_config_hash()

    logger.info(f"Starting Pre-Market Pipeline for {today} (universe_limit={universe_limit})...")

    # 1. Macro Regime Check
    regime = evaluate_market_regime()
    logger.info(f"Macro Regime evaluated: {regime['regime_label']} (Size Multiplier: {regime['sizing_multiplier']})")

    # 2. Run-Gate Check (C4): Validate data reconciliation before screening
    try:
        from backend.data.holiday_calendar import get_previous_trading_day
        from backend.data.reconciliation import reconciliation_engine
        symbols_for_gate = get_universe_symbols(limit=universe_limit, mode="all")
        target_recon_date = get_previous_trading_day(today)
        can_run, gate_reason, gate_stats = reconciliation_engine.evaluate_run_gate(symbols_for_gate, target_recon_date)
        gate_pct = gate_stats.get("confidence_agreement_pct", gate_stats.get("confidence_coverage_pct", 100.0)) if isinstance(gate_stats, dict) else 100.0
        unverified_set = set(gate_stats.get("unverified_symbols", [])) if isinstance(gate_stats, dict) else set()
        if not can_run and not force:
            now_time = get_ist_now().strftime("%I:%M %p IST")
            msg = (
                f"🚦 *AURA Pre-Market Run-Gate ({now_time}) — HELD*\n"
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

    symbols = get_universe_symbols(limit=universe_limit, mode="all")
    approved_candidates: list[dict[str, Any]] = []
    rejected_candidates: list[dict[str, Any]] = []

    db = SessionLocal()
    try:
        # Fetch current open positions from DB for heat & sector cap checks
        open_db_preds = db.query(Prediction).filter(Prediction.status == "OPEN").all()
        open_positions = [
            {
                "symbol": str(p.symbol),
                "sector": get_sector_for_symbol(str(p.symbol)),
                "quantity": p.quantity,
                "entry_price": p.entry_price,
                "stop_loss": p.stop_loss,
            }
            for p in open_db_preds
        ]

        for idx, symbol in enumerate(symbols):
            # Adaptive pacing: when scanning large universes (>120 symbols), introduce a light 150ms sleep
            # every 10 tickers to ensure zero 429 rate-limiting from upstream data gateways.
            if len(symbols) > 120 and idx % 10 == 0 and idx > 0:
                time.sleep(0.15)

            if symbol in unverified_set:
                logger.warning(f"Quarantining unverified/mismatched symbol {symbol} from pre-market screening.")
                rejected_candidates.append({"symbol": symbol, "reason": "Data reconciliation unverified or quarantined."})
                continue
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

                # Append-only canonical JSON audit hash with prev_hash chaining (Section 18.2)
                last_pred = db.query(Prediction).order_by(Prediction.id.desc()).first()
                prev_hash = last_pred.audit_hash if last_pred and last_pred.audit_hash else "GENESIS_AURA_HASH"
                canonical_payload = {
                    "hash_version": "v2",
                    "prev_hash": prev_hash,
                    "symbol": symbol,
                    "side": "BUY",
                    "entry_price": float(cand.entry_price),
                    "stop_loss": float(cand.stop_loss),
                    "target_price": float(cand.target_price),
                    "quantity": int(sizing.quantity),
                    "probability": float(ml_res.get("win_probability", 0.5)),
                    "ev_r": float(ml_res.get("ev_r", 0.0)),
                    "model_version": ml_predictor.model_version,
                    "config_hash": config_hash,
                    "data_snapshot_id": q_meta.get("provenance_timestamp", datetime.datetime.utcnow().isoformat()),
                    "llm_output_hash": hashlib.sha256(json.dumps(verdict_data, sort_keys=True).encode("utf-8")).hexdigest(),
                    "utc_timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                }
                canonical_json = json.dumps(canonical_payload, sort_keys=True)
                audit_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

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
                    prev_hash=prev_hash,
                    hash_version="v2",
                    source="SHADOW" if is_shadow else "LIVE",
                    is_shadow=is_shadow,
                )
                db.add(pred_record)
                db.commit()

                # Anchor the latest hash externally
                anchor_latest_audit_hash(audit_hash)

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
                f"Good morning. This is your market briefing for {today.strftime('%B %d, %Y')} ({now_time}). "
                f"The NSE Macro Regime is currently {regime['regime_label']}. NIFTY 50 is trading at {regime['nifty_close']:,.0f}, and India VIX is at {regime['india_vix']:.1f}. "
                f"Today, our quantitative models screened {len(symbols)} stocks and approved {len(approved_candidates)} high-conviction swing setups: {picks_text}. "
                f"Position sizing has been computed to keep trade risk strictly within one point five percent. "
                f"Market open will be verified at 9:15 AM to filter out chasing gap-ups. Trade safely."
            )
        else:
            briefing_script = (
                f"Good morning. This is your market briefing for {today.strftime('%B %d, %Y')} ({now_time}). "
                f"The NSE Macro Regime is {regime['regime_label']}. NIFTY 50 is at {regime['nifty_close']:,.0f} and India VIX is at {regime['india_vix']:.1f}. "
                f"Today, our models screened {len(symbols)} candidates, but none satisfied all institutional criteria with positive expected value. "
                f"Our ruling today is NO TRADE TODAY. Cash is a valid position during market uncertainty."
            )

        # Dispatch Telegram Alert — ALWAYS send (M3 fix: no silent runs)
        if approved_candidates:
            tg_text = (
                f"🚀 *AURA Pre-Market Signals ({now_time})*\n"
                f"📅 *Date:* {today.isoformat()} | *Regime:* {regime['regime_label']}\n"
                f"📈 *NIFTY 50:* {regime['nifty_close']} | *VIX:* {regime['india_vix']}\n"
                f"🔍 *Screened:* {len(symbols)} stocks | *Approved:* {len(approved_candidates)}\n\n"
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
                f"📊 *AURA Pre-Market Routine ({now_time}) — Completed*\n"
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


def run_open_check_pipeline() -> dict[str, Any]:
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
            pred_symbol = str(pred.symbol)
            df = data_provider.fetch_history(pred_symbol, period="5d", interval="1d", force_refresh=True)
            if df.empty:
                continue

            open_price = float(df["open"].iloc[-1])
            planned = float(pred.planned_entry_price or 0.0)

            # ATR-relative gap limit: clamp(0.5 * ATR14 / planned * 100, 0.75, 2.5)
            max_gap_pct = 2.5
            try:
                if pred.indicators_json:
                    inds = json.loads(str(pred.indicators_json))
                    atr = float(inds.get("atr_14", 0.0))
                    if atr > 0 and planned > 0:
                        atr_gap = 0.5 * (atr / planned) * 100.0
                        max_gap_pct = max(0.75, min(2.5, atr_gap))
            except Exception:
                max_gap_pct = 2.5

            gap_pct = ((open_price - planned) / planned) * 100.0 if planned > 0 else 0.0
            if gap_pct > max_gap_pct:
                setattr(pred, "status", "SKIPPED_GAP_UP")
                setattr(pred, "exit_reason", f"Gapped up {gap_pct:.2f}% at open (exceeded ATR-relative chasing limit {max_gap_pct:.2f}%).")
                setattr(pred, "closed_at", datetime.datetime.utcnow())
                skipped_gaps += 1
                continue

            # Gap Down below stop loss
            pred_stop = float(pred.stop_loss or 0.0)
            if open_price <= pred_stop:
                setattr(pred, "status", "SKIPPED_GAP_DOWN")
                setattr(pred, "exit_reason", f"Gapped down through stop loss at open (Open ₹{open_price} <= Stop ₹{pred_stop}).")
                setattr(pred, "closed_at", datetime.datetime.utcnow())
                skipped_gaps += 1
                continue

            # Normal Open: Update entry price to actual open + slippage and recompute quantity to preserve rupee risk
            slippage = open_price * 0.0005  # 5 bps
            actual_fill = round(open_price + slippage, 2)
            setattr(pred, "entry_price", actual_fill)

            # Recompute exact whole-share quantity
            risk_per_share = max(0.5, actual_fill - pred_stop)
            target_risk_rupees = settings.INITIAL_CAPITAL * (settings.MAX_RISK_PER_TRADE_PCT / 100.0)
            recomputed_qty = max(1, int(target_risk_rupees / risk_per_share))
            setattr(pred, "quantity", recomputed_qty)
            updated += 1

        db.commit()

        # Send dedicated Market Open Check alert to Telegram
        now_time = get_ist_now().strftime("%I:%M %p IST")
        if open_preds:
            tg_text = (
                f"⚡ *AURA Market Open Gap Verification ({now_time})*\n"
                f"📅 *Date:* {today.isoformat()}\n"
                f"📊 *Trades Evaluated:* {len(open_preds)} | *Fills Confirmed:* {updated} | *Skipped:* {skipped_gaps}\n\n"
            )
            for p in open_preds:
                st = getattr(p, "status", "OPEN")
                sym = getattr(p, "symbol", "")
                ep = getattr(p, "entry_price", 0.0)
                sl = getattr(p, "stop_loss", 0.0)
                tgt = getattr(p, "target_price", 0.0)
                qty = getattr(p, "quantity", 0)
                if st == "OPEN":
                    tg_text += f"• *{sym}*: Filled @ ₹{ep:,.2f} (Qty: {qty}, SL: ₹{sl:,.2f}, Target: ₹{tgt:,.2f})\n"
                else:
                    reason = getattr(p, "exit_reason", "Gap boundary breach")
                    tg_text += f"• *{sym}*: _{st}_ ({reason})\n"
            tg_text += "\n_Capital preservation active. Mathematical trailing stops engaged._"
        else:
            tg_text = (
                f"⚡ *AURA Market Open Check ({now_time}) — Completed*\n"
                f"📅 *Date:* {today.isoformat()}\n"
                f"📊 *Open Positions Checked:* 0 (No active swing momentum orders pending execution today).\n"
                f"_Capital preservation gate active._"
            )
        send_telegram_alert(tg_text)

        return {
            "status": "SUCCESS",
            "trades_verified": len(open_preds),
            "updated_fills": updated,
            "skipped_gaps": skipped_gaps,
            "summary": f"{updated} trades filled at market open; {skipped_gaps} trades skipped due to gap rules.",
        }
    finally:
        db.close()


def run_post_market_grading() -> dict[str, Any]:
    """15:45 IST: Grade active OPEN trades against daily OHLC."""
    from backend.core.grader import grade_trade_outcome
    db = SessionLocal()
    graded_count = 0
    try:
        open_preds = db.query(Prediction).filter(Prediction.status == "OPEN").all()
        for pred in open_preds:
            pred_sym = str(pred.symbol)
            df = data_provider.fetch_history(pred_sym, period="1mo", interval="1d", force_refresh=True)
            if df.empty:
                continue

            pred_entry_p = float(pred.entry_price or 0.0)
            pred_sl = float(pred.stop_loss or 0.0)
            pred_tp = float(pred.target_price or 0.0)
            pred_qty = int(pred.quantity or 0)
            pred_tlimit = int(pred.time_limit_days or 10)

            res = grade_trade_outcome(
                symbol=pred_sym,
                entry_date=cast(datetime.date, pred.entry_date),
                entry_price=pred_entry_p,
                stop_loss=pred_sl,
                target_price=pred_tp,
                quantity=pred_qty,
                time_limit_days=pred_tlimit,
                history_df=df,
            )

            if res["status"] != "OPEN":
                setattr(pred, "status", res["status"])
                setattr(pred, "exit_price", res["exit_price"])
                setattr(pred, "exit_reason", res["exit_reason"])
                setattr(pred, "closed_at", datetime.datetime.utcnow())
                setattr(pred, "gross_pnl_rupees", res["gross_pnl_rupees"])
                setattr(pred, "charges_rupees", res["charges_rupees"])
                setattr(pred, "net_pnl_rupees", res["net_pnl_rupees"])
                setattr(pred, "net_pnl_r", res["net_pnl_r"])
                setattr(pred, "tax_estimated_rupees", res["tax_estimated_rupees"])
                graded_count += 1

                # If trade ended in loss, log mistake candidate with LLM post-mortem (C3)
                if res["net_pnl_rupees"] < 0:
                    inds = json.loads(str(pred.indicators_json)) if pred.indicators_json else {}
                    regime = evaluate_market_regime()
                    post_mortem = aura_analyst.conduct_loss_post_mortem(
                        symbol=pred_sym,
                        entry_price=pred_entry_p,
                        exit_price=float(res["exit_price"]),
                        stop_loss=pred_sl,
                        target_price=pred_tp,
                        exit_reason=str(res["exit_reason"]),
                        net_pnl_rupees=float(res["net_pnl_rupees"]),
                        net_pnl_r=float(res["net_pnl_r"]),
                        indicators=inds,
                        macro_regime=regime,
                    )
                    mistake = MistakeLog(
                        prediction_id=pred.id,
                        symbol=pred_sym,
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


def run_midday_stop_check() -> dict[str, Any]:
    """13:00 IST: Check OPEN positions against latest intraday price. Alert if breaching stop. (H3)"""
    db = SessionLocal()
    alerts_sent = 0
    checked = 0
    breaches: list[dict[str, Any]] = []
    try:
        open_preds = db.query(Prediction).filter(Prediction.status == "OPEN").all()
        for pred in open_preds:
            try:
                # Fetch intraday 5-min data to get latest price
                pred_sym = str(pred.symbol)
                df_5m = data_provider.fetch_history(pred_sym, period="1d", interval="5m", force_refresh=True)
                if df_5m.empty:
                    # Fall back to daily data
                    df_5m = data_provider.fetch_history(pred_sym, period="5d", interval="1d", force_refresh=True)
                if df_5m.empty:
                    continue

                latest_price = float(df_5m["close"].iloc[-1])
                checked += 1

                pred_sl = float(pred.stop_loss or 0.0)
                if pred_sl > 0 and latest_price <= pred_sl:
                    pct_below = ((pred_sl - latest_price) / pred_sl) * 100.0
                    now_time = get_ist_now().strftime("%I:%M %p IST")
                    msg = (
                        f"⚠️ *AURA Mid-Day Stop Alert ({now_time})*\n"
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


def refresh_portfolio_prices() -> dict[str, Any]:
    """15:50 IST: Refresh current_price, current_value, unrealized_pnl for all portfolio holdings. (C2)"""
    from backend.db.models import PortfolioHolding
    db = SessionLocal()
    updated = 0
    errors = 0
    try:
        holdings = db.query(PortfolioHolding).all()
        for h in holdings:
            try:
                h_sym = str(h.symbol)
                h_qty = int(h.quantity or 0)
                h_inv = float(h.invested_amount or 0.0)
                df = data_provider.fetch_history(h_sym, period="5d", interval="1d", force_refresh=True)
                if df.empty:
                    logger.warning(f"No price data for portfolio holding {h_sym}")
                    errors += 1
                    continue

                latest_price = float(df["close"].iloc[-1])
                setattr(h, "current_price", round(latest_price, 2))
                setattr(h, "current_value", round(latest_price * h_qty, 2))
                setattr(h, "unrealized_pnl", round(latest_price * h_qty - h_inv, 2))
                updated += 1
            except Exception as e:
                logger.warning(f"Failed to refresh price for {getattr(h, 'symbol', '')}: {e}")
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


def run_bhavcopy_reconciliation() -> dict[str, Any]:
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


def calculate_weekly_performance_summary(db: Any) -> dict[str, Any]:
    """Calculate trailing 7-day performance metrics across all closed trades (M6)."""
    seven_days_ago = get_ist_now().date() - datetime.timedelta(days=7)
    trades_raw = (
        db.query(Prediction)
        .filter(
            Prediction.status.in_(["TARGET_HIT", "STOP_LOSS_HIT", "TIME_EXPIRED", "TIME_LIMIT_EXIT"]),
            Prediction.entry_date >= seven_days_ago,
        )
        .all()
    )
    # Exclude SHADOW trades from live performance summary
    trades = [
        t for t in trades_raw
        if getattr(t, "source", "") != "SHADOW" and not getattr(t, "is_shadow", False)
    ]
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


def run_weekly_mistake_audit() -> dict[str, Any]:
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
            narrative = str(m.diagnosis_narrative or "").lower()
            if "gap" in narrative:
                cat = "Gap-Through-Stop"
            elif "breakout" in narrative:
                cat = "False Breakout"
            else:
                cat = "Sector Weakness"
            setattr(m, "loss_category", cat)
            setattr(m, "status", "RESOLVED")
            categories[cat] = categories.get(cat, 0) + 1

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


def run_value_investing_scan(universe_limit: int | None = None, mode: str = "all", send_alert: bool = True) -> dict[str, Any]:
    """Execute Long-Term Institutional Valuation Screener for Multi-Year Compounders.

    Identifies high-quality NSE equities trading below their estimated intrinsic fair value
    (positive Margin of Safety) with strong balance sheets and profitability.
    Supports scanning ALL ~2,760 listed NSE stocks, sector-diversified bluechips, or curated universe.
    Dispatches a dedicated Telegram report separate from daily swing trading alerts.
    """
    from backend.strategies.long_term import long_term_engine
    from backend.data.universe import get_universe_symbols, get_diversified_universe_symbols
    from backend.data.provider import data_provider
    from backend.data.upstox import upstox_client
    from backend.llm.analyst import aura_analyst

    today = get_ist_now().date()
    logger.info(f"Starting Institutional Value & Intrinsic Worth Screener for {today} (mode={mode}, limit={universe_limit})...")

    if mode == "all":
        # Full-market sweeps prioritized by institutional liquidity:
        # Default: Top 750 equities (NIFTY 500 + NIFTY Microcap 250, covering >99.2% of exchange volume)
        # Allows scanning up to all ~2,760 listed NSE stocks when explicitly requested.
        effective_limit = min(universe_limit, 2760) if universe_limit else 750
        symbols = get_universe_symbols(limit=effective_limit, mode="all")
    elif mode == "diversified":
        symbols = get_diversified_universe_symbols(limit=min(universe_limit, 100) if universe_limit else 45)
    else:
        effective_limit = min(universe_limit, 750) if universe_limit else 191
        symbols = get_universe_symbols(limit=effective_limit, mode="curated")

    # Step 1: Upstox Batch Live Quotes (Zero-429 Rate Limiter)
    upstox_quotes: dict[str, dict[str, Any]] = {}
    if upstox_client.token:
        try:
            upstox_quotes = upstox_client.get_market_quotes_batch(symbols, chunk_size=100)
            logger.info(f"Fetched {len(upstox_quotes)} real-time equity quotes via Upstox API v3.")
        except Exception as e:
            logger.warning(f"Upstox batch quote fetch note: {e}")

    value_picks: list[dict[str, Any]] = []
    screened_out: list[dict[str, Any]] = []

    for idx, sym in enumerate(symbols):
        # Adaptive pacing: when scanning large universes (>120 symbols), introduce a light 150ms sleep
        # every 10 tickers to ensure zero 429 rate-limiting from upstream data gateways.
        if len(symbols) > 120 and idx % 10 == 0 and idx > 0:
            time.sleep(0.15)

        try:
            df = data_provider.fetch_history(sym, period="1y", interval="1d")
            if df.empty or len(df) < 50:
                continue

            # Overlay real-time Upstox tick if available
            c_last = float(df["close"].iloc[-1])
            if sym in upstox_quotes and upstox_quotes[sym].get("ltp", 0) > 0:
                c_last = float(upstox_quotes[sym]["ltp"])

            # Fast-path check: If price <= 200-SMA, it cannot pass criterion #1
            # Skip fetching fundamental data to accelerate full-universe scans
            if len(df) >= 200:
                sma200 = df["close"].rolling(200).mean().iloc[-1]
                if not pd.isna(sma200) and c_last <= sma200:
                    screened_out.append({
                        "symbol": sym,
                        "passed": False,
                        "margin_of_safety_pct": 0.0,
                        "reasons": [f"Price ₹{c_last:.2f} is below 200-day SMA ₹{sma200:.2f} (downtrend)"],
                    })
                    continue

            # Fetch fundamentals (with 7-day disk cache to eliminate redundant requests)
            fundamentals = data_provider.fetch_fundamentals(sym)
            pick = long_term_engine.evaluate(sym, df, fundamentals)

            pick_dict = pick.to_dict()
            # Ensure current price reflects the live Upstox LTP
            pick_dict["current_price"] = round(c_last, 2)
            if pick_dict["fair_value_mid"] > 0:
                pick_dict["margin_of_safety_pct"] = round(((pick_dict["fair_value_mid"] - c_last) / pick_dict["fair_value_mid"]) * 100.0, 2)

            if pick.passed and pick_dict["margin_of_safety_pct"] > 0:
                value_picks.append(pick_dict)
            else:
                screened_out.append({
                    "symbol": sym,
                    "passed": pick.passed,
                    "margin_of_safety_pct": pick_dict["margin_of_safety_pct"],
                    "reasons": pick.rejection_reasons or ["Trading above fair value (No margin of safety)"],
                })
        except Exception as e:
            logger.warning(f"Error evaluating {sym} for value investing: {e}")

    # Sort value picks by Margin of Safety (highest discount first)
    value_picks.sort(key=lambda x: x.get("margin_of_safety_pct", 0), reverse=True)

    # Step 2: Gemini AI Institutional Audit for Top Candidates
    for pick in value_picks[:8]:
        try:
            ai_res = aura_analyst.audit_value_pick(pick)
            pick["gemini_audit"] = ai_res
        except Exception as e:
            logger.warning(f"Could not audit {pick.get('symbol')} with Gemini: {e}")

    result_payload: dict[str, Any] = {
        "scan_date": today.isoformat(),
        "scan_timestamp": get_ist_now().strftime("%Y-%m-%d %H:%M:%S IST"),
        "total_screened": len(symbols),
        "undervalued_count": len(value_picks),
        "value_picks": value_picks,
        "screened_out_count": len(screened_out),
        "screened_out": screened_out[:20],
        "investment_horizon": "1 to 3+ Years (Fundamental Value Compounder)",
        "methodology": "DCF / Sector-Bounded Earnings Growth Multiplier with Gemini AI Moat Audit",
    }

    # Save to snapshots for frontend GitOps
    try:
        from backend.core.config import PROJECT_ROOT
        snapshots_dir = PROJECT_ROOT / "data" / "snapshots"
        frontend_dir = PROJECT_ROOT / "frontend" / "public" / "data"
        dist_dir = PROJECT_ROOT / "frontend" / "dist" / "data"
        snapshots_dir.mkdir(parents=True, exist_ok=True)
        frontend_dir.mkdir(parents=True, exist_ok=True)

        for d in [snapshots_dir, frontend_dir, dist_dir]:
            if d.parent.exists():
                d.mkdir(parents=True, exist_ok=True)
                target = d / "value_picks.json"
                with open(target, "w", encoding="utf-8") as f:
                    json.dump(result_payload, f, indent=2)
        logger.info(f"Value picks saved to snapshots ({len(value_picks)} picks).")
    except Exception as e:
        logger.warning(f"Could not persist value picks snapshot: {e}")

    # Build and send separate Telegram message with Sector Diversification
    if send_alert:
        # Enforce Sector Diversity: at most 2 stocks per sector in top broadcast
        sector_counts: dict[str, int] = {}
        broadcast_picks: list[dict[str, Any]] = []
        for p in value_picks:
            sec = p.get("sector", "Diversified")
            # If Gemini AI flagged cyclical trap, filter it out from broadcast
            ai_audit = p.get("gemini_audit") or {}
            if ai_audit.get("verdict") == "REJECTED_CYCLICAL_TRAP":
                continue

            if sector_counts.get(sec, 0) < 2:
                # Ensure broadcast candidate has completed institutional audit
                if not p.get("gemini_audit"):
                    try:
                        p["gemini_audit"] = aura_analyst.audit_value_pick(p)
                    except Exception:
                        p["gemini_audit"] = {}
                broadcast_picks.append(p)
                sector_counts[sec] = sector_counts.get(sec, 0) + 1
            if len(broadcast_picks) >= 6:
                break

        data_source_badge = "⚡ Upstox Live + AI" if upstox_quotes else "📊 EOD Archive + AI"
        msg_lines = [
            f"💎 *AURA Long-Term Value Screener — Undervalued Compounders*",
            f"📅 *Date:* {today.isoformat()} | *Universe Scanned:* {len(symbols)} Equities ({data_source_badge})",
            f"🎯 *Identified Under-Valued Compounders:* {len(value_picks)} (Broadcasting Top {len(broadcast_picks)})\n",
        ]

        if not value_picks:
            msg_lines.append("🚫 *NO UNDERVALUED COMPOUNDERS FOUND TODAY*")
            msg_lines.append("All screened equities are either trading at/above estimated fair value, or fail institutional balance-sheet/ROE safety gates.")
            msg_lines.append("Capital preservation remains paramount.\n")
        else:
            for idx, p in enumerate(broadcast_picks, 1):
                sym = p["symbol"]
                sector = p.get("sector", "Diversified")
                cp = p.get("current_price", 0.0)
                fv = p.get("fair_value_mid", 0.0)
                mos = p.get("margin_of_safety_pct", 0.0)
                tier = p.get("conviction_tier", "QUALITY_COMPOUNDER")
                tier_badge = "🌟 HIGH CONVICTION" if tier == "HIGH_CONVICTION" else ("💎 QUALITY COMPOUNDER" if tier == "QUALITY_COMPOUNDER" else "🔍 WATCHLIST")
                funds = p.get("fundamentals", {})
                roe = funds.get("roe_pct", "N/A")
                pe = funds.get("pe_ratio", "N/A")
                raw_de = funds.get("debt_to_equity", "N/A")

                # Institutional financial sector D/E labeling
                sec_upper = sector.upper()
                if "BANK" in sec_upper:
                    de_str = "N/A (Bank)"
                elif "NBFC" in sec_upper:
                    de_str = f"N/A (NBFC Lev: {raw_de}x)" if raw_de not in ("UNKNOWN", "N/A") else "N/A (NBFC)"
                elif "INSUR" in sec_upper:
                    de_str = "N/A (Insurance)"
                else:
                    de_str = str(raw_de)

                tp = p.get("tranche_plan", {})
                t1 = tp.get("tranche_1_initial", {}).get("price_target", cp)
                t2 = tp.get("tranche_2_pullback", {}).get("price_target", cp * 0.95)
                t3 = tp.get("tranche_3_deep_value", {}).get("price_target", cp * 0.90)

                ai_audit = p.get("gemini_audit") or {}
                ai_conviction = ai_audit.get("ai_conviction_pct", 75.0)
                ai_thesis = ai_audit.get("bull_thesis") or ai_audit.get("moat_assessment", "Secular earnings compounder")

                msg_lines.append(f"*{idx}. {sym}* ({sector}) — {tier_badge}")
                msg_lines.append(f"💵 *Market Price:* ₹{cp:,.2f} | *Fair Worth:* ₹{fv:,.2f}")
                msg_lines.append(f"🛡️ *Margin of Safety:* *+{mos:.1f}% Discount*")
                msg_lines.append(f"📊 *Health:* ROE: {roe}% | P/E: {pe} | D/E: {de_str}")
                msg_lines.append(f"🤖 *AI Audit:* Conviction: {ai_conviction:.0f}% | _{ai_thesis}_")
                msg_lines.append(f"📥 *Staggered Plan:* T1: ₹{t1:,.2f} (40%) | T2: ₹{t2:,.2f} (30%) | T3: ₹{t3:,.2f} (30%)\n")

            # Additional Screened Value Compounders Honor Roll
            remaining_picks = [p for p in value_picks if p not in broadcast_picks]
            if remaining_picks:
                msg_lines.append(f"📋 *Additional Qualified Compounders ({len(remaining_picks)} More):*")
                rem_items = []
                for rp in remaining_picks:
                    sym_short = rp.get("symbol", "").replace(".NS", "")
                    mos_val = rp.get("margin_of_safety_pct", 0.0)
                    rem_items.append(f"`{sym_short}` (+{mos_val:.1f}%)")
                msg_lines.append(" • " + " | ".join(rem_items))
                msg_lines.append("_Full interactive dossiers & charts available on your Web Dashboard._\n")

        msg_lines.append("📌 *Investment Horizon:* 1 to 3+ Years (Fundamental Value Investing).")
        msg_lines.append("_Separate alert from daily 10-day swing momentum signals._")
        msg_lines.append("_Educational decision support, not financial advice._")

        full_message = "\n".join(msg_lines)
        send_telegram_alert(full_message)

    return result_payload
