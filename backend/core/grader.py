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
from typing import Dict, List, Any, Optional, Tuple
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
    intraday_candles: List[Dict[str, Any]],
    stop_loss: float,
    target_price: float,
    fill_time: Optional[datetime.time] = None,
) -> Optional[Tuple[str, float, str]]:
    """Replay 1-minute or 5-minute candles to resolve ambiguous same-day bars."""
    for candle in intraday_candles:
        candle_time = candle.get("time")
        if fill_time and candle_time:
            if isinstance(candle_time, str):
                try:
                    c_time = datetime.time.fromisoformat(candle_time)
                except Exception:
                    c_time = None
            elif isinstance(candle_time, datetime.time):
                c_time = candle_time
            else:
                c_time = None
            if c_time and c_time <= fill_time:
                continue

        h = float(candle.get("high", 0.0))
        l = float(candle.get("low", 0.0))

        # Check which was hit first within this fine-grained bar
        if l <= stop_loss and h >= target_price:
            # Still ambiguous inside fine-grained candle -> conservative stop first
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
    entry_at_open: bool = True,
    fill_time: Optional[datetime.time] = None,
    intraday_candles_by_date: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """Grade an open trade with precise time-of-fill awareness.

    - When entry_at_open is True: evaluates entry bar starting from open fill.
      If open gaps through stop, status is SKIPPED_GAP_DOWN (trade not filled).
    - When entry_at_open is False: strictly evaluates bars after entry_date.
    - Intraday entries evaluate 5-minute bars strictly after fill_time.
    """
    if history_df.empty:
        return {"status": "OPEN", "reason": "No price history available."}

    # Apply exchange tick precision
    entry_price = round_to_exchange_tick(entry_price)
    stop_loss = round_to_exchange_tick(stop_loss)
    target_price = round_to_exchange_tick(target_price)

    # Determine candidate bars
    if entry_at_open:
        df_bars = history_df.loc[history_df.index.date >= entry_date]
    else:
        df_bars = history_df.loc[history_df.index.date > entry_date]

    if df_bars.empty:
        return {"status": "OPEN", "reason": "Trade entered today; awaiting subsequent market bars."}

    bars_elapsed = len(df_bars)
    final_status = "OPEN"
    exit_price = 0.0
    exit_reason = ""
    exit_date = None

    for idx, (bar_ts, bar) in enumerate(df_bars.iterrows(), start=1):
        o = float(bar["open"])
        h = float(bar["high"])
        l = float(bar["low"])
        c = float(bar["close"])
        bar_date = bar_ts.date()
        date_str = bar_date.isoformat()

        # Handle entry day when entry is at market open
        if bar_date == entry_date and entry_at_open:
            # 1. Open gaps down through stop loss -> Trade is skipped (never filled)
            if o <= stop_loss:
                return {
                    "status": "SKIPPED_GAP_DOWN",
                    "exit_price": round_to_exchange_tick(o),
                    "exit_reason": f"Gapped down through stop loss at open (Open ₹{o} <= Stop ₹{stop_loss}); trade was not filled.",
                    "exit_date": bar_date.isoformat(),
                    "gross_pnl_rupees": 0.0,
                    "gross_pnl_r": 0.0,
                    "charges_rupees": 0.0,
                    "net_pnl_rupees": 0.0,
                    "net_pnl_r": 0.0,
                    "tax_estimated_rupees": 0.0,
                    "charges_breakdown": {},
                }

            # 2. Open gaps up to target -> Filled and exited at open
            if o >= target_price:
                final_status = "TARGET_HIT"
                exit_price = round_to_exchange_tick(o)
                exit_reason = "Gap-up above target at market open."
                exit_date = bar_date
                break

            # 3. Intraday replay on entry day (evaluating only bars after fill_time)
            intraday_bars = intraday_candles_by_date.get(date_str) if intraday_candles_by_date else None
            active_fill_time = fill_time or datetime.time(9, 15)
            tie_result = replay_intraday_tie_breaker(intraday_bars, stop_loss, target_price, fill_time=active_fill_time) if intraday_bars else None

            if tie_result:
                final_status, exit_price, exit_reason = tie_result
                exit_date = bar_date
                break
            elif l <= stop_loss and h >= target_price:
                final_status = "STOP_LOSS_HIT"
                exit_price = stop_loss
                exit_reason = "Ambiguous bar on entry day (no intraday replay): conservative stop-first attributed."
                exit_date = bar_date
                break
            elif l <= stop_loss:
                final_status = "STOP_LOSS_HIT"
                exit_price = stop_loss
                exit_reason = "Stop loss touched on entry day."
                exit_date = bar_date
                break
            elif h >= target_price:
                final_status = "TARGET_HIT"
                exit_price = target_price
                exit_reason = "Target reached on entry day."
                exit_date = bar_date
                break

            # If neither touched on entry day, continue to subsequent days
            continue

        # For subsequent days (strictly after entry)
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
            intraday_bars = intraday_candles_by_date.get(date_str) if intraday_candles_by_date else None
            tie_result = replay_intraday_tie_breaker(intraday_bars, stop_loss, target_price) if intraday_bars else None

            if tie_result:
                final_status, exit_price, exit_reason = tie_result
            else:
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
            "current_price": float(df_bars["close"].iloc[-1]),
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
    gross_r = round(gross_pnl / planned_rupee_risk, 2)
    net_r = round(net_pnl / planned_rupee_risk, 2)

    # Estimated capital gains tax
    est_tax = round(max(0.0, net_pnl * tax_engine.stcg_rate), 2)

    return {
        "status": final_status,
        "exit_price": exit_price,
        "exit_reason": exit_reason,
        "exit_date": exit_date.isoformat() if exit_date else None,
        "gross_pnl_rupees": gross_pnl,
        "gross_pnl_r": gross_r,
        "charges_rupees": charges.total_charges_and_brokerage,
        "net_pnl_rupees": net_pnl,
        "net_pnl_r": net_r,
        "tax_estimated_rupees": est_tax,
        "charges_breakdown": charges.to_dict(),
    }
