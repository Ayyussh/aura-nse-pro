"""NSE Official Archive & Bhavcopy Ingestion Engine (Tier 1 Source of Truth).

Downloads and parses official daily closing files from NSE archives:
- Supports both post-July 2024 UDiFF format (`BhavCopy_NSE_CM_0_0_0_<YYYYMMDD>_F_0000.csv.zip`)
  and legacy CM bhavcopy archives.
- Extracts official Closes, Highs, Lows, Volumes, and EQ series classifications.
- Provides immutable ground truth for EOD reconciliation and performance grading.
"""

from __future__ import annotations
import datetime
import io
import logging
from pathlib import Path
from typing import Dict, Optional, Any
import zipfile

import httpx
import pandas as pd

from backend.core.config import PROJECT_ROOT

logger = logging.getLogger("aura.bhavcopy")
BHAVCOPY_DIR = PROJECT_ROOT / "data" / "bhavcopy"
BHAVCOPY_DIR.mkdir(parents=True, exist_ok=True)


class NSEBhavcopyEngine:
    """Manages official NSE End-of-Day archive file retrieval and normalization."""

    def __init__(self):
        self.bhavcopy_dir = BHAVCOPY_DIR
        self._memory_cache: Dict[str, pd.DataFrame] = {}

    def _get_udiff_url(self, dt: datetime.date) -> str:
        """Post-July 2024 UDiFF CM Bhavcopy format."""
        ymd = dt.strftime("%Y%m%d")
        return f"https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{ymd}_F_0000.csv.zip"

    def _get_legacy_url(self, dt: datetime.date) -> str:
        """Pre-July 2024 legacy bhavcopy format."""
        year = dt.strftime("%Y")
        month = dt.strftime("%b").upper()
        day = dt.strftime("%d")
        return f"https://nsearchives.nseindia.com/content/historical/EQUITIES/{year}/{month}/cm{day}{month}{year}bhav.csv.zip"

    def download_and_parse_bhavcopy(self, dt: datetime.date) -> pd.DataFrame:
        """Fetch and parse official NSE bhavcopy for a given trading day."""
        date_str = dt.isoformat()
        if date_str in self._memory_cache:
            return self._memory_cache[date_str]

        # Check local parquet / csv cache first
        cached_file = self.bhavcopy_dir / f"bhavcopy_{date_str}.parquet"
        if cached_file.exists():
            try:
                df = pd.read_parquet(cached_file)
                self._memory_cache[date_str] = df
                return df
            except Exception as e:
                logger.warning(f"Failed to read local bhavcopy cache for {date_str}: {e}")

        # Attempt download from NSE Archives (UDiFF first, fallback to legacy)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Referer": "https://www.nseindia.com",
        }

        urls = [self._get_udiff_url(dt), self._get_legacy_url(dt)]
        df_parsed: Optional[pd.DataFrame] = None

        for url in urls:
            try:
                with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                    resp = client.get(url, headers=headers)
                    if resp.status_code == 200 and resp.content:
                        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
                            csv_names = [n for n in z.namelist() if n.endswith(".csv")]
                            if csv_names:
                                with z.open(csv_names[0]) as csv_file:
                                    raw_df = pd.read_csv(csv_file)
                                    df_parsed = self._normalize_bhavcopy_schema(raw_df)
                                    break
            except Exception as e:
                logger.debug(f"Attempt failed for URL {url}: {e}")

        if df_parsed is not None and not df_parsed.empty:
            try:
                df_parsed.to_parquet(cached_file)
            except Exception as e:
                logger.warning(f"Could not cache bhavcopy parquet: {e}")
            self._memory_cache[date_str] = df_parsed
            return df_parsed

        return pd.DataFrame()

    def _normalize_bhavcopy_schema(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        """Standardize column names across UDiFF and legacy formats into clean schema:

        Columns: [symbol, series, open, high, low, close, volume]
        """
        cols = {c.strip(): c.strip() for c in raw_df.columns}

        # Check if UDiFF format
        if "TckrSymb" in cols:
            df = raw_df.rename(
                columns={
                    "TckrSymb": "symbol",
                    "SctySrs": "series",
                    "OpnPric": "open",
                    "HghPric": "high",
                    "LwPric": "low",
                    "ClsPric": "close",
                    "TtlTradgVol": "volume",
                }
            )
        # Check if legacy format
        elif "SYMBOL" in cols:
            df = raw_df.rename(
                columns={
                    "SYMBOL": "symbol",
                    "SERIES": "series",
                    "OPEN": "open",
                    "HIGH": "high",
                    "LOW": "low",
                    "CLOSE": "close",
                    "TOTTRDQTY": "volume",
                }
            )
        else:
            return pd.DataFrame()

        # Keep EQ series only
        if "series" in df.columns:
            df = df[df["series"].astype(str).str.strip() == "EQ"]

        df["symbol"] = df["symbol"].astype(str).str.strip() + ".NS"
        return df[["symbol", "open", "high", "low", "close", "volume"]]

    def get_official_eod_price(self, symbol: str, dt: datetime.date) -> Optional[Dict[str, float]]:
        """Lookup official EOD OHLCV values for a symbol on a specific date."""
        df = self.download_and_parse_bhavcopy(dt)
        if df.empty:
            return None

        clean_sym = symbol if symbol.endswith(".NS") else f"{symbol}.NS"
        match = df[df["symbol"] == clean_sym]
        if match.empty:
            return None

        row = match.iloc[0]
        return {
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row["volume"]),
            "source": "NSE_OFFICIAL_BHAVCOPY",
        }


bhavcopy_engine = NSEBhavcopyEngine()
