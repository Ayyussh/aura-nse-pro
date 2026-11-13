"""Broker Contract Note & Tradebook Reconciliation Engine (Section 17.6).

Imports broker tradebooks (Zerodha, Upstox, Groww CSVs) to:
- Compare actual fills against planned entry prices (Execution Slippage)
- Compare actual statutory charges against the Indian Charges Engine
- Fire 'Charge Drift' alerts if charges differ by > ₹10 per trade
- Recalibrate slippage assumptions from real fills.
"""

from __future__ import annotations
import csv
import io
from dataclasses import dataclass
from typing import Dict, List, Any, Optional

from backend.costs.charges import charges_engine


@dataclass
class TradebookRecord:
    symbol: str
    trade_date: str
    side: str  # BUY or SELL
    quantity: int
    price: float
    total_charges_actual: float
    brokerage_actual: float = 0.0
    stt_actual: float = 0.0


class ContractNoteReconciliationEngine:
    """Audits real broker contract notes against theoretical model predictions."""

    def parse_tradebook_csv(self, csv_content: str) -> List[TradebookRecord]:
        """Parse standard broker tradebook CSV format."""
        records: List[TradebookRecord] = []
        reader = csv.DictReader(io.StringIO(csv_content))

        for row in reader:
            # Handle varied column naming across Zerodha, Upstox, Groww
            sym = row.get("symbol") or row.get("Symbol") or row.get("Tradingsymbol") or ""
            if not sym:
                continue

            clean_sym = sym.strip()
            if not clean_sym.endswith(".NS") and not clean_sym.endswith(".BO"):
                clean_sym = f"{clean_sym}.NS"

            date_str = row.get("trade_date") or row.get("Trade Date") or row.get("Order Date") or ""
            side = (row.get("trade_type") or row.get("Side") or row.get("Type") or "BUY").strip().upper()
            qty = abs(int(float(row.get("quantity") or row.get("Qty") or 1)))
            price = float(row.get("price") or row.get("Price") or row.get("Average Price") or 0.0)

            # Charges if present in row
            charges = float(row.get("total_charges") or row.get("Charges") or 0.0)

            records.append(TradebookRecord(
                symbol=clean_sym,
                trade_date=date_str,
                side=side,
                quantity=qty,
                price=price,
                total_charges_actual=charges,
            ))

        return records

    def audit_trade_fills(
        self,
        planned_trades: List[Dict[str, Any]],
        actual_records: List[TradebookRecord],
    ) -> Dict[str, Any]:
        """Compare planned entries vs actual broker fills."""
        audit_results = []
        drift_alerts = []
        slippage_diffs = []

        for plan in planned_trades:
            sym = plan.get("symbol")
            plan_price = plan.get("entry_price", 0.0)
            plan_qty = plan.get("quantity", 0)

            # Find matching actual record
            matches = [r for r in actual_records if r.symbol == sym]
            if not matches:
                continue

            actual = matches[0]
            slippage_pts = actual.price - plan_price
            slippage_pct = (slippage_pts / plan_price * 100.0) if plan_price > 0 else 0.0
            slippage_diffs.append(slippage_pct)

            # Calculate theoretical model charges
            model_charges = charges_engine.calculate_delivery_charges(
                buy_price=actual.price,
                sell_price=actual.price * 1.05,
                quantity=actual.quantity,
            )

            # Charge drift check: if broker charges differ by > ₹10
            charge_drift = abs(actual.total_charges_actual - (model_charges.total_charges_and_brokerage / 2.0))
            is_drift_flagged = actual.total_charges_actual > 0 and charge_drift > 10.0

            if is_drift_flagged:
                drift_alerts.append({
                    "symbol": sym,
                    "model_est": round(model_charges.total_charges_and_brokerage / 2.0, 2),
                    "actual_broker": actual.total_charges_actual,
                    "drift_rupees": round(charge_drift, 2),
                })

            audit_results.append({
                "symbol": sym,
                "planned_price": plan_price,
                "actual_fill_price": actual.price,
                "slippage_rupees": round(slippage_pts, 2),
                "slippage_pct": round(slippage_pct, 2),
                "charge_drift_flagged": is_drift_flagged,
            })

        avg_slippage = sum(slippage_diffs) / len(slippage_diffs) if slippage_diffs else 0.0

        return {
            "audited_trades_count": len(audit_results),
            "charge_drift_alerts": drift_alerts,
            "average_execution_slippage_pct": round(avg_slippage, 3),
            "records": audit_results,
        }


contract_note_engine = ContractNoteReconciliationEngine()
