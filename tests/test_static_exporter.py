"""Unit Tests for Static GitOps Snapshot Exporter Engine.

Verifies that static JSON snapshots required for GitHub Pages serverless operation
are correctly generated, formatted, and non-empty.
"""

from __future__ import annotations
import json
from pathlib import Path
import pytest

from backend.core.config import PROJECT_ROOT
from backend.data.static_exporter import export_all_static_snapshots, EXPORT_DIRS


def test_export_all_static_snapshots_generates_required_files():
    """Verify that export_all_static_snapshots generates all core JSON files."""
    results = export_all_static_snapshots()
    assert isinstance(results, dict)
    assert "market_status" in results
    assert "regime" in results
    assert "today_predictions" in results
    assert "accuracy_tracker" in results
    assert "stress_metrics" in results

    public_dir = PROJECT_ROOT / "frontend" / "public" / "data"
    assert public_dir.exists(), "frontend/public/data must exist"

    expected_files = [
        "market_status.json",
        "regime.json",
        "today_predictions.json",
        "accuracy_tracker.json",
        "stress_metrics.json",
        "fii_dii.json",
        "sector_matrix.json",
        "portfolio.json",
        "mistakes.json",
    ]

    for fname in expected_files:
        fpath = public_dir / fname
        assert fpath.exists(), f"Snapshot file {fname} must exist in {public_dir}"
        assert fpath.stat().st_size > 0, f"Snapshot file {fname} must not be empty"

        # Verify valid JSON syntax
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data is not None


def test_today_predictions_snapshot_structure():
    """Verify that today_predictions.json has the structure required by the frontend."""
    public_dir = PROJECT_ROOT / "frontend" / "public" / "data"
    preds_file = public_dir / "today_predictions.json"
    assert preds_file.exists()

    with open(preds_file, "r", encoding="utf-8") as f:
        payload = json.load(f)

    assert "date" in payload
    assert "count" in payload
    assert "predictions" in payload
    assert "snapshot_updated_at" in payload
    assert isinstance(payload["predictions"], list)

    if len(payload["predictions"]) > 0:
        first = payload["predictions"][0]
        assert "symbol" in first
        assert "entry_price" in first
        assert "stop_loss" in first
        assert "target_price" in first
        assert "quantity" in first


def test_accuracy_tracker_snapshot_structure():
    """Verify accuracy_tracker.json fields match frontend expectations."""
    public_dir = PROJECT_ROOT / "frontend" / "public" / "data"
    acc_file = public_dir / "accuracy_tracker.json"
    assert acc_file.exists()

    with open(acc_file, "r", encoding="utf-8") as f:
        payload = json.load(f)

    assert "total_predictions" in payload
    assert "total_graded" in payload
    assert "true_predictions_count" in payload
    assert "false_predictions_count" in payload
    assert "true_prediction_rate_pct" in payload
    assert "avg_expectancy_r" in payload
    assert "history" in payload
    assert isinstance(payload["history"], list)
