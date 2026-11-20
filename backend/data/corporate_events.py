"""Corporate Governance & Regulatory Event Risk Shield.

Monitors and scans official exchange corporate announcements (BSE & NSE):
- Statutory Auditor Resignations & Qualified Audit Opinions
- US FDA Form 483, Import Alerts, and Warning Letters
- Law Enforcement Raids (Enforcement Directorate, CBI, Income Tax, SEBI)
- Loan / NCD Payment Defaults & NCLT Insolvency Filings
- Sudden CFO / Management Departures
- Triggers instant hard veto in Swing and Compounder pipelines
"""

from __future__ import annotations
import datetime
import json
import logging
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

from backend.core.config import PROJECT_ROOT
from backend.data.holiday_calendar import get_ist_now

logger = logging.getLogger("aura.corporate_events")
CACHE_FILE = PROJECT_ROOT / "data" / "cache" / "corporate_events_latest.json"
CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class EventItem:
    headline: str
    category: str
    severity: str  # HIGH, MEDIUM, LOW
    announcement_date: str
    source: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CorporateEventRisk:
    symbol: str
    risk_level: str  # HIGH, MEDIUM, CLEAN
    veto_trade: bool
    veto_reason: str
    flagged_events: List[EventItem]
    as_of_date: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "risk_level": self.risk_level,
            "veto_trade": self.veto_trade,
            "veto_reason": self.veto_reason,
            "flagged_events": [e.to_dict() for e in self.flagged_events],
            "as_of_date": self.as_of_date,
        }


class CorporateEventShield:
    """Monitors exchange regulatory and governance disclosures for institutional danger tags."""

    HIGH_RISK_PATTERNS = {
        "AUDITOR_RESIGNATION": [
            r"resignation of (?:statutory )?auditor",
            r"auditor (?:has )?resigned",
            r"casual vacancy caused by resignation of auditor",
        ],
        "QUALIFIED_AUDIT": [
            r"qualified (?:audit )?opinion",
            r"adverse (?:audit )?opinion",
            r"disclaimer of opinion",
            r"material misstatement",
            r"emphasis of matter.*going concern",
        ],
        "INVESTIGATION_RAID": [
            r"search and seizure",
            r"enforcement directorate",
            r"cbi raid",
            r"income tax (?:department )?search",
            r"sebi show cause notice",
            r"allegation.*fraud",
        ],
        "FDA_WARNING": [
            r"form 483.*(?:observations|warning)",
            r"warning letter.*(?:us fda|fda)",
            r"import alert.*fda",
            r"official action indicated.*oai",
        ],
        "DEBT_DEFAULT": [
            r"default in payment of (?:interest|principal)",
            r"nclt.*insolvency",
            r"corporate insolvency resolution process",
            r"cirp.*initiated",
        ],
    }

    MEDIUM_RISK_PATTERNS = {
        "CFO_RESIGNATION": [
            r"resignation of (?:chief financial officer|cfo)",
            r"cfo (?:has )?resigned",
        ],
        "CREDIT_DOWNGRADE": [
            r"downgraded by (?:crisil|icra|care|india ratings)",
            r"credit rating downgraded",
            r"rating watch with negative implications",
        ],
    }

    def __init__(self, cache_ttl_hours: int = 12):
        self.cache_ttl_hours = cache_ttl_hours
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "*/*",
        }

    def scan_text_for_risks(self, text: str) -> Tuple[str, str, str]:
        """Scan announcement text against institutional risk regexes.
        Returns: (risk_level, category, reason)
        """
        clean_text = text.lower()

        # 1. High Risk Scans (Hard Veto)
        for category, patterns in self.HIGH_RISK_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, clean_text):
                    reason = f"High-Severity Corporate Governance Alert: {category.replace('_', ' ')} detected in exchange filing."
                    return "HIGH", category, reason

        # 2. Medium Risk Scans (Caution)
        for category, patterns in self.MEDIUM_RISK_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, clean_text):
                    reason = f"Medium-Severity Management/Credit Alert: {category.replace('_', ' ')} detected."
                    return "MEDIUM", category, reason

        return "CLEAN", "NONE", ""

    def check_symbol_event_risk(self, symbol: str) -> CorporateEventRisk:
        """Check whether an equity has recent severe corporate governance alerts."""
        clean_sym = symbol.replace(".NS", "").replace("^", "").strip().upper()
        cache = self._load_cache()

        symbol_events = cache.get(clean_sym, [])
        flagged: List[EventItem] = []
        highest_risk = "CLEAN"
        veto_reason = ""

        for ev in symbol_events:
            text = f"{ev.get('headline', '')} {ev.get('description', '')}"
            risk_lvl, cat, rsn = self.scan_text_for_risks(text)
            if risk_lvl == "HIGH":
                highest_risk = "HIGH"
                veto_reason = rsn
                flagged.append(EventItem(
                    headline=ev.get("headline", "Regulatory Filing"),
                    category=cat,
                    severity="HIGH",
                    announcement_date=ev.get("date", get_ist_now().strftime("%Y-%m-%d")),
                    source=ev.get("source", "EXCHANGE_FEED"),
                ))
            elif risk_lvl == "MEDIUM" and highest_risk != "HIGH":
                highest_risk = "MEDIUM"
                veto_reason = rsn
                flagged.append(EventItem(
                    headline=ev.get("headline", "Management Filing"),
                    category=cat,
                    severity="MEDIUM",
                    announcement_date=ev.get("date", get_ist_now().strftime("%Y-%m-%d")),
                    source=ev.get("source", "EXCHANGE_FEED"),
                ))

        return CorporateEventRisk(
            symbol=clean_sym,
            risk_level=highest_risk,
            veto_trade=bool(highest_risk == "HIGH"),
            veto_reason=veto_reason,
            flagged_events=flagged,
            as_of_date=get_ist_now().strftime("%Y-%m-%d"),
        )

    def _load_cache(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load recent announcement database from disk."""
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.debug(f"Could not load event cache: {e}")
        return {}

    def record_announcement(self, symbol: str, headline: str, description: str = "", source: str = "EXCHANGE_FEED"):
        """Record an announcement into local registry."""
        clean_sym = symbol.replace(".NS", "").replace("^", "").strip().upper()
        cache = self._load_cache()
        if clean_sym not in cache:
            cache[clean_sym] = []

        cache[clean_sym].append({
            "headline": headline,
            "description": description,
            "date": get_ist_now().strftime("%Y-%m-%d"),
            "source": source,
        })

        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(cache, f, indent=2)
        except Exception as e:
            logger.debug(f"Could not save announcement: {e}")


corporate_event_shield = CorporateEventShield()
