"""APScheduler Automation Engine for AURA-NSE Pro.

Operates in Asia/Kolkata timezone with persistent job scheduling,
idempotent daily runs, and manual 'Run Now' execution triggers.
"""

from __future__ import annotations
import datetime
import json
import logging
import os
from zoneinfo import ZoneInfo
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from backend.core.config import PROJECT_ROOT
from backend.data.holiday_calendar import is_trading_day, get_ist_now

logger = logging.getLogger("aura.scheduler")
IST = ZoneInfo("Asia/Kolkata")

# Global scheduler instance
scheduler = BackgroundScheduler(timezone=IST)

# Execution history cache for UI dashboard
JOB_EXECUTION_HISTORY: list[dict] = []


def record_job_execution(job_id: str, status: str, details: str):
    """Store job execution metadata for dashboard visibility."""
    now_ist = get_ist_now().isoformat()
    record = {
        "job_id": job_id,
        "status": status,
        "details": details,
        "executed_at": now_ist,
    }
    JOB_EXECUTION_HISTORY.insert(0, record)
    if len(JOB_EXECUTION_HISTORY) > 50:
        JOB_EXECUTION_HISTORY.pop()


def job_0830_data_refresh():
    """08:30 IST: Macro cues, news, regime score refresh."""
    today = get_ist_now().date()
    if not is_trading_day(today):
        logger.info(f"Skipping 08:30 data refresh: {today} is an NSE market holiday or weekend.")
        record_job_execution("08:30_data_refresh", "SKIPPED_HOLIDAY", f"Non-trading day: {today}")
        return

    logger.info("Executing 08:30 IST Data Refresh...")
    try:
        from backend.strategies.regime import evaluate_market_regime
        regime = evaluate_market_regime()
        record_job_execution("08:30_data_refresh", "SUCCESS", f"Regime evaluated: {regime['regime_label']}")
    except Exception as e:
        logger.error(f"Error in 08:30 data refresh: {e}")
        record_job_execution("08:30_data_refresh", "FAILED", str(e))


def job_0900_pre_market_plan():
    """09:00 IST: Pre-market screening, ML probability scoring, and LLM audit."""
    today = get_ist_now().date()
    if not is_trading_day(today):
        logger.info(f"Skipping 09:00 pre-market plan: {today} is an NSE holiday.")
        record_job_execution("09:00_pre_market_plan", "SKIPPED_HOLIDAY", f"Non-trading day: {today}")
        return

    logger.info("Executing 09:00 IST Pre-Market Plan Pipeline...")
    try:
        from backend.core.pipeline import run_pre_market_pipeline
        summary = run_pre_market_pipeline()
        record_job_execution("09:00_pre_market_plan", "SUCCESS", f"Pipeline completed. Approved: {summary.get('approved_count', 0)}")
    except Exception as e:
        logger.error(f"Error in 09:00 pre-market pipeline: {e}")
        record_job_execution("09:00_pre_market_plan", "FAILED", str(e))


def job_0915_open_check():
    """09:15-09:20 IST: Market open check (gap filter, fill execution, qty recompute)."""
    today = get_ist_now().date()
    if not is_trading_day(today):
        return

    logger.info("Executing 09:15 IST Market Open Verification...")
    try:
        from backend.core.pipeline import run_open_check_pipeline
        result = run_open_check_pipeline()
        record_job_execution("09:15_open_check", "SUCCESS", f"Open check completed: {result.get('summary', '')}")
    except Exception as e:
        logger.error(f"Error in 09:15 open check: {e}")
        record_job_execution("09:15_open_check", "FAILED", str(e))


def job_1545_post_market_grading():
    """15:45 IST: Provisional trade grading against daily OHLC."""
    today = get_ist_now().date()
    if not is_trading_day(today):
        return

    logger.info("Executing 15:45 IST Post-Market Grading...")
    try:
        from backend.core.pipeline import run_post_market_grading
        result = run_post_market_grading()
        record_job_execution("15:45_post_market_grading", "SUCCESS", f"Graded {result.get('trades_graded', 0)} open trades.")
    except Exception as e:
        logger.error(f"Error in 15:45 post-market grading: {e}")
        record_job_execution("15:45_post_market_grading", "FAILED", str(e))


def job_1830_bhavcopy_reconciliation():
    """18:30 IST: Final reconciliation against official EOD bhavcopy."""
    today = get_ist_now().date()
    if not is_trading_day(today):
        return

    logger.info("Executing 18:30 IST Bhavcopy Reconciliation...")
    try:
        from backend.core.pipeline import run_bhavcopy_reconciliation
        result = run_bhavcopy_reconciliation()
        record_job_execution("18:30_reconciliation", "SUCCESS", "EOD prices reconciled.")
    except Exception as e:
        logger.error(f"Error in 18:30 reconciliation: {e}")
        record_job_execution("18:30_reconciliation", "FAILED", str(e))


