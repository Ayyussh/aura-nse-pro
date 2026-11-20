"""NSE Derivatives Telemetry & Options Chain Sentiment Engine.

Calculates institutional derivatives positioning:
- Put-Call Ratio (PCR on Open Interest & Volume)
- Option Max Pain Strike (Option writers' minimal payout zone)
- Gamma Resistance (Highest Call OI strike) & Gamma Support (Highest Put OI strike)
- Futures Open Interest Buildup Classification (Long Buildup vs Short Buildup)
"""

from __future__ import annotations
import datetime
import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

from backend.core.config import PROJECT_ROOT
from backend.data.holiday_calendar import get_ist_now

logger = logging.getLogger("aura.derivatives")
CACHE_FILE = PROJECT_ROOT / "data" / "cache" / "derivatives_nifty_latest.json"
CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class IndexDerivativesSnapshot:
    underlying: str
    underlying_price: float
    pcr_oi: float
    pcr_volume: float
    max_pain_strike: float
    gamma_resistance_call_strike: float
    gamma_support_put_strike: float
    total_call_oi: int
    total_put_oi: int
    sentiment: str  # BULLISH, BEARISH, NEUTRAL, EXTREME_OVERSOLD, EXTREME_OVERBOUGHT
    as_of_timestamp: str
    data_source: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EquityDerivativesSnapshot:
    symbol: str
    is_fno: bool
    buildup_type: str  # LONG_BUILDUP, SHORT_BUILDUP, SHORT_COVERING, LONG_UNWINDING, NEUTRAL
    price_change_pct: float
    oi_change_pct: float
    pcr: float
    as_of_date: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class NseDerivativesEngine:
    """Computes Derivatives & Options Chain Telemetry for NSE."""

    def __init__(self, cache_ttl_minutes: int = 45):
        self.cache_ttl_minutes = cache_ttl_minutes
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def fetch_index_derivatives(self, symbol: str = "NIFTY") -> IndexDerivativesSnapshot:
        """Fetch and analyze option chain telemetry for NIFTY / BANKNIFTY."""
        # 1. Check local cache
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                ts = datetime.datetime.fromisoformat(data.get("as_of_timestamp", "2000-01-01T00:00:00"))
                now = datetime.datetime.now()
                if (now - ts).total_seconds() < (self.cache_ttl_minutes * 60):
                    return IndexDerivativesSnapshot(**data)
            except Exception as e:
                logger.debug(f"Could not read derivatives cache: {e}")

        # 2. Query official NSE option chain API
        snap = self._query_nse_option_chain(symbol)
        if snap is None:
            snap = self._generate_fallback_index_snapshot(symbol)

        # 3. Save cache
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(snap.to_dict(), f, indent=2)
        except Exception as e:
            logger.debug(f"Could not save derivatives cache: {e}")

        return snap

    def _query_nse_option_chain(self, symbol: str) -> Optional[IndexDerivativesSnapshot]:
        """Fetch option chain directly from NSE API."""
        url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
        try:
            with httpx.Client(headers=self.headers, timeout=8.0, follow_redirects=True) as client:
                client.get("https://www.nseindia.com")
                resp = client.get(url)
                if resp.status_code == 200:
                    payload = resp.json()
                    records = payload.get("records", {})
                    data_items = records.get("data", [])
                    underlying_price = float(records.get("underlyingValue", 25800.0))

                    if not data_items:
                        return None

                    total_call_oi = 0
                    total_put_oi = 0
                    total_call_vol = 0
                    total_put_vol = 0

                    strike_call_oi: Dict[float, int] = {}
                    strike_put_oi: Dict[float, int] = {}

                    for item in data_items:
                        strike = float(item.get("strikePrice", 0.0))
                        ce = item.get("CE")
                        pe = item.get("PE")

                        if ce:
                            ce_oi = int(ce.get("openInterest", 0))
                            ce_vol = int(ce.get("totalTradedVolume", 0))
                            total_call_oi += ce_oi
                            total_call_vol += ce_vol
                            strike_call_oi[strike] = strike_call_oi.get(strike, 0) + ce_oi

                        if pe:
                            pe_oi = int(pe.get("openInterest", 0))
                            pe_vol = int(pe.get("totalTradedVolume", 0))
                            total_put_oi += pe_oi
                            total_put_vol += pe_vol
                            strike_put_oi[strike] = strike_put_oi.get(strike, 0) + pe_oi

                    pcr_oi = round(total_put_oi / total_call_oi, 2) if total_call_oi > 0 else 1.0
                    pcr_vol = round(total_put_vol / total_call_vol, 2) if total_call_vol > 0 else 1.0

                    # Max Pain Calculation: strike with lowest total loss for option sellers
                    all_strikes = sorted(list(set(strike_call_oi.keys()).union(set(strike_put_oi.keys()))))
                    # Narrow to reasonable band around ATM (within 6%)
                    near_strikes = [s for s in all_strikes if abs(s - underlying_price) <= underlying_price * 0.06] or all_strikes

                    min_pain_loss = float("inf")
                    max_pain_strike = underlying_price
                    for test_strike in near_strikes:
                        total_payout = 0.0
                        for s, c_oi in strike_call_oi.items():
                            if test_strike > s:
                                total_payout += (test_strike - s) * c_oi
                        for s, p_oi in strike_put_oi.items():
                            if test_strike < s:
                                total_payout += (s - test_strike) * p_oi
                        if total_payout < min_pain_loss:
                            min_pain_loss = total_payout
                            max_pain_strike = test_strike

                    # Gamma walls: Strikes with highest Call and Put Open Interest
                    gamma_call = max(strike_call_oi.items(), key=lambda x: x[1])[0] if strike_call_oi else underlying_price + 200
                    gamma_put = max(strike_put_oi.items(), key=lambda x: x[1])[0] if strike_put_oi else underlying_price - 200

                    sentiment = self._classify_sentiment(pcr_oi)

                    return IndexDerivativesSnapshot(
                        underlying=symbol,
                        underlying_price=round(underlying_price, 2),
                        pcr_oi=pcr_oi,
                        pcr_volume=pcr_vol,
                        max_pain_strike=round(max_pain_strike, 0),
                        gamma_resistance_call_strike=round(gamma_call, 0),
                        gamma_support_put_strike=round(gamma_put, 0),
                        total_call_oi=total_call_oi,
                        total_put_oi=total_put_oi,
                        sentiment=sentiment,
                        as_of_timestamp=datetime.datetime.now().isoformat(),
                        data_source="NSE_LIVE_OPTION_CHAIN",
                    )
        except Exception as e:
            logger.debug(f"Option chain query note for {symbol}: {e}")
        return None

    def _classify_sentiment(self, pcr_oi: float) -> str:
        """Classify derivatives sentiment based on Put-Call Ratio."""
        if pcr_oi >= 1.35:
            return "EXTREME_OVERBOUGHT"
        elif pcr_oi >= 1.10:
            return "BULLISH"
        elif pcr_oi <= 0.65:
            return "EXTREME_OVERSOLD"
        elif pcr_oi <= 0.85:
            return "BEARISH"
        return "NEUTRAL"

    def classify_equity_buildup(
        self, symbol: str, price_change_pct: float, oi_change_pct: float
    ) -> EquityDerivativesSnapshot:
        """Classify Futures Open Interest buildup for single equities."""
        if price_change_pct > 0.3 and oi_change_pct > 2.0:
            buildup = "LONG_BUILDUP"
        elif price_change_pct < -0.3 and oi_change_pct > 2.0:
            buildup = "SHORT_BUILDUP"
        elif price_change_pct > 0.3 and oi_change_pct < -2.0:
            buildup = "SHORT_COVERING"
        elif price_change_pct < -0.3 and oi_change_pct < -2.0:
            buildup = "LONG_UNWINDING"
        else:
            buildup = "NEUTRAL"

        return EquityDerivativesSnapshot(
            symbol=symbol,
            is_fno=True,
            buildup_type=buildup,
            price_change_pct=round(price_change_pct, 2),
            oi_change_pct=round(oi_change_pct, 2),
            pcr=1.0,
            as_of_date=get_ist_now().strftime("%Y-%m-%d"),
        )

    def _generate_fallback_index_snapshot(self, symbol: str) -> IndexDerivativesSnapshot:
        """Conservative baseline when NSE option chain is unreachable."""
        return IndexDerivativesSnapshot(
            underlying=symbol,
            underlying_price=25800.0,
            pcr_oi=1.02,
            pcr_volume=0.98,
            max_pain_strike=25800.0,
            gamma_resistance_call_strike=26000.0,
            gamma_support_put_strike=25500.0,
            total_call_oi=15000000,
            total_put_oi=15300000,
            sentiment="NEUTRAL",
            as_of_timestamp=datetime.datetime.now().isoformat(),
            data_source="BENCHMARK_DERIVATIVES_BASELINE",
        )


derivatives_engine = NseDerivativesEngine()
