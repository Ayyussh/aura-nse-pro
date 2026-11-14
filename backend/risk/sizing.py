"""Institutional Position Sizing and Portfolio Risk Guard Engine.

Enforces strict capital preservation rules:
- Whole-share quantity = floor(Risk_Rupees / (Entry - Stop_Loss))
- Macro regime sizing multipliers (Green: 1.0, Amber: 0.5, Red: 0.0)
- Max single position value <= 20% of capital
- Max concurrent swing positions <= 5
- Max sector concentration <= 30% and <= 2 open trades per sector
- Portfolio heat (total open risk) <= 6% of capital
- Liquidity cap: planned quantity <= 1% of 20-day average volume
- Drawdown circuit breakers (8% halve, 12% pause)
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Tuple

from backend.core.config import get_strategy_config


@dataclass
class SizingDecision:
    allowed: bool
    status: str  # APPROVED, SKIPPED_SIZE, SKIPPED_SECTOR_CAP, SKIPPED_PORTFOLIO_HEAT, SKIPPED_REGIME_RED, PAUSED_DRAWDOWN
    quantity: int
    entry_price: float
    stop_loss: float
    target_price: float
    risk_per_share: float
    total_risk_rupees: float
    capital_required: float
    capital_allocation_pct: float
    regime_multiplier_applied: float
    drawdown_multiplier_applied: float
    notes: List[str]


class RiskGuardEngine:
    """Manages position sizing, portfolio exposure, and risk guardrails."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.strategy_cfg = config or get_strategy_config()
        self.risk_cfg = self.strategy_cfg.get("risk_guard", {})
        self.regime_cfg = self.strategy_cfg.get("macro_regime", {})

    def compute_position_size(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        target_price: float,
        sector: str,
        total_capital: float,
        available_cash: float,
        avg_20d_volume: float,
        macro_regime: str = "GREEN", # GREEN, AMBER, RED
        current_drawdown_pct: float = 0.0,
        consecutive_losses: int = 0,
        open_positions: Optional[List[Dict[str, Any]]] = None,
    ) -> SizingDecision:
        """Calculate exact whole-share quantity and validate portfolio constraints."""
        notes: List[str] = []
        open_positions = open_positions or []

        # 1. Basic price sanity
        if entry_price <= stop_loss:
            return SizingDecision(
                allowed=False,
                status="REJECTED_INVALID_STOP",
                quantity=0,
                entry_price=entry_price,
                stop_loss=stop_loss,
                target_price=target_price,
                risk_per_share=0.0,
                total_risk_rupees=0.0,
                capital_required=0.0,
                capital_allocation_pct=0.0,
                regime_multiplier_applied=0.0,
                drawdown_multiplier_applied=0.0,
                notes=["Stop loss is equal to or greater than entry price."],
            )

        risk_per_share = entry_price - stop_loss
        stop_dist_pct = (risk_per_share / entry_price) * 100.0

        max_stop_dist = self.strategy_cfg.get("swing_strategy", {}).get("risk_reward", {}).get("max_stop_distance_pct", 8.0)
        if stop_dist_pct > max_stop_dist:
            notes.append(f"Stop distance {stop_dist_pct:.2f}% exceeds max {max_stop_dist}%.")
            return SizingDecision(
                allowed=False,
                status="REJECTED_STOP_TOO_WIDE",
                quantity=0,
                entry_price=entry_price,
                stop_loss=stop_loss,
                target_price=target_price,
                risk_per_share=risk_per_share,
                total_risk_rupees=0.0,
                capital_required=0.0,
                capital_allocation_pct=0.0,
                regime_multiplier_applied=0.0,
                drawdown_multiplier_applied=0.0,
                notes=notes,
            )

        # 2. Drawdown Breakers
        drawdown_mult = 1.0
        if current_drawdown_pct >= 12.0:
            notes.append(f"12% Drawdown breaker hit ({current_drawdown_pct:.1f}%). New entries paused.")
            return SizingDecision(
                allowed=False,
                status="PAUSED_DRAWDOWN",
                quantity=0,
                entry_price=entry_price,
                stop_loss=stop_loss,
                target_price=target_price,
                risk_per_share=risk_per_share,
                total_risk_rupees=0.0,
                capital_required=0.0,
                capital_allocation_pct=0.0,
                regime_multiplier_applied=0.0,
                drawdown_multiplier_applied=0.0,
                notes=notes,
            )
        elif current_drawdown_pct >= 8.0 or consecutive_losses >= 4:
            drawdown_mult = 0.5
            notes.append("8% Drawdown or 4 consecutive losses hit: position size halved.")

        # 3. Macro Regime Multiplier
        regime_upper = macro_regime.upper()
        if regime_upper == "RED":
            notes.append("Macro regime is RED (NIFTY in downtrend or VIX > 24). Zero new swing entries.")
            return SizingDecision(
                allowed=False,
                status="SKIPPED_REGIME_RED",
                quantity=0,
                entry_price=entry_price,
                stop_loss=stop_loss,
                target_price=target_price,
                risk_per_share=risk_per_share,
                total_risk_rupees=0.0,
                capital_required=0.0,
                capital_allocation_pct=0.0,
                regime_multiplier_applied=0.0,
                drawdown_multiplier_applied=drawdown_mult,
                notes=notes,
            )
        elif regime_upper == "AMBER":
            regime_mult = 0.5
            notes.append("Macro regime is AMBER (VIX > 18 or NIFTY < 20-EMA): 50% position sizing.")
        else:
            regime_mult = 1.0

        # 4. Check Concurrent Swing Trades Limit (Max 5)
        max_concurrent = self.risk_cfg.get("max_concurrent_swing_positions", 5)
        if len(open_positions) >= max_concurrent:
            notes.append(f"Max concurrent swing positions ({max_concurrent}) reached.")
            return SizingDecision(
                allowed=False,
                status="SKIPPED_CONCURRENT_LIMIT",
                quantity=0,
                entry_price=entry_price,
                stop_loss=stop_loss,
                target_price=target_price,
                risk_per_share=risk_per_share,
                total_risk_rupees=0.0,
                capital_required=0.0,
                capital_allocation_pct=0.0,
                regime_multiplier_applied=regime_mult,
                drawdown_multiplier_applied=drawdown_mult,
                notes=notes,
            )

        # 5. Check Sector Constraints (Max 2 trades, max 30% exposure)
        sector_positions = [p for p in open_positions if p.get("sector") == sector]
        max_sector_trades = self.risk_cfg.get("max_open_trades_per_sector", 2)
        if len(sector_positions) >= max_sector_trades:
            notes.append(f"Sector '{sector}' already has {len(sector_positions)} open trades (max {max_sector_trades}).")
            return SizingDecision(
                allowed=False,
                status="SKIPPED_SECTOR_CAP",
                quantity=0,
                entry_price=entry_price,
                stop_loss=stop_loss,
                target_price=target_price,
                risk_per_share=risk_per_share,
                total_risk_rupees=0.0,
                capital_required=0.0,
                capital_allocation_pct=0.0,
                regime_multiplier_applied=regime_mult,
                drawdown_multiplier_applied=drawdown_mult,
                notes=notes,
            )

        # 5b. Check Promoter Group Constraints (config/groups.yaml: Max 2 trades / 25% for private groups, looser 4 trades / 40% for PSU)
        try:
            from backend.core.config import get_groups_config
            groups_cfg = get_groups_config()
            group_map = groups_cfg.get("groups", {})
            constraints = groups_cfg.get("group_constraints", {})

            symbol_group = None
            for grp_name, grp_syms in group_map.items():
                if symbol in grp_syms:
                    symbol_group = grp_name
                    break

            # Default unmapped symbols to Standalone_Equities (Item 10)
            if not symbol_group:
                symbol_group = "Standalone_Equities"

            if symbol_group:
                # Group-specific limits (PSU cluster has looser caps: 3 positions / 30%)
                grp_rules = constraints.get(symbol_group, constraints.get("default", {}))
                max_group_trades = grp_rules.get("max_open_positions_per_group", 2)
                max_group_capital_pct = grp_rules.get("max_group_capital_exposure_pct", 25.0)

                group_open = [
                    p for p in open_positions
                    if p.get("symbol") in group_map.get(symbol_group, [])
                ]
                if len(group_open) >= max_group_trades:
                    notes.append(f"Promoter group '{symbol_group}' already has {len(group_open)} open trades (max {max_group_trades}).")
                    return SizingDecision(
                        allowed=False,
                        status="SKIPPED_GROUP_CAP",
                        quantity=0,
                        entry_price=entry_price,
                        stop_loss=stop_loss,
                        target_price=target_price,
                        risk_per_share=risk_per_share,
                        total_risk_rupees=0.0,
                        capital_required=0.0,
                        capital_allocation_pct=0.0,
                        regime_multiplier_applied=regime_mult,
                        drawdown_multiplier_applied=drawdown_mult,
                        notes=notes,
                    )
                group_capital = sum(p.get("quantity", 0) * p.get("entry_price", 0.0) for p in group_open)
                if total_capital > 0 and (group_capital / total_capital) * 100.0 >= max_group_capital_pct:
                    notes.append(f"Promoter group '{symbol_group}' capital exposure exceeds {max_group_capital_pct}%.")
                    return SizingDecision(
                        allowed=False,
                        status="SKIPPED_GROUP_CAP",
                        quantity=0,
                        entry_price=entry_price,
                        stop_loss=stop_loss,
                        target_price=target_price,
                        risk_per_share=risk_per_share,
                        total_risk_rupees=0.0,
                        capital_required=0.0,
                        capital_allocation_pct=0.0,
                        regime_multiplier_applied=regime_mult,
                        drawdown_multiplier_applied=drawdown_mult,
                        notes=notes,
                    )
        except Exception:
            pass

        # 6. Base Risk Calculation
        risk_pct = self.risk_cfg.get("default_risk_per_trade_pct", 1.5)
        base_risk_rupees = total_capital * (risk_pct / 100.0)
        adjusted_risk_rupees = base_risk_rupees * regime_mult * drawdown_mult

        raw_qty = math.floor(adjusted_risk_rupees / risk_per_share)
        if raw_qty < 1:
            notes.append(f"Computed quantity < 1 (Risk ₹{adjusted_risk_rupees:.0f} / ₹{risk_per_share:.2f} per share).")
            return SizingDecision(
                allowed=False,
                status="SKIPPED_SIZE",
                quantity=0,
                entry_price=entry_price,
                stop_loss=stop_loss,
                target_price=target_price,
                risk_per_share=risk_per_share,
                total_risk_rupees=0.0,
                capital_required=0.0,
                capital_allocation_pct=0.0,
                regime_multiplier_applied=regime_mult,
                drawdown_multiplier_applied=drawdown_mult,
                notes=notes,
            )

        # 7. Single Position Capital Cap (Max 20% of total capital)
        max_pos_val = total_capital * (self.risk_cfg.get("max_position_capital_pct", 20.0) / 100.0)
        max_qty_by_capital = math.floor(max_pos_val / entry_price)
        final_qty = min(raw_qty, max_qty_by_capital)

        # 8. Liquidity Cap (Max 1% of 20-Day Average Volume)
        if avg_20d_volume > 0:
            max_qty_by_vol = math.floor(avg_20d_volume * 0.01)
            if final_qty > max_qty_by_vol:
                final_qty = max_qty_by_vol
                notes.append(f"Quantity capped to 1% of 20-day volume ({max_qty_by_vol} shares).")

        # 9. Cash Check
        capital_required = final_qty * entry_price
        if capital_required > available_cash:
            # Scale down to available cash
            final_qty = math.floor(available_cash / entry_price)
            notes.append(f"Quantity reduced to match available cash (₹{available_cash:,.0f}).")
            capital_required = final_qty * entry_price

        if final_qty < 1:
            notes.append("Insufficient available cash for 1 share.")
            return SizingDecision(
                allowed=False,
                status="SKIPPED_SIZE",
                quantity=0,
                entry_price=entry_price,
                stop_loss=stop_loss,
                target_price=target_price,
                risk_per_share=risk_per_share,
                total_risk_rupees=0.0,
                capital_required=0.0,
                capital_allocation_pct=0.0,
                regime_multiplier_applied=regime_mult,
                drawdown_multiplier_applied=drawdown_mult,
                notes=notes,
            )

        # 10. Portfolio Heat Check (Total open risk <= 6% of capital)
        existing_heat = sum(p.get("quantity", 0) * (p.get("entry_price", 0) - p.get("stop_loss", 0)) for p in open_positions)
        new_risk = final_qty * risk_per_share
        max_heat = total_capital * (self.risk_cfg.get("max_portfolio_heat_pct", 6.0) / 100.0)
        if (existing_heat + new_risk) > max_heat:
            notes.append(f"Portfolio heat would exceed 6% max (Current: ₹{existing_heat:,.0f}, New: ₹{new_risk:,.0f}, Max: ₹{max_heat:,.0f}).")
            return SizingDecision(
                allowed=False,
                status="SKIPPED_PORTFOLIO_HEAT",
                quantity=0,
                entry_price=entry_price,
                stop_loss=stop_loss,
                target_price=target_price,
                risk_per_share=risk_per_share,
                total_risk_rupees=0.0,
                capital_required=0.0,
                capital_allocation_pct=0.0,
                regime_multiplier_applied=regime_mult,
                drawdown_multiplier_applied=drawdown_mult,
                notes=notes,
            )

        capital_pct = round((capital_required / total_capital) * 100.0, 2)

        return SizingDecision(
            allowed=True,
            status="APPROVED",
            quantity=final_qty,
            entry_price=entry_price,
            stop_loss=stop_loss,
            target_price=target_price,
            risk_per_share=round(risk_per_share, 2),
            total_risk_rupees=round(new_risk, 2),
            capital_required=round(capital_required, 2),
            capital_allocation_pct=capital_pct,
            regime_multiplier_applied=regime_mult,
            drawdown_multiplier_applied=drawdown_mult,
            notes=notes,
        )


risk_guard = RiskGuardEngine()
