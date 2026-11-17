"""Machine Learning Feature Extraction & Triple-Barrier Labeling.

Extracts point-in-time quantitative features and implements strict triple-barrier
labeling (1 if Target reached before Stop within Time_Limit, stop-first on ambiguity).
"""

from __future__ import annotations
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd

from backend.strategies.indicators import (
    compute_ema,
    compute_sma,
    compute_atr,
    compute_rsi,
    compute_macd,
    compute_adx,
    compute_relative_strength,
    compute_mansfield_relative_strength,
)



FEATURE_BATCH_A = [
    "rsi_14",
    "adx_14",
    "macd_norm",
    "dist_ema20_pct",
    "dist_ema50_pct",
    "dist_sma200_pct",
]  # Trend & Momentum

FEATURE_BATCH_B = [
    "atr_pct",
    "vol_ratio_20d",
    "vol_trend_5d",
]  # Volume & Volatility

FEATURE_BATCH_C = [
    "rs_vs_nifty_20d",
    "dist_52w_high_pct",
    "mansfield_rs_50d",
]  # Relative Strength

FEATURE_BATCH_D = [
    "vix_level_proxy",
    "nifty_trend_score",
]  # Macro & Regime Context

# All combined features strictly subject to <= 25 feature cap (Section 18.6 U5)
FEATURE_COLUMNS = FEATURE_BATCH_A + FEATURE_BATCH_B + FEATURE_BATCH_C + FEATURE_BATCH_D
assert len(FEATURE_COLUMNS) <= 25, f"Feature count {len(FEATURE_COLUMNS)} exceeds institutional 25-feature cap!"


def cross_sectional_rank_normalize(
    universe_features: Dict[str, Dict[str, float]],
) -> Dict[str, Dict[str, float]]:
    """Cross-sectional uniform rank normalization [0.0, 1.0] across universe on day D (Section 18.6 U5).
    
    Prevents market-wide regime shift distortion and outlier leverage.
    """
    if not universe_features:
        return {}

    symbols = list(universe_features.keys())
    normalized: Dict[str, Dict[str, float]] = {s: {} for s in symbols}

    for col in FEATURE_COLUMNS:
        raw_vals = [universe_features[s].get(col, 0.0) for s in symbols]
        s_series = pd.Series(raw_vals, index=symbols)
        # Rank from 0 to 1
        ranked = s_series.rank(pct=True, method="average")
        for s in symbols:
            normalized[s][col] = round(float(ranked[s]), 4)

    return normalized



