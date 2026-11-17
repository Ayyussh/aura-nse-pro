"""SQLite WAL-Safe Database Backup & Restore Utility (Section 12 / P7 Operational Resilience).

Implements online backup via sqlite3.Connection.backup() ensuring zero-downtime,
consistent snapshots even under active WAL write transactions.
"""

from __future__ import annotations
import datetime
import logging
from pathlib import Path
import sqlite3
import sys
from typing import Dict, Any, Optional

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from backend.core.config import PROJECT_ROOT

logger = logging.getLogger("aura.backup")
DB_PATH = PROJECT_ROOT / "backend" / "aura_nse.db"
BACKUP_DIR = PROJECT_ROOT / "data" / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def backup_database(destination_path: Optional[Path] = None) -> Path:
    """Create a consistent snapshot using SQLite Online Backup API."""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database file not found at {DB_PATH}")

    if destination_path is None:
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
        destination_path = BACKUP_DIR / f"aura_nse_backup_{timestamp}.db"

    destination_path.parent.mkdir(parents=True, exist_ok=True)

    src = sqlite3.connect(str(DB_PATH))
    dst = sqlite3.connect(str(destination_path))
    try:
        # SQLite Online Backup API handles WAL seamlessly
        src.backup(dst, pages=100)
    finally:
        dst.close()
        src.close()

    logger.info(f"Database successfully backed up to {destination_path}")
    return destination_path


def restore_database(backup_path: Path) -> Dict[str, Any]:
    """Restore database from backup snapshot after verifying integrity."""
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup file not found at {backup_path}")

    # 1. Verify backup file integrity
    test_conn = sqlite3.connect(str(backup_path))
    try:
        cursor = test_conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        res = cursor.fetchone()
        if not res or res[0] != "ok":
            raise ValueError(f"Integrity check failed for backup {backup_path}: {res}")
    finally:
        test_conn.close()

    # 2. Restore by copying snapshot to DB_PATH using backup API
    src = sqlite3.connect(str(backup_path))
    dst = sqlite3.connect(str(DB_PATH))
    try:
        src.backup(dst, pages=100)
    finally:
        dst.close()
        src.close()

    logger.info(f"Database successfully restored from {backup_path}")
    return {
        "status": "RESTORED",
        "backup_path": str(backup_path),
        "restored_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "integrity": "ok",
    }


if __name__ == "__main__":
    b_path = backup_database()
    print(f"Backed up to: {b_path}")
    verify = restore_database(b_path)
    print(f"Restore verification: {verify}")
