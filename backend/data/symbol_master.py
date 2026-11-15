"""Symbol Master & Historical Ticker Change Resolver (Section 17 / Gate G1).

Tracks official corporate symbol changes, amalgamations, demergers, and ISIN mappings
with effective dates to ensure survivorship-bias-free continuous historical data lookups.
"""

from __future__ import annotations
import datetime
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

from backend.core.config import PROJECT_ROOT

logger = logging.getLogger("aura.symbol_master")
SYMBOL_MASTER_PATH = PROJECT_ROOT / "data" / "symbol_master.json"


class SymbolMaster:
    """Manages official NSE symbol transformations with effective dates and ISINs."""

    def __init__(self, master_path: Optional[Path] = None):
        self.master_path = master_path or SYMBOL_MASTER_PATH
        self.records: List[Dict[str, Any]] = []
        self._old_to_record: Dict[str, List[Dict[str, Any]]] = {}
        self._isin_to_record: Dict[str, Dict[str, Any]] = {}
        self.load_master()

    def load_master(self):
        """Load symbol master records from JSON file."""
        if not self.master_path.exists():
            logger.warning(f"Symbol master not found at {self.master_path}")
            return

        try:
            with open(self.master_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.records = data.get("symbol_changes", [])
            self._old_to_record.clear()
            self._isin_to_record.clear()

            for rec in self.records:
                old_sym = rec["old_symbol"].upper()
                self._old_to_record.setdefault(old_sym, []).append(rec)
                isin = rec.get("isin")
                if isin:
                    self._isin_to_record[isin] = rec
        except Exception as e:
            logger.error(f"Error loading symbol master: {e}")

    def resolve_symbol_at_date(self, symbol: str, query_date: Optional[datetime.date] = None) -> str:
        """Resolve a legacy or current symbol to the active ticker on a given query date."""
        base_sym = symbol.upper().replace(".NS", "").replace(".BO", "")
        if query_date is None:
            query_date = datetime.date.today()

        if base_sym in self._old_to_record:
            for rec in self._old_to_record[base_sym]:
                eff_date = datetime.date.fromisoformat(rec["effective_date"])
                if query_date >= eff_date:
                    resolved = rec["new_symbol"]
                    return f"{resolved}.NS" if symbol.endswith(".NS") else resolved

        # Also check reverse (querying with new symbol for an earlier date)
        for rec in self.records:
            if rec["new_symbol"].upper() == base_sym:
                eff_date = datetime.date.fromisoformat(rec["effective_date"])
                if query_date < eff_date:
                    resolved = rec["old_symbol"]
                    return f"{resolved}.NS" if symbol.endswith(".NS") else resolved

        return symbol

    def get_isin_for_symbol(self, symbol: str) -> Optional[str]:
        """Look up the permanent ISIN for a symbol."""
        base_sym = symbol.upper().replace(".NS", "").replace(".BO", "")
        for rec in self.records:
            if rec["old_symbol"].upper() == base_sym or rec["new_symbol"].upper() == base_sym:
                return rec.get("isin")
        return None

    def get_change_history(self, symbol: str) -> List[Dict[str, Any]]:
        """Return full corporate symbol change history for a symbol."""
        base_sym = symbol.upper().replace(".NS", "").replace(".BO", "")
        matching = []
        for rec in self.records:
            if rec["old_symbol"].upper() == base_sym or rec["new_symbol"].upper() == base_sym:
                matching.append(rec)
        return matching


symbol_master = SymbolMaster()
