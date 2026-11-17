"""SQLAlchemy Models for AURA-NSE Pro.

Includes immutable prediction ledger, trade executions, portfolio holdings,
mistake logs, API key vault, and system audit logs.
"""

from __future__ import annotations
import datetime
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from backend.db.session import Base


class Prediction(Base):
    """Immutable prediction ledger with cryptographic audit trail."""
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    config_hash = Column(String(32), nullable=False)
    model_version = Column(String(32), nullable=False, default="v1.0.0")
    data_snapshot_id = Column(String(64), nullable=False)

    symbol = Column(String(32), nullable=False, index=True)
    series = Column(String(8), nullable=False, default="EQ")
    horizon = Column(String(16), nullable=False, default="SWING") # SWING or LONG_TERM
    setup_tag = Column(String(32), nullable=True) # breakout, pullback_ema, base, compounder

    status = Column(String(32), nullable=False, default="OPEN", index=True)
    # OPEN, TARGET_HIT, STOP_LOSS_HIT, TIME_EXPIRED, SKIPPED_GAP_UP, SKIPPED_GAP_DOWN, SKIPPED_NO_FILL, SKIPPED_SIZE, CANCELLED

    planned_entry_price = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    actual_fill_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=False)
    target_price = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False)
    time_limit_days = Column(Integer, nullable=False, default=10)

    win_probability = Column(Float, nullable=True)
    win_prob_lower = Column(Float, nullable=True)
    win_prob_upper = Column(Float, nullable=True)
    ev_r = Column(Float, nullable=True)

    llm_verdict = Column(String(32), nullable=True, default="APPROVED")
    llm_confidence = Column(Float, nullable=True)
    llm_reasoning_json = Column(Text, nullable=True)
    indicators_json = Column(Text, nullable=True)
    news_citations_json = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    entry_date = Column(Date, nullable=False)
    closed_at = Column(DateTime, nullable=True)

    exit_price = Column(Float, nullable=True)
    exit_reason = Column(String(64), nullable=True)
    gross_pnl_rupees = Column(Float, nullable=True)
    charges_rupees = Column(Float, nullable=True)
    net_pnl_rupees = Column(Float, nullable=True)
    net_pnl_r = Column(Float, nullable=True)
    tax_estimated_rupees = Column(Float, nullable=True)

    audit_hash = Column(String(64), nullable=True) # Hash-chain link
    prev_hash = Column(String(64), nullable=True, default="GENESIS_AURA_HASH", server_default="GENESIS_AURA_HASH")
    hash_version = Column(String(16), nullable=False, default="v2", server_default="v2")
    source = Column(String(16), default="LIVE", nullable=True) # LIVE or SHADOW
    is_shadow = Column(Boolean, default=False, nullable=True)

    executions = relationship("TradeExecution", back_populates="prediction", cascade="all, delete-orphan")
    mistakes = relationship("MistakeLog", back_populates="prediction")


class TradeExecution(Base):
    """Detailed trade executions for paper or live trades."""
    __tablename__ = "trade_executions"

    id = Column(Integer, primary_key=True, index=True)
    prediction_id = Column(Integer, ForeignKey("predictions.id"), nullable=True)
    symbol = Column(String(32), nullable=False)
    side = Column(String(8), nullable=False) # BUY or SELL
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    turnover = Column(Float, nullable=False)
    charges_json = Column(Text, nullable=True) # STT, Stamp, Txn, SEBI, GST, DP
    total_charges = Column(Float, nullable=False, default=0.0)
    executed_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    prediction = relationship("Prediction", back_populates="executions")


