"""Phase P7 Operational Resilience Tests: Backup/Restore, Scheduler Catch-Up, Heartbeat, and Frontend Dist.

Validates:
1. Online SQLite backup creation via SQLite backup API and PRAGMA integrity verification on restore.
2. Dead-man's heartbeat generation and health monitor endpoint.
3. APScheduler catch-up flags (coalesce=True, misfire_grace_time >= 300).
4. Frontend build output (frontend/dist/index.html, JS/CSS bundles, pre-exported snapshots).
"""

from __future__ import annotations
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.core.config import PROJECT_ROOT
from backend.main import app
from backend.jobs.scheduler import job_heartbeat, scheduler, start_scheduler
from scripts.backup_db import backup_database, restore_database


client = TestClient(app)


def test_sqlite_online_backup_and_restore(tmp_path):
    """Verify that SQLite online backup creates a valid copy and restore passes integrity check."""
    backup_file = tmp_path / "test_backup.db"
    created = backup_database(destination_path=backup_file)
    assert created.exists()
    assert created.stat().st_size > 0

    # Restore from the temporary backup
    res = restore_database(created)
    assert res["status"] == "RESTORED"
    assert res["integrity"] == "ok"


def test_dead_mans_heartbeat_and_endpoint():
    """Verify dead-man's heartbeat updates file and endpoint responds ALIVE."""
    job_heartbeat()
    hb_file = PROJECT_ROOT / "data" / "heartbeat.json"
    assert hb_file.exists()

    with open(hb_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["status"] == "ALIVE"
    assert "last_beat_utc" in data

    # Test API endpoint
    resp = client.get("/api/health/heartbeat")
    assert resp.status_code == 200
    res_json = resp.json()
    assert res_json["status"] == "ALIVE"
    assert res_json["seconds_since_last_beat"] < 10.0
    assert res_json["coalesce_enabled"] is True
    assert res_json["misfire_grace_seconds"] == 3600


def test_scheduler_catchup_configuration():
    """Verify APScheduler jobs have coalesce=True and misfire_grace_time configured."""
    start_scheduler()
    job = scheduler.get_job("0900_pre_market_plan")
    assert job is not None
    assert job.coalesce is True
    assert job.misfire_grace_time == 3600

    hb_job = scheduler.get_job("heartbeat")
    assert hb_job is not None
    assert hb_job.coalesce is True


def test_frontend_dist_and_static_snapshots_ready():
    """Verify frontend/dist exists with production bundles and all required data snapshots."""
    dist_dir = PROJECT_ROOT / "frontend" / "dist"
    if not dist_dir.exists():
        pytest.skip("frontend/dist is generated during frontend-build CI phase")
    assert (dist_dir / "index.html").exists()

    assets_dir = dist_dir / "assets"
    assert assets_dir.exists()
    js_files = list(assets_dir.glob("*.js"))
    css_files = list(assets_dir.glob("*.css"))
    assert len(js_files) >= 1
    assert len(css_files) >= 1

    # Static data snapshots
    data_dir = dist_dir / "data"
    assert data_dir.exists()
    required_snapshots = [
        "today_predictions.json",
        "market_status.json",
        "regime.json",
        "accuracy_tracker.json",
        "fii_dii.json",
        "sector_matrix.json",
        "mistakes.json",
        "stress_metrics.json",
    ]
    for snap in required_snapshots:
        snap_path = data_dir / snap
        assert snap_path.exists(), f"Snapshot {snap} missing from dist/data"
