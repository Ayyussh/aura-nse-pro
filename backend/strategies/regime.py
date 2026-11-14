"""NSE Macro Regime & Sector Rotation Engine.

Evaluates NIFTY 50 trends, India VIX volatility regime, sector momentum,
and outputs dynamic sizing multipliers (Green: 100%, Amber: 50%, Red: 0%).
"""

from __future__ import annotations
import datetime
from typing import Dict, Any, List

import pandas as pd

from backend.data.provider import data_provider
from backend.strategies.indicators import compute_ema


REGIME_RANK = {"RED": 0, "AMBER": 1, "GREEN": 2}


def classify_raw_regime(
    nifty_close: float,
    ema20: float,
    ema50: float,
    vix_level: float,
    breadth_pct: Optional[float] = None,
) -> str:
    """Classify raw market state without hysteresis.
    Middle state is strictly named 'AMBER'.
    """
    # 1. Extreme volatility or breakdown -> RED
    if vix_level > 24.0 or (nifty_close < ema50 and vix_level > 20.0):
        return "RED"
    if breadth_pct is not None and breadth_pct < 20.0:
        return "RED"

    # 2. Caution / choppiness -> AMBER
    if vix_level > 18.0 or nifty_close < ema20:
        return "AMBER"
    if breadth_pct is not None and breadth_pct < 40.0:
        return "AMBER"

    return "GREEN"


def apply_regime_hysteresis(
    confirmed_prev_regime: str,
    today_raw: str,
    prev_day_raw: str,
    vix_spike: bool = False,
) -> str:
    """Apply institutional asymmetric hysteresis (Section 18.2 & Item 10):
    - STEP DOWN immediately on 1 close or VIX spike (preserves capital).
    - STEP UP only after 2 confirming closes (avoids bear trap whipsaws).
    - Middle state is strictly named 'AMBER'.
    """
    confirmed_prev = confirmed_prev_regime.upper()
    today_r = today_raw.upper()
    prev_r = prev_day_raw.upper()

    if vix_spike:
        return "RED" if today_r == "RED" else "AMBER"

    # Step down immediately on 1 close
    if REGIME_RANK[today_r] < REGIME_RANK[confirmed_prev]:
        return today_r

    # Step up requires 2 consecutive confirming closes
    if REGIME_RANK[today_r] > REGIME_RANK[confirmed_prev]:
        if REGIME_RANK[prev_r] >= REGIME_RANK[today_r]:
            return today_r
        return confirmed_prev

    return confirmed_prev