class PortfolioHolding(Base):
    """Portfolio holdings tracker (paper and real accounts)."""
    __tablename__ = "portfolio_holdings"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(32), nullable=False, index=True)
    series = Column(String(8), nullable=False, default="EQ")
    sector = Column(String(64), nullable=False)
    quantity = Column(Integer, nullable=False)
    average_buy_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=False, default=0.0)
    invested_amount = Column(Float, nullable=False)
    current_value = Column(Float, nullable=False, default=0.0)
    unrealized_pnl = Column(Float, nullable=False, default=0.0)
    is_paper = Column(Boolean, nullable=False, default=True)
    buy_date = Column(Date, nullable=False)
    target_weight_pct = Column(Float, nullable=True, default=5.0)
    tranche = Column(Integer, nullable=False, default=1)
    notes = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class MistakeLog(Base):
    """Mistake & Loss Diagnosis logs for walk-forward learning."""
    __tablename__ = "mistake_logs"

    id = Column(Integer, primary_key=True, index=True)
    prediction_id = Column(Integer, ForeignKey("predictions.id"), nullable=True)
    symbol = Column(String(32), nullable=False)
    loss_category = Column(String(64), nullable=False)
    # High VIX Trap, Sector Weakness, Regime Flip, Earnings Gap, News Shock,
    # False Breakout, Gap-Through-Stop, Stop Too Tight, Chased Entry, Liquidity or Circuit, Flat Expiry, Model Error
    loss_rupees = Column(Float, nullable=False)
    loss_r = Column(Float, nullable=False)
    diagnosis_narrative = Column(Text, nullable=False)
    proposed_guardrail = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="PENDING_REVIEW")
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    prediction = relationship("Prediction", back_populates="mistakes")


class ApiKeyVault(Base):
    """Encrypted multi-LLM API key and model rotation vault."""
    __tablename__ = "api_key_vault"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(32), nullable=False) # gemini, groq, openrouter, openai, ollama
    key_label = Column(String(64), nullable=False)
    model_name = Column(String(64), nullable=False)
    encrypted_key = Column(Text, nullable=False)
    priority_order = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True)
    status = Column(String(32), nullable=False, default="ACTIVE") # ACTIVE, COOLING, DISABLED, RATE_LIMITED
    cooling_until = Column(DateTime, nullable=True)
    rpm_count = Column(Integer, nullable=False, default=0)
    rpd_count = Column(Integer, nullable=False, default=0)
    last_latency_ms = Column(Float, nullable=True)
    last_error = Column(Text, nullable=True)
    last_tested_at = Column(DateTime, nullable=True)


class SystemAuditLog(Base):
    """Append-only system audit log."""
    __tablename__ = "system_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(64), nullable=False)
    details_json = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class PriceTruth(Base):
    """Reconciled 3-way multi-source price truth ledger (Section 17.1 & 18.3).

    Stores reconciled daily OHLCV bars across Tier 1 (NSE Bhavcopy), Tier 2 (Upstox v3),
    and Tier 3 (yfinance) with assigned Confidence Grades (A, B, C).
    """
    __tablename__ = "price_truth"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(32), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(BigInteger, nullable=False, default=0)
    confidence_grade = Column(String(4), nullable=False)  # "A", "B", "C"
    source_set = Column(Text, nullable=True)  # JSON list of responding sources
    discrepancies = Column(Text, nullable=True)  # JSON list of price discrepancies
    is_tradable = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class TradeFillEvent(Base):
    """Separate append-only chained event table for trade fill prices (Section 19.3 / Housekeeping)."""
    __tablename__ = "trade_fill_events"

    id = Column(Integer, primary_key=True, index=True)
    prediction_id = Column(Integer, ForeignKey("predictions.id"), nullable=False)
    symbol = Column(String(32), nullable=False)
    order_side = Column(String(8), nullable=False, default="BUY")  # BUY / SELL
    planned_price = Column(Float, nullable=False)
    fill_price = Column(Float, nullable=False)
    slippage_rupees = Column(Float, nullable=False, default=0.0)
    quantity = Column(Integer, nullable=False)
    fill_timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    event_hash = Column(String(64), nullable=False)
    prev_event_hash = Column(String(64), nullable=False, default="GENESIS_FILL_EVENT")