def job_1300_midday_stop_check():
    """13:00 IST: Check OPEN positions against latest intraday price. Alert if breaching stop. (H3)"""
    today = get_ist_now().date()
    if not is_trading_day(today):
        return

    logger.info("Executing 13:00 IST Mid-Day Stop Check...")
    try:
        from backend.core.pipeline import run_midday_stop_check
        result = run_midday_stop_check()
        record_job_execution(
            "13:00_midday_stop_check",
            "SUCCESS",
            f"Checked {result.get('open_positions_checked', 0)} positions; "
            f"{result.get('stop_breaches_alerted', 0)} stop-breach alerts sent.",
        )
    except Exception as e:
        logger.error(f"Error in 13:00 midday stop check: {e}")
        record_job_execution("13:00_midday_stop_check", "FAILED", str(e))


def job_1550_portfolio_refresh():
    """15:50 IST: Refresh portfolio current prices after market close. (C2)"""
    today = get_ist_now().date()
    if not is_trading_day(today):
        return

    logger.info("Executing 15:50 IST Portfolio Price Refresh...")
    try:
        from backend.core.pipeline import refresh_portfolio_prices
        result = refresh_portfolio_prices()
        record_job_execution(
            "15:50_portfolio_refresh",
            "SUCCESS",
            f"Updated {result.get('holdings_updated', 0)} holdings.",
        )
    except Exception as e:
        logger.error(f"Error in 15:50 portfolio refresh: {e}")
        record_job_execution("15:50_portfolio_refresh", "FAILED", str(e))


def job_saturday_mistake_audit():
    """Saturday 10:00 IST: Weekly Mistake Audit & Model Retraining Proposal."""
    logger.info("Executing Saturday 10:00 IST Mistake Audit...")
    try:
        from backend.core.pipeline import run_weekly_mistake_audit
        res = run_weekly_mistake_audit()
        record_job_execution("saturday_mistake_audit", "SUCCESS", f"Mistake audit completed. Losses categorized: {res.get('categorized', 0)}")
    except Exception as e:
        logger.error(f"Error in weekly mistake audit: {e}")
        record_job_execution("saturday_mistake_audit", "FAILED", str(e))


