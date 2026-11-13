"""AURA-NSE Pro Swing Strategy Engine (5 to 15 Trading Days).

Evaluates trend alignment (Close > EMA50 > SMA200), momentum (RSI 50-70),
trend strength (ADX > 20), MACD bullish crossover, volume expansion (> 1.2x 20d SMA),
relative strength vs NIFTY 50, setup classification, anti-chase guardrails,
and 1:2 Risk-Reward with ATR stops.
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, Tuple, List
import pandas as pd

from backend.core.config import get_strategy_config
from backend.costs.charges import charges_engine
from backend.strategies.indicators import (
    compute_ema,
    compute_sma,
    compute_atr,
    compute_rsi,
    compute_macd,
    compute_adx,
    compute_relative_strength,
)


@dataclass
class SwingCandidate:
    symbol: str
    passed: bool
    setup_tag: str  # breakout, pullback_ema, base_consolidation
    entry_price: float
    stop_loss: float
    target_price: float
    atr_14: float
    stop_distance_pct: float
    net_rr_ratio: float
    time_limit_days: int
    anti_chase_ratio: float
    rs_vs_nifty_20d: float
    indicators: Dict[str, Any]
    rejection_reasons: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SwingStrategyEngine:
    """Evaluates swing setups on NSE equities."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.cfg = config or get_strategy_config()
        self.swing_cfg = self.cfg.get("swing_strategy", {})
        self.rr_cfg = self.swing_cfg.get("risk_reward", {})

    def evaluate(
        self,
        symbol: str,
        df: pd.DataFrame,
        nifty_df: Optional[pd.DataFrame] = None,
    ) -> SwingCandidate:
        """Run complete swing screening rule pipeline on historical daily OHLCV."""
        rejection_reasons: List[str] = []

        if df.empty or len(df) < 200:
            return SwingCandidate(
                symbol=symbol,
                passed=False,
                setup_tag="none",
                entry_price=0.0,
                stop_loss=0.0,
                target_price=0.0,
                atr_14=0.0,
                stop_distance_pct=0.0,
                net_rr_ratio=0.0,
                time_limit_days=10,
                anti_chase_ratio=0.0,
                rs_vs_nifty_20d=0.0,
                indicators={},
                rejection_reasons=["Insufficient historical bars for indicator computation."],
            )

        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        # Compute Technical Indicators
        ema20 = compute_ema(close, 20)
        ema50 = compute_ema(close, self.swing_cfg.get("trend", {}).get("ema_fast", 50))
        sma200 = compute_sma(close, self.swing_cfg.get("trend", {}).get("sma_slow", 200))
        atr14 = compute_atr(df, self.rr_cfg.get("atr_period", 14))
        rsi14 = compute_rsi(close, self.swing_cfg.get("rsi", {}).get("period", 14))
        macd_line, signal_line, _ = compute_macd(close)
        adx14 = compute_adx(df, self.swing_cfg.get("adx", {}).get("period", 14))
        vol_sma20 = compute_sma(volume, self.swing_cfg.get("volume", {}).get("sma_period", 20))

        # Latest values
        c_last = float(close.iloc[-1])
        ema20_last = float(ema20.iloc[-1])
        ema50_last = float(ema50.iloc[-1])
        sma200_last = float(sma200.iloc[-1])
        atr_last = float(atr14.iloc[-1])
        rsi_last = float(rsi14.iloc[-1])
        macd_last = float(macd_line.iloc[-1])
        sig_last = float(signal_line.iloc[-1])
        adx_last = float(adx14.iloc[-1])
        vol_last = float(volume.iloc[-1])
        vol_sma_last = float(vol_sma20.iloc[-1]) if not pd.isna(vol_sma20.iloc[-1]) else 1.0

        # Relative Strength vs NIFTY 50
        rs_20d = 0.0
        if nifty_df is not None and not nifty_df.empty:
            rs_20d = compute_relative_strength(close, nifty_df["close"], period=20)

        # 1. Trend Rule: Close > 50-EMA > 200-SMA
        if not (c_last > ema50_last > sma200_last):
            rejection_reasons.append(
                f"Trend failed: Close ({c_last:.2f}) > EMA50 ({ema50_last:.2f}) > SMA200 ({sma200_last:.2f}) required."
            )

        # 2. ADX Rule: ADX14 > 20 (Strong Trend)
        min_adx = self.swing_cfg.get("adx", {}).get("min_threshold", 20.0)
        if adx_last < min_adx:
            rejection_reasons.append(f"ADX {adx_last:.1f} below minimum threshold of {min_adx}.")

        # 3. RSI Rule: RSI14 in 50 - 70 range
        rsi_min = self.swing_cfg.get("rsi", {}).get("min_threshold", 50.0)
        rsi_max = self.swing_cfg.get("rsi", {}).get("max_threshold", 70.0)
        if not (rsi_min <= rsi_last <= rsi_max):
            rejection_reasons.append(f"RSI {rsi_last:.1f} outside institutional sweet spot [{rsi_min}, {rsi_max}].")

        # 4. MACD Rule: MACD Line > Signal Line
        if not (macd_last > sig_last):
            rejection_reasons.append(f"MACD line ({macd_last:.2f}) not above Signal ({sig_last:.2f}).")

        # 5. Volume Rule: Volume > 1.2x 20-Day SMA
        min_vol_mult = self.swing_cfg.get("volume", {}).get("min_volume_ratio", 1.2)
        vol_ratio = vol_last / vol_sma_last if vol_sma_last > 0 else 0.0
        if vol_ratio < min_vol_mult:
            rejection_reasons.append(f"Volume ratio {vol_ratio:.2f}x below required {min_vol_mult}x 20d SMA.")

        # 6. Relative Strength Rule: Outperforming NIFTY 50 over 20 days
        if rs_20d < 0.0:
            rejection_reasons.append(f"Relative strength vs NIFTY 50 ({rs_20d:.2f}%) is negative (lagging index).")

        # 7. Anti-chase Guardrail: (Close - EMA20) / ATR14 <= 2.5
        max_chase = self.swing_cfg.get("anti_chase", {}).get("max_chase_atr_ratio", 2.5)
        chase_ratio = (c_last - ema20_last) / atr_last if atr_last > 0 else 0.0
        if chase_ratio > max_chase:
            rejection_reasons.append(f"Anti-chase breached: {chase_ratio:.2f} ATRs extended above 20-EMA (max {max_chase}).")

        # Risk Calculation: Stop = Entry - 2*ATR, Target = Entry + 4*ATR
        stop_mult = self.rr_cfg.get("stop_atr_mult", 2.0)
        target_mult = self.rr_cfg.get("target_atr_mult", 4.0)

        entry_price = round(c_last, 2)
        stop_loss = round(max(0.01, entry_price - (stop_mult * atr_last)), 2)
        target_price = round(entry_price + (target_mult * atr_last), 2)
        stop_dist_pct = round(((entry_price - stop_loss) / entry_price) * 100.0, 2)

        # 8. Max stop distance check (<= 8%)
        max_stop_dist = self.rr_cfg.get("max_stop_distance_pct", 8.0)
        if stop_dist_pct > max_stop_dist:
            rejection_reasons.append(f"Stop distance {stop_dist_pct:.2f}% exceeds maximum allowable {max_stop_dist}%.")

        # 9. Net R:R check after realistic Indian costs
        # Sample test with 100 shares to compute net R:R
        gross_profit_per_share = target_price - entry_price
        gross_loss_per_share = entry_price - stop_loss
        cost_profile = charges_engine.calculate_delivery_charges(entry_price, target_price, 100)
        cost_per_share = cost_profile.total_charges_and_brokerage / 100.0

        net_profit_per_share = gross_profit_per_share - cost_per_share
        net_loss_per_share = gross_loss_per_share + cost_per_share
        net_rr = round(net_profit_per_share / net_loss_per_share, 2) if net_loss_per_share > 0 else 0.0

        min_net_rr = self.rr_cfg.get("min_net_rr_ratio", 1.8)
        if net_rr < min_net_rr:
            rejection_reasons.append(f"Net R:R after Indian costs {net_rr:.2f} is below minimum {min_net_rr} requirement.")

        # Setup Tagging
        high_20d = float(high.tail(20).max())
        if c_last >= high_20d * 0.99:
            setup_tag = "breakout"
        elif abs(c_last - ema20_last) <= atr_last:
            setup_tag = "pullback_ema"
        else:
            setup_tag = "base_consolidation"

        # Time limit dynamically scaled by volatility
        atr_pct = (atr_last / c_last) * 100.0
        if atr_pct > 3.0:
            time_limit = 7  # High volatility moves faster
        elif atr_pct < 1.5:
            time_limit = 12
        else:
            time_limit = 10

        indicators_meta = {
            "close": entry_price,
            "ema_20": round(ema20_last, 2),
            "ema_50": round(ema50_last, 2),
            "sma_200": round(sma200_last, 2),
            "atr_14": round(atr_last, 2),
            "rsi_14": round(rsi_last, 2),
            "macd": round(macd_last, 2),
            "macd_signal": round(sig_last, 2),
            "adx_14": round(adx_last, 2),
            "volume_ratio_20d": round(vol_ratio, 2),
            "relative_strength_nifty_20d": round(rs_20d, 2),
        }

        passed = len(rejection_reasons) == 0

        return SwingCandidate(
            symbol=symbol,
            passed=passed,
            setup_tag=setup_tag,
            entry_price=entry_price,
            stop_loss=stop_loss,
            target_price=target_price,
            atr_14=round(atr_last, 2),
            stop_distance_pct=stop_dist_pct,
            net_rr_ratio=net_rr,
            time_limit_days=time_limit,
            anti_chase_ratio=round(chase_ratio, 2),
            rs_vs_nifty_20d=round(rs_20d, 2),
            indicators=indicators_meta,
            rejection_reasons=rejection_reasons,
        )


swing_engine = SwingStrategyEngine()
