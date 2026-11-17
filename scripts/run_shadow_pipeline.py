"""Phase P7 & P9: Live Shadow Mode Pipeline Runner.

Executes a live daily pre-market cycle:
1. Macro regime check.
2. Quality gate & data reconciliation run-gate check.
3. High-conviction swing screening with anti-chase guard.
4. ML probability scoring & three-outcome EV_R gate.
5. Bull/Bear LLM audit with negative few-shot mistake avoidance.
6. Position sizing, tax, and charge computation.
7. Cryptographic audit hashing with immutable SQLite triggers.
8. ALL picks logged with source="SHADOW" and is_shadow=True.
9. ZERO broker orders placed (Decision Support Only).

Outputs: reports/shadow_mode_status.json
"""

from __future__ import annotations
import datetime
import json
import logging
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from backend.core.config import PROJECT_ROOT
from backend.core.pipeline import run_pre_market_pipeline
from backend.data.holiday_calendar import get_ist_now
from backend.db.session import SessionLocal
from backend.db.models import Prediction

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("aura.shadow")

REPORTS_DIR = PROJECT_ROOT / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
SHADOW_STATUS_FILE = REPORTS_DIR / "shadow_mode_status.json"


def execute_live_shadow_cycle(universe_limit: int = 15) -> dict:
    """Run live daily shadow mode execution."""
    logger.info("Initializing Live Shadow Mode Run...")

    # Run the pre-market screening with is_shadow=True and force=True for off-hours test execution
    summary = run_pre_market_pipeline(universe_limit=universe_limit, force=True, is_shadow=True)

    db = SessionLocal()
    try:
        shadow_preds = db.query(Prediction).filter(Prediction.source == "SHADOW").order_by(Prediction.id.desc()).limit(20).all()
        shadow_records = [
            {
                "id": p.id,
                "symbol": p.symbol,
                "entry_price": p.entry_price,
                "stop_loss": p.stop_loss,
                "target_price": p.target_price,
                "quantity": p.quantity,
                "win_probability": p.win_probability,
                "ev_r": p.ev_r,
                "llm_verdict": p.llm_verdict,
                "source": p.source,
                "is_shadow": p.is_shadow,
                "audit_hash": p.audit_hash[:16] + "..." if p.audit_hash else None,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in shadow_preds
        ]
    finally:
        db.close()

    status_report = {
        "mode": "LIVE_SHADOW_MODE",
        "status": "ACTIVE_RUNNING",
        "timestamp_ist": get_ist_now().strftime("%Y-%m-%d %H:%M:%S IST"),
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "broker_order_execution": "DISABLED (Decision Support Only - Zero Orders Placed)",
        "pipeline_summary": summary,
        "recent_shadow_picks_count": len(shadow_records),
        "recent_shadow_picks": shadow_records[:5],
        "compliance_footer": "Educational decision support, not investment advice. Backtests and paper results do not guarantee future returns.",
    }

    with open(SHADOW_STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status_report, f, indent=2)

    logger.info(f"Live Shadow Mode executed successfully. Report written to {SHADOW_STATUS_FILE}")
    return status_report


if __name__ == "__main__":
    execute_live_shadow_cycle()
