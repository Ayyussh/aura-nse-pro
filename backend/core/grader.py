"""AURA-NSE Pro Trade Outcome Grader (Section 17.7 Upgraded).

Implements institutional outcome grading on daily OHLC and intraday replay:
- Intraday Tie-Breaker: When a daily bar touches both Target and Stop, replays
  1-minute / 5-minute bars to determine true execution sequence, falling back
  conservatively to stop-first if intraday data is missing.
- Tick-Aware Levels: Rounds entry, stop, and target to exact exchange tick sizes
  (₹0.01 tick for sub-₹250 stocks, ₹0.05 tick for stocks >= ₹250).
- Realistic gap-through-stop fill at open price.
- Exact Indian brokerage, STT, exchange, and statutory deduction.
- Computes realized R-multiple from net cash P&L.
"""

from __future__ import annotations
import datetime
from typing import Dict, List, Any, Optional
import pandas as pd

from backend.costs.charges import charges_engine
from backend.tax.capital_gains import tax_engine


def round_to_exchange_tick(price: float) -> float:
    """Harmonize price to official NSE exchange tick size:

    - Stocks < ₹250.00: ₹0.01 tick size
    - Stocks >= ₹250.00: ₹0.05 tick size
    """
    if price < 250.0:
        return round(round(price / 0.01) * 0.01, 2)
    return round(round(price / 0.05) * 0.05, 2)


def replay_intraday_tie_breaker(
    intraday_candles: List[Dict[str, float]],
    stop_loss: float,
    target_price: float,
) -> Optional[Tuple[str, float, str]]:
    """Replay 1-minute or 5-minute candles to resolve ambiguous same-day bars."""
    for candle in intraday_candles:
        h = candle.get("high", 0.0)
        l = candle.get("low", 0.0)

        # Check which was hit first within this fine-grained bar
        if l <= stop_loss and h >= target_price:
            # Still ambiguous inside 1-min candle -> conservative stop first
            return "STOP_LOSS_HIT", stop_loss, "Intraday 1-min tie: conservative stop-first attributed."
        if l <= stop_loss:
            return "STOP_LOSS_HIT", stop_loss, "Intraday replay verified stop loss hit first."
        if h >= target_price:
            return "TARGET_HIT", target_price, "Intraday replay verified target reached before stop."

    return None


def grade_trade_outcome(
    symbol: str,
    entry_date: datetime.date,
    entry_price: float,
    stop_loss: float,
    target_price: float,
    quantity: int,
    time_limit_days: int,
    history_df: pd.DataFrame,
    intraday_candles_by_date: Optional[Dict[str, List[Dict[str, float]]]] = None,
) -> Dict[str, Any]:
    """Grade an open trade strictly using price bars after the entry date."""
    if history_df.empty:
        return {"status": "OPEN", "reason": "No price history available."}

    # Apply exchange tick precision
    entry_price = round_to_exchange_tick(entry_price)
    stop_loss = round_to_exchange_tick(stop_loss)
    target_price = round_to_exchange_tick(target_price)

    # Filter bars strictly after entry date
    df_after = history_df.loc[history_df.index.date > entry_date]
    if df_after.empty:
        return {"status": "OPEN", "reason": "Trade entered today; awaiting subsequent market bars."}

    bars_elapsed = len(df_after)
    final_status = "OPEN"
    exit_price = 0.0
    exit_reason = ""
    exit_date = None

    for idx, (bar_ts, bar) in enumerate(df_after.iterrows(), start=1):
        o = float(bar["open"])
        h = float(bar["high"])
        l = float(bar["low"])
        c = float(bar["close"])
        bar_date = bar_ts.date()
        date_str = bar_date.isoformat()

        # 1. Gap down through stop at open
        if o <= stop_loss:
            final_status = "STOP_LOSS_HIT"
            exit_price = round_to_exchange_tick(o)  # Slipped to market open
            exit_reason = "Gap-down below stop loss at open."
            exit_date = bar_date
            break

        # 2. Gap up to target at open
        if o >= target_price:
            final_status = "TARGET_HIT"
            exit_price = round_to_exchange_tick(o)
            exit_reason = "Gap-up to target at open."
            exit_date = bar_date
            break

        # 3. Ambiguous day: High touches target AND Low touches stop
        if l <= stop_loss and h >= target_price:
            # Check if intraday 1m/5m replay data is available
            intraday_bars = intraday_candles_by_date.get(date_str) if intraday_candles_by_date else None
            tie_result = replay_intraday_tie_breaker(intraday_bars, stop_loss, target_price) if intraday_bars else None

            if tie_result:
                final_status, exit_price, exit_reason = tie_result
            else:
                # Conservative fallback: STOP FIRST
                final_status = "STOP_LOSS_HIT"
                exit_price = stop_loss
                exit_reason = "Ambiguous bar (no intraday candles): conservative stop-first attributed."

            exit_date = bar_date
            break

        # 4. Stop touched
        if l <= stop_loss:
            final_status = "STOP_LOSS_HIT"
            exit_price = stop_loss
            exit_reason = "Stop loss touched."
            exit_date = bar_date
            break

        # 5. Target touched
        if h >= target_price:
            final_status = "TARGET_HIT"
            exit_price = target_price
            exit_reason = "Target reached."
            exit_date = bar_date
            break

        # 6. Time limit expiration
        if idx >= time_limit_days:
            final_status = "TIME_EXPIRED"
            exit_price = round_to_exchange_tick(c)
            exit_reason = f"Holding period reached {time_limit_days} days limit."
            exit_date = bar_date
            break

    if final_status == "OPEN":
        return {
            "status": "OPEN",
            "current_price": float(df_after["close"].iloc[-1]),
            "bars_held": bars_elapsed,
        }

    # Calculate real Indian charges and cash P&L
    charges = charges_engine.calculate_delivery_charges(
        buy_price=entry_price,
        sell_price=exit_price,
        quantity=quantity,
    )

    gross_pnl = round((exit_price - entry_price) * quantity, 2)
    net_pnl = round(gross_pnl - charges.total_charges_and_brokerage, 2)

    # Initial planned rupee risk
    planned_rupee_risk = max(1.0, (entry_price - stop_loss) * quantity)
    net_r = round(net_pnl / planned_rupee_risk, 2)

    # Estimated capital gains tax
    est_tax = round(max(0.0, net_pnl * tax_engine.stcg_rate), 2)

    return {
        "status": final_status,
        "exit_price": exit_price,
        "exit_reason": exit_reason,
        "exit_date": exit_date.isoformat() if exit_date else None,
        "gross_pnl_rupees": gross_pnl,
        "charges_rupees": charges.total_charges_and_brokerage,
        "net_pnl_rupees": net_pnl,
        "net_pnl_r": net_r,
        "tax_estimated_rupees": est_tax,
        "charges_breakdown": charges.to_dict(),
    }
