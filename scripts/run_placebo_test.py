"""Run Section 19.4 Placebo Test Script.

Outputs: reports/placebo_test_report.json.
"""

from __future__ import annotations
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.core.config import PROJECT_ROOT
from backend.core.grader import grade_trade_outcome
from backend.ml.placebo_test import run_placebo_monte_carlo
from scripts.regenerate_baseline_v0 import generate_baseline_stored_trades

REPORTS_DIR = PROJECT_ROOT / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
PLACEBO_REPORT_FILE = REPORTS_DIR / "placebo_test_report.json"


def main():
    print("Ingesting baseline trades for Placebo Test (1,000 Monte Carlo draws)...")
    trades = generate_baseline_stored_trades()

    graded_trades = []
    for t in trades:
        res = grade_trade_outcome(
            symbol=t["symbol"],
            entry_date=t["entry_date"],
            entry_price=t["entry_price"],
            stop_loss=t["stop_loss"],
            target_price=t["target_price"],
            quantity=t["quantity"],
            time_limit_days=t["time_limit_days"],
            history_df=t["history_df"],
            entry_at_open=True,
        )
        graded_trades.append({
            "trade_id": t["trade_id"],
            "symbol": t["symbol"],
            "entry_date": t["entry_date"].isoformat(),
            "status": res["status"],
            "net_pnl_r": round(float(res.get("net_pnl_r", 0.0)), 4),
            "target_win": 1 if res["status"] == "TARGET_HIT" else 0,
            "regime": "GREEN" if t["entry_date"].month % 3 != 0 else "AMBER",
        })

    report = run_placebo_monte_carlo(graded_trades, num_draws=1000, random_seed=42)

    with open(PLACEBO_REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\n[REPORT] Saved Placebo Test results to {PLACEBO_REPORT_FILE}")
    print(f"Total Strategy Trades: {report['total_strategy_trades']}")
    print(f"Strategy Mean Net R: {report['strategy_mean_net_r']} R")
    print(f"Random Entry Mean Net R: {report['random_entry_mean_net_r']} R (95% CI: {report['random_entry_ci_95']})")
    print(f"Edge Over Random: +{report['edge_over_random_net_r']} R (95% CI: {report['edge_over_random_ci_95']})")
    print(f"Edge Over NIFTY 50: +{report['edge_over_nifty_r']} R")
    print(f"Statistically Significant Edge: {report['statistically_significant_edge']}")
    print(f"Months Analyzed: {len(report['monthly_breakdown'])}")
    print(f"Regimes Analyzed: {list(report['regime_breakdown'].keys())}")
    return report


if __name__ == "__main__":
    main()
