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


def evaluate_market_regime() -> Dict[str, Any]:
    """Evaluate current Indian equity macro regime."""
    # 1. Fetch NIFTY 50 and INDIA VIX
    nifty_df = data_provider.fetch_history("^NSEI", period="1y", interval="1d")
    vix_df = data_provider.fetch_history("^INDIAVIX", period="3mo", interval="1d")

    nifty_close = float(nifty_df["close"].iloc[-1]) if not nifty_df.empty else 25000.0
    vix_level = float(vix_df["close"].iloc[-1]) if not vix_df.empty else 15.0
    vix_5d_change = 0.0
    if not vix_df.empty and len(vix_df) >= 6:
        vix_5d_change = float(vix_level - vix_df["close"].iloc[-6])

    # 2. Moving average status for NIFTY 50
    ema20 = float(compute_ema(nifty_df["close"], 20).iloc[-1]) if not nifty_df.empty else nifty_close
    ema50 = float(compute_ema(nifty_df["close"], 50).iloc[-1]) if not nifty_df.empty else nifty_close
    sma200 = float(nifty_df["close"].rolling(200).mean().iloc[-1]) if len(nifty_df) >= 200 else nifty_close

    nifty_above_20ema = bool(nifty_close > ema20)
    nifty_above_50ema = bool(nifty_close > ema50)
    nifty_above_200sma = bool(nifty_close > sma200)

    # 3. Macro Regime Classification Rules
    # RED: VIX > 24 or NIFTY below 50-EMA with sharp drop
    # AMBER: VIX > 18 or NIFTY < 20-EMA
    # GREEN: NIFTY > 20-EMA and VIX <= 18
    if vix_level > 24.0 or (not nifty_above_50ema and vix_level > 20.0):
        regime_label = "RED"
        sizing_multiplier = 0.0
        regime_description = "Defensive / Bearish: High volatility (VIX > 24) or NIFTY breaking below 50-EMA. Zero new swing entries."
    elif vix_level > 18.0 or not nifty_above_20ema:
        regime_label = "AMBER"
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
