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
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.api.auth import get_current_user, UserProfile
from backend.core.config import settings, encrypt_secret, mask_secret
from backend.core.pipeline import run_pre_market_pipeline, run_open_check_pipeline, run_post_market_grading
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
