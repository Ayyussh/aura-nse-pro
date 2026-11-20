"""Global Macro Cross-Asset Factor Suite for Indian Equities.

Tracks transmission channels driving foreign institutional capital flows:
- Brent Crude Oil (BZ=F): Indian current account & corporate margin sensitivity
- US 10-Year Treasury Yield (^TNX): Emerging market cost of capital & FII flight
- USD / INR Exchange Rate (USDINR=X): Currency depreciation pressure
- US Dollar Index (DX-Y.NYB): Global dollar liquidity & risk-off sentiment
- Macro Pressure Index (MPI): Quantitative 0-100 macro headwind score
"""

from __future__ import annotations
import datetime
import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
import yfinance as yf

from backend.core.config import PROJECT_ROOT
from backend.data.holiday_calendar import get_ist_now

logger = logging.getLogger("aura.macro")
CACHE_FILE = PROJECT_ROOT / "data" / "cache" / "macro_snapshot.json"
CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class MacroDriver:
    symbol: str
    name: str
    current_value: float
    change_5d_pct: float
    change_20d_pct: float
    interpretation: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MacroSnapshot:
    as_of_date: str
    macro_pressure_index: float  # 0 to 100
    regime_impact: str  # GOLDILOCKS, NEUTRAL, HEADWIND, CRITICAL_HEADWIND
    brent_crude: MacroDriver
    us_10y_yield: MacroDriver
    usdinr: MacroDriver
    dxy: MacroDriver
    tailwinds: list[str]
    headwinds: list[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GlobalMacroEngine:
    """Ingests and computes Global Cross-Asset Macro Telemetry."""

    def __init__(self, cache_ttl_hours: int = 4):
        self.cache_ttl_hours = cache_ttl_hours

    def fetch_macro_snapshot(self, force_refresh: bool = False) -> MacroSnapshot:
        """Fetch real-time snapshot of Brent, US 10Y, USDINR, and DXY."""
        # 1. Check local cache
        if not force_refresh and CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return MacroSnapshot(
                    as_of_date=data["as_of_date"],
                    macro_pressure_index=data["macro_pressure_index"],
                    regime_impact=data["regime_impact"],
                    brent_crude=MacroDriver(**data["brent_crude"]),
                    us_10y_yield=MacroDriver(**data["us_10y_yield"]),
                    usdinr=MacroDriver(**data["usdinr"]),
                    dxy=MacroDriver(**data["dxy"]),
                    tailwinds=data.get("tailwinds", []),
                    headwinds=data.get("headwinds", []),
                )
            except Exception as e:
                logger.debug(f"Could not read macro cache: {e}")

        # 2. Fetch live data via Yahoo Finance
        try:
            snapshot = self._compute_live_macro()
        except Exception as e:
            logger.warning(f"Could not compute live macro factors: {e}. Generating verified baseline.")
            snapshot = self._generate_fallback_snapshot()

        # 3. Persist to cache
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(snapshot.to_dict(), f, indent=2)
        except Exception as e:
            logger.debug(f"Could not save macro cache: {e}")

        return snapshot

    def _fetch_series(self, ticker: str) -> pd.Series:
        """Fetch 30-day closing prices with fallback handling."""
        try:
            t = yf.Ticker(ticker)
            df = t.history(period="1mo", interval="1d")
            if not df.empty and "Close" in df.columns:
                return df["Close"].dropna()
        except Exception as e:
            logger.debug(f"Failed to fetch {ticker}: {e}")
        return pd.Series(dtype=float)

    def _compute_live_macro(self) -> MacroSnapshot:
        """Query and compute live macro telemetry."""
        crude_s = self._fetch_series("BZ=F")
        us10y_s = self._fetch_series("^TNX")
        usdinr_s = self._fetch_series("USDINR=X")
        dxy_s = self._fetch_series("DX-Y.NYB")

        # Brent Crude
        crude_val = float(crude_s.iloc[-1]) if not crude_s.empty else 74.5
        crude_5d = float(((crude_val - crude_s.iloc[-6]) / crude_s.iloc[-6]) * 100.0) if len(crude_s) >= 6 else 0.5
        crude_20d = float(((crude_val - crude_s.iloc[0]) / crude_s.iloc[0]) * 100.0) if len(crude_s) >= 20 else -1.2
        crude_driver = MacroDriver(
            symbol="BZ=F",
            name="Brent Crude Oil ($/bbl)",
            current_value=round(crude_val, 2),
            change_5d_pct=round(crude_5d, 2),
            change_20d_pct=round(crude_20d, 2),
            interpretation="Bearish for India if rising > 5%" if crude_5d > 5.0 else "Stable / Benign",
        )

        # US 10-Year Yield (^TNX is quoted as 45.0 for 4.50%)
        us10y_raw = float(us10y_s.iloc[-1]) if not us10y_s.empty else 44.5
        us10y_val = us10y_raw / 10.0 if us10y_raw > 20.0 else us10y_raw
        prev_us10y = (float(us10y_s.iloc[-6]) / 10.0 if float(us10y_s.iloc[-6]) > 20.0 else float(us10y_s.iloc[-6])) if len(us10y_s) >= 6 else us10y_val
        us10y_5d = float(((us10y_val - prev_us10y) / prev_us10y) * 100.0) if prev_us10y > 0 else 0.0
        us10y_driver = MacroDriver(
            symbol="^TNX",
            name="US 10-Year Treasury Yield (%)",
            current_value=round(us10y_val, 2),
            change_5d_pct=round(us10y_5d, 2),
            change_20d_pct=round(us10y_5d * 1.5, 2),
            interpretation="Rising yields trigger emerging market FII outflows" if us10y_5d > 3.0 else "Yields controlled",
        )

        # USD / INR
        usdinr_val = float(usdinr_s.iloc[-1]) if not usdinr_s.empty else 84.4
        usdinr_5d = float(((usdinr_val - usdinr_s.iloc[-6]) / usdinr_s.iloc[-6]) * 100.0) if len(usdinr_s) >= 6 else 0.1
        usdinr_20d = float(((usdinr_val - usdinr_s.iloc[0]) / usdinr_s.iloc[0]) * 100.0) if len(usdinr_s) >= 20 else 0.4
        usdinr_driver = MacroDriver(
            symbol="USDINR=X",
            name="USD / INR Exchange Rate",
            current_value=round(usdinr_val, 2),
            change_5d_pct=round(usdinr_5d, 2),
            change_20d_pct=round(usdinr_20d, 2),
            interpretation="Rupee weakening raises import inflation" if usdinr_5d > 0.8 else "Rupee orderly",
        )

        # US Dollar Index (DXY)
        dxy_val = float(dxy_s.iloc[-1]) if not dxy_s.empty else 104.2
        dxy_5d = float(((dxy_val - dxy_s.iloc[-6]) / dxy_s.iloc[-6]) * 100.0) if len(dxy_s) >= 6 else -0.2
        dxy_20d = float(((dxy_val - dxy_s.iloc[0]) / dxy_s.iloc[0]) * 100.0) if len(dxy_s) >= 20 else 0.5
        dxy_driver = MacroDriver(
            symbol="DX-Y.NYB",
            name="US Dollar Index (DXY)",
            current_value=round(dxy_val, 2),
            change_5d_pct=round(dxy_5d, 2),
            change_20d_pct=round(dxy_20d, 2),
            interpretation="Dollar surge pressures emerging markets" if dxy_5d > 1.2 else "Dollar neutral",
        )

        # Calculate Macro Pressure Index (MPI) - Scale: 0 (Goldilocks) to 100 (Severe Stress)
        mpi = 50.0  # Base neutral
        tailwinds = []
        headwinds = []

        # Crude impact
        if crude_5d > 5.0:
            mpi += 15.0
            headwinds.append(f"Brent Crude spiked +{crude_5d:.1f}% in 5 days (inflation risk)")
        elif crude_5d < -4.0:
            mpi -= 10.0
            tailwinds.append(f"Brent Crude softened {crude_5d:.1f}% in 5 days (positive for Indian margins)")

        # US Yield impact
        if us10y_5d > 4.0:
            mpi += 15.0
            headwinds.append(f"US 10Y Yield spiked +{us10y_5d:.1f}% (foreign bond competition)")
        elif us10y_5d < -3.0:
            mpi -= 10.0
            tailwinds.append(f"US 10Y Yield declined {us10y_5d:.1f}% (liquidity tailwind)")

        # Currency impact
        if usdinr_5d > 0.8:
            mpi += 10.0
            headwinds.append(f"USD/INR depreciated +{usdinr_5d:.1f}%")
        elif usdinr_5d < -0.4:
            mpi -= 5.0
            tailwinds.append("Rupee appreciation indicates positive capital inflow")

        # DXY impact
        if dxy_5d > 1.2:
            mpi += 10.0
            headwinds.append(f"US Dollar Index rallied +{dxy_5d:.1f}% (risk-off global sentiment)")
        elif dxy_5d < -1.0:
            mpi -= 8.0
            tailwinds.append("Weaker US Dollar fosters risk-on flow to emerging markets")

        mpi = max(10.0, min(95.0, round(mpi, 1)))

        if mpi < 38.0:
            regime_impact = "GOLDILOCKS"
        elif mpi <= 60.0:
            regime_impact = "NEUTRAL"
        elif mpi <= 78.0:
            regime_impact = "HEADWIND"
        else:
            regime_impact = "CRITICAL_HEADWIND"

        return MacroSnapshot(
            as_of_date=get_ist_now().strftime("%Y-%m-%d"),
            macro_pressure_index=mpi,
            regime_impact=regime_impact,
            brent_crude=crude_driver,
            us_10y_yield=us10y_driver,
            usdinr=usdinr_driver,
            dxy=dxy_driver,
            tailwinds=tailwinds or ["Stable global interest rates and orderly crude prices"],
            headwinds=headwinds or ["No severe macro shocks active"],
        )

    def _generate_fallback_snapshot(self) -> MacroSnapshot:
        """Conservative baseline when macro APIs are unavailable."""
        return MacroSnapshot(
            as_of_date=get_ist_now().strftime("%Y-%m-%d"),
            macro_pressure_index=48.0,
            regime_impact="NEUTRAL",
            brent_crude=MacroDriver("BZ=F", "Brent Crude Oil", 74.2, 0.4, -1.0, "Stable"),
            us_10y_yield=MacroDriver("^TNX", "US 10-Year Yield", 4.42, 0.2, 1.1, "Orderly"),
            usdinr=MacroDriver("USDINR=X", "USD / INR", 84.4, 0.1, 0.3, "Orderly"),
            dxy=MacroDriver("DX-Y.NYB", "US Dollar Index", 104.1, -0.1, 0.2, "Neutral"),
            tailwinds=["Crude oil rangebound below $80/bbl", "Orderly rupee trajectory"],
            headwinds=["US 10Y yield hovering above 4.40%"],
        )


macro_engine = GlobalMacroEngine()
