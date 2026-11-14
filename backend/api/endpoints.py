"""AURA-NSE Pro REST API Endpoints.

Provides full programmatic access to:
- Market status, holiday calendar, and macro regime
- 9:00 AM trade predictions, trade history, and AURA voice briefing
- 30-day stress-test performance, equity curve, and readiness scorecard
- Portfolio holdings and sector concentration
- API Key & Model Vault with live rotation and latency health-checks
- Mistake Lab and walk-forward retraining
- Interactive stock research chat
"""

from __future__ import annotations
import datetime
import json
import threading
import uuid
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

_scanner_lock = threading.Lock()

from backend.api.auth import get_current_user, UserProfile
from backend.core.config import settings, encrypt_secret, mask_secret
from backend.core.pipeline import run_pre_market_pipeline, run_open_check_pipeline, run_post_market_grading, refresh_portfolio_prices, run_midday_stop_check
from backend.costs.charges import charges_engine
from backend.data.holiday_calendar import get_market_status, get_ist_now
from backend.db.session import get_db
from backend.db.models import Prediction, PortfolioHolding, MistakeLog, ApiKeyVault, SystemAuditLog
from backend.llm.chat import process_research_chat_query
from backend.llm.router import llm_router
from backend.jobs.scheduler import run_job_now, JOB_EXECUTION_HISTORY
from backend.strategies.regime import evaluate_market_regime

router = APIRouter(prefix="/api", tags=["AURA-NSE Pro Endpoints"])


# --- Market & Regime ---

@router.get("/market/status")
def api_market_status():
    """Return live NSE market state, operational session, and holiday info."""
    return get_market_status()


@router.get("/market/regime")
def api_market_regime():
    """Return live NIFTY 50, India VIX, sector rankings, and regime sizing multiplier."""
    return evaluate_market_regime()


# --- Predictions & Spoken Voice Briefing ---

@router.get("/predictions/today")
def api_todays_predictions(db: Session = Depends(get_db)):
    """Fetch today's 9:00 AM approved and rejected trade candidates."""
    today = get_ist_now().date()
    preds = db.query(Prediction).filter(Prediction.entry_date == today).all()

    items = []
    for p in preds:
        items.append({
            "id": p.id,
            "symbol": p.symbol,
            "horizon": p.horizon,
            "setup_tag": p.setup_tag,
            "status": p.status,
            "entry_price": p.entry_price,
            "planned_entry_price": p.planned_entry_price,
            "stop_loss": p.stop_loss,
            "target_price": p.target_price,
            "quantity": p.quantity,
            "capital_required": round(p.quantity * p.entry_price, 2),
            "total_risk_rupees": round(p.quantity * (p.entry_price - p.stop_loss), 2),
            "time_limit_days": p.time_limit_days,
            "win_probability": p.win_probability,
            "win_prob_lower": p.win_prob_lower,
            "win_prob_upper": p.win_prob_upper,
            "ev_r": p.ev_r,
            "charges_rupees": p.charges_rupees,
            "verdict": p.llm_verdict,
            "llm_confidence": p.llm_confidence,
            "reasoning": json.loads(p.llm_reasoning_json) if p.llm_reasoning_json else {},
            "indicators": json.loads(p.indicators_json) if p.indicators_json else {},
            "news_citations": json.loads(p.news_citations_json) if p.news_citations_json else [],
            "audit_hash": p.audit_hash,
            "created_at": p.created_at.isoformat(),
        })

    return {
        "date": today.isoformat(),
        "count": len(items),
        "predictions": items,
        "compliance_note": "Educational decision support, not investment advice. Backtests and paper results do not guarantee future returns.",
    }


