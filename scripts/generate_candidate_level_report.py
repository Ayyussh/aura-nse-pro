"""Section 21.1 Item 2: Comprehensive Candidate-Level Replay & Attribution Engine.

Generates candidate-level attribution:
- Mean Net R for all candidates, taken only, and rejected only.
- Broken down by year (2021, 2022, 2023, 2024, 2025) and setup (pullback_ema, breakout_52w, mean_reversion_rsi).
- 95% week-block bootstrap intervals on every stratum.
- Formal documentation of candidate ranking criteria.

Outputs: reports/candidate_level_annual_attribution.json
"""

from __future__ import annotations
import datetime
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Any
import numpy as np
import pandas as pd

_current_file = Path(__file__).resolve()
_project_root = _current_file.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from backend.core.config import PROJECT_ROOT
from backend.data.historical_store import historical_store
from backend.strategies.swing import SwingStrategyEngine
from backend.core.grader import grade_trade_outcome
from backend.ml.setup_priors import get_setup_empirical_priors
from backend.strategies.indicators import compute_mansfield_relative_strength

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("aura.candidate_report")

REPORTS_DIR = PROJECT_ROOT / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
REPORT_FILE = REPORTS_DIR / "candidate_level_annual_attribution.json"


def compute_week_block_bootstrap_ci(r_multiples: List[float], dates: List[datetime.date], num_reps: int = 1000) -> Dict[str, Any]:
    """Compute 95% week-block bootstrap confidence interval."""
    if not r_multiples:
        return {"count": 0, "mean": 0.0, "ci_lower_95": 0.0, "ci_upper_95": 0.0}

    week_blocks: Dict[str, List[float]] = {}
    for r, d in zip(r_multiples, dates):
        w_key = f"{d.year}-W{d.isocalendar()[1]:02d}"
        week_blocks.setdefault(w_key, []).append(r)

    weeks = list(week_blocks.keys())
    rng = np.random.RandomState(42)
    boot_means = []

    for _ in range(num_reps):
        sampled_weeks = rng.choice(weeks, size=len(weeks), replace=True)
        sampled_rs = []
        for w in sampled_weeks:
            sampled_rs.extend(week_blocks[w])
        if sampled_rs:
            boot_means.append(float(np.mean(sampled_rs)))

    return {
        "count": len(r_multiples),
        "mean": round(float(np.mean(r_multiples)), 4),
        "ci_lower_95": round(float(np.percentile(boot_means, 2.5)), 4),
        "ci_upper_95": round(float(np.percentile(boot_means, 97.5)), 4),
    }


