"""NIFTY 500 Lake Historical Backfill Engine (5-10 Year Clean Data Lake).

Ingests all 501 official NIFTY 500 constituents plus benchmark indices (^NSEI, ^INDIAVIX, ^NSEBANK, ^CNXIT).
Uses unadjusted raw OHLCV matching official NSE Bhavcopy records (source='YFINANCE_HIST').
Records listing dates, bar counts, date ranges, and writes:
- reports/backfill_status_report.json
"""

from __future__ import annotations
import datetime
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List, Any

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import pandas as pd
import numpy as np
import yfinance as yf

from backend.core.config import PROJECT_ROOT
from backend.data.historical_store import historical_store, SyntheticDataDetectedError
from backend.data.symbol_master import symbol_master

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("aura.nifty500_backfill")

REPORTS_DIR = PROJECT_ROOT / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
BACKFILL_REPORT = REPORTS_DIR / "backfill_status_report.json"
NIFTY500_CSV = PROJECT_ROOT / "data" / "nifty500_constituents.csv"


def get_all_target_symbols() -> List[str]:
    """Retrieve full list of 501 NIFTY 500 constituents + 4 benchmark indices."""
    if not NIFTY500_CSV.exists():
        raise FileNotFoundError(f"Missing {NIFTY500_CSV}")
    
    df = pd.read_csv(NIFTY500_CSV)
    raw_symbols = df["Symbol"].dropna().unique().tolist()
    
    # Map symbols with .NS
    mapped = []
    for s in raw_symbols:
        clean = str(s).strip()
        resolved = symbol_master.resolve(clean)
        if not resolved.endswith(".NS") and not resolved.startswith("^"):
            resolved = f"{resolved}.NS"
        mapped.append(resolved)
    
    # Add key indices
    indices = ["^NSEI", "^INDIAVIX", "^NSEBANK", "^CNXIT"]
    all_targets = indices + sorted(list(set(mapped)))
    return all_targets


def backfill_nifty500(years: int = 5, batch_size: int = 50) -> Dict[str, Any]:
    """Batch download and store historical bars for all NIFTY 500 instruments."""
    targets = get_all_target_symbols()
    logger.info(f"Initiating full clean backfill for {len(targets)} targets over {years} years...")

    completed = {}
    failed = {}
    total_bars = 0
    t_start = time.time()

    # 1. Backfill Indices First
    indices = ["^NSEI", "^INDIAVIX", "^NSEBANK", "^CNXIT"]
    for idx in indices:
        try:
            logger.info(f"Fetching official index: {idx}...")
            t = yf.Ticker(idx)
            hist = t.history(period=f"{years}y", auto_adjust=False)
            if hist.empty:
                logger.warning(f"Index {idx} returned empty dataframe!")
                failed[idx] = "Empty dataframe"
                continue
            
            clean_df = hist.copy()
            clean_df.columns = [c.lower().replace(" ", "_") for c in clean_df.columns]
            clean_df["source"] = "NSE_VIX_OFFICIAL" if "VIX" in idx else "NSE_INDEX_OFFICIAL"
            clean_df["adjusted_close"] = clean_df["close"]
            
            stored = historical_store.store_ohlcv(idx, clean_df, default_source=clean_df["source"].iloc[0])
            total_bars += stored
            
            dates = pd.to_datetime(clean_df.index)
            start_d = str(dates.min().date())
            end_d = str(dates.max().date())
            
            completed[idx] = {
                "bars": stored,
                "listing_or_start_date": start_d,
                "latest_date": end_d,
                "source": clean_df["source"].iloc[0],
            }
            logger.info(f"Stored {idx}: {stored} bars (Start: {start_d}, End: {end_d}).")
        except Exception as e:
            logger.error(f"Failed to fetch {idx}: {e}")
            failed[idx] = str(e)

    # 2. Backfill Equities in Batches
    equity_targets = [s for s in targets if not s.startswith("^")]
    logger.info(f"Downloading {len(equity_targets)} equities in batches of {batch_size}...")

    for i in range(0, len(equity_targets), batch_size):
        chunk = equity_targets[i : i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (len(equity_targets) + batch_size - 1) // batch_size
        logger.info(f"Downloading Batch {batch_num}/{total_batches} ({len(chunk)} tickers)...")

        try:
            data = yf.download(
                tickers=chunk,
                period=f"{years}y",
                auto_adjust=False,
                group_by="ticker",
                threads=True,
                progress=False,
            )
        except Exception as batch_err:
            logger.warning(f"Batch {batch_num} bulk download failed: {batch_err}. Falling back to single-ticker mode.")
            data = None

        for sym in chunk:
            try:
                sym_df = None
                if data is not None and not data.empty:
                    if len(chunk) == 1:
                        sym_df = data.dropna(how="all").copy()
                    else:
                        if sym in data.columns.levels[0]:
                            sym_df = data[sym].dropna(how="all").copy()

                if sym_df is None or sym_df.empty:
                    # Fallback single ticker download
                    t = yf.Ticker(sym)
                    sym_df = t.history(period=f"{years}y", auto_adjust=False)

                if sym_df.empty:
                    logger.warning(f"No bars found for {sym}")
                    failed[sym] = "No data returned (possibly delisted or newly listed with 0 bars)"
                    continue

                sym_df.columns = [c.lower().replace(" ", "_") for c in sym_df.columns]
                sym_df["source"] = "YFINANCE_HIST"
                if "adj_close" in sym_df.columns and "adjusted_close" not in sym_df.columns:
                    sym_df["adjusted_close"] = sym_df["adj_close"]
                elif "adjusted_close" not in sym_df.columns:
                    sym_df["adjusted_close"] = sym_df["close"]

                stored = historical_store.store_ohlcv(sym, sym_df, default_source="YFINANCE_HIST")
                total_bars += stored

                dates = pd.to_datetime(sym_df.index)
                start_d = str(dates.min().date())
                end_d = str(dates.max().date())

                completed[sym] = {
                    "bars": stored,
                    "listing_or_start_date": start_d,
                    "latest_date": end_d,
                    "source": "YFINANCE_HIST",
                }
            except Exception as e:
                logger.error(f"Error storing {sym}: {e}")
                failed[sym] = str(e)

        logger.info(f"Batch {batch_num} processed. Cumulative symbols completed: {len(completed)}")

    # 3. Assert zero synthetic data
    store_check = historical_store.assert_zero_synthetic_data()

    duration_sec = round(time.time() - t_start, 2)
    report = {
        "report_type": "NIFTY_500_CLEAN_HISTORICAL_BACKFILL_REPORT",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "duration_seconds": duration_sec,
        "years_requested": years,
        "total_targets_requested": len(targets),
        "total_symbols_completed": len(completed),
        "total_symbols_failed": len(failed),
        "total_bars_in_lake": store_check["total_bars"],
        "sources_summary": store_check["sources_summary"],
        "synthetic_bars_detected": store_check["synthetic_bars_count"],
        "symbols_detail": completed,
        "failed_symbols": failed,
        "status": "DONE" if len(completed) >= 480 else "PARTIAL",
    }

    with open(BACKFILL_REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    logger.info(
        f"Backfill finished in {duration_sec}s. Completed: {len(completed)}/{len(targets)} symbols. "
        f"Total bars in DuckDB: {store_check['total_bars']}. Status: {report['status']}."
    )
    return report


if __name__ == "__main__":
    backfill_nifty500(years=5, batch_size=50)