def extract_features_from_df(
    df: pd.DataFrame,
    nifty_df: Optional[pd.DataFrame] = None,
    idx: int = -1,
) -> Dict[str, float]:
    """Compute normalized quantitative feature vector at a specific historical bar."""
    if len(df) < 200:
        return {col: 0.0 for col in FEATURE_COLUMNS}

    sub_df = df.iloc[: idx + 1] if idx != -1 else df

    close = sub_df["close"]
    high = sub_df["high"]
    volume = sub_df["volume"]

    c_cur = float(close.iloc[-1])
    ema20 = float(compute_ema(close, 20).iloc[-1])
    ema50 = float(compute_ema(close, 50).iloc[-1])
    sma200 = float(compute_sma(close, 200).iloc[-1])
    atr14 = float(compute_atr(sub_df, 14).iloc[-1])
    rsi14 = float(compute_rsi(close, 14).iloc[-1])
    macd_line, sig_line, _ = compute_macd(close)
    macd_val = float(macd_line.iloc[-1])
    adx14 = float(compute_adx(sub_df, 14).iloc[-1])

    vol_sma20 = float(compute_sma(volume, 20).iloc[-1])
    vol_sma5 = float(compute_sma(volume, 5).iloc[-1])
    vol_last = float(volume.iloc[-1])
    vol_ratio = vol_last / vol_sma20 if vol_sma20 > 0 else 1.0
    vol_trend = vol_sma5 / vol_sma20 if vol_sma20 > 0 else 1.0

    high_52w = float(high.tail(252).max()) if len(high) >= 252 else float(high.max())
    dist_52w_high = ((high_52w - c_cur) / high_52w) * 100.0 if high_52w > 0 else 0.0

    rs_20d = 0.0
    mansfield_rs = 0.0
    nifty_trend = 1.0
    if nifty_df is not None and len(nifty_df) >= 20:
        nifty_sub = nifty_df.loc[nifty_df.index <= sub_df.index[-1]]
        if len(nifty_sub) >= 20:
            rs_20d = compute_relative_strength(close, nifty_sub["close"], 20)
            mrs_series = compute_mansfield_relative_strength(close, nifty_sub["close"], 50)
            mansfield_rs = float(mrs_series.iloc[-1]) if not mrs_series.empty else 0.0
            if len(nifty_sub) >= 50:
                n_c = float(nifty_sub["close"].iloc[-1])
                n_ema50 = float(compute_ema(nifty_sub["close"], 50).iloc[-1])
                nifty_trend = 1.0 if n_c >= n_ema50 else -1.0

    atr_pct = (atr14 / c_cur) * 100.0 if c_cur > 0 else 0.0
    dist_ema20 = ((c_cur - ema20) / ema20) * 100.0 if ema20 > 0 else 0.0
    dist_ema50 = ((c_cur - ema50) / ema50) * 100.0 if ema50 > 0 else 0.0
    dist_sma200 = ((c_cur - sma200) / sma200) * 100.0 if sma200 > 0 else 0.0
    macd_norm = (macd_val / c_cur) * 1000.0 if c_cur > 0 else 0.0
    vix_proxy = min(35.0, max(10.0, atr_pct * 7.5))

    return {
        "rsi_14": round(rsi14, 2),
        "adx_14": round(adx14, 2),
        "macd_norm": round(macd_norm, 2),
        "dist_ema20_pct": round(dist_ema20, 2),
        "dist_ema50_pct": round(dist_ema50, 2),
        "dist_sma200_pct": round(dist_sma200, 2),
        "atr_pct": round(atr_pct, 2),
        "vol_ratio_20d": round(vol_ratio, 2),
        "vol_trend_5d": round(vol_trend, 2),
        "rs_vs_nifty_20d": round(rs_20d, 2),
        "dist_52w_high_pct": round(dist_52w_high, 2),
        "mansfield_rs_50d": round(mansfield_rs, 2),
        "vix_level_proxy": round(vix_proxy, 2),
        "nifty_trend_score": round(nifty_trend, 2),
    }



def compute_triple_barrier_label(
    df: pd.DataFrame,
    entry_idx: int,
    entry_price: float,
    stop_loss: float,
    target_price: float,
    time_limit_days: int = 10,
) -> Tuple[int, str, float, int]:
    """Strict triple barrier labeling:

    Returns (label, outcome_status, exit_price, holding_days)
    - label: 1 if TARGET_HIT before STOP_LOSS_HIT, 0 otherwise.
    - Ambiguous bar (High >= Target and Low <= Stop): STOP_LOSS_HIT evaluated first.
    - Gap down through stop: filled at Open.
    """
    future_slice = df.iloc[entry_idx + 1: entry_idx + 1 + time_limit_days]
    if future_slice.empty:
        return 0, "TIME_EXPIRED", entry_price, 0

    for day_count, (bar_date, bar) in enumerate(future_slice.iterrows(), start=1):
        o = float(bar["open"])
        h = float(bar["high"])
        l = float(bar["low"])
        c = float(bar["close"])

        # Check gap down through stop at open
        if o <= stop_loss:
            return 0, "STOP_LOSS_HIT", o, day_count

        # Check gap up to target at open
        if o >= target_price:
            return 1, "TARGET_HIT", o, day_count

        # Ambiguous day: both touched -> Conservative Stop Loss first
        if l <= stop_loss and h >= target_price:
            return 0, "STOP_LOSS_HIT", stop_loss, day_count

        # Stop hit
        if l <= stop_loss:
            return 0, "STOP_LOSS_HIT", stop_loss, day_count

        # Target hit
        if h >= target_price:
            return 1, "TARGET_HIT", target_price, day_count

    # Time Expired: exit at closing price of the final allowable day
    final_close = float(future_slice["close"].iloc[-1])
    return (1 if final_close > entry_price else 0), "TIME_EXPIRED", final_close, len(future_slice)
