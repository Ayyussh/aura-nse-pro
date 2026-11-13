"""APScheduler Automation Engine for AURA-NSE Pro.

Operates in Asia/Kolkata timezone with persistent job scheduling,
idempotent daily runs, and manual 'Run Now' execution triggers.
"""

from __future__ import annotations
import datetime
import logging
from zoneinfo import ZoneInfo
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

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


def start_scheduler():
    """Register cron jobs and start APScheduler in background."""
    if not scheduler.running:
        scheduler.add_job(job_0830_data_refresh, CronTrigger(hour=8, minute=30, timezone=IST), id="0830_data_refresh", replace_existing=True)
        scheduler.add_job(job_0900_pre_market_plan, CronTrigger(hour=9, minute=0, timezone=IST), id="0900_pre_market_plan", replace_existing=True)
        scheduler.add_job(job_0915_open_check, CronTrigger(hour=9, minute=18, timezone=IST), id="0915_open_check", replace_existing=True)
        scheduler.add_job(job_1545_post_market_grading, CronTrigger(hour=15, minute=45, timezone=IST), id="1545_post_market_grading", replace_existing=True)
        scheduler.add_job(job_1830_bhavcopy_reconciliation, CronTrigger(hour=18, minute=30, timezone=IST), id="1830_reconciliation", replace_existing=True)
        scheduler.add_job(job_saturday_mistake_audit, CronTrigger(day_of_week="sat", hour=10, minute=0, timezone=IST), id="saturday_mistake_audit", replace_existing=True)
        scheduler.start()
        logger.info("APScheduler started with Asia/Kolkata timezone.")


def run_job_now(job_name: str) -> dict:
    """Manually trigger a job immediately for testing or on-demand operations."""
    mapping = {
        "0830_data_refresh": job_0830_data_refresh,
        "0900_pre_market_plan": job_0900_pre_market_plan,
        "0915_open_check": job_0915_open_check,
        "1545_post_market_grading": job_1545_post_market_grading,
        "1830_reconciliation": job_1830_bhavcopy_reconciliation,
        "saturday_mistake_audit": job_saturday_mistake_audit,
    }
    if job_name not in mapping:
        return {"status": "ERROR", "message": f"Unknown job name: {job_name}"}

    fn = mapping[job_name]
    fn()
    return {"status": "TRIGGERED", "job_name": job_name, "triggered_at": get_ist_now().isoformat()}