def evaluate_market_regime(
    breadth_pct: Optional[float] = None,
    prev_confirmed_regime: Optional[str] = None,
) -> Dict[str, Any]:
    """Evaluate current Indian equity macro regime."""
    # 1. Fetch NIFTY 50 and INDIA VIX
    nifty_df = data_provider.fetch_history("^NSEI", period="1y", interval="1d")
    vix_df = data_provider.fetch_history("^INDIAVIX", period="3mo", interval="1d")

    nifty_close = float(nifty_df["close"].iloc[-1]) if not nifty_df.empty else 25000.0
    vix_level = float(vix_df["close"].iloc[-1]) if not vix_df.empty else 15.0
    vix_5d_change = 0.0
    vix_1d_change = 0.0
    if not vix_df.empty and len(vix_df) >= 2:
        vix_1d_change = float(vix_level - vix_df["close"].iloc[-2])
    if not vix_df.empty and len(vix_df) >= 6:
        vix_5d_change = float(vix_level - vix_df["close"].iloc[-6])

    # VIX spike definition: 1-day spike > +2.5 pts or 5-day spike > +5.0 pts
    vix_spike = bool(vix_1d_change >= 2.5 or vix_5d_change >= 5.0)

    # 2. Moving average status for NIFTY 50
    ema20 = float(compute_ema(nifty_df["close"], 20).iloc[-1]) if not nifty_df.empty else nifty_close
    ema50 = float(compute_ema(nifty_df["close"], 50).iloc[-1]) if not nifty_df.empty else nifty_close
    sma200 = float(nifty_df["close"].rolling(200).mean().iloc[-1]) if len(nifty_df) >= 200 else nifty_close

    nifty_above_20ema = bool(nifty_close > ema20)
    nifty_above_50ema = bool(nifty_close > ema50)
    nifty_above_200sma = bool(nifty_close > sma200)

    # 3. Macro Regime Classification Rules with Asymmetric Two-Close Hysteresis
    today_regime = classify_raw_regime(nifty_close, ema20, ema50, vix_level, breadth_pct=breadth_pct)

    # Historical bar for hysteresis evaluation
    prev_day_raw = today_regime
    if len(nifty_df) >= 2 and len(vix_df) >= 2:
        prev_c = float(nifty_df["close"].iloc[-2])
        prev_vx = float(vix_df["close"].iloc[-2])
        e20_s = compute_ema(nifty_df["close"], 20)
        e50_s = compute_ema(nifty_df["close"], 50)
        prev_e20 = float(e20_s.iloc[-2]) if len(e20_s) >= 2 else prev_c
        prev_e50 = float(e50_s.iloc[-2]) if len(e50_s) >= 2 else prev_c
        prev_day_raw = classify_raw_regime(prev_c, prev_e20, prev_e50, prev_vx, breadth_pct=breadth_pct)

    initial_state = prev_confirmed_regime or prev_day_raw
    regime_label = apply_regime_hysteresis(
        confirmed_prev_regime=initial_state,
        today_raw=today_regime,
        prev_day_raw=prev_day_raw,
        vix_spike=vix_spike,
    )

    is_shadow_mode = bool(regime_label == "RED")
    if regime_label == "RED":
        sizing_multiplier = 0.0
        regime_description = "Defensive / Bearish: High volatility (VIX > 24) or NIFTY breaking below 50-EMA. Zero new live swing entries (Shadow tracking active)."
    elif regime_label == "AMBER":
        sizing_multiplier = 0.5
        regime_description = "Cautionary / Choppy: VIX > 18 or NIFTY below 20-EMA. Position sizing reduced to 50%."
    else:
        regime_label = "GREEN"
        sizing_multiplier = 1.0
        regime_description = "Favorable / Bullish: NIFTY trading above key short-term EMAs and India VIX remains subdued (<= 18)."

    # 4. Leading vs Lagging Sectors (Bank Nifty, IT, Auto, Metals, Pharma)
    sector_tickers = {
        "Banking": "^NSEBANK",
        "IT": "^CNXIT",
        "Auto": "^CNXAUTO",
        "Pharma": "^CNXPHARMA",
        "Energy": "^CNXENERGY",
        "Metals": "^CNXMETAL",
    }
    sector_momentum: List[Dict[str, Any]] = []
    nifty_1m_return = ((nifty_close / nifty_df["close"].iloc[-21]) - 1.0) * 100.0 if len(nifty_df) >= 22 else 0.0

    for sector_name, ticker in sector_tickers.items():
        sec_df = data_provider.fetch_history(ticker, period="3mo", interval="1d")
        if not sec_df.empty and len(sec_df) >= 22:
            sec_close = float(sec_df["close"].iloc[-1])
            sec_1m_ret = float(((sec_close / sec_df["close"].iloc[-21]) - 1.0) * 100.0)
            rs_vs_nifty = float(round(sec_1m_ret - nifty_1m_return, 2))
            sector_momentum.append({
                "sector": sector_name,
                "monthly_return_pct": round(sec_1m_ret, 2),
                "relative_strength": rs_vs_nifty,
                "is_outperforming": bool(rs_vs_nifty > 0),
            })
        else:
            # Fallback estimation
            sector_momentum.append({
                "sector": sector_name,
                "monthly_return_pct": round(float(nifty_1m_return), 2),
                "relative_strength": 0.0,
                "is_outperforming": True,
            })

    # Sort sectors by relative strength descending
    sector_momentum.sort(key=lambda s: s["relative_strength"], reverse=True)
    top_sectors = [s["sector"] for s in sector_momentum if s["is_outperforming"]][:3]

    return {
        "regime_label": regime_label,
        "is_shadow_mode": is_shadow_mode,
        "sizing_multiplier": sizing_multiplier,
        "description": regime_description,
        "nifty_close": round(nifty_close, 2),
        "nifty_20_ema": round(ema20, 2),
        "nifty_50_ema": round(ema50, 2),
        "nifty_200_sma": round(sma200, 2),
        "nifty_above_20ema": nifty_above_20ema,
        "nifty_above_50ema": nifty_above_50ema,
        "nifty_above_200sma": nifty_above_200sma,
        "india_vix": round(vix_level, 2),
        "vix_5d_change": round(vix_5d_change, 2),
        "top_leading_sectors": top_sectors,
        "sector_rankings": sector_momentum,
        "evaluated_at": datetime.datetime.utcnow().isoformat(),
    }
