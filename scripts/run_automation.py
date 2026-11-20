"""AURA-NSE Pro Headless Automation CLI for GitHub Actions & Server Schedulers.

Usage:
    python scripts/run_automation.py --mode premarket
    python scripts/run_automation.py --mode open_check
    python scripts/run_automation.py --mode postmarket
    python scripts/run_automation.py --mode retrain
    python scripts/run_automation.py --mode full_cycle [--force]
"""

import argparse
import datetime
import logging
import os
import sys
import httpx

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.core.config import settings
from backend.data.holiday_calendar import is_trading_day, get_ist_now
from backend.core.pipeline import (
    run_pre_market_pipeline,
    run_open_check_pipeline,
    run_midday_stop_check,
    run_post_market_grading,
    refresh_portfolio_prices,
    run_bhavcopy_reconciliation,
    run_weekly_mistake_audit,
    run_value_investing_scan,
)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("aura.cli")


def ping_heartbeat(url: str, status: str = "ok", message: str = ""):
    """Send Dead-Man's Switch heartbeat ping to Healthchecks.io / Better Stack."""
    if not url:
        return
    try:
        ping_url = f"{url.rstrip('/')}/{status}" if status != "ok" else url
        with httpx.Client(timeout=5.0) as client:
            client.post(ping_url, content=message)
            logger.info("Heartbeat ping sent successfully.")
    except Exception as e:
        logger.warning(f"Could not send heartbeat ping: {e}")


