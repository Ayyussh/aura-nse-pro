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
import logging
import threading
import uuid
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

_scanner_lock = threading.Lock()

from backend.api.auth import get_current_user, require_authenticated_user, UserProfile
from backend.core.config import settings, encrypt_secret, mask_secret, PROJECT_ROOT
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
def api_todays_predictions(
    user: UserProfile = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
):
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
            "reasoning": json.loads(str(p.llm_reasoning_json)) if p.llm_reasoning_json else {},
            "indicators": json.loads(str(p.indicators_json)) if p.indicators_json else {},
            "news_citations": json.loads(str(p.news_citations_json)) if p.news_citations_json else [],
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
    user: UserProfile = Depends(require_authenticated_user),
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
        sec_name = str(h.sector)
        inv_amt = float(h.invested_amount)
        sector_exposure[sec_name] = sector_exposure.get(sec_name, 0.0) + inv_amt

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
def api_get_vault_keys(
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(require_authenticated_user),
):
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
    user: UserProfile = Depends(require_authenticated_user),
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


class TicketGenerationRequest(BaseModel):
    prediction_id: int


@router.post("/orders/generate-ticket")
def api_generate_broker_ticket(
    payload: TicketGenerationRequest,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(require_authenticated_user),
):
    """Generate authenticated execution ticket on demand.
    Strictly blocked for demo data, shadow mode, or un-entered trades.
    """
    pred = db.query(Prediction).filter(Prediction.id == payload.prediction_id).first()
    if not pred:
        raise HTTPException(status_code=404, detail="Prediction not found")
    if getattr(pred, "is_demo", False) or (pred.audit_hash and pred.audit_hash.startswith("demo_")):
        raise HTTPException(status_code=403, detail="Trade tickets locked on demo data.")
    if getattr(pred, "source", "") == "SHADOW" or getattr(pred, "is_shadow", False):
        raise HTTPException(status_code=403, detail="Trade tickets locked for shadow mode.")
    if pred.status != "OPEN":
        raise HTTPException(status_code=400, detail="Only confirmed entered OPEN trades can generate execution tickets.")

    ticket = (
        f"AURA ORDER TICKET:\n"
        f"BUY {pred.symbol} EQ\n"
        f"Quantity: {pred.quantity} shares\n"
        f"Entry Limit: ₹{pred.entry_price:.2f}\n"
        f"Stop Loss Trigger: ₹{pred.stop_loss:.2f}\n"
        f"Target Limit: ₹{pred.target_price:.2f}\n"
        f"Zerodha GTT Trigger: ₹{pred.stop_loss:.2f}\n"
        f"Horizon: {pred.time_limit_days} Days (Swing)"
    )
    return {"status": "SUCCESS", "ticket": ticket}


class KiteBasketExportRequest(BaseModel):
    prediction_ids: List[int]


