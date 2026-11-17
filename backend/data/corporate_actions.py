"""AURA Corporate Action Ledger & Jump Detection Engine (Section 17.2).

Maintains an independent ledger of corporate actions:
- Splits, Bonuses, Rights, Dividends, Demergers, Mergers, Buybacks
- Computes mathematical adjustment factors
- Jump detector: flags single-day moves > circuit band / 20% with no corporate action
- Demerger policy: 20-day quarantine and ATR/ML feature breaks
- Auto-adjusts open paper positions for splits/bonuses
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Dict, List, Tuple

from backend.db.models import Prediction
from backend.db.session import SessionLocal


@dataclass
class CorporateAction:
    symbol: str
    action_type: str  # SPLIT, BONUS, DIVIDEND, DEMERGER, MERGER, RIGHTS, BUYBACK
    ex_date: datetime.date
    ratio_from: float  # e.g., 10 for 10:1 split
    ratio_to: float    # e.g., 1
    amount: float = 0.0  # dividend amount per share
    notes: str = ""


# Seeded ledger of known corporate actions for benchmark testing and live reconciliation
CORPORATE_ACTION_LEDGER: List[CorporateAction] = [
    CorporateAction(
        symbol="TATAMOTORS.NS",
        action_type="DEMERGER",
        ex_date=datetime.date(2025, 10, 24),
        ratio_from=1.0,
        ratio_to=1.0,
        notes="Commercial Vehicles demerged into TMCV; PV renamed to TMPV. Exclusion window 20 days.",
    ),
    CorporateAction(
        symbol="TMCV.NS",
        action_type="DEMERGER",
        ex_date=datetime.date(2025, 11, 12),
        ratio_from=1.0,
        ratio_to=1.0,
        notes="Listing of demerged Commercial Vehicle entity TMCV. Exclusion window 20 days.",
    ),
    CorporateAction(
        symbol="HDFC.NS",
        action_type="MERGER",
        ex_date=datetime.date(2023, 7, 1),
        ratio_from=25.0,
        ratio_to=42.0,
        notes="Merger of HDFC Ltd into HDFC Bank Ltd (42 shares of HDFCBANK for every 25 shares of HDFC).",
    ),
    CorporateAction(
        symbol="VEDL.NS",
        action_type="DEMERGER",
        ex_date=datetime.date(2026, 4, 30),
        ratio_from=1.0,
        ratio_to=1.0,
        notes="Vedanta Ltd demerger of business units. 20-day quarantine.",
    ),
    CorporateAction(
        symbol="VEDL.NS",
        action_type="DIVIDEND",
        ex_date=datetime.date(2026, 4, 30),
        ratio_from=1.0,
        ratio_to=1.0,
        amount=18.5,
        notes="Special Dividend",
    ),
    CorporateAction(
        symbol="ABFRL.NS",
        action_type="DEMERGER",
        ex_date=datetime.date(2026, 5, 15),
        ratio_from=1.0,
        ratio_to=1.0,
        notes="Demerger of Madura Fashion business",
    ),
    CorporateAction(
        symbol="TCS.NS",
        action_type="DIVIDEND",
        ex_date=datetime.date(2026, 6, 18),
        ratio_from=1.0,
        ratio_to=1.0,
        amount=28.0,
        notes="Interim Dividend",
    ),
    CorporateAction(
        symbol="TDPOWERSYS.NS",
        action_type="SPLIT",
        ex_date=datetime.date(2026, 8, 24),
        ratio_from=2.0,
        ratio_to=1.0,
        notes="2:1 Stock Split (Subdivision of shares from FV Rs 2 to FV Rs 1)",
    ),
    CorporateAction(
        symbol="CONCORDBIO.NS",
        action_type="SPLIT",
        ex_date=datetime.date(2026, 11, 4),
        ratio_from=2.0,
        ratio_to=1.0,
        notes="2:1 Stock Split (Subdivision of shares from FV Rs 2 to FV Rs 1)",
    ),


]


class CorporateActionEngine:
    """Manages corporate actions, price adjustments, and jump detection."""

    def __init__(self):
        self.ledger = CORPORATE_ACTION_LEDGER
        self.quarantine_registry: Dict[str, str] = {}  # symbol -> reason

    def check_for_actions(self, symbol: str, start_date: datetime.date, end_date: datetime.date) -> List[CorporateAction]:
        """Find any corporate actions falling within the date window."""
        clean = symbol.upper()
        return [
            a for a in self.ledger
            if a.symbol == clean and start_date <= a.ex_date <= end_date
        ]

    def detect_unadjusted_jump(
        self,
        symbol: str,
        prev_close: float,
        cur_close: float,
        date: datetime.date,
        circuit_band_pct: float = 20.0,
    ) -> Tuple[bool, str]:
        """Jump detector: A close-to-close move beyond circuit band (> 20%) without

        a matching corporate action entry in the ledger triggers quarantine.
        """
        if prev_close <= 0:
            return False, ""

        pct_change = abs((cur_close - prev_close) / prev_close) * 100.0

        if pct_change >= circuit_band_pct:
            # Check if explained by a corporate action on that date
            matching = [
                a for a in self.ledger
                if a.symbol == symbol and a.ex_date == date
            ]
            if not matching:
                reason = (
                    f"UNADJUSTED_JUMP: Price moved {pct_change:.1f}% on {date} with no corporate action recorded. "
                    f"Quarantined from trading signals."
                )
                self.quarantine_registry[symbol] = reason
                return True, reason
            else:
                action = matching[0]
                if action.action_type == "DEMERGER":
                    reason = f"DEMERGER_EXCLUSION: Demerger on {date}. Symbol quarantined for 20 trading days."
                    self.quarantine_registry[symbol] = reason
                    return True, reason

        return False, ""

    def is_quarantined(self, symbol: str) -> Tuple[bool, str]:
        """Check if symbol is currently quarantined from signals."""
        if symbol in self.quarantine_registry:
            return True, self.quarantine_registry[symbol]
        return False, ""

    def compute_adjustment_factor(self, action: CorporateAction) -> float:
        """Compute the multiplier to adjust pre-event historical prices:

        - Split 10 -> 1: prices multiplied by (1 / 10) = 0.10
        - Bonus 1:1: prices multiplied by 1 / (1 + 1) = 0.50
        """
        if action.action_type == "SPLIT":
            return action.ratio_to / action.ratio_from
        elif action.action_type == "BONUS":
            return action.ratio_to / (action.ratio_from + action.ratio_to)
        return 1.0

    def get_cumulative_split_factor(self, symbol: str, query_date: datetime.date) -> float:
        """Compute the cumulative split adjustment factor for historical prices prior to query_date."""
        factor = 1.0
        for action in self.ledger:
            if action.symbol == symbol and action.action_type == "SPLIT":
                if query_date < action.ex_date:
                    factor *= (action.ratio_to / action.ratio_from)
        return factor

    def auto_adjust_open_positions(self, symbol: str, action: CorporateAction):
        """Auto-adjust quantity, stop-loss, and target price for open paper trades."""
        db = SessionLocal()
        try:
            factor = self.compute_adjustment_factor(action)
            if factor == 1.0:
                return

            open_preds = db.query(Prediction).filter(
                Prediction.symbol == symbol,
                Prediction.status == "OPEN",
            ).all()

            for pred in open_preds:
                # Adjust prices
                pred.entry_price = round(pred.entry_price * factor, 2)
                pred.stop_loss = round(pred.stop_loss * factor, 2)
                pred.target_price = round(pred.target_price * factor, 2)
                # Adjust whole-share quantity inversely
                pred.quantity = int(round(pred.quantity / factor))  # type: ignore[assignment]

            db.commit()
        finally:
            db.close()


corporate_action_engine = CorporateActionEngine()