def main():
    parser = argparse.ArgumentParser(description="AURA-NSE Pro Headless Automation Engine")
    parser.add_argument(
        "--mode",
        choices=["premarket", "open_check", "midday", "postmarket", "refresh_portfolio", "eod_recon", "retrain", "full_cycle", "value_scan", "eod_master"],
        required=True,
        help="Automation phase to execute",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=750,
        help="Universe scan candidate limit (default: 750 across institutional universe)",
    )
    parser.add_argument(
        "--universe-mode",
        choices=["all", "diversified", "curated"],
        default="all",
        help="Universe scope: 'all' (all 2,760 listed NSE stocks), 'diversified' (bluechips), 'curated' (191)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force execution even if current day is a holiday/weekend",
    )
    args = parser.parse_args()

    now_ist = get_ist_now()
    today = now_ist.date()
    logger.info(f"AURA Automation Started. Mode: '{args.mode}', IST Time: {now_ist.strftime('%Y-%m-%d %H:%M:%S IST')}")

    # Trading day check (Retrain is allowed on Saturday)
    if args.mode != "retrain" and not args.force:
        if not is_trading_day(today):
            logger.info(f"Today ({today}) is not an active NSE trading day (Weekend/Holiday). Exiting cleanly.")
            sys.exit(0)

    heartbeat_url = os.environ.get("HEALTHCHECKS_IO_URL") or getattr(settings, "HEALTHCHECKS_IO_URL", "")

    try:
        if args.mode == "premarket":
            scan_limit = args.limit or 750
            logger.info(f"Running Pre-Market Screening on top {scan_limit} candidates...")
            res = run_pre_market_pipeline(universe_limit=scan_limit, force=args.force)
            logger.info(f"Pre-Market Run Complete: {res.get('approved_count', 0)} Approved Setups, Regime: {res.get('regime', {}).get('regime_label')}")
            print("\n--- AURA Spoken Briefing ---")
            print(res.get("briefing_script", "No briefing generated."))

        elif args.mode == "open_check":
            logger.info("Running 09:15 AM IST Market Open Gap Verification...")
            res = run_open_check_pipeline()
            logger.info(f"Open Check Complete: {res.get('summary')}")

        elif args.mode == "midday":
            logger.info("Running 13:00 PM IST Mid-Day Stop Loss Monitoring...")
            res = run_midday_stop_check()
            logger.info(f"Mid-Day Check Complete: {res.get('open_positions_checked', 0)} checked, {res.get('stop_breaches_alerted', 0)} alerts sent.")

        elif args.mode == "postmarket":
            logger.info("Running 15:45 PM IST Post-Market Trade Grading...")
            res = run_post_market_grading()
            logger.info(f"Grading Complete: {res.get('trades_graded', 0)} trades resolved.")

        elif args.mode == "refresh_portfolio":
            logger.info("Running 15:50 PM IST Portfolio Holding Price Refresh...")
            res = refresh_portfolio_prices()
            logger.info(f"Portfolio Refresh Complete: {res.get('holdings_updated', 0)} holdings updated.")

        elif args.mode == "eod_recon":
            logger.info("Running 18:30 IST Official Bhavcopy Reconciliation...")
            res = run_bhavcopy_reconciliation()
            logger.info(f"Reconciliation Complete: {res.get('reconciliation')}")

        elif args.mode == "retrain":
            logger.info("Running Saturday Self-Improving Mistake Audit & ML Retraining...")
            res = run_weekly_mistake_audit()
            report = res.get("retraining_report", {})
            logger.info(
                f"Retraining Complete. Decision: {report.get('decision')}, "
                f"Active Version: {report.get('active_version')}, "
                f"Brier: {report.get('candidate_metrics', {}).get('brier_score')}"
            )

        elif args.mode == "full_cycle":
            logger.info("Running full end-to-end pipeline cycle...")
            run_pre_market_pipeline(universe_limit=args.limit or 750, force=args.force)
            run_open_check_pipeline()
            run_midday_stop_check()
            run_post_market_grading()
            refresh_portfolio_prices()
            run_weekly_mistake_audit()
            logger.info("Full Cycle Completed successfully.")

        elif args.mode == "value_scan":
            scan_limit = args.limit or 750
            logger.info(f"Running Long-Term Institutional Value Screener across '{args.universe_mode}' universe (limit={scan_limit})...")
            res = run_value_investing_scan(universe_limit=scan_limit, mode=args.universe_mode, send_alert=True)
            logger.info(f"Value Scan Complete: {res.get('undervalued_count', 0)} Undervalued Compounders identified from {res.get('total_screened', 0)} screened.")

        elif args.mode == "eod_master":
            logger.info("Running EOD Master Workflow (Portfolio Refresh + Trade Grading + Long-Term Quality Compounder Screener)...")
            # 1. Refresh holding prices with EOD close
            p_res = refresh_portfolio_prices()
            logger.info(f"Portfolio Refresh: {p_res.get('holdings_updated', 0)} holdings updated.")

            # 2. Grade any active/closed trades
            g_res = run_post_market_grading()
            logger.info(f"Post-Market Trade Grading: {g_res.get('trades_graded', 0)} trades graded.")

            # 3. Run Quality Compounders Screener (Long-Term Investing)
            scan_limit = args.limit or 750
            logger.info(f"Running Long-Term Quality Compounders to Invest Screener across '{args.universe_mode}' universe (limit={scan_limit})...")
            v_res = run_value_investing_scan(universe_limit=scan_limit, mode=args.universe_mode, send_alert=True)
            logger.info(f"Quality Compounders Identified: {v_res.get('undervalued_count', 0)} from {v_res.get('total_screened', 0)} screened.")

        # Always export latest static snapshots for serverless GitHub Pages dashboard
        try:
            from backend.data.static_exporter import export_all_static_snapshots
            export_all_static_snapshots()
            logger.info("Static GitOps analytics snapshots updated successfully.")
        except Exception as e:
            logger.warning(f"Could not export static snapshots: {e}")

        # Heartbeat success ping
        ping_heartbeat(heartbeat_url, status="ok", message=f"Mode {args.mode} executed successfully on {today}")
        logger.info("Automation task finished successfully.")

    except Exception as e:
        logger.error(f"Fatal error during '{args.mode}' execution: {e}", exc_info=True)
        ping_heartbeat(heartbeat_url, status="fail", message=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
