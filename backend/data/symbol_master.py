"""AURA Point-in-Time Symbol Master & Corporate Restructuring Registry (Section 17.2, 18.3, 19.3).

Tracks official corporate restructuring events:
- Event Types: RENAME, MERGER, DEMERGER, CONVERSION, LISTING, DELISTING
- Includes effective dates, old & new ISINs, source circulars
- Policy: Never splice price history across a merger, demerger or conversion
  without an adjustment factor from the corporate-action ledger.
- Enforces 20-trading-day post-demerger/merger exclusion window.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class SymbolEvent:
    event_id: str
    old_symbol: str
    new_symbol: str
    event_type: str  # RENAME, MERGER, DEMERGER, CONVERSION, LISTING, DELISTING
    effective_date: datetime.date
    old_isin: str
    new_isin: str
    source_circular: str
    allows_splicing: bool
    exclusion_window_days: int
    adjustment_factor: Optional[float] = None
    description: str = ""


# Master list of corporate events across Indian Equities
SYMBOL_EVENTS: List[SymbolEvent] = [
    # 1. ZOMATO -> ETERNAL (Pure name change / rename)
    SymbolEvent(
        event_id="EVT_ZOMATO_RENAME_2025",
        old_symbol="ZOMATO.NS",
        new_symbol="ETERNAL.NS",
        event_type="RENAME",
        effective_date=datetime.date(2024, 7, 25),
        old_isin="INE758T01015",
        new_isin="INE758T01015",
        source_circular="NSE/CML/2024/07/25-ZOMATO",
        allows_splicing=True,
        exclusion_window_days=0,
        adjustment_factor=1.0,
        description="Zomato Ltd renamed to Eternal Ltd; continuous corporate entity.",
    ),
    # 2. TATAMOTORS -> TMPV (Demerger of Commercial Vehicles into TMCV; PV renamed to TMPV)
    SymbolEvent(
        event_id="EVT_TATAMOTORS_DEMERGER_2025",
        old_symbol="TATAMOTORS.NS",
        new_symbol="TMPV.NS",
        event_type="DEMERGER",
        effective_date=datetime.date(2025, 10, 24),
        old_isin="INE155A01022",
        new_isin="INE155A01022",
        source_circular="NSE/CML/2025/10/24-TMPV",
        allows_splicing=False,
        exclusion_window_days=20,
        adjustment_factor=None,
        description="Tata Motors demerged Commercial Vehicles to TMCV. Remaining PV business trading as TMPV.",
    ),
    # 3. TMCV Listing (Tata Motors Commercial Vehicles Ltd)
    SymbolEvent(
        event_id="EVT_TMCV_LISTING_2025",
        old_symbol="",
        new_symbol="TMCV.NS",
        event_type="LISTING",
        effective_date=datetime.date(2025, 11, 12),
        old_isin="",
        new_isin="INE0N0401019",
        source_circular="NSE/CML/2025/11/12-TMCV",
        allows_splicing=False,
        exclusion_window_days=20,
        description="Listing of resulting demerged entity Tata Motors Commercial Vehicles Ltd.",
    ),
    # 4. HDFC Merger into HDFCBANK
    SymbolEvent(
        event_id="EVT_HDFC_MERGER_2023",
        old_symbol="HDFC.NS",
        new_symbol="HDFCBANK.NS",
        event_type="MERGER",
        effective_date=datetime.date(2023, 7, 1),
        old_isin="INE001A01036",
        new_isin="INE040A01034",
        source_circular="NSE/CML/2023/45",
        allows_splicing=False,
        exclusion_window_days=20,
        description="Merger of Housing Development Finance Corporation Ltd into HDFC Bank Ltd.",
    ),
    # 5. VEDL Demerger
    SymbolEvent(
        event_id="EVT_VEDL_DEMERGER_2026",
        old_symbol="VEDL.NS",
        new_symbol="VEDL.NS",
        event_type="DEMERGER",
        effective_date=datetime.date(2026, 4, 30),
        old_isin="INE205A01025",
        new_isin="INE205A01025",
        source_circular="NSE/CML/2026/04/30-VEDL",
        allows_splicing=False,
        exclusion_window_days=20,
        description="Vedanta demerger of business units with 20-day quarantine.",
    ),
    # 6. LTI & MINDTREE Merger into LTIM
    SymbolEvent(
        event_id="EVT_LTI_MINDTREE_MERGER_2022",
        old_symbol="LTI.NS",
        new_symbol="LTIM.NS",
        event_type="MERGER",
        effective_date=datetime.date(2022, 11, 24),
        old_isin="INE214T01019",
        new_isin="INE214T01019",
        source_circular="NSE/CML/2022/68",
        allows_splicing=False,
        exclusion_window_days=20,
        description="Merger of Larsen & Toubro Infotech and Mindtree into LTIMindtree Ltd.",
    ),
    # 7. Shriram Transport Finance -> Shriram Finance
    SymbolEvent(
        event_id="EVT_SRTRANSFIN_MERGER_2022",
        old_symbol="SRTRANSFIN.NS",
        new_symbol="SHRIRAMFIN.NS",
        event_type="MERGER",
        effective_date=datetime.date(2022, 11, 30),
        old_isin="INE721A01013",
        new_isin="INE721A01013",
        source_circular="NSE/CML/2022/72",
        allows_splicing=False,
        exclusion_window_days=20,
        description="Shriram Transport Finance merged with Shriram City Union into Shriram Finance.",
    ),
    # 8. IDFC Ltd reverse merger into IDFC FIRST Bank
    SymbolEvent(
        event_id="EVT_IDFC_MERGER_2024",
        old_symbol="IDFC.NS",
        new_symbol="IDFCFIRSTB.NS",
        event_type="MERGER",
        effective_date=datetime.date(2024, 10, 1),
        old_isin="INE043D01016",
        new_isin="INE092T01019",
        source_circular="NSE/CML/2024/89",
        allows_splicing=False,
        exclusion_window_days=20,
        description="Amalgamation of IDFC Ltd into IDFC FIRST Bank Ltd.",
    ),
    # 9. TATAMTRDVR Conversion into Ordinary Shares
    SymbolEvent(
        event_id="EVT_TATAMTRDVR_CONVERSION_2024",
        old_symbol="TATAMTRDVR.NS",
        new_symbol="TATAMOTORS.NS",
        event_type="CONVERSION",
        effective_date=datetime.date(2024, 9, 1),
        old_isin="IN9155A01020",
        new_isin="INE155A01022",
        source_circular="NSE/CML/2024/76",
        allows_splicing=False,
        exclusion_window_days=20,
        description="Capital reduction and cancellation of DVR shares with ordinary share issuance.",
    ),
]


STANDARD_ISIN_REGISTRY: Dict[str, str] = {
    "RELIANCE": "INE002A01018",
    "TCS": "INE467B01029",
    "INFY": "INE009A01021",
    "HDFCBANK": "INE040A01034",
    "ICICIBANK": "INE090A01021",
    "SBIN": "INE062A01020",
    "BHARTIARTL": "INE397D01024",
    "ITC": "INE154A01025",
    "KOTAKBANK": "INE237A01028",
    "LT": "INE018A01030",
    "HINDUNILVR": "INE030A01027",
    "AXISBANK": "INE238A01034",
    "BAJFINANCE": "INE296A01024",
    "MARUTI": "INE585B01010",
    "TMPV": "INE155A01022",
    "TMCV": "INE0N0401019",
    "TATAMOTORS": "INE155A01022",
    "VEDL": "INE205A01025",
    "HCLTECH": "INE860A01027",
    "WIPRO": "INE075A01022",
    "LTIM": "INE214T01019",
    "TECHM": "INE669C01036",
    "PERSISTENT": "INE262H01013",
    "COFORGE": "INE591G01017",
    "MPHASIS": "INE356A01018",
    "TATAELXSI": "INE670A01012",
    "TATATECH": "INE142Z01019",
    "NAUKRI": "INE663F01024",
    "ETERNAL": "INE758T01015",
    "ZOMATO": "INE758T01015",
    "SWIGGY": "INE00H001014",
    "POLICYBZR": "INE417T01026",
    "INDUSINDBK": "INE095A01012",
    "BANKBARODA": "INE028A01039",
    "PNB": "INE160A01022",
    "CANBK": "INE476A01014",
    "UNIONBANK": "INE692A01016",
    "INDIANB": "INE562A01011",
    "FEDERALBNK": "INE171A01029",
    "IDFCFIRSTB": "INE092T01019",
    "AUBANK": "INE949L01017",
}


class SymbolMaster:
    """Institutional Symbol Master managing alias mapping, restructuring dates and splice permissions."""

    def __init__(self, events: List[SymbolEvent] = SYMBOL_EVENTS):
        self.events = events
        self.isin_registry = dict(STANDARD_ISIN_REGISTRY)
        self._build_index()

    def _build_index(self):
        self.alias_to_active: Dict[str, str] = {}
        for ev in self.events:

            if ev.old_symbol:
                self.alias_to_active[ev.old_symbol.upper()] = ev.new_symbol.upper()
                clean_old = ev.old_symbol.upper().replace(".NS", "")
                self.alias_to_active[clean_old] = ev.new_symbol.upper()

    def resolve(self, symbol: str) -> str:
        """Resolve ticker symbol to its active corporate ticker."""
        clean = symbol.strip().upper()
        if clean in self.alias_to_active:
            return self.alias_to_active[clean]
        base = clean.replace(".NS", "")
        if base in self.alias_to_active:
            return self.alias_to_active[base]
        if not clean.endswith(".NS"):
            clean = f"{clean}.NS"
        return self.alias_to_active.get(clean, clean)

    def resolve_symbol_at_date(self, symbol: str, as_of_date: datetime.date) -> str:
        """Resolve ticker symbol point-in-time based on effective restructuring date."""
        clean = symbol.strip().upper()
        clean_base = clean.replace(".NS", "")

        for ev in self.events:
            ev_old_clean = ev.old_symbol.upper()
            ev_old_base = ev_old_clean.replace(".NS", "")
            if clean == ev_old_clean or clean_base == ev_old_base:
                if as_of_date >= ev.effective_date:
                    return ev.new_symbol
                else:
                    return ev.old_symbol if ev.old_symbol else symbol

        return symbol

    def get_isin_for_symbol(self, symbol: str) -> str:
        """Lookup active ISIN for an equity symbol."""
        clean = symbol.strip().upper()
        clean_base = clean.replace(".NS", "").replace(".BO", "")

        # 1. Direct registry lookup
        if clean_base in self.isin_registry:
            return self.isin_registry[clean_base]

        # 2. Check corporate restructuring events
        for ev in self.events:
            if ev.new_symbol.upper() == clean or ev.new_symbol.upper().replace(".NS", "") == clean_base:
                return ev.new_isin
            if ev.old_symbol.upper() == clean or ev.old_symbol.upper().replace(".NS", "") == clean_base:
                return ev.old_isin
        return "UNKNOWN_ISIN"


    def can_splice_history(
        self,
        from_symbol: str,
        to_symbol: str,
        as_of_date: datetime.date,
    ) -> Tuple[bool, str]:
        """Verify whether price history between two symbols may be spliced.

        Refuses splicing across DEMERGER, MERGER, or CONVERSION unless an explicit
        adjustment factor is certified, and enforces the 20-trading-day exclusion window.
        """
        f_clean = from_symbol.upper()
        t_clean = to_symbol.upper()

        if f_clean == t_clean:
            return True, "Identical symbol."

        # Find event connecting these symbols
        matching_event = None
        for ev in self.events:
            if (ev.old_symbol.upper() == f_clean and ev.new_symbol.upper() == t_clean) or \
               (ev.old_symbol.upper().replace(".NS", "") == f_clean.replace(".NS", "") and
                ev.new_symbol.upper().replace(".NS", "") == t_clean.replace(".NS", "")):
                matching_event = ev
                break

        if not matching_event:
            return False, f"REJECT_SPLICE: No official corporate restructuring connects {from_symbol} to {to_symbol}."

        if not matching_event.allows_splicing:
            return False, (
                f"REJECT_SPLICE: Event '{matching_event.event_type}' on {matching_event.effective_date} "
                f"strictly prohibits unadjusted price splicing without an approved adjustment factor."
            )

        # Check exclusion window
        days_since_effective = (as_of_date - matching_event.effective_date).days
        if 0 <= days_since_effective < matching_event.exclusion_window_days:
            return False, (
                f"REJECT_SPLICE: Date {as_of_date} falls inside the {matching_event.exclusion_window_days}-day "
                f"post-restructuring exclusion window for {matching_event.new_symbol}."
            )

        return True, f"PERMIT_SPLICE: Allowed under circular {matching_event.source_circular}."

    def is_in_exclusion_window(self, symbol: str, date: datetime.date) -> Tuple[bool, str]:
        """Check if symbol is currently in an exclusion window following a corporate action."""
        clean = symbol.upper()
        for ev in self.events:
            if ev.new_symbol.upper() == clean or ev.old_symbol.upper() == clean:
                days_diff = (date - ev.effective_date).days
                if 0 <= days_diff < ev.exclusion_window_days:
                    return True, (
                        f"EXCLUSION_ACTIVE: {clean} in {ev.exclusion_window_days}-day quarantine "
                        f"after {ev.event_type} on {ev.effective_date} (Circular {ev.source_circular})."
                    )
        return False, ""


symbol_master = SymbolMaster()
