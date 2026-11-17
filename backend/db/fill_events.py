"""Append-Only Chained Event Ledger for Trade Fills (Section 19.3 & Housekeeping).

Records actual execution fills, tracks execution slippage vs planned price,
and cryptographically chains events to prevent tampering.
"""

from __future__ import annotations
import datetime
import hashlib
import json
import logging
from typing import Optional
from sqlalchemy.orm import Session

from backend.db.models import TradeFillEvent, Prediction

logger = logging.getLogger("aura.fill_events")


def compute_fill_event_hash(
    prediction_id: int,
    symbol: str,
    order_side: str,
    planned_price: float,
    fill_price: float,
    quantity: int,
    timestamp_iso: str,
    prev_hash: str,
) -> str:
    """Compute deterministic SHA-256 hash for a trade fill event."""
    payload = {
        "prediction_id": prediction_id,
        "symbol": symbol,
        "order_side": order_side,
        "planned_price": round(planned_price, 2),
        "fill_price": round(fill_price, 2),
        "quantity": quantity,
        "fill_timestamp": timestamp_iso,
        "prev_hash": prev_hash,
    }
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def record_trade_fill_event(
    db: Session,
    prediction_id: int,
    symbol: str,
    planned_price: float,
    fill_price: float,
    quantity: int,
    order_side: str = "BUY",
) -> TradeFillEvent:
    """Record an append-only chained fill event and update actual_fill_price on prediction."""
    # Find latest event hash in chain
    latest_event = db.query(TradeFillEvent).order_by(TradeFillEvent.id.desc()).first()
    prev_hash = latest_event.event_hash if latest_event else "GENESIS_FILL_EVENT"

    now = datetime.datetime.utcnow()
    now_iso = now.isoformat()

    # Calculate slippage
    if order_side.upper() == "BUY":
        slippage = round(fill_price - planned_price, 2)
    else:
        slippage = round(planned_price - fill_price, 2)

    event_hash = compute_fill_event_hash(
        prediction_id=prediction_id,
        symbol=symbol,
        order_side=order_side.upper(),
        planned_price=planned_price,
        fill_price=fill_price,
        quantity=quantity,
        timestamp_iso=now_iso,
        prev_hash=prev_hash,
    )

    fill_event = TradeFillEvent(
        prediction_id=prediction_id,
        symbol=symbol,
        order_side=order_side.upper(),
        planned_price=round(planned_price, 2),
        fill_price=round(fill_price, 2),
        slippage_rupees=slippage,
        quantity=quantity,
        fill_timestamp=now,
        event_hash=event_hash,
        prev_event_hash=prev_hash,
    )

    db.add(fill_event)
    db.commit()
    db.refresh(fill_event)
    logger.info(f"Recorded TradeFillEvent {fill_event.id} for {symbol}: fill ₹{fill_price} (slippage ₹{slippage}).")
    return fill_event

