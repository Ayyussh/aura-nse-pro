"""Technical Indicators and Quantitative Calculations.

Self-contained, robust vectorized calculations using pandas and numpy
for EMA, SMA, ATR, RSI, MACD, ADX, and Relative Strength.
"""

from __future__ import annotations
import numpy as np
import pandas as pd


def compute_sma(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=period, min_periods=period).mean()


def compute_ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average."""
    return series.ewm(span=period, adjust=False).mean()


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range (ATR)."""
    high = df["high"]
    low = df["low"]
    close_prev = df["close"].shift(1)

    tr1 = high - low
    tr2 = (high - close_prev).abs()
    tr3 = (low - close_prev).abs()

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return true_range.ewm(span=period, adjust=False).mean()


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index (RSI)."""
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -1.0 * delta.clip(upper=0.0)

    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.fillna(50.0)


def compute_macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Moving Average Convergence Divergence (MACD)."""
    ema_fast = compute_ema(series, fast)
    ema_slow = compute_ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = compute_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def compute_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average Directional Index (ADX) measuring trend strength."""
    high = df["high"]
    low = df["low"]
    close_prev = df["close"].shift(1)

    up_move = high - high.shift(1)
    down_move = low.shift(1) - low

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr1 = high - low
    tr2 = (high - close_prev).abs()
    tr3 = (low - close_prev).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    tr_smoothed = true_range.ewm(alpha=1.0 / period, adjust=False).mean()
    plus_dm_smoothed = pd.Series(plus_dm, index=df.index).ewm(alpha=1.0 / period, adjust=False).mean()
    minus_dm_smoothed = pd.Series(minus_dm, index=df.index).ewm(alpha=1.0 / period, adjust=False).mean()

    plus_di = 100.0 * (plus_dm_smoothed / tr_smoothed.replace(0, np.nan))
    minus_di = 100.0 * (minus_dm_smoothed / tr_smoothed.replace(0, np.nan))

    dx = 100.0 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    adx = dx.ewm(alpha=1.0 / period, adjust=False).mean()
    return adx.fillna(0.0)


def compute_relative_strength(stock_close: pd.Series, benchmark_close: pd.Series, period: int = 20) -> float:
    """Compute percentage outperformance of stock vs benchmark over specified lookback."""
    if len(stock_close) < period or len(benchmark_close) < period:
        return 0.0

    stock_ret = (stock_close.iloc[-1] / stock_close.iloc[-period] - 1.0) * 100.0
    bench_ret = (benchmark_close.iloc[-1] / benchmark_close.iloc[-period] - 1.0) * 100.0
    return round(float(stock_ret - bench_ret), 2)


def compute_mansfield_relative_strength(
    stock_close: pd.Series,
    benchmark_close: pd.Series,
    period: int = 50,
) -> pd.Series:
    """Institutional Mansfield Relative Strength (MRS) vs Benchmark:
    
    Formula:
      BP = Stock_Close / Benchmark_Close
      MRS = ((BP / SMA(BP, period)) - 1.0) * 100.0
      
    Values > 0 indicate true institutional outperformance against benchmark base.
    """
    if len(stock_close) < period or len(benchmark_close) < period:
        return pd.Series(0.0, index=stock_close.index)

    # Reindex benchmark to match stock series
    bench_aligned = benchmark_close.reindex(stock_close.index).ffill().bfill()
    base_performance = stock_close / bench_aligned.replace(0, np.nan)
    sma_bp = compute_sma(base_performance, period)
    mrs = ((base_performance / sma_bp.replace(0, np.nan)) - 1.0) * 100.0
    return mrs.fillna(0.0)