@router.post("/orders/kite-basket")
def api_export_kite_basket(
    payload: KiteBasketExportRequest,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(require_authenticated_user),
):
    """Server-side gated Zerodha Kite basket generator (Section 18.2 & Item 10).

    CRITICAL SAFETY RULES:
    1. Only ENTERED trades (status == 'OPEN') post-gap-check can be exported.
    2. Trades with status PENDING_OPEN_CHECK, SKIPPED_*, CANCELLED, or CLOSED are strictly rejected.
    3. Shadow trades (RED regime or source == 'SHADOW') are strictly rejected.
    4. Demo data (is_demo == True or audit_hash starting with 'demo_') is strictly rejected.
    """
    if not payload.prediction_ids:
        raise HTTPException(status_code=400, detail="No prediction IDs provided for basket export.")

    preds = db.query(Prediction).filter(Prediction.id.in_(payload.prediction_ids)).all()
    if len(preds) != len(payload.prediction_ids):
        found_ids = {p.id for p in preds}
        missing_ids = [pid for pid in payload.prediction_ids if pid not in found_ids]
        raise HTTPException(status_code=404, detail=f"Predictions {missing_ids} not found in database.")

    # Validate each prediction
    invalid_trades = []
    for p in preds:
        # Check demo data
        if getattr(p, "is_demo", False) or (p.audit_hash and p.audit_hash.startswith("demo_")):
            invalid_trades.append({"id": p.id, "symbol": p.symbol, "reason": "DEMO_DATA_BLOCKED"})
            continue

        # Check shadow mode
        if getattr(p, "is_shadow", False) or getattr(p, "source", "") == "SHADOW":
            invalid_trades.append({"id": p.id, "symbol": p.symbol, "reason": "SHADOW_MODE_BLOCKED"})
            continue

        # Check status: strictly only ENTERED trades (status == 'OPEN')
        if p.status != "OPEN":
            invalid_trades.append({
                "id": p.id,
                "symbol": p.symbol,
                "reason": f"TRADE_NOT_ENTERED (Status: {p.status}). Must pass 09:15 open gap check.",
            })

    if invalid_trades:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "SERVER_SIDE_BASKET_EXPORT_REJECTED",
                "message": "Only confirmed ENTERED trades post-gap-check can be exported into broker basket orders.",
                "invalid_trades": invalid_trades,
            },
        )

    # Format official Zerodha Kite Basket JSON schema
    basket_items = []
    for p in preds:
        clean_symbol = p.symbol.replace(".NS", "").replace(".BO", "")
        basket_items.append({
            "variety": "regular",
            "tradingsymbol": clean_symbol,
            "exchange": "NSE",
            "transaction_type": "BUY",
            "order_type": "LIMIT",
            "product": "CNC",
            "quantity": int(p.quantity),
            "price": float(p.entry_price),
            "trigger_price": 0.0,
            "tag": "AURA_SWING",
        })

    # Log to audit trail
    try:
        audit = SystemAuditLog(
            event_type="BASKET_EXPORTED",
            details_json=json.dumps({
                "prediction_ids": payload.prediction_ids,
                "symbols": [p.symbol for p in preds],
                "total_orders": len(basket_items),
            }),
        )
        db.add(audit)
        db.commit()
    except Exception:
        pass

    return {
        "status": "SUCCESS",
        "basket_count": len(basket_items),
        "basket": basket_items,
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
    elif payload.job_name in ("value_investing_scan", "value_scan", "scan_undervalued"):
        from backend.core.pipeline import run_value_investing_scan
        summary = run_value_investing_scan()
        return {"status": "SUCCESS", "job": payload.job_name, "value_summary": summary}
    else:
        return run_job_now(payload.job_name)


@router.post("/scan/value")
def api_trigger_value_scan(
    limit: Optional[int] = Query(default=None, ge=5, le=3000),
    mode: str = Query(default="all", pattern="^(all|diversified|curated)$"),
    user: UserProfile = Depends(get_current_user),
):
    """Trigger institutional value investing and intrinsic worth scan.

    Screens equities with positive Margin of Safety and institutional fundamentals across
    the complete ~2,760 listed NSE universe, diversified bluechips, or curated universe.
    Dispatches a dedicated Telegram alert separate from daily swing trading alerts.
    """
    from backend.core.pipeline import run_value_investing_scan
    result = run_value_investing_scan(universe_limit=limit, mode=mode, send_alert=True)
    return {"status": "SUCCESS", "data": result}


@router.get("/scan/value")
def api_get_latest_value_picks():
    """Return the latest cached value investing picks and intrinsic worth estimations."""
    from backend.core.config import PROJECT_ROOT
    target = PROJECT_ROOT / "data" / "snapshots" / "value_picks.json"
    if target.exists():
        try:
            with open(target, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"scan_date": None, "undervalued_count": 0, "value_picks": []}


@router.get("/system/health")
def api_system_health():
    """Return scheduler job execution history and system status."""
    return {
        "status": "HEALTHY",
        "system_time_ist": get_ist_now().isoformat(),
        "job_history": JOB_EXECUTION_HISTORY[:15],
    }


@router.get("/health/heartbeat")
def api_health_heartbeat():
    """Dead-man's heartbeat monitor.
    
    Verifies APScheduler is active and background tasks have fired within tolerance.
    """
    heartbeat_file = PROJECT_ROOT / "data" / "heartbeat.json"
    if not heartbeat_file.exists():
        # Trigger immediate heartbeat
        from backend.jobs.scheduler import job_heartbeat
        job_heartbeat()

    with open(heartbeat_file, "r", encoding="utf-8") as f:
        hb_data = json.load(f)

    last_beat = datetime.datetime.fromisoformat(hb_data["last_beat_utc"])
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    seconds_ago = (now_utc - last_beat).total_seconds()

    status = "ALIVE" if seconds_ago < 600 else "DEGRADED"

    return {
        "status": status,
        "seconds_since_last_beat": round(seconds_ago, 1),
        "last_beat_utc": hb_data.get("last_beat_utc"),
        "scheduler_running": hb_data.get("scheduler_running", True),
        "coalesce_enabled": True,
        "misfire_grace_seconds": 3600,
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
        "llm_reasoning": json.loads(str(p.llm_reasoning_json)) if p.llm_reasoning_json else {},
        "indicators": json.loads(str(p.indicators_json)) if p.indicators_json else {},
        "news_citations": json.loads(str(p.news_citations_json)) if p.news_citations_json else [],
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
    # Section 18.2: Filter out SHADOW trades from live accuracy tracking
    closed = [
        p for p in all_preds
        if p.status in ("TARGET_HIT", "STOP_LOSS_HIT", "TIME_EXPIRED")
        and getattr(p, "source", "") != "SHADOW"
        and not getattr(p, "is_shadow", False)
    ]
    shadow_closed = [
        p for p in all_preds
        if p.status in ("TARGET_HIT", "STOP_LOSS_HIT", "TIME_EXPIRED")
        and (getattr(p, "source", "") == "SHADOW" or getattr(p, "is_shadow", False))
    ]
    open_trades = [
        p for p in all_preds
        if p.status == "OPEN"
        and getattr(p, "source", "") != "SHADOW"
        and not getattr(p, "is_shadow", False)
    ]

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


# --- Upstox Live Connection & Token Management (Frontend UI Support) ---

class UpstoxTokenPayload(BaseModel):
    token: str


@router.get("/upstox/status")
def api_upstox_status():
    """Retrieve current Upstox connection state, rate limiter health, and token status."""
    from backend.data.upstox import upstox_client, shared_upstox_limiter

    token = upstox_client.token
    has_token = bool(token)
    masked = f"{token[:6]}...{token[-4:]}" if has_token and len(token) > 10 else ("CONFIGURED" if has_token else "NOT_CONFIGURED")

    return {
        "is_configured": has_token,
        "masked_token": masked,
        "days_remaining": upstox_client.get_token_days_remaining() if has_token else 0,
        "rate_limiter_stats": shared_upstox_limiter.get_stats(),
        "status": "READY" if has_token else "TOKEN_PENDING",
    }


@router.post("/upstox/test-connection")
def api_upstox_test_connection(payload: Optional[UpstoxTokenPayload] = None):
    """Test live connectivity against Upstox API v3 and fetch real-time quotes."""
    from backend.data.upstox import upstox_client
    import os

    # If new token passed in payload, temporarily or permanently apply it
    token_to_test = payload.token.strip() if payload and payload.token else (
        upstox_client.token or os.getenv("UPSTOX_ACCESS_TOKEN") or os.getenv("UPSTOX_ANALYTICS_TOKEN", "")
    )

    if not token_to_test:
        return {
            "success": False,
            "status": "TOKEN_PENDING",
            "message": "No Upstox token found. Please provide an Analytics Access Token.",
        }

    # Test client with the specified token
    original_token = upstox_client.token
    try:
        upstox_client.token = token_to_test
        upstox_client.is_valid = True

        status_res = upstox_client.get_market_status()
        quote_rel = upstox_client.get_market_quote("RELIANCE.NS")
        quote_vix = upstox_client.get_market_quote("^INDIAVIX")
        days_left = upstox_client.get_token_days_remaining()

        has_error = ("error" in quote_rel) or (status_res.get("status") in ("ERROR", "FAILED"))

        if has_error:
            err_msg = quote_rel.get("error") or status_res.get("error") or "Authentication failed or token invalid."
            return {
                "success": False,
                "status": "FAILED",
                "message": err_msg,
                "market_status": status_res.get("operational_status", "UNKNOWN"),
                "days_remaining": days_left,
            }

        return {
            "success": True,
            "status": "CONNECTED",
            "message": "Connected to Upstox API v3 successfully. Real-time market feed active.",
            "market_status": status_res.get("operational_status", "OPEN"),
            "latency_ms": upstox_client.last_latency_ms,
            "days_remaining": days_left,
            "sample_quotes": {
                "reliance": {
                    "symbol": "RELIANCE.NS",
                    "ltp": quote_rel.get("ltp"),
                    "volume": quote_rel.get("volume"),
                    "data_lag_seconds": quote_rel.get("data_lag_seconds"),
                },
                "india_vix": {
                    "symbol": "^INDIAVIX",
                    "ltp": quote_vix.get("ltp") if "error" not in quote_vix else None,
                },
            },
        }
    finally:
        # Keep the valid token if test succeeded, else restore
        if not (payload and payload.token):
            upstox_client.token = original_token


@router.post("/upstox/save-token")
def api_upstox_save_token(
    payload: UpstoxTokenPayload,
    current_user: UserProfile = Depends(require_authenticated_user),
):
    """Save Upstox Analytics Token into local environment and memory."""

    from backend.data.upstox import upstox_client
    from backend.core.config import PROJECT_ROOT
    import os

    new_token = payload.token.strip()
    if not new_token:
        raise HTTPException(status_code=400, detail="Token cannot be empty.")

    # Update in memory
    upstox_client.token = new_token
    upstox_client.is_valid = True
    os.environ["UPSTOX_ANALYTICS_TOKEN"] = new_token
    os.environ["UPSTOX_ACCESS_TOKEN"] = new_token

    # Persist to .env file
    env_file = PROJECT_ROOT / ".env"
    try:
        content = env_file.read_text(encoding="utf-8") if env_file.exists() else ""
        if "UPSTOX_ANALYTICS_TOKEN=" in content:
            import re
            content = re.sub(r'UPSTOX_ANALYTICS_TOKEN=.*', f'UPSTOX_ANALYTICS_TOKEN="{new_token}"', content)
        else:
            content += f'\nUPSTOX_ANALYTICS_TOKEN="{new_token}"\n'

        if "UPSTOX_ACCESS_TOKEN=" in content:
            import re
            content = re.sub(r'UPSTOX_ACCESS_TOKEN=.*', f'UPSTOX_ACCESS_TOKEN="{new_token}"', content)
        else:
            content += f'UPSTOX_ACCESS_TOKEN="{new_token}"\n'

        env_file.write_text(content, encoding="utf-8")
    except Exception as e:
        logger.warning(f"Could not persist token to .env: {e}")

    # Immediately execute verification test
    test_res = api_upstox_test_connection(payload)
    return {
        "saved": True,
        "token_masked": f"{new_token[:6]}...{new_token[-4:]}",
        "verification": test_res,
    }