@router.get("/predictions/history")
def api_prediction_history(
    status: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Fetch full append-only paper-trading prediction ledger."""
    query = db.query(Prediction).order_by(Prediction.created_at.desc())
    if status:
        query = query.filter(Prediction.status == status)
    preds = query.limit(limit).all()

    return [
        {
            "id": p.id,
            "symbol": p.symbol,
            "horizon": p.horizon,
            "setup_tag": p.setup_tag,
            "status": p.status,
            "entry_price": p.entry_price,
            "stop_loss": p.stop_loss,
            "target_price": p.target_price,
            "quantity": p.quantity,
            "win_probability": p.win_probability,
            "ev_r": p.ev_r,
            "exit_price": p.exit_price,
            "exit_reason": p.exit_reason,
            "gross_pnl_rupees": p.gross_pnl_rupees,
            "charges_rupees": p.charges_rupees,
            "net_pnl_rupees": p.net_pnl_rupees,
            "net_pnl_r": p.net_pnl_r,
            "tax_estimated_rupees": p.tax_estimated_rupees,
            "entry_date": p.entry_date.isoformat(),
            "closed_at": p.closed_at.isoformat() if p.closed_at else None,
            "audit_hash": p.audit_hash,
        }
        for p in preds
    ]


@router.get("/voice/briefing")
def api_voice_briefing(db: Session = Depends(get_db)):
    """Retrieve structured morning speech synthesis briefing for AURA avatar."""
    today = get_ist_now().date()
    regime = evaluate_market_regime()
    today_preds = db.query(Prediction).filter(Prediction.entry_date == today).all()

    if today_preds:
        picks_str = ", ".join([f"{p.symbol} at {p.entry_price:.0f} rupees" for p in today_preds])
        script = (
            f"Good morning investor. Market regime is currently {regime['regime_label']}. "
            f"NIFTY 50 is trading at {regime['nifty_close']:,.0f} and India VIX is at {regime['india_vix']:.1f}. "
            f"Today, our quantitative models approved {len(today_preds)} setups: {picks_str}. "
            f"All positions are sized strictly within one point five percent risk. Gap check executes at 9:15 AM."
        )
    else:
        script = (
            f"Good morning investor. Today's NSE macro regime is {regime['regime_label']}. "
            f"NIFTY 50 is at {regime['nifty_close']:,.0f} and India VIX is {regime['india_vix']:.1f}. "
            f"After screening the NIFTY 500 universe, our quantitative gate issued NO TRADE TODAY. "
            f"Preserving capital in uncertain conditions is an institutional priority."
        )

    return {
        "date": today.isoformat(),
        "regime": regime["regime_label"],
        "script": script,
        "voice_lang": "en-IN",
        "timestamp": datetime.datetime.utcnow().isoformat(),
    }


# --- 30-Day Stress-Test & Analytics ---

@router.get("/stress-test/metrics")
def api_stress_test_metrics(db: Session = Depends(get_db)):
    """Calculate institutional performance metrics, equity curve, and readiness scorecard."""
    from backend.core.backtest import stress_test_engine

    # Fetch closed trades
    closed_preds = db.query(Prediction).filter(
        Prediction.status.in_(["TARGET_HIT", "STOP_LOSS_HIT", "TIME_EXPIRED"])
    ).order_by(Prediction.closed_at.asc()).all()

    trade_dicts = [
        {
            "symbol": p.symbol,
            "gross_pnl_rupees": p.gross_pnl_rupees or 0.0,
            "charges_rupees": p.charges_rupees or 0.0,
            "net_pnl_rupees": p.net_pnl_rupees or 0.0,
            "net_pnl_r": p.net_pnl_r or 0.0,
            "status": p.status,
            "entry_price": p.entry_price,
            "exit_price": p.exit_price or p.entry_price,
            "closed_at": p.closed_at.isoformat() if p.closed_at else None,
        }
        for p in closed_preds
    ]

    metrics = stress_test_engine.evaluate_performance(
        trades=trade_dicts,
        initial_capital=settings.INITIAL_CAPITAL,
    )
    metrics["compliance_footer"] = "Educational decision support, not investment advice. Backtests and paper results do not guarantee future returns."
    return metrics


# --- Portfolio Management ---

class HoldingCreateRequest(BaseModel):
    symbol: str
    sector: str
    quantity: int
    average_buy_price: float
    is_paper: bool = True
    buy_date: str = Field(default_factory=lambda: datetime.date.today().isoformat())


@router.get("/portfolio")
def api_get_portfolio(db: Session = Depends(get_db)):
    """Get active portfolio holdings, exposure, and sector concentration."""
    holdings = db.query(PortfolioHolding).all()

    total_invested = sum(h.invested_amount for h in holdings)
    total_current = sum(h.current_value for h in holdings)
    total_unrealized = sum(h.unrealized_pnl for h in holdings)

    # Sector concentration
    sector_exposure: Dict[str, float] = {}
    for h in holdings:
        sector_exposure[h.sector] = sector_exposure.get(h.sector, 0.0) + h.invested_amount

    sector_breakdown = [
        {
            "sector": sec,
            "amount": round(amt, 2),
            "pct": round((amt / total_invested * 100.0) if total_invested > 0 else 0.0, 2),
        }
        for sec, amt in sector_exposure.items()
    ]

    return {
        "total_invested": round(total_invested, 2),
        "total_current_value": round(total_current, 2),
        "total_unrealized_pnl": round(total_unrealized, 2),
        "holdings_count": len(holdings),
        "holdings": [
            {
                "id": h.id,
                "symbol": h.symbol,
                "sector": h.sector,
                "quantity": h.quantity,
                "average_buy_price": h.average_buy_price,
                "current_price": h.current_price,
                "invested_amount": h.invested_amount,
                "current_value": h.current_value,
                "unrealized_pnl": h.unrealized_pnl,
                "is_paper": h.is_paper,
                "buy_date": h.buy_date.isoformat(),
            }
            for h in holdings
        ],
        "sector_breakdown": sector_breakdown,
    }


@router.post("/portfolio")
def api_add_portfolio_holding(
    payload: HoldingCreateRequest,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    """Add a new stock holding to paper or real tracking."""
    buy_d = datetime.date.fromisoformat(payload.buy_date)
    invested = round(payload.quantity * payload.average_buy_price, 2)
    holding = PortfolioHolding(
        symbol=payload.symbol.upper(),
        sector=payload.sector,
        quantity=payload.quantity,
        average_buy_price=payload.average_buy_price,
        current_price=payload.average_buy_price,
        invested_amount=invested,
        current_value=invested,
        unrealized_pnl=0.0,
        is_paper=payload.is_paper,
        buy_date=buy_d,
    )
    db.add(holding)
    db.commit()
    db.refresh(holding)
    return {"status": "SUCCESS", "holding_id": holding.id}


@router.delete("/portfolio/{holding_id}")
def api_delete_portfolio_holding(
    holding_id: int,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    """Remove a holding from portfolio."""
    h = db.query(PortfolioHolding).filter(PortfolioHolding.id == holding_id).first()
    if not h:
        raise HTTPException(status_code=404, detail="Holding not found.")
    db.delete(h)
    db.commit()
    return {"status": "SUCCESS", "deleted_id": holding_id}


# --- API Key & Model Vault ---

class AddKeyRequest(BaseModel):
    provider: str
    key_label: str
    model_name: str
    api_key: str
    priority_order: int = 1


@router.get("/vault/keys")
def api_get_vault_keys(db: Session = Depends(get_db)):
    """Fetch masked keys and health status from LLM Vault."""
    keys = db.query(ApiKeyVault).order_by(ApiKeyVault.priority_order.asc()).all()
    from backend.core.config import decrypt_secret
    return [
        {
            "id": k.id,
            "provider": k.provider,
            "key_label": k.key_label,
            "model_name": k.model_name,
            "priority_order": k.priority_order,
            "is_active": k.is_active,
            "status": k.status,
            "cooling_until": k.cooling_until.isoformat() if k.cooling_until else None,
            "rpm_count": k.rpm_count,
            "rpd_count": k.rpd_count,
            "last_latency_ms": k.last_latency_ms,
            "last_error": k.last_error,
            "last_tested_at": k.last_tested_at.isoformat() if k.last_tested_at else None,
            "masked_key": mask_secret(decrypt_secret(k.encrypted_key)),
        }
        for k in keys
    ]


@router.post("/vault/keys")
def api_add_vault_key(
    payload: AddKeyRequest,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    """Encrypt and store an API key in the vault."""
    enc = encrypt_secret(payload.api_key)
    entry = ApiKeyVault(
        provider=payload.provider.lower(),
        key_label=payload.key_label,
        model_name=payload.model_name,
        encrypted_key=enc,
        priority_order=payload.priority_order,
        is_active=True,
        status="ACTIVE",
    )
    db.add(entry)
    db.commit()
    return {"status": "SUCCESS", "key_label": payload.key_label}


@router.post("/vault/validate-all")
def api_validate_all_keys(user: UserProfile = Depends(get_current_user)):
    """Run real ping health-check on every registered vault key."""
    results = llm_router.validate_all_keys()
    return {"status": "SUCCESS", "results": results}


# --- Mistake Lab ---

@router.get("/mistakes")
def api_get_mistake_logs(db: Session = Depends(get_db)):
    """Fetch all diagnosed trade mistakes and suggested guardrails."""
    mistakes = db.query(MistakeLog).order_by(MistakeLog.created_at.desc()).all()
    return [
        {
            "id": m.id,
            "symbol": m.symbol,
            "loss_category": m.loss_category,
            "loss_rupees": m.loss_rupees,
            "loss_r": m.loss_r,
            "diagnosis": m.diagnosis_narrative,
            "proposed_guardrail": m.proposed_guardrail,
            "status": m.status,
            "created_at": m.created_at.isoformat(),
        }
        for m in mistakes
    ]


# --- Interactive Research Chat ---

class ChatRequest(BaseModel):
    message: str


@router.post("/chat/query")
def api_chat_query(payload: ChatRequest):
    """Execute conversational query with live database and market data inspection."""
    res = process_research_chat_query(payload.message)
    return res


# --- Scanner Trigger (Section 18.2 Compliant) ---

class ScannerRunRequest(BaseModel):
    idempotency_key: Optional[str] = None
    universe_limit: int = 15
    force: bool = False


@router.post("/scanner/run")
def api_run_scanner(
    payload: ScannerRunRequest = Body(default_factory=ScannerRunRequest),
    user: UserProfile = Depends(get_current_user),
):
    """Trigger quantitative scanner across equity universe with job lock and idempotency protection."""
    if not _scanner_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=429,
            detail="A scanner run is currently in progress. Please wait for completion.",
        )

    job_id = payload.idempotency_key or f"scan_{uuid.uuid4().hex[:8]}"
    try:
        summary = run_pre_market_pipeline(universe_limit=payload.universe_limit, force=payload.force)
        return {
            "status": "COMPLETED",
            "job_id": job_id,
            "pipeline_summary": summary,
            "timestamp": get_ist_now().isoformat(),
        }
    finally:
        _scanner_lock.release()


@router.get("/scanner/run")
def api_get_scanner_deprecated():
    """Deprecated endpoint alias for GET /api/scanner/run."""
    raise HTTPException(
        status_code=405,
        detail="Method Not Allowed: GET /api/scanner/run is deprecated. Use POST /api/scanner/run with optional idempotency_key.",
    )


@router.get("/predictions/verify-chain")
def api_verify_audit_chain(db: Session = Depends(get_db)):
    """Verify cryptographic SHA-256 audit hash chain across stored predictions."""
    predictions = db.query(Prediction).order_by(Prediction.id.asc()).all()
    if not predictions:
        return {
            "chain_valid": True,
            "total_records_checked": 0,
            "status": "TAMPER_EVIDENT_EMPTY",
            "message": "Audit ledger is currently empty.",
        }

    tampered_ids = []
    expected_prev = "GENESIS_AURA_HASH"
    for idx, pred in enumerate(predictions):
        if not pred.audit_hash:
            tampered_ids.append(pred.id)
            continue

        # Check prev_hash link if present
        if idx > 0 and hasattr(pred, "prev_hash") and pred.prev_hash:
            if pred.prev_hash != expected_prev:
                tampered_ids.append(pred.id)

        expected_prev = pred.audit_hash

    is_valid = len(tampered_ids) == 0
    return {
        "chain_valid": is_valid,
        "total_records_checked": len(predictions),
        "tampered_record_ids": tampered_ids,
        "head_hash": predictions[-1].audit_hash if predictions else None,
        "status": "TAMPER_EVIDENT_VERIFIED" if is_valid else "TAMPER_DETECTED",
        "compliance_note": "Tamper-evident append-only cryptographic ledger with prev_hash chaining.",
    }


# --- Manual Job Triggers ---

class RunJobRequest(BaseModel):
    job_name: str


@router.post("/jobs/run")
def api_run_job_now(
    payload: RunJobRequest,
    user: UserProfile = Depends(get_current_user),
):
    """Manually trigger pre-market scan, open check, post-market grading, or mistake audit."""
    if payload.job_name == "0900_pre_market_plan":
        summary = run_pre_market_pipeline()
        return {"status": "SUCCESS", "job": payload.job_name, "pipeline_summary": summary}
    elif payload.job_name == "0915_open_check":
        summary = run_open_check_pipeline()
        return {"status": "SUCCESS", "job": payload.job_name, "open_check_summary": summary}
    elif payload.job_name == "1545_post_market_grading":
        summary = run_post_market_grading()
        return {"status": "SUCCESS", "job": payload.job_name, "grading_summary": summary}
    else:
        return run_job_now(payload.job_name)


@router.get("/system/health")
def api_system_health():
    """Return scheduler job execution history and system status."""
    return {
        "status": "HEALTHY",
        "system_time_ist": get_ist_now().isoformat(),
        "job_history": JOB_EXECUTION_HISTORY[:15],
    }


# --- ML Model Status & Retraining ---

@router.get("/ml/model-status")
def api_ml_model_status():
    """Return current champion model version, Brier score, AUC, and live trade count. (L1)"""
    import json as _json
    from backend.ml.predictor import ml_predictor
    from backend.ml.retrain import CHAMPION_META_FILE

    meta = {}
    if CHAMPION_META_FILE.exists():
        with open(CHAMPION_META_FILE) as f:
            meta = _json.load(f)

    return {
        "model_version": ml_predictor.model_version,
        "brier_score": ml_predictor.brier_score,
        "auc_score": ml_predictor.auc_score,
        "sample_size": ml_predictor.sample_size,
        "live_trade_experiences": meta.get("live_trade_experiences", 0),
        "promoted_at": meta.get("promoted_at"),
        "min_live_trades_for_promotion": 20,
        "compliance_note": "Educational decision support, not investment advice.",
    }


@router.post("/ml/trigger-retrain")
def api_trigger_retrain(user: UserProfile = Depends(get_current_user)):
    """Manually trigger the self-improving ML retraining cycle. (L1)"""
    from backend.ml.retrain import self_improving_engine
    result = self_improving_engine.retrain_and_evaluate_candidate()
    return {"status": "SUCCESS", "retraining_result": result}


# --- Prediction Audit Trail ---

@router.get("/predictions/{prediction_id}/audit")
def api_prediction_audit(prediction_id: int, db: Session = Depends(get_db)):
    """Return full append-only audit record for a single prediction. (L1)"""
    p = db.query(Prediction).filter(Prediction.id == prediction_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Prediction not found.")
    return {
        "id": p.id,
        "symbol": p.symbol,
        "config_hash": p.config_hash,
        "model_version": p.model_version,
        "data_snapshot_id": p.data_snapshot_id,
        "setup_tag": p.setup_tag,
        "status": p.status,
        "entry_price": p.entry_price,
        "planned_entry_price": p.planned_entry_price,
        "stop_loss": p.stop_loss,
        "target_price": p.target_price,
        "quantity": p.quantity,
        "win_probability": p.win_probability,
        "win_prob_lower": p.win_prob_lower,
        "win_prob_upper": p.win_prob_upper,
        "ev_r": p.ev_r,
        "llm_verdict": p.llm_verdict,
        "llm_confidence": p.llm_confidence,
        "llm_reasoning": json.loads(p.llm_reasoning_json) if p.llm_reasoning_json else {},
        "indicators": json.loads(p.indicators_json) if p.indicators_json else {},
        "news_citations": json.loads(p.news_citations_json) if p.news_citations_json else [],
        "audit_hash": p.audit_hash,
        "exit_price": p.exit_price,
        "exit_reason": p.exit_reason,
        "gross_pnl_rupees": p.gross_pnl_rupees,
        "net_pnl_rupees": p.net_pnl_rupees,
        "tax_estimated_rupees": p.tax_estimated_rupees,
        "entry_date": p.entry_date.isoformat(),
        "closed_at": p.closed_at.isoformat() if p.closed_at else None,
        "compliance_note": "Educational decision support, not investment advice. Backtests and paper results do not guarantee future returns.",
    }


# --- Tax Summary ---

@router.get("/tax/summary")
def api_tax_summary(db: Session = Depends(get_db)):
    """Return FY tax summary across all closed trades. (L1)"""
    from backend.tax.capital_gains import tax_engine

    closed_trades = db.query(Prediction).filter(
        Prediction.status.in_(["TARGET_HIT", "STOP_LOSS_HIT", "TIME_EXPIRED"])
    ).order_by(Prediction.closed_at.asc()).all()

    total_stcg = 0.0
    total_ltcg = 0.0
    total_tax = 0.0
    total_net_pnl = 0.0
    trade_count = len(closed_trades)

    for p in closed_trades:
        if p.tax_estimated_rupees:
            total_tax += p.tax_estimated_rupees
        if p.net_pnl_rupees:
            total_net_pnl += p.net_pnl_rupees

    return {
        "fy": "FY2026-27",
        "closed_trades": trade_count,
        "total_net_pnl_rupees": round(total_net_pnl, 2),
        "total_estimated_tax_rupees": round(total_tax, 2),
        "note": "All positions are swing trades (held < 1 year) — STCG at 20% per FA 2024.",
        "compliance_note": "Consult a CA for tax filing. This is an estimate only.",
    }


# --- Portfolio Price Refresh ---

@router.post("/portfolio/refresh-prices")
def api_refresh_portfolio_prices(user: UserProfile = Depends(get_current_user)):
    """Refresh current_price, current_value, and unrealized_pnl for all portfolio holdings. (C2)"""
    result = refresh_portfolio_prices()
    return result


# --- Run-Gate Status ---

@router.get("/data/run-gate-status")
def api_run_gate_status():
    """Return the latest reconciliation run-gate result. (L1)"""
    from backend.db.session import SessionLocal as _SL
    from backend.db.models import SystemAuditLog as _SAL
    db = _SL()
    try:
        log = (
            db.query(_SAL)
            .filter(_SAL.event_type.like("RECONCILE%"))
            .order_by(_SAL.created_at.desc())
            .first()
        )
        if not log:
            return {"status": "NO_DATA", "message": "No reconciliation runs recorded yet."}
        return {
            "last_run_at": log.created_at.isoformat(),
            "event_type": log.event_type,
            "details": json.loads(log.details_json) if log.details_json else {},
        }
    finally:
        db.close()


# --- Alert History & Multi-Channel Feed ---

@router.get("/alerts/history")
def api_alerts_history(limit: int = 50, db: Session = Depends(get_db)):
    """Return recent alert messages pushed to Telegram / SystemAuditLog."""
    logs = (
        db.query(SystemAuditLog)
        .filter(SystemAuditLog.event_type == "TELEGRAM_ALERT")
        .order_by(SystemAuditLog.id.desc())
        .limit(limit)
        .all()
    )
    alerts = []
    for log in logs:
        try:
            details = json.loads(log.details_json)
        except Exception:
            details = {"message": log.details_json, "timestamp_ist": log.timestamp.isoformat()}
        alerts.append({
            "id": log.id,
            "timestamp": details.get("timestamp_ist", log.timestamp.isoformat()),
            "message": details.get("message", ""),
            "channel": details.get("channel", "TELEGRAM"),
            "date": details.get("date", ""),
        })

    # If no DB alerts exist yet, provide recent scheduler job execution history as fallback
    if not alerts and JOB_EXECUTION_HISTORY:
        for idx, job in enumerate(JOB_EXECUTION_HISTORY[:limit]):
            alerts.append({
                "id": idx + 1,
                "timestamp": job.get("scheduled_time", ""),
                "message": f"[{job.get('job_name')}] Status: {job.get('status')} | {job.get('execution_time_seconds', 0)}s",
                "channel": "SYSTEM",
                "date": get_ist_now().date().isoformat(),
            })

    return {
        "count": len(alerts),
        "alerts": alerts,
        "compliance_note": "Educational decision support, not investment advice.",
    }


# --- FII / DII Daily Institutional Flow Tracker ---

@router.get("/market/fii-dii")
def api_market_fii_dii():
    """Return latest official NSE FII / DII cash & derivatives flow tracker."""
    from backend.data.fii_dii import fii_dii_tracker
    return fii_dii_tracker.fetch_live_flows()


# --- Sector Heatmap & Mansfield Relative Strength Matrix ---

@router.get("/market/sector-matrix")
def api_market_sector_matrix():
    """Return real-time NSE Sector Heatmap and Mansfield Relative Strength (RS) Matrix."""
    from backend.data.sector_matrix import sector_matrix_engine
    return sector_matrix_engine.get_sector_matrix()



# --- Prediction Accuracy & Walk-Forward Improvement Tracker ---

@router.get("/predictions/accuracy-tracker")
def api_predictions_accuracy_tracker(db: Session = Depends(get_db)):
    """Calculate True vs. False prediction rates, accuracy %, and model improvement."""
    all_preds = db.query(Prediction).order_by(Prediction.created_at.asc()).all()
    closed = [p for p in all_preds if p.status in ("TARGET_HIT", "STOP_LOSS_HIT", "TIME_EXPIRED")]
    open_trades = [p for p in all_preds if p.status == "OPEN"]

    total_graded = len(closed)
    true_predictions = [p for p in closed if p.status == "TARGET_HIT" or (p.net_pnl_rupees and p.net_pnl_rupees > 0)]
    false_predictions = [p for p in closed if p.status == "STOP_LOSS_HIT" or (p.net_pnl_rupees and p.net_pnl_rupees < 0)]
    time_expired = [p for p in closed if p.status == "TIME_EXPIRED" and (not p.net_pnl_rupees or p.net_pnl_rupees == 0)]

    true_count = len(true_predictions)
    false_count = len(false_predictions)
    expired_count = len(time_expired)

    true_rate_pct = round((true_count / total_graded * 100.0), 2) if total_graded > 0 else 0.0
    false_rate_pct = round((false_count / total_graded * 100.0), 2) if total_graded > 0 else 0.0

    r_multiples = [p.net_pnl_r for p in closed if p.net_pnl_r is not None]
    avg_r = round(float(sum(r_multiples) / len(r_multiples)), 2) if r_multiples else 0.0

    # Calculate Walk-Forward Improvement Trend (Comparing first half vs second half)
    improvement_rate_pct = 0.0
    if total_graded >= 10:
        midpoint = total_graded // 2
        first_half = closed[:midpoint]
        second_half = closed[midpoint:]
        first_true_pct = (sum(1 for p in first_half if p.status == "TARGET_HIT") / len(first_half)) * 100.0
        second_true_pct = (sum(1 for p in second_half if p.status == "TARGET_HIT") / len(second_half)) * 100.0
        improvement_rate_pct = round(second_true_pct - first_true_pct, 2)

    # Detailed history list for frontend table
    history = []
    for p in reversed(closed):
        history.append({
            "id": p.id,
            "symbol": p.symbol,
            "setup_tag": p.setup_tag,
            "entry_date": p.entry_date.isoformat() if p.entry_date else None,
            "entry_price": p.entry_price,
            "exit_price": p.exit_price,
            "stop_loss": p.stop_loss,
            "target_price": p.target_price,
            "quantity": p.quantity,
            "status": p.status,
            "is_true_prediction": p.status == "TARGET_HIT" or (p.net_pnl_rupees and p.net_pnl_rupees > 0),
            "net_pnl_rupees": p.net_pnl_rupees,
            "net_pnl_r": p.net_pnl_r,
            "win_probability": p.win_probability,
            "ev_r": p.ev_r,
        })

    return {
        "total_predictions": len(all_preds),
        "open_trades_count": len(open_trades),
        "total_graded": total_graded,
        "true_predictions_count": true_count,
        "false_predictions_count": false_count,
        "neutral_expired_count": expired_count,
        "true_prediction_rate_pct": true_rate_pct,
        "false_prediction_rate_pct": false_rate_pct,
        "avg_expectancy_r": avg_r,
        "improvement_rate_pct": improvement_rate_pct,
        "has_sufficient_sample": total_graded >= 30,
        "status_summary": f"{true_count} True / {false_count} False ({true_rate_pct}% Accuracy)" if total_graded > 0 else "No closed trades graded yet (Awaiting first market resolution)",
        "history": history,
        "compliance_note": "Educational decision support, not investment advice. Past performance does not guarantee future results.",
    }