def rank_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Point-in-time ranking function on Day D:

    1. EV_R descending (risk-adjusted mathematical edge).
    2. win_probability descending.
    3. relative_strength vs NIFTY descending.
    """
    return sorted(
        candidates,
        key=lambda c: (
            c.get("ev_r", 0.0),
            c.get("win_probability", 0.0),
            c.get("mansfield_rs", 0.0),
        ),
        reverse=True,
    )


def generate_candidate_report() -> Dict[str, Any]:
    logger.info("Generating Candidate-Level Annual Attribution Report...")
    engine = SwingStrategyEngine()
    symbols = [s for s in historical_store.list_available_symbols() if not s.startswith("^")]
    nifty_df = historical_store.load_ohlcv("^NSEI.NS")

    start_d = datetime.date(2021, 1, 1)
    end_d = datetime.date(2025, 8, 31)  # Holdout partition strictly sealed

    dfs: Dict[str, pd.DataFrame] = {}
    for sym in symbols:
        df = historical_store.load_ohlcv(sym)
        if len(df) >= 200:
            df["date"] = pd.to_datetime(df["date"] if "date" in df.columns else df.index).date
            dfs[sym] = df

    all_trading_days = sorted(list(set(
        d for df in dfs.values() for d in df["date"] if start_d <= d <= end_d
    )))

    all_candidates: List[Dict[str, Any]] = []
    portfolio_open_positions: List[Dict[str, Any]] = []
    MAX_CONCURRENT_POSITIONS = 5
    MAX_PER_SECTOR = 2

    for day in all_trading_days:
        # 1. Update/exit open positions
        active_positions = []
        for pos in portfolio_open_positions:
            if day >= pos["exit_date"]:
                # Position exited
                pass
            else:
                active_positions.append(pos)
        portfolio_open_positions = active_positions

        # 2. Daily Scan on Day D
        day_candidates = []
        sub_nifty = nifty_df[pd.to_datetime(nifty_df.index).date <= day] if not nifty_df.empty else None

        for sym, df in dfs.items():
            if day not in df["date"].values:
                continue

            sub_df = df[df["date"] <= day]
            if len(sub_df) < 200:
                continue

            cand = engine.evaluate(sym, sub_df, sub_nifty)
            if not cand:
                continue

            fut_df = df[df["date"] >= day]
            if len(fut_df) < 2:
                continue

            # Prior probability and EV_R
            priors = get_setup_empirical_priors()
            prior = priors.get(cand.setup_tag, {})
            p_target = prior.get("p_target", 0.45)
            p_stop = prior.get("p_stop", 0.40)
            p_expired = prior.get("p_expired", 0.15)
            e_r_expired = prior.get("e_r_expired", 0.05)
            cost_r = 0.06
            target_r = (cand.target_price - cand.entry_price) / max(1.0, cand.entry_price - cand.stop_loss)

            ev_r = round(p_target * target_r - p_stop * 1.0 + p_expired * e_r_expired - cost_r, 3)

            # Mansfield RS
            bench_close = sub_nifty["close"] if sub_nifty is not None and not sub_nifty.empty else sub_df["close"]
            mrs = compute_mansfield_relative_strength(sub_df["close"], bench_close, 20).iloc[-1]

            # Grade trade outcome
            graded = grade_trade_outcome(
                symbol=sym,
                entry_date=fut_df["date"].iloc[1],
                entry_price=float(fut_df["open"].iloc[1]),
                stop_loss=cand.stop_loss,
                target_price=cand.target_price,
                quantity=max(1, int(50000 / fut_df["open"].iloc[1])),
                time_limit_days=cand.time_limit_days,
                history_df=fut_df.iloc[1:cand.time_limit_days+2],
                entry_at_open=True,
            )

            exit_dt = graded.get("exit_date", fut_df["date"].iloc[-1])
            exit_date = exit_dt if isinstance(exit_dt, datetime.date) else pd.Timestamp(exit_dt).date()

            cand_rec = {
                "symbol": sym,
                "scan_date": day,
                "entry_date": fut_df["date"].iloc[1],
                "year": fut_df["date"].iloc[1].year,
                "setup_tag": cand.setup_tag,
                "ev_r": ev_r,
                "win_probability": p_target,
                "mansfield_rs": float(mrs),
                "net_pnl_r": float(graded.get("net_pnl_r", 0.0)),
                "exit_date": exit_date,
                "status": graded.get("status", "UNKNOWN"),
                "taken": False,
                "rejection_reason": None,
            }
            day_candidates.append(cand_rec)

        # 3. Rank candidates using Day D point-in-time criteria
        ranked_candidates = rank_candidates(day_candidates)

        # 4. Allocate into portfolio subject to limits
        for cand in ranked_candidates:
            if len(portfolio_open_positions) >= MAX_CONCURRENT_POSITIONS:
                cand["taken"] = False
                cand["rejection_reason"] = "MAX_PORTFOLIO_CAP_REACHED"
            elif cand["ev_r"] < 0.20:
                cand["taken"] = False
                cand["rejection_reason"] = "EV_R_BELOW_THRESHOLD"
            else:
                cand["taken"] = True
                cand["rejection_reason"] = None
                portfolio_open_positions.append(cand)

            all_candidates.append(cand)

    logger.info(f"Processed {len(all_candidates)} total candidates. Aggregating by year and setup...")

    # Aggregations by Year and Setup
    years = sorted(list(set(c["year"] for c in all_candidates)))
    setups = ["pullback_ema", "breakout_52w", "mean_reversion_rsi"]

    annual_attribution = {}
    for yr in years:
        annual_attribution[str(yr)] = {}
        yr_cands = [c for c in all_candidates if c["year"] == yr]

        for st in setups:
            st_cands = [c for c in yr_cands if c["setup_tag"] == st]
            taken = [c for c in st_cands if c["taken"]]
            rejected = [c for c in st_cands if not c["taken"]]

            annual_attribution[str(yr)][st] = {
                "all_candidates": compute_week_block_bootstrap_ci([c["net_pnl_r"] for c in st_cands], [c["entry_date"] for c in st_cands]),
                "taken_only": compute_week_block_bootstrap_ci([c["net_pnl_r"] for c in taken], [c["entry_date"] for c in taken]),
                "rejected_only": compute_week_block_bootstrap_ci([c["net_pnl_r"] for c in rejected], [c["entry_date"] for c in rejected]),
            }

    # Summary Totals
    total_taken = [c for c in all_candidates if c["taken"]]
    total_rejected = [c for c in all_candidates if not c["taken"]]

    report_payload = {
        "report_type": "CANDIDATE_LEVEL_ANNUAL_ATTRIBUTION",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "ranking_criteria": {
            "primary": "EV_R descending (Three-outcome risk-adjusted mathematical expectation)",
            "secondary": "Calibrated Win Probability descending",
            "tertiary": "Mansfield Relative Strength vs NIFTY 50 descending",
            "lookahead_guarantee": "Strictly uses Day D closing prices; zero future data accessible during ranking.",
        },
        "totals": {
            "all_candidates": compute_week_block_bootstrap_ci([c["net_pnl_r"] for c in all_candidates], [c["entry_date"] for c in all_candidates]),
            "taken_only": compute_week_block_bootstrap_ci([c["net_pnl_r"] for c in total_taken], [c["entry_date"] for c in total_taken]),
            "rejected_only": compute_week_block_bootstrap_ci([c["net_pnl_r"] for c in total_rejected], [c["entry_date"] for c in total_rejected]),
        },
        "annual_breakdown": annual_attribution,
        "selection_edge_r": round(
            float(np.mean([c["net_pnl_r"] for c in total_taken])) - float(np.mean([c["net_pnl_r"] for c in total_rejected])),
            4
        ),
        "status": "DONE",
    }

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report_payload, f, indent=2)

    logger.info(f"Report written to {REPORT_FILE}")
    print(f"Taken Candidates: {len(total_taken)} (Mean Net R: {report_payload['totals']['taken_only']['mean']} R)")
    print(f"Rejected Candidates: {len(total_rejected)} (Mean Net R: {report_payload['totals']['rejected_only']['mean']} R)")
    print(f"Selection Edge: {report_payload['selection_edge_r']:+0.4f} R")
    return report_payload


if __name__ == "__main__":
    generate_candidate_report()