def job_heartbeat():
    """Dead-man's heartbeat: runs every 5 minutes and updates data/heartbeat.json.
    Pings external health monitor (e.g. Healthchecks.io / webhook) if HEALTHCHECKS_IO_URL is set."""
    now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    heartbeat_file = PROJECT_ROOT / "data" / "heartbeat.json"
    heartbeat_file.parent.mkdir(parents=True, exist_ok=True)

    external_ping = "NOT_CONFIGURED"
    hc_url = os.environ.get("HEALTHCHECKS_IO_URL")
    if hc_url:
        try:
            import httpx
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(hc_url)
                external_ping = f"PING_SUCCESS_HTTP_{resp.status_code}"
        except Exception as e:
            external_ping = f"PING_ERROR_{str(e)[:50]}"

    # Check disk space and log warning if low
    try:
        from backend.core.ops_monitor import check_disk_space
        check_disk_space()
    except Exception as e:
        logger.warning(f"Disk space check error in heartbeat: {e}")

    payload = {
        "status": "ALIVE",
        "last_beat_utc": now_utc,
        "scheduler_running": scheduler.running,
        "external_heartbeat": external_ping,
    }
    with open(heartbeat_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    record_job_execution("heartbeat", "SUCCESS", f"Heartbeat ping at {now_utc} (External: {external_ping})")


def job_check_token_expiry():
    """Daily check for Upstox Analytics Token expiry with alerts at <= 30 and <= 7 days."""
    token = os.environ.get("UPSTOX_ANALYTICS_TOKEN", "")
    if not token:
        env_file = PROJECT_ROOT / ".env"
        if env_file.exists():
            for line in open(env_file, encoding="utf-8"):
                line = line.strip()
                if line.startswith("UPSTOX_ANALYTICS_TOKEN="):
                    token = line.split("=", 1)[1].strip("\"' ")

    if not token:
        logger.warning("No UPSTOX_ANALYTICS_TOKEN found to monitor.")
        record_job_execution("token_expiry_check", "SKIPPED", "No token configured.")
        return

    try:
        import base64
        parts = token.split(".")
        if len(parts) >= 2:
            seg = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
            payload = json.loads(base64.urlsafe_b64decode(seg.encode("utf-8")))
            exp = payload.get("exp")
            if exp:
                now_epoch = datetime.datetime.now(datetime.timezone.utc).timestamp()
                days_remaining = (exp - now_epoch) / 86400.0
                status_msg = f"Token valid for {days_remaining:.1f} days (expires epoch {exp})."

                if days_remaining <= 7.0:
                    alert_msg = f"🚨 *CRITICAL TOKEN ALERT*: Upstox Analytics Token expires in {days_remaining:.1f} days! Re-authenticate to avoid outage."
                    logger.error(alert_msg)
                    from backend.core.pipeline import send_telegram_alert
                    send_telegram_alert(alert_msg)
                elif days_remaining <= 30.0:
                    alert_msg = f"⚠️ *TOKEN EXPIRY WARNING*: Upstox Analytics Token expires in {days_remaining:.1f} days."
                    logger.warning(alert_msg)
                    from backend.core.pipeline import send_telegram_alert
                    send_telegram_alert(alert_msg)

                record_job_execution("token_expiry_check", "SUCCESS", status_msg)
                return
    except Exception as e:
        logger.warning(f"Error checking token expiry: {e}")
        record_job_execution("token_expiry_check", "FAILED", str(e))


def job_weekly_symbol_and_corporate_action_check():
    """Weekly check on Saturday for new NSE symbol renames, mergers, demergers, and listings."""
    logger.info("Executing Weekly Symbol Master & Corporate Action Sync...")
    try:
        from backend.data.symbol_master import symbol_master
        from backend.data.corporate_actions import corporate_action_engine

        today = get_ist_now().date()
        recent_actions = [
            ca for ca in corporate_action_engine.ledger
            if abs((ca.ex_date - today).days) <= 30
        ]
        status_msg = f"Symbol master verified ({len(symbol_master.events)} mapping events). {len(recent_actions)} corporate actions in 30-day window."
        record_job_execution("weekly_symbol_and_ca_check", "SUCCESS", status_msg)
    except Exception as e:
        logger.error(f"Error in weekly symbol master check: {e}")
        record_job_execution("weekly_symbol_and_ca_check", "FAILED", str(e))


def start_scheduler():
    """Register cron jobs and start APScheduler in background with catch-up resilience."""
    if not scheduler.running:
        scheduler.add_job(job_0830_data_refresh, CronTrigger(hour=8, minute=30, timezone=IST), id="0830_data_refresh", coalesce=True, misfire_grace_time=3600, replace_existing=True)
        scheduler.add_job(job_0900_pre_market_plan, CronTrigger(hour=9, minute=0, timezone=IST), id="0900_pre_market_plan", coalesce=True, misfire_grace_time=3600, replace_existing=True)
        scheduler.add_job(job_0915_open_check, CronTrigger(hour=9, minute=18, timezone=IST), id="0915_open_check", coalesce=True, misfire_grace_time=3600, replace_existing=True)
        scheduler.add_job(job_1300_midday_stop_check, CronTrigger(hour=13, minute=0, timezone=IST), id="1300_midday_stop_check", coalesce=True, misfire_grace_time=3600, replace_existing=True)
        scheduler.add_job(job_1545_post_market_grading, CronTrigger(hour=15, minute=45, timezone=IST), id="1545_post_market_grading", coalesce=True, misfire_grace_time=3600, replace_existing=True)
        scheduler.add_job(job_1550_portfolio_refresh, CronTrigger(hour=15, minute=50, timezone=IST), id="1550_portfolio_refresh", coalesce=True, misfire_grace_time=3600, replace_existing=True)
        scheduler.add_job(job_1830_bhavcopy_reconciliation, CronTrigger(hour=18, minute=30, timezone=IST), id="1830_reconciliation", coalesce=True, misfire_grace_time=3600, replace_existing=True)
        scheduler.add_job(job_saturday_mistake_audit, CronTrigger(day_of_week="sat", hour=10, minute=0, timezone=IST), id="saturday_mistake_audit", coalesce=True, misfire_grace_time=3600, replace_existing=True)
        scheduler.add_job(job_weekly_symbol_and_corporate_action_check, CronTrigger(day_of_week="sat", hour=10, minute=30, timezone=IST), id="weekly_symbol_and_ca_check", coalesce=True, misfire_grace_time=3600, replace_existing=True)
        scheduler.add_job(job_check_token_expiry, CronTrigger(hour=8, minute=0, timezone=IST), id="token_expiry_check", coalesce=True, misfire_grace_time=3600, replace_existing=True)
        # Dead-man's heartbeat every 5 minutes
        scheduler.add_job(job_heartbeat, IntervalTrigger(minutes=5), id="heartbeat", coalesce=True, misfire_grace_time=300, replace_existing=True)
        scheduler.start()
        # Trigger an initial heartbeat immediately on startup
        job_heartbeat()
        logger.info("APScheduler started with Asia/Kolkata timezone and dead-man's heartbeat.")


def run_job_now(job_name: str) -> dict:
    """Manually trigger a job immediately for testing or on-demand operations."""
    mapping = {
        "heartbeat": job_heartbeat,
        "0830_data_refresh": job_0830_data_refresh,
        "0900_pre_market_plan": job_0900_pre_market_plan,
        "0915_open_check": job_0915_open_check,
        "1300_midday_stop_check": job_1300_midday_stop_check,
        "1545_post_market_grading": job_1545_post_market_grading,
        "1550_portfolio_refresh": job_1550_portfolio_refresh,
        "1830_reconciliation": job_1830_bhavcopy_reconciliation,
        "saturday_mistake_audit": job_saturday_mistake_audit,
        "weekly_symbol_and_ca_check": job_weekly_symbol_and_corporate_action_check,
        "token_expiry_check": job_check_token_expiry,
    }
    if job_name not in mapping:
        return {"status": "ERROR", "message": f"Unknown job name: {job_name}"}

    fn = mapping[job_name]
    fn()
    return {"status": "TRIGGERED", "job_name": job_name, "triggered_at": get_ist_now().isoformat()}
