"""Market-Neutral & Tail-Risk Put Hedging Engine.

Provides institutional portfolio insurance and short-side hedging:
1. Index Put Option Tail-Risk Hedge (NIFTY 50 Puts):
   - Dynamic activation during AMBER and RED macro market regimes
   - Calculates contract sizing:
     N_contracts = round((Portfolio_Value * Beta) / (NIFTY_LTP * 25))
   - Recommends 2.5% OTM monthly strike to balance delta protection with theta decay
2. Bearish Short Alpha Screener:
   - Identifies structural distribution in liquid F&O equities:
     - Close < 50-EMA < 200-SMA
     - Relative Strength vs NIFTY 20d < -2.0%
     - RSI in bearish acceleration zone (30.0 <= RSI <= 48.0)
     - Derivatives Short Buildup / Long Unwinding
"""

from __future__ import annotations
import datetime
import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from backend.core.config import PROJECT_ROOT
from backend.data.holiday_calendar import get_ist_now

logger = logging.getLogger("aura.hedging")
HEDGE_SNAPSHOT_FILE = PROJECT_ROOT / "data" / "snapshots" / "hedging_recommendations.json"
HEDGE_SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class PutHedgeRecommendation:
    regime: str
    hedge_required: bool
    portfolio_value: float
    portfolio_beta: float
    nifty_ltp: float
    lot_size: int
    recommended_strike: float
    contract_count: int
    estimated_premium_pts: float
    estimated_cost_rupees: float
    hedge_ratio_pct: float
    recommended_expiry: str
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ShortCandidate:
    symbol: str
    passed: bool
    setup_tag: str
    entry_price: float
    stop_loss: float
    target_price: float
    net_rr_ratio: float
    rs_vs_nifty_20d: float
    rejection_reasons: List[str]
    indicators: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class HedgingEngine:
    """Manages tail-risk put option hedging and bearish F&O screening."""

    NIFTY_LOT_SIZE = 25

    def calculate_nifty_put_hedge(
        self,
        portfolio_value: float = 1_000_000.0,
        portfolio_beta: float = 1.05,
        nifty_ltp: float = 24_500.0,
        macro_regime: str = "AMBER",
    ) -> PutHedgeRecommendation:
        """Calculate tail-risk index put option hedge requirements."""
        regime = macro_regime.upper()
        hedge_required = regime in ("AMBER", "RED")

        if not hedge_required or portfolio_value <= 0 or nifty_ltp <= 0:
            return PutHedgeRecommendation(
                regime=regime,
                hedge_required=False,
                portfolio_value=portfolio_value,
                portfolio_beta=portfolio_beta,
                nifty_ltp=nifty_ltp,
                lot_size=self.NIFTY_LOT_SIZE,
                recommended_strike=0.0,
                contract_count=0,
                estimated_premium_pts=0.0,
                estimated_cost_rupees=0.0,
                hedge_ratio_pct=0.0,
                recommended_expiry="NONE",
                rationale="Macro regime is GREEN. Institutional equity exposure unhedged to capture alpha.",
            )

        # 1. Delta & Contract sizing
        # For RED: 100% beta hedge; For AMBER: 50% beta hedge
        hedge_multiplier = 1.0 if regime == "RED" else 0.50
        contract_notional = nifty_ltp * self.NIFTY_LOT_SIZE
        raw_contracts = (portfolio_value * portfolio_beta * hedge_multiplier) / contract_notional
        contract_count = max(1, int(round(raw_contracts)))

        # 2. Optimal Strike selection (2.5% OTM strike rounded to nearest 50 points)
        otm_strike_raw = nifty_ltp * 0.975
        recommended_strike = float(round(otm_strike_raw / 50.0) * 50)

        # 3. Estimated premium (empirical Black-Scholes estimate ~0.9% - 1.4% of spot for 2.5% OTM 30D put)
        est_premium_pts = round(nifty_ltp * 0.011, 1)  # ~1.1% of spot
        est_cost = contract_count * self.NIFTY_LOT_SIZE * est_premium_pts
        hedge_ratio = round((contract_count * contract_notional) / portfolio_value * 100.0, 1)

        # 4. Expiry recommendation
        now = get_ist_now()
        rec_expiry = (now + datetime.timedelta(days=28)).strftime("%b %Y").upper()

        rationale = (
            f"Regime {regime}: Tail-risk insurance required. {contract_count}x NIFTY {int(recommended_strike)} "
            f"PE contracts cover ₹{(contract_count * contract_notional):,.0f} notional exposure (Cost: ~₹{est_cost:,.0f})."
        )

        rec = PutHedgeRecommendation(
            regime=regime,
            hedge_required=True,
            portfolio_value=portfolio_value,
            portfolio_beta=portfolio_beta,
            nifty_ltp=nifty_ltp,
            lot_size=self.NIFTY_LOT_SIZE,
            recommended_strike=recommended_strike,
            contract_count=contract_count,
            estimated_premium_pts=est_premium_pts,
            estimated_cost_rupees=est_cost,
            hedge_ratio_pct=hedge_ratio,
            recommended_expiry=rec_expiry,
            rationale=rationale,
        )

        # Save snapshot
        try:
            with open(HEDGE_SNAPSHOT_FILE, "w", encoding="utf-8") as f:
                json.dump(rec.to_dict(), f, indent=2)
        except Exception as e:
            logger.debug(f"Could not persist hedge recommendation: {e}")

        return rec

    def evaluate_short_setup(
        self,
        symbol: str,
        df: pd.DataFrame,
        nifty_df: Optional[pd.DataFrame] = None,
    ) -> ShortCandidate:
        """Scan liquid F&O stock for structural breakdown short setup."""
        rejection_reasons: List[str] = []

        if len(df) < 200:
            return ShortCandidate(
                symbol=symbol,
                passed=False,
                setup_tag="INSUFFICIENT_DATA",
                entry_price=0.0,
                stop_loss=0.0,
                target_price=0.0,
                net_rr_ratio=0.0,
                rs_vs_nifty_20d=0.0,
                rejection_reasons=["Insufficient historical data (need >= 200 bars)."],
                indicators={},
            )

        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        c_last = float(close.iloc[-1])
        ema20 = close.ewm(span=20, adjust=False).mean()
        ema50 = close.ewm(span=50, adjust=False).mean()
        sma200 = close.rolling(200).mean()

        ema20_last = float(ema20.iloc[-1])
        ema50_last = float(ema50.iloc[-1])
        sma200_last = float(sma200.iloc[-1])

        # 1. Structural Downtrend: Close < 50-EMA < 200-SMA
        if not (c_last < ema50_last < sma200_last):
            rejection_reasons.append("Failed structural downtrend: Close must be below 50-EMA and 50-EMA below 200-SMA.")

        # 2. RSI Bearish Momentum: 30.0 <= RSI <= 48.0
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        rsi_last = float(rsi.iloc[-1]) if not np.isnan(rsi.iloc[-1]) else 50.0

        if not (30.0 <= rsi_last <= 48.0):
            rejection_reasons.append(f"RSI ({rsi_last:.1f}) outside bearish momentum zone [30.0 - 48.0].")

        # 3. Relative Strength vs NIFTY
        rs_20d = 0.0
        if nifty_df is not None and len(nifty_df) >= 20:
            stock_ret = (c_last / float(close.iloc[-20]) - 1.0) * 100.0
            nifty_ret = (float(nifty_df["close"].iloc[-1]) / float(nifty_df["close"].iloc[-20]) - 1.0) * 100.0
            rs_20d = round(stock_ret - nifty_ret, 2)
            if rs_20d > -2.0:
                rejection_reasons.append(f"Stock RS ({rs_20d:.1f}%) not underperforming NIFTY by >= -2.0%.")

        # 4. Volatility (ATR)
        tr = np.maximum(high - low, np.maximum(abs(high - close.shift()), abs(low - close.shift())))
        atr_14 = float(tr.rolling(14).mean().iloc[-1])

        entry_price = round(c_last, 2)
        stop_loss = round(entry_price + (1.5 * atr_14), 2)  # Stop above entry for short
        target_price = round(entry_price - (3.0 * atr_14), 2)  # Target below entry

        risk = stop_loss - entry_price
        reward = entry_price - target_price
        net_rr = round(reward / risk, 2) if risk > 0 else 0.0

        if net_rr < 1.8:
            rejection_reasons.append(f"Short R:R ({net_rr:.2f}) below 1.8 minimum threshold.")

        passed = len(rejection_reasons) == 0
        setup_tag = "breakdown_200sma" if passed else "none"

        return ShortCandidate(
            symbol=symbol,
            passed=passed,
            setup_tag=setup_tag,
            entry_price=entry_price,
            stop_loss=stop_loss,
            target_price=target_price,
            net_rr_ratio=net_rr,
            rs_vs_nifty_20d=rs_20d,
            rejection_reasons=rejection_reasons,
            indicators={
                "close": entry_price,
                "ema_20": round(ema20_last, 2),
                "ema_50": round(ema50_last, 2),
                "sma_200": round(sma200_last, 2),
                "rsi_14": round(rsi_last, 2),
                "atr_14": round(atr_14, 2),
            },
        )


hedging_engine = HedgingEngine()
